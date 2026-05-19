"""Layer 3 — AI Sherpa API 라우터.

설계서 5.6.4절 + API_계약서 Layer 3 섹션.
- POST /api/sherpa/brief    — 컨텍스트 브리핑 (우선)
- POST /api/sherpa/chat     — 자연어 질의 (우선)
- POST /api/sherpa/suggest  — 빠진 고리 후보 (후순위)
- POST /api/sherpa/playbook — 플레이북 추천 (후순위)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.intake.incident_case import IncidentCase
from core.sherpa.ai_sherpa import AISherpa
from core.sherpa.incident_inference import infer_from_attacks
from core.sherpa.knowledge_base import stats as kb_stats
from core.sherpa.llm_engine import LLMEngine
from core.sherpa.rag_retriever import RAGRetriever
from db.session import get_db

router = APIRouter(prefix="/api/sherpa", tags=["sherpa"])


# ── 공통 에러 헬퍼 (intake/board/report.py 와 동일 패턴) ──


def _case_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "status": "error",
            "message": "케이스를 찾을 수 없습니다",
            "code": "CASE_NOT_FOUND",
        },
    )


# ── 요청 스키마 ────────────────────────────────────────────


class BriefRequest(BaseModel):
    caseId: str
    eventId: Optional[str] = None  # attack_id (선택)


class ChatHistoryItem(BaseModel):
    role: str  # 'user' / 'assistant'
    content: str


class ChatRequest(BaseModel):
    caseId: Optional[str] = None
    sessionId: Optional[str] = None
    query: str
    history: Optional[list[ChatHistoryItem]] = None


class SuggestRequest(BaseModel):
    caseId: str
    nodeA: str
    nodeB: str


class PlaybookRequest(BaseModel):
    caseId: Optional[str] = None
    chain: list[str]


class VerifyIncidentTypesRequest(BaseModel):
    """POST /api/sherpa/verify-incident-types — V-8 사후 검증.

    confirmed incident_type 과 Layer 2 매핑 결과를 비교해 추가 사고유형 제안.
    수사관이 결과를 받아 PATCH /api/cases (secondary_incident_types) 로 확정.
    """

    caseId: str


# ── 엔드포인트 ────────────────────────────────────────────


@router.post("/brief")
async def post_brief(req: BriefRequest, db: Session = Depends(get_db)) -> dict:
    """ATT&CK 컨텍스트 브리핑.

    eventId(attack_id) 미지정 시 case 내 최상위 위험도 attack 자동 선택.
    case 미존재 시 HTTP 404.
    """
    case = IncidentCase.get_by_id(db, req.caseId)
    if case is None:
        raise _case_not_found()
    data = AISherpa.brief(db, req.caseId, req.eventId)
    return {"status": "ok", "data": data}


@router.post("/chat")
async def post_chat(req: ChatRequest, db: Session = Depends(get_db)) -> dict:
    """자연어 질의 — RAG 검색 + 응답.

    sessionId 가 주어지면 서버 인메모리 세션을 이어 사용 (stateful).
    sessionId 가 없고 history 가 주어지면 stateless 클라이언트로 간주하여
    history 를 신규 세션에 미리 채우고 그 위에 query 를 더한다 (설계서 5.1절 정합).

    caseId 가 주어지면 존재 여부를 검증하고, 없으면 HTTP 404.
    """
    if req.caseId:
        case = IncidentCase.get_by_id(db, req.caseId)
        if case is None:
            raise _case_not_found()

    history = [h.model_dump() for h in (req.history or [])]
    data = AISherpa.chat(
        case_id=req.caseId,
        session_id=req.sessionId,
        query=req.query,
        history=history,
    )
    return {"status": "ok", "data": data}


@router.post("/chat/stream")
async def post_chat_stream(req: ChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """자연어 질의 스트리밍 (Phase 2.3, 2026-05-18).

    ndjson 응답 — 각 라인이 JSON object:
      {"type":"start","sessionId":"...","sources":[...]}    첫 라인
      {"type":"delta","content":"..."}                       토큰 0..N건
      {"type":"done"}                                        종료

    UX: 100초 대기 → 첫 토큰까지 ~5초 + 점진 표시. 사용자 체감 응답시간 1/3.
    인증·case 검증은 동기 chat 과 동일.
    """
    if req.caseId:
        case = IncidentCase.get_by_id(db, req.caseId)
        if case is None:
            raise _case_not_found()

    history = [h.model_dump() for h in (req.history or [])]
    gen = AISherpa.chat_stream(
        case_id=req.caseId,
        session_id=req.sessionId,
        query=req.query,
        history=history,
    )
    return StreamingResponse(
        gen,
        media_type="application/x-ndjson",
        # 프록시·브라우저 버퍼링 방지
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/suggest")
async def post_suggest(req: SuggestRequest, db: Session = Depends(get_db)) -> dict:
    """빠진 고리 후보 (후순위 깡통)."""
    case = IncidentCase.get_by_id(db, req.caseId)
    if case is None:
        raise _case_not_found()
    data = AISherpa.suggest_missing_link(db, req.caseId, req.nodeA, req.nodeB)
    return {"status": "ok", "data": data}


@router.post("/playbook")
async def post_playbook(req: PlaybookRequest, db: Session = Depends(get_db)) -> dict:
    """공격 체인에 대한 플레이북 추천 (후순위 깡통)."""
    if req.caseId:
        case = IncidentCase.get_by_id(db, req.caseId)
        if case is None:
            raise _case_not_found()
    data = AISherpa.recommend_playbook(req.chain)
    return {"status": "ok", "data": data}


@router.get("/kb")
async def get_kb_stats() -> dict:
    """KB 인덱스 통계 + LLM/RAG 엔진 상태 (V8 우측 패널)."""
    return {
        "status": "ok",
        "data": {
            **kb_stats(),
            "engine": LLMEngine.health(),
            "rag": RAGRetriever.backend_info(),
        },
    }


@router.post("/verify-incident-types")
async def post_verify_incident_types(
    req: VerifyIncidentTypesRequest, db: Session = Depends(get_db)
) -> dict:
    """V-8 사후 검증 — Layer 2 매핑 결과로 사고유형 보완 제안.

    동작:
      1. case 의 attack_events 전체 조회
      2. (technique_id, tactic) → incident_type 정적 매핑으로 점수 집계
      3. confirmed 와 다른 사고유형 중 임계값 통과한 것을 secondary 로 제안
      4. 대표 증거(samples)를 함께 반환

    결정성 100% — 같은 attack_events → 같은 결과 (AI 호출 없음, 정적 규칙).
    수사관이 결과를 보고 채택하려면 PATCH /api/cases (secondary_incident_types) 호출.

    case 미존재 시 HTTP 404.
    """
    case = IncidentCase.get_by_id(db, req.caseId)
    if case is None:
        raise _case_not_found()
    data = infer_from_attacks(db, req.caseId)
    return {"status": "ok", "data": data}
