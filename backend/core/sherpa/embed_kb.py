"""Layer 3 — KB 청크를 ChromaDB 에 임베딩하는 모듈.

설계서 5.4.5절 RAGRetriever 의 vectorDB 백엔드 구현.

동작 원칙:
- chromadb · sentence-transformers 가 설치되어 있으면 실제 임베딩
- 미설치 또는 모델 다운로드 실패 시 RAGRetriever 가 키워드 fallback 으로 자동 전환
- 별도 인프라 없이 BASE_DIR/chroma_data 에 영속화 (오프라인 동작, SNF-01)

사용법:
1) 서버 startup 시 자동 호출 (main.py lifespan)
2) CLI 로도 가능: `python -m core.sherpa.embed_kb`

향후:
- 한국어 특화 모델(ko-sroberta-multitask) 교체 가능 (EMBEDDING_MODEL 환경변수)
- 청크 크기 분할(현재 KB JSON 자체 청크 단위 사용)
"""
from __future__ import annotations

import logging
from typing import Optional

from config import settings
from core.sherpa.knowledge_base import KBChunk, load_all

logger = logging.getLogger(__name__)


# ── 모듈 import 보호 — 미설치 시에도 backend 가 기동되도록 ──

_chromadb_available = False
_sentence_transformers_available = False

try:
    import chromadb
    from chromadb.api import ClientAPI
    from chromadb.api.models.Collection import Collection
    from chromadb.config import Settings as ChromaSettings

    _chromadb_available = True
except ImportError:  # pragma: no cover
    chromadb = None  # type: ignore
    ClientAPI = None  # type: ignore
    Collection = None  # type: ignore
    ChromaSettings = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer

    _sentence_transformers_available = True
except ImportError:  # pragma: no cover
    SentenceTransformer = None  # type: ignore


# ── 전역 캐시 ──

_client: Optional["ClientAPI"] = None
_collection: Optional["Collection"] = None
_embedder: Optional["SentenceTransformer"] = None
_init_attempted = False
_last_error: Optional[str] = None


def is_available() -> bool:
    """패키지가 둘 다 import 되었는지 — 환경 점검용."""
    return _chromadb_available and _sentence_transformers_available


def status() -> dict:
    """현재 임베딩 백엔드 상태. V-8 KB 패널·health 응답에 사용.

    lazy init 보장 — embed_kb CLI 로 빌드 후 backend 재기동 시 첫 status() 가
    _collection 을 자동 로드하므로 'collection empty' 라벨이 잘못 표시되지 않는다.
    """
    if _collection is None and _chromadb_available:
        _ensure_collection()
    if _embedder is None and _sentence_transformers_available:
        _ensure_embedder()
    return {
        "chromadb_installed": _chromadb_available,
        "sentence_transformers_installed": _sentence_transformers_available,
        "embedder_loaded": _embedder is not None,
        "collection_loaded": _collection is not None,
        "collection_size": _collection.count() if _collection is not None else 0,
        "last_error": _last_error,
        "model": settings.EMBEDDING_MODEL if _embedder is not None else None,
    }


def _ensure_embedder() -> Optional["SentenceTransformer"]:
    """임베딩 모델 lazy 로드. 실패 시 None."""
    global _embedder, _last_error
    if _embedder is not None:
        return _embedder
    if not _sentence_transformers_available:
        _last_error = "sentence-transformers not installed"
        return None
    try:
        logger.info(f"loading embedder: {settings.EMBEDDING_MODEL}")
        _embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
        return _embedder
    except Exception as exc:  # pragma: no cover
        _last_error = f"embedder load failed: {exc}"
        logger.exception("embedder load failed")
        return None


def _ensure_client() -> Optional["ClientAPI"]:
    """ChromaDB persistent client lazy 초기화."""
    global _client, _last_error
    if _client is not None:
        return _client
    if not _chromadb_available:
        _last_error = "chromadb not installed"
        return None
    try:
        _client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        return _client
    except Exception as exc:  # pragma: no cover
        _last_error = f"chromadb client init failed: {exc}"
        logger.exception("chromadb client init failed")
        return None


def _ensure_collection() -> Optional["Collection"]:
    """KB 컬렉션 lazy 초기화. embedder 와 client 둘 다 준비되어야 함."""
    global _collection, _last_error
    if _collection is not None:
        return _collection
    client = _ensure_client()
    if client is None:
        return None
    try:
        _collection = client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        return _collection
    except Exception as exc:  # pragma: no cover
        _last_error = f"collection init failed: {exc}"
        logger.exception("collection init failed")
        return None


def _encode(texts: list[str]) -> Optional[list[list[float]]]:
    """문장들을 임베딩 벡터로 변환."""
    embedder = _ensure_embedder()
    if embedder is None:
        return None
    try:
        # convert_to_numpy=True → list 변환을 직접 처리
        vecs = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vecs]
    except Exception as exc:  # pragma: no cover
        global _last_error
        _last_error = f"encode failed: {exc}"
        logger.exception("encode failed")
        return None


def _chunk_to_document(c: KBChunk) -> str:
    """검색용 문서 텍스트. title + text + meta 의 일부."""
    parts = [c.title or "", c.text or ""]
    for k in ("technique_id", "tactic", "incident_type", "csp"):
        v = c.meta.get(k)
        if v:
            parts.append(f"{k}={v}")
    return "\n".join(p for p in parts if p)


def embed_all(force: bool = False) -> dict:
    """모든 KB 청크를 ChromaDB 에 적재.

    Args:
        force: True 면 컬렉션을 비우고 새로 적재. False 면 비어있을 때만 적재.

    Returns:
        통계 dict (적재 건수·skip 여부·에러).
    """
    global _init_attempted, _last_error
    _init_attempted = True

    chunks = load_all()
    if not chunks:
        _last_error = "no KB chunks found"
        return {"loaded": 0, "skipped": True, "reason": "no chunks"}

    collection = _ensure_collection()
    embedder = _ensure_embedder()
    if collection is None or embedder is None:
        return {
            "loaded": 0,
            "skipped": True,
            "reason": "chromadb or embedder unavailable",
            "error": _last_error,
        }

    existing = collection.count()
    if existing > 0 and not force:
        return {"loaded": existing, "skipped": True, "reason": "already populated"}

    if existing > 0 and force:
        # ChromaDB 0.5 → 컬렉션 비우기: 전체 ID 삭제
        try:
            ids = collection.get()["ids"]
            if ids:
                collection.delete(ids=ids)
        except Exception as exc:
            _last_error = f"clear failed: {exc}"
            logger.exception("clear failed")

    docs = [_chunk_to_document(c) for c in chunks]
    embeddings = _encode(docs)
    if embeddings is None:
        return {"loaded": 0, "skipped": True, "reason": "encode failed", "error": _last_error}

    ids = [c.chunk_id for c in chunks]
    metadatas = [
        {
            "kb_name": c.kb_name,
            "title": c.title or "",
            "source": c.source or "",
            # ChromaDB metadata 는 scalar 만 허용 → list 필드는 직렬화
            **{k: (v if isinstance(v, (str, int, float, bool)) else str(v))
               for k, v in c.meta.items()
               if v is not None and not isinstance(v, dict)},
        }
        for c in chunks
    ]
    try:
        collection.add(ids=ids, embeddings=embeddings, documents=docs, metadatas=metadatas)
        return {"loaded": len(ids), "skipped": False, "total_in_collection": collection.count()}
    except Exception as exc:  # pragma: no cover
        _last_error = f"add failed: {exc}"
        logger.exception("collection.add failed")
        return {"loaded": 0, "skipped": True, "reason": "add failed", "error": _last_error}


def query(
    text: str, k: int = 3, kb_filter: Optional[list[str]] = None
) -> Optional[list[tuple[str, float, dict]]]:
    """ChromaDB 에 의미 검색 질의.

    Returns:
        [(chunk_id, score, metadata)] — score 는 0~1 cosine similarity.
        ChromaDB 미준비 시 None (호출자가 키워드 fallback 으로 전환).
    """
    collection = _ensure_collection()
    if collection is None or collection.count() == 0:
        return None
    embedder = _ensure_embedder()
    if embedder is None:
        return None

    q_vecs = _encode([text])
    if q_vecs is None:
        return None

    where = None
    if kb_filter:
        # ChromaDB where 는 단일 값 또는 $in 연산자
        where = {"kb_name": {"$in": kb_filter}}

    try:
        res = collection.query(
            query_embeddings=q_vecs,
            n_results=k,
            where=where,
        )
    except Exception as exc:  # pragma: no cover
        global _last_error
        _last_error = f"query failed: {exc}"
        logger.exception("collection.query failed")
        return None

    out: list[tuple[str, float, dict]] = []
    ids = res.get("ids", [[]])[0]
    distances = res.get("distances", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    for cid, dist, meta in zip(ids, distances, metas):
        # cosine distance(0~2) → similarity(0~1)
        similarity = max(0.0, 1.0 - float(dist))
        out.append((cid, similarity, meta or {}))
    return out


# CLI 실행
if __name__ == "__main__":  # pragma: no cover
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print("Status:")
    print(json.dumps(status(), indent=2, ensure_ascii=False))
    print("\nEmbedding all KB chunks...")
    result = embed_all(force=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\nAfter embedding status:")
    print(json.dumps(status(), indent=2, ensure_ascii=False))
