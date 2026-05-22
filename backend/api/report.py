"""Layer 4 — Report API 라우터.

설계서 5.6.5절 + UC-08 + API_계약서 Layer 4 섹션.

- POST   /api/report                       — 보고서 초안 생성 (없으면 자동, 있으면 기존 반환)
- GET    /api/report/{case_id}             — 보고서 조회
- PATCH  /api/report/{case_id}             — 섹션 부분 갱신 + 상태 변경
- GET    /api/report/{case_id}/export?format=docx|pdf — 산출물 다운로드
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.board.report_generator import ReportGenerator
from core.intake.incident_case import IncidentCase
from db.models import ActionLogModel
from db.session import get_db

router = APIRouter(prefix="/api/report", tags=["report"])


ReportStatus = Literal["draft", "edited", "finalized"]


# ── 요청 스키마 ──────────────────────────────────────────


class CreateReportRequest(BaseModel):
    caseId: str
    regenerate: bool = False  # True 면 기존 보고서 덮어쓰고 재생성


class UpdateReportRequest(BaseModel):
    sections: Optional[dict] = None  # { "overview": "...", "comments": "..." }
    status: Optional[ReportStatus] = None


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


def _report_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "status": "error",
            "message": "보고서가 아직 생성되지 않았습니다",
            "code": "REPORT_NOT_FOUND",
        },
    )


# ── 엔드포인트 ────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_report(req: CreateReportRequest, db: Session = Depends(get_db)) -> dict:
    """보고서 초안 생성. regenerate=True 면 기존 보고서 무시하고 새로 만든다."""
    case = IncidentCase.get_by_id(db, req.caseId)
    if case is None:
        raise _case_not_found()

    if req.regenerate:
        report = ReportGenerator.generate_draft(db, req.caseId)
        if report is None:
            raise _case_not_found()
        ReportGenerator.save(req.caseId, report)
    else:
        report = ReportGenerator.get_or_create(db, req.caseId)
        if report is None:
            raise _case_not_found()

    return {"status": "ok", "data": report}


@router.get("/{case_id}")
async def get_report(case_id: str, db: Session = Depends(get_db)) -> dict:
    """저장된 보고서 조회. 없으면 404."""
    if IncidentCase.get_by_id(db, case_id) is None:
        raise _case_not_found()
    report = ReportGenerator.load(case_id)
    if report is None:
        raise _report_not_found()
    return {"status": "ok", "data": report}


@router.patch("/{case_id}")
async def update_report(
    case_id: str, req: UpdateReportRequest, db: Session = Depends(get_db)
) -> dict:
    """섹션 부분 갱신 + 상태 변경. status='finalized' 변경 시 action_logs 적재."""
    if IncidentCase.get_by_id(db, case_id) is None:
        raise _case_not_found()

    existing = ReportGenerator.load(case_id)
    if existing is None:
        raise _report_not_found()

    prev_status = existing.get("status")
    updated = ReportGenerator.update_sections(
        case_id,
        section_updates=req.sections or {},
        status=req.status,
    )
    if updated is None:
        raise _report_not_found()

    # 액션 로깅 — 섹션 편집 / 최종화
    if req.sections:
        db.add(
            ActionLogModel(
                case_id=case_id,
                actor="investigator",
                action="EDIT_REPORT",
                target_type="report",
                target_id=case_id,
                detail={"keys": list(req.sections.keys())},
            )
        )
    if req.status == "finalized" and prev_status != "finalized":
        db.add(
            ActionLogModel(
                case_id=case_id,
                actor="investigator",
                action="FINALIZE_REPORT",
                target_type="report",
                target_id=case_id,
                detail={"from": prev_status, "to": "finalized"},
            )
        )
    db.commit()

    return {"status": "ok", "data": updated}


@router.get("/{case_id}/export")
async def export_report(
    case_id: str,
    format: Literal["docx", "pdf"] = Query("docx"),
    db: Session = Depends(get_db),
) -> FileResponse:
    """보고서 산출물 다운로드. docx + pdf 양쪽 지원 (Phase 2.1 — 2026-05-18)."""
    if IncidentCase.get_by_id(db, case_id) is None:
        raise _case_not_found()

    report = ReportGenerator.load(case_id)
    if report is None:
        raise _report_not_found()

    if format == "pdf":
        out_path = ReportGenerator.render_pdf(report)
        media_type = "application/pdf"
        extension = "pdf"
    else:
        out_path = ReportGenerator.render_docx(report)
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        extension = "docx"

    # 액션 로깅 — 내보내기
    db.add(
        ActionLogModel(
            case_id=case_id,
            actor="investigator",
            action="EXPORT_REPORT",
            target_type="report",
            target_id=case_id,
            detail={"format": format},
        )
    )
    db.commit()

    return FileResponse(
        path=str(out_path),
        filename=f"incident_report_{case_id}.{extension}",
        media_type=media_type,
    )
