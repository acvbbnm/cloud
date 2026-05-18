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
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.intake.incident_case import IncidentCase
from core.intake.triage import Triage
from db.models import IncidentCaseModel
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
