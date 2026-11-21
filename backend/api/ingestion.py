"""Layer 1 — Ingestion API 라우터.

설계서 5.6.2절 + API_계약서 Layer 1 섹션.
- POST /api/logs/upload   — multipart 파일 업로드 + 해시 + 파싱 + 매칭
- GET  /api/logs          — 이벤트 목록 (페이지네이션, query: caseId, page, pageSize)
- GET  /api/logs/{eventId} — 원본 이벤트 JSON 조회
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from core.ingestion.log_ingestor import LogIngestor
from core.intake.incident_case import IncidentCase
from db.models import RawEventModel
from db.session import get_db

router = APIRouter(prefix="/api/logs", tags=["ingestion"])


# ── 직렬화 헬퍼 ────────────────────────────────────────────


def _serialize_event(ev: RawEventModel, include_raw: bool = False) -> dict:
    """RawEventModel → API 응답 dict.

    V-2 COLLECT 테이블 표시용으로 raw_json 에서 eventTime/eventName/sourceIp/user 를
    CSP 포맷별로 추출해 함께 반환한다 (목록·단건 공통).
    """
    raw_obj: Optional[dict] = None
    if ev.raw_json:
        try:
            parsed = json.loads(ev.raw_json)
            if isinstance(parsed, dict):
                raw_obj = parsed
        except json.JSONDecodeError:
            raw_obj = None

    display = LogIngestor.extract_display_fields(ev.csp, raw_obj)

    data = {
        "eventId": ev.event_id,
        "caseId": ev.case_id,
        "csp": ev.csp,
        "sha256": ev.sha256,
        "matchedTargetId": ev.matched_target_id,
        "ingestedAt": ev.ingested_at.isoformat() if ev.ingested_at else None,
        "sourceFile": ev.source_file,
        # 표시용 추출 필드 (Timestamp / Event Name / Source IP / User)
        "eventTime": display["time"],
        "eventName": display["event_name"],
        "sourceIp": display["source_ip"],
        "user": display["user"],
    }
    if include_raw:
        if raw_obj is not None:
            data["raw"] = raw_obj
        else:
            data["raw"] = ev.raw_json
    return data


def _case_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "status": "error",
            "message": "케이스를 찾을 수 없습니다",
            "code": "CASE_NOT_FOUND",
        },
    )


def _event_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "status": "error",
            "message": "이벤트를 찾을 수 없습니다",
            "code": "EVENT_NOT_FOUND",
        },
    )


# ── 엔드포인트 ────────────────────────────────────────────


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_log(
    caseId: str = Form(..., description="대상 사고 케이스 UUID"),
    file: UploadFile = File(..., description="NCP/NHN 원본 로그 파일 (JSON)"),
    db: Session = Depends(get_db),
) -> dict:
    """원본 로그 파일을 업로드하여 raw_events 에 적재한다.

    - SHA-256 해시로 무결성 검증값 저장
    - case.csp 에 맞는 파서 자동 선택
    - collection_targets 카탈로그와 매칭하여 matched_target_id 채움
    """
    case = IncidentCase.get_by_id(db, caseId)
    if case is None:
        raise _case_not_found()

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "빈 파일입니다",
                "code": "EMPTY_FILE",
            },
        )

    try:
        stats = LogIngestor.ingest(
            db, case=case, filename=file.filename, content=content
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": str(e),
                "code": "PARSE_FAILED",
            },
        )

    # P0 (2026-05-24 walkthrough): UNCLASSIFIED 케이스는 collection_targets 카탈로그가
    # 비어있어 항상 matched=0 — silent failure 방지 위해 응답에 경고 필드 첨부.
    # 시연 대본 워크플로우(V-1 Step 3 결정트리 → incident_type 확정 → V-2 업로드) 우회 시
    # 수사관이 매칭 0건 사실을 놓치지 않도록 명시.
    data = stats.to_dict()
    warnings: list[dict] = []
    if case.incident_type == "UNCLASSIFIED":
        warnings.append({
            "code": "UNCLASSIFIED_CASE",
            "message": (
                "사고 유형이 UNCLASSIFIED 상태라 collection_targets 카탈로그가 비어있어 "
                "모든 이벤트가 미매칭 처리됩니다. V-1 Discovery Loop(결정 트리)에서 "
                "사고 유형을 확정한 뒤 다시 업로드하거나 PATCH /api/cases 로 incident_type 을 "
                "지정해 주세요."
            ),
        })
    if data.get("matched", 0) == 0 and data.get("totalEvents", 0) > 0 and not warnings:
        # incident_type 은 확정인데도 매칭 0 — 매처 룰 미보유 또는 로그 포맷 mismatch
        warnings.append({
            "code": "NO_MATCH",
            "message": (
                f"전체 {data['totalEvents']}건 모두 매처에 매칭되지 않았습니다. "
                f"사고 유형({case.incident_type}) × CSP({case.csp}) 의 collection_targets "
                "카탈로그 또는 로그 포맷을 확인해 주세요."
            ),
        })
    if warnings:
        data["warnings"] = warnings

    return {"status": "ok", "data": data}


@router.get("")
async def list_logs(
    caseId: str = Query(..., description="대상 사고 케이스 UUID"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    """case 의 raw_events 페이지네이션 조회."""
    if IncidentCase.get_by_id(db, caseId) is None:
        raise _case_not_found()

    rows, total = LogIngestor.list_events(
        db, case_id=caseId, page=page, page_size=pageSize
    )
    return {
        "status": "ok",
        "data": {
            "items": [_serialize_event(r) for r in rows],
            "total": total,
            "page": page,
            "pageSize": pageSize,
        },
    }


@router.get("/{event_id}")
async def get_log(event_id: str, db: Session = Depends(get_db)) -> dict:
    """단건 raw event 의 원본 JSON 까지 포함하여 반환."""
    ev = LogIngestor.get_event(db, event_id)
    if ev is None:
        raise _event_not_found()
    return {"status": "ok", "data": _serialize_event(ev, include_raw=True)}
