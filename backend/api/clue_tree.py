"""Phase B.3 — Evidence Tree REST API (2026-05-25, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §6

엔드포인트:
  POST /api/clue-tree/start    빈 트리 생성 + 초기 후보 5개 (uniform prior 시작)
  POST /api/clue-tree/expand   단서 채택 → 베이즈 갱신 + 다음 후보 (entropy 동적 K)
  POST /api/clue-tree/suggest  현 leaf 후보 재계산 (트리는 그대로)
  GET  /api/clue-tree          현재 트리 상태 조회

응답 공통 형식
-------------
    {"status": "ok", "data": {
        "tree": {...},
        "current_leaf_id": str,
        "posterior_current": {h: prob},
        "confidence": {primary, primary_prob, secondary, gap, confidence_reached,
                       recommended_action, entropy_bits},
        "candidates": [{candidate_id, clue_key, label, expected_info_gain, ...}],
        "path": [...]
    }}
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.intake import bayes_net
from core.intake.info_gain import load_catalog
from core.intake.clue_tree_service import (
    CaseNotFound,
    ClueTreeNotFound,
    advance_stage,
    expand_tree,
    get_tree,
    reset_tree,
    start_tree,
    suggest_candidates,
)
from db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/clue-tree", tags=["intake"])


# ── 공통 에러 ─────────────────────────────────────────────


def _case_not_found(case_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "status": "error",
            "message": f"케이스를 찾을 수 없습니다: {case_id}",
            "code": "CASE_NOT_FOUND",
        },
    )


def _tree_not_started(case_id: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "status": "error",
            "message": f"단서 트리가 시작되지 않음 — /api/clue-tree/start 먼저 호출 ({case_id})",
            "code": "CLUE_TREE_NOT_STARTED",
        },
    )


# ── 요청 스키마 ────────────────────────────────────────────


class CueTreeStartRequest(BaseModel):
    caseId: str


class CueTreeExpandRequest(BaseModel):
    caseId: str
    parent_node_id: str
    clue_key: str
    source: Optional[Literal["tree_candidate", "direct_input", "log_analysis"]] = (
        "tree_candidate"
    )
    # 사용자 입력 값 (예: "203.0.113.5") 을 트리 노드 라벨로 표시 — 가시성 강화
    label_override: Optional[str] = None


class CueTreeSuggestRequest(BaseModel):
    caseId: str


class CueTreeResetRequest(BaseModel):
    caseId: str


class CueTreeAdvanceStageRequest(BaseModel):
    """Phase N.4 — 확정된 사고유형 anchor → 다음 stage 진입 요청."""

    caseId: str
    confirmed_hypothesis: str  # 확정된 사고유형 (8 사고유형 중 1)


# ── 엔드포인트 ─────────────────────────────────────────────


@router.post("/start")
async def start(req: CueTreeStartRequest, db: Session = Depends(get_db)) -> dict:
    """빈 단서 트리 생성. 이미 시작된 경우 기존 트리 반환 (idempotent).

    초기 후보는 entropy 3.0 bits (uniform) → 5개 노출.
    """
    try:
        data = start_tree(db, req.caseId)
    except CaseNotFound:
        raise _case_not_found(req.caseId)
    return {"status": "ok", "data": data}


@router.post("/expand")
async def expand(req: CueTreeExpandRequest, db: Session = Depends(get_db)) -> dict:
    """단서 채택 → 베이즈 갱신 + 다음 후보 자동 생성.

    confidence ≥0.65 + gap ≥0.20 도달 시 confidence.recommended_action 이
    "notify_user_confirm" 으로 반환됨 (자동 종료 X — 사용자 결정 paradigm §16).
    """
    try:
        data = expand_tree(
            db,
            req.caseId,
            parent_node_id=req.parent_node_id,
            clue_key=req.clue_key,
            source=req.source or "tree_candidate",
            label_override=req.label_override,
        )
    except CaseNotFound:
        raise _case_not_found(req.caseId)
    except ClueTreeNotFound:
        raise _tree_not_started(req.caseId)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": str(e),
                "code": "CLUE_TREE_INVALID_EXPAND",
            },
        )
    return {"status": "ok", "data": data}


@router.post("/suggest")
async def suggest(req: CueTreeSuggestRequest, db: Session = Depends(get_db)) -> dict:
    """현 leaf 의 다음 후보 재계산 (트리는 그대로).

    Information Gain 가 다른 단서를 노출하고 싶을 때 사용.
    """
    try:
        data = suggest_candidates(db, req.caseId)
    except CaseNotFound:
        raise _case_not_found(req.caseId)
    except ClueTreeNotFound:
        raise _tree_not_started(req.caseId)
    return {"status": "ok", "data": data}


@router.get("")
async def get(caseId: str = Query(...), db: Session = Depends(get_db)) -> dict:
    """현재 트리 상태 조회 (페이지 새로고침·복귀 시)."""
    try:
        data = get_tree(db, caseId)
    except CaseNotFound:
        raise _case_not_found(caseId)
    except ClueTreeNotFound:
        raise _tree_not_started(caseId)
    return {"status": "ok", "data": data}


@router.post("/reset")
async def reset(req: CueTreeResetRequest, db: Session = Depends(get_db)) -> dict:
    """트리 초기화 — 기존 트리 폐기 후 cold-start 로 새 트리 생성.

    사용자가 잘못된 단서 시퀀스를 시작했거나 처음부터 다시 보고 싶을 때 사용.
    Phase A~F 데이터 모델 변경 (cold-start 정책 도입 등) 시에도 기존 케이스의
    오래된 트리를 초기화하는 용도.
    """
    try:
        data = reset_tree(db, req.caseId)
    except CaseNotFound:
        raise _case_not_found(req.caseId)
    return {"status": "ok", "data": data}


@router.post("/advance-stage")
async def advance_stage_endpoint(
    req: CueTreeAdvanceStageRequest, db: Session = Depends(get_db)
) -> dict:
    """Phase N.4 — 다단계 공격 chain 추적 진입.

    설계서: `docs/evidence_tree_paradigm.md` §23 (Phase N.4)
    학술 정합: MITRE ATT&CK Flow + Mandiant M-Trends 2024 multi-stage chain.

    동작:
      1. tree.confirmed_hypotheses 에 새 가설 추가
      2. stage += 1
      3. posterior_current = STAGE_TRANSITION_MATRIX 의 새 baseline
         (확정 가설 freeze + 연관 가설 가중치 부여)
      4. confidence_reached / recommendation reset
      5. 현 leaf 의 children_candidates 새 baseline 기반 재계산

    사용 시나리오:
      Stage 1: CRED 92% 확정 → advance-stage("CREDENTIAL_THEFT")
      → Stage 2 baseline = {PRIV: 0.30, DATA: 0.20, INSIDER: 0.15, ...}
      → 사용자가 stage 2 단서 누적 → PRIV 확정 → advance-stage("PRIVILEGE_ESCALATION")
      → Stage 3 baseline = {DATA: 0.34, RANSOM: 0.30, AUDIT: 0.17, ...}
      → ...
    """
    try:
        data = advance_stage(db, req.caseId, req.confirmed_hypothesis)
    except CaseNotFound:
        raise _case_not_found(req.caseId)
    except ClueTreeNotFound:
        raise _tree_not_started(req.caseId)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": str(e),
                "code": "CLUE_TREE_INVALID_ADVANCE",
            },
        )
    return {"status": "ok", "data": data}


@router.get("/recon-options")
async def recon_options() -> dict:
    """Phase N.1 — 1차 정찰 단서 옵션 (사고유형 무관 약한 신호).

    설계서: `docs/evidence_tree_paradigm.md` §4.4 (Phase N 신설)
    학술 정합:
      - NIST SP 800-86 §4.1 Initial Triage
      - NIST SP 800-61r2 §3.2 Sources of Precursors and Indicators

    Cold-start 직후 사용자에게 노출. 사고유형 무관 약한 단서 (Q1 inception
    "어떻게 알게 됐나" / Q2A alert_type "어떤 이상이 있었나") 를 그룹별로
    반환. 사용자가 2~4개 선택 → posterior 약 비균등 → 그 후 자체 단서로
    한 쪽 쏠림 차단.

    반환 (`groups[]` 각 그룹 = 정찰 질문 1개):
      {
        "status": "ok",
        "data": {
          "groups": [
            {
              "node_id": "Q1_inception",
              "question": "어떻게 사고를 알게 됐나요?",
              "options": [{clue_key, label, short_label, value, weights}, ...]
            },
            {"node_id": "Q2A_alert_type", ...}
          ]
        }
      }
    """
    # 정찰 카테고리 — 사고유형 무관 약한 신호 (NIST SP 800-86 Initial Triage).
    #
    # V1.fix.8 (2026-05-31, byungwoo) — Q1_inception 제거.
    #   "어떻게 사고를 알게 됐나요?" 는 발견 경로 메타 정보로 사고유형 변별력 0.
    #   V1.fix.4 평탄화 후 IG=0 단서가 됨 → "다음 단서 후보" 자리를 차지하면 안 됨.
    #   사고 인지 경로는 Step 2 basic 탭의 `detection_route` 가 단일 입력점.
    #   카탈로그의 Q1_inception:* entry 자체는 보존 (V-7 보고서 메타 표시용).
    RECON_CATEGORIES = [
        ("Q2A_alert_type", "어떤 이상이 있었나요?"),
    ]

    catalog = load_catalog()
    clues = catalog.get("clues", {})

    groups = []
    for node_id, question in RECON_CATEGORIES:
        # 해당 category 의 단서들 추출 (weight_key prefix 매칭)
        # Q1_inception → "Q1_inception:*" 또는 category="Q1_inception"
        # Q2A_alert_type → "Q2A:*" (weights.json 의 short prefix)
        prefixes = {
            "Q1_inception": ["Q1_inception:"],
            "Q2A_alert_type": ["Q2A:"],
        }.get(node_id, [f"{node_id}:"])

        options = []
        for clue_key, entry in clues.items():
            if not entry.get("has_weights"):
                continue
            if not any(clue_key.startswith(p) for p in prefixes):
                continue
            options.append({
                "clue_key": clue_key,
                "label": entry.get("label", clue_key),
                "short_label": entry.get("short_label", entry.get("label", clue_key)),
                "category": entry.get("category", ""),
                "value": entry.get("value", ""),
                "weights": entry.get("weights", {}),
                "weight_source": entry.get("weight_source", ""),
            })
        if options:
            groups.append({
                "node_id": node_id,
                "question": question,
                "options": options,
            })

    return {"status": "ok", "data": {"groups": groups}}


@router.get("/explain/{clue_key:path}")
async def explain(clue_key: str) -> dict:
    """Phase H.4 — 단서의 BN 추론 trace 반환.

    UI 가 후보 hover/click 시 호출하여 ATT&CK 매핑·per-technique likelihood·
    aggregated likelihood 를 노출. PDF §17.B BAN 학술 설명용.

    `clue_key` 는 ':' 포함 가능 ("IP_ADDRESS:tor_vpn") → path 변환자 :path 사용.

    반환:
      {
        "status": "ok",
        "data": {
          "clue_key": str,
          "techniques": [...],
          "confidence": str,
          "per_technique_likelihood": {tid: {h: prob}}  (BN 경유 시),
          "aggregated_likelihood": {h: prob},
          "source": "bn" | "legacy_fallback"
        }
      }
    """
    try:
        info = bayes_net.explain_clue(clue_key)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": f"clue_to_attack.json 누락: {e}",
                "code": "MAPPING_NOT_FOUND",
            },
        )
    return {"status": "ok", "data": info}
