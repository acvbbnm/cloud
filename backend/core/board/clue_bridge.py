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

# ── 좌표 상수 (보드 캔버스 1100×620 격자 배치) ──
# NODE_W=168, NODE_H=64 + 충분한 여유 (X 200, Y 95 셀)
BRIDGE_BASE_X = 80
BRIDGE_BASE_Y = 80
BRIDGE_CELL_W = 200
BRIDGE_CELL_H = 95
BRIDGE_COLS = 5         # 5열 (가로 = 80 + 5*200 = 1080 < 1100 OK)
BRIDGE_X_STEP = 240     # legacy — _next_base_x 가 max(pos_x)+step 으로 사용
BRIDGE_FALLBACK_X = 80  # 기존 노드 없을 때 시작 x


def _is_overlap(
    x: int, y: int, taken: list[tuple[int, int]],
    *, gap_x: int = 200, gap_y: int = 95,
) -> bool:
    """주어진 (x, y) 가 기존 노드 위치 중 어느 것과 겹치면 True."""
    return any(abs(x - tx) < gap_x and abs(y - ty) < gap_y for tx, ty in taken)


def _next_free_slot(
    taken: list[tuple[int, int]],
    *, start_idx: int = 0,
) -> tuple[int, int]:
    """비어 있는 격자 셀 좌표 반환. row-major 순서로 탐색.

    겹침이 없을 때까지 격자를 늘려가며 자리 확보 (최대 200 슬롯).
    """
    for i in range(start_idx, start_idx + 200):
        r, c = divmod(i, BRIDGE_COLS)
        x = BRIDGE_BASE_X + c * BRIDGE_CELL_W
        y = BRIDGE_BASE_Y + r * BRIDGE_CELL_H
        if not _is_overlap(x, y, taken):
            return x, y
    # fallback — 200 슬롯 다 차면 그냥 row-major
    r, c = divmod(start_idx, BRIDGE_COLS)
    return BRIDGE_BASE_X + c * BRIDGE_CELL_W, BRIDGE_BASE_Y + r * BRIDGE_CELL_H


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

    # anchor 가설 — tree 의 마지막 확정 가설
    anchor_hypothesis: Optional[str] = (
        tree.confirmed_hypotheses[-1] if tree.confirmed_hypotheses else None
    )

    # 기존 보드 노드 좌표 수집 — 충돌 회피용
    existing_positions: list[tuple[int, int]] = [
        (n.pos_x, n.pos_y)
        for n in db.query(ChainNodeModel)
        .filter(ChainNodeModel.case_id == case_id)
        .all()
        if n.pos_x is not None and n.pos_y is not None
    ]

    created_nodes: list[ChainNodeModel] = []
    skipped: list[dict] = []

    for tnode in path:
        if tnode.clue_key in existing_keys:
            skipped.append(
                {"clue_key": tnode.clue_key, "reason": "already_on_board"}
            )
            continue

        # label — clue_tree node label > catalog short_label > clue_key fallback
        label = (
            tnode.label
            or ChainNode.derive_label_from_clue(tnode.clue_key)
            or tnode.clue_key
        )

        meta = ChainNode.build_clue_meta(
            clue_key=tnode.clue_key,
            stage=tree.stage,
            hypothesis=anchor_hypothesis,
            source=source,
            extra={
                "tree_node_id": tnode.node_id,
                "tree_depth": tnode.depth,
                "tree_source": tnode.source,  # tree_candidate | direct_input | log_analysis
            },
        )

        # 격자 빈 자리 자동 탐색 (기존 노드 + 같은 호출 내 추가 노드 모두 회피)
        pos_x, pos_y = _next_free_slot(existing_positions)
        existing_positions.append((pos_x, pos_y))

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
