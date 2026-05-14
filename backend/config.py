"""환경 설정 — 모든 설정값은 여기서 관리한다.

하드코딩된 절대 경로 사용 금지. 필요한 경로는 이 파일에서 정의한다.
"""
import os
from pathlib import Path


class Settings:
    """앱 전역 설정."""

    # ── 기본 ──
    VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # ── 경로 ──
    BASE_DIR: Path = Path(__file__).resolve().parent
    DATA_DIR: Path = BASE_DIR / "data"
    MAPPING_RULES_DIR: Path = DATA_DIR / "mapping_rules"
    ATTACK_RULES_DIR: Path = DATA_DIR / "attack_rules"
    KB_DIR: Path = DATA_DIR / "kb"
    COLLECTION_TARGETS_DIR: Path = DATA_DIR / "collection_targets"
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    TEMPLATE_DIR: Path = BASE_DIR / "templates"

    # ── DB ──
    DB_URL: str = os.getenv("DB_URL", f"sqlite:///{BASE_DIR / 'ai_sherpa.db'}")

    # ── CORS ──
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",  # Vite 기본 포트
        "http://localhost:5174",  # Vite 충돌 시 자동 fallback
        "http://localhost:3000",
    ]

    # ── Ollama (sLLM) ──
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3.1:8b")
    LLM_TIMEOUT: int = 30  # 초 (SNF-02)

    # ── ChromaDB ──
    CHROMA_PERSIST_DIR: str = os.getenv(
        "CHROMA_PERSIST_DIR", str(BASE_DIR / "chroma_data")
    )

    # ── 페이지네이션 ──
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100


settings = Settings()

# 업로드 폴더 자동 생성
settings.UPLOAD_DIR.mkdir(exist_ok=True)
