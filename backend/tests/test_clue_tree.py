"""Phase A.4 — Evidence Tree 자료구조 + 단서 카탈로그 단위 테스트 (2026-05-25, byungwoo).

검증 대상:
    1. ClueTreeNode·ClueTree·ClueCandidate 생성·직렬화·역직렬화
    2. make_root / append_clue_node / set_candidates 트리 조작 헬퍼
    3. posterior_entropy (Shannon, 0 ≤ H ≤ 3.0 bits for 8 hypothesis)
    4. candidate_count_by_entropy 동적 후보 개수 (사용자 결정 — paradigm §16)
    5. evaluate_confidence 임계값 도달 시 notify_user_confirm 액션
    6. clue_catalog.json 로드 + 구조 무결성
    7. path_from_root 트리 경로 재구성
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from core.intake.clue_tree import (
    ClueCandidate,
    ClueTree,
    ClueTreeNode,
    append_clue_node,
    candidate_count_by_entropy,
    evaluate_confidence,
    make_node_id,
    make_root,
    path_from_root,
    posterior_entropy,
    set_candidates,
    tree_from_dict,
    tree_to_dict,
)


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────


UNIFORM_PRIOR = {
    "CREDENTIAL_THEFT": 0.125,
    "PRIVILEGE_ESCALATION": 0.125,
    "DATA_EXFILTRATION": 0.125,
    "AUDIT_LOG_TAMPERING": 0.125,
    "RANSOMWARE": 0.125,
    "MISCONFIG_EXPOSURE": 0.125,
    "PHISH_INITIAL_ACCESS": 0.125,
    "INSIDER_THREAT": 0.125,
    "UNCLASSIFIED": 0.0,
}


@pytest.fixture
def fresh_tree() -> ClueTree:
    """uniform prior 로 시작하는 빈 트리."""
    return make_root("case-test-001", UNIFORM_PRIOR)


# ─────────────────────────────────────────────────────────────
# 1. 자료구조 기본
# ─────────────────────────────────────────────────────────────


def test_make_root_creates_single_node(fresh_tree: ClueTree) -> None:
    t = fresh_tree
    assert t.case_id == "case-test-001"
    assert len(t.nodes) == 1
    assert t.root_id in t.nodes
    root = t.nodes[t.root_id]
    assert root.parent_id is None
    assert root.depth == 0
    assert root.clue_key == "__ROOT__"
    assert root.posterior_after == UNIFORM_PRIOR
    assert t.current_leaf_id == t.root_id
    assert t.confidence_reached is False


def test_make_node_id_is_unique() -> None:
    ids = {make_node_id() for _ in range(200)}
    assert len(ids) == 200


def test_clue_candidate_creation() -> None:
    c = ClueCandidate(
        candidate_id="c1",
        clue_key="IP_ADDRESS:tor_vpn",
        label="Tor·VPN exit node",
        category="IP_ADDRESS",
        value="tor_vpn",
        expected_info_gain=1.42,
        rationale="CRED 가설 변별력 최고",
    )
    assert c.clue_key == "IP_ADDRESS:tor_vpn"
    assert c.expected_info_gain == 1.42


# ─────────────────────────────────────────────────────────────
# 2. 트리 조작
# ─────────────────────────────────────────────────────────────


def test_append_clue_node_grows_tree(fresh_tree: ClueTree) -> None:
    t = fresh_tree
    before = dict(t.posterior_current)
    after = {**before, "CREDENTIAL_THEFT": 0.45, "PRIVILEGE_ESCALATION": 0.10}
    # 정규화 (sum=1)
    s = sum(v for k, v in after.items() if k != "UNCLASSIFIED")
    after = {k: (v / s if k != "UNCLASSIFIED" else 0) for k, v in after.items()}

    node = append_clue_node(
        t,
        parent_id=t.root_id,
        clue_key="IP_ADDRESS:tor_vpn",
        category="IP_ADDRESS",
        value="tor_vpn",
        label="Tor·VPN exit node 출처",
        source="direct_input",
        posterior_before=before,
        posterior_after=after,
    )
    assert node.depth == 1
    assert node.parent_id == t.root_id
    assert node.clue_key == "IP_ADDRESS:tor_vpn"
    assert t.current_leaf_id == node.node_id
    assert len(t.nodes) == 2
    # score_delta 검증 — CRED 는 증가, AUDIT 는 변화 검출 가능
    assert node.score_delta["CREDENTIAL_THEFT"] > 0


def test_append_with_invalid_parent_raises(fresh_tree: ClueTree) -> None:
    with pytest.raises(ValueError):
        append_clue_node(
            fresh_tree,
            parent_id="nonexistent",
            clue_key="X",
            category="X",
            value="x",
            label="x",
            source="x",
            posterior_before=UNIFORM_PRIOR,
            posterior_after=UNIFORM_PRIOR,
        )


def test_set_candidates_updates_leaf(fresh_tree: ClueTree) -> None:
    cands = [
        ClueCandidate(
            candidate_id="c1",
            clue_key="IP_ADDRESS:tor_vpn",
            label="Tor·VPN exit",
            category="IP_ADDRESS",
            value="tor_vpn",
        ),
        ClueCandidate(
            candidate_id="c2",
            clue_key="ACCOUNT:mfa_disabled",
            label="MFA off",
            category="ACCOUNT",
            value="mfa_disabled",
        ),
    ]
    set_candidates(fresh_tree, fresh_tree.root_id, cands)
    assert len(fresh_tree.nodes[fresh_tree.root_id].children_candidates) == 2


# ─────────────────────────────────────────────────────────────
# 3. Entropy + 동적 후보 개수 (사용자 결정 — paradigm §16)
# ─────────────────────────────────────────────────────────────


def test_entropy_uniform_is_3_bits() -> None:
    """8 사고유형 균등 = log2(8) = 3.0 bits (Shannon)."""
    H = posterior_entropy(UNIFORM_PRIOR)
    assert math.isclose(H, 3.0, abs_tol=0.01)


def test_entropy_zero_when_single_hypothesis() -> None:
    """1 사고유형 100% → entropy = 0."""
    p = {h: 0.0 for h in UNIFORM_PRIOR}
    p["CREDENTIAL_THEFT"] = 1.0
    H = posterior_entropy(p)
    assert math.isclose(H, 0.0, abs_tol=0.01)


def test_candidate_count_uniform_returns_5() -> None:
    """모호 (uniform) 상태 → 5개 노출."""
    assert candidate_count_by_entropy(UNIFORM_PRIOR) == 5


def test_candidate_count_clear_returns_2() -> None:
    """수렴 (1위 95%) → 2개."""
    p = {h: 0.0 for h in UNIFORM_PRIOR}
    p["CREDENTIAL_THEFT"] = 0.95
    p["PHISH_INITIAL_ACCESS"] = 0.05
    assert candidate_count_by_entropy(p) == 2


def test_candidate_count_middle_returns_3() -> None:
    """중간 (1.5 ≤ H < 2.5) → 3개."""
    # 1위 50%, 2위 30%, 나머지 분산
    p = {h: 0.025 for h in UNIFORM_PRIOR}
    p["UNCLASSIFIED"] = 0.0
    p["CREDENTIAL_THEFT"] = 0.50
    p["PHISH_INITIAL_ACCESS"] = 0.30
    # 정규화
    s = sum(v for k, v in p.items() if k != "UNCLASSIFIED")
    p = {k: (v / s if k != "UNCLASSIFIED" else 0) for k, v in p.items()}
    H = posterior_entropy(p)
    assert 1.5 <= H < 2.5
    assert candidate_count_by_entropy(p) == 3


# ─────────────────────────────────────────────────────────────
# 4. Confidence 평가 (사용자 결정 — 알림만)
# ─────────────────────────────────────────────────────────────


def test_confidence_not_reached_uniform() -> None:
    info = evaluate_confidence(UNIFORM_PRIOR)
    assert info["confidence_reached"] is False
    assert info["recommended_action"] == "continue_collecting"


def test_confidence_reached_triggers_notify_action() -> None:
    """primary ≥ 0.65 + gap ≥ 0.20 + depth ≥ 5 → notify_user_confirm.

    Phase K 후속 (2026-05-26 byungwoo) — depth 별 차등 임계값 도입.
    표준 임계값 (0.65/0.20) 은 depth ≥ 5 에서만 적용.
    """
    p = {h: 0.0 for h in UNIFORM_PRIOR}
    p["RANSOMWARE"] = 0.89
    p["INSIDER_THREAT"] = 0.04
    p["MISCONFIG_EXPOSURE"] = 0.03
    p["CREDENTIAL_THEFT"] = 0.04
    info = evaluate_confidence(p, depth=5)
    assert info["confidence_reached"] is True
    assert info["recommended_action"] == "notify_user_confirm"
    assert info["primary"] == "RANSOMWARE"
    assert info["gap"] >= 0.20


def test_confidence_depth_based_throttle() -> None:
    """Phase K 후속 — depth 별 차등 임계값.

    사용자 피드백 (2026-05-26): "단서 2-3개로 너무 빠른 확정" — depth < 3 절대 차단.
    """
    # 매우 강한 신호 — RANSOM 95%, gap 90% (단서 1-2개로도 도달 가능한 정도)
    p_strong = {h: 0.0 for h in UNIFORM_PRIOR}
    p_strong["RANSOMWARE"] = 0.95
    p_strong["INSIDER_THREAT"] = 0.02
    p_strong["MISCONFIG_EXPOSURE"] = 0.02
    p_strong["CREDENTIAL_THEFT"] = 0.01

    # depth 0-2 — 절대 차단 (단서 부족)
    for d in (0, 1, 2):
        assert evaluate_confidence(p_strong, depth=d)["confidence_reached"] is False, (
            f"depth {d} 에서 단서 부족인데 reached=True 됨 — 사용자 피드백 위배"
        )

    # depth 3 — 엄격 (0.80/0.30) — 0.95/0.90 충족, 도달
    info3 = evaluate_confidence(p_strong, depth=3)
    assert info3["confidence_reached"] is True
    assert info3["recommended_action"] == "notify_user_confirm"

    # depth 5 — 표준 (0.65/0.20) — 충분히 충족
    assert evaluate_confidence(p_strong, depth=5)["confidence_reached"] is True

    # 중간 신호 — depth 3 임계값 (0.80/0.30) 미달
    p_mid = {h: 0.0 for h in UNIFORM_PRIOR}
    p_mid["RANSOMWARE"] = 0.70
    p_mid["INSIDER_THREAT"] = 0.15
    p_mid["MISCONFIG_EXPOSURE"] = 0.10
    p_mid["CREDENTIAL_THEFT"] = 0.05
    # depth 3 (0.80/0.30) — 0.70/0.55 — auto_confirm 미달
    assert evaluate_confidence(p_mid, depth=3)["confidence_reached"] is False
    # depth 5 (0.65/0.20) — 충족
    assert evaluate_confidence(p_mid, depth=5)["confidence_reached"] is True


def test_confidence_propose_single_below_auto_confirm() -> None:
    p = {h: 0.0 for h in UNIFORM_PRIOR}
    p["RANSOMWARE"] = 0.62
    p["INSIDER_THREAT"] = 0.20
    p["MISCONFIG_EXPOSURE"] = 0.10
    p["CREDENTIAL_THEFT"] = 0.08
    info = evaluate_confidence(p, depth=5)
    assert info["confidence_reached"] is False
    assert info["recommended_action"] == "propose_single"


# ─────────────────────────────────────────────────────────────
# 5. 직렬화 / 역직렬화 (DB JSON 컬럼 영속화)
# ─────────────────────────────────────────────────────────────


def test_tree_roundtrip_serialization(fresh_tree: ClueTree) -> None:
    # 단서 1개 추가
    before = dict(fresh_tree.posterior_current)
    after = {k: (0.30 if k == "CREDENTIAL_THEFT" else 0.10) for k in UNIFORM_PRIOR}
    after["UNCLASSIFIED"] = 0.0
    s = sum(v for k, v in after.items() if k != "UNCLASSIFIED")
    after = {k: (v / s if k != "UNCLASSIFIED" else 0) for k, v in after.items()}
    append_clue_node(
        fresh_tree,
        parent_id=fresh_tree.root_id,
        clue_key="IP_ADDRESS:tor_vpn",
        category="IP_ADDRESS",
        value="tor_vpn",
        label="Tor",
        source="direct_input",
        posterior_before=before,
        posterior_after=after,
    )
    set_candidates(
        fresh_tree,
        fresh_tree.current_leaf_id,
        [ClueCandidate(candidate_id="c1", clue_key="X:y", label="x", category="X", value="y")],
    )

    # to_dict → JSON → from_dict
    d = tree_to_dict(fresh_tree)
    s = json.dumps(d, ensure_ascii=False)
    d2 = json.loads(s)
    restored = tree_from_dict(d2)

    assert restored.case_id == fresh_tree.case_id
    assert restored.root_id == fresh_tree.root_id
    assert restored.current_leaf_id == fresh_tree.current_leaf_id
    assert len(restored.nodes) == len(fresh_tree.nodes)
    leaf = restored.nodes[restored.current_leaf_id]
    assert leaf.clue_key == "IP_ADDRESS:tor_vpn"
    assert len(leaf.children_candidates) == 1


# ─────────────────────────────────────────────────────────────
# 6. path_from_root — 트리 경로 재구성
# ─────────────────────────────────────────────────────────────


def test_path_from_root_chain(fresh_tree: ClueTree) -> None:
    t = fresh_tree
    before = dict(t.posterior_current)
    # 단서 3개 누적
    for clue_key in ("IP_ADDRESS:tor_vpn", "ACCOUNT:mfa_disabled", "Q5_CRED:tor_vpn"):
        after = {**before, "CREDENTIAL_THEFT": before.get("CREDENTIAL_THEFT", 0.125) * 2}
        s = sum(v for k, v in after.items() if k != "UNCLASSIFIED")
        after = {k: (v / s if k != "UNCLASSIFIED" else 0) for k, v in after.items()}
        append_clue_node(
            t,
            parent_id=t.current_leaf_id,
            clue_key=clue_key,
            category=clue_key.split(":")[0],
            value=clue_key.split(":")[1],
            label=clue_key,
            source="direct_input",
            posterior_before=before,
            posterior_after=after,
        )
        before = after

    path = path_from_root(t)
    assert len(path) == 4  # root + 3 단서
    assert path[0].clue_key == "__ROOT__"
    assert path[-1].clue_key == "Q5_CRED:tor_vpn"
    assert path[-1].depth == 3


# ─────────────────────────────────────────────────────────────
# 7. clue_catalog.json 무결성
# ─────────────────────────────────────────────────────────────


CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "triage" / "clue_catalog.json"


def test_clue_catalog_exists() -> None:
    assert CATALOG_PATH.exists(), (
        f"clue_catalog.json 없음 — scripts/build_clue_catalog.py 실행 필요: {CATALOG_PATH}"
    )


def test_clue_catalog_schema() -> None:
    cat = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert "_meta" in cat
    assert "clues" in cat
    assert cat["_meta"]["version"].startswith("v1")
    assert isinstance(cat["clues"], dict)
    assert len(cat["clues"]) >= 100, f"단서 수 {len(cat['clues'])} 가 100 미만 — 추출 누락 의심"


def test_clue_catalog_entries_have_required_fields() -> None:
    cat = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    required = {"clue_key", "category", "value", "label", "source", "has_weights", "weights", "outcome_flags"}
    missing_examples: list[str] = []
    for key, entry in cat["clues"].items():
        miss = required - set(entry.keys())
        if miss:
            missing_examples.append(f"{key}: missing {miss}")
            if len(missing_examples) >= 5:
                break
    assert not missing_examples, "필드 누락: " + "; ".join(missing_examples)


def test_clue_catalog_weights_sum_per_hypothesis() -> None:
    """가중치 있는 단서는 모든 8 사고유형 가중치를 포함해야 함."""
    cat = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    expected_hypotheses = {
        "CREDENTIAL_THEFT", "PRIVILEGE_ESCALATION", "DATA_EXFILTRATION", "AUDIT_LOG_TAMPERING",
        "RANSOMWARE", "MISCONFIG_EXPOSURE", "PHISH_INITIAL_ACCESS", "INSIDER_THREAT",
    }
    incomplete: list[str] = []
    for key, entry in cat["clues"].items():
        if not entry.get("has_weights"):
            continue
        w = entry.get("weights", {})
        missing = expected_hypotheses - set(w.keys())
        if missing:
            incomplete.append(f"{key}: missing {missing}")
            if len(incomplete) >= 3:
                break
    # 일부 decision_tree 옵션은 routing-only — weights 없을 수 있음. has_weights=True 인 것만 검사
    assert not incomplete, "가중치 미완: " + "; ".join(incomplete)


def test_clue_catalog_outcome_flags_sample() -> None:
    """대표 단서들이 적절한 outcome_flags 를 가지는지 확인 (PDF §17.A)."""
    cat = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    tor = cat["clues"].get("IP_ADDRESS:tor_vpn")
    assert tor is not None
    assert tor["outcome_flags"].get("outcomeIsAnonymizedSource") is True

    tech = cat["clues"].get("TECHNIQUE:T1078.004")
    assert tech is not None
    assert tech["outcome_flags"].get("outcomeAttackTechniqueId") == "T1078.004"
