"""Layer 3 — LLMEngine (Ollama 통합 버전).

설계서 5.4.5절 + 모듈별_구현_명세.md `LLMEngine` 항목.

흐름:
  AISherpa.chat() → LLMEngine.generate(query, context) → Ollama /api/chat → 응답 텍스트

핵심 원칙 (CLAUDE.md / 설계서 5.1절 정합):
  - AI 는 판단·결정하지 않는다. 검색·요약·제안만 수행.
  - 모든 응답은 한국어 + 출처 [N] 인용 + "최종 판단은 수사관" 문구 포함.
  - 30초 timeout (SNF-02) 시 정해진 fallback 메시지 반환.

설정 (config.py + .env):
  - OLLAMA_BASE_URL : 기본 http://localhost:11434
  - LLM_MODEL       : 기본 llama3.1:8b (gpt-oss:20b 등 교체 가능)
  - LLM_TIMEOUT     : 초 (SNF-02 = 30)
"""
import logging
from typing import Optional

import httpx

from config import settings
from core.sherpa.knowledge_base import KBChunk

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# System prompt — AI 셰르파 역할·규칙·출력형식
# ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """당신은 한국 멀티 클라우드(NCP/NHN) 침해사고 분석을 보조하는 AI 셰르파입니다.

[역할]
- 침해사고 대응 수사관에게 컨텍스트 정보를 제공
- ATT&CK 기법·CSP 로그·플레이북·과거 사례를 기반으로 검색·요약·제안 수행
- 최종 판단은 항상 수사관이 한다. AI는 결정하지 않는다.

[응답 규칙]
1. 한국어로 답변한다.
2. 아래 [지식베이스] 섹션에 제공된 청크만 근거로 사용한다. 청크에 없는 사실은 추측하지 않고 "추가 확인 필요"로 표시한다.
3. 본문에서 출처를 [1], [2] 형식으로 인용한다 (예: "T1078.004는 자격증명 남용입니다 [1].").
4. 답할 수 없으면 "제공된 정보로는 답변할 수 없습니다"로 명시한다.
5. 응답은 핵심 포인트 3~5개를 글머리표(-)로 구조화한다.
6. 마지막 줄에 정확히 다음 문구를 추가한다: "※ 최종 판단은 수사관께서 직접 수행해 주세요."
"""


# ─────────────────────────────────────────────────────────────
# Fallback 응답 (LLM 미연결 / timeout / 컨텍스트 없음)
# ─────────────────────────────────────────────────────────────
_FALLBACK_NO_CONTEXT = (
    "- 제공된 정보로는 답변할 수 없습니다.\n"
    "- V-3 정규화·V-4 ATT&CK 매핑을 먼저 수행하면 더 구체적인 답변이 가능합니다.\n"
    "\n※ 최종 판단은 수사관께서 직접 수행해 주세요."
)

_FALLBACK_TIMEOUT = (
    "- AI 응답이 지연되어 시간 내에 완료되지 못했습니다.\n"
    "- 잠시 후 다시 시도하거나 V-6 ATT&CK 히트맵에서 직접 분석을 시작해 주세요.\n"
    "\n※ 최종 판단은 수사관께서 직접 수행해 주세요."
)


# ─────────────────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────────────────
def _build_user_prompt(query: str, context: list[KBChunk]) -> str:
    """RAG 청크를 user prompt 에 주입한다.

    각 청크 텍스트는 500자로 컷 — 토큰 절약 + 응답 시간 단축.
    출처 인용용으로 [N] 번호를 부여하여 모델이 본문에서 [1], [2] 형태로 인용하도록 유도.
    """
    parts = ["[지식베이스]"]
    if not context:
        parts.append("(관련 청크 없음)")
    else:
        for i, c in enumerate(context, 1):
            text = c.text.strip().replace("\n", " ")
            if len(text) > 500:
                text = text[:497] + "…"
            parts.append(f"[{i}] {c.title} ({c.kb_name})")
            parts.append(f"출처: {c.source}")
            parts.append(text)
            parts.append("")
    parts.append("[질의]")
    parts.append(query.strip())
    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────
# LLMEngine
# ─────────────────────────────────────────────────────────────
class LLMEngine:
    """sLLM 추상화 — Ollama Chat API 호출. 인터페이스는 깡통 시절과 동일."""

    @classmethod
    def generate(
        cls,
        prompt: str,
        context: Optional[list[KBChunk]] = None,
    ) -> str:
        """주어진 질의 + RAG 청크로 응답을 생성한다.

        Args:
            prompt:  사용자 자연어 질의.
            context: RAGRetriever 가 반환한 KB 청크 리스트 (k=3 권장).

        Returns:
            한국어 응답 텍스트. timeout 또는 컨텍스트 부재 시 fallback.
        """
        if not context:
            return _FALLBACK_NO_CONTEXT

        user_prompt = _build_user_prompt(prompt, context)

        try:
            r = httpx.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {
                        # 시연 안정성 — 응답이 매번 흔들리지 않도록 결정성 ↑
                        "temperature": 0.3,
                        # 노트북 환경 기준 800 tokens ≈ 16~27초 (30s timeout 안 걸림)
                        "num_predict": 800,
                        # system + 3청크(@500자) + 질의 ≈ 2k tokens → 4k 윈도우면 여유
                        "num_ctx": 4096,
                    },
                },
                timeout=settings.LLM_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            content = (data.get("message") or {}).get("content", "").strip()
            return content or _FALLBACK_NO_CONTEXT

        except httpx.TimeoutException:
            logger.warning(
                "[LLMEngine] Ollama timeout (>%ds, model=%s)",
                settings.LLM_TIMEOUT,
                settings.LLM_MODEL,
            )
            return _FALLBACK_TIMEOUT

        except httpx.HTTPError as e:
            logger.warning("[LLMEngine] Ollama HTTP error: %s", e)
            return _FALLBACK_TIMEOUT

        except Exception:
            logger.exception("[LLMEngine] unexpected error")
            return _FALLBACK_TIMEOUT

    @classmethod
    def health(cls) -> dict:
        """Ollama 서버 상태 + 설정 모델 존재 여부 확인.

        Returns:
            {
              "engine":           "ollama" | "ollama-no-model" | "stub",
              "model":            LLM_MODEL,
              "available_models": [...],
              "connected":        bool,
            }
        """
        try:
            r = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2.0)
            if r.ok:
                models = [m.get("name") for m in r.json().get("models", [])]
                connected = settings.LLM_MODEL in models
                return {
                    "engine": "ollama" if connected else "ollama-no-model",
                    "model": settings.LLM_MODEL,
                    "available_models": models,
                    "connected": connected,
                }
        except Exception:
            pass

        return {
            "engine": "stub",
            "model": settings.LLM_MODEL,
            "available_models": [],
            "connected": False,
            "note": "Ollama 서버 미연결 — 설치 후 'ollama serve' 실행 + 모델 pull 필요",
        }
