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
    # 브라우저는 호스트명을 입력값 그대로 보내므로 localhost / 127.0.0.1 모두 등록 (preflight 400 방지)
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",  # Vite 기본 포트
        "http://localhost:5174",  # Vite 충돌 시 자동 fallback
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ]

    # ── Ollama (sLLM) ──
    # 기본 모델: llama3.1:8b — 시연 표준 (8GB+ RAM 에서 동작, 한국어 양호).
    #   GPU 가속 환경이면 .env 에서 gpt-oss:20b 로 올려 사용 가능 (추론 품질 ↑).
    #   ⚠ default 를 20b 로 두면 .env 누락/시스템 env override 시 미설치 모델로
    #     fail → 셰르파 무응답. 안전하게 설치 보장 모델(8b)을 default 로. (2026-05-28)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3.1:8b")
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

    # ── Triage 분류 모드 (Phase 2.5~H.4 실험, 2026-05-25) ──
    # "additive"       (기본) — 누적 합산: 절대 점수 0~180, 임계값 90/130/gap30
    # "bayesian"               — 베이즈 갱신: 확률 0~1, 임계값 0.65/0.60/0.30/gap0.20
    #                            Uniform prior (Jaynes 1968) + Laplace smoothing likelihood
    # "evidence_tree"          — Phase E (2026-05-25): 단서 기반 동적 트리.
    #                            docs/evidence_tree_paradigm.md 패러다임.
    #                            프론트가 /api/clue-tree/* 엔드포인트로 분기. legacy
    #                            /api/triage/* 는 호환 응답만 (scoring_mode 만 전파).
    # "bayes_net"              — Phase H.3+H.4 (2026-05-25): Bayesian Network DAG +
    #                            Noisy-OR 추론. PDF §17.B BAN paper IEEE 2023 정합.
    #                            3-layer H → T → C, clue_to_attack 매핑 + Hybrid Fallback.
    #                            /api/clue-tree/* 흐름 그대로 쓰되, likelihood 계산만
    #                            bayes_net.clue_likelihood_via_bn 으로 교체.
    #                            e2e 47/47 (INSIDER T3 약한 시그널 정합 향상).
    # 모든 모드 결정성 100% (같은 입력 → 같은 출력). 환경변수로 안전 토글.
    TRIAGE_MODE: str = os.getenv("TRIAGE_MODE", "additive")

    # ── Phase N.2 (2026-05-26 byungwoo) — Robust Bayes ε-contamination ──
    # bayes_update 후처리로 모든 8 사고유형에 floor (ε/8 = 1%) 보장.
    # 학술: Berger 1985 *Robust Bayesian Analysis* — ε-contamination model.
    # 동기 (paradigm §21.1 ②): "복합 공격이 정상" — 단일 가설 99% 쏠림 차단.
    # 0.0 = 비활성 (legacy 동작), 0.08 = ε 권장 (1%/가설). 환경변수 토글 가능.
    ROBUST_FLOOR_EPSILON: float = float(os.getenv("ROBUST_FLOOR_EPSILON", "0.08"))

    # ── 페이지네이션 ──
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100


settings = Settings()

# 업로드·보고서·산출물 폴더 자동 생성
settings.UPLOAD_DIR.mkdir(exist_ok=True)
settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
settings.EXPORTS_DIR.mkdir(exist_ok=True)
