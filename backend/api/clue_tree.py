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

from core.intake.clue_tree_service import (
    CaseNotFound,
    ClueTreeNotFound,
    expand_tree,
    get_tree,
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


class CueTreeSuggestRequest(BaseModel):
    caseId: str


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
