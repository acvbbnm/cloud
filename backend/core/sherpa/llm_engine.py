"""Layer 3 — LLMEngine.

깡통 구현: Ollama Llama 호출 없이 템플릿 기반 응답을 생성.
인터페이스(`generate(prompt, context)`)는 Ollama 교체 시 동일 시그니처 유지.

향후 확장:
- OLLAMA_BASE_URL 환경변수로 Ollama Llama 3.1 8B 호출
- 30초 timeout 시 fallback 메시지 (SNF-02 요구사항)
"""
from typing import Optional

from core.sherpa.knowledge_base import KBChunk


class LLMEngine:
    """sLLM 추상화 — 현재는 템플릿 응답, 추후 Ollama 로 교체."""

    @classmethod
    def generate(
        cls,
        prompt: str,
        context: Optional[list[KBChunk]] = None,
    ) -> str:
        """주어진 프롬프트 + 컨텍스트로 응답 생성. 깡통은 컨텍스트를 그대로 인용한다.

        진짜 LLM 으로 교체 시:
          POST {OLLAMA_BASE_URL}/api/generate
            { "model": "llama3.1:8b", "prompt": "{prompt}\\n\\n{context}", "stream": false }
        """
        if not context:
            return (
                "관련 지식베이스 검색 결과가 없습니다. 질의를 더 구체적으로 입력해 보시거나 "
                "수집된 ATT&CK 매핑 결과(V-6)를 확인해 주세요."
            )

        lines = [
            "지식베이스에서 관련 정보를 찾았습니다:",
            "",
        ]
        for i, c in enumerate(context, 1):
            preview = c.text.strip().replace("\n", " ")
            if len(preview) > 300:
                preview = preview[:297] + "…"
            lines.append(f"[{i}] **{c.title}** ({c.kb_name})")
            lines.append(f"    {preview}")
            lines.append("")

        lines.append("⚠ 본 응답은 결정론적 키워드 매칭 기반입니다. "
                     "최종 판단은 수사관께서 직접 수행해 주세요.")
        return "\n".join(lines)

    @classmethod
    def health(cls) -> dict:
        """LLM 엔진 상태 (현재는 항상 'stub')."""
        return {
            "engine": "stub",
            "model": "template-based",
            "note": "Ollama Llama 3.1 8B 미연결 — Phase 3 후반에 교체 예정",
        }
