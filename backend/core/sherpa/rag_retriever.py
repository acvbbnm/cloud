"""Layer 3 — RAGRetriever.

설계서 5.4.5절 RAGRetriever 구현. **인터페이스 (`retrieve`/`retrieve_by_technique`)
는 깡통 1차와 동일** — V-5/V-8 프론트엔드 변경 없음.

동작 우선순위:
1. ChromaDB 의미 검색 (embed_kb.query) — 임베딩 모델 + 컬렉션 준비된 경우
2. 키워드 매칭 + 점수화 (1차 깡통 로직) — fallback

이렇게 두 단계로 두면:
- Ollama·ChromaDB 셋업 전: 깡통 동작 (현재 그대로)
- 셋업 후: 의미 검색 자동 활성화
- 둘 다 호출자 입장에서 동일한 `[(KBChunk, score)]` 형식 반환
"""
import re
from typing import Optional

from core.sherpa.knowledge_base import KBChunk, load_all

# ChromaDB 백엔드 (선택적)
try:
    from core.sherpa import embed_kb as _embed_kb
except Exception:  # pragma: no cover — 절대 안 일어나야 하지만 안전 가드
    _embed_kb = None  # type: ignore


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\.\_가-힣]+")


def _tokenize(text: str) -> list[str]:
    """간단 토큰화 — 영문/숫자/한글/.·_ 기준 ≥2자, 소문자."""
    return [t.lower() for t in _TOKEN_PATTERN.findall(text or "") if len(t) >= 2]


def _keyword_score(query_tokens: list[str], chunk: KBChunk) -> float:
    """청크 점수 = 쿼리 토큰 각각이 title+text 에 나타난 횟수 가중합."""
    blob = (chunk.title + " " + chunk.text).lower()
    score = 0.0
    for tok in query_tokens:
        if tok in blob:
            score += blob.count(tok) * (1.0 + min(len(tok) / 10.0, 1.0))
    return score


def _keyword_retrieve(
    query: str, k: int, kb_filter: Optional[list[str]]
) -> list[tuple[KBChunk, float]]:
    """키워드 fallback 구현 (1차 깡통과 동일 로직)."""
    chunks = load_all()
    if kb_filter:
        chunks = [c for c in chunks if c.kb_name in kb_filter]

    tokens = _tokenize(query)
    if not tokens:
        return []

    scored: list[tuple[KBChunk, float]] = []
    for c in chunks:
        s = _keyword_score(tokens, c)
        if s > 0:
            scored.append((c, s))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


def _chroma_retrieve(
    query: str, k: int, kb_filter: Optional[list[str]]
) -> Optional[list[tuple[KBChunk, float]]]:
    """ChromaDB 의미 검색. 미준비 시 None → 호출자가 키워드 fallback."""
    if _embed_kb is None:
        return None

    result = _embed_kb.query(text=query, k=k, kb_filter=kb_filter)
    if result is None:
        return None  # ChromaDB 미준비 (컬렉션 비어있거나 모델 미설치)
    if not result:
        return []  # 의미 있는 결과 0건

    # chunk_id → KBChunk 매핑
    all_chunks = {c.chunk_id: c for c in load_all()}
    out: list[tuple[KBChunk, float]] = []
    for chunk_id, similarity, _meta in result:
        chunk = all_chunks.get(chunk_id)
        if chunk is None:
            continue
        out.append((chunk, similarity))
    return out


class RAGRetriever:
    """KB 청크 검색기 — ChromaDB 우선 + 키워드 fallback."""

    @classmethod
    def retrieve(
        cls,
        query: str,
        k: int = 3,
        kb_filter: Optional[list[str]] = None,
    ) -> list[tuple[KBChunk, float]]:
        """쿼리에 가장 관련 있는 KB 청크 k개 반환.

        kb_filter: ['ATTACK', 'PLAYBOOK'] 등으로 카테고리 한정 가능.
        """
        # 1차: ChromaDB 의미 검색
        chroma = _chroma_retrieve(query, k, kb_filter)
        if chroma is not None:
            # 상위 점수가 약하면(< 0.2) 키워드 결과로 보강
            if not chroma or chroma[0][1] < 0.2:
                kw = _keyword_retrieve(query, k, kb_filter)
                seen = {c.chunk_id for c, _ in chroma}
                for c, s in kw:
                    if c.chunk_id not in seen and len(chroma) < k:
                        # 키워드 점수를 0~1 스케일로 단순 정규화 (보조 결과 표시용)
                        chroma.append((c, min(s / 100.0, 0.5)))
                        seen.add(c.chunk_id)
            return chroma

        # 2차: 키워드 fallback (ChromaDB 미준비 환경)
        return _keyword_retrieve(query, k, kb_filter)

    @classmethod
    def retrieve_by_technique(
        cls, technique_id: str, k: int = 3
    ) -> list[tuple[KBChunk, float]]:
        """ATT&CK 기법 ID 직매칭 우선 + 의미/키워드 검색 보조.

        기법 ID가 메타에 정확히 매칭되는 청크는 score=1.0 (최우선).
        그 다음 의미 검색 또는 키워드 검색으로 보강.
        """
        chunks = load_all()
        direct = [c for c in chunks if c.meta.get("technique_id") == technique_id]
        if direct:
            return [(c, 1.0) for c in direct[:k]]
        # fallback — 의미 검색 또는 키워드 검색
        return cls.retrieve(technique_id, k=k)

    @classmethod
    def backend_info(cls) -> dict:
        """현재 RAG 백엔드 상태 (V-8 KB 패널 / health 응답용)."""
        if _embed_kb is None:
            return {"backend": "keyword", "reason": "embed_kb module unavailable"}
        status = _embed_kb.status()
        if status["embedder_loaded"] and status["collection_size"] > 0:
            return {
                "backend": "chromadb",
                "model": status["model"],
                "collection_size": status["collection_size"],
            }
        if not status["chromadb_installed"]:
            return {"backend": "keyword", "reason": "chromadb not installed"}
        if not status["sentence_transformers_installed"]:
            return {"backend": "keyword", "reason": "sentence-transformers not installed"}
        if status["collection_size"] == 0:
            return {
                "backend": "keyword",
                "reason": "ChromaDB collection empty — run `python -m core.sherpa.embed_kb` to populate",
            }
        return {"backend": "keyword", "reason": status.get("last_error") or "unknown"}
