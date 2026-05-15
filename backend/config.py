"""환경 설정 — 모든 설정값은 여기서 관리한다.

하드코딩된 절대 경로 사용 금지. 필요한 경로는 이 파일에서 정의한다.

.env 파일을 자동 로드 (python-dotenv). backend/.env 가 있으면 os.getenv 가 그 값을
우선 반영하므로 OLLAMA_BASE_URL / LLM_MODEL 등을 환경별로 오버라이드할 수 있다.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    # backend/.env 명시적으로 로드 (실행 디렉토리와 무관하게)
    _env_path = Path(__file__).resolve().parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:  # pragma: no cover
    # python-dotenv 미설치 시 시스템 환경변수만 사용 (graceful fallback)
    pass


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
    REPORTS_DIR: Path = DATA_DIR / "reports"  # JSON 영속화
    EXPORTS_DIR: Path = BASE_DIR / "exports"  # DOCX/PDF 산출물

    # ── DB ──
    DB_URL: str = os.getenv("DB_URL", f"sqlite:///{BASE_DIR / 'ai_sherpa.db'}")

    # ── CORS ──
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",  # Vite 기본 포트
        "http://localhost:5174",  # Vite 충돌 시 자동 fallback
        "http://localhost:3000",
    ]

    # ── Ollama (sLLM) ──
    # 기본 모델: gpt-oss:20b (OpenAI 오픈웨이트, 추론·한국어 모두 우수).
    # 시스템 RAM 16GB 미만이면 환경변수로 더 작은 모델 지정 권장 (예: llama3.1:8b).
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-oss:20b")
    # SNF-02 기본 30초. CPU 전용 / 8B+ 모델 환경에서는 .env 에서 늘려 사용 (예: 120).
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "30"))

    # ── ChromaDB (Layer 3 RAG) ──
    CHROMA_PERSIST_DIR: str = os.getenv(
        "CHROMA_PERSIST_DIR", str(BASE_DIR / "chroma_data")
    )
    CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "ai_sherpa_kb")

    # ── 임베딩 모델 ──
    # 다국어 지원 (한국어 KB 청크 검색). 첫 로드 시 약 120MB 다운로드.
    # 미설치 시 RAGRetriever 가 키워드 매칭 fallback 으로 자동 전환.
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
    )

    # ── 페이지네이션 ──
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100


settings = Settings()

# 업로드·보고서·산출물 폴더 자동 생성
settings.UPLOAD_DIR.mkdir(exist_ok=True)
settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
settings.EXPORTS_DIR.mkdir(exist_ok=True)
