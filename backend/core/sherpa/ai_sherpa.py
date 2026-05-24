"""Layer 3 — AISherpa.

설계서 5.4.5절 + UC-05~07 시퀀스.
4가지 역할:
  - brief(caseId, eventId)        : ATT&CK 컨텍스트 브리핑 (우선)
  - chat(query, history)          : 자연어 질의 (우선)
  - suggest_missing_link(...)     : 빠진 고리 후보 (후순위)
  - recommend_playbook(chain)     : 플레이북 추천 (후순위)

핵심 원칙: AI 는 판단하지 않고 검색·요약·제안만 수행한다. 모든 응답에 출처 첨부.
"""
import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from core.intake.knowledge import IncidentTypeKnowledge
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


# ── 빠진 고리 추론용 정적 데이터 (suggest_missing_link) ──────────────
#
# MITRE ATT&CK Enterprise kill-chain 전술 순서. 두 노드의 전술 단계 인덱스
# 사이가 "비어 있는 단계" = 빠진 고리 후보 공간. 정적 표준이라 결정성 100%.
_TACTIC_ORDER = [
    "Reconnaissance",
    "Resource Development",
    "Initial Access",
    "Execution",
    "Persistence",
    "Privilege Escalation",
    "Defense Evasion",
    "Credential Access",
    "Discovery",
    "Lateral Movement",
    "Collection",
    "Command and Control",
    "Exfiltration",
    "Impact",
]

_rules_cache: dict[str, str] = {}


def _technique_tactic_index() -> dict[str, str]:
    """`attack_rules/rules.json` → {technique_id: tactic}.

    NCP/NHN 매처 룰이 존재하는 기법만 — 즉 우리 시스템이 raw 로그에서 실제로
    검출·검증 가능한 기법만 후보가 된다 (실행 가능한 제안 보장).
    """
    if _rules_cache:
        return _rules_cache
    path = settings.DATA_DIR / "attack_rules" / "rules.json"
    if not path.exists():
        return _rules_cache
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    rules = doc.get("rules", doc) if isinstance(doc, dict) else doc
    for r in rules:
        tech = r.get("technique_id")
        tactic = r.get("tactic")
        if tech and tactic and tech not in _rules_cache:
            _rules_cache[tech] = tactic
    return _rules_cache


def _tactic_index(tactic: Optional[str]) -> Optional[int]:
    """전술명 → kill-chain 순서 인덱스. 미상·미지원 전술이면 None."""
    if not tactic:
        return None
    try:
        return _TACTIC_ORDER.index(tactic)
    except ValueError:
        return None


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
        """nodeA → nodeB 사이 빠진 고리(ATT&CK 기법) 후보 — 결정론적 추론.

        Kill-chain 전술 순서로 두 노드 사이 '비어 있는 단계'를 계산하고, 그
        단계에 속하면서 케이스에 아직 매핑되지 않은 기법을 후보로 제시한다.

        AI 판단 없음 — 정적 데이터만 사용 (CLAUDE.md 정합):
          - `_TACTIC_ORDER`        : MITRE ATT&CK kill-chain 전술 순서
          - `attack_rules/rules.json` : 기법↔전술 (NCP/NHN 검출 가능 기법)
          - `IncidentTypeKnowledge`   : 사고유형별 대표 기법·전술 (신뢰도 등급)
        모든 후보에 KB 출처 첨부. 채택 여부는 수사관이 결정.
        """
        rows = list(
            db.execute(
                select(AttackEventModel)
                .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
                .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
                .where(RawEventModel.case_id == case_id)
                .order_by(AttackEventModel.mapped_at.desc())
            ).scalars()
        )
        by_attack_id = {r.attack_id: r for r in rows}
        a = by_attack_id.get(node_a)
        b = by_attack_id.get(node_b)
        if a is None or b is None:
            return {
                "suggestions": [],
                "message": "노드 A 또는 B 를 케이스 attack_events 에서 찾을 수 없습니다.",
            }

        idx_a = _tactic_index(a.tactic)
        idx_b = _tactic_index(b.tactic)
        if idx_a is None or idx_b is None:
            return {
                "suggestions": [],
                "message": f"전술 단계를 판정할 수 없습니다 (A={a.tactic}, B={b.tactic}).",
            }

        lo, hi = sorted([idx_a, idx_b])
        missing_tactics = _TACTIC_ORDER[lo + 1 : hi]
        if not missing_tactics:
            return {
                "suggestions": [],
                "missing_tactics": [],
                "message": "두 노드가 인접·동일 전술 단계 — 사이 빠진 고리 없음.",
            }

        # 케이스에 이미 매핑된 기법 — 중복 제안 방지
        present = {r.technique_id for r in rows}

        # 사고유형 도메인 지식 — 신뢰도 등급 산출용
        case_obj = db.execute(
            select(IncidentCaseModel).where(IncidentCaseModel.case_id == case_id)
        ).scalar_one_or_none()
        incident_type = case_obj.incident_type if case_obj else None
        knowledge = (
            IncidentTypeKnowledge.lookup(incident_type) if incident_type else None
        )
        related = set(knowledge.get("related_techniques", [])) if knowledge else set()
        type_tactics = set(knowledge.get("tactics", [])) if knowledge else set()

        # 빈 단계별 후보 기법 수집
        tech_tac = _technique_tactic_index()
        suggestions: list[dict] = []
        for missing in missing_tactics:
            for tech, tac in sorted(tech_tac.items()):
                if tac != missing or tech in present:
                    continue
                # 신뢰도 — 정적 룰 (높을수록 사고유형 정합)
                if tech in related:
                    confidence = "high"
                    note = f"{incident_type} 유형의 대표 기법 — 확인 우선순위 높음."
                elif tac in type_tactics:
                    confidence = "medium"
                    note = f"{incident_type} 유형에서 관측되는 전술 단계."
                else:
                    confidence = "low"
                    note = "공격 체인 구조상 누락 가능 단계."
                # KB 출처 — 해당 기법의 ATTACK 청크를 정확히 매칭한 것만 사용.
                # 매칭 청크가 없으면 잘못된 제목 차용을 막기 위해 technique_id 를
                # 그대로 기법명으로 쓰고 출처는 비운다 (KB 미수록 기법).
                scored = RAGRetriever.retrieve_by_technique(tech, k=3)
                exact = next(
                    (
                        c
                        for c, _ in scored
                        if c.kb_name == "ATTACK"
                        and c.meta.get("technique_id") == tech
                    ),
                    None,
                )
                suggestions.append(
                    {
                        "technique_id": tech,
                        "technique_name": exact.title if exact else tech,
                        "tactic": tac,
                        "reason": (
                            f"노드 A({a.technique_id}·{a.tactic})와 "
                            f"노드 B({b.technique_id}·{b.tactic}) 사이 "
                            f"'{missing}' 단계가 비어 있습니다. {note}"
                        ),
                        "candidateEvents": [],
                        "confidence": confidence,
                        "sources": [_source_dict(exact)] if exact else [],
                    }
                )

        # 신뢰도 high > medium > low 정렬, 상위 5건
        rank = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: rank[s["confidence"]])
        return {
            "suggestions": suggestions[:5],
            "missing_tactics": missing_tactics,
            "message": (
                f"{a.tactic} → {b.tactic} 사이 {len(missing_tactics)}개 전술 단계 "
                f"점검 권장 — 후보 {min(len(suggestions), 5)}건."
            ),
        }

    # ── playbook (RAG + LLM 결합, 2026-05-24 마지막 깡통 해소) ──
    @classmethod
    def recommend_playbook(cls, chain: list[str]) -> dict:
        """기법 chain 에 해당하는 플레이북 RAG 검색 + LLM 맥락화 요약.

        흐름:
          1. chain (technique_id 리스트) → PLAYBOOK KB 청크 RAG 검색 (k=3)
          2. 각 청크에서 기본 steps 추출 (KB 원본)
          3. LLM 호출로 chain 컨텍스트에 맞춰 우선순위·요약 추가
             (기존 KB 검색 결과를 컨텍스트로 주입, AI 가 정렬·요약만 — 판단 X)
          4. summary 필드를 응답에 첨부 (KB 출처 인용 + 수사관 판단 문구 포함)

        결정성: KB 검색은 결정성 100%. LLM 요약은 매번 다를 수 있어 출처 칩으로 검증 가능.
        Fallback: LLM 호출 실패 시 summary 없이 KB 청크만 반환 (안전).
        """
        if not chain:
            return {"playbooks": [], "summary": None}

        query = " ".join(chain)
        scored = RAGRetriever.retrieve(query, k=3, kb_filter=["PLAYBOOK"])

        playbooks: list[dict] = []
        kb_chunks_for_llm = []
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
            kb_chunks_for_llm.append(c)

        # LLM 맥락화 요약 — 사용자가 보고 있는 attack chain 에 맞춰
        # 플레이북 우선순위·핵심 단계를 정리. KB 청크만 컨텍스트로 사용.
        summary: Optional[str] = None
        sources: list[dict] = []
        if kb_chunks_for_llm:
            chain_str = " → ".join(chain)
            llm_prompt = (
                f"수사관이 발견한 ATT&CK 공격 체인: {chain_str}\n\n"
                f"위 KB 의 플레이북 {len(kb_chunks_for_llm)} 건을 분석해 다음을 해 주세요:\n"
                f"1. 어떤 플레이북이 이 체인에 가장 적합한지 우선순위\n"
                f"2. 즉시 수행해야 할 최우선 3 단계 추출 (출처 [1], [2] 형식 인용)\n"
                f"3. 각 단계의 목적·기대 효과 한 줄"
            )
            try:
                summary = LLMEngine.generate(prompt=llm_prompt, context=kb_chunks_for_llm)
                sources = [_source_dict(c) for c in kb_chunks_for_llm]
            except Exception:
                # LLM 실패 — KB 결과만 반환 (graceful degrade)
                summary = None
                sources = []

        return {
            "playbooks": playbooks,
            "summary": summary,
            "summary_sources": sources,
            "chain": chain,
        }

    # ── KB 인덱스 노출용 ──
    @classmethod
    def history(cls, session_id: str) -> list[Message]:
        return ChatSession.history(session_id)
