"""Layer 3 — RAGRetriever.

깡통 구현: ChromaDB 임베딩 없이 키워드 매칭 + 점수화로 KB 청크를 검색한다.
인터페이스(`retrieve(query, k)`)는 ChromaDB 교체 시에도 동일하게 사용 가능.

향후 확장:
- core/sherpa/embed_kb.py 로 KB 청크를 ChromaDB 에 임베딩
- 본 모듈을 sentence-transformer + cosine similarity 기반으로 교체
"""
import re
from typing import Optional

from core.sherpa.knowledge_base import KBChunk, load_all


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\.\_가-힣]+")


def _tokenize(text: str) -> list[str]:
    """간단 토큰화: 영문/숫자/한글/.(점)/_(언더바) 기준."""
    return [t.lower() for t in _TOKEN_PATTERN.findall(text or "") if len(t) >= 2]


def _score(query_tokens: list[str], chunk: KBChunk) -> float:
    """청크 점수 = 쿼리 토큰 각각이 title+text 에 나타난 횟수 합 (단순)."""
    blob = (chunk.title + " " + chunk.text).lower()
    score = 0.0
    for tok in query_tokens:
        # 정확 매칭 가산점 (technique_id 같은 케이스)
        if tok in blob:
            score += blob.count(tok) * (1.0 + min(len(tok) / 10.0, 1.0))
    return score


class RAGRetriever:
    """KB 청크 검색기 — 깡통 키워드 매칭 구현."""

    @classmethod
    def retrieve(
        cls,
        query: str,
        k: int = 3,
        kb_filter: Optional[list[str]] = None,
    ) -> list[tuple[KBChunk, float]]:
        """쿼리에 가장 관련 있는 KB 청크 k개를 score 내림차순으로 반환.

        kb_filter: ['ATTACK', 'PLAYBOOK'] 등으로 카테고리 한정 가능.
        """
        chunks = load_all()
        if kb_filter:
            chunks = [c for c in chunks if c.kb_name in kb_filter]

        tokens = _tokenize(query)
        if not tokens:
            return []

        scored: list[tuple[KBChunk, float]] = []
        for c in chunks:
            s = _score(tokens, c)
            if s > 0:
                scored.append((c, s))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    @classmethod
    def retrieve_by_technique(cls, technique_id: str, k: int = 3) -> list[tuple[KBChunk, float]]:
        """ATT&CK 기법 ID 직매칭 우선 + 키워드 검색 보조."""
        chunks = load_all()
        direct = [c for c in chunks if c.meta.get("technique_id") == technique_id]
        if direct:
            return [(c, 100.0) for c in direct[:k]]
        # fallback: 키워드 검색
        return cls.retrieve(technique_id, k=k)
