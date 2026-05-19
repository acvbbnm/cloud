"""Layer 0 — Intake API 라우터.

설계서 5.6.1절 + API_계약서 Layer 0 섹션.
- POST   /api/cases
- GET    /api/cases/{case_id}
- PATCH  /api/cases/{case_id}
- GET    /api/guide/v2?caseId=    (v1 폐기 — dev2 채택 결정 2026-05-18)
"""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.intake.collection_guide_v2 import CollectionGuideV2
from core.intake.incident_case import IncidentCase
from db.models import IncidentCaseModel
from db.session import get_db

router = APIRouter(prefix="/api", tags=["intake"])


IncidentType = Literal[
    "CREDENTIAL_THEFT",
    "PRIVILEGE_ESCALATION",
    "DATA_EXFILTRATION",
    "AUDIT_LOG_TAMPERING",
    "MULTI_CSP_LATERAL",
    "UNCLASSIFIED",  # dev3: V-1 Step 1 빈 케이스 기본값 (Step 2 Discovery 에서 확정)
]
CSP = Literal["naver", "nhn", "all"]
Severity = Literal["critical", "high", "medium", "low"]
# dev3 §5.1 — TLP 분류 (Traffic Light Protocol, FIRST.org 표준)
TLP = Literal["RED", "AMBER", "GREEN", "WHITE"]


# ── 요청/응답 스키마 ──


class CreateCaseRequest(BaseModel):
    """POST /api/cases 요청 바디.

    dev3 (2026-05-19): title·tlp·observables 신규 필드. Step 2 Discovery 진입 전
    Step 1 Case Metadata 에서 사용자가 입력.
    """

    incident_type: IncidentType
    csp: CSP
    severity: Severity
    occurred_at: datetime
    system_config: Optional[dict] = None
    # ── dev3 신규 ──
    title: Optional[str] = Field(
        default=None,
        max_length=200,
        description="사용자 입력 사고 제목 (Step 1)",
    )
    tlp: Optional[TLP] = Field(
        default="AMBER",
        description="TLP 분류 — 기본 AMBER",
    )
    observables: Optional[list[dict]] = Field(
        default=None,
        description="Step 2 Discovery 단서 배열",
    )


class UpdateCaseRequest(BaseModel):
    """PATCH /api/cases/{case_id} 요청 바디 (부분 갱신).

    dev3: incident_type·observables·secondary_incident_types·triage_state·tlp·title 갱신 가능.
    Step 2 Discovery 종료 후 트리 평가 결과를 PATCH 로 확정한다.
    """

    severity: Optional[Severity] = None
    system_config: Optional[dict] = None
    # ── dev3 신규 ──
    incident_type: Optional[IncidentType] = None
    title: Optional[str] = Field(default=None, max_length=200)
    tlp: Optional[TLP] = None
    observables: Optional[list[dict]] = None
    secondary_incident_types: Optional[list[str]] = None
    triage_state: Optional[dict] = None


# ── 직렬화 헬퍼 ──


def _serialize_case(case: IncidentCaseModel) -> dict:
    """IncidentCaseModel → API 응답 dict (계약서 형식 + dev3 §5.2 신규 필드)."""
    return {
        "caseId": case.case_id,
        "incident_type": case.incident_type,
        "csp": case.csp,
        "severity": case.severity,
        "occurred_at": case.occurred_at.isoformat() if case.occurred_at else None,
        "system_config": case.system_config,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "closed_at": case.closed_at.isoformat() if case.closed_at else None,
        # ── dev3 신규 ──
        "title": case.title,
        "tlp": case.tlp,
        "observables": case.observables or [],
        "secondary_incident_types": case.secondary_incident_types,
        "triage_state": case.triage_state,
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


# ── 엔드포인트 ──


@router.post("/cases", status_code=status.HTTP_201_CREATED)
async def create_case(req: CreateCaseRequest, db: Session = Depends(get_db)) -> dict:
    """사고 케이스를 신규 생성한다.

    dev3: title·tlp·observables 신규 필드 전달. UNCLASSIFIED 도 허용
    (Step 2 Discovery 결과를 PATCH 로 확정하는 흐름).
    """
    case = IncidentCase.create(
        db,
        incident_type=req.incident_type,
        csp=req.csp,
        severity=req.severity,
        occurred_at=req.occurred_at,
        system_config=req.system_config,
        title=req.title,
        tlp=req.tlp,
        observables=req.observables,
    )
    return {"status": "ok", "data": _serialize_case(case)}


@router.get("/cases/{case_id}")
async def get_case(case_id: str, db: Session = Depends(get_db)) -> dict:
    """case_id로 케이스 상세를 조회한다."""
    case = IncidentCase.get_by_id(db, case_id)
    if case is None:
        raise _case_not_found()
    return {"status": "ok", "data": _serialize_case(case)}


@router.patch("/cases/{case_id}")
async def update_case(
    case_id: str, req: UpdateCaseRequest, db: Session = Depends(get_db)
) -> dict:
    """case를 부분 갱신한다.

    dev3: incident_type / observables / secondary_incident_types / triage_state /
          tlp / title 갱신 가능. Step 2 Discovery 종료 후 트리 평가 결과 확정에 사용.
    """
    case = IncidentCase.update_config(
        db,
        case_id=case_id,
        severity=req.severity,
        system_config=req.system_config,
        incident_type=req.incident_type,
        title=req.title,
        tlp=req.tlp,
        observables=req.observables,
        secondary_incident_types=req.secondary_incident_types,
        triage_state=req.triage_state,
    )
    if case is None:
        raise _case_not_found()
    return {"status": "ok", "data": _serialize_case(case)}


@router.get("/guide/v2")
async def get_guide_v2(
    caseId: str = Query(..., description="케이스 UUID"),
    db: Session = Depends(get_db),
) -> dict:
    """수집 체크리스트 — 외부 표준 6종 기반 Kill Chain 매트릭스 (dev2 채택, 2026-05-18).

    사고유형 → MITRE Kill Chain 단계 매핑 → Google Cloud 1.x 카테고리 시드 매칭 →
    `system_config` 환경 보정 적용 → NIST/KISA 휘발성 우선순위 정렬 → phase 별 그룹화.

    응답 형식:
      { caseId, completionRate, phases: {[phase]: {targets, ...}},
        applied_modifiers, environment_warnings, source_standards, version: "v2" }

    v1 `/api/guide` 는 2026-05-18 회의 결정에 따라 폐기됨.
    """
    guide = CollectionGuideV2.generate(db, caseId)
    if guide is None:
        raise _case_not_found()
    return {"status": "ok", "data": guide}
