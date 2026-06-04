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


def _collect_existing_tree_node_ids(db: Session, case_id: str) -> set[str]:
    """이미 보드에 올라간 *트리 노드 ID* 집합 (멱등 차단용).

    P.41 (2026-06-04 사용자 피드백: "22개 중 5개만 옮겨졌어")
      변경: clue_key 멱등 → tree_node_id 멱등.
      같은 clue_key 가 트리에서 여러 번 채택 (예: TECHNIQUE:T1078.004 × 12)
      되어도 *각 채택 행위* (다른 tree_node_id) 는 별도 보드 노드로 이관.

      학술 정합: Pearl belief propagation 에서 같은 observable 의 *반복 관측*
      은 변별력 강화 — 보드 시각화에도 모두 표시되는 게 사건 전모 정합.

    meta.tree_node_id 가 있는 노드만 추출 (단서 노드 = clue_bridge 가 부여).
    """
    nodes = db.execute(
        select(ChainNodeModel).where(ChainNodeModel.case_id == case_id)
    ).scalars()
    ids: set[str] = set()
    for n in nodes:
        meta = n.meta or {}
        tid = meta.get("tree_node_id")
        if tid:
            ids.add(tid)
    return ids


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
    # P.40 (2026-06-04 사용자 피드백: "수사보드 넘어가는게 4개밖에 안 넘어가는게 문제")
    #   원인: path_from_root(tree) 가 root → current_leaf_id 의 *단일 경로* 만 반환.
    #         트리에 분기 (예: stage 1 중 직접 입력으로 다른 가지 채택 + stage 2 진입 시
    #         current_leaf 가 한 가지에 머물면) 다른 가지의 채택 단서가 path 에서 누락.
    #   Fix: tree.nodes 전체를 *채택 순서대로* 순회. 보드는 사건 전모 시각화이지 trail X.
    #
    #   include_root 옵션은 보존 — root 가상 노드 (__ROOT__) 표시 여부.
    #   node_ids 부분 이관 옵션도 보존 — 명시적 ID 리스트 받으면 그 노드만.
    #
    # 순서 보장: ClueTreeNode.depth 기준 오름차순 (root 0 → leaf N)
    #   → 보드 격자 배치 시 채택 순서대로 좌→우→하 흐름.
    all_nodes = sorted(tree.nodes.values(), key=lambda n: (n.depth, n.node_id))
    path = list(all_nodes)

    # root 제외 (default)
    if not include_root:
        path = [n for n in path if n.clue_key and n.clue_key != "__ROOT__"]

    # 부분 이관
    if node_ids is not None:
        node_id_set = set(node_ids)
        path = [n for n in path if n.node_id in node_id_set]

    # P.41 — 멱등 기준 변경 (clue_key → tree_node_id)
    #   같은 clue_key 가 여러 번 채택돼도 *각 채택 행위* 별 보드 노드 생성.
    existing_tree_node_ids = _collect_existing_tree_node_ids(db, case_id)

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
        # fix (2026-05-31) — stage > len(confirmed) 면 마지막 확정 가설을
        # anchor 로 사용. 현재 stage 의 단서들은 직전 확정 가설을 추적 중.
        return tree.confirmed_hypotheses[-1]

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
        # P.41 — tree_node_id 멱등 (같은 채택 행위만 차단, 같은 clue_key 는 허용)
        if tnode.node_id in existing_tree_node_ids:
            skipped.append(
                {
                    "clue_key": tnode.clue_key,
                    "tree_node_id": tnode.node_id,
                    "reason": "already_on_board",
                }
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
        # fix (2026-05-31) — tnode.stage 가 default 1 (명시 안 됨) 이면 tree.stage 사용.
        # 명시적으로 stage 가 다른 값으로 설정된 경우만 그 값 그대로 보존.
        effective_stage = tnode.stage if tnode.stage > 1 else tree.stage
        node_hypothesis = _hypothesis_for_stage(effective_stage)
        meta = ChainNode.build_clue_meta(
            clue_key=tnode.clue_key,
            stage=effective_stage,
            hypothesis=node_hypothesis,
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
        # P.41 — 같은 호출 내 중복 방지 (tree_node_id 기준)
        existing_tree_node_ids.add(tnode.node_id)

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
