"""Layer 3 — LLMEngine (Ollama 통합 버전).

설계서 5.4.5절 + 모듈별_구현_명세.md `LLMEngine` 항목.

흐름:
  AISherpa.chat() → LLMEngine.generate(query, context) → Ollama /api/chat → 응답 텍스트
  AISherpa.chat_stream() → LLMEngine.generate_stream() → 토큰 단위 yield (Phase 2.3)

핵심 원칙 (CLAUDE.md / 설계서 5.1절 정합):
  - AI 는 판단·결정하지 않는다. 검색·요약·제안만 수행.
  - 모든 응답은 한국어 + 출처 [N] 인용 + "최종 판단은 수사관" 문구 포함.
  - 30초 timeout (SNF-02) 시 정해진 fallback 메시지 반환.

설정 (config.py + .env):
  - OLLAMA_BASE_URL : 기본 http://localhost:11434
  - LLM_MODEL       : 기본 gpt-oss:20b (필요 시 llama3.1:8b 등 교체)
  - LLM_TIMEOUT     : 초 (SNF-02 = 30)

GPT-OSS 호환:
  - 응답에 `<thinking>`, `<think>`, `analysis...assistantfinal` 같은 reasoning 토큰이
    섞일 수 있어 `_strip_reasoning()` 으로 후처리하여 최종 답변만 V-8 에 노출.
  - 스트리밍 시: reasoning 영역 끝(`</think>` 또는 `assistantfinal`)을 만나기 전까지의
    토큰은 클라이언트에 전송하지 않고 버퍼링. 끝 마커 이후 토큰만 yield.
"""
import json
import logging
import os
import re
from typing import Iterator, Optional

import httpx

from config import settings
from core.sherpa.knowledge_base import KBChunk

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Reasoning 토큰 후처리 (GPT-OSS / DeepSeek 등 호환)
# ─────────────────────────────────────────────────────────────
# 일부 추론 모델은 응답에 사고 과정을 그대로 노출함 (XML 태그 또는 마커).
# 평가용 화면(V-8)에서는 최종 답변만 보여야 하므로 제거한다.
_THINKING_TAG = re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE)
_THINK_TAG = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_ANALYSIS_BLOCK = re.compile(
    r"^.*?analysis.*?assistantfinal\s*",
    re.DOTALL | re.IGNORECASE,
)


def _strip_reasoning(text: str) -> str:
    """모델 응답에서 reasoning 토큰을 제거하고 최종 답변만 남긴다.

    빈 문자열이면 그대로 반환 (호출자가 fallback 처리).
    """
    if not text:
        return text
    text = _THINKING_TAG.sub("", text)
    text = _THINK_TAG.sub("", text)
    # GPT-OSS "analysis ... assistantfinal" 패턴 (있을 때만 한 번)
    text = _ANALYSIS_BLOCK.sub("", text, count=1)
    return text.strip()


# ─────────────────────────────────────────────────────────────
# 환각 검출·라벨링 — Phase 2.5 KB 인용 감사 (2026-05-24, P1)
# ─────────────────────────────────────────────────────────────
# CLAUDE.md "AI 는 판단하지 않음" 원칙 정합. KB audit 에서 LLM 이 컨텍스트 밖
# T-id 12 건 신규 도입 (D_no_halluc 85.7%) → 본 P1 적용 후 100% 달성.
#
# 2단 방어선:
#   1) SYSTEM_PROMPT 의 [ATT&CK 기법 인용 — 엄수] 조항 + 좋은/나쁜 예시
#   2) 응답 후처리 — 화이트리스트 밖 T-id 를 [KB외:T1234] 라벨로 표시
#      (제거 X — 문장 의미 보존 + 수사관이 직접 식별 가능)
#
# G1 결정 (회의 2026-05-24): 라벨 형식 "[KB외:T1234]" 채택 — 구체적 T-id 노출이
# 수사관 검증 시간을 단축. 감사 도구의 _LABELED_TECH_RE 가 이 형식을 직접 카운트.
# 진규 안의 sub-technique 관용 처리 (base T1078 allowed → T1078.004 통과) 도 흡수.
_TECH_REF_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")


def _collect_context_techs(context: Optional[list[KBChunk]]) -> set[str]:
    """KB context 청크들에서 인용 가능한 T-id 화이트리스트 추출.

    수집 소스 (OR):
      - chunk.meta["technique_id"]  (ATTACK chunk 의 직접 메타)
      - chunk.text 내부의 T1234 / T1234.567 패턴 (본문 등장)
      - chunk.title 의 T-id 도 본문 등장으로 간주
    """
    techs: set[str] = set()
    for c in context or []:
        tid = c.meta.get("technique_id") if hasattr(c, "meta") else None
        if tid:
            techs.add(tid)
        techs.update(_TECH_REF_RE.findall(c.text or ""))
        techs.update(_TECH_REF_RE.findall(c.title or ""))
    return techs


def _sanitize_response(text: str, context: Optional[list[KBChunk]]) -> str:
    """응답 텍스트의 KB 외 T-id 를 [KB외:T1234] 라벨로 치환.

    동작:
      - context 청크의 T-id 화이트리스트 구축
      - 응답의 모든 T-id 정규식 매칭 → 화이트리스트 외이면 라벨링
      - sub-technique 관용 허용 (진규 안 흡수): base T1078 in allowed → T1078.004 통과
      - 이미 라벨된 토큰 (직전 12자 내 "[KB외:") 은 중복 라벨링 안 함

    context 가 None / 빈 리스트면 sanitize skip (fallback 응답 보호).
    """
    if not text or not context:
        return text
    allowed = _collect_context_techs(context)
    # 빈 화이트리스트도 진행 — 답변이 비-ATT&CK 영역일 수 있어 라벨링만 수행

    def _label(match: re.Match) -> str:
        tid = match.group(0)
        if tid in allowed:
            return tid
        # sub-technique 관용 — base T1078 in allowed 면 T1078.004 도 통과
        base = tid.split(".")[0]
        if base in allowed:
            return tid
        # 이미 라벨된 토큰 중복 방지
        start = match.start()
        head = text[max(0, start - 12) : start]
        if "[KB외:" in head:
            return tid
        return f"[KB외:{tid}]"

    return _TECH_REF_RE.sub(_label, text)


# 진규 안 호환 alias — CLAUDE.md 5-1 규칙이 명시한 함수명 + 테스트 파일 호환.
# 신규 코드에선 _sanitize_response / _collect_context_techs 사용 권장.
_strip_unsourced_techniques = _sanitize_response
_extract_allowed_techniques = _collect_context_techs
_TID_PATTERN = _TECH_REF_RE


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

[ATT&CK 기법 인용 — 엄수]
- T-id (예: T1078, T1098.001)를 응답에 쓸 때는 반드시 [지식베이스] 청크 본문이나 메타에 명시된 T-id 만 인용한다.
- 제공된 청크에 없는 T-id 는 절대 새로 만들지 않는다. 청크 외 ATT&CK 기법이 떠오르면 "관련 ATT&CK 기법은 V-4 매핑 결과 참조" 로만 안내하고 구체 T-id 를 적지 않는다.
- 이 규칙은 수사관 신뢰와 직결된다. 위반 시 응답이 후처리에서 [KB외:Txxxx] 라벨로 자동 변조되며, 사용자에게 "환각" 으로 노출되어 신뢰도가 떨어진다.

[좋은 예]
청크 [1] 본문: "T1098.001 Account Manipulation: Additional Cloud Credentials — IAM 키 추가로 영속성 확보."
→ 답: "공격자는 추가 IAM 키 등록으로 영속성을 확보한 것으로 보입니다 (T1098.001) [1]."

[나쁜 예 — 절대 금지]
청크 [1] 에 T1098.001 만 있는데
→ 답: "T1078 Valid Accounts 와 T1552.001 Credentials In Files 도 의심됩니다." (청크에 없는 T-id 생성 — 금지)
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
            추론 모델(gpt-oss 등)의 reasoning 토큰은 자동 제거.
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
                        # GPU 노트북 기준 800 tokens 약 20초, CPU 전용은 그 5~10배.
                        # 환경변수 LLM_NUM_PREDICT 로 오버라이드 가능 (CPU 머신은 300 권장).
                        "num_predict": int(os.getenv("LLM_NUM_PREDICT", "400")),
                        # system + 3청크(@500자) + 질의 ≈ 2k tokens → 4k 윈도우면 여유
                        "num_ctx": 4096,
                    },
                },
                timeout=settings.LLM_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            content = (data.get("message") or {}).get("content", "").strip()
            # gpt-oss 등의 reasoning 토큰 제거
            content = _strip_reasoning(content)
            # Phase 2.5 (P1) — KB 외 ATT&CK T-id 를 [KB외:T1234] 로 라벨링하여 환각 차단
            content = _sanitize_response(content, context)
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
    def generate_stream(
        cls,
        prompt: str,
        context: Optional[list[KBChunk]] = None,
    ) -> Iterator[str]:
        """스트리밍 응답 생성 — Ollama stream=True. 토큰 단위 yield (Phase 2.3).

        UX 효과: 100초 체감 대기 → 첫 토큰까지 ~5초 + 점진 표시.

        후처리:
          - Reasoning 토큰(`<think>...</think>`, GPT-OSS analysis 블록) 안의 토큰은
            yield 하지 않고 버퍼링. 끝 마커 이후부터만 클라이언트로 흘려보냄.
          - 컨텍스트 없거나 오류 시 fallback 한 번에 반환 후 종료.

        Yields:
            응답 텍스트의 점진적 청크 (delta). 한 번의 호출이 종료되면 generator 끝.
        """
        if not context:
            yield _FALLBACK_NO_CONTEXT
            return

        user_prompt = _build_user_prompt(prompt, context)
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
            "options": {
                "temperature": 0.3,
                "num_predict": int(os.getenv("LLM_NUM_PREDICT", "400")),
                "num_ctx": 4096,
            },
        }

        try:
            with httpx.stream(
                "POST",
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json=payload,
                timeout=settings.LLM_TIMEOUT,
            ) as r:
                if not r.is_success:
                    logger.warning(
                        "[LLMEngine.stream] Ollama HTTP %d (model=%s)",
                        r.status_code,
                        settings.LLM_MODEL,
                    )
                    yield _FALLBACK_TIMEOUT
                    return

                # 스트리밍 상태 머신
                in_thinking = False       # <think> 또는 <thinking> 진입 여부
                analysis_skipped = False  # GPT-OSS analysis 블록 통과 완료 여부
                buffer = ""               # 마커 매칭 대비 사이드 버퍼
                emitted_any = False       # 최소 1 토큰 emit 됐는지

                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = chunk.get("message") or {}
                    delta = msg.get("content", "")
                    if not delta:
                        if chunk.get("done"):
                            break
                        continue

                    buffer += delta

                    # GPT-OSS analysis 블록 — 첫 'assistantfinal' 마커 전까지 skip
                    if not analysis_skipped and "assistantfinal" in buffer.lower():
                        idx = buffer.lower().rfind("assistantfinal")
                        buffer = buffer[idx + len("assistantfinal"):]
                        analysis_skipped = True

                    # <think> 또는 <thinking> 오픈/클로즈 마커 처리
                    while True:
                        if not in_thinking:
                            # 열림 마커 찾기
                            low = buffer.lower()
                            i_open = -1
                            for tag in ("<thinking>", "<think>"):
                                pos = low.find(tag)
                                if pos != -1 and (i_open == -1 or pos < i_open):
                                    i_open = pos
                            if i_open == -1:
                                break
                            # 마커 전까지는 emit
                            if i_open > 0:
                                yield buffer[:i_open]
                                emitted_any = True
                            buffer = buffer[i_open:]
                            in_thinking = True
                        else:
                            low = buffer.lower()
                            i_close = max(low.find("</thinking>"), low.find("</think>"))
                            if i_close == -1:
                                # 아직 닫힘 마커 안 옴 — 추가 청크 대기
                                buffer = ""
                                break
                            # 닫힘 마커 길이는 7 또는 10
                            close_tag = "</thinking>" if "</thinking>" in low else "</think>"
                            buffer = buffer[i_close + len(close_tag):]
                            in_thinking = False

                    # 안전 emit — 마커 매칭 후 남은 텍스트가 길어지면 보냄
                    # (마지막 32자는 마커 분할 대비 유지 — T-id 최대 9자 < 32자 보호)
                    if not in_thinking and len(buffer) > 32:
                        # P0 환각 방지 — 컨텍스트 밖 T-id 라벨링 후 emit
                        yield _strip_unsourced_techniques(buffer[:-32], context)
                        buffer = buffer[-32:]
                        emitted_any = True

                    if chunk.get("done"):
                        break

                # 잔여 버퍼 정리
                if not in_thinking and buffer:
                    yield _strip_unsourced_techniques(buffer, context)
                    emitted_any = True

                if not emitted_any:
                    yield _FALLBACK_NO_CONTEXT

        except httpx.TimeoutException:
            logger.warning(
                "[LLMEngine.stream] timeout (>%ds, model=%s)",
                settings.LLM_TIMEOUT,
                settings.LLM_MODEL,
            )
            yield _FALLBACK_TIMEOUT
        except httpx.HTTPError as e:
            logger.warning("[LLMEngine.stream] HTTP error: %s", e)
            yield _FALLBACK_TIMEOUT
        except Exception:
            logger.exception("[LLMEngine.stream] unexpected error")
            yield _FALLBACK_TIMEOUT

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
            # 10초로 완화 — Ollama 가 추론 중일 때 /api/tags 응답이 큐잉되어 지연되는 케이스 대응.
            # 너무 짧으면 모델이 RAM 에 로드된 상태에서도 health 가 'stub' 으로 표시되는 문제.
            r = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=10.0)
            # httpx 는 requests 와 달리 .ok 속성이 없음 — is_success 사용
            if r.is_success:
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
