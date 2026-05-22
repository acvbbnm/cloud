"""Layer 3 — AISherpa.

설계서 5.4.5절 + UC-05~07 시퀀스.
4가지 역할:
  - brief(caseId, eventId)        : ATT&CK 컨텍스트 브리핑 (우선)
  - chat(query, history)          : 자연어 질의 (우선)
  - suggest_missing_link(...)     : 빠진 고리 후보 (후순위)
  - recommend_playbook(chain)     : 플레이북 추천 (후순위)

핵심 원칙: AI 는 판단하지 않고 검색·요약·제안만 수행한다. 모든 응답에 출처 첨부.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.sherpa.chat_session import ChatSession, Message
from core.sherpa.knowledge_base import KBChunk
from core.sherpa.llm_engine import LLMEngine
from core.sherpa.rag_retriever import RAGRetriever
from db.models import AttackEventModel, IncidentCaseModel, OCSFEventModel, RawEventModel


def _source_dict(chunk: KBChunk) -> dict:
    """KBChunk → API 응답 sources 항목."""
    return {
        "source_id": chunk.chunk_id,
        "type": chunk.kb_name,
        "title": chunk.title,
        "url": chunk.url,
    }


class AISherpa:
    """AI 셰르파 — 4가지 모드."""

    # ── brief ──
    @classmethod
    def brief(cls, db: Session, case_id: str, event_id: Optional[str] = None) -> dict:
        """ATT&CK 컨텍스트 브리핑.

        event_id 가 ATT&CK event_id (`attack_id`) 이면 그 기법 기준,
        없으면 케이스의 최상위 위험도 attack_event 자동 선택.
        """
        attack_row = None
        if event_id:
            attack_row = db.execute(
                select(AttackEventModel).where(AttackEventModel.attack_id == event_id)
            ).scalar_one_or_none()

        if attack_row is None:
            # 케이스 내 최신 매핑된 attack 선택 (위험도 정렬 제거 — 산출 근거 부재)
            attack_row = db.execute(
                select(AttackEventModel)
                .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
                .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
                .where(RawEventModel.case_id == case_id)
                .order_by(AttackEventModel.mapped_at.desc())
                .limit(1)
            ).scalar_one_or_none()

        if attack_row is None:
            return {
                "technique_id": None,
                "technique_name": None,
                "tactic": None,
                "briefing": (
                    "이 케이스에서 ATT&CK 매핑된 이벤트가 없습니다. 먼저 V-3 에서 정규화, "
                    "V-4 에서 ATT&CK 매핑을 실행하세요."
                ),
                "sources": [],
                "relatedTechniques": [],
                "confidence": "low",
            }

        # KB 검색 — HIGH 3 (2026-05-21): case 의 incident_type·csp 도 전달하여
        # CASE_DB / PLAYBOOK 청크도 검색 (진규 E2E §4.5 fix).
        case_obj = db.execute(
            select(IncidentCaseModel).where(IncidentCaseModel.case_id == case_id)
        ).scalar_one_or_none()
        incident_type = case_obj.incident_type if case_obj else None
        csp = case_obj.csp if case_obj else None
        scored = RAGRetriever.retrieve_by_technique(
            attack_row.technique_id, k=3, incident_type=incident_type, csp=csp,
        )
        sources = [_source_dict(c) for c, _ in scored]
        related = sorted(
            {c.meta.get("technique_id") for c, _ in scored if c.meta.get("technique_id")}
        )

        ctx_chunks = [c for c, _ in scored]
        primary = ctx_chunks[0] if ctx_chunks else None
        primary_text = primary.text.strip() if primary else ""
        if len(primary_text) > 400:
            primary_text = primary_text[:397] + "…"

        # 기법명 결정 우선순위 (Phase 2.4):
        #   1) ATTACK KB 청크 중 technique_id 정확 매칭한 청크의 title
        #   2) attack_rules.json 의 룰 description (rule_id 매칭)
        #   3) attack_row.technique_id (raw)
        technique_name = attack_row.technique_id  # fallback
        exact_chunk = next(
            (c for c in ctx_chunks if c.meta.get("technique_id") == attack_row.technique_id),
            None,
        )
        if exact_chunk:
            technique_name = exact_chunk.title
        else:
            from core.analysis.attack_mapper import get_rule_technique_name

            rule_desc = get_rule_technique_name(attack_row.rule_id)
            if rule_desc:
                technique_name = rule_desc
            elif primary:
                technique_name = primary.title

        briefing = (
            f"매핑된 기법: **{attack_row.technique_id}** {technique_name} ({attack_row.tactic}). "
            f"룰 {attack_row.rule_id}.\n\n"
            f"{primary_text}\n\n"
            f"※ 본 브리핑은 결정론적 KB 검색 결과입니다. 출처 {len(sources)}건 첨부."
        )

        return {
            "technique_id": attack_row.technique_id,
            "technique_name": technique_name,
            "tactic": attack_row.tactic,
            "briefing": briefing,
            "sources": sources,
            "relatedTechniques": [t for t in related if t != attack_row.technique_id],
            "confidence": "medium" if len(scored) > 0 else "low",
        }

    # ── chat ──
    @classmethod
    def chat(
        cls,
        case_id: Optional[str],
        session_id: Optional[str],
        query: str,
        history: Optional[list[dict]] = None,
    ) -> dict:
        """자연어 질의 — RAG 검색 + LLM 응답 + 세션 누적.

        세션 정책 (설계서 5.1절 정합):
          - session_id 가 있고 서버 메모리에 존재하면: 그 세션을 이어 사용 (stateful)
          - 그 외에는 신규 세션을 만들고, history 가 주어졌으면 미리 채워넣는다
            (클라이언트 stateless 흐름 지원 — 클라이언트가 매 요청 history 배열을
            전달하면 서버는 그 위에 추가만 한다)
        """
        sess = ChatSession.get_or_create(session_id, case_id)

        # 신규 세션이고 history 가 들어왔으면 미리 채움 (멱등 보장 위해 빈 세션에만)
        if history and not sess.messages:
            for h in history:
                role = h.get("role")
                content = h.get("content")
                if role in ("user", "assistant") and isinstance(content, str):
                    ChatSession.append(sess.session_id, role, content)

        ChatSession.append(sess.session_id, "user", query)

        scored = RAGRetriever.retrieve(query, k=3)
        context_chunks = [c for c, _ in scored]
        response_text = LLMEngine.generate(prompt=query, context=context_chunks)
        ChatSession.append(sess.session_id, "assistant", response_text)

        return {
            "sessionId": sess.session_id,
            "response": response_text,
            "sources": [_source_dict(c) for c in context_chunks],
        }

    # ── chat (stream) — Phase 2.3 ────────────────────────────
    @classmethod
    def chat_stream(
        cls,
        case_id: Optional[str],
        session_id: Optional[str],
        query: str,
        history: Optional[list[dict]] = None,
    ):
        """자연어 질의 스트리밍 — 토큰 단위 ndjson yield.

        프로토콜 (ndjson — 각 라인이 JSON object):
          1) {"type":"start","sessionId":"...","sources":[...]}   — 첫 라인
          2) {"type":"delta","content":"..."}                       — 토큰 0..N건
          3) {"type":"done"}                                        — 종료 마커

        세션 정책은 chat() 과 동일. 모든 토큰이 끝난 후 ChatSession 에 누적 저장.
        """
        sess = ChatSession.get_or_create(session_id, case_id)
        if history and not sess.messages:
            for h in history:
                role = h.get("role")
                content = h.get("content")
                if role in ("user", "assistant") and isinstance(content, str):
                    ChatSession.append(sess.session_id, role, content)
        ChatSession.append(sess.session_id, "user", query)

        scored = RAGRetriever.retrieve(query, k=3)
        context_chunks = [c for c, _ in scored]

        # 첫 라인: 세션 ID + sources (출처는 RAG 단계에서 즉시 알 수 있음)
        import json as _json
        yield _json.dumps({
            "type": "start",
            "sessionId": sess.session_id,
            "sources": [_source_dict(c) for c in context_chunks],
        }, ensure_ascii=False) + "\n"

        # 토큰 스트림
        full_text_parts: list[str] = []
        for delta in LLMEngine.generate_stream(prompt=query, context=context_chunks):
            if not delta:
                continue
            full_text_parts.append(delta)
            yield _json.dumps(
                {"type": "delta", "content": delta},
                ensure_ascii=False,
            ) + "\n"

        # 종료 마커 + ChatSession 누적 저장 (assistant 한 번에)
        ChatSession.append(sess.session_id, "assistant", "".join(full_text_parts))
        yield _json.dumps({"type": "done"}, ensure_ascii=False) + "\n"

    # ── suggest (후순위 깡통) ──
    @classmethod
    def suggest_missing_link(
        cls, db: Session, case_id: str, node_a: str, node_b: str
    ) -> dict:
        """nodeA → nodeB 사이에 끼워넣을 후보 ATT&CK 기법.

        깡통 구현: case 내 attack_events 중 nodeA·nodeB 의 기법 ID 와 다른 기법을
        최신 매핑 순으로 추천. 진짜 추론은 향후 LLM 으로.
        """
        rows = list(
            db.execute(
                select(AttackEventModel)
                .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
                .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
                .where(RawEventModel.case_id == case_id)
                .order_by(AttackEventModel.mapped_at.desc())
                .limit(20)
            ).scalars()
        )
        node_a_tech = next((r.technique_id for r in rows if r.attack_id == node_a), None)
        node_b_tech = next((r.technique_id for r in rows if r.attack_id == node_b), None)
        seen = {node_a_tech, node_b_tech, None}

        suggestions = []
        for r in rows:
            if r.technique_id in seen:
                continue
            seen.add(r.technique_id)
            chunks = RAGRetriever.retrieve_by_technique(r.technique_id, k=1)
            ctitle = chunks[0][0].title if chunks else r.technique_id
            suggestions.append(
                {
                    "technique_id": r.technique_id,
                    "technique_name": ctitle,
                    "tactic": r.tactic,
                    "reason": f"케이스에 존재하는 {r.tactic} 기법으로, nodeA·B 사이 흐름 보완 후보.",
                    "candidateEvents": [r.attack_id],
                    "confidence": "low",
                    "sources": [_source_dict(c) for c, _ in chunks],
                }
            )
            if len(suggestions) >= 3:
                break

        return {"suggestions": suggestions}

    # ── playbook (후순위 깡통) ──
    @classmethod
    def recommend_playbook(cls, chain: list[str]) -> dict:
        """기법 chain 에 해당하는 플레이북 KB 검색."""
        if not chain:
            return {"playbooks": []}

        # chain 의 모든 기법을 합쳐서 키워드 검색 (PLAYBOOK 카테고리만)
        query = " ".join(chain)
        scored = RAGRetriever.retrieve(query, k=3, kb_filter=["PLAYBOOK"])

        playbooks = []
        for c, _ in scored:
            steps = [s.strip() for s in c.text.split("\n") if s.strip()]
            playbooks.append(
                {
                    "playbook_id": c.chunk_id,
                    "title": c.title,
                    "steps": steps[:10],
                    "tactics_addressed": c.meta.get("tactics_addressed", []),
                    "sources": [_source_dict(c)],
                }
            )

        return {"playbooks": playbooks}

    # ── KB 인덱스 노출용 ──
    @classmethod
    def history(cls, session_id: str) -> list[Message]:
        return ChatSession.history(session_id)
