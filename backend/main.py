"""AI Sherpa — FastAPI 엔트리포인트

라우터 등록만 수행하며, 비즈니스 로직은 core/ 패키지에 위치한다.
"""
import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings

# ── 라우터 import (구현 완료 시 주석 해제) ──
from api.intake import router as intake_router
from api.ingestion import router as ingestion_router
from api.analysis import router as analysis_router
# from api.sherpa import router as sherpa_router
# from api.board import router as board_router
# from api.report import router as report_router

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

# ── 라우터 등록 (구현 완료 시 주석 해제) ──
app.include_router(intake_router)
app.include_router(ingestion_router)
app.include_router(analysis_router)
# app.include_router(sherpa_router)
# app.include_router(board_router)
# app.include_router(report_router)


@app.get("/api/health", tags=["common"])
async def health_check() -> dict:
    """서버 상태 확인."""
    return {
        "status": "ok",
        "data": {
            "server": "running",
            "db": "connected",
            "ollama": "unknown",
            "chromadb": "unknown",
            "version": settings.VERSION,
        },
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
