"""NCP Cloud Activity Tracer raw log 파서.

설계서 5.2.1절 NCP 필드 매핑 + data/mapping_rules/ncp_cloudtrail.json 기준.
실제 raw 형식:
  - 최상위가 list (events 배열) 또는 dict.
  - 각 event는 {historyId, nrn, productName, regionCode, regionName, action,
    actionResultType, eventTime, content{actionUserName, sourceIp, ...}, ...}
  - eventTime 은 Tracer Export 시 Unix ms(int), 콘솔/API 응답 시 "YYYY-MM-DD HH:MM:SS UTC" 문자열.

이 파서의 책임:
  - bytes/str → JSON 파싱 후 event 배열 추출
  - 매칭에 필요한 필드(action, productName, source_ip 등)만 평탄화하여 반환
  - OCSF 정규화는 Layer 2 OCSFNormalizer 의 책임이므로 여기서는 하지 않는다
"""
import json
from datetime import datetime, timezone
from typing import Optional, Union


# eventTime 문자열 포맷 (NCP 콘솔 응답)
_NCP_DT_FORMAT = "%Y-%m-%d %H:%M:%S UTC"


def parse_event_time(value: Union[int, float, str, None]) -> Optional[datetime]:
    """NCP eventTime 두 가지 형식을 datetime으로 변환한다.

    - int/float: Unix ms (Tracer Export 형식)
    - str: "YYYY-MM-DD HH:MM:SS UTC" (콘솔/API 형식)

    실패 시 None 반환 (raw_event에는 어차피 원본이 그대로 보존된다).
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Unix ms → seconds
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc).replace(tzinfo=None)
    if isinstance(value, str):
        try:
            return datetime.strptime(value, _NCP_DT_FORMAT)
        except ValueError:
            # ISO8601 fallback
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
    return None


def parse(payload: Union[bytes, str]) -> list[dict]:
    """NCP raw log payload(파일 바이트 또는 문자열) → 평탄화 dict 리스트.

    반환 dict 각 항목:
      {
        "raw": <원본 event dict>,           # 그대로 raw_events.raw_json 에 저장
        "action": str | None,              # 매칭에 사용
        "product_name": str | None,        # 매칭에 사용
        "actor_user_name": str | None,
        "source_ip": str | None,
        "event_time": datetime | None,
        "result": str | None,              # SUCCESS/FAIL
      }
    """
    if isinstance(payload, bytes):
        # utf-8-sig 는 BOM 이 있으면 자동 제거, 없으면 utf-8 와 동일하게 동작.
        # NCP Tracer Export 파일에 BOM 이 포함되는 경우 대비.
        payload = payload.decode("utf-8-sig")
    elif payload.startswith("﻿"):
        payload = payload.lstrip("﻿")
    data = json.loads(payload)

    # 최상위 형식 흡수: list / {"events": [...]} / 단일 dict
    if isinstance(data, list):
        events = data
    elif isinstance(data, dict):
        events = data.get("events") or data.get("items") or [data]
    else:
        raise ValueError("NCP raw 형식이 list 또는 dict 가 아닙니다.")

    parsed: list[dict] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        content = ev.get("content") or {}
        parsed.append(
            {
                "raw": ev,
                "action": ev.get("action"),
                "product_name": ev.get("productName"),
                "actor_user_name": content.get("actionUserName")
                or ev.get("actionUserName"),
                "source_ip": content.get("sourceIp") or ev.get("sourceIp"),
                "event_time": parse_event_time(ev.get("eventTime")),
                "result": ev.get("actionResultType"),
            }
        )
    return parsed
