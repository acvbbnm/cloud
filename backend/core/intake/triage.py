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
from core.intake.modifier_eval import load_modifiers, triggered_modifier_ids

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


def seed_scores_from_environment(
    system_config: Optional[dict],
) -> tuple[dict[str, int], list[str]]:
    """시스템 구성(M0-2) → environment_modifiers 발동 → 가설 점수 시드 (2026-05-22).

    `environment_modifiers.json` 의 트리거 조건을 `system_config` 로 평가해
    발동한 modifier 의 `weights.json.environment_modifiers_to_hypothesis` 가중치를
    초기 가설 점수에 누적한다. 단서 루프(M0-3) 진입 시 0 이 아닌 환경 기반
    시작점을 제공 — 청사진 §2 + 사용자 결정 2026-05-22.

    Returns:
        (seeded_scores, applied_modifier_ids)
    """
    scores = _initial_scores()
    if not system_config:
        return scores, []
    em_table = _weights().get("environment_modifiers_to_hypothesis") or {}
    applied: list[str] = []
    for mid in triggered_modifier_ids(system_config):
        delta = em_table.get(mid)
        if delta:
            scores = _accumulate(scores, delta)
            applied.append(mid)
    return scores, applied


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
    def start(cls, system_config: Optional[dict] = None) -> dict:
        """트리아주 시작 — root 노드 + 초기 점수.

        `system_config` 가 주어지면 environment_modifiers 를 평가해 가설 점수를
        0 이 아닌 환경 기반 값으로 시딩한다 (M0-2 시스템 구성 → M0-3 단서 루프).

        Returns:
            { next_node, hypothesis_scores, tree_path: [], is_terminal: False,
              environment_seed: [발동 modifier id, ...] }
        """
        tree = _decision_tree()
        root_id = tree.get("root", "Q1_inception")
        scores, applied = seed_scores_from_environment(system_config)
        return {
            "next_node": _serialize_node(root_id),
            "hypothesis_scores": scores,
            "tree_path": [],
            "is_terminal": False,
            "recommendation": None,
            "environment_seed": applied,
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
        # 옵션 레벨 next 없으면 dynamic_next (E4 동적 분기) 시도
        if not next_node_id:
            dynamic_next = node.get("dynamic_next")
            if dynamic_next:
                # current_path 에서 Q2 노드 ID 를 찾아 분기 결정
                q2_node_id = None
                for p in current_path:
                    pid = p.get("node_id", "")
                    if pid.startswith("Q2"):
                        q2_node_id = pid
                        break
                if q2_node_id and q2_node_id in dynamic_next:
                    next_node_id = dynamic_next[q2_node_id]
                else:
                    next_node_id = dynamic_next.get("default")
        # 그래도 없으면 노드 레벨 next 사용 (Q2A·Q2B·Q2C·Q2D 다중/단일 합류형)
        if not next_node_id:
            next_node_id = node.get("next")

        # 점수 누적 (decision_tree_answers 가중치)
        weight_table = _weights().get("decision_tree_answers") or {}
        new_scores = _accumulate_many(current_scores, weight_keys, weight_table)

        # E4 조합 부스트 — 이전 답변과 현재 답변의 조합에 추가 점수
        combo_table = _weights().get("combination_boosts") or {}
        if combo_table:
            all_answer_keys = set()
            for p in current_path:
                for oid in p.get("selected_option_ids", []):
                    pid = p.get("node_id", "")
                    node_def = (tree.get("nodes") or {}).get(pid, {})
                    for opt in node_def.get("options") or []:
                        if opt.get("id") == oid and opt.get("weight_key"):
                            all_answer_keys.add(opt["weight_key"])
            all_answer_keys.update(weight_keys)
            for combo_key, combo_delta in combo_table.items():
                if combo_key.startswith("_"):
                    continue
                parts = combo_key.split("+")
                if len(parts) == 2 and all(p in all_answer_keys for p in parts):
                    new_scores = _accumulate(new_scores, combo_delta)

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
    def breakdown(
        cls,
        system_config: Optional[dict] = None,
        tree_path: Optional[list[dict]] = None,
        observables: Optional[list[dict]] = None,
        technique_ids: Optional[list[str]] = None,
    ) -> dict:
        """현재 누적된 가설 점수를 소스별·항목별로 분해 (V-1 차트 출처 트레이스).

        클라이언트가 보유한 상태(`tree_path`·`observables`·`technique_ids`)와
        케이스의 `system_config`를 받아, 5개 점수 소스 각각이 사고유형별로
        몇 점씩 기여했는지 재계산하여 반환한다.

        점수 소스 (weights.json 단일 소스):
          1. environment            — system_config → environment_modifiers
          2. tree                   — decision_tree_answers
          3. combo                  — combination_boosts (트리 답변 조합)
          4. clues                  — clue_types (단서 variant 자동 분류 포함)
          5. techniques             — partial_analysis_techniques

        결정성 100% 보장 — 같은 입력 시 같은 분해 결과 (학술 변호).
        AI 판단 X — 정적 가중치 lookup 만 수행.

        Returns:
            {
              totals: {CRED: 95, ...},        # 5 소스 합산
              by_source: {                    # 사고유형 × 소스 매트릭스
                environment: {CRED: 5, ...},
                tree: {CRED: 30, ...},
                combo: {CRED: 10, ...},
                clues: {CRED: 25, ...},
                techniques: {CRED: 25, ...}
              },
              items: [                        # 항목별 기여 trace
                {source, key, label, weights, rationale?},
                ...
              ]
            }
        """
        zero = {t: 0 for t in INCIDENT_TYPES_8}
        by_source: dict[str, dict[str, int]] = {
            "environment": dict(zero),
            "tree": dict(zero),
            "combo": dict(zero),
            "clues": dict(zero),
            "techniques": dict(zero),
        }
        items: list[dict] = []

        tree = _decision_tree()
        nodes_raw = tree.get("nodes") or {}
        weights = _weights()

        def _typed_delta(delta: dict) -> dict[str, int]:
            """delta dict 에서 사고유형 키만 추출 (source/_meta 등 메타 키 제거)."""
            return {t: int(delta.get(t, 0) or 0) for t in INCIDENT_TYPES_8}

        def _add(src: str, contrib: dict[str, int]) -> None:
            for t in INCIDENT_TYPES_8:
                by_source[src][t] += contrib.get(t, 0)

        # ── 1) environment_modifiers — system_config 트리거 평가 ──
        if system_config:
            em_table = weights.get("environment_modifiers_to_hypothesis") or {}
            mod_index = {
                m.get("id"): m
                for m in (load_modifiers().get("modifiers") or [])
            }
            for mid in triggered_modifier_ids(system_config):
                delta = em_table.get(mid)
                if not delta:
                    continue
                contrib = _typed_delta(delta)
                if not any(contrib.values()):
                    continue
                _add("environment", contrib)
                mod = mod_index.get(mid) or {}
                target = mod.get("target") or {}
                label_text = (
                    target.get("category_name")
                    or mod.get("reason")
                    or f"환경 보정 {mid}"
                )
                items.append({
                    "source": "environment",
                    "key": mid,
                    "label": label_text,
                    "weights": contrib,
                    "rationale": delta.get("source"),
                })

        # ── 2) tree answers — decision_tree_answers ──
        tree_table = weights.get("decision_tree_answers") or {}
        all_tree_keys: set[str] = set()
        if tree_path:
            for entry in tree_path:
                node_id = entry.get("node_id") or ""
                node = nodes_raw.get(node_id) or {}
                opts_by_id = {o.get("id"): o for o in (node.get("options") or [])}
                for opt_id in entry.get("selected_option_ids") or []:
                    opt = opts_by_id.get(opt_id) or {}
                    wk = opt.get("weight_key")
                    if not wk:
                        continue
                    all_tree_keys.add(wk)
                    delta = tree_table.get(wk)
                    if not delta:
                        continue
                    contrib = _typed_delta(delta)
                    if not any(contrib.values()):
                        continue
                    _add("tree", contrib)
                    q_label = node.get("question") or node_id
                    opt_label = opt.get("label") or opt_id
                    items.append({
                        "source": "tree",
                        "key": wk,
                        "label": f"{q_label} — {opt_label}",
                        "weights": contrib,
                        "rationale": delta.get("source"),
                    })

        # ── 3) combination_boosts — 트리 답변 조합 부스트 ──
        combo_table = weights.get("combination_boosts") or {}
        for combo_key, combo_delta in combo_table.items():
            if not isinstance(combo_key, str) or combo_key.startswith("_"):
                continue
            if not isinstance(combo_delta, dict):
                continue
            parts = combo_key.split("+")
            if len(parts) != 2:
                continue
            if not all(p in all_tree_keys for p in parts):
                continue
            contrib = _typed_delta(combo_delta)
            if not any(contrib.values()):
                continue
            _add("combo", contrib)
            items.append({
                "source": "combo",
                "key": combo_key,
                "label": f"조합 부스트 — {parts[0]} + {parts[1]}",
                "weights": contrib,
                "rationale": combo_delta.get("source"),
            })

        # ── 4) clue_types — 단서 (variant 자동 분류 포함) ──
        clue_table = weights.get("clue_types") or {}
        if observables:
            from core.intake.clue_classifier import enrich_clue
            for clue in observables:
                if not isinstance(clue, dict):
                    continue
                try:
                    enriched = enrich_clue(clue)
                except Exception:  # noqa: BLE001
                    enriched = dict(clue)
                wk = enriched.get("weight_key")
                if not wk and enriched.get("type"):
                    wk = f"{enriched['type']}:generic"
                delta = clue_table.get(wk) if wk else None
                if not delta:
                    continue
                contrib = _typed_delta(delta)
                if not any(contrib.values()):
                    continue
                _add("clues", contrib)
                ctype = enriched.get("type") or "?"
                value = (clue.get("value") or "")[:48]
                items.append({
                    "source": "clue",
                    "key": wk,
                    "label": f"{ctype} 단서 — {value}",
                    "weights": contrib,
                    "rationale": delta.get("source"),
                })

        # ── 5) partial_analysis_techniques — 부분 로그 매핑 ──
        tech_table = weights.get("partial_analysis_techniques") or {}
        if technique_ids:
            for tid in technique_ids:
                if not tid:
                    continue
                delta = tech_table.get(tid)
                if not delta:
                    continue
                contrib = _typed_delta(delta)
                if not any(contrib.values()):
                    continue
                _add("techniques", contrib)
                items.append({
                    "source": "technique",
                    "key": tid,
                    "label": f"{tid} 매핑",
                    "weights": contrib,
                    "rationale": delta.get("source"),
                })

        # totals — 5 소스 합산
        totals = dict(zero)
        for src_scores in by_source.values():
            for t, v in src_scores.items():
                totals[t] += v

        return {
            "totals": totals,
            "by_source": by_source,
            "items": items,
        }

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
