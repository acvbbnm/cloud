"""합성 raw 로그 검증 스크립트.

`data/synthetic/*.json` 4종 시나리오를 dev 백엔드의 풀 파이프라인에 통과시켜
설계 의도대로 갭 결과가 나오는지 확인한다.

기대 결과:
  ncp_none       → gap_type = NONE,       completionRate = 100%
  ncp_collection → gap_type = COLLECTION, missing 에 CT-NCP-IAM-003 포함
  nhn_none       → gap_type = NONE,       completionRate = 100%
  nhn_collection → gap_type = COLLECTION, missing 에 CT-NHN-IAM-002 포함

선행 조건:
  - uvicorn 백엔드가 http://localhost:8000 에서 동작 중
  - DB는 init 된 상태 (collection_targets 10건 시드 적재)

사용:
  python -m scripts.verify_synthetic
"""
import json
import sys
import time
from pathlib import Path

import requests

BASE = "http://localhost:8000"
BACKEND_DIR = Path(__file__).resolve().parents[1]
SYNTH_DIR = BACKEND_DIR / "data" / "synthetic"

EXPECTED = {
    "ncp_none": {
        "csp": "naver",
        "gap_type": "NONE",
        "missing_required": [],
    },
    "ncp_collection": {
        "csp": "naver",
        "gap_type": "COLLECTION",
        "missing_required": ["CT-NCP-IAM-003"],
    },
    "nhn_none": {
        "csp": "nhn",
        "gap_type": "NONE",
        "missing_required": [],
    },
    "nhn_collection": {
        "csp": "nhn",
        "gap_type": "COLLECTION",
        "missing_required": ["CT-NHN-IAM-002"],
    },
}


def wait_ready(timeout_s: float = 20.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE}/api/health", timeout=0.5)
            if r.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.3)
    print("[FAIL] server not ready", file=sys.stderr)
    sys.exit(1)


def create_case(csp: str) -> str:
    r = requests.post(
        f"{BASE}/api/cases",
        json={
            "incident_type": "CREDENTIAL_THEFT",
            "csp": csp,
            "severity": "high",
            "occurred_at": "2026-05-13T02:30:00Z",
        },
    )
    assert r.status_code == 201, f"case create failed: {r.status_code} {r.text}"
    return r.json()["data"]["caseId"]


def upload(case_id: str, fixture: Path) -> dict:
    with fixture.open("rb") as f:
        files = {"file": (fixture.name, f, "application/json")}
        data = {"caseId": case_id}
        r = requests.post(f"{BASE}/api/logs/upload", files=files, data=data)
    assert r.status_code in (200, 201), f"upload failed: {r.status_code} {r.text}"
    return r.json()["data"]


def normalize(case_id: str) -> dict:
    r = requests.post(f"{BASE}/api/analysis/normalize", json={"caseId": case_id})
    assert r.status_code == 200, f"normalize failed: {r.status_code} {r.text}"
    return r.json()["data"]


def map_attack(case_id: str) -> dict:
    r = requests.post(f"{BASE}/api/analysis/map", json={"caseId": case_id})
    assert r.status_code == 200, f"map failed: {r.status_code} {r.text}"
    return r.json()["data"]


def gap(case_id: str) -> dict:
    r = requests.post(f"{BASE}/api/analysis/gap", json={"caseId": case_id})
    assert r.status_code == 200, f"gap failed: {r.status_code} {r.text}"
    return r.json()["data"]


def run_scenario(name: str) -> dict:
    expected = EXPECTED[name]
    fixture = SYNTH_DIR / f"{name}.json"
    print(f"\n========== {name} ==========")
    print(f"fixture: {fixture.name}")

    case_id = create_case(expected["csp"])
    print(f"caseId: {case_id}")

    up = upload(case_id, fixture)
    matched = up.get("byTarget", {})
    print(f"upload: total={up.get('totalEvents')} matched={up.get('matched')} unmatched={up.get('unmatched')}")
    print(f"matched targets: {sorted(matched.keys())}")

    nm = normalize(case_id)
    print(f"normalize: total={nm.get('total')} normalized={nm.get('normalized')} failed={nm.get('failed')}")

    mp = map_attack(case_id)
    print(f"attack map: total_ocsf={mp.get('total_ocsf')} mapped={mp.get('mapped')} unmapped={mp.get('unmapped')}")

    gp = gap(case_id)
    print(f"gap_type: {gp.get('gap_type')} completionRate: {gp.get('completionRate')}%")
    missing_ids = [m.get("target_id") for m in (gp.get("missing") or [])]
    print(f"missing required: {missing_ids}")

    # 기대값 대조
    actual_gap = gp.get("gap_type")
    expected_gap = expected["gap_type"]
    ok = actual_gap == expected_gap
    if expected["missing_required"]:
        ok = ok and all(t in missing_ids for t in expected["missing_required"])

    print(f"[{'OK' if ok else 'FAIL'}] expected gap_type={expected_gap}, missing={expected['missing_required']}")
    return {
        "name": name,
        "ok": ok,
        "gap_type": actual_gap,
        "missing": missing_ids,
        "matched": matched,
    }


def main() -> int:
    wait_ready()
    results = []
    for name in EXPECTED.keys():
        results.append(run_scenario(name))

    print("\n========== SUMMARY ==========")
    for r in results:
        flag = "OK" if r["ok"] else "FAIL"
        print(f"  [{flag}] {r['name']}: gap_type={r['gap_type']}, missing={r['missing']}")

    failed = [r for r in results if not r["ok"]]
    if failed:
        print(f"\n[FAIL] {len(failed)} scenario(s) failed", file=sys.stderr)
        return 1
    print("\n[OK] all 4 synthetic scenarios pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
