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
    # ── 5종 (dev3 이전 기존) ──
    "CREDENTIAL_THEFT",
    "PRIVILEGE_ESCALATION",
    "DATA_EXFILTRATION",
    "AUDIT_LOG_TAMPERING",
    "MULTI_CSP_LATERAL",
    # ── dev3 C-1 신규 4종 (2026-05-19) ──
    "RANSOMWARE",            # CSA #5 + Verizon DBIR 2024 24%
    "MISCONFIG_EXPOSURE",    # CSA #3 + DBIR 24% (빈도 1위)
    "PHISH_INITIAL_ACCESS",  # CSA #2 IAM + MITRE TA0001
    "INSIDER_THREAT",        # KISA §3.3 "불법적 자원 사용" 변형 + MITRE T1078
    # ── 미분류 (TheHive·IRIS·NIST 800-61r2 빈 케이스 시작) ──
    "UNCLASSIFIED",
]
CSP = Literal["naver", "nhn", "all"]
Severity = Literal["critical", "high", "medium", "low"]
TLP = Literal["RED", "AMBER", "GREEN", "WHITE"]  # dev3 — TheHive 5 정보 공유 등급


# ── 요청/응답 스키마 ──


class CreateCaseRequest(BaseModel):
    """POST /api/cases 요청 바디."""

    incident_type: IncidentType
    csp: CSP
    severity: Severity
    occurred_at: datetime
    system_config: Optional[dict] = None
    # ── dev3 B-3 (Step 1 케이스 메타) ──
    title: Optional[str] = Field(default=None, max_length=200)
    tlp: TLP = "AMBER"
    observables: Optional[list[dict]] = None  # [{type, value, weight_key?, note?, added_at?}]


class UpdateCaseRequest(BaseModel):
    """PATCH /api/cases/{case_id} 요청 바디 (부분 갱신).

    dev3: incident_type / title / tlp / observables / secondary_incident_types /
    triage_state 도 부분 갱신 가능. V-8 사후 검증에서 부 사고유형 추가 등에 사용.
    """

    severity: Optional[Severity] = None
    system_config: Optional[dict] = None
    # ── dev3 B-3 ──
    incident_type: Optional[IncidentType] = None
    title: Optional[str] = Field(default=None, max_length=200)
    tlp: Optional[TLP] = None
    observables: Optional[list[dict]] = None
    secondary_incident_types: Optional[list[IncidentType]] = None
    triage_state: Optional[dict] = None


# ── 직렬화 헬퍼 ──


def _serialize_case(case: IncidentCaseModel) -> dict:
    """IncidentCaseModel → API 응답 dict (계약서 형식).

    dev3 B-3: title·tlp·observables·secondary_incident_types·triage_state 5종 추가.
    구버전 row (마이그레이션 직후) 호환 — 기본값으로 fallback.
    """
    return {
        "caseId": case.case_id,
        "incident_type": case.incident_type,
        "csp": case.csp,
        "severity": case.severity,
        "occurred_at": case.occurred_at.isoformat() if case.occurred_at else None,
        "system_config": case.system_config,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "closed_at": case.closed_at.isoformat() if case.closed_at else None,
        # ── dev3 B-3 ──
        "title": case.title,
        "tlp": case.tlp or "AMBER",
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

    dev3: V-1 Step 1 케이스 메타 (title·tlp·observables) 수용. UNCLASSIFIED 도 허용.
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
    """case의 메타·시스템 구성·트리아주 상태를 부분 갱신한다.

    dev3: incident_type 변경 (V-8 사후 검증 후) + observables / secondary_incident_types /
    triage_state 영속화 지원.
    """
    case = IncidentCase.update_config(
        db,
        case_id=case_id,
        severity=req.severity,
        system_config=req.system_config,
        title=req.title,
        tlp=req.tlp,
        observables=req.observables,
        secondary_incident_types=req.secondary_incident_types,
        triage_state=req.triage_state,
        incident_type=req.incident_type,
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
