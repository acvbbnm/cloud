"""Layer 3 — AI Sherpa API 라우터.

설계서 5.6.4절 + API_계약서 Layer 3 섹션.
- POST /api/sherpa/brief    — 컨텍스트 브리핑 (우선)
- POST /api/sherpa/chat     — 자연어 질의 (우선)
- POST /api/sherpa/suggest  — 빠진 고리 후보 (후순위)
- POST /api/sherpa/playbook — 플레이북 추천 (후순위)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.intake.incident_case import IncidentCase
from core.intake.knowledge import IncidentTypeKnowledge
from core.sherpa.ai_sherpa import AISherpa
from core.sherpa.knowledge_base import stats as kb_stats
from core.sherpa.llm_engine import LLMEngine
from core.sherpa.rag_retriever import RAGRetriever
from db.models import AttackEventModel, OCSFEventModel, RawEventModel
from db.session import get_db

router = APIRouter(prefix="/api/sherpa", tags=["sherpa"])


# ── 공통 에러 헬퍼 (intake/board/report.py 와 동일 패턴) ──


def _case_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "status": "error",
            "message": "케이스를 찾을 수 없습니다",
            "code": "CASE_NOT_FOUND",
        },
    )


# ── 요청 스키마 ────────────────────────────────────────────


class BriefRequest(BaseModel):
    caseId: str
    eventId: Optional[str] = None  # attack_id (선택)


class ChatHistoryItem(BaseModel):
    role: str  # 'user' / 'assistant'
    content: str


class ChatRequest(BaseModel):
    caseId: Optional[str] = None
    sessionId: Optional[str] = None
    query: str
    history: Optional[list[ChatHistoryItem]] = None


class SuggestRequest(BaseModel):
    caseId: str
    nodeA: str
    nodeB: str


class PlaybookRequest(BaseModel):
    caseId: Optional[str] = None
    chain: list[str]


# ── 엔드포인트 ────────────────────────────────────────────


@router.post("/brief")
async def post_brief(req: BriefRequest, db: Session = Depends(get_db)) -> dict:
    """ATT&CK 컨텍스트 브리핑.

    eventId(attack_id) 미지정 시 case 내 최상위 위험도 attack 자동 선택.
    case 미존재 시 HTTP 404.
    """
    case = IncidentCase.get_by_id(db, req.caseId)
    if case is None:
        raise _case_not_found()
    data = AISherpa.brief(db, req.caseId, req.eventId)
    return {"status": "ok", "data": data}


@router.post("/chat")
async def post_chat(req: ChatRequest, db: Session = Depends(get_db)) -> dict:
    """자연어 질의 — RAG 검색 + 응답.

    sessionId 가 주어지면 서버 인메모리 세션을 이어 사용 (stateful).
    sessionId 가 없고 history 가 주어지면 stateless 클라이언트로 간주하여
    history 를 신규 세션에 미리 채우고 그 위에 query 를 더한다 (설계서 5.1절 정합).

    caseId 가 주어지면 존재 여부를 검증하고, 없으면 HTTP 404.
    """
    if req.caseId:
        case = IncidentCase.get_by_id(db, req.caseId)
        if case is None:
            raise _case_not_found()

    history = [h.model_dump() for h in (req.history or [])]
    data = AISherpa.chat(
        case_id=req.caseId,
        session_id=req.sessionId,
        query=req.query,
        history=history,
    )
    return {"status": "ok", "data": data}


@router.post("/chat/stream")
async def post_chat_stream(req: ChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """자연어 질의 스트리밍 (Phase 2.3, 2026-05-18).

    ndjson 응답 — 각 라인이 JSON object:
      {"type":"start","sessionId":"...","sources":[...]}    첫 라인
      {"type":"delta","content":"..."}                       토큰 0..N건
      {"type":"done"}                                        종료

    UX: 100초 대기 → 첫 토큰까지 ~5초 + 점진 표시. 사용자 체감 응답시간 1/3.
    인증·case 검증은 동기 chat 과 동일.
    """
    if req.caseId:
        case = IncidentCase.get_by_id(db, req.caseId)
        if case is None:
            raise _case_not_found()

    history = [h.model_dump() for h in (req.history or [])]
    gen = AISherpa.chat_stream(
        case_id=req.caseId,
        session_id=req.sessionId,
        query=req.query,
        history=history,
    )
    return StreamingResponse(
        gen,
        media_type="application/x-ndjson",
        # 프록시·브라우저 버퍼링 방지
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/suggest")
async def post_suggest(req: SuggestRequest, db: Session = Depends(get_db)) -> dict:
    """빠진 고리 후보 (후순위 깡통)."""
    case = IncidentCase.get_by_id(db, req.caseId)
    if case is None:
        raise _case_not_found()
    data = AISherpa.suggest_missing_link(db, req.caseId, req.nodeA, req.nodeB)
    return {"status": "ok", "data": data}


@router.post("/playbook")
async def post_playbook(req: PlaybookRequest, db: Session = Depends(get_db)) -> dict:
    """공격 체인에 대한 플레이북 추천 (후순위 깡통)."""
    if req.caseId:
        case = IncidentCase.get_by_id(db, req.caseId)
        if case is None:
            raise _case_not_found()
    data = AISherpa.recommend_playbook(req.chain)
    return {"status": "ok", "data": data}


@router.get("/kb")
async def get_kb_stats() -> dict:
    """KB 인덱스 통계 + LLM/RAG 엔진 상태 (V8 우측 패널)."""
    return {
        "status": "ok",
        "data": {
            **kb_stats(),
            "engine": LLMEngine.health(),
            "rag": RAGRetriever.backend_info(),
        },
    }


# ── V-8 정합성 평가 — 청사진 §6.3 (2026-05-18) ──────────────────


def _normalize_technique(technique_id: str) -> str:
    """T1078.004 → T1078 (sub-technique 제거하여 매칭률 향상)."""
    return technique_id.split(".")[0] if technique_id else technique_id


def _score_incident_type(
    expected: list[str],
    observed_set: set[str],
) -> tuple[int, int, list[str]]:
    """주어진 expected 기법 목록 중 observed 에 포함된 갯수.

    Returns: (matched_count, expected_count, missing_list).
    sub-technique 일치도 정규화하여 비교.
    """
    if not expected:
        return 0, 0, []
    norm_expected = {_normalize_technique(t) for t in expected}
    matched = norm_expected & {_normalize_technique(t) for t in observed_set}
    missing = sorted(norm_expected - matched)
    return len(matched), len(norm_expected), missing


@router.get("/validate-incident-type")
async def validate_incident_type(
    caseId: str,
    db: Session = Depends(get_db),
) -> dict:
    """V-3 매핑 결과 vs case.incident_type 정합성 평가.

    동작:
      1. case 의 attack_events 에서 고유 technique_id 집합 추출
      2. 현재 incident_type 의 related_techniques 와 비교 → matched/expected/missing
      3. 다른 모든 incident_type 도 동일 점수화하여 candidate_types 후보 목록 생성
      4. UNCLASSIFIED 이거나, 더 높은 점수의 후보가 있으면 REVIEW_NEEDED

    응답:
      {
        status: 'CONSISTENT' | 'REVIEW_NEEDED',
        current_incident_type, current_match, current_expected, missing,
        observed_techniques: [...],
        extra_techniques: [...],   # 관측 됐지만 현재 type 에 없는 기법
        candidate_types: [{type, matched, expected, score_ratio, reason}, ...],
        message
      }
    """
    case = IncidentCase.get_by_id(db, caseId)
    if case is None:
        raise _case_not_found()

    # 1) 케이스의 관측 기법 집합 (attack_events join raw_events)
    stmt = (
        select(AttackEventModel.technique_id)
        .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
        .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
        .where(RawEventModel.case_id == caseId)
    )
    observed: list[str] = [row[0] for row in db.execute(stmt).all() if row[0]]
    observed_set = set(observed)
    observed_norm_set = {_normalize_technique(t) for t in observed_set}

    # 2) 현재 type 점수
    current_type = case.incident_type
    current_knowledge = IncidentTypeKnowledge.lookup(current_type) or {}
    current_expected = current_knowledge.get("related_techniques") or []
    cur_matched, cur_total, cur_missing = _score_incident_type(
        current_expected, observed_set
    )
    # dev3 (2026-05-20): current 의 score_ratio 도 계산 — REVIEW_NEEDED 판정에서
    # 후보의 ratio 와 비교하기 위해 (matched 동률 시 ratio 더 좋은 후보가 더 적합).
    current_ratio = round(cur_matched / cur_total, 4) if cur_total else 0.0
    extra_techniques = sorted(
        observed_norm_set - {_normalize_technique(t) for t in current_expected}
    )

    # 3) 모든 후보 점수화 (dev3 C-1: MULTI_CSP_LATERAL 제거, 4종 신규 추가 — 총 8 후보)
    candidates: list[dict] = []
    for other_type, k in [
        ("CREDENTIAL_THEFT", IncidentTypeKnowledge.lookup("CREDENTIAL_THEFT")),
        ("PRIVILEGE_ESCALATION", IncidentTypeKnowledge.lookup("PRIVILEGE_ESCALATION")),
        ("DATA_EXFILTRATION", IncidentTypeKnowledge.lookup("DATA_EXFILTRATION")),
        ("AUDIT_LOG_TAMPERING", IncidentTypeKnowledge.lookup("AUDIT_LOG_TAMPERING")),
        ("RANSOMWARE", IncidentTypeKnowledge.lookup("RANSOMWARE")),
        ("MISCONFIG_EXPOSURE", IncidentTypeKnowledge.lookup("MISCONFIG_EXPOSURE")),
        ("PHISH_INITIAL_ACCESS", IncidentTypeKnowledge.lookup("PHISH_INITIAL_ACCESS")),
        ("INSIDER_THREAT", IncidentTypeKnowledge.lookup("INSIDER_THREAT")),
    ]:
        if k is None:
            continue
        expected_list = k.get("related_techniques") or []
        m, e, miss = _score_incident_type(expected_list, observed_set)
        ratio = round(m / e, 4) if e else 0.0
        reason_parts: list[str] = []
        if m > 0:
            reason_parts.append(f"{m}/{e} 기법 관측 (matched={m})")
        if miss:
            reason_parts.append(f"누락 {len(miss)}건: {', '.join(miss[:3])}{'…' if len(miss)>3 else ''}")
        candidates.append({
            "type": other_type,
            "matched": m,
            "expected": e,
            "score_ratio": ratio,
            "reason": " · ".join(reason_parts) or "관측 없음",
        })
    candidates.sort(key=lambda c: c["score_ratio"], reverse=True)

    # 4) 정합성 판정
    top = candidates[0] if candidates else None
    status_val = "CONSISTENT"
    message_parts: list[str] = []

    if current_type == "UNCLASSIFIED":
        status_val = "REVIEW_NEEDED"
        message_parts.append("사고유형 미확정 — 가장 가능성 높은 후보를 검토하세요.")
    elif (
        top
        and top["type"] != current_type
        and top["score_ratio"] > 0
        and (
            top["matched"] > cur_matched
            # dev3 (2026-05-20): matched 동률이라도 ratio 가 더 좋으면 REVIEW_NEEDED.
            # 기존 조건 `top["matched"] > cur_matched` 단독은 1=1 동률 시 CONSISTENT
            # 잘못 반환 (E2E 시나리오 5 회귀). 학술 정합 — 후보가 더 적은 expected
            # 기법 중 같은 수를 매치하면 비율로는 더 적합.
            or (top["matched"] == cur_matched and top["score_ratio"] > current_ratio)
        )
    ):
        status_val = "REVIEW_NEEDED"
        message_parts.append(
            f"현재 {current_type} 매칭 {cur_matched}/{cur_total} ({current_ratio:.0%}) 보다 "
            f"{top['type']} 매칭 {top['matched']}/{top['expected']} ({top['score_ratio']:.0%}) 이 더 적합합니다."
        )
    elif cur_total > 0 and cur_matched == 0 and observed:
        status_val = "REVIEW_NEEDED"
        message_parts.append(
            f"현재 {current_type} 의 기대 기법이 하나도 관측되지 않았습니다."
        )
    else:
        message_parts.append(
            f"{current_type} 매칭 {cur_matched}/{cur_total} — 정합성 양호."
        )

    if extra_techniques:
        message_parts.append(
            f"추가 관측 기법: {', '.join(extra_techniques[:5])}"
            + ("…" if len(extra_techniques) > 5 else "")
        )

    # HIGH 3 후속 (2026-05-21): E2E 스크립트 호환용 verdict 필드 추가.
    # 최상위 후보 type — REVIEW_NEEDED 또는 CONSISTENT 모두에서 가장 유력 사고유형.
    verdict = candidates[0]["type"] if candidates and candidates[0].get("score_ratio", 0) > 0 else current_type

    return {
        "status": "ok",
        "data": {
            "caseId": caseId,
            "status": status_val,
            "verdict": verdict,
            "current_incident_type": current_type,
            "current_match": cur_matched,
            "current_expected": cur_total,
            "current_missing": cur_missing,
            "observed_techniques": sorted(observed_set),
            "observed_count": len(observed),
            "extra_techniques": extra_techniques,
            "candidate_types": candidates,
            "message": " ".join(message_parts),
        },
    }
