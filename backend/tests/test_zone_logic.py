"""Phase M.1.3 — zone_logic 단위 테스트 (2026-05-26, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §22.2.M.1.3 (합격 기준 8 케이스)

검증 항목
---------
    1. depth < 3 → Zone 1 (트리거 미달)
    2. depth ≥ 3 + weak likelihood (< 0.45) → Zone 1
    3. depth ≥ 3 + strong likelihood (≥ 0.45) → Zone 2
    4. depth ≥ 5 + weak likelihood → 여전히 Zone 1 (보스 단서 약함)
    5. should_regress — entropy ≥ 2.0 → True
    6. should_regress — Top1·Top2 gap < 0.10 → True
    7. should_regress — clear winner (gap ≥ 0.10 + entropy < 2.0) → False
    8. compute_attack_chain — RANSOM·CRED·PHISH → Kill Chain 순 (PHISH→CRED→RANSOM)
    9. compute_attack_chain — Top 3 미만 입력 안전 (1개·empty)
"""
from __future__ import annotations

import pytest

from core.intake.bayesian import bayes_update, initial_posterior
from core.intake.clue_tree import (
    ClueTree,
    append_clue_node,
    make_root,
)
from core.intake.info_gain import load_catalog, weights_to_likelihood
from core.intake.zone_logic import (
    KILL_CHAIN_ORDER,
    TRIGGER_MIN_DEPTH,
    TRIGGER_MIN_LIKELIHOOD,
    compute_attack_chain,
    core_clue_likelihood,
    is_zone2_unlocked,
    should_regress,
)


# ─────────────────────────────────────────────────────────────
# Fixtures — 카탈로그에서 known-strong / known-weak 단서 사용
# ─────────────────────────────────────────────────────────────
#   강한 단서  : TECHNIQUE:T1567 (max P(c|h) ≈ 0.50 ≥ 0.45 트리거)
#   약한 단서  : IP_ADDRESS:tor_vpn (max P(c|h) ≈ 0.29 < 0.45 트리거)


STRONG_CLUE = "TECHNIQUE:T1567"
WEAK_CLUE = "IP_ADDRESS:tor_vpn"


def _build_tree(clue_keys: list[str]) -> ClueTree:
    """채택 단서 리스트로 ClueTree 직접 빌드 — 카탈로그 weights 로 베이즈 갱신."""
    tree = make_root("case-zone-test", initial_posterior())
    catalog = load_catalog().get("clues", {})
    parent_id = tree.root_id
    for k in clue_keys:
        entry = catalog[k]
        likelihood = weights_to_likelihood(entry["weights"])
        before = dict(tree.posterior_current)
        after = bayes_update(before, likelihood)
        node = append_clue_node(
            tree,
            parent_id=parent_id,
            clue_key=k,
            category=entry.get("category", ""),
            value=entry.get("value", ""),
            label=entry.get("label", k),
            source="test",
            posterior_before=before,
            posterior_after=after,
        )
        parent_id = node.node_id
    return tree


# ─────────────────────────────────────────────────────────────
# 1. is_zone2_unlocked — 트리거 평가
# ─────────────────────────────────────────────────────────────


def test_zone2_locked_when_depth_below_min() -> None:
    """depth < 3 (강한 단서라도) → Zone 1."""
    tree = _build_tree([STRONG_CLUE, STRONG_CLUE])  # depth = 2
    assert is_zone2_unlocked(tree, tree.posterior_current) is False


def test_zone2_locked_when_likelihood_below_min() -> None:
    """depth ≥ 3 + 약한 단서만 → Zone 1."""
    tree = _build_tree([WEAK_CLUE, WEAK_CLUE, WEAK_CLUE])  # depth = 3
    assert max((n.depth for n in tree.nodes.values()), default=0) >= TRIGGER_MIN_DEPTH
    assert core_clue_likelihood(tree) < TRIGGER_MIN_LIKELIHOOD
    assert is_zone2_unlocked(tree, tree.posterior_current) is False


def test_zone2_unlocked_when_both_satisfied() -> None:
    """depth ≥ 3 + 강한 단서 → Zone 2."""
    tree = _build_tree([WEAK_CLUE, WEAK_CLUE, STRONG_CLUE])  # depth = 3 + 보스 단서
    assert is_zone2_unlocked(tree, tree.posterior_current) is True


def test_zone2_locked_deep_but_weak() -> None:
    """깊이만 깊고 보스 단서 없으면 Zone 1 유지 (paradigm §21.4 ②)."""
    tree = _build_tree([WEAK_CLUE] * 6)  # depth = 6 + 약한 단서만
    assert max((n.depth for n in tree.nodes.values()), default=0) >= 5
    assert is_zone2_unlocked(tree, tree.posterior_current) is False


# ─────────────────────────────────────────────────────────────
# 2. core_clue_likelihood — 보스 단서 식별
# ─────────────────────────────────────────────────────────────


def test_core_clue_likelihood_empty_tree() -> None:
    """root 만 있는 트리 → 0.0."""
    tree = make_root("case-empty", initial_posterior())
    assert core_clue_likelihood(tree) == 0.0


def test_core_clue_likelihood_picks_max() -> None:
    """약한 + 강한 단서 혼합 → 강한 쪽 max likelihood 반환."""
    tree_weak = _build_tree([WEAK_CLUE])
    tree_strong = _build_tree([WEAK_CLUE, STRONG_CLUE])
    assert core_clue_likelihood(tree_strong) > core_clue_likelihood(tree_weak)
    assert core_clue_likelihood(tree_strong) >= TRIGGER_MIN_LIKELIHOOD


# ─────────────────────────────────────────────────────────────
# 3. should_regress — Zone 2 → Zone 1 자동 회귀 조건
# ─────────────────────────────────────────────────────────────


def test_should_regress_when_high_entropy() -> None:
    """uniform 근처 (entropy ≥ 2.0) → 회귀 권고."""
    # uniform 1/8 over 8 types → entropy = log2(8) = 3.0 bits
    posterior = initial_posterior()
    assert should_regress(posterior) is True


def test_should_regress_when_narrow_gap() -> None:
    """Top1·Top2 gap < 0.10 → 회귀 권고 (entropy 낮아도)."""
    # 두 가설 0.48·0.45 → entropy 약 1.0 < 2.0, gap 0.03 < 0.10
    posterior = {
        "CREDENTIAL_THEFT": 0.48,
        "PHISH_INITIAL_ACCESS": 0.45,
        "RANSOMWARE": 0.04,
        "DATA_EXFILTRATION": 0.03,
        "PRIVILEGE_ESCALATION": 0.0,
        "AUDIT_LOG_TAMPERING": 0.0,
        "MISCONFIG_EXPOSURE": 0.0,
        "INSIDER_THREAT": 0.0,
        "UNCLASSIFIED": 0.0,
    }
    assert should_regress(posterior) is True


def test_should_not_regress_when_clear_winner() -> None:
    """clear winner — gap ≥ 0.10 + entropy < 2.0 → 회귀 안 함."""
    posterior = {
        "RANSOMWARE": 0.80,
        "CREDENTIAL_THEFT": 0.10,
        "PHISH_INITIAL_ACCESS": 0.05,
        "DATA_EXFILTRATION": 0.05,
        "PRIVILEGE_ESCALATION": 0.0,
        "AUDIT_LOG_TAMPERING": 0.0,
        "MISCONFIG_EXPOSURE": 0.0,
        "INSIDER_THREAT": 0.0,
        "UNCLASSIFIED": 0.0,
    }
    assert should_regress(posterior) is False


def test_should_not_regress_when_stage_ge_2() -> None:
    """Phase P.4 (2026-05-26) — Multi-Stage 진입 후 (stage ≥ 2) 회귀 권고 OFF.

    Stage 2 의 새 baseline 은 anchor 가설 0 + 나머지 12-30% 분포 → entropy 자연
    높음. 이건 "다시 모호" 가 아니라 "새 광범위 탐색" 정상 상태. 사용자 인지
    부조화 ("막 확정했는데 왜 회귀?!") 차단.
    """
    # 일부러 entropy 매우 높은 posterior 구성 — stage=1 이면 True 가 나옴
    posterior = {
        "CREDENTIAL_THEFT": 0.0,           # anchor freeze
        "PRIVILEGE_ESCALATION": 0.30,
        "DATA_EXFILTRATION": 0.20,
        "INSIDER_THREAT": 0.15,
        "RANSOMWARE": 0.12,
        "AUDIT_LOG_TAMPERING": 0.10,
        "MISCONFIG_EXPOSURE": 0.08,
        "PHISH_INITIAL_ACCESS": 0.05,
        "UNCLASSIFIED": 0.0,
    }
    # stage 1 — 회귀 권고 발동해야 정상 (entropy 높음)
    assert should_regress(posterior, stage=1) is True
    # stage 2 — 회귀 권고 차단 (Multi-Stage 새 baseline)
    assert should_regress(posterior, stage=2) is False
    # stage 3, 4 — 동일
    assert should_regress(posterior, stage=3) is False
    assert should_regress(posterior, stage=99) is False


# ─────────────────────────────────────────────────────────────
# 4. compute_attack_chain — Kill Chain 순 재정렬
# ─────────────────────────────────────────────────────────────


def test_attack_chain_kill_chain_order() -> None:
    """Top 3 = RANSOM 70·CRED 20·PHISH 5 → Kill Chain 순 (PHISH 1·CRED 2·RANSOM 7)."""
    posterior = {
        "RANSOMWARE": 0.70,
        "CREDENTIAL_THEFT": 0.20,
        "PHISH_INITIAL_ACCESS": 0.05,
        "DATA_EXFILTRATION": 0.03,
        "PRIVILEGE_ESCALATION": 0.02,
        "AUDIT_LOG_TAMPERING": 0.0,
        "MISCONFIG_EXPOSURE": 0.0,
        "INSIDER_THREAT": 0.0,
        "UNCLASSIFIED": 0.0,
    }
    chain = compute_attack_chain(posterior)
    assert len(chain) == 3
    # Kill Chain 시간순 — PHISH(1) → CRED(2) → RANSOM(7)
    assert [c["hypothesis"] for c in chain] == [
        "PHISH_INITIAL_ACCESS",
        "CREDENTIAL_THEFT",
        "RANSOMWARE",
    ]
    assert [c["kill_chain_phase"] for c in chain] == [1, 2, 7]
    # 확률 보존
    assert chain[0]["probability"] == pytest.approx(0.05)
    assert chain[2]["probability"] == pytest.approx(0.70)


def test_attack_chain_handles_under_top_n() -> None:
    """Top 3 미만 가설 — 가능한 만큼만 반환 (안전)."""
    # 1개 가설만 비-제로
    posterior_single = {
        "RANSOMWARE": 1.0,
        "CREDENTIAL_THEFT": 0.0,
        "PHISH_INITIAL_ACCESS": 0.0,
        "DATA_EXFILTRATION": 0.0,
        "PRIVILEGE_ESCALATION": 0.0,
        "AUDIT_LOG_TAMPERING": 0.0,
        "MISCONFIG_EXPOSURE": 0.0,
        "INSIDER_THREAT": 0.0,
        "UNCLASSIFIED": 0.0,
    }
    chain = compute_attack_chain(posterior_single)
    # top_n(n=3) 은 비-제로 외에도 0 값도 채워 반환 가능 — len ≤ 3 보장
    assert len(chain) <= 3
    assert chain[-1]["hypothesis"] == "RANSOMWARE"

    # 빈 posterior (UNCLASSIFIED 만)
    posterior_empty = {"UNCLASSIFIED": 1.0}
    assert compute_attack_chain(posterior_empty) == []


def test_attack_chain_kill_chain_order_constant() -> None:
    """KILL_CHAIN_ORDER 매핑 8 사고유형 모두 정의 — 누락 방지."""
    expected = {
        "PHISH_INITIAL_ACCESS",
        "CREDENTIAL_THEFT",
        "PRIVILEGE_ESCALATION",
        "INSIDER_THREAT",
        "MISCONFIG_EXPOSURE",
        "AUDIT_LOG_TAMPERING",
        "DATA_EXFILTRATION",
        "RANSOMWARE",
    }
    assert set(KILL_CHAIN_ORDER.keys()) == expected
    # 단계는 1~7 범위
    assert min(KILL_CHAIN_ORDER.values()) == 1
    assert max(KILL_CHAIN_ORDER.values()) == 7
