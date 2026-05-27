"""Phase B.2 — ClueTreeService (2026-05-25, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §5·§6·§17

비즈니스 로직:
  - start_tree(case_id)              : uniform prior 로 빈 트리 생성 + 초기 후보
  - expand_tree(case_id, parent_id, clue_key) : 단서 채택 → 사후확률 갱신 + 다음 후보
  - suggest_candidates(case_id)      : 현 leaf 의 후보 재계산 (entropy 동적 K)
  - get_tree(case_id)                : DB 영속화된 트리 로드

영속화
------
    `incident_cases.triage_state` JSON 컬럼에 sub-key `"evidence_tree"` 로 직렬화.
    기존 additive/bayesian state (current_node_id, completed_path 등) 와 공존.

설계 결정 (paradigm doc §16)
-----------------------------
    - 다음 후보 개수 = posterior entropy 기반 동적 (5 / 3 / 2)
    - confidence 도달 (≥0.65 + gap ≥0.20) 시 → notify_user_confirm 액션만 반환,
      자동 종료 X
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from core.intake import bayes_net
from core.intake.bayesian import (
    bayes_update,
    initial_posterior,
)
from core.intake.clue_tree import (
    ClueCandidate,
    ClueTree,
    ClueTreeNode,
    append_clue_node,
    candidate_count_by_entropy,
    evaluate_confidence,
    heal_tree_invariants,
    make_node_id,
    make_root,
    path_from_root,
    set_candidates,
    tree_from_dict,
    tree_to_dict,
)
from core.intake.info_gain import (
    load_catalog,
    pick_top_candidates,
    weights_to_likelihood,
)
from core.intake.zone_logic import (
    compute_attack_chain,
    core_clue_likelihood,
    is_zone2_unlocked,
    should_regress,
)
from core.intake.stage_transition import (
    chain_description,
    compute_stage_prior,
    is_multistage,
)
from db.models import IncidentCaseModel

logger = logging.getLogger(__name__)


TRIAGE_STATE_KEY = "evidence_tree"  # incident_cases.triage_state 내 sub-key


class ClueTreeNotFound(Exception):
    """ClueTree 가 아직 시작되지 않은 케이스 — start_tree 먼저 호출 필요."""


class CaseNotFound(Exception):
    """incident_cases 에 해당 case_id 없음."""


# ─────────────────────────────────────────────────────────────
# DB 영속화 헬퍼
# ─────────────────────────────────────────────────────────────


def _load_case(db: Session, case_id: str) -> IncidentCaseModel:
    case = db.query(IncidentCaseModel).filter_by(case_id=case_id).first()
    if not case:
        raise CaseNotFound(case_id)
    return case


def _load_tree_from_case(case: IncidentCaseModel) -> Optional[ClueTree]:
    state = case.triage_state or {}
    raw = state.get(TRIAGE_STATE_KEY)
    if not raw:
        return None
    tree = tree_from_dict(raw)
    # P.19 (2026-05-28, hard) — 역직렬화 직후 invariant 강제 보장.
    # 옛 버전·외부 조작으로 손상된 triage_state JSON 의 잔존 케이스 자동 복구.
    healed = heal_tree_invariants(tree, logger=logger)
    if healed > 0:
        logger.info(
            "_load_tree_from_case: healed %d invariant(s) for case=%s — 손상된 triage_state 자동 복구",
            healed,
            case.case_id,
        )
    return tree


def _save_tree_to_case(
    db: Session, case: IncidentCaseModel, tree: ClueTree
) -> None:
    """ClueTree 직렬화 → incident_cases.triage_state["evidence_tree"] 저장."""
    # P.19 (2026-05-28, hard) — 저장 직전 invariant 강제 보장.
    # 응답 빌더가 healing 한 in-memory tree 가 그대로 영속화되어 DB 손상 제거.
    healed = heal_tree_invariants(tree, logger=logger)
    if healed > 0:
        logger.warning(
            "_save_tree_to_case: %d invariant(s) healed before save — case=%s",
            healed,
            case.case_id,
        )
    state = dict(case.triage_state or {})
    state[TRIAGE_STATE_KEY] = tree_to_dict(tree)
    # 평면 dict 재할당해야 SQLAlchemy JSON 변경 감지
    case.triage_state = state
    db.commit()


# ─────────────────────────────────────────────────────────────
# 후보 빌더 — IG 정렬 + entropy 기반 K
# ─────────────────────────────────────────────────────────────


def _is_bayes_net_mode() -> bool:
    """현재 mode 가 bayes_net 인지 (Phase H.4)."""
    return settings.TRIAGE_MODE == "bayes_net"


def _likelihood_fn_for_mode():
    """현재 TRIAGE_MODE 에 따른 clue → likelihood 함수.

    - bayes_net: bayes_net.clue_likelihood_via_bn (Noisy-OR DAG 추론, H.3)
    - 그 외:     None (info_gain 기본 weights_to_likelihood 사용)
    """
    if _is_bayes_net_mode():
        return bayes_net.clue_likelihood_via_bn
    return None


def _lookup_clue_techniques(clue_key: str) -> list[str]:
    """clue_to_attack 매핑에서 단서의 ATT&CK 기법 리스트 조회 (Phase H.4).

    매핑 없거나 null/빈 리스트면 빈 리스트. UI 가 기법 badge 표시할 때 사용.
    """
    try:
        m = bayes_net.load_clue_to_attack().get("mappings", {}).get(clue_key, {})
        return list(m.get("techniques") or [])
    except FileNotFoundError:
        return []


def _build_candidates(
    posterior: dict[str, float],
    *,
    accepted_clue_keys: set[str],
    k_override: Optional[int] = None,
) -> list[ClueCandidate]:
    """현재 사후확률에서 entropy 기반 K개 후보 선정.

    K 결정 (사용자 결정 — paradigm §16):
        H ≥ 2.5 bits → 5개
        1.5 ≤ H < 2.5 → 3개
        H < 1.5      → 2개
    k_override 가 주어지면 강제.

    Phase H.4 — TRIAGE_MODE=bayes_net 일 때 IG 계산이 BN Noisy-OR likelihood 사용.
    또한 응답 candidate 에 ATT&CK 기법 매핑 (techniques) 동봉 — UI badge 용.
    """
    k = k_override if k_override is not None else candidate_count_by_entropy(posterior)
    top = pick_top_candidates(
        posterior,
        k=k,
        exclude_clue_keys=accepted_clue_keys,
        use_marginalization=True,
        likelihood_fn=_likelihood_fn_for_mode(),
    )
    out: list[ClueCandidate] = []
    for entry in top:
        clue_key = entry["clue_key"]
        out.append(
            ClueCandidate(
                candidate_id=make_node_id(),
                clue_key=clue_key,
                label=entry["label"],
                category=entry["category"],
                value=entry["value"],
                expected_info_gain=float(entry["expected_info_gain"]),
                rationale=entry.get("rationale", ""),
                outcome_flags=dict(entry.get("outcome_flags", {})),  # Phase D
                techniques=_lookup_clue_techniques(clue_key),  # Phase H.4
            )
        )
    return out


def _collect_accepted_keys(tree: ClueTree) -> set[str]:
    """트리에서 이미 채택된 단서 키들 (중복 제안 차단)."""
    keys: set[str] = set()
    for node in tree.nodes.values():
        if node.clue_key and node.clue_key != "__ROOT__":
            keys.add(node.clue_key)
    return keys


# ─────────────────────────────────────────────────────────────
# 핵심 비즈니스 로직
# ─────────────────────────────────────────────────────────────


def start_tree(db: Session, case_id: str) -> dict:
    """케이스에 빈 ClueTree 생성. **Cold-start 정책 (2026-05-25, byungwoo)**:
    root 만 만들고 후보는 비움 — 첫 단서가 입력되어야 IG 후보 풀이 등장한다.

    비유 정합 (paradigm §1): "어두운 맵" 은 시작 시 아무것도 안 보이는 게 정상.
    첫 단서가 횃불을 켠다.

    학술 정합: uniform prior 에서 모든 단서의 IG 가 사실상 균등 → 추천 의미 미약.
    첫 단서가 들어와야 posterior 가 기울고, 그때부터 변별력 있는 후보 산출 가능.

    사용자는 CluesInput 직접 입력 또는 PartialLogAnalysis 로그 분석으로
    첫 단서를 채택 → 이후 트리 후보 자라기 시작.

    이미 시작된 경우 기존 트리 반환 (idempotent — 재호출 안전).
    """
    case = _load_case(db, case_id)
    existing = _load_tree_from_case(case)
    if existing is not None:
        logger.info("clue-tree already exists for %s — returning existing", case_id)
        return _build_response(existing)

    tree = make_root(case_id, initial_posterior())
    # Cold-start: 후보 0개 — 첫 단서 입력 후 expand_tree 가 채움
    set_candidates(tree, tree.root_id, [])
    _save_tree_to_case(db, case, tree)
    logger.info("clue-tree started for %s — cold-start (no candidates)", case_id)
    return _build_response(tree)


def expand_tree(
    db: Session,
    case_id: str,
    parent_node_id: str,
    clue_key: str,
    *,
    source: str = "tree_candidate",
    label_override: Optional[str] = None,
) -> dict:
    """단서 채택 → 트리 노드 추가 + 베이즈 갱신 + 다음 후보.

    source 값:
      - "tree_candidate" : children_candidates 클릭
      - "direct_input"   : 사용자 직접 입력
      - "log_analysis"   : 로그 분석 결과

    label_override (2026-05-26):
      - 사용자가 직접 입력한 값 (예: "203.0.113.5") 을 트리 노드 라벨로 표시.
      - None 이면 카탈로그의 entry.label 사용 (기본).
      - direct_input source 일 때 generic clue_key 라도 사용자 입력값 가시화.
    """
    case = _load_case(db, case_id)
    tree = _load_tree_from_case(case)
    if tree is None:
        raise ClueTreeNotFound(case_id)

    if parent_node_id not in tree.nodes:
        raise ValueError(f"parent_node_id {parent_node_id} 가 트리에 없음")

    catalog = load_catalog()
    clue_entry = catalog.get("clues", {}).get(clue_key)
    if clue_entry is None:
        raise ValueError(f"clue_key {clue_key} 가 카탈로그에 없음")

    if not clue_entry.get("has_weights"):
        raise ValueError(f"clue_key {clue_key} 에 weights 없음 — 채택 불가")

    # 베이즈 갱신 — Phase H.4 mode 분기
    posterior_before = dict(tree.posterior_current)
    if _is_bayes_net_mode():
        # BN 모드 — clue_to_attack 매핑 + Noisy-OR DAG 추론 (H.3)
        likelihood = bayes_net.clue_likelihood_via_bn(clue_key)
    else:
        # legacy — weights.json 직접 likelihood
        likelihood = weights_to_likelihood(clue_entry["weights"])
    posterior_after = bayes_update(posterior_before, likelihood)

    # 트리에 단서 노드 추가
    node = append_clue_node(
        tree,
        parent_id=parent_node_id,
        clue_key=clue_key,
        category=clue_entry.get("category", ""),
        value=clue_entry.get("value", ""),
        label=label_override or clue_entry.get("label", clue_key),
        source=source,
        posterior_before=posterior_before,
        posterior_after=posterior_after,
    )

    # confidence 평가 — Phase K 후속 (2026-05-26): depth 별 차등 임계값
    # node.depth 는 root=0 기준이므로 채택된 단서 수와 동일.
    confidence = evaluate_confidence(posterior_after, depth=node.depth)
    tree.confidence_reached = confidence["confidence_reached"]
    if confidence["confidence_reached"]:
        tree.incident_type_recommendation = confidence["primary"]

    # 다음 후보 (entropy 기반 K)
    accepted = _collect_accepted_keys(tree)
    candidates = _build_candidates(posterior_after, accepted_clue_keys=accepted)
    set_candidates(tree, node.node_id, candidates)

    _save_tree_to_case(db, case, tree)
    logger.info(
        "clue-tree expand %s ← %s — primary=%s prob=%.3f gap=%.3f",
        case_id,
        clue_key,
        confidence["primary"],
        confidence["primary_prob"],
        confidence["gap"],
    )
    return _build_response(tree)


def suggest_candidates(db: Session, case_id: str) -> dict:
    """현 leaf 의 다음 후보 재계산 (사용자가 새로고침 요청 시).

    트리 자체는 변하지 않음. 후보만 갱신.
    """
    case = _load_case(db, case_id)
    tree = _load_tree_from_case(case)
    if tree is None:
        raise ClueTreeNotFound(case_id)

    accepted = _collect_accepted_keys(tree)
    candidates = _build_candidates(
        tree.posterior_current, accepted_clue_keys=accepted
    )
    set_candidates(tree, tree.current_leaf_id, candidates)
    _save_tree_to_case(db, case, tree)
    return _build_response(tree)


def get_tree(db: Session, case_id: str) -> dict:
    """현재 트리 상태 조회."""
    case = _load_case(db, case_id)
    tree = _load_tree_from_case(case)
    if tree is None:
        raise ClueTreeNotFound(case_id)
    return _build_response(tree)


def reset_tree(db: Session, case_id: str) -> dict:
    """트리 초기화 — 디버그·재시작용. 기존 evidence_tree state 삭제."""
    case = _load_case(db, case_id)
    state = dict(case.triage_state or {})
    state.pop(TRIAGE_STATE_KEY, None)
    case.triage_state = state
    db.commit()
    return start_tree(db, case_id)


# ─────────────────────────────────────────────────────────────
# Phase N.4 — Multi-Stage Attack Chain (paradigm §23, 2026-05-26)
# ─────────────────────────────────────────────────────────────


def advance_stage(
    db: Session, case_id: str, confirmed_hypothesis: str
) -> dict:
    """확정된 사고유형을 anchor 로 두고 다음 stage 진입.

    동작
    ----
    1. confirmed_hypotheses 시퀀스에 새 가설 추가 (시간순)
    2. stage += 1
    3. posterior_current = STAGE_TRANSITION_MATRIX 의 다음 baseline (확정 가설 제외 + 연관 가중치)
    4. confidence_reached / recommendation reset — 새 stage 진행 위해
    5. current_leaf 의 children_candidates 새 baseline 기반 재계산

    설계 결정 (paradigm §23.3):
      - 기존 nodes 보존 (시계열·보고서 추적용)
      - current_leaf_id 그대로 — 새 stage 단서들은 같은 leaf 의 children 으로 자라남
      - 베이즈 갱신은 새 baseline 에서 시작 → expand_tree 동작 변경 없음

    사용:
      Stage 1 에서 CREDENTIAL_THEFT 확정 (confidence_reached=True) →
      사용자 [확정하고 다음 단계 추적] 클릭 → advance_stage(db, case_id, "CREDENTIAL_THEFT")
    """
    case = _load_case(db, case_id)
    tree = _load_tree_from_case(case)
    if tree is None:
        raise ClueTreeNotFound(case_id)

    # 이미 확정된 가설은 중복 추가 안 함
    if confirmed_hypothesis in tree.confirmed_hypotheses:
        raise ValueError(
            f"가설 {confirmed_hypothesis} 가 이미 확정 시퀀스에 있음: "
            f"{tree.confirmed_hypotheses}"
        )

    new_confirmed = list(tree.confirmed_hypotheses) + [confirmed_hypothesis]
    new_baseline = compute_stage_prior(new_confirmed)

    tree.confirmed_hypotheses = new_confirmed
    tree.stage += 1
    tree.posterior_current = new_baseline
    tree.confidence_reached = False
    tree.incident_type_recommendation = None

    # 현 leaf 의 children_candidates 재계산 — 새 baseline 기준 IG
    accepted = _collect_accepted_keys(tree)
    candidates = _build_candidates(new_baseline, accepted_clue_keys=accepted)
    set_candidates(tree, tree.current_leaf_id, candidates)

    _save_tree_to_case(db, case, tree)
    logger.info(
        "clue-tree advance-stage %s — confirmed=%s, stage=%d, chain=%s",
        case_id,
        confirmed_hypothesis,
        tree.stage,
        chain_description(new_confirmed),
    )
    return _build_response(tree)


# ─────────────────────────────────────────────────────────────
# 응답 빌더 — API 공통 포맷
# ─────────────────────────────────────────────────────────────


def _build_response(tree: ClueTree) -> dict:
    """공통 응답 형식.

    {
      "tree": <serialized>,
      "current_leaf_id": str,
      "posterior_current": {...},
      "confidence": {...},
      "candidates": [...],   # 현재 leaf 의 children_candidates 평탄화
      "path": [...]          # root → leaf 단서 시퀀스 (UI 미니맵용)
    }
    """
    # P.19 (2026-05-28, hard) — 응답 직전 invariant 마지막 방어선.
    # _load 직후·_save 직전에 이미 healing 호출되지만, 응답 빌더가 단독 호출되는
    # 경로(get_tree 등)도 모두 안전하도록 3중 방어. 정합 트리면 healed=0 (zero-cost).
    heal_tree_invariants(tree, logger=logger)
    leaf = tree.nodes.get(tree.current_leaf_id)
    candidates_raw = leaf.children_candidates if leaf else []
    path = path_from_root(tree)
    # Phase K 후속 — 현재 leaf depth (=채택된 단서 수) 를 confidence 평가에 전달
    current_depth = leaf.depth if leaf else 0

    # Phase M.1 — 2-zone 메타 (paradigm §21·§22.2)
    # Phase P.15 (2026-05-27 e2e 감사 — P.4 fix 가 P.8 easy 흡수로 되돌려진 회귀)
    #   should_regress 에 stage 전달 필수 — stage ≥ 2 시 자동 False (Multi-Stage
    #   새 baseline 의 entropy 자연 높음을 회귀 권고로 오인 차단).
    zone2 = is_zone2_unlocked(tree, tree.posterior_current)
    regress_suggested = zone2 and should_regress(
        tree.posterior_current, stage=tree.stage
    )
    # 회귀 권고 시 final zone = 1 (UI 가 자동 강제 X, 사용자 결정. paradigm §21.8 #5)
    final_zone = 1 if (not zone2 or regress_suggested) else 2

    return {
        "tree": tree_to_dict(tree),
        "current_leaf_id": tree.current_leaf_id,
        "posterior_current": tree.posterior_current,
        "confidence": evaluate_confidence(tree.posterior_current, depth=current_depth),
        # Phase M.1 신규 — paradigm §21·§22.2
        "zone": final_zone,                                       # 1 or 2
        "attack_chain": compute_attack_chain(tree.posterior_current),
        "core_clue_likelihood": core_clue_likelihood(tree),
        "regress_suggested": regress_suggested,
        # Phase N.4 신규 — Multi-Stage Attack Chain (paradigm §23)
        "stage": tree.stage,
        "confirmed_hypotheses": list(tree.confirmed_hypotheses),
        "is_multistage": is_multistage(tree.confirmed_hypotheses),
        "chain_description": chain_description(tree.confirmed_hypotheses),
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "clue_key": c.clue_key,
                "label": c.label,
                "category": c.category,
                "value": c.value,
                "expected_info_gain": c.expected_info_gain,
                "rationale": c.rationale,
                # Phase D — outcome_flags 전파 (Google Chronicle 패턴, PDF §17.A)
                "outcome_flags": c.outcome_flags,
                # Phase H.4 — ATT&CK 기법 ID (clue_to_attack 매핑) 전파. UI badge 용.
                "techniques": list(c.techniques or []),
            }
            for c in candidates_raw
        ],
        # Phase H.4 — 현재 추론 mode (프론트가 BN 표시 결정에 사용)
        "scoring_mode": settings.TRIAGE_MODE,
        "path": [
            {
                "node_id": n.node_id,
                "depth": n.depth,
                "clue_key": n.clue_key,
                "label": n.label,
                "category": n.category,
                "value": n.value,
                "source": n.source,
                "posterior_after": n.posterior_after,
                # Phase P (KBW, 2026-05-27) — multi-stage 시각화용
                "stage": getattr(n, "stage", 1),
            }
            for n in path
        ],
    }
