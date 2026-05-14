"""Layer 2 — Analysis API 라우터.

설계서 5.6.3절 + API_계약서 Layer 2 섹션.
- POST /api/analysis/normalize  — OCSF 정규화
- GET  /api/analysis/ocsf       — OCSF 결과 조회 (페이지네이션)
- POST /api/analysis/map        — ATT&CK 매핑
- GET  /api/analysis/attack     — ATT&CK 결과 조회 (페이지네이션)
- POST /api/analysis/gap        — 갭 감지
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.analysis.attack_mapper import AttackMapper, get_rule_technique_name
from core.analysis.gap_detector import GapDetector
from core.analysis.ocsf_normalizer import OCSFNormalizer
from core.intake.incident_case import IncidentCase
from db.models import AttackEventModel, OCSFEventModel, RawEventModel
from db.session import get_db

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


# ── 요청 스키마 ────────────────────────────────────────────


class NormalizeRequest(BaseModel):
    caseId: str
    eventIds: Optional[list[str]] = None


class CaseIdRequest(BaseModel):
    caseId: str


# ── 직렬화 헬퍼 ────────────────────────────────────────────


def _serialize_ocsf(ev: OCSFEventModel) -> dict:
    return {
        "ocsf_id": ev.ocsf_id,
        "event_id": ev.event_id,
        "time": ev.time.isoformat() if ev.time else None,
        "actor_user_name": ev.actor_user_name,
        "src_endpoint_ip": ev.src_endpoint_ip,
        "activity_name": ev.activity_name,
        "status_code": ev.status_code,
        "unmapped_raw": ev.unmapped_raw,
    }


def _serialize_attack(ev: AttackEventModel, ocsf: Optional[OCSFEventModel] = None) -> dict:
    return {
        "attack_id": ev.attack_id,
        "ocsf_id": ev.ocsf_id,
        "technique_id": ev.technique_id,
        "technique_name": get_rule_technique_name(ev.rule_id),
        "tactic": ev.tactic,
        "rule_id": ev.rule_id,
        "risk_score": float(ev.risk_score) if ev.risk_score is not None else None,
        "mapped_at": ev.mapped_at.isoformat() if ev.mapped_at else None,
        "event_time": ocsf.time.isoformat() if ocsf and ocsf.time else None,
        "activity_name": ocsf.activity_name if ocsf else None,
    }


def _case_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "status": "error",
            "message": "케이스를 찾을 수 없습니다",
            "code": "CASE_NOT_FOUND",
        },
    )


# ── 엔드포인트 ────────────────────────────────────────────


@router.post("/normalize", status_code=status.HTTP_200_OK)
async def post_normalize(req: NormalizeRequest, db: Session = Depends(get_db)) -> dict:
    """raw_events → ocsf_events 정규화."""
    case = IncidentCase.get_by_id(db, req.caseId)
    if case is None:
        raise _case_not_found()
    stats = OCSFNormalizer.normalize_case(db, req.caseId, req.eventIds)
    return {"status": "ok", "data": stats}


@router.get("/ocsf")
async def get_ocsf(
    caseId: str = Query(...),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    eventId: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """OCSF 결과 조회 (페이지네이션). 특정 eventId 지정 가능."""
    case = IncidentCase.get_by_id(db, caseId)
    if case is None:
        raise _case_not_found()

    base = (
        select(OCSFEventModel)
        .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
        .where(RawEventModel.case_id == caseId)
    )
    if eventId:
        base = base.where(OCSFEventModel.event_id == eventId)

    # total
    total = db.execute(
        select(func.count())
        .select_from(OCSFEventModel)
        .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
        .where(RawEventModel.case_id == caseId)
        .where(*([OCSFEventModel.event_id == eventId] if eventId else []))
    ).scalar() or 0

    items = list(
        db.execute(
            base.order_by(OCSFEventModel.time)
            .offset((page - 1) * pageSize)
            .limit(pageSize)
        ).scalars()
    )

    return {
        "status": "ok",
        "data": {
            "items": [_serialize_ocsf(i) for i in items],
            "total": total,
            "page": page,
            "pageSize": pageSize,
        },
    }


@router.post("/map", status_code=status.HTTP_200_OK)
async def post_map(req: CaseIdRequest, db: Session = Depends(get_db)) -> dict:
    """OCSF events → ATT&CK 매핑."""
    case = IncidentCase.get_by_id(db, req.caseId)
    if case is None:
        raise _case_not_found()
    stats = AttackMapper.map_case(db, req.caseId)

    # 매핑 결과 일부 events 응답에 포함 (계약서)
    rows = list(
        db.execute(
            select(AttackEventModel, OCSFEventModel)
            .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
            .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
            .where(RawEventModel.case_id == req.caseId)
            .order_by(AttackEventModel.risk_score.desc())
            .limit(20)
        ).all()
    )
    stats["events"] = [_serialize_attack(att, ocsf) for att, ocsf in rows]
    return {"status": "ok", "data": stats}


@router.get("/attack")
async def get_attack(
    caseId: str = Query(...),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """ATT&CK 매핑 결과 조회 (페이지네이션)."""
    case = IncidentCase.get_by_id(db, caseId)
    if case is None:
        raise _case_not_found()

    total = db.execute(
        select(func.count())
        .select_from(AttackEventModel)
        .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
        .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
        .where(RawEventModel.case_id == caseId)
    ).scalar() or 0

    rows = list(
        db.execute(
            select(AttackEventModel, OCSFEventModel)
            .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
            .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
            .where(RawEventModel.case_id == caseId)
            .order_by(AttackEventModel.risk_score.desc(), AttackEventModel.mapped_at)
            .offset((page - 1) * pageSize)
            .limit(pageSize)
        ).all()
    )

    return {
        "status": "ok",
        "data": {
            "items": [_serialize_attack(att, ocsf) for att, ocsf in rows],
            "total": total,
            "page": page,
            "pageSize": pageSize,
        },
    }


@router.post("/gap", status_code=status.HTTP_200_OK)
async def post_gap(req: CaseIdRequest, db: Session = Depends(get_db)) -> dict:
    """케이스 갭 감지 + gap_results INSERT."""
    result = GapDetector.detect(db, req.caseId)
    if result is None:
        raise _case_not_found()
    return {"status": "ok", "data": result}
