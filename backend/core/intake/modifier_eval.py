"""환경 변경자(environment_modifiers) 평가 — 가이드·가설 점수 공용 (2026-05-22).

`system_config` 입력값을 `environment_modifiers.json` 의 트리거 조건과 대조하여
어떤 modifier 가 발동하는지 판정한다. 동일 트리거를 두 곳에서 분리 사용:
  - 수집 가이드 : `collection_guide_v2` 가 BOOST/ADD effect 로 사용
  - 가설 점수   : `triage` 가 `weights.json` 의
    `environment_modifiers_to_hypothesis` 가중치로 사용

설계 원칙 (CLAUDE.md 정합):
  - 결정성 100% — 정적 JSON 트리거 평가만. 같은 system_config → 같은 발동 집합.
  - AI 판단 X.
"""
import json
import logging
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

_cache: dict[str, object] = {}


def _modifiers_path() -> Path:
    """`backend/data/collection_targets_v2/environment_modifiers.json` 경로."""
    return settings.DATA_DIR / "collection_targets_v2" / "environment_modifiers.json"


def load_modifiers() -> dict:
    """`environment_modifiers.json` 로딩 + 캐시."""
    if "modifiers" in _cache:
        return _cache["modifiers"]  # type: ignore[return-value]
    p = _modifiers_path()
    if not p.exists():
        logger.warning("environment_modifiers.json missing: %s", p)
        _cache["modifiers"] = {"modifiers": [], "fallback_modifiers": []}
        return _cache["modifiers"]
    with open(p, encoding="utf-8") as fp:
        _cache["modifiers"] = json.load(fp)
    return _cache["modifiers"]


def invalidate_cache() -> None:
    """테스트·시드 핫리로드용."""
    _cache.clear()


def resolve_field(system_config: dict, field_path: str) -> object:
    """`system_config.mfa_status` 같은 dot-path 를 dict 에서 추출."""
    if not system_config:
        return None
    if field_path.startswith("system_config."):
        field_path = field_path[len("system_config."):]
    cur: object = system_config
    for key in field_path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
        if cur is None:
            return None
    return cur


def eval_operator(actual: object, operator: str, expected: object) -> bool:
    """modifier operator 평가. 미지원 operator 는 False."""
    if actual is None:
        return False
    op = operator.lower()
    if op == "equals":
        return actual == expected
    if op == "contains":
        if isinstance(actual, str):
            return str(expected) in actual
        if isinstance(actual, (list, tuple)):
            return expected in actual
        return False
    if op == "contains_any":
        if not isinstance(expected, (list, tuple)):
            return False
        if isinstance(actual, str):
            return any(str(e) in actual for e in expected)
        if isinstance(actual, (list, tuple)):
            actual_set = set(actual)
            return any(e in actual_set for e in expected)
        return False
    if op in ("greater_than_or_equal", "gte"):
        try:
            return float(actual) >= float(expected)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
    if op == "less_than":
        try:
            return float(actual) < float(expected)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
    logger.warning("unknown operator: %s", operator)
    return False


def triggered_modifier_ids(system_config: dict | None) -> list[str]:
    """`system_config` 에 대해 발동(트리거 매칭)하는 modifier id 목록.

    `environment_modifiers.json` 의 각 modifier 의 field/operator/value 조건을
    평가한다. system_config 가 비면 빈 리스트.
    """
    sc = system_config or {}
    if not sc:
        return []
    ids: list[str] = []
    for m in load_modifiers().get("modifiers", []):
        actual = resolve_field(sc, m.get("field", ""))
        if eval_operator(actual, m.get("operator", ""), m.get("value")):
            mid = m.get("id")
            if mid:
                ids.append(mid)
    return ids
