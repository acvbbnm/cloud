"""AI Sherpa — FastAPI 엔트리포인트

라우터 등록만 수행하며, 비즈니스 로직은 core/ 패키지에 위치한다.
"""
import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings

# ── 라우터 import ──
from api.intake import router as intake_router
from api.ingestion import router as ingestion_router
from api.analysis import router as analysis_router
from api.sherpa import router as sherpa_router
from api.board import router as board_router
from api.report import router as report_router
from api.common import router as common_router
from api.triage import router as triage_router  # dev3 B-1
from api.clue_tree import router as clue_tree_router  # Phase B (Evidence Tree, 2026-05-25)

app = FastAPI(
    title="AI Sherpa",
    description="국내 멀티 클라우드 침해사고 분석 시스템",
    version="0.1.0",
)

# ── CORS (프론트엔드 개발 서버 허용) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 라우터 등록 ──
app.include_router(intake_router)
app.include_router(ingestion_router)
app.include_router(analysis_router)
app.include_router(sherpa_router)
app.include_router(board_router)
app.include_router(report_router)
app.include_router(common_router)
app.include_router(triage_router)  # dev3 B-1
app.include_router(clue_tree_router)  # Phase B Evidence Tree


@app.on_event("startup")
def on_startup() -> None:
    """서버 시작 시 DB 테이블 생성 + 시드 데이터 로딩."""
    from db.init_db import init
    init()


@app.get("/api/health", tags=["common"])
async def health_check(deep: bool = False) -> dict:
    """서버 상태 health check — 기본은 가벼운 핑, deep=true 일 때만 실측.

    2026-05-25 머지 검증 후속: 진규의 LLM/ChromaDB 실측 health 가 SentenceTransformer
    모델 로드를 trigger 해서 첫 호출 2분+ hang. 시연·CI 가용성 확보를 위해 가벼운
    기본 응답 + deep=true 옵션으로 분리.

    /api/health           → 즉시 ok (server/db 만)
    /api/health?deep=true → ollama/chromadb 실측 (느림, 시연 사전 점검용)
    """
    response: dict = {
        "status": "ok",
        "data": {
            "server": "running",
            "db": "connected",
            "version": settings.VERSION,
        },
    }
    if not deep:
        return response

    # ollama 실측 — LLMEngine.health() 가 /api/tags 호출 후 모델 존재까지 검증
    try:
        from core.sherpa.llm_engine import LLMEngine
        engine = LLMEngine.health()
        response["data"]["ollama"] = engine.get("engine", "unknown")
        response["data"]["ollama_detail"] = {
            "connected": engine.get("connected", False),
            "model": engine.get("model"),
            "available_models": engine.get("available_models", []),
        }
    except Exception as e:
        response["data"]["ollama"] = "error"
        response["data"]["ollama_detail"] = {"error": str(e)}

    # chromadb 실측 — RAGRetriever.backend_info() 가 'chromadb' | 'keyword' 분기
    try:
        from core.sherpa.rag_retriever import RAGRetriever
        rag = RAGRetriever.backend_info()
        response["data"]["chromadb"] = rag.get("backend", "unknown")
        response["data"]["chromadb_detail"] = {k: v for k, v in rag.items() if k != "backend"}
    except Exception as e:
        response["data"]["chromadb"] = "error"
        response["data"]["chromadb_detail"] = {"error": str(e)}

    return response


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

