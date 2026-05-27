"""Layer 4 — Investigation Board API 라우터.

설계서 5.6.5절 + API_계약서 Layer 4 섹션 + UC-06 시퀀스.

- POST  /api/board/nodes              — 노드 추가 (attack_id ⊕ clue_key)
- POST  /api/board/nodes/from-clue-tree — Evidence Tree → 보드 일괄 bridge (Phase O.3)
- PATCH /api/board/nodes/{node_id}    — 노드 수락/거부 (action_logs 적재)
- POST  /api/board/edges              — 엣지 추가 (양 끝 노드 검증)
- GET   /api/board?caseId=            — case 전체 보드 상태
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.board.chain import ChainEdge, ChainNode
from core.board.clue_bridge import bridge_clue_tree_to_board
from core.board.investigation_board import InvestigationBoard
from core.intake.clue_tree_service import _load_tree_from_case  # Phase O.3 — internal helper
from core.intake.incident_case import IncidentCase
from db.models import ActionLogModel, AttackEventModel
from db.session import get_db

router = APIRouter(prefix="/api/board", tags=["board"])


NodeStatus = Literal["CONFIRMED", "REJECTED"]


# ── 요청 스키마 ──────────────────────────────────────────


class CreateNodeRequest(BaseModel):
    caseId: str
    attack_id: Optional[str] = None
    clue_key: Optional[str] = None  # Phase O — 단서 1st-class 노드 (XOR with attack_id)
    label: Optional[str] = None  # 미지정 시 attack_id/clue_key 기반 자동 생성 시도
    is_ai_suggested: bool = False
    pos_x: Optional[int] = Field(default=None, ge=-10000, le=10000)
    pos_y: Optional[int] = Field(default=None, ge=-10000, le=10000)
    # Phase O — 단서 노드 메타 (clue_key 동반 시 build_clue_meta 입력)
    stage: Optional[int] = Field(default=None, ge=1, le=20)
    hypothesis: Optional[str] = None
    source: Optional[str] = None  # 'manual_drag' | 'auto_seed' | 'user_added'
    meta: Optional[dict] = None  # 명시 meta (clue_key 없을 때도 attack 노드 보강 가능)


class UpdateNodeRequest(BaseModel):
    status: Optional[NodeStatus] = None
    pos_x: Optional[int] = Field(default=None, ge=-10000, le=10000)
    pos_y: Optional[int] = Field(default=None, ge=-10000, le=10000)
    label: Optional[str] = None
    meta: Optional[dict] = None  # Phase O — meta 부분 갱신 (shallow merge)


class CreateEdgeRequest(BaseModel):
    caseId: str
    from_node_id: str
    to_node_id: str
    label: Optional[str] = None


class BridgeFromClueTreeRequest(BaseModel):
    """Phase O.3 — Evidence Tree → 보드 일괄 bridge 요청."""

    caseId: str
    source: str = "manual_bulk"  # 신규 노드 meta.source
    include_root: bool = False
    include_edges: bool = False
    node_ids: Optional[list[str]] = None  # 부분 이관 (None=전체 path)


# ── 에러 헬퍼 ────────────────────────────────────────────


def _case_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "status": "error",
            "message": "케이스를 찾을 수 없습니다",
            "code": "CASE_NOT_FOUND",
        },
    )


def _node_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "status": "error",
            "message": "노드를 찾을 수 없습니다",
            "code": "NODE_NOT_FOUND",
        },
    )


# ── 엔드포인트 ────────────────────────────────────────────


@router.post("/nodes", status_code=status.HTTP_201_CREATED)
async def create_node(req: CreateNodeRequest, db: Session = Depends(get_db)) -> dict:
    """수사 보드 노드를 추가한다.

    Phase O (2026-05-26) — 단서 1st-class 노드 지원:
      - attack_id 만 → 기존 ATT&CK 노드 (meta=None 또는 사용자 명시 meta)
      - clue_key 만 → 단서 노드 (meta auto-build: type=clue, clue_key, stage, ...)
      - 둘 다 X → label 필수 (unnamed AI 후보 노드)
      - 둘 다 O → 400 (상호 배타)

    - label 미지정 + attack_id 주어진 경우 ATT&CK 기반 기본 라벨 자동 생성
    - label 미지정 + clue_key 주어진 경우 clue_catalog short_label 추출
    """
    case = IncidentCase.get_by_id(db, req.caseId)
    if case is None:
        raise _case_not_found()

    # Phase O — attack_id 와 clue_key 동시 지정 금지
    if req.attack_id and req.clue_key:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "attack_id 와 clue_key 는 동시에 지정할 수 없습니다",
                "code": "NODE_TYPE_AMBIGUOUS",
            },
        )

    # attack_id 유효성 검증 (있을 때만)
    if req.attack_id:
        att = db.get(AttackEventModel, req.attack_id)
        if att is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": "attack_id 가 존재하지 않습니다",
                    "code": "ATTACK_NOT_FOUND",
                },
            )

    # 라벨 자동 생성 — attack > clue > unnamed
    label = (
        req.label
        or ChainNode.derive_label_from_attack(db, req.attack_id)
        or ChainNode.derive_label_from_clue(req.clue_key)
        or "(unnamed)"
    )

    # meta 결정 — clue_key 우선 (자동 빌드), 없으면 명시 meta
    if req.clue_key:
        meta = ChainNode.build_clue_meta(
            clue_key=req.clue_key,
            stage=req.stage or 1,
            hypothesis=req.hypothesis,
            source=req.source or "manual_drag",
            extra=req.meta,
        )
    else:
        meta = req.meta

    node = ChainNode.create(
        db,
        case_id=req.caseId,
        label=label,
        attack_id=req.attack_id,
        is_ai_suggested=req.is_ai_suggested,
        pos_x=req.pos_x,
        pos_y=req.pos_y,
        meta=meta,
    )
    return {"status": "ok", "data": ChainNode.serialize(node)}


@router.post("/nodes/from-clue-tree", status_code=status.HTTP_201_CREATED)
async def bridge_from_clue_tree(
    req: BridgeFromClueTreeRequest, db: Session = Depends(get_db)
) -> dict:
    """Phase O.3 — Evidence Tree 의 채택 단서를 보드 노드로 일괄 이관.

    사용자 비전: 단서들을 보드에서 조합하며 타임라인·어택 체인 재구성.

    동작:
      - tree 채택 path → type='clue' 보드 노드 batch 생성
      - 같은 case 보드에 동일 clue_key 노드가 이미 있으면 skip (멱등)
      - include_edges=True 시 path 순서대로 ChainEdge 자동 생성
      - include_root=True 시 root 가상 노드도 포함 (보통 False)
      - node_ids 부분 이관 — 특정 tree node 만 선택

    실패:
      - case 미존재 → 404
      - tree 미생성 → 404 EVIDENCE_TREE_NOT_FOUND (먼저 evidence tree 진행 필요)
    """
    case = IncidentCase.get_by_id(db, req.caseId)
    if case is None:
        raise _case_not_found()

    tree = _load_tree_from_case(case)
    if tree is None:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": "Evidence Tree 가 아직 생성되지 않았습니다. "
                "먼저 단서 트리를 진행하세요.",
                "code": "EVIDENCE_TREE_NOT_FOUND",
            },
        )

    result = bridge_clue_tree_to_board(
        db,
        case_id=req.caseId,
        tree=tree,
        source=req.source,
        include_root=req.include_root,
        include_edges=req.include_edges,
        node_ids=req.node_ids,
    )
    return {"status": "ok", "data": result}


@router.patch("/nodes/{node_id}")
async def update_node(
    node_id: str, req: UpdateNodeRequest, db: Session = Depends(get_db)
) -> dict:
    """노드 상태·좌표·라벨을 부분 갱신한다.

    status 가 CONFIRMED/REJECTED 로 바뀌면 action_logs 에 ACCEPT/REJECT 기록.
    """
    existing = ChainNode.get_by_id(db, node_id)
    if existing is None:
        raise _node_not_found()

    prev_status = existing.status
    updated = ChainNode.update(
        db,
        node_id=node_id,
        status=req.status,
        pos_x=req.pos_x,
        pos_y=req.pos_y,
        label=req.label,
        meta=req.meta,
    )
    if updated is None:
        raise _node_not_found()

    # status 가 실제로 변경된 경우만 action_logs 적재
    if req.status is not None and req.status != prev_status:
        action_map = {"CONFIRMED": "ACCEPT", "REJECTED": "REJECT"}
        action = action_map.get(req.status)
        if action:
            log = ActionLogModel(
                case_id=updated.case_id,
                actor="investigator",  # CLAUDE.md 단일 수사관 정책
                action=action,
                target_type="chain_node",
                target_id=node_id,
                detail={"from": prev_status, "to": req.status},
            )
            db.add(log)
            db.commit()

    return {"status": "ok", "data": ChainNode.serialize(updated)}


@router.post("/edges", status_code=status.HTTP_201_CREATED)
async def create_edge(req: CreateEdgeRequest, db: Session = Depends(get_db)) -> dict:
    """공격 체인 엣지를 추가한다. self-loop·case 불일치 검증."""
    case = IncidentCase.get_by_id(db, req.caseId)
    if case is None:
        raise _case_not_found()

    err = InvestigationBoard.validate_edge(
        db, req.caseId, req.from_node_id, req.to_node_id
    )
    if err is not None:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": err,
                "code": "INVALID_EDGE",
            },
        )

    edge = ChainEdge.create(
        db,
        case_id=req.caseId,
        from_node_id=req.from_node_id,
        to_node_id=req.to_node_id,
        label=req.label,
    )
    return {"status": "ok", "data": ChainEdge.serialize(edge)}


@router.get("")
async def get_board(
    caseId: str = Query(..., description="대상 사고 케이스 UUID"),
    db: Session = Depends(get_db),
) -> dict:
    """case 의 보드 전체 상태를 반환한다."""
    state = InvestigationBoard.get_state(db, caseId)
    if state is None:
        raise _case_not_found()
    return {"status": "ok", "data": state}
