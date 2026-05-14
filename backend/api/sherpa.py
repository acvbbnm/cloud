"""Layer 3 — AI Sherpa API 라우터.

설계서 5.6.4절 + API_계약서 Layer 3 섹션.
- POST /api/sherpa/brief    — 컨텍스트 브리핑 (우선)
- POST /api/sherpa/chat     — 자연어 질의 (우선)
- POST /api/sherpa/suggest  — 빠진 고리 후보 (후순위)
- POST /api/sherpa/playbook — 플레이북 추천 (후순위)
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.intake.incident_case import IncidentCase
from core.sherpa.ai_sherpa import AISherpa
from core.sherpa.knowledge_base import stats as kb_stats
from core.sherpa.llm_engine import LLMEngine
from db.session import get_db

router = APIRouter(prefix="/api/sherpa", tags=["sherpa"])


# ── 요청 스키마 ────────────────────────────────────────────


class BriefRequest(BaseModel):
    caseId: str
    eventId: Optional[str] = None  # attack_id (선택)


class ChatHistoryItem(BaseModel):
    role: str
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


# ── 엔드포인트 ────────────────────────────────────────────


@router.post("/brief")
async def post_brief(req: BriefRequest, db: Session = Depends(get_db)) -> dict:
    """ATT&CK 컨텍스트 브리핑."""
    case = IncidentCase.get_by_id(db, req.caseId)
    if case is None:
        return {"status": "error", "message": "케이스를 찾을 수 없습니다", "code": "CASE_NOT_FOUND"}
    data = AISherpa.brief(db, req.caseId, req.eventId)
    return {"status": "ok", "data": data}


@router.post("/chat")
async def post_chat(req: ChatRequest) -> dict:
    """자연어 질의 — RAG 검색 + 응답."""
    history = [h.model_dump() for h in (req.history or [])]
    data = AISherpa.chat(req.caseId, req.sessionId, req.query, history)
    return {"status": "ok", "data": data}


@router.post("/suggest")
async def post_suggest(req: SuggestRequest, db: Session = Depends(get_db)) -> dict:
    """빠진 고리 후보 (후순위 깡통)."""
    data = AISherpa.suggest_missing_link(db, req.caseId, req.nodeA, req.nodeB)
    return {"status": "ok", "data": data}


@router.post("/playbook")
async def post_playbook(req: PlaybookRequest) -> dict:
    """공격 체인에 대한 플레이북 추천 (후순위 깡통)."""
    data = AISherpa.recommend_playbook(req.chain)
    return {"status": "ok", "data": data}


@router.get("/kb")
async def get_kb_stats() -> dict:
    """KB 인덱스 통계 (V8 화면 우측 패널)."""
    return {"status": "ok", "data": {**kb_stats(), "engine": LLMEngine.health()}}
