"""Phase O.3 — Evidence Tree → Investigation Board bridge (2026-05-26 byungwoo).

paradigm doc §24 Phase O — Evidence Board 통합.

사용자 비전 (2026-05-26):
    "단서들이 수사보드에 연동되어서 수사보드에서 단서들을 조합해보면서
     타임라인을 직접 예측하며 어택 체인을 재구성"

핵심 책임:
    Evidence Tree (clue_tree_service) 가 누적한 채택 단서 path 를
    chain_nodes (보드) 의 type='clue' 노드로 일괄 이관.

설계 결정:
    1. 멱등성 — 같은 case 보드에 동일 clue_key 노드 있으면 skip
       (단서 조합 UX 가 중복 노드로 혼란되지 않도록)
    2. 엣지 자동 생성은 옵션 (include_edges) — 기본 OFF.
       paradigm §16 "AI 비판단" 정합: 타임라인 순서는 수사관 판단.
    3. 좌표 — 기존 보드 노드 우측에서 horizontal 분포 (지그재그).
       사용자가 보드에서 자유 드래그로 재배치.
    4. anchor 가설 — tree.confirmed_hypotheses[-1] 사용. 미확정 시 None.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.board.chain import ChainEdge, ChainNode
from core.intake.clue_tree import ClueTree, path_from_root
from db.models import ChainNodeModel

# ── 좌표 상수 (시연 안정성 — 보드 캔버스 1200×800 가정) ──
BRIDGE_BASE_Y = 200
BRIDGE_X_STEP = 240
BRIDGE_Y_JITTER = 60
BRIDGE_FALLBACK_X = 80  # 기존 노드 없을 때 시작 x


def _collect_existing_clue_keys(db: Session, case_id: str) -> set[str]:
    """이미 보드에 올라간 단서 clue_key 집합 (멱등 차단용).

    type='clue' 또는 meta.clue_key 가 있는 노드만 추출.
    """
    nodes = db.execute(
        select(ChainNodeModel).where(ChainNodeModel.case_id == case_id)
    ).scalars()
    keys: set[str] = set()
    for n in nodes:
        meta = n.meta or {}
        ck = meta.get("clue_key")
        if ck:
            keys.add(ck)
    return keys


def _next_base_x(db: Session, case_id: str) -> int:
    """기존 보드 노드들의 max(pos_x) 다음 위치를 신규 노드 시작점으로."""
    nodes = list(
        db.execute(
            select(ChainNodeModel.pos_x).where(ChainNodeModel.case_id == case_id)
        ).scalars()
    )
    xs = [x for x in nodes if x is not None]
    if not xs:
        return BRIDGE_FALLBACK_X
    return max(xs) + BRIDGE_X_STEP


def bridge_clue_tree_to_board(
    db: Session,
    case_id: str,
    tree: ClueTree,
    *,
    source: str = "manual_bulk",
    include_root: bool = False,
    include_edges: bool = False,
    node_ids: Optional[list[str]] = None,
) -> dict:
    """Evidence Tree path 의 채택 단서를 보드 노드로 일괄 이관.

    Args:
        case_id: 대상 사고 케이스
        tree: ClueTree (이미 _load_tree_from_case 로 로드된 상태)
        source: 신규 노드 meta.source (기본 "manual_bulk" — 사용자 일괄)
        include_root: root 가상 노드 포함 여부 (기본 False)
        include_edges: path 순서대로 엣지 자동 생성 (기본 False)
        node_ids: 부분 이관 — 특정 tree 노드만. None 이면 전체 path

    Returns:
        {
          "created_nodes": [serialize(ChainNodeModel)...],
          "skipped":       [{"clue_key": ..., "reason": ...}, ...],
          "created_edges": [serialize(ChainEdgeModel)...]
        }
    """
    path = path_from_root(tree)

    # root 제외 (default)
    if not include_root:
        path = [n for n in path if n.clue_key and n.clue_key != "__ROOT__"]

    # 부분 이관
    if node_ids is not None:
        node_id_set = set(node_ids)
        path = [n for n in path if n.node_id in node_id_set]

    # 멱등 — 기존 보드에 있는 clue_key 차단
    existing_keys = _collect_existing_clue_keys(db, case_id)

    # P.33 (2026-05-31 사용자 피드백: "현재 랜섬인 상태면 랜섬 마킹이 다
    #   붙어버려서 7개는 자격증명 7개는 권한상승 7개는 랜섬이었는데 한번에
    #   떡져서 나와") — anchor_hypothesis 변수(모든 단서 동일) 제거.
    #   각 단서의 ClueTreeNode.stage 로 confirmed_hypotheses 매칭.
    #
    #   confirmed_hypotheses 는 stage 별 확정 사고유형 시퀀스:
    #     stage 1 단서 → confirmed[0] (예: CREDENTIAL_THEFT)
    #     stage 2 단서 → confirmed[1] (예: PRIVILEGE_ESCALATION)
    #     stage 3 단서 → confirmed[2] (예: RANSOMWARE)
    #
    #   stage > len(confirmed) 면 미확정 (현재 진행 중 stage) → None.

    def _hypothesis_for_stage(node_stage: int) -> Optional[str]:
        if not tree.confirmed_hypotheses:
            return None
        idx = max(0, (node_stage or 1) - 1)
        if idx < len(tree.confirmed_hypotheses):
            return tree.confirmed_hypotheses[idx]
        # 미확정 stage (현재 진행 중) — None 으로 라벨 미부착.
        # 사용자 fix 의도: 그 stage 의 단서가 *어느* 사고유형인지 모를 때는
        # 잘못된 (마지막 확정) 사고유형 라벨을 강제하지 않는다.
        return None

    # 좌표 시작점
    base_x = _next_base_x(db, case_id)

    created_nodes: list[ChainNodeModel] = []
    skipped: list[dict] = []

    for idx, tnode in enumerate(path):
        if tnode.clue_key in existing_keys:
            skipped.append(
                {"clue_key": tnode.clue_key, "reason": "already_on_board"}
            )
            continue

        # label — P.34 (사용자: "보드 정보는 intake 와 똑같은게 아니라 어떤
        #   단서인지 설명이 나와야") — derive_label_from_clue 가 description
        #   풀이 합성한 풍부 라벨을 만들면 그것을 우선 사용.
        #   직접 입력 단서 (catalog 누락) 는 합성 불가 → tnode.label fallback.
        rich = ChainNode.derive_label_from_clue(tnode.clue_key)
        is_rich = bool(rich and " — " in rich)
        label = rich if is_rich else (tnode.label or rich or tnode.clue_key)

        # P.33 — 각 단서의 stage 로 confirmed 매칭 (마지막 가설 일괄 부착 X)
        node_hypothesis = _hypothesis_for_stage(tnode.stage)
        meta = ChainNode.build_clue_meta(
            clue_key=tnode.clue_key,
            stage=tnode.stage,  # P.33 — tree.stage(현재) 대신 단서 본인 stage
            hypothesis=node_hypothesis,
            source=source,
            extra={
                "tree_node_id": tnode.node_id,
                "tree_depth": tnode.depth,
                "tree_source": tnode.source,  # tree_candidate | direct_input | log_analysis
            },
        )

        pos_x = base_x + idx * BRIDGE_X_STEP
        pos_y = BRIDGE_BASE_Y + (idx % 2) * BRIDGE_Y_JITTER

        node = ChainNode.create(
            db,
            case_id=case_id,
            label=label,
            attack_id=None,
            is_ai_suggested=False,
            pos_x=pos_x,
            pos_y=pos_y,
            meta=meta,
        )
        created_nodes.append(node)
        existing_keys.add(tnode.clue_key)  # 같은 호출 내 중복 방지

    # 엣지 — 새로 만든 노드 인접쌍만 (skip 된 자리 건너뛰지 않음).
    # 기존 노드 ↔ 새 노드 자동 연결은 X (사용자 의도 모호).
    created_edges: list = []
    if include_edges and len(created_nodes) >= 2:
        for prev, nxt in zip(created_nodes, created_nodes[1:]):
            edge = ChainEdge.create(
                db,
                case_id=case_id,
                from_node_id=prev.node_id,
                to_node_id=nxt.node_id,
                label="단서 시퀀스",
            )
            created_edges.append(edge)

    return {
        "created_nodes": [ChainNode.serialize(n) for n in created_nodes],
        "skipped": skipped,
        "created_edges": [ChainEdge.serialize(e) for e in created_edges],
    }
