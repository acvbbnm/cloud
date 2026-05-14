"""Layer 3 — KnowledgeBase 로더.

data/kb/{attack,playbook,csp_doc,case_db}.json 의 청크를 통일된 형식(KBChunk)으로
변환·캐시한다. ChromaDB 임베딩 없이도 RAG 인터페이스가 동작하도록 추상화.

추후 ChromaDB로 교체할 때 KBChunk 형식만 유지하면 retriever 만 갈아끼우면 된다.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config import settings


@dataclass
class KBChunk:
    """KB 청크 통일 형식."""

    chunk_id: str
    kb_name: str  # ATTACK / PLAYBOOK / CSP_DOC / CASE_DB
    title: str
    text: str
    source: str
    url: Optional[str] = None
    meta: dict = field(default_factory=dict)


_CACHE: Optional[list[KBChunk]] = None


def _convert_attack(raw: dict) -> list[KBChunk]:
    """attack.json (KB-1) → KBChunk."""
    out = []
    for c in raw.get("chunks", []):
        out.append(
            KBChunk(
                chunk_id=c["chunk_id"],
                kb_name="ATTACK",
                title=c.get("title", ""),
                text=c.get("text", ""),
                source=c.get("source", ""),
                url=c.get("url"),
                meta={
                    "technique_id": c.get("technique_id"),
                    "tactic": c.get("tactic"),
                },
            )
        )
    return out


def _convert_playbook(raw: dict) -> list[KBChunk]:
    out = []
    for c in raw.get("chunks", []):
        out.append(
            KBChunk(
                chunk_id=c["chunk_id"],
                kb_name="PLAYBOOK",
                title=c.get("title", ""),
                text=c.get("text", ""),
                source=c.get("source", ""),
                url=None,
                meta={
                    "incident_type": c.get("incident_type"),
                    "tactics_addressed": c.get("tactics_addressed", []),
                },
            )
        )
    return out


def _convert_csp_doc(raw: dict) -> list[KBChunk]:
    out = []
    for c in raw.get("chunks", []):
        out.append(
            KBChunk(
                chunk_id=c["chunk_id"],
                kb_name="CSP_DOC",
                title=c.get("title", ""),
                text=c.get("text", ""),
                source=c.get("source", ""),
                url=c.get("url"),
                meta={"csp": c.get("csp"), "service": c.get("service")},
            )
        )
    return out


def _convert_case_db(raw: dict) -> list[KBChunk]:
    """case_db.json — 사례 데이터. timeline 등은 text 로 합쳐서 풀어준다."""
    out = []
    for c in raw.get("chunks", []):
        text_parts = []
        if "text" in c:
            text_parts.append(c["text"])
        # 타임라인이 있는 경우 텍스트화
        if "timeline" in c:
            tl = "\n".join(
                f"  - {e.get('time', '?')} {e.get('action', e.get('eventId', '?'))}"
                f" (ip={e.get('ip', '?')}, tactic={e.get('tactic', '?')})"
                for e in c["timeline"]
            )
            text_parts.append(f"타임라인:\n{tl}")
        if "lessons_learned" in c:
            text_parts.append(f"교훈: {c['lessons_learned']}")
        if "evidence" in c:
            text_parts.append("주요 증거:\n" + "\n".join(f"  - {e}" for e in c["evidence"]))

        out.append(
            KBChunk(
                chunk_id=c["chunk_id"],
                kb_name="CASE_DB",
                title=c.get("title", ""),
                text="\n\n".join(text_parts),
                source=c.get("source", ""),
                url=None,
                meta={
                    "incident_type": c.get("incident_type"),
                    "csp": c.get("csp"),
                    "actor": c.get("actor"),
                    "time_window": c.get("time_window"),
                },
            )
        )
    return out


_LOADERS = [
    ("attack.json", _convert_attack),
    ("playbook.json", _convert_playbook),
    ("csp_doc.json", _convert_csp_doc),
    ("case_db.json", _convert_case_db),
]


def load_all() -> list[KBChunk]:
    """모든 KB 청크 로드 (startup 1회 캐시)."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    chunks: list[KBChunk] = []
    kb_dir: Path = settings.KB_DIR
    for fname, converter in _LOADERS:
        path = kb_dir / fname
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        chunks.extend(converter(raw))
    _CACHE = chunks
    return _CACHE


def stats() -> dict:
    """KB 인덱스 통계 (V8 화면 표시용)."""
    chunks = load_all()
    counts: dict[str, int] = {}
    for c in chunks:
        counts[c.kb_name] = counts.get(c.kb_name, 0) + 1
    return {"total": len(chunks), "byKb": counts}
