"""Layer 3 — RAGRetriever.

ChromaDB cosine similarity 기반 KB 검색. 인터페이스(`retrieve`, `retrieve_by_technique`)
는 깡통 시절과 동일하므로 AISherpa 등 호출자 영향 없음.

Fallback 정책 (시연 안정성):
  ChromaDB import 실패 / 컬렉션 비어있음 / 쿼리 예외 → 키워드 매칭 fallback.
  즉 `python -m core.sherpa.embed_kb` 를 한 번도 실행 안 했어도 RAG 가 동작은 한다.

설계서 5.4.5절 + 설치 검증 2026-05-14 (ONNX MiniLM L6 v2, 384 dim, ~80MB 캐시).
"""
import logging
import re
from typing import Optional

from core.sherpa.knowledge_base import KBChunk, load_all

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# ChromaDB 모듈 import — 실패 시 키워드 fallback 만 동작
# ─────────────────────────────────────────────────────────────
try:
    from core.sherpa import embed_kb as _ek

    _CHROMADB_AVAILABLE = True
except Exception as e:  # noqa: BLE001 — import-time 오류는 광범위 catch
    logger.warning("[RAGRetriever] ChromaDB import 실패 — 키워드 fallback 만 사용: %s", e)
    _ek = None
    _CHROMADB_AVAILABLE = False


# ─────────────────────────────────────────────────────────────
# 키워드 fallback 유틸 (옛 깡통 로직 그대로 보존)
# ─────────────────────────────────────────────────────────────
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\.\_가-힣]+")


def _tokenize(text: str) -> list[str]:
    """영문/숫자/한글/.(점)/_(언더바) 기준 토큰화 (≥2자)."""
    return [t.lower() for t in _TOKEN_PATTERN.findall(text or "") if len(t) >= 2]


def _keyword_score(query_tokens: list[str], chunk: KBChunk) -> float:
    """쿼리 토큰 × 청크 title+text 출현 횟수 × 토큰 길이 가중치."""
    blob = (chunk.title + " " + chunk.text).lower()
    score = 0.0
    for tok in query_tokens:
        if tok in blob:
            score += blob.count(tok) * (1.0 + min(len(tok) / 10.0, 1.0))
    return score


# ─────────────────────────────────────────────────────────────
# RAGRetriever
# ─────────────────────────────────────────────────────────────
class RAGRetriever:
    """KB 청크 검색기 — ChromaDB cosine 우선, 키워드 fallback."""

    @classmethod
    def retrieve(
        cls,
        query: str,
        k: int = 3,
        kb_filter: Optional[list[str]] = None,
    ) -> list[tuple[KBChunk, float]]:
        """가장 관련 있는 KB 청크 k개를 (chunk, score) 내림차순으로 반환.

        Args:
            query: 자연어 질의.
            k: 반환할 청크 수.
            kb_filter: ['ATTACK', 'PLAYBOOK'] 등 카테고리 한정 (선택).

        Returns:
            cosine 의 경우 score = 1 - cosine_distance (0~1, 1이 가장 유사).
            키워드의 경우 score = 단순 가중 횟수 (절대 비교 의미 없음).
        """
        if not query or not query.strip():
            return []

        if _CHROMADB_AVAILABLE:
            try:
                return cls._retrieve_chromadb(query, k, kb_filter)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "[RAGRetriever] ChromaDB retrieve 실패 — 키워드 fallback: %s", e
                )

        return cls._retrieve_keyword(query, k, kb_filter)

    # ── ChromaDB ────────────────────────────────────────────
    @classmethod
    def _retrieve_chromadb(
        cls, query: str, k: int, kb_filter: Optional[list[str]]
    ) -> list[tuple[KBChunk, float]]:
        collection = _ek.get_collection(create_if_missing=False)
        if collection.count() == 0:
            raise RuntimeError(
                "kb_chunks 컬렉션 비어있음 — 'python -m core.sherpa.embed_kb' 먼저 실행"
            )

        where = None
        if kb_filter:
            where = {"kb_name": {"$in": kb_filter}}

        result = collection.query(
            query_texts=[query],
            n_results=k,
            where=where,
        )
        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        if not ids:
            return []

        # chunk_id → KBChunk 매핑 (인메모리 KB와 ChromaDB ID 동기화 가정)
        chunks_by_id = {c.chunk_id: c for c in load_all()}

        out: list[tuple[KBChunk, float]] = []
        for chunk_id, distance in zip(ids, distances):
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                # ChromaDB에는 있는데 인메모리 KB엔 없음 — 컬렉션 stale, skip
                logger.warning(
                    "[RAGRetriever] chunk_id 매칭 없음(stale collection?): %s", chunk_id
                )
                continue
            score = max(0.0, 1.0 - float(distance))  # cosine: 1 - distance
            out.append((chunk, score))
        return out

    # ── 키워드 fallback ─────────────────────────────────────
    @classmethod
    def _retrieve_keyword(
        cls, query: str, k: int, kb_filter: Optional[list[str]]
    ) -> list[tuple[KBChunk, float]]:
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

    # ── ATT&CK 직매칭 (cosine 거치지 않음 — 빠르고 정확) ──
    @classmethod
    def retrieve_by_technique(
        cls, technique_id: str, k: int = 3
    ) -> list[tuple[KBChunk, float]]:
        """ATT&CK technique_id 메타 직매칭 우선, 없으면 일반 retrieve fallback."""
        chunks = load_all()
        direct = [c for c in chunks if c.meta.get("technique_id") == technique_id]
        if direct:
            return [(c, 1.0) for c in direct[:k]]
        return cls.retrieve(technique_id, k=k)

    # ── health (V-8 우측 패널 + /api/sherpa/kb 응답) ──
    @classmethod
    def health(cls) -> dict:
        """RAG 엔진 상태."""
        if not _CHROMADB_AVAILABLE:
            return {
                "engine": "keyword",
                "indexed": 0,
                "note": "ChromaDB 미설치 — 키워드 매칭으로 동작 중",
            }

        try:
            collection = _ek.get_collection(create_if_missing=False)
            count = collection.count()
            if count == 0:
                return {
                    "engine": "keyword",
                    "indexed": 0,
                    "note": "ChromaDB 컬렉션 비어있음 — 'python -m core.sherpa.embed_kb' 실행 필요",
                }
            return {
                "engine": "chromadb",
                "indexed": count,
                "collection": _ek.COLLECTION_NAME,
                "embedding": "all-MiniLM-L6-v2 (ONNX, 384 dim)",
            }
        except Exception as e:  # noqa: BLE001
            return {
                "engine": "keyword",
                "indexed": 0,
                "note": f"ChromaDB 접근 실패 — 키워드 fallback: {e}",
            }
