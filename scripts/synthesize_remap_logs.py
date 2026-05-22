"""REMAP 시나리오 16편 → NCP/NHN raw 로그 16개 파일 생성.

case_db.json 의 CASE-REMAP-* 청크 timeline 을 읽어
- naver/all+naver→NCP Cloud Activity Tracer raw JSON
- nhn/all+nhn→NHN Cloud Trail raw JSON
형식으로 변환한다.

출력: data/test_logs/remap/{chunk_id}.json
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CASE_DB = BASE / "backend" / "data" / "kb" / "case_db.json"
OUT_DIR = BASE / "data" / "test_logs" / "remap"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def parse_window_date(time_window: str) -> str:
    """time_window 문자열에서 시작 날짜(YYYY-MM-DD) 추출."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", time_window or "")
    if not m:
        return "2026-05-21"
    return m.group(1)


def parse_time(t: str, default_date: str) -> tuple[str, str]:
    """timeline 의 'time' 값을 (YYYY-MM-DD HH:MM:SS UTC, ISO8601) 두 형식으로 반환."""
    t = (t or "").strip()
    # 'MM-DD HH:MM:SS' 형식 처리 (날짜 prefix 있는 경우)
    m = re.match(r"^(\d{2})-(\d{2})\s+(\d{2}:\d{2}:\d{2})$", t)
    if m:
        year = default_date.split("-")[0]
        date = f"{year}-{m.group(1)}-{m.group(2)}"
        time_only = m.group(3)
    else:
        # 'HH:MM:SS' 만 있는 경우
        m2 = re.match(r"^(\d{2}:\d{2}:\d{2})$", t)
        if m2:
            date = default_date
            time_only = m2.group(1)
        else:
            date = default_date
            time_only = "00:00:00"
    ncp_str = f"{date} {time_only} UTC"
    iso = f"{date}T{time_only}.000+0000"
    return ncp_str, iso


def make_ncp_event(actor: str, action: str, result: str, ip: str, time_str: str, idx: int) -> dict:
    """NCP Activity Tracer raw 1건 생성."""
    # 'audit OFF' 같은 IP placeholder 처리
    ip_clean = ip if ip and re.match(r"^[\d.]+$", ip) else "0.0.0.0"
    return {
        "historyId": f"h-{uuid.uuid4().hex[:12]}",
        "nrn": f"nrn:ncp:iam:KR:5000000:account/{actor}",
        "regionCode": "KR",
        "regionName": "Korea, Republic of",
        "resourceType": "Account",
        "productName": _ncp_product(action),
        "actionUserType": "SUB_ACCOUNT",
        "actionSubAccountNo": f"{20000000 + idx}",
        "sourceType": "CONSOLE",
        "domainCode": "kr",
        "action": action,
        "actionResultType": result,
        "eventTime": time_str,
        "content": {
            "actionUserName": actor,
            "sourceIp": ip_clean,
            "productData": {},
        },
    }


def _ncp_product(action: str) -> str:
    """action 에서 productName 추정 (룰 매칭에 영향 없음, 메타 표시용)."""
    a = action.lower()
    if "policy" in a or "sub account" in a or "accesskey" in a or "access key" in a or "password" in a or a in ("login",):
        return "SubAccount"
    if "server" in a or "root password" in a:
        return "Server"
    if "object storage" in a or "bucket" in a or "exporting" in a:
        return "Object Storage"
    if "tracer" in a or "auto export" in a:
        return "Cloud Activity Tracer"
    return "SubAccount"


def make_nhn_event(actor: str, event_id: str, result: str, ip: str, time_iso: str) -> dict:
    """NHN Cloud Trail raw 1건 생성."""
    ip_clean = ip if ip and re.match(r"^[\d.]+$", ip) else "0.0.0.0"
    return {
        "eventLogUuid": str(uuid.uuid4()),
        "eventTime": time_iso,
        "eventId": event_id,
        "result": result,
        "userName": actor,
        "userIp": ip_clean,
        "userId": f"{actor}@remap.org",
        "userIdNo": f"uuid-{actor}",
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "eventSourceType": "ADMIN_CONSOLE",
        "orgId": "org-remap-001",
        "projectId": "p-remap-001",
        "projectName": "remap-project",
        "appKey": "appkey-remap-001",
        "tenantId": "tenant-remap-001",
        "request": "{}",
        "response": '{"result":"' + ("success" if result == "SUCCESS" else "fail") + '"}',
    }


def is_ncp_action(action: str) -> bool:
    """action 문자열이 NCP 형식인지 (NHN 은 'event_id.' prefix)."""
    return not action.startswith("event_id.")


def main() -> None:
    case_db = json.loads(CASE_DB.read_text(encoding="utf-8"))
    remap_chunks = [c for c in case_db["chunks"] if c["chunk_id"].startswith("CASE-REMAP-")]
    print(f"REMAP chunks: {len(remap_chunks)}")

    summary = []
    for chunk in remap_chunks:
        cid = chunk["chunk_id"]
        csp = chunk.get("csp", "naver")
        actor = (chunk.get("actor", "") or "remap-actor").split(" (")[0]  # 괄호 부가설명 제거
        actor = re.sub(r"[^A-Za-z0-9_\-]", "_", actor)[:32] or "remap-actor"
        default_date = parse_window_date(chunk.get("time_window", ""))

        events = []
        timeline = chunk.get("timeline", [])
        for idx, ev in enumerate(timeline):
            ev_actor = ev.get("actor", actor)
            ev_actor = re.sub(r"[^A-Za-z0-9_@\-\.]", "_", ev_actor)[:32]
            action = ev.get("action", "")
            result = ev.get("result", "SUCCESS")
            ip = ev.get("ip", "")
            ncp_str, iso = parse_time(ev.get("time", ""), default_date)

            if is_ncp_action(action):
                events.append(make_ncp_event(ev_actor, action, result, ip, ncp_str, idx))
            else:
                events.append(make_nhn_event(ev_actor, action, result, ip, iso))

        out_path = OUT_DIR / f"{cid}.json"
        out_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
        ncp_count = sum(1 for e in events if "action" in e and "content" in e)
        nhn_count = sum(1 for e in events if "eventId" in e)
        summary.append((cid, csp, len(events), ncp_count, nhn_count, out_path.name))
        print(f"  {cid:<40} csp={csp:<6} events={len(events)} (NCP={ncp_count}, NHN={nhn_count})")

    # 요약 인덱스 파일
    index = {
        "_status": "generated",
        "_generator": "scripts/synthesize_remap_logs.py",
        "_source": "backend/data/kb/case_db.json (CASE-REMAP-*)",
        "files": [
            {
                "chunk_id": cid,
                "csp": csp,
                "event_count": n,
                "ncp_events": ncp,
                "nhn_events": nhn,
                "filename": fn,
            }
            for cid, csp, n, ncp, nhn, fn in summary
        ],
    }
    (OUT_DIR / "_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal: {len(summary)} files, total events: {sum(s[2] for s in summary)}")
    print(f"Index: {OUT_DIR}/_index.json")


if __name__ == "__main__":
    main()
