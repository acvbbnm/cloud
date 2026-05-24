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


@app.on_event("startup")
def on_startup() -> None:
    """서버 시작 시 DB 테이블 생성 + 시드 데이터 로딩."""
    from db.init_db import init
    init()


@app.get("/api/health", tags=["common"])
async def health_check() -> dict:
    """서버 상태 + 외부 의존성(ollama·chromadb) 실측 health.

    2026-05-24 walkthrough 보강: 기존엔 ollama/chromadb 가 항상 "unknown" 반환되어
    시연 사전 헬스 체크 의미가 없었음. LLMEngine.health() / RAGRetriever.backend_info()
    실호출로 교체. 의존성 import 는 함수 내 lazy 로 진행 (CI 경량 의존성 셋업 호환).
    """
    # ollama 실측 — LLMEngine.health() 가 /api/tags 호출 후 모델 존재까지 검증
    try:
        from core.sherpa.llm_engine import LLMEngine
        engine = LLMEngine.health()
        ollama_status = engine.get("engine", "unknown")  # 'ollama' | 'ollama-no-model' | 'stub'
        ollama_detail = {
            "connected": engine.get("connected", False),
            "model": engine.get("model"),
            "available_models": engine.get("available_models", []),
        }
    except Exception as e:
        ollama_status = "error"
        ollama_detail = {"error": str(e)}

    # chromadb 실측 — RAGRetriever.backend_info() 가 'chromadb' | 'keyword' 분기
    try:
        from core.sherpa.rag_retriever import RAGRetriever
        rag = RAGRetriever.backend_info()
        chromadb_status = rag.get("backend", "unknown")  # 'chromadb' | 'keyword'
        chromadb_detail = {k: v for k, v in rag.items() if k != "backend"}
    except Exception as e:
        chromadb_status = "error"
        chromadb_detail = {"error": str(e)}

    return {
        "status": "ok",
        "data": {
            "server": "running",
            "db": "connected",
            "ollama": ollama_status,
            "ollama_detail": ollama_detail,
            "chromadb": chromadb_status,
            "chromadb_detail": chromadb_detail,
            "version": settings.VERSION,
        },
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

