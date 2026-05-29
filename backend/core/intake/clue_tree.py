"""Layer 0 — Evidence Tree (단서 기반 동적 결정 트리, Phase A — 2026-05-25, byungwoo).

설계서: `docs/evidence_tree_paradigm.md`

핵심 자료구조
------------
- `ClueTreeNode` : 트리 노드 1개 = 채택된 단서 1개 + 사후확률 스냅샷
- `ClueTree`     : 케이스별 전체 단서 트리 (root + nodes dict)

설계 원칙 (paradigm doc §3 정합)
-------------------------------
- **트리 노드 = 단서** (확정된 사실, IoC). 질문 노드 X.
- **children = 다음 단서 후보** (Information Gain 동적 계산)
- **무한 깊이** — confidence ≥ 0.65 + gap ≥ 0.20 도달 시 알림 카드만 노출, 자동 종료 X
- **결정성 100%** — 같은 단서 시퀀스 → 같은 사후확률

학술
----
- Pearl 1988 Bayesian Belief Propagation
- Peirce 1903 Abductive Reasoning
- Shannon 1948 Information Gain (entropy)
- Jaynes 1968 Maximum Entropy Prior (1/8 uniform)
"""
from __future__ import annotations

import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional


# ─────────────────────────────────────────────────────────────
# 모듈 상수 (R.1, 2026-05-28, hard) — 매직 문자열·숫자 외부화
# ─────────────────────────────────────────────────────────────
#
# 배경 (docs/하드코딩_감사_P18_P19_2026-05-28.md §2 항목 #3·#4·#6·#7):
#   root sentinel·source enum·UNCLASSIFIED 필터·INCIDENT_COUNT 가 여러 곳에
#   박혀 있어 DRY 위반 + 추가/변경 시 동기화 비용. 모듈 상수로 한 곳에서 관리.

# Root 노드 sentinel — make_root + heal_tree_invariants 양쪽에서 사용.
ROOT_CLUE_KEY: str = "__ROOT__"
ROOT_CATEGORY: str = "ROOT"

# 사고유형 개수 (UNCLASSIFIED 제외 = "real" 사고유형 수, dev3 C-1 풀세트 8종).
# entropy 최대값 log2(N) 계산에 사용. types/index.ts 의 IncidentType 길이 - 1 과 일치.
INCIDENT_COUNT: int = 8

# Posterior 분석 시 제외할 가설 키 (sentinel — 분류 안 됨 상태).
# entropy 계산·confidence 평가에서 일관 제외. 추가 sentinel 생기면 여기만 추가.
SENTINEL_HYPOTHESIS_KEYS: frozenset[str] = frozenset({"UNCLASSIFIED"})

# 단서 채택 출처 enum — types narrowing 으로 IDE/mypy 가 오타 차단.
#   system         : make_root 가 만든 가상 ROOT 노드
#   tree_candidate : children_candidates 클릭
#   direct_input   : 사용자 직접 입력
#   log_analysis   : 로그 분석 결과
#   heal           : heal_tree_invariants 가 root 재생성한 경우 (P.19, hard)
ClueSource = Literal["system", "tree_candidate", "direct_input", "log_analysis", "heal"]


def real_hypotheses(posterior: dict[str, float]) -> dict[str, float]:
    """sentinel(UNCLASSIFIED 등) 제외한 실제 사고유형 사후확률만 반환.

    R.1 (hard) — entropy_of_posterior + evaluate_confidence 의 중복 필터를 DRY 통합.
    sentinel 키가 추가될 때 SENTINEL_HYPOTHESIS_KEYS 한 곳만 수정하면 모두 반영.
    """
    return {k: v for k, v in posterior.items() if k not in SENTINEL_HYPOTHESIS_KEYS}


# ─────────────────────────────────────────────────────────────
# Confidence / Entropy 정책 로더 (R.3, 2026-05-28, hard) — #1·#2 해결
# ─────────────────────────────────────────────────────────────
#
# 배경: 하드코딩 감사 §2-A·§2-B — depth 차등 임계값 7개 + entropy 기반 K 4개가
#       함수 본문에 박혀 있어 학술 변호값 변경 시 코드 수정 + 회귀 위험.
# 정책: backend/data/triage/confidence_policy.json 으로 외부화 + lazy load + cache.
#       JSON 부재 시 FileNotFoundError — fail-fast (정책 누락 = 시스템 무결성 손상).

_CONFIDENCE_POLICY_PATH: Path = (
    Path(__file__).resolve().parents[2] / "data" / "triage" / "confidence_policy.json"
)


@lru_cache(maxsize=1)
def load_confidence_policy() -> dict:
    """confidence_policy.json 로드 + 캐시 (R.3, hard).

    Returns:
        dict — depth_thresholds, confidence_levels, entropy_candidate_k 3 섹션.

    Raises:
        FileNotFoundError — JSON 파일 부재 시 (fail-fast).
        ValueError — JSON 파싱 실패 시.
    """
    if not _CONFIDENCE_POLICY_PATH.exists():
        raise FileNotFoundError(
            f"confidence_policy.json not found at {_CONFIDENCE_POLICY_PATH} — "
            "R.3 (hard) 정책 외부화 후 필수 파일. data/triage 에 복원 필요."
        )
    with _CONFIDENCE_POLICY_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _resolve_depth_policy(depth: int) -> tuple[float, float]:
    """주어진 depth 에 해당하는 (auto_confirm, gap_req) 임계값 반환.

    policies 배열을 순회하며 depth_min ≤ depth ≤ depth_max (None=무한대) 매칭.
    """
    policy = load_confidence_policy()
    for p in policy["depth_thresholds"]["policies"]:
        dmin = p["depth_min"]
        dmax = p["depth_max"]
        if depth >= dmin and (dmax is None or depth <= dmax):
            return float(p["auto_confirm"]), float(p["gap_req"])
    # 모든 정책이 매칭 안 되면 (이론상 발생 X) sentinel-block 반환
    return 1.01, 1.01


def _resolve_k_by_entropy(H: float) -> int:
    """주어진 entropy(bits) 에 해당하는 후보 노출 개수 K 반환.

    entropy_min 내림차순으로 정렬된 thresholds 를 순회 — 가장 먼저 매칭되는 K.
    """
    policy = load_confidence_policy()
    sorted_th = sorted(
        policy["entropy_candidate_k"]["thresholds"],
        key=lambda x: -x["entropy_min"],
    )
    for th in sorted_th:
        if H >= float(th["entropy_min"]):
            return int(th["k"])
    return 2  # 안전 디폴트 (가장 작은 K)


# ─────────────────────────────────────────────────────────────
# 자료구조
# ─────────────────────────────────────────────────────────────


@dataclass
class ClueCandidate:
    """다음 단서 후보 — 트리에 아직 채택되지 않은 점선 child."""

    candidate_id: str  # uuid (채택 시 ClueTreeNode.node_id 로 승격)
    clue_key: str  # 카탈로그 키 (예: "Q5_CRED:tor_vpn" 또는 "IP_ADDRESS:tor_vpn")
    label: str  # 사용자에게 보일 짧은 라벨
    category: str  # 단서 분류 (예: "Q5_CRED", "IP_ADDRESS")
    value: str  # 단서 값 (예: "tor_vpn")
    expected_info_gain: float = 0.0  # Phase B 에서 채움 (KL divergence, bits)
    rationale: str = ""  # 왜 이 후보가 추천되는지 (top 사고유형 근거)
    # PDF §17.A — Google Chronicle Rule-to-Outcome 정형 Boolean (Phase D)
    outcome_flags: dict = field(default_factory=dict)
    # Phase H.4 — ATT&CK 기법 ID 리스트 (clue_to_attack 매핑). UI badge 용.
    # BN 모드 (TRIAGE_MODE=bayes_net) 가 아니어도 항상 동봉 — 학술 정보 노출.
    techniques: list = field(default_factory=list)


@dataclass
class ClueTreeNode:
    """채택된 단서 노드 1개.

    score_delta 와 posterior_after 는 베이즈 갱신 결과 스냅샷.
    stage 는 multi-stage 추적용 (Phase P 후속 — 2026-05-27, KBW).
    """

    node_id: str
    parent_id: Optional[str]
    depth: int
    # 채택된 단서 정보
    clue_key: str  # 카탈로그 키
    category: str
    value: str
    label: str
    source: ClueSource  # R.1 (hard) — Literal 타입화 (위 모듈 상수 ClueSource 참조)
    # 베이즈 갱신 결과
    score_delta: dict[str, float] = field(default_factory=dict)
    posterior_after: dict[str, float] = field(default_factory=dict)
    accepted_at: str = ""  # ISO-8601
    # 다음 후보 (자식 들)
    children_candidates: list[ClueCandidate] = field(default_factory=list)
    # Phase P (KBW, 2026-05-27) — 노드가 속한 stage. advance_to_next_stage 이후
    # 채택되는 노드는 tree.stage 값을 그대로 기록 → 시각화에서 stage 경계 검출에 사용.
    stage: int = 1


@dataclass
class ClueTree:
    """케이스 1건의 전체 단서 트리."""

    case_id: str
    root_id: str  # uniform prior 시작 노드 ID
    nodes: dict[str, ClueTreeNode] = field(default_factory=dict)
    current_leaf_id: str = ""  # 가장 최근 채택 단서 (다음 채택 위치)
    posterior_current: dict[str, float] = field(default_factory=dict)
    confidence_reached: bool = False  # primary_prob ≥ 0.65 + gap ≥ 0.20
    incident_type_recommendation: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    # Phase N.4 (2026-05-26) — Multi-Stage Attack Chain 추적
    # 확정된 사고유형 시퀀스 (시간순). 길이 ≥ 1 이면 multi-stage 진행 중.
    # 학술 정합: ATT&CK Flow + Mandiant M-Trends double extortion chain.
    confirmed_hypotheses: list[str] = field(default_factory=list)
    # 현재 stage (1 = 첫 분석, 2 = 첫 사고유형 확정 후 추적, ...).
    stage: int = 1


# ─────────────────────────────────────────────────────────────
# 생성·조작 헬퍼
# ─────────────────────────────────────────────────────────────


def make_node_id() -> str:
    """node_id 발급 — uuid4 짧은 문자열."""
    return uuid.uuid4().hex[:12]


def make_root(case_id: str, initial_posterior: dict[str, float]) -> ClueTree:
    """uniform prior 로 시작하는 빈 트리 생성.

    root 노드는 가상의 "ROOT" 단서 1개 (사전 정보 없음).
    """
    root_id = make_node_id()
    now = datetime.utcnow().isoformat() + "Z"
    root_node = ClueTreeNode(
        node_id=root_id,
        parent_id=None,
        depth=0,
        clue_key=ROOT_CLUE_KEY,  # R.1 — 모듈 상수
        category=ROOT_CATEGORY,
        value="initial",
        label="수사 시작 (uniform prior 1/8)",
        source="system",  # ClueSource Literal — 가상 ROOT 노드
        score_delta={},
        posterior_after=dict(initial_posterior),
        accepted_at=now,
        children_candidates=[],
    )
    return ClueTree(
        case_id=case_id,
        root_id=root_id,
        nodes={root_id: root_node},
        current_leaf_id=root_id,
        posterior_current=dict(initial_posterior),
        confidence_reached=False,
        incident_type_recommendation=None,
        created_at=now,
        updated_at=now,
    )


def append_clue_node(
    tree: ClueTree,
    parent_id: str,
    clue_key: str,
    category: str,
    value: str,
    label: str,
    source: str,
    posterior_before: dict[str, float],
    posterior_after: dict[str, float],
) -> ClueTreeNode:
    """단서 채택 → 트리에 노드 추가. posterior_current·current_leaf_id 갱신.

    score_delta = posterior_after − posterior_before (사고유형별 변동).
    """
    if parent_id not in tree.nodes:
        raise ValueError(f"parent_id {parent_id} 가 트리에 없음")

    parent = tree.nodes[parent_id]
    new_id = make_node_id()
    now = datetime.utcnow().isoformat() + "Z"

    score_delta = {
        h: posterior_after.get(h, 0.0) - posterior_before.get(h, 0.0)
        for h in posterior_after
    }

    node = ClueTreeNode(
        node_id=new_id,
        parent_id=parent_id,
        depth=parent.depth + 1,
        clue_key=clue_key,
        category=category,
        value=value,
        label=label,
        source=source,
        score_delta=score_delta,
        posterior_after=dict(posterior_after),
        accepted_at=now,
        children_candidates=[],
        stage=tree.stage,
    )
    tree.nodes[new_id] = node
    tree.current_leaf_id = new_id
    tree.posterior_current = dict(posterior_after)
    tree.updated_at = now
    return node


def set_candidates(
    tree: ClueTree, node_id: str, candidates: list[ClueCandidate]
) -> None:
    """노드의 다음 후보 (점선 child) 갱신."""
    if node_id not in tree.nodes:
        raise ValueError(f"node_id {node_id} 가 트리에 없음")
    tree.nodes[node_id].children_candidates = list(candidates)
    tree.updated_at = datetime.utcnow().isoformat() + "Z"


# ─────────────────────────────────────────────────────────────
# Entropy + 동적 후보 개수 (사용자 결정: 동적 entropy 기반)
# ─────────────────────────────────────────────────────────────


def posterior_entropy(posterior: dict[str, float]) -> float:
    """사후확률 분포의 Shannon entropy (bits).

    sentinel(UNCLASSIFIED) 는 제외. 0 ≤ H ≤ log2(INCIDENT_COUNT) bits.

    R.1 (hard) — real_hypotheses 헬퍼 + INCIDENT_COUNT 상수 사용으로 매직 제거.
    """
    p = [v for v in real_hypotheses(posterior).values() if v > 0]
    s = sum(p)
    if s <= 0:
        return math.log2(INCIDENT_COUNT)  # 정보 없음 = 최대 entropy
    p = [x / s for x in p]
    return -sum(x * math.log2(x) for x in p if x > 0)


def candidate_count_by_entropy(posterior: dict[str, float]) -> int:
    """사후확률 분포의 entropy 에 따라 다음 후보 노출 개수 결정.

    사용자 결정 (2026-05-25, paradigm doc §16) — 동적 entropy 기반.

    R.3 (hard) — 임계값을 data/triage/confidence_policy.json 외부화.
    JSON 의 entropy_candidate_k.thresholds 가 단일 출처.
    """
    H = posterior_entropy(posterior)
    return _resolve_k_by_entropy(H)


# ─────────────────────────────────────────────────────────────
# Confidence — 도달 시 알림만 (사용자 결정, paradigm doc §16)
# ─────────────────────────────────────────────────────────────


def evaluate_confidence(
    posterior: dict[str, float], depth: int = 0
) -> dict:
    """현재 사후확률 기반 confidence 평가.

    Phase K 후속 (2026-05-26 byungwoo) — **depth 별 차등 임계값** 도입.
    사용자 피드백: 단서 2-3개만으로 너무 빠른 확정 도달. 단서 충분히 모인
    후에야 확정 허용하도록 점진 완화.

    임계값 정책
    ----------
        depth = 0    : 가상의 ROOT 만 — confidence 도달 불가
        depth 1-2    : 매우 엄격 — primary_p ≥ 0.85 + gap ≥ 0.35
                       (강한 단서 1-2개만으로 확정 차단)
        depth 3-4    : 엄격 — primary_p ≥ 0.75 + gap ≥ 0.25
                       (단서 3-4개 누적되어야 확정 허용)
        depth ≥ 5    : 표준 — primary_p ≥ 0.65 + gap ≥ 0.20
                       (bayesian.py:confidence_level Phase 3.5 grid 값)

    트리 자동 종료 X — UI 에 알림 카드만 노출 (paradigm doc §16).
    """
    # R.1 (hard) — real_hypotheses 헬퍼로 sentinel 일관 제외
    ranked = sorted(
        real_hypotheses(posterior).items(),
        key=lambda x: -x[1],
    )

    primary, primary_p = (ranked[0] if ranked else (None, 0.0))
    secondary, secondary_p = (ranked[1] if len(ranked) > 1 else (None, 0.0))
    gap = primary_p - secondary_p
    H = posterior_entropy(posterior)

    # R.3 (hard) — depth 차등 임계값을 data/triage/confidence_policy.json 외부화.
    # 사용자 피드백 정책 (paradigm doc §16 + 2026-05-26 "단서 2-3개 너무 빠른 확정")
    # 은 JSON 단일 출처에서 관리. 함수 본문은 정책 lookup 만 수행.
    auto_confirm, gap_req = _resolve_depth_policy(depth)

    reached = primary_p >= auto_confirm and gap >= gap_req

    # R.3 (hard) — confidence_levels 보조 레벨도 JSON 외부화.
    policy = load_confidence_policy()
    medium = policy["confidence_levels"]["medium"]
    low = policy["confidence_levels"]["low"]

    if reached:
        action = "notify_user_confirm"  # 알림 카드 노출, 사용자가 [확정] 클릭 대기
    elif primary_p >= float(medium["primary_p_min"]) and gap >= float(medium["gap_min"]):
        action = "propose_single"
    elif primary_p >= float(low["primary_p_min"]):
        action = "propose_composite"
    else:
        action = "continue_collecting"

    return {
        "primary": primary,
        "primary_prob": primary_p,
        "secondary": secondary,
        "secondary_prob": secondary_p,
        "gap": gap,
        "confidence_reached": reached,
        "recommended_action": action,
        "entropy_bits": H,
        # Phase K 후속 — 디버그·UI 안내용
        "depth": depth,
        "thresholds": {"auto_confirm": auto_confirm, "gap_req": gap_req},
    }


# ─────────────────────────────────────────────────────────────
# 직렬화 (DB JSON 컬럼 / API 응답)
# ─────────────────────────────────────────────────────────────


def tree_to_dict(tree: ClueTree) -> dict:
    """ClueTree → JSON 직렬화 가능 dict.

    DB `incident_cases.triage_state` JSON 컬럼 영속화용.
    """
    return {
        "case_id": tree.case_id,
        "root_id": tree.root_id,
        "current_leaf_id": tree.current_leaf_id,
        "posterior_current": tree.posterior_current,
        "confidence_reached": tree.confidence_reached,
        "incident_type_recommendation": tree.incident_type_recommendation,
        "created_at": tree.created_at,
        "updated_at": tree.updated_at,
        "nodes": {nid: asdict(n) for nid, n in tree.nodes.items()},
        # Phase N.4 — Multi-Stage 추적
        "confirmed_hypotheses": list(tree.confirmed_hypotheses),
        "stage": tree.stage,
    }


def tree_from_dict(data: dict) -> ClueTree:
    """JSON dict → ClueTree 역직렬화. DB 로드용."""
    nodes_raw = data.get("nodes", {})
    nodes: dict[str, ClueTreeNode] = {}
    for nid, n in nodes_raw.items():
        # techniques 필드는 Phase H.4 신규 — 과거 직렬화 데이터 호환 위해 default 보장
        children = []
        for c in n.get("children_candidates", []):
            c = {**c}  # 입력 mutate 방지
            c.setdefault("techniques", [])
            c.setdefault("outcome_flags", {})
            children.append(ClueCandidate(**c))
        nodes[nid] = ClueTreeNode(
            node_id=n["node_id"],
            parent_id=n.get("parent_id"),
            depth=n["depth"],
            clue_key=n["clue_key"],
            category=n["category"],
            value=n["value"],
            label=n["label"],
            source=n.get("source", "unknown"),
            score_delta=dict(n.get("score_delta", {})),
            posterior_after=dict(n.get("posterior_after", {})),
            accepted_at=n.get("accepted_at", ""),
            children_candidates=children,
            stage=int(n.get("stage", 1)),
        )
    return ClueTree(
        case_id=data["case_id"],
        root_id=data["root_id"],
        nodes=nodes,
        current_leaf_id=data.get("current_leaf_id", data["root_id"]),
        posterior_current=dict(data.get("posterior_current", {})),
        confidence_reached=bool(data.get("confidence_reached", False)),
        incident_type_recommendation=data.get("incident_type_recommendation"),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        # Phase N.4 — Multi-Stage 추적 (legacy 호환: default [], 1)
        confirmed_hypotheses=list(data.get("confirmed_hypotheses", [])),
        stage=int(data.get("stage", 1)),
    )


def path_from_root(tree: ClueTree, node_id: Optional[str] = None) -> list[ClueTreeNode]:
    """root → node_id 까지의 채택 단서 경로 반환 (선조 포함).

    node_id 미지정 시 current_leaf_id 사용. 시각화·시나리오 재생용.
    """
    target = node_id or tree.current_leaf_id
    if target not in tree.nodes:
        return []
    path: list[ClueTreeNode] = []
    cur: Optional[str] = target
    while cur is not None and cur in tree.nodes:
        node = tree.nodes[cur]
        path.append(node)
        cur = node.parent_id
    return list(reversed(path))


# ─────────────────────────────────────────────────────────────
# P.19 (2026-05-28, hard) — Invariant Healing
# ─────────────────────────────────────────────────────────────
#
# 배경 — P.18 (easy) 의 프론트 안전망 (collectPath root 강제 prepend, 중앙 ◆
# fallback, polyline 가시성) 은 시각적 손상을 막지만 백엔드 데이터 정합성
# 자체는 보장하지 않는다. 사용자 캡쳐 (라벨 1·2·4 + root 없음) 의 진짜 원인은
# tree.nodes 의 parent_id 체인이 어딘가에서 끊긴 케이스로 의심되며, 정상 호출
# 경로 (expand_tree → append_clue_node ValueError 검증, advance_stage 보존)
# 에서는 발생할 위치가 없다. 따라서 진짜 원인은 다음 중 하나로 추정한다:
#   1. 옛 버전에서 저장된 triage_state JSON 의 잔존 손상 (역호환 이슈)
#   2. 직렬화/역직렬화 사이클 중 외부 요인 (DB JSON 조작, 동시성 등)
#   3. 추후 추가될 진입점이 invariant 를 깨뜨림 (회귀 방어)
#
# 정책 — 응답·저장·로드 시점에 invariant 를 강제 보장 (in-memory healing 우선).
# 깨진 노드는 root 로 재연결하고 warning 로그로 발생 위치 식별 가능하게 한다.


def heal_tree_invariants(tree: ClueTree, *, logger=None) -> int:
    """ClueTree invariant 검증 + 자동 복구.

    검증 항목:
      1. root_id 노드가 tree.nodes 에 존재 (없으면 빈 root 재생성)
      2. 모든 비-root 노드의 parent_id 가 tree.nodes 에 존재
         (orphan 이면 tree.root_id 로 재연결)
      3. root 노드의 parent_id 가 None (외부 변경 흔적 복구)
      4. current_leaf_id 가 tree.nodes 에 존재 (없으면 root_id 로 fallback)

    in-memory healing 만 수행 — caller 가 명시적으로 save 호출해야 영구 반영.
    이는 진짜 원인 추적을 위해 원본 손상 흔적을 즉시 덮어쓰지 않으려는 의도.

    Args:
        tree: 검증·복구 대상 ClueTree (mutated in-place)
        logger: optional logging.Logger — 복구 이벤트 기록용

    Returns:
        복구된 invariant 위반 건수 (0 = 정합).
    """
    healed = 0

    # 1. root 노드 존재 보장
    if tree.root_id not in tree.nodes:
        if logger:
            logger.error(
                "heal_tree_invariants: root_id=%s NOT IN nodes — recreating empty root (case=%s)",
                tree.root_id,
                tree.case_id,
            )
        now = datetime.utcnow().isoformat() + "Z"
        tree.nodes[tree.root_id] = ClueTreeNode(
            node_id=tree.root_id,
            parent_id=None,
            depth=0,
            clue_key=ROOT_CLUE_KEY,  # R.1 — 모듈 상수 (make_root 와 통일)
            category=ROOT_CATEGORY,
            value="recreated",
            label="수사 시작 (heal: 복구된 root)",
            source="heal",
            score_delta={},
            posterior_after=dict(tree.posterior_current),
            accepted_at=now,
            children_candidates=[],
        )
        healed += 1

    # 2·3. parent_id 정합성
    for nid, n in tree.nodes.items():
        if nid == tree.root_id:
            # root 는 parent_id 가 None 이어야 정상
            if n.parent_id is not None:
                if logger:
                    logger.warning(
                        "heal_tree_invariants: root %s has non-None parent_id=%s — resetting (case=%s)",
                        nid,
                        n.parent_id,
                        tree.case_id,
                    )
                n.parent_id = None
                healed += 1
            continue
        if n.parent_id is None or n.parent_id not in tree.nodes:
            if logger:
                logger.warning(
                    "heal_tree_invariants: %s (depth=%d, clue=%s) orphan parent_id=%s → reattach to root (case=%s)",
                    nid,
                    n.depth,
                    n.clue_key,
                    n.parent_id,
                    tree.case_id,
                )
            n.parent_id = tree.root_id
            healed += 1

    # 4. current_leaf_id 존재 보장
    if tree.current_leaf_id and tree.current_leaf_id not in tree.nodes:
        if logger:
            logger.warning(
                "heal_tree_invariants: current_leaf_id=%s NOT IN nodes — fallback to root_id (case=%s)",
                tree.current_leaf_id,
                tree.case_id,
            )
        tree.current_leaf_id = tree.root_id
        healed += 1

    return healed
