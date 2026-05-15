"""Layer 3 — LLMEngine.

설계서 5.4.5절 LLMEngine 구현.

동작 우선순위:
1. Ollama HTTP 호출 (`OLLAMA_BASE_URL/api/generate`) — 환경변수 + 30초 timeout
2. 템플릿 응답 (1차 깡통) — Ollama 미연결·타임아웃·에러 시 자동 fallback (SNF-02)

기본 모델 = `gpt-oss:20b` (LLM_MODEL 환경변수로 변경 가능).
GPT-OSS 는 응답에 `<thinking>...</thinking>` 또는 `analysis...assistantfinal` 같은
reasoning 토큰이 섞일 수 있어 본 모듈에서 후처리해 최종 답변만 추출한다.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import requests

from config import settings
from core.sherpa.knowledge_base import KBChunk

logger = logging.getLogger(__name__)


# ── reasoning 토큰 후처리 ──
# GPT-OSS / DeepSeek 등은 응답에 사고 과정을 그대로 노출하는 경우가 있음.
# 평가용 화면(V-8)에서는 최종 답변만 보여야 하므로 제거한다.
_THINKING_TAG = re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE)
_THINK_TAG = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_ANALYSIS_BLOCK = re.compile(
    r"^.*?analysis.*?assistantfinal\s*",
    re.DOTALL | re.IGNORECASE,
)


def _strip_reasoning(text: str) -> str:
    """모델 응답에서 reasoning 토큰을 제거하고 최종 답변만 남긴다."""
    if not text:
        return text
    text = _THINKING_TAG.sub("", text)
    text = _THINK_TAG.sub("", text)
    # GPT-OSS "analysis ... assistantfinal" 패턴 (있을 때만)
    text = _ANALYSIS_BLOCK.sub("", text, count=1)
    return text.strip()


# ── Ollama 클라이언트 ──


_ollama_last_error: Optional[str] = None
_ollama_ok_cache: Optional[bool] = None  # 첫 헬스 체크 결과 캐싱


def _ollama_health() -> bool:
    """Ollama 서버 연결 여부 + 모델 보유 여부 빠른 점검 (5초 timeout)."""
    global _ollama_last_error, _ollama_ok_cache
    try:
        res = requests.get(
            f"{settings.OLLAMA_BASE_URL}/api/tags",
            timeout=5,
        )
        res.raise_for_status()
        data = res.json()
        models = [m.get("name", "") for m in data.get("models", [])]
        has_model = any(settings.LLM_MODEL in m for m in models)
        if not has_model:
            _ollama_last_error = (
                f"Ollama up but model '{settings.LLM_MODEL}' missing. "
                f"Run: ollama pull {settings.LLM_MODEL}"
            )
            _ollama_ok_cache = False
            return False
        _ollama_ok_cache = True
        _ollama_last_error = None
        return True
    except Exception as exc:
        _ollama_last_error = f"Ollama unreachable at {settings.OLLAMA_BASE_URL}: {exc}"
        _ollama_ok_cache = False
        return False


def _build_prompt(prompt: str, context: Optional[list[KBChunk]]) -> str:
    """수사관 지원 시스템 컨텍스트 + RAG 청크 + 사용자 질의 결합.

    원칙: AI는 판단하지 않는다. 검색·요약·제안만. 모든 응답에 출처 명시 권장.
    """
    sys_prompt = (
        "당신은 침해사고 분석을 보조하는 검색·요약 도구입니다. "
        "수집된 지식베이스에 기반하여 한국어로 간결히 답하세요. "
        "다음 규칙을 반드시 지키세요:\n"
        "1. 지식베이스에 없는 내용을 추측하거나 새로 만들어내지 마세요.\n"
        "2. 인용 가능한 KB 청크가 있으면 본문에 [1], [2] 같은 번호로 표시하세요.\n"
        "3. 최종 결정·판단은 수사관(human investigator)이 합니다. "
        "당신은 후보·맥락·요약만 제공하세요.\n"
        "4. 응답은 300자 내외로 짧게 정리하세요."
    )

    parts = [sys_prompt, ""]
    if context:
        parts.append("[참고 KB 청크]")
        for i, c in enumerate(context, 1):
            text = (c.text or "").strip().replace("\n\n", "\n")
            if len(text) > 500:
                text = text[:497] + "…"
            parts.append(f"[{i}] {c.title} ({c.kb_name})\n{text}")
        parts.append("")
    parts.append(f"[수사관 질의]\n{prompt}")
    parts.append("\n[답변]")
    return "\n".join(parts)


def _ollama_generate(prompt: str, context: Optional[list[KBChunk]]) -> Optional[str]:
    """Ollama 호출. 성공 시 응답 텍스트, 실패·timeout 시 None.

    timeout 은 SNF-02 (30초) 명세 준수. 초과 시 fallback.
    """
    global _ollama_last_error
    full_prompt = _build_prompt(prompt, context)

    payload = {
        "model": settings.LLM_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,  # 결정론적 응답 (환각 억제)
            "num_predict": 512,
            "top_p": 0.9,
        },
    }
    try:
        res = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=settings.LLM_TIMEOUT,
        )
        res.raise_for_status()
        data = res.json()
        text = data.get("response", "").strip()
        text = _strip_reasoning(text)
        return text or None
    except requests.exceptions.Timeout:
        _ollama_last_error = (
            f"Ollama timeout after {settings.LLM_TIMEOUT}s — SNF-02 fallback to template"
        )
        logger.warning(_ollama_last_error)
        return None
    except Exception as exc:
        _ollama_last_error = f"Ollama generate failed: {exc}"
        logger.exception("Ollama generate failed")
        return None


# ── 템플릿 fallback (1차 깡통 로직 유지) ──


def _template_generate(prompt: str, context: Optional[list[KBChunk]]) -> str:
    """Ollama 없이 동작하는 결정론적 응답. context 청크를 그대로 인용."""
    if not context:
        return (
            "관련 지식베이스 검색 결과가 없습니다. 질의를 더 구체적으로 입력해 "
            "보시거나 수집된 ATT&CK 매핑 결과(V-6)를 확인해 주세요."
        )

    lines = ["지식베이스에서 관련 정보를 찾았습니다:", ""]
    for i, c in enumerate(context, 1):
        preview = c.text.strip().replace("\n", " ")
        if len(preview) > 300:
            preview = preview[:297] + "…"
        lines.append(f"[{i}] **{c.title}** ({c.kb_name})")
        lines.append(f"    {preview}")
        lines.append("")
    lines.append(
        "⚠ 본 응답은 결정론적 키워드 매칭 기반입니다. 최종 판단은 수사관께서 "
        "직접 수행해 주세요."
    )
    return "\n".join(lines)


# ── 공개 API ──


class LLMEngine:
    """sLLM 추상화 — Ollama 우선 + 템플릿 fallback."""

    @classmethod
    def generate(
        cls,
        prompt: str,
        context: Optional[list[KBChunk]] = None,
    ) -> str:
        """주어진 프롬프트 + 컨텍스트로 응답 생성.

        Ollama 미연결·타임아웃·에러 시 자동 템플릿 응답 (SNF-02 명세).
        """
        # 첫 호출 시 1회 health check (성공이면 후속 호출은 바로 generate)
        if _ollama_ok_cache is None:
            _ollama_health()

        if _ollama_ok_cache:
            response = _ollama_generate(prompt, context)
            if response:
                return response
            # Ollama 호출 실패 시 fallback
        return _template_generate(prompt, context)

    @classmethod
    def health(cls) -> dict:
        """LLM 엔진 상태 (V-8 우측 패널·sherpa.health 응답).

        매 호출마다 갱신 — Ollama 가 도중에 켜지면 즉시 반영 (캐시는 generate 의
        시작 부담을 줄이기 위함).
        """
        ok = _ollama_health()
        if ok:
            return {
                "engine": "ollama",
                "model": settings.LLM_MODEL,
                "base_url": settings.OLLAMA_BASE_URL,
                "note": f"Ollama 연결 정상 (timeout {settings.LLM_TIMEOUT}s)",
            }
        return {
            "engine": "stub",
            "model": "template-based",
            "note": _ollama_last_error
            or "Ollama 미연결 — 템플릿 응답으로 자동 fallback",
        }
