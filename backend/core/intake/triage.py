"""Layer 0 — Triage 엔진 (dev3 B-1, 2026-05-18).

V-1 Step 2 Discovery Loop 의 백엔드 평가 엔진. 3개 소스의 가중치를 누적하여
사고유형 가설 점수를 산출하고, 임계값 도달 시 recommendation 을 반환한다.

가중치 소스 (모두 `backend/data/triage/*.json` 정적 JSON):
  1. decision_tree_answers : 결정 트리 답변 (Q1·Q2x·Q3 등)
  2. clue_types            : 단서(Observable) 타입·변종별
  3. partial_analysis_techniques : 부분 로그 분석 매핑된 ATT&CK 기법 ID

설계 원칙 (청사진 §2 + CLAUDE.md 정합):
  - 결정성 100% — 같은 입력 시 같은 출력 (학술 변호)
  - AI 판단 X — 점수 산출은 정적 가중치만 사용
  - 임계값은 weights.json `thresholds` 단일 소스 (auto_skip_tree=90, high_confidence=70)
  - 클라이언트가 hypothesis_scores 를 전달 — 서버는 stateless 누적 계산
    (DB 영속화는 B-3 작업으로 분리)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, Optional

from config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 데이터 로딩 (startup 1회 캐싱)
# ─────────────────────────────────────────────────────────────

_TRIAGE_DIR = settings.DATA_DIR / "triage"

INCIDENT_TYPES_8 = [
    # ── 4종 기존 (MULTI_CSP_LATERAL 제거, 2026-05-19) ──
    "CREDENTIAL_THEFT",
    "PRIVILEGE_ESCALATION",
    "DATA_EXFILTRATION",
    "AUDIT_LOG_TAMPERING",
    # ── dev3 C-1 신규 4종 ──
    "RANSOMWARE",
    "MISCONFIG_EXPOSURE",
    "PHISH_INITIAL_ACCESS",
    "INSIDER_THREAT",
]

# 하위 호환 — 기존 코드에서 INCIDENT_TYPES_5 / _9 import 시 8종으로 그대로 동작
INCIDENT_TYPES_5 = INCIDENT_TYPES_8
INCIDENT_TYPES_9 = INCIDENT_TYPES_8


def _initial_scores() -> dict[str, int]:
    """8 사고유형 + UNCLASSIFIED 모두 0 인 점수 초기값 (2026-05-19)."""
    return {t: 0 for t in INCIDENT_TYPES_8} | {"UNCLASSIFIED": 0}


_cache: dict[str, object] = {}


def _load_json(name: str) -> dict:
    """`backend/data/triage/{name}.json` 로드 + 캐시."""
    key = f"json:{name}"
    if key in _cache:
        return _cache[key]  # type: ignore[return-value]
    path = _TRIAGE_DIR / f"{name}.json"
    if not path.exists():
        logger.warning("triage data missing: %s", path)
        _cache[key] = {}
        return {}
    with open(path, encoding="utf-8") as f:
        _cache[key] = json.load(f)
    return _cache[key]


def _decision_tree() -> dict:
    return _load_json("decision_tree")


def _weights() -> dict:
    return _load_json("weights")


def _next_clue_graph() -> dict:
    return _load_json("next_clue_graph")


def invalidate_cache() -> None:
    """테스트·시드 핫리로드용. 운영에서는 호출 X."""
    _cache.clear()


# ─────────────────────────────────────────────────────────────
# 점수 누적 헬퍼
# ─────────────────────────────────────────────────────────────


def _accumulate(
    base: dict[str, int],
    delta: Optional[dict[str, int | str]],
) -> dict[str, int]:
    """가중치 dict 의 5 사고유형 키만 base 에 누적. source 등 메타 키는 무시.

    빈 dict 또는 None 이면 base 사본 그대로 반환.
    """
    out = dict(base)
    if not delta:
        return out
    for k in INCIDENT_TYPES_5:
        v = delta.get(k)
        if isinstance(v, (int, float)):
            out[k] = int(out.get(k, 0)) + int(v)
    return out


def _accumulate_many(
    base: dict[str, int],
    weight_keys: Iterable[str],
    weight_table: dict[str, dict],
) -> dict[str, int]:
    """weight_keys 의 각 키를 weight_table 에서 조회해 base 에 누적."""
    out = dict(base)
    for k in weight_keys:
        delta = weight_table.get(k)
        if delta:
            out = _accumulate(out, delta)
    return out


# ─────────────────────────────────────────────────────────────
# 트리 노드 직렬화 (응답 형식)
# ─────────────────────────────────────────────────────────────


def _serialize_node(node_id: str) -> Optional[dict]:
    """트리 노드를 응답 dict 로 직렬화. 노드 없으면 None."""
    tree = _decision_tree()
    nodes = tree.get("nodes") or {}
    node = nodes.get(node_id)
    if node is None:
        return None
    return {
        "id": node_id,
        "type": node.get("type", "question"),
        "question": node.get("question"),
        "options": node.get("options"),
        "multi_select": node.get("multi_select", False),
        "action": node.get("action"),
        "message": node.get("message"),
        "fallback_incident_type": node.get("fallback_incident_type"),
        "kisa_field": node.get("kisa_field"),
    }


# ─────────────────────────────────────────────────────────────
# 추천 평가
# ─────────────────────────────────────────────────────────────


def _thresholds() -> dict[str, int]:
    t = _weights().get("thresholds") or {}
    return {
        "high_confidence": int(t.get("high_confidence", 70)),
        "auto_skip_tree": int(t.get("auto_skip_tree", 90)),
        "gap_to_2nd": int(t.get("gap_to_2nd", 20)),
        "terminal_score": int(t.get("terminal_score", 120)),
    }


def evaluate_recommendation(scores: dict[str, int]) -> dict:
    """현재 가설 점수 → recommendation.

    outcome:
      auto_confirm       : primary >= auto_skip_tree(90) AND gap >= gap_to_2nd(20)
      propose_composite  : primary >= high_confidence(70) AND gap < gap_to_2nd(20)
      propose_single     : primary >= high_confidence(70)
      continue_or_skip   : 그 외 — 추가 단서 또는 UNCLASSIFIED 진행
    """
    th = _thresholds()
    sorted_pairs = sorted(
        [(t, scores.get(t, 0)) for t in INCIDENT_TYPES_5],
        key=lambda x: x[1],
        reverse=True,
    )
    primary_type, primary_score = sorted_pairs[0]
    secondary_type, secondary_score = sorted_pairs[1]
    gap = primary_score - secondary_score

    if primary_score >= th["auto_skip_tree"] and gap >= th["gap_to_2nd"]:
        return {
            "outcome": "auto_confirm",
            "primary": {"incident_type": primary_type, "score": primary_score},
            "rationale": [
                f"{primary_type} {primary_score}점 — auto_skip {th['auto_skip_tree']} + gap {gap} ≥ {th['gap_to_2nd']}"
            ],
            "message": "단일 사고유형 자동 확정",
        }
    if primary_score >= th["high_confidence"] and gap < th["gap_to_2nd"]:
        return {
            "outcome": "propose_composite",
            "primary": {"incident_type": primary_type, "score": primary_score},
            "secondary": {"incident_type": secondary_type, "score": secondary_score},
            "rationale": [
                f"{primary_type} {primary_score}점",
                f"{secondary_type} {secondary_score}점 (gap {gap} — 복합 가설)",
            ],
            "message": "복합 사고유형 제시 — 메인 + 부 사고유형",
        }
    if primary_score >= th["high_confidence"]:
        return {
            "outcome": "propose_single",
            "primary": {"incident_type": primary_type, "score": primary_score},
            "rationale": [
                f"{primary_type} {primary_score}점 — 단일 가설 (사용자 수락 필요)"
            ],
            "message": "단일 사고유형 제시 (사용자 수락 필요)",
        }
    return {
        "outcome": "continue_or_skip",
        "primary": {"incident_type": primary_type, "score": primary_score},
        "rationale": [
            f"최상위 {primary_type} {primary_score}점 — 임계값 {th['high_confidence']} 미달"
        ],
        "message": "임계값 미달 — 추가 단서 입력 또는 UNCLASSIFIED 진행",
    }


# ─────────────────────────────────────────────────────────────
# 공개 API — 라우터에서 호출
# ─────────────────────────────────────────────────────────────


class Triage:
    """결정 트리 트리아주 평가 엔진."""

    @classmethod
    def start(cls) -> dict:
        """트리아주 시작 — root 노드 + 초기 점수.

        Returns:
            { next_node, hypothesis_scores, tree_path: [], is_terminal: False }
        """
        tree = _decision_tree()
        root_id = tree.get("root", "Q1_inception")
        return {
            "next_node": _serialize_node(root_id),
            "hypothesis_scores": _initial_scores(),
            "tree_path": [],
            "is_terminal": False,
            "recommendation": None,
        }

    @classmethod
    def next_question(
        cls,
        current_node_id: str,
        answer_ids: list[str],
        current_scores: dict[str, int],
        current_path: list[dict],
    ) -> dict:
        """현재 질문에 답변 → 다음 노드 + 점수 갱신.

        Args:
            current_node_id: 답변한 노드 ID (예: 'Q1_inception')
            answer_ids:      선택한 옵션 ID 배열 (multi_select 시 N개)
            current_scores:  클라이언트가 들고 있는 누적 점수
            current_path:    [{node_id, selected_option_ids}, ...]

        Returns:
            { next_node, hypothesis_scores, tree_path, is_terminal, recommendation? }
        """
        tree = _decision_tree()
        node = (tree.get("nodes") or {}).get(current_node_id)
        if node is None:
            return {
                "next_node": None,
                "hypothesis_scores": current_scores,
                "tree_path": current_path,
                "is_terminal": True,
                "recommendation": None,
                "error": f"unknown node: {current_node_id}",
            }

        # 선택된 옵션의 weight_key 들 수집 + 다음 노드 결정
        # decision_tree.json 의 next 필드는 두 위치 가능:
        #   1) 옵션 레벨 (예: Q1_inception 의 각 옵션마다 next) — single_select 분기형
        #   2) 노드 레벨 (예: Q2A_alert_type 다중 선택 후 모두 동일한 next) — multi_select 합류형
        # 옵션 레벨이 우선, 없으면 노드 레벨로 fallback.
        weight_keys: list[str] = []
        next_node_id: Optional[str] = None
        options = node.get("options") or []
        for opt in options:
            if opt.get("id") not in answer_ids:
                continue
            wk = opt.get("weight_key")
            if wk:
                weight_keys.append(wk)
            if not next_node_id and opt.get("next"):
                next_node_id = opt.get("next")
        # 옵션 레벨 next 없으면 노드 레벨 next 사용 (Q2A·Q2B·Q2C·Q2D 다중/단일 합류형)
        if not next_node_id:
            next_node_id = node.get("next")

        # 점수 누적 (decision_tree_answers 가중치)
        weight_table = _weights().get("decision_tree_answers") or {}
        new_scores = _accumulate_many(current_scores, weight_keys, weight_table)

        # 경로 갱신
        new_path = [p for p in current_path if p.get("node_id") != current_node_id]
        new_path.append(
            {"node_id": current_node_id, "selected_option_ids": answer_ids}
        )

        # 다음 노드 직렬화
        next_node = _serialize_node(next_node_id) if next_node_id else None
        is_terminal = not next_node or next_node.get("type") == "terminal"

        # T_evaluate 도달 시 recommendation 계산
        recommendation: Optional[dict] = None
        if next_node and next_node.get("id") == "T_evaluate":
            recommendation = evaluate_recommendation(new_scores)

        return {
            "next_node": next_node,
            "hypothesis_scores": new_scores,
            "tree_path": new_path,
            "is_terminal": is_terminal,
            "recommendation": recommendation,
        }

    @classmethod
    def analyze(
        cls,
        current_scores: dict[str, int],
        clue: Optional[dict] = None,
        technique_ids: Optional[list[str]] = None,
    ) -> dict:
        """단서·부분 로그 분석 결과를 가설 점수에 누적.

        Args:
            current_scores: 클라이언트 누적 점수
            clue:           Observable dict (type, value, weight_key?, note?)
            technique_ids:  부분 로그 분석으로 매핑된 ATT&CK 기법 ID 목록

        가중치 적용 규칙:
          - clue.weight_key 가 있으면 weights.clue_types 에서 직접 조회
          - clue.weight_key 가 없으면 ClueType 기본값 ("IP_ADDRESS:default" 등) — 차후 보강
          - technique_ids 는 weights.partial_analysis_techniques 에서 조회 (다중 누적)

        Returns:
            { hypothesis_scores, mapped_techniques, next_clues: [] }
        """
        new_scores = dict(current_scores)

        # 단서 가중치
        if clue:
            # Q3 (2026-05-21): 자동 variant 분류 — weight_key 없으면 백엔드가 자동 추정.
            # 폐쇄망 호환 (정적 룰만 — 외부 IP DB·VT API 호출 X).
            # 자동 분류 실패 시 Q1 generic fallback (5점) 적용.
            from core.intake.clue_classifier import enrich_clue
            enriched = enrich_clue(clue)
            wk = enriched.get("weight_key")
            if not wk and enriched.get("type"):
                wk = f"{enriched['type']}:generic"
            clue_table = _weights().get("clue_types") or {}
            new_scores = _accumulate_many(new_scores, [wk] if wk else [], clue_table)

        # 부분 로그 매핑 가중치
        if technique_ids:
            tech_table = _weights().get("partial_analysis_techniques") or {}
            new_scores = _accumulate_many(new_scores, technique_ids, tech_table)

        return {
            "hypothesis_scores": new_scores,
            "mapped_techniques": technique_ids or [],
            # 다음 단서 제안 — pivots 자료가 list 형식이라 차후 구조 검토 필요. 일단 [] 반환
            "next_clues": [],
        }

    @classmethod
    def evaluate(cls, scores: dict[str, int]) -> dict:
        """현재 점수만으로 추천 결과 산출 (강제 평가)."""
        return evaluate_recommendation(scores)

    @classmethod
    def tree_visualization(cls, current_node_id: Optional[str] = None) -> dict:
        """결정 트리 전체 노드·엣지 응답 (V-1 Step 2 시각화·미니맵용).

        Returns:
            {
              root: str,
              current_node: str | None,
              nodes: [{id, type, label, multi_select}, ...],
              edges: [{from, to, label, option_id?}, ...]
            }
        """
        tree = _decision_tree()
        nodes_raw = tree.get("nodes") or {}
        root_id = tree.get("root", "Q1_inception")

        nodes: list[dict] = []
        edges: list[dict] = []
        for nid, node in nodes_raw.items():
            label = (
                node.get("question")
                or node.get("message")
                or node.get("action")
                or nid
            )
            nodes.append(
                {
                    "id": nid,
                    "type": node.get("type", "question"),
                    "label": label,
                    "multi_select": bool(node.get("multi_select", False)),
                    "fallback_incident_type": node.get("fallback_incident_type"),
                }
            )

            options = node.get("options") or []
            for opt in options:
                nxt = opt.get("next")
                if nxt:
                    edges.append(
                        {
                            "from": nid,
                            "to": nxt,
                            "label": opt.get("text") or opt.get("id") or "",
                            "option_id": opt.get("id"),
                        }
                    )
            # 노드 레벨 next (multi_select 합류형) — 옵션에 next 가 하나도 없을 때만
            node_next = node.get("next")
            if node_next and not any(o.get("next") for o in options):
                edges.append(
                    {
                        "from": nid,
                        "to": node_next,
                        "label": "",
                        "option_id": None,
                    }
                )

        return {
            "root": root_id,
            "current_node": current_node_id,
            "nodes": nodes,
            "edges": edges,
        }
