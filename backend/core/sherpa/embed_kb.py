"""KB 청크 → ChromaDB 컬렉션 적재 스크립트.

설계서 5.4.5절 + PROGRESS.md "다음 할 일 #1".

흐름:
  knowledge_base.load_all() → KB 4종 청크 → ChromaDB PersistentClient 의
  "kb_chunks" 컬렉션에 upsert. cosine similarity 인덱스. 임베딩 함수는
  ChromaDB 1.x 의 DefaultEmbeddingFunction (ONNX MiniLM L6 v2, 384 dim).

오프라인 동작:
  - 첫 실행 시 ONNX 모델(~80MB) 을 `~/.cache/chroma/onnx_models/` 로 다운로드.
  - 이후 실행은 캐시에서 로드 (오프라인 OK).
  - 시연 노트북 셋업 시 한 번 인터넷에 연결한 상태에서 `embed_kb --reset` 실행 권장.

CLI:
  python -m core.sherpa.embed_kb              # idempotent upsert
  python -m core.sherpa.embed_kb --reset      # 컬렉션 삭제 후 재적재
  python -m core.sherpa.embed_kb --stats      # 통계만 출력
  python -m core.sherpa.embed_kb --query Q    # 임시 검색 (디버그)

서버 startup 시 자동 호출은 의도적으로 안 함 (DB 초기화처럼 명시적 단계).
"""
import argparse
import io
import logging
import sys
from typing import Optional

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from config import settings
from core.sherpa.knowledge_base import KBChunk, load_all

logger = logging.getLogger(__name__)

COLLECTION_NAME = "kb_chunks"


# ─────────────────────────────────────────────────────────────
# 클라이언트 / 컬렉션
# ─────────────────────────────────────────────────────────────
_client: Optional[ClientAPI] = None
_embedding_fn = None


def _get_client() -> ClientAPI:
    """ChromaDB Persistent 클라이언트 — process-wide 싱글톤."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _client


def _get_embedding_fn():
    """기본 임베딩 함수 (ONNX MiniLM L6 v2, 384 dim) — process-wide 싱글톤."""
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = DefaultEmbeddingFunction()
    return _embedding_fn


def get_collection(create_if_missing: bool = True) -> Collection:
    """KB 컬렉션 반환. cosine 거리, default ONNX 임베딩."""
    client = _get_client()
    ef = _get_embedding_fn()
    if create_if_missing:
        return client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    return client.get_collection(name=COLLECTION_NAME, embedding_function=ef)


# ─────────────────────────────────────────────────────────────
# 메타 정리 — ChromaDB metadata 는 str/int/float/bool 만 허용
# ─────────────────────────────────────────────────────────────
def _flatten_meta(chunk: KBChunk) -> dict:
    """KBChunk → ChromaDB 호환 메타 dict."""
    meta: dict = {
        "kb_name": chunk.kb_name,
        "title": chunk.title or "",
        "source": chunk.source or "",
        "url": chunk.url or "",
    }
    for k, v in (chunk.meta or {}).items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            meta[k] = v
        else:
            # list / dict 는 문자열로 직렬화 (RAG 메타에서는 검색에만 사용되므로 손실 허용)
            meta[k] = str(v)
    return meta


# ─────────────────────────────────────────────────────────────
# 적재 / 통계 / 임시 검색
# ─────────────────────────────────────────────────────────────
def embed_all(reset: bool = False) -> dict:
    """KB 4종 청크를 ChromaDB 에 upsert. 동일 chunk_id 는 덮어쓰기."""
    client = _get_client()

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            logger.info("[embed_kb] reset: collection deleted")
        except Exception:
            # 컬렉션이 없으면 조용히 패스
            pass

    collection = get_collection(create_if_missing=True)
    chunks = load_all()

    if not chunks:
        logger.warning("[embed_kb] no chunks loaded from KB JSON")
        return {"loaded": 0, "by_kb": {}}

    ids = [c.chunk_id for c in chunks]
    documents = [f"{c.title}\n\n{c.text}".strip() for c in chunks]
    metadatas = [_flatten_meta(c) for c in chunks]

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    by_kb: dict[str, int] = {}
    for c in chunks:
        by_kb[c.kb_name] = by_kb.get(c.kb_name, 0) + 1

    return {"loaded": len(chunks), "by_kb": by_kb, "total_in_collection": collection.count()}


def stats() -> dict:
    """현재 컬렉션 상태 — 적재 건수 + 카테고리 카운트."""
    try:
        collection = get_collection(create_if_missing=False)
        count = collection.count()
        if count == 0:
            return {"indexed": 0, "by_kb": {}, "note": "embed_all() 미실행"}
        # by_kb 집계는 get() 으로 전체 메타 가져와서 셈
        result = collection.get(include=["metadatas"])
        by_kb: dict[str, int] = {}
        for m in result.get("metadatas") or []:
            kb = m.get("kb_name", "?")
            by_kb[kb] = by_kb.get(kb, 0) + 1
        return {"indexed": count, "by_kb": by_kb}
    except Exception as e:
        return {"indexed": 0, "by_kb": {}, "error": str(e)}


def quick_query(query_text: str, k: int = 3) -> list[dict]:
    """디버그용 임시 검색 — CLI --query 옵션이 사용."""
    collection = get_collection(create_if_missing=False)
    result = collection.query(query_texts=[query_text], n_results=k)
    ids = (result.get("ids") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    out = []
    for cid, dist, meta in zip(ids, distances, metadatas):
        out.append(
            {
                "chunk_id": cid,
                "score": round(max(0.0, 1.0 - dist), 4),
                "kb_name": (meta or {}).get("kb_name"),
                "title": (meta or {}).get("title"),
            }
        )
    return out


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
def _force_utf8_stdout() -> None:
    """Windows 콘솔(cp949)에서 한글·em-dash 출력 시 UnicodeEncodeError 방지."""
    if isinstance(sys.stdout, io.TextIOWrapper):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main() -> None:
    _force_utf8_stdout()
    parser = argparse.ArgumentParser(description="KB 청크 ChromaDB 적재 스크립트")
    parser.add_argument("--reset", action="store_true", help="컬렉션 삭제 후 재적재")
    parser.add_argument("--stats", action="store_true", help="현재 적재 통계만 출력")
    parser.add_argument("--query", help="디버그: 임시 검색 (텍스트)")
    parser.add_argument("--k", type=int, default=3, help="--query 시 top-k (기본 3)")
    args = parser.parse_args()

    if args.stats:
        s = stats()
        print(f"[stats] indexed={s.get('indexed')} by_kb={s.get('by_kb')}")
        if s.get("note"):
            print(f"        note: {s['note']}")
        return

    if args.query:
        rows = quick_query(args.query, k=args.k)
        print(f"[query='{args.query}' k={args.k}]")
        for i, r in enumerate(rows, 1):
            print(f"  [{i}] score={r['score']} {r['kb_name']:<10} {r['chunk_id']:<40} {r['title'][:60]}")
        return

    r = embed_all(reset=args.reset)
    print(
        f"[OK] embed_kb upsert: loaded={r['loaded']} "
        f"by_kb={r['by_kb']} total_in_collection={r.get('total_in_collection')}"
    )


if __name__ == "__main__":
    main()
