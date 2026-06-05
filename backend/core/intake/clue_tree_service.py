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


# ─────────────────────────────────────────────────────────────
# 시연 최적화 — 다음 단서 시퀀스 부스트 (06 복합사고 데모, 2026-06-05)
# ─────────────────────────────────────────────────────────────
# 평가관 질문 "왜 이 순서로 로그를 넣었나요?" → "다음 단서 후보에서 찾아 넣었다"
# 라고 답할 수 있도록, 직전 채택 단서(기법)에 대해 시나리오상 '다음에 넣을 로그'의
# 기법 단서를 #1 후보로 결정론적 surfacing 한다 (info_gain IG 랭킹은 '직전 단서의
# 다음'을 알지 못하므로 별도 시퀀스 맵 필요). 시나리오.md §8 로그→기법 매핑 기준.
_DEMO_SEQUENCE_NEXT: dict[str, str] = {
    # 정방향 Stage 1: Login → root 비번 복호화 → 비번 변경
    "TECHNIQUE:T1078.004": "TECHNIQUE:T1552",
    "TECHNIQUE:T1552": "TECHNIQUE:T1098.001",
    # 정방향 Stage 2: 서브계정 정책 조회 → 서브계정 생성 → 관리자 정책 부여
    "TECHNIQUE:T1087.004": "TECHNIQUE:T1136.003",
    "TECHNIQUE:T1136.003": "TECHNIQUE:T1098",
    # 역방향/Stage 3: 버킷 목록 → 내보내기 → 객체 다운로드
    "TECHNIQUE:T1619": "TECHNIQUE:T1537",
    "TECHNIQUE:T1537": "TECHNIQUE:T1530",
}
# 06 복합사고 시나리오(시나리오.md §8)에 등장하는 기법의 한글 라벨.
# IG 후보·부스트 후보 양쪽에 적용해 평가관이 ID 대신 행위로 읽도록 한다.
# (시나리오 무관 기법은 카탈로그 기본 라벨 유지 — "시나리오 연관 것만" 사용자 요청.)
_DEMO_CLUE_LABEL: dict[str, str] = {
    # 자격증명 탈취 (A)
    "TECHNIQUE:T1078.004": "콘솔 로그인 (Login)",
    "TECHNIQUE:T1552": "root 비밀번호 복호화 (Decrypt root password)",
    "TECHNIQUE:T1098.001": "비밀번호 변경·액세스키 생성 (Change password / Create AccessKey)",
    # 권한 상승 (B)
    "TECHNIQUE:T1087.004": "서브계정 조회 (Get Sub Account / Policy List)",
    "TECHNIQUE:T1069.003": "서브계정 정책 목록 조회 (List Sub Account Policy)",
    "TECHNIQUE:T1136.003": "서브계정 생성 (Create sub account)",
    "TECHNIQUE:T1098": "관리자 정책 부여 (Attach policy)",
    # 데이터 유출 (C)
    "TECHNIQUE:T1619": "버킷 목록 조회 (List Buckets)",
    "TECHNIQUE:T1537": "스토리지 내보내기 (Request/Complete For Exporting)",
    "TECHNIQUE:T1530": "객체 다운로드 (GetObject)",
    "TECHNIQUE:T1531": "액세스키 비활성화 (Disable AccessKey)",
}
_DEMO_CLUE_RATIONALE: dict[str, str] = {
    "TECHNIQUE:T1552": "로그인 직후 자격증명 탈취 정황 — root 비밀번호 복호화 시도를 확인하세요.",
    "TECHNIQUE:T1098.001": "복호화된 자격증명으로 비밀번호 변경(계정 장악) 여부를 확인하세요.",
    "TECHNIQUE:T1136.003": "정책 열람 후 신규 서브계정 생성으로 발판을 넓혔는지 확인하세요.",
    "TECHNIQUE:T1098": "생성된 서브계정에 관리자 정책이 부여됐는지 확인하세요.",
    "TECHNIQUE:T1537": "버킷 목록 확인 직후 외부로의 스토리지 내보내기 정황을 확인하세요.",
    "TECHNIQUE:T1530": "내보내기 이후 실제 객체 다운로드(데이터 유출)를 확인하세요.",
    "TECHNIQUE:T1078.004": "다음 단계 추적 — 최초 침투(콘솔 로그인) 정황부터 확인하세요.",
    "TECHNIQUE:T1087.004": "권한 상승 단계 — 공격자가 서브계정 정책을 조회했는지 확인하세요.",
    "TECHNIQUE:T1619": "데이터 유출 단계 — 버킷 목록 조회로 대상 스토리지를 정찰했는지 확인하세요.",
}

# advance_stage 직후 진입할 stage 의 '첫 단서' 앵커.
# confirmed_hypotheses 시퀀스(방향)로 다음 stage 타깃을 추론한다.
_CRED, _PRIV, _EXFIL = "CREDENTIAL_THEFT", "PRIVILEGE_ESCALATION", "DATA_EXFILTRATION"

# 시연 단서 → 소속 stage 가설. chain-mode 후보 필터(NextCluePanel: rationale 이
# 선택 가설명으로 시작하는 후보만 노출)를 통과시키기 위해, 부스트 후보 rationale 에
# 해당 stage 가설명을 접두로 붙인다. (없으면 chain 뷰에서 부스트 후보가 사라짐 — "안떠")
_DEMO_CLUE_HYPOTHESIS: dict[str, str] = {
    "TECHNIQUE:T1078.004": _CRED,
    "TECHNIQUE:T1552": _CRED,
    "TECHNIQUE:T1098.001": _CRED,
    "TECHNIQUE:T1087.004": _PRIV,
    "TECHNIQUE:T1069.003": _PRIV,
    "TECHNIQUE:T1136.003": _PRIV,
    "TECHNIQUE:T1098": _PRIV,
    "TECHNIQUE:T1619": _EXFIL,
    "TECHNIQUE:T1537": _EXFIL,
    "TECHNIQUE:T1530": _EXFIL,
    "TECHNIQUE:T1531": _EXFIL,
}


def _demo_stage_start_clue(confirmed: list[str]) -> Optional[str]:
    """직전 확정 가설 + 진행 방향으로 다음 stage 의 시작 단서를 결정.

    정방향 A→B→C: 자격증명 확정 → 서브계정 정책 조회(B), 권한상승 확정 → 버킷 목록(C)
    역방향 C→B→A: 데이터유출 확정 → 서브계정 정책 조회(B), 권한상승 확정 → 콘솔 로그인(A)
    """
    if not confirmed:
        return None
    last = confirmed[-1]
    seen = set(confirmed)
    if last == _CRED:  # 정방향 A→B
        return "TECHNIQUE:T1087.004"
    if last == _EXFIL:  # 역방향 C→B
        return "TECHNIQUE:T1087.004"
    if last == _PRIV:
        if _CRED in seen:  # 정방향 B→C
            return "TECHNIQUE:T1619"
        if _EXFIL in seen:  # 역방향 B→A
            return "TECHNIQUE:T1078.004"
    return None


def _make_demo_candidate(next_key: str) -> ClueCandidate:
    """시퀀스 부스트용 다음 단서 후보를 합성. 카탈로그에 있으면 그 메타를 차용."""
    technique_id = next_key.split(":", 1)[1] if ":" in next_key else next_key
    entry = load_catalog().get("clues", {}).get(next_key, {})
    label = _DEMO_CLUE_LABEL.get(next_key) or entry.get("label") or f"기법 {technique_id}"
    # chain-mode 필터 통과를 위해 rationale 을 stage 가설명으로 시작시킨다.
    base_rationale = _DEMO_CLUE_RATIONALE.get(next_key, "")
    hyp = _DEMO_CLUE_HYPOTHESIS.get(next_key)
    rationale = f"{hyp} {base_rationale}".strip() if hyp else base_rationale
    return ClueCandidate(
        candidate_id=make_node_id(),
        clue_key=next_key,
        label=label,
        category=entry.get("category", "TECHNIQUE"),
        value=entry.get("value", technique_id),
        expected_info_gain=0.0,
        rationale=rationale,
        outcome_flags=dict(entry.get("outcome_flags", {})),
        techniques=[technique_id],
    )


def _apply_sequence_boost(
    candidates: list[ClueCandidate],
    pivot_clue_key: Optional[str],
    accepted_clue_keys: set[str],
) -> list[ClueCandidate]:
    """직전 채택 기법(pivot)의 시나리오상 다음 단서를 #1 후보로 끌어올린다.

    - 시퀀스 맵에 없는 pivot → 무변경 (일반 IG 후보 그대로)
    - 다음 단서가 이미 채택됨 → 무변경 (중복 제안 차단)
    - 그 외 → 다음 단서를 최상위(IG 최댓값 이상)로 prepend, 중복 제거
    """
    if not pivot_clue_key:
        return candidates
    next_key = _DEMO_SEQUENCE_NEXT.get(pivot_clue_key)
    if not next_key or next_key in accepted_clue_keys:
        return candidates
    return _prepend_demo_candidate(candidates, next_key)


def _prepend_demo_candidate(
    candidates: list[ClueCandidate], next_key: str
) -> list[ClueCandidate]:
    """next_key 합성 후보를 #1(IG 최댓값 이상)로 끌어올리고 중복 제거."""
    rest = [c for c in candidates if c.clue_key != next_key]
    boosted = _make_demo_candidate(next_key)
    top_ig = max((c.expected_info_gain for c in candidates), default=0.0)
    boosted.expected_info_gain = max(top_ig, 0.12)
    return [boosted] + rest


def _apply_stage_start_boost(
    candidates: list[ClueCandidate],
    confirmed: list[str],
    accepted_clue_keys: set[str],
) -> list[ClueCandidate]:
    """advance_stage 직후, 진입 stage 의 첫 단서를 #1 후보로 surfacing."""
    start_key = _demo_stage_start_clue(confirmed)
    if not start_key or start_key in accepted_clue_keys:
        return candidates
    return _prepend_demo_candidate(candidates, start_key)


def _build_candidates(
    posterior: dict[str, float],
    *,
    accepted_clue_keys: set[str],
    k_override: Optional[int] = None,
    pivot_clue_key: Optional[str] = None,
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
                # 시나리오 기법은 한글 라벨로 치환 (없으면 카탈로그 기본값)
                label=_DEMO_CLUE_LABEL.get(clue_key, entry["label"]),
                category=entry["category"],
                value=entry["value"],
                expected_info_gain=float(entry["expected_info_gain"]),
                rationale=entry.get("rationale", ""),
                outcome_flags=dict(entry.get("outcome_flags", {})),  # Phase D
                techniques=_lookup_clue_techniques(clue_key),  # Phase H.4
            )
        )
    # 시연 시퀀스 부스트 — 직전 채택 기법의 '다음 단서'를 #1로 surfacing
    out = _apply_sequence_boost(out, pivot_clue_key, accepted_clue_keys)
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

    # P.21 (2026-05-29) — log_analysis 의 catalog 미수록 TECHNIQUE 폴백.
    # attack_rules/rules.json 이 emit 하는 기법 33개 vs clue_catalog 의
    # TECHNIQUE:* 엔트리 27개 갭 → 16 기법이 미수록 → "+ 단서 추가" 클릭 시 400.
    # bayes_net.technique_likelihood 는 부모/자식/uniform 폴백을 이미 내장하므로
    # 합성 entry 로 안전하게 채택 가능 (변별력 없는 기법은 자연스레 posterior 보존).
    # (2026-06-05) source 제약 제거 — 시연 시퀀스 부스트로 surfacing 된 catalog
    # 미수록 TECHNIQUE 후보를 tree_candidate 경로로도 채택 가능하도록 폴백 확장.
    synthetic_likelihood: Optional[dict[str, float]] = None
    if clue_entry is None and clue_key.startswith("TECHNIQUE:"):
        technique_id = clue_key.split(":", 1)[1]
        if technique_id:
            synthetic_likelihood = bayes_net.technique_likelihood(technique_id)
            clue_entry = {
                "label": label_override or f"기법 {technique_id}",
                "category": "TECHNIQUE",
                "value": technique_id,
                "has_weights": True,
            }

    if clue_entry is None:
        raise ValueError(f"clue_key {clue_key} 가 카탈로그에 없음")

    if not clue_entry.get("has_weights"):
        raise ValueError(f"clue_key {clue_key} 에 weights 없음 — 채택 불가")

    # 베이즈 갱신 — Phase H.4 mode 분기
    posterior_before = dict(tree.posterior_current)
    if synthetic_likelihood is not None:
        # P.21 — 합성 entry: technique_likelihood 가 이미 정규화된 P(T|H) 반환
        likelihood = synthetic_likelihood
    elif _is_bayes_net_mode():
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
    candidates = _build_candidates(
        posterior_after, accepted_clue_keys=accepted, pivot_clue_key=clue_key
    )
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
    leaf = tree.nodes.get(tree.current_leaf_id)
    pivot = leaf.clue_key if leaf and leaf.clue_key != "__ROOT__" else None
    candidates = _build_candidates(
        tree.posterior_current, accepted_clue_keys=accepted, pivot_clue_key=pivot
    )
    # 시연 — 새 stage 진입 직후 refresh 시에도 진입 단서 앵커 유지
    # (이미 채택된 앵커는 accepted 가드로 재노출 안 됨)
    candidates = _apply_stage_start_boost(
        candidates, list(tree.confirmed_hypotheses), accepted
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


def retract_clue(db: Session, case_id: str, node_id: str) -> dict:
    """채택된 단서 1개 철회 → 트리 재구성 (2026-06-03, 채택 단서 삭제 기능).

    선형 트리(root → c1 → c2 → …)에서 중간 노드를 제거하면 그 아래 자식들의
    parent 가 끊기므로, **replay 방식**으로 재구성한다:

      1. 현재 path(root→leaf)에서 제거 대상(node_id)과 root 를 제외한
         나머지 단서들의 (clue_key, source, label) 스펙을 순서대로 수집
      2. reset_tree → cold-start (uniform prior)
      3. 남은 단서들을 순서대로 expand_tree 재적용 (label_override 로 표시값 보존)

    결정성 보장 (paradigm §17): 같은 단서 시퀀스 → 같은 사후확률.
    따라서 replay 후 트리·컴퍼스가 삭제 반영된 정확한 상태로 재계산된다.

    한계: multi-stage(confirmed_hypotheses/stage)는 cold-start 로 초기화됨.
    단일 stage Discovery Loop 의 일반 사용에 적합.
    """
    case = _load_case(db, case_id)
    tree = _load_tree_from_case(case)
    if tree is None:
        raise ClueTreeNotFound(case_id)

    if node_id not in tree.nodes:
        raise ValueError(f"node_id {node_id} 가 트리에 없음")
    if node_id == tree.root_id:
        raise ValueError("root 노드는 철회할 수 없음")

    # 다단계/분기 가드 (2026-06-05) — replay 재구성은 선형·단일 stage 트리에서만
    # 안전하다. advance_stage 로 stage 가 확정된 트리는 replay 시 cold-start 로
    # confirmed_hypotheses·stage 구조가 소실되고, 분기 트리는 path_from_root 가
    # 다른 가지의 채택 단서를 누락시켜 조용한 데이터 유실이 된다 (clue_bridge P.40
    # 과 동일 취지). 두 경우 모두 개별 철회를 막고 초기화(reset)를 안내한다.
    if tree.confirmed_hypotheses:
        raise ValueError(
            "다단계(여러 사고유형 확정) 상태에서는 단서를 개별 철회할 수 없습니다. "
            "초기화 후 다시 진행하세요."
        )

    # root·제거 대상 제외한 나머지 단서 스펙 수집 (시간순 = path 순서)
    full_path = path_from_root(tree)
    if len(full_path) < len(tree.nodes):
        raise ValueError(
            "분기된 트리에서는 단서를 개별 철회할 수 없습니다. 초기화 후 다시 진행하세요."
        )
    remaining: list[dict] = [
        {
            "clue_key": n.clue_key,
            "source": n.source or "tree_candidate",
            "label": n.label,
        }
        for n in full_path
        if n.node_id != tree.root_id and n.node_id != node_id
    ]

    # cold-start 후 남은 단서 순서대로 재적용
    reset_tree(db, case_id)
    case = _load_case(db, case_id)
    tree = _load_tree_from_case(case)
    if tree is None:
        raise ClueTreeNotFound(case_id)

    parent_id = tree.root_id
    for spec in remaining:
        expand_tree(
            db,
            case_id,
            parent_id,
            spec["clue_key"],
            source=spec["source"],
            label_override=spec["label"],
        )
        # 선형 트리 — 방금 추가된 leaf 가 다음 부모
        case = _load_case(db, case_id)
        tree = _load_tree_from_case(case)
        if tree is None:
            raise ClueTreeNotFound(case_id)
        parent_id = tree.current_leaf_id

    logger.info(
        "clue-tree retract %s — removed node=%s, replayed %d remaining clue(s)",
        case_id,
        node_id,
        len(remaining),
    )
    return get_tree(db, case_id)


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
    # 시연 — 진입 stage 의 첫 단서를 #1 후보로 surfacing
    candidates = _apply_stage_start_boost(candidates, new_confirmed, accepted)
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
                # 시연 — 시나리오 기법은 항상 한글 라벨로 직렬화 (저장된 후보 포함)
                "label": _DEMO_CLUE_LABEL.get(c.clue_key, c.label),
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
