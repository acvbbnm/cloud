"""공통 API — /api/actions (수사관 조작 이력 조회).

설계서 5.6절 + CLAUDE.md "Common — 액션 로그" 명세.

INSERT 는 board.py·report.py 가 PATCH/POST 시 자동 기록. 본 모듈은 SELECT 만 담당.

- GET /api/actions?caseId=&limit=&offset=  → 케이스의 액션 로그 (최신순)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.models import ActionLogModel, IncidentCaseModel
from db.session import get_db

router = APIRouter(prefix="/api", tags=["common"])


def _serialize_action(log: ActionLogModel) -> dict:
    """ActionLogModel → API 응답 dict."""
    return {
        "log_id": log.log_id,
        "case_id": log.case_id,
        "actor": log.actor,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "detail": log.detail,
        "logged_at": log.logged_at.isoformat() if log.logged_at else None,
    }


@router.get("/actions")
async def list_actions(
    caseId: str = Query(..., description="대상 사고 케이스 UUID"),
    limit: int = Query(100, ge=1, le=500, description="최대 반환 건수 (기본 100)"),
    offset: int = Query(0, ge=0, description="페이지네이션 오프셋"),
    action: Optional[str] = Query(
        None, description="특정 action 만 필터 (ACCEPT/REJECT/EDIT_REPORT 등)"
    ),
    db: Session = Depends(get_db),
) -> dict:
    """케이스의 수사관 조작 이력을 최신순으로 반환한다.

    설계서 4.3절 시퀀스 + CLAUDE.md "단일 수사관 정책" — actor 는 'investigator' 고정.
    """
    # 케이스 존재 검증
    if db.get(IncidentCaseModel, caseId) is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "케이스를 찾을 수 없습니다", "code": "CASE_NOT_FOUND"},
        )

    query = (
        db.query(ActionLogModel)
        .filter(ActionLogModel.case_id == caseId)
        .order_by(ActionLogModel.logged_at.desc())
    )
    if action:
        query = query.filter(ActionLogModel.action == action)

    total = query.count()
    items = query.offset(offset).limit(limit).all()

    return {
        "status": "ok",
        "data": [_serialize_action(a) for a in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
