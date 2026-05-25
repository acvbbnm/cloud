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
    return tree_from_dict(raw)


def _save_tree_to_case(
    db: Session, case: IncidentCaseModel, tree: ClueTree
) -> None:
    """ClueTree 직렬화 → incident_cases.triage_state["evidence_tree"] 저장."""
    state = dict(case.triage_state or {})
    state[TRIAGE_STATE_KEY] = tree_to_dict(tree)
    # 평면 dict 재할당해야 SQLAlchemy JSON 변경 감지
    case.triage_state = state
    db.commit()


# ─────────────────────────────────────────────────────────────
# 후보 빌더 — IG 정렬 + entropy 기반 K
# ─────────────────────────────────────────────────────────────


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
    """
    k = k_override if k_override is not None else candidate_count_by_entropy(posterior)
    top = pick_top_candidates(
        posterior, k=k, exclude_clue_keys=accepted_clue_keys, use_marginalization=True
    )
    out: list[ClueCandidate] = []
    for entry in top:
        out.append(
            ClueCandidate(
                candidate_id=make_node_id(),
                clue_key=entry["clue_key"],
                label=entry["label"],
                category=entry["category"],
                value=entry["value"],
                expected_info_gain=float(entry["expected_info_gain"]),
                rationale=entry.get("rationale", ""),
                outcome_flags=dict(entry.get("outcome_flags", {})),  # Phase D
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
    """케이스에 빈 ClueTree 생성 + 초기 후보 5개.

    이미 시작된 경우 기존 트리 반환 (idempotent — 재호출 안전).
    """
    case = _load_case(db, case_id)
    existing = _load_tree_from_case(case)
    if existing is not None:
        logger.info("clue-tree already exists for %s — returning existing", case_id)
        return _build_response(existing)

    tree = make_root(case_id, initial_posterior())
    # uniform prior → entropy 3.0 → 5 후보
    candidates = _build_candidates(
        tree.posterior_current, accepted_clue_keys=set()
    )
    set_candidates(tree, tree.root_id, candidates)
    _save_tree_to_case(db, case, tree)
    logger.info(
        "clue-tree started for %s — %d initial candidates", case_id, len(candidates)
    )
    return _build_response(tree)


def expand_tree(
    db: Session,
    case_id: str,
    parent_node_id: str,
    clue_key: str,
    *,
    source: str = "tree_candidate",
) -> dict:
    """단서 채택 → 트리 노드 추가 + 베이즈 갱신 + 다음 후보.

    source 값:
      - "tree_candidate" : children_candidates 클릭
      - "direct_input"   : 사용자 직접 입력
      - "log_analysis"   : 로그 분석 결과
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

    # 베이즈 갱신
    posterior_before = dict(tree.posterior_current)
    likelihood = weights_to_likelihood(clue_entry["weights"])
    posterior_after = bayes_update(posterior_before, likelihood)

    # 트리에 단서 노드 추가
    node = append_clue_node(
        tree,
        parent_id=parent_node_id,
        clue_key=clue_key,
        category=clue_entry.get("category", ""),
        value=clue_entry.get("value", ""),
        label=clue_entry.get("label", clue_key),
        source=source,
        posterior_before=posterior_before,
        posterior_after=posterior_after,
    )

    # confidence 평가
    confidence = evaluate_confidence(posterior_after)
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
    leaf = tree.nodes.get(tree.current_leaf_id)
    candidates_raw = leaf.children_candidates if leaf else []
    path = path_from_root(tree)

    return {
        "tree": tree_to_dict(tree),
        "current_leaf_id": tree.current_leaf_id,
        "posterior_current": tree.posterior_current,
        "confidence": evaluate_confidence(tree.posterior_current),
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
            }
            for c in candidates_raw
        ],
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
            }
            for n in path
        ],
    }
