"""Layer 0 — Triage API 라우터 (dev3 B-1, 2026-05-18).

V-1 Step 2 Discovery Loop 의 백엔드 진입점.

엔드포인트:
  POST /api/triage/start    초기 트리 시작 (root 노드 + 초기 점수)
  POST /api/triage/next     사용자 답변 → 다음 노드 + 점수 갱신
  POST /api/triage/analyze  단서·부분 로그 → 가설 점수 보강
  POST /api/triage/confirm  사고유형 확정 → incident_cases.incident_type 업데이트

설계 원칙:
  - 트리아주 진행 상태는 클라이언트가 sessionStorage 에 영속화 (CLAUDE.md
    단일 수사관 정책 + 청사진 §5 클라이언트 stateless 흐름)
  - 서버는 매 요청 (current_node_id + answer_ids + current_scores) 를 받아
    누적 계산하여 새 (next_node + new_scores) 반환
  - DB 확장(B-3 title·tlp·triage_state JSON 칼럼)은 별도 작업으로 분리
"""
import json
from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.analysis.attack_mapper import AttackMapper, get_rule_technique_name
from core.analysis.ocsf_normalizer import OCSFNormalizer
from core.ingestion.log_ingestor import LogIngestor
from core.intake.incident_case import IncidentCase
from core.intake.triage import Triage
from db.models import (
    AttackEventModel,
    IncidentCaseModel,
    OCSFEventModel,
    RawEventModel,
)
from db.session import get_db

router = APIRouter(prefix="/api/triage", tags=["intake"])


# ── 공통 에러 ────────────────────────────────────────────


def _case_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "status": "error",
            "message": "케이스를 찾을 수 없습니다",
            "code": "CASE_NOT_FOUND",
        },
    )


# ── 요청/응답 스키마 ─────────────────────────────────────


IncidentType = Literal[
    "CREDENTIAL_THEFT",
    "PRIVILEGE_ESCALATION",
    "DATA_EXFILTRATION",
    "AUDIT_LOG_TAMPERING",
    "MULTI_CSP_LATERAL",
    "UNCLASSIFIED",
]

ClueType = Literal[
    "IP_ADDRESS",
    "ACCOUNT",
    "HASH",
    "DOMAIN",
    "TIME_WINDOW",
    "SERVICE",
]


class ObservableModel(BaseModel):
    """단서(Observable) — V-1 Step 2 ① 단서 입력 결과."""

    type: ClueType
    value: str
    note: Optional[str] = None
    weight_key: Optional[str] = None  # 직접 지정 시 weights.clue_types 에서 조회
    added_at: Optional[str] = None


class TriageStartRequest(BaseModel):
    caseId: str


class TriageNextRequest(BaseModel):
    caseId: str
    current_node_id: str
    answer_ids: list[str]
    # 클라이언트가 들고 있는 누적 점수 — stateless 정책
    hypothesis_scores: dict[str, int]
    tree_path: list[dict]


class TriageAnalyzeRequest(BaseModel):
    caseId: str
    hypothesis_scores: dict[str, int]
    clue: Optional[ObservableModel] = None
    technique_ids: Optional[list[str]] = None


class TriageConfirmRequest(BaseModel):
    caseId: str
    incident_type: IncidentType
    hypothesis_scores: dict[str, int]
    secondary_incident_types: Optional[list[IncidentType]] = None


# ── 라우터 ───────────────────────────────────────────────


def _ensure_case(db: Session, case_id: str) -> IncidentCaseModel:
    case = IncidentCase.get_by_id(db, case_id)
    if case is None:
        raise _case_not_found()
    return case


@router.post("/start")
async def post_start(req: TriageStartRequest, db: Session = Depends(get_db)) -> dict:
    """트리아주 시작 — root 노드 반환.

    클라이언트가 신규 케이스 진입 시 1회 호출. 응답의 next_node 를 화면에 표시.
    """
    _ensure_case(db, req.caseId)
    data = Triage.start()
    return {"status": "ok", "data": {"caseId": req.caseId, **data}}


@router.post("/next")
async def post_next(req: TriageNextRequest, db: Session = Depends(get_db)) -> dict:
    """사용자 답변 → 다음 노드 + 점수 갱신.

    `current_node_id` 의 옵션 중 `answer_ids` 선택 시 weights.decision_tree_answers
    에서 가중치를 누적한 새 점수와 next_node 를 반환. T_evaluate 노드 도달 시
    recommendation 필드에 평가 결과 포함.
    """
    _ensure_case(db, req.caseId)
    data = Triage.next_question(
        current_node_id=req.current_node_id,
        answer_ids=req.answer_ids,
        current_scores=req.hypothesis_scores,
        current_path=req.tree_path,
    )
    return {"status": "ok", "data": {"caseId": req.caseId, **data}}


@router.post("/analyze")
async def post_analyze(req: TriageAnalyzeRequest, db: Session = Depends(get_db)) -> dict:
    """단서·부분 로그 분석 결과를 가설 점수에 보강.

    - clue        : weights.clue_types 에서 weight_key 로 조회
    - technique_ids : weights.partial_analysis_techniques 에서 다중 누적
    - 두 필드 모두 없으면 점수 변화 없이 그대로 반환

    ※ 멀티파트 파일 업로드는 차후 작업 (B-2 확장) — 현재는 클라이언트가 OCSF 정규화
       결과를 알아서 매핑한 뒤 technique_ids 만 전달 (mock 흐름) 하거나, Layer 2
       /api/analysis/map 호출 후 응답의 technique_id 를 그대로 본 라우터에 전달.
    """
    _ensure_case(db, req.caseId)
    clue_dict = req.clue.model_dump() if req.clue else None
    data = Triage.analyze(
        current_scores=req.hypothesis_scores,
        clue=clue_dict,
        technique_ids=req.technique_ids,
    )
    return {"status": "ok", "data": {"caseId": req.caseId, **data}}


@router.post("/confirm")
async def post_confirm(req: TriageConfirmRequest, db: Session = Depends(get_db)) -> dict:
    """확정 사고유형을 incident_cases.incident_type 에 반영.

    UNCLASSIFIED 도 유효 — 사용자가 '건너뛰기' 선택 시 그대로 저장.
    secondary_incident_types 는 B-3 (DB 칼럼 추가) 전까지 응답에 echo 만 함.
    """
    case = _ensure_case(db, req.caseId)
    prev_type = case.incident_type
    case.incident_type = req.incident_type
    db.commit()
    db.refresh(case)
    return {
        "status": "ok",
        "data": {
            "caseId": req.caseId,
            "incident_type": case.incident_type,
            "previous_incident_type": prev_type,
            "hypothesis_scores": req.hypothesis_scores,
            "secondary_incident_types": req.secondary_incident_types or [],
            "_note": (
                "secondary_incident_types · triage_state 영속화는 B-3 DB 칼럼 추가 후 활성. "
                "현재는 incident_type 만 갱신."
            ),
        },
    }


# ── B-2: 부분 로그 멀티파트 업로드 (2026-05-18) ────────────────


def _parse_clue_time(raw: Optional[str]) -> Optional[datetime]:
    """ISO8601 / 공백 분리 / 'Z' suffix 모두 수용. 실패 시 None."""
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    # tz-aware → naive UTC 로 통일 (OCSF time 컬럼이 naive)
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz=None).replace(tzinfo=None)
    return dt


def _serialize_mapped_event(attack: AttackEventModel, ocsf: OCSFEventModel) -> dict:
    """analyze-logs 응답용 매핑 이벤트 직렬화."""
    technique_name = get_rule_technique_name(attack.rule_id)
    return {
        "attack_id": attack.attack_id,
        "ocsf_id": ocsf.ocsf_id,
        "technique_id": attack.technique_id,
        "technique_name": technique_name,
        "tactic": attack.tactic,
        "rule_id": attack.rule_id,
        "time": ocsf.time.isoformat() if ocsf.time else None,
        "actor_user_name": ocsf.actor_user_name,
        "src_endpoint_ip": ocsf.src_endpoint_ip,
        "activity_name": ocsf.activity_name,
    }


@router.post("/analyze-logs")
async def post_analyze_logs(
    caseId: str = Form(...),
    hypothesis_scores: str = Form(..., description="현재 누적 점수 JSON 문자열"),
    clue_time: Optional[str] = Form(
        None, description="단서 시각 ISO8601 — ±window_minutes 범위 이벤트만 점수에 반영"
    ),
    window_minutes: int = Form(5, ge=0, le=1440),
    file: UploadFile = File(..., description="NCP Activity Tracer / NHN CloudTrail JSON 로그"),
    db: Session = Depends(get_db),
) -> dict:
    """부분 로그 파일 분석 → 가설 점수 보강.

    Flow:
      1. 파일 수신 + LogIngestor.ingest (raw_events 저장)
      2. OCSFNormalizer.normalize_case (ocsf_events 저장)
      3. AttackMapper.map_case (attack_events 저장)
      4. clue_time ±window_minutes 윈도우로 attack_events 필터
      5. technique_ids → Triage.analyze 로 점수 누적
      6. 매핑된 이벤트 목록 + 갱신 점수 반환

    참고: 윈도우 밖의 이벤트도 DB 에는 저장됨 (다른 분석에서 활용 가능).
    triage 점수에만 윈도우 적용.
    """
    case = _ensure_case(db, caseId)

    try:
        scores: dict[str, int] = json.loads(hypothesis_scores)
        if not isinstance(scores, dict):
            raise ValueError("hypothesis_scores must be JSON object")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": f"hypothesis_scores 파싱 실패: {e}",
                "code": "INVALID_SCORES",
            },
        )

    content = await file.read()
    clue_dt = _parse_clue_time(clue_time)

    # 1) ingest
    try:
        ingest_stats = LogIngestor.ingest(db, case, file.filename, content)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": str(e),
                "code": "INGEST_FAILED",
            },
        )

    # 2) normalize + 3) map (해당 케이스 전체 — 새로 추가된 raw 만 처리됨, 기존은 skip)
    norm_stats = OCSFNormalizer.normalize_case(db, case.case_id)
    map_stats = AttackMapper.map_case(db, case.case_id)

    # 4) attack_events 윈도우 필터 — sha256 으로 이번 업로드 분만 식별
    stmt = (
        select(AttackEventModel, OCSFEventModel)
        .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
        .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
        .where(RawEventModel.case_id == case.case_id)
        .where(RawEventModel.sha256 == ingest_stats.sha256)
    )
    rows: list[tuple[AttackEventModel, OCSFEventModel]] = list(db.execute(stmt).all())

    if clue_dt is not None:
        window = timedelta(minutes=window_minutes)
        in_window = [
            (a, o) for (a, o) in rows
            if o.time is not None and abs(o.time - clue_dt) <= window
        ]
    else:
        in_window = rows

    technique_ids: list[str] = [a.technique_id for (a, _o) in in_window]

    # 5) 점수 누적
    analyze_out = Triage.analyze(
        current_scores=scores,
        clue=None,
        technique_ids=technique_ids,
    )

    return {
        "status": "ok",
        "data": {
            "caseId": caseId,
            "used_csp": case.csp,
            "clue_time": clue_dt.isoformat() if clue_dt else None,
            "window_minutes": window_minutes,
            "hypothesis_scores": analyze_out["hypothesis_scores"],
            "mapped_techniques": technique_ids,
            "mapped_events": [_serialize_mapped_event(a, o) for (a, o) in in_window],
            "events_outside_window": max(0, len(rows) - len(in_window)),
            "ingestion": ingest_stats.to_dict(),
            "normalization": norm_stats,
            "mapping": map_stats,
            "next_clues": [],
        },
    }


# ── 결정 트리 시각화 (2026-05-18) ─────────────────────────────


@router.get("/tree")
async def get_tree(
    caseId: str,
    current_node_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    """결정 트리 시각화 응답 — 노드·엣지 + 루트·현재 노드.

    프론트 V-1 Step 2 ② 트리 시각화·미니맵 영역에서 사용.
    `current_node_id` 가 주어지면 응답에 echo (하이라이트용).
    """
    _ensure_case(db, caseId)
    return {
        "status": "ok",
        "data": Triage.tree_visualization(current_node_id=current_node_id),
    }
