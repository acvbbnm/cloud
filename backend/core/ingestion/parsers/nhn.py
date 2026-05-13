"""NHN Cloud Trail raw log 파서.

설계서 5.2.1절 NHN 필드 매핑 + data/mapping_rules/nhn_cloud_trail.json 기준.
실제 raw 형식 (nhn_activity_logs.json 147건 분석):
  - 최상위 list, 각 event는
    {eventLogUuid, eventTime, eventId, userName, userIp, result,
     userId(이메일), userIdNo(UUID), userAgent, projectId, orgId,
     request(JSON 문자열), response(JSON 문자열), ...}
  - eventTime 은 ISO8601 with timezone offset: "2024-12-30T14:23:01.123+0900"
  - eventId 는 "event_id.iam.login", "event_id.iaas.s3credential.create" 등
    점-분리 계층형 코드. 매칭의 핵심 필드.
"""
import json
from datetime import datetime, timezone
from typing import Optional, Union


# NHN eventTime 포맷 (예: "2024-12-30T14:23:01.123+0900")
_NHN_DT_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"


def parse_event_time(value: Optional[str]) -> Optional[datetime]:
    """NHN eventTime ISO8601(+0900 등) → naive UTC datetime.

    실패 시 None.
    """
    if not isinstance(value, str):
        return None
    try:
        # strptime은 +0900 포맷 ok, +09:00은 fromisoformat
        dt = datetime.strptime(value, _NHN_DT_FORMAT)
    except ValueError:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    # tz-aware → naive UTC 로 통일 (DB 컬럼이 naive DateTime 이므로 시스템 timezone 의존 제거).
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def parse(payload: Union[bytes, str]) -> list[dict]:
    """NHN raw log payload → 평탄화 dict 리스트.

    반환 dict 각 항목:
      {
        "raw": <원본 event dict>,
        "event_id": str | None,             # event_id.iam.login 형식
        "actor_user_name": str | None,
        "source_ip": str | None,
        "event_time": datetime | None,
        "result": str | None,               # SUCCESS/FAIL
      }
    """
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8-sig")
    elif payload.startswith("﻿"):
        payload = payload.lstrip("﻿")
    data = json.loads(payload)

    if isinstance(data, list):
        events = data
    elif isinstance(data, dict):
        events = data.get("events") or data.get("items") or [data]
    else:
        raise ValueError("NHN raw 형식이 list 또는 dict 가 아닙니다.")

    parsed: list[dict] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        parsed.append(
            {
                "raw": ev,
                "event_id": ev.get("eventId"),
                "actor_user_name": ev.get("userName"),
                "source_ip": ev.get("userIp"),
                "event_time": parse_event_time(ev.get("eventTime")),
                "result": ev.get("result"),
            }
        )
    return parsed
