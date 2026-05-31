"""V-1 Setup 필드 매핑 회귀 e2e (V1.fix.3, 2026-05-31 byungwoo).

배경
----
Step 1 (케이스 메타) ↔ Step 2 (시스템 구성) 사이의 중복 입력·dead 8필드 사각지대 차단.
이전 e2e 들 (Phase M/N/O) 은 Step 3 Evidence Tree 이후만 검증했고, V-1 form → API
필드 매핑은 사각지대였음 (사용자 검증 2026-05-31).

검증 항목
----------
    1. POST /api/cases — Step 1 의 4필드 (title/severity/tlp/occurred_at) 영속화
    2. PATCH /api/cases/{id} — Step 2 의 system_config 21필드 영속화
        ① environment_modifiers 트리거 13필드 (auditEnabled, mfa_status, …)
        ② V1.fix.2 부가 메타 8필드 (investigator/memo/detection_route/os_type/
           server_role/server_count/scope_vpc/scope_resources)
    3. PATCH 에 severity 가 없어도 (V1.fix.1) Step 1 의 severity 가 보존됨
    4. PATCH 에 occurred_at 누락 — Step 1 의 occurred_at 그대로 유지

사용
----
    백엔드 8000 떠있는 상태에서:
        cd backend && .venv/Scripts/python.exe -X utf8 -m scripts.e2e_v1_setup_field_mapping

종료 코드
--------
    0  통과 · 1 실패
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from urllib import error, request


API_BASE = "http://localhost:8000/api"


def _http(method: str, path: str, body: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = request.Request(API_BASE + path, data=data, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as e:
        print(f"[HTTP {e.code}] {method} {path}")
        print(e.read().decode("utf-8", errors="replace"))
        raise


def _expect(actual, expected, label: str, fails: list[str]) -> None:
    if actual != expected:
        fails.append(f"{label}: 기대={expected!r}, 실제={actual!r}")
        print(f"  ✗ {label}: 기대={expected!r}, 실제={actual!r}")
    else:
        print(f"  ✓ {label}")


def main() -> int:
    print("=" * 78)
    print(" V-1 Setup 필드 매핑 회귀 e2e (V1.fix.1 + V1.fix.2)")
    print("=" * 78)
    fails: list[str] = []

    # ── 헬스 ──
    try:
        h = _http("GET", "/health")
        if h.get("status") != "ok":
            print("✗ 백엔드 헬스 실패")
            return 1
    except Exception as e:
        print(f"✗ 백엔드 연결 실패: {e}")
        return 1
    print("✓ 백엔드 연결\n")

    # ── 1) POST /api/cases — Step 1 4필드 ──
    occurred = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    step1_body = {
        "incident_type": "UNCLASSIFIED",
        "csp": "naver",
        "severity": "high",
        "occurred_at": occurred,
        "title": "V1.fix e2e — 케이스 메타 4필드",
        "tlp": "AMBER",
        "observables": [],
    }
    print("[1] POST /api/cases — Step 1 케이스 메타 4필드 영속화")
    created = _http("POST", "/cases", step1_body)["data"]
    case_id = created["caseId"]
    _expect(created["title"], step1_body["title"], "title", fails)
    _expect(created["severity"], "high", "severity (Step 1)", fails)
    _expect(created["tlp"], "AMBER", "tlp", fails)
    _expect(created["incident_type"], "UNCLASSIFIED", "incident_type", fails)
    # occurred_at 은 timezone 정규화 가능성 → ISO 부분만 비교 (yyyy-mm-ddTHH:MM)
    _expect(created["occurred_at"][:16], occurred[:16], "occurred_at (분 단위)", fails)
    print(f"  → caseId={case_id[:12]}…\n")

    # ── 2) PATCH — Step 2 system_config 21필드 ──
    step2_config = {
        # environment_modifiers 트리거 13필드
        "vpc_id": "vpc-prod-01",
        "region": "KR (한국)",
        "services": ["Object Storage", "Cloud DB"],
        "network": "VPC + ACG + NACL 모두 적용",
        "publicIp": "있음 (서버 직접 할당)",
        "auditEnabled": "활성화 (정상 수집 중)",
        "scope": "admin-user, svc-backup",
        "mfa_status": "미적용",
        "iam_account_count": 75,
        "audit_log_retention_days": 30,
        "data_sensitivity": "있음 (개인정보·민감정보)",
        "sso_enabled": "있음 (외부 IdP 연동)",
        "multi_cloud": "없음",
        # V1.fix.2 부가 메타 8필드
        "investigator": "홍길동",
        "memo": "야간 SIEM 알럿으로 인지. Sub Account 신규 생성 의심.",
        "detection_route": "SIEM 알럿",
        "os_type": "Ubuntu 22.04",
        "server_role": "WAS (Application)",
        "server_count": 12,
        "scope_vpc": "vpc-prod-01 / 172.16.0.0/24",
        "scope_resources": "Object Storage (bucket-finance-2026), Sub Account IAM",
    }
    print("[2] PATCH /api/cases/{id} — Step 2 system_config 21필드 영속화")
    patched = _http(
        "PATCH",
        f"/cases/{case_id}",
        {"system_config": step2_config},  # ← V1.fix.1: severity 안 넣음
    )["data"]
    sc = patched["system_config"] or {}
    # environment_modifiers 트리거 13필드
    for k in [
        "vpc_id", "region", "services", "network", "publicIp", "auditEnabled",
        "scope", "mfa_status", "iam_account_count", "audit_log_retention_days",
        "data_sensitivity", "sso_enabled", "multi_cloud",
    ]:
        _expect(sc.get(k), step2_config[k], f"trigger.{k}", fails)
    # V1.fix.2 부가 메타 8필드
    for k in [
        "investigator", "memo", "detection_route", "os_type",
        "server_role", "server_count", "scope_vpc", "scope_resources",
    ]:
        _expect(sc.get(k), step2_config[k], f"meta.{k}", fails)
    print()

    # ── 3) Step 1 severity 가 PATCH 후에도 보존 ──
    print("[3] V1.fix.1 — Step 2 PATCH 에 severity 없어도 Step 1 의 'high' 보존")
    _expect(patched["severity"], "high", "severity 보존", fails)
    # occurred_at 도 PATCH 페이로드에 없으니 그대로
    _expect(
        patched["occurred_at"][:16], occurred[:16],
        "occurred_at 보존 (Step 2 dead-input 차단)", fails,
    )
    print()

    # ── 4) GET 으로 한 번 더 확인 (round-trip) ──
    print("[4] GET /api/cases/{id} — round-trip 확인")
    got = _http("GET", f"/cases/{case_id}")["data"]
    sc = got["system_config"] or {}
    _expect(sc.get("mfa_status"), "미적용", "trigger.mfa_status (round-trip)", fails)
    _expect(sc.get("investigator"), "홍길동", "meta.investigator (round-trip)", fails)
    _expect(got["severity"], "high", "severity (round-trip)", fails)

    # ── 종합 ──
    print()
    print("=" * 78)
    if fails:
        print(f" ✗ V1.fix 회귀 실패 — {len(fails)} 건")
        for f in fails:
            print(f"   - {f}")
        return 1
    print(" ✓ V1.fix.1 + V1.fix.2 회귀 모두 통과 (21 필드 매핑 OK)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
