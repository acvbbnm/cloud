"""Layer 2 — OCSFNormalizer.

설계서 5.4.4절 + 5.2.1절 + 모듈별_구현_명세 OCSFNormalizer 항목.

raw_events → ocsf_events 변환:
  1. csp 별 mapping rule JSON 로딩 (startup 1회 캐시)
  2. raw_json 파싱 후 field_mappings 적용 (dot 표기 nested 접근)
  3. value_transforms 적용 (datetime 이중 형식 / SUCCESS-FAIL → 200-500)
  4. 매핑되지 않은 원본 필드는 unmapped_raw 에 그대로 보존
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from db.models import OCSFEventModel, RawEventModel


# ── CSP → mapping rule 파일명 ────────────────────────────────
_CSP_TO_FILE = {
    "naver": "ncp_cloudtrail.json",
    "nhn": "nhn_cloud_trail.json",
}

# 캐시: 첫 호출 시 로딩
_RULE_CACHE: dict[str, dict] = {}


def _load_rules(csp: str) -> Optional[dict]:
    """csp(naver/nhn)의 mapping rule JSON 을 로드/캐시."""
    if csp in _RULE_CACHE:
        return _RULE_CACHE[csp]
    fname = _CSP_TO_FILE.get(csp)
    if fname is None:
        return None
    path: Path = settings.MAPPING_RULES_DIR / fname
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        rules = json.load(f)
    _RULE_CACHE[csp] = rules
    return rules


def _get_nested(d: Any, dotted_path: str) -> Any:
    """'content.actionUserName' 같은 dot 표기로 nested dict 에서 값 추출."""
    value = d
    for key in dotted_path.split("."):
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def _transform_value(value: Any, transform: dict) -> Any:
    """value_transforms 정의에 따라 값을 변환. 변환 실패/미지원 시 None."""
    if value is None:
        return None

    ttype = transform.get("type")

    if ttype == "datetime":
        accept = transform.get("accept", [])
        fmt = transform.get("string_format")

        # Unix milliseconds (int 또는 float)
        if "unix_ms_int" in accept and isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc).replace(
                    tzinfo=None
                )
            except (OverflowError, OSError, ValueError):
                return None

        # 문자열 — ISO8601 우선 시도, 실패하면 명시 포맷
        if isinstance(value, str):
            if "iso8601" in accept:
                try:
                    iso = value.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(iso)
                    if dt.tzinfo is not None:
                        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                    return dt
                except ValueError:
                    pass
            if fmt:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    pass
        return None

    if ttype == "enum_to_int":
        return transform.get("map", {}).get(value)

    return value


class OCSFNormalizer:
    """OCSF 정규화기 — raw_events 한 건 또는 다수를 ocsf_events 로 변환·적재."""

    @classmethod
    def normalize_one(cls, db: Session, raw: RawEventModel) -> tuple[bool, Optional[str]]:
        """raw_event 1건 정규화. (성공여부, 실패사유). 이미 정규화돼 있으면 (True, None)로 skip."""
        # 이미 정규화된 이벤트는 skip (event_id UNIQUE 제약)
        existing = db.execute(
            select(OCSFEventModel).where(OCSFEventModel.event_id == raw.event_id)
        ).scalar_one_or_none()
        if existing is not None:
            return True, None

        rules = _load_rules(raw.csp)
        if rules is None:
            return False, f"mapping rule not found for csp={raw.csp}"

        try:
            payload = json.loads(raw.raw_json) if isinstance(raw.raw_json, str) else raw.raw_json
        except (json.JSONDecodeError, TypeError):
            return False, "raw_json parse error"

        field_mappings: dict = rules.get("field_mappings", {})
        value_transforms: dict = rules.get("value_transforms", {})

        flat: dict[str, Any] = {}
        for source_path, target_col in field_mappings.items():
            raw_value = _get_nested(payload, source_path)
            transform = value_transforms.get(source_path)
            if transform is not None:
                raw_value = _transform_value(raw_value, transform)
            flat[target_col] = raw_value

        # 필수 컬럼 검증
        if flat.get("time") is None:
            return False, "time field missing or unparsable"
        if not flat.get("activity_name"):
            return False, "activity_name field missing"

        ocsf = OCSFEventModel(
            event_id=raw.event_id,
            time=flat["time"],
            actor_user_name=flat.get("actor_user_name"),
            src_endpoint_ip=flat.get("src_endpoint_ip"),
            activity_name=str(flat["activity_name"])[:128],
            status_code=flat.get("status_code"),
            unmapped_raw=payload,  # 원본 전체 보존
        )

        try:
            db.add(ocsf)
            db.flush()
        except IntegrityError:
            db.rollback()
            return False, "ocsf insert integrity error"

        return True, None

    @classmethod
    def normalize_case(
        cls,
        db: Session,
        case_id: str,
        event_ids: Optional[list[str]] = None,
    ) -> dict:
        """케이스의 raw_events 를 일괄 정규화. event_ids 지정 시 그 이벤트만.

        반환: {total, normalized, failed, normalizationRate, failedEvents}
        """
        stmt = select(RawEventModel).where(RawEventModel.case_id == case_id)
        if event_ids:
            stmt = stmt.where(RawEventModel.event_id.in_(event_ids))
        rows = list(db.execute(stmt).scalars())

        normalized = 0
        failed: list[dict] = []
        for raw in rows:
            ok, reason = cls.normalize_one(db, raw)
            if ok:
                normalized += 1
            else:
                failed.append({"event_id": raw.event_id, "reason": reason})

        db.commit()
        total = len(rows)
        rate = round(normalized / total * 100, 2) if total else 0.0
        return {
            "total": total,
            "normalized": normalized,
            "failed": len(failed),
            "normalizationRate": rate,
            "failedEvents": failed[:20],  # 너무 많으면 앞 20건만
        }
