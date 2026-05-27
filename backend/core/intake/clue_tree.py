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

import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional


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
    """

    node_id: str
    parent_id: Optional[str]
    depth: int
    # 채택된 단서 정보
    clue_key: str  # 카탈로그 키
    category: str
    value: str
    label: str
    source: str  # "tree_candidate" | "direct_input" | "log_analysis"
    # 베이즈 갱신 결과
    score_delta: dict[str, float] = field(default_factory=dict)
    posterior_after: dict[str, float] = field(default_factory=dict)
    accepted_at: str = ""  # ISO-8601
    # 다음 후보 (자식 들)
    children_candidates: list[ClueCandidate] = field(default_factory=list)


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
        clue_key="__ROOT__",
        category="ROOT",
        value="initial",
        label="수사 시작 (uniform prior 1/8)",
        source="system",
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

    UNCLASSIFIED 는 제외. 0 ≤ H ≤ log2(8) = 3.0 bits.
    """
    p = [v for k, v in posterior.items() if k != "UNCLASSIFIED" and v > 0]
    s = sum(p)
    if s <= 0:
        return math.log2(8)  # 정보 없음 = 최대 entropy
    p = [x / s for x in p]
    return -sum(x * math.log2(x) for x in p if x > 0)


def candidate_count_by_entropy(posterior: dict[str, float]) -> int:
    """사후확률 분포의 entropy 에 따라 다음 후보 노출 개수 결정.

    사용자 결정 (2026-05-25, paradigm doc §16) — 동적 entropy 기반.

    임계값
    -----
        H ≥ 2.5 bits (모호, uniform 근처) → 5개
        1.5 ≤ H < 2.5 (점차 좁혀짐)       → 3개
        H < 1.5 (수렴 단계)               → 2개
    """
    H = posterior_entropy(posterior)
    if H >= 2.5:
        return 5
    if H >= 1.5:
        return 3
    return 2


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
    ranked = sorted(
        [(h, p) for h, p in posterior.items() if h != "UNCLASSIFIED"],
        key=lambda x: -x[1],
    )

    primary, primary_p = (ranked[0] if ranked else (None, 0.0))
    secondary, secondary_p = (ranked[1] if len(ranked) > 1 else (None, 0.0))
    gap = primary_p - secondary_p
    H = posterior_entropy(posterior)

    # depth 별 임계값 (사용자 피드백 2026-05-26 — "단서 2-3개로 너무 빠른 확정")
    # 정책: 최소 3 단서 (depth ≥ 3) 채택 후에만 확정 허용. 그 이전엔 절대 차단.
    MIN_DEPTH_FOR_CONFIRM = 3
    if depth < MIN_DEPTH_FOR_CONFIRM:
        auto_confirm, gap_req = 1.01, 1.01  # 절대 도달 불가
    elif depth == 3:
        auto_confirm, gap_req = 0.80, 0.30
    elif depth == 4:
        auto_confirm, gap_req = 0.75, 0.25
    else:  # depth ≥ 5
        auto_confirm, gap_req = 0.65, 0.20  # 표준 (Phase 3.5 fitted)

    reached = primary_p >= auto_confirm and gap >= gap_req

    if reached:
        action = "notify_user_confirm"  # 알림 카드 노출, 사용자가 [확정] 클릭 대기
    elif primary_p >= 0.60 and gap >= 0.10:
        action = "propose_single"
    elif primary_p >= 0.30:
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
