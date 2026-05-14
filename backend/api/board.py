"""Layer 4 — Investigation Board API 라우터.

설계서 5.6.5절 + API_계약서 Layer 4 섹션 + UC-06 시퀀스.

- POST  /api/board/nodes              — 노드 추가
- PATCH /api/board/nodes/{node_id}    — 노드 수락/거부 (action_logs 적재)
- POST  /api/board/edges              — 엣지 추가 (양 끝 노드 검증)
- GET   /api/board?caseId=            — case 전체 보드 상태
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.board.chain import ChainEdge, ChainNode
from core.board.investigation_board import InvestigationBoard
from core.intake.incident_case import IncidentCase
from db.models import ActionLogModel, AttackEventModel
from db.session import get_db

router = APIRouter(prefix="/api/board", tags=["board"])


NodeStatus = Literal["CONFIRMED", "REJECTED"]


# ── 요청 스키마 ──────────────────────────────────────────


class CreateNodeRequest(BaseModel):
    caseId: str
    attack_id: Optional[str] = None
    label: Optional[str] = None  # 미지정 시 attack_id 기반 자동 생성 시도
    is_ai_suggested: bool = False
    pos_x: Optional[int] = Field(default=None, ge=-10000, le=10000)
    pos_y: Optional[int] = Field(default=None, ge=-10000, le=10000)


class UpdateNodeRequest(BaseModel):
    status: Optional[NodeStatus] = None
    pos_x: Optional[int] = Field(default=None, ge=-10000, le=10000)
    pos_y: Optional[int] = Field(default=None, ge=-10000, le=10000)
    label: Optional[str] = None


class CreateEdgeRequest(BaseModel):
    caseId: str
    from_node_id: str
    to_node_id: str
    label: Optional[str] = None


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

    - label 미지정 + attack_id 주어진 경우 ATT&CK 기반 기본 라벨 자동 생성
    - attack_id 주어진 경우 동일 case 매핑인지 검증
    """
    case = IncidentCase.get_by_id(db, req.caseId)
    if case is None:
        raise _case_not_found()

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

    label = req.label or ChainNode.derive_label_from_attack(db, req.attack_id) or "(unnamed)"

    node = ChainNode.create(
        db,
        case_id=req.caseId,
        label=label,
        attack_id=req.attack_id,
        is_ai_suggested=req.is_ai_suggested,
        pos_x=req.pos_x,
        pos_y=req.pos_y,
    )
    return {"status": "ok", "data": ChainNode.serialize(node)}


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
