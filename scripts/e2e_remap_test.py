"""REMAP 시나리오 4편 E2E 테스트.

각 시나리오마다:
1. POST /api/cases (사고유형: UNCLASSIFIED — 트리아지로 분류되는지 검증)
2. POST /api/logs/upload (synthesize_remap_logs.py 산출물)
3. POST /api/analysis/normalize
4. POST /api/analysis/map
5. POST /api/analysis/gap
6. GET /api/analysis/attack
7. GET /api/board
8. GET /api/sherpa/validate-incident-type (사후 검증으로 분류 정확도 평가)

결과: data/test_logs/remap/e2e_report.json 에 저장.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "data" / "test_logs" / "remap"
API = "http://127.0.0.1:8000"

# 4개 대표 시나리오 — 각 신규 사고유형 + 다양한 CSP
SCENARIOS = [
    {
        "chunk_id": "CASE-REMAP-NCP-RANSOM-001",
        "expected_incident_type": "RANSOMWARE",
        "csp": "naver",
        "title": "[E2E] Colonial Pipeline 2021 역매핑 (RANSOMWARE / NCP)",
        "severity": "critical",
        "occurred_at": "2026-05-07T02:10:00Z",
    },
    {
        "chunk_id": "CASE-REMAP-NHN-MISCFG-001",
        "expected_incident_type": "MISCONFIG_EXPOSURE",
        "csp": "nhn",
        "title": "[E2E] Verkada 2021 역매핑 (MISCONFIG_EXPOSURE / NHN)",
        "severity": "high",
        "occurred_at": "2026-05-10T11:08:00Z",
    },
    {
        "chunk_id": "CASE-REMAP-NCP-PHISH-001",
        "expected_incident_type": "PHISH_INITIAL_ACCESS",
        "csp": "naver",
        "title": "[E2E] Twilio 0ktapus 2022 역매핑 (PHISH_INITIAL_ACCESS / NCP)",
        "severity": "high",
        "occurred_at": "2026-05-11T08:15:00Z",
    },
    {
        "chunk_id": "CASE-REMAP-NHN-INSIDER-001",
        "expected_incident_type": "INSIDER_THREAT",
        "csp": "nhn",
        "title": "[E2E] Coinbase 2023 역매핑 (INSIDER_THREAT / NHN)",
        "severity": "high",
        "occurred_at": "2026-05-14T22:48:00Z",
    },
]


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def run_scenario(s: dict) -> dict:
    cid = s["chunk_id"]
    print(f"\n=== {cid} (expected={s['expected_incident_type']}, csp={s['csp']}) ===", flush=True)
    result = {"chunk_id": cid, "expected": s["expected_incident_type"], "csp": s["csp"], "steps": {}}

    # 1) Create case (UNCLASSIFIED — let triage classify it)
    payload = {
        "incident_type": "UNCLASSIFIED",
        "csp": s["csp"],
        "severity": s["severity"],
        "occurred_at": s["occurred_at"],
        "title": s["title"],
        "tlp": "AMBER",
    }
    try:
        r = requests.post(f"{API}/api/cases", json=payload, timeout=10)
        r.raise_for_status()
        case_id = r.json()["data"]["caseId"]
        result["steps"]["1_create"] = {"status": "ok", "caseId": case_id, "http": r.status_code}
        log(f"1) POST /api/cases → {r.status_code}, caseId={case_id[:8]}...")
    except Exception as e:
        result["steps"]["1_create"] = {"status": "error", "error": str(e)[:300]}
        log(f"1) POST /api/cases FAIL: {e}")
        return result

    # 2) Upload raw log file
    log_path = LOG_DIR / f"{cid}.json"
    try:
        with open(log_path, "rb") as f:
            files = {"file": (log_path.name, f, "application/json")}
            data = {"caseId": case_id}
            r = requests.post(f"{API}/api/logs/upload", data=data, files=files, timeout=15)
        r.raise_for_status()
        stats = r.json()["data"]
        result["steps"]["2_upload"] = {"status": "ok", "http": r.status_code, "stats": stats}
        log(f"2) POST /api/logs/upload → {r.status_code}, parsed={stats.get('parsed_count', '?')}, matched={stats.get('matched_count', '?')}")
    except Exception as e:
        result["steps"]["2_upload"] = {"status": "error", "error": str(e)[:300], "http": getattr(r, "status_code", None)}
        log(f"2) POST /api/logs/upload FAIL: {e}")
        return result

    # 3) Normalize
    try:
        r = requests.post(f"{API}/api/analysis/normalize", json={"caseId": case_id}, timeout=30)
        r.raise_for_status()
        result["steps"]["3_normalize"] = {"status": "ok", "http": r.status_code, "data": r.json().get("data")}
        log(f"3) POST /api/analysis/normalize → {r.status_code}, {r.json().get('data')}")
    except Exception as e:
        result["steps"]["3_normalize"] = {"status": "error", "error": str(e)[:300], "http": getattr(r, "status_code", None)}
        log(f"3) normalize FAIL: {e}")

    # 4) Map
    try:
        r = requests.post(f"{API}/api/analysis/map", json={"caseId": case_id}, timeout=30)
        r.raise_for_status()
        result["steps"]["4_map"] = {"status": "ok", "http": r.status_code, "data": r.json().get("data")}
        log(f"4) POST /api/analysis/map → {r.status_code}, {r.json().get('data')}")
    except Exception as e:
        result["steps"]["4_map"] = {"status": "error", "error": str(e)[:300], "http": getattr(r, "status_code", None)}
        log(f"4) map FAIL: {e}")

    # 5) Gap
    try:
        r = requests.post(f"{API}/api/analysis/gap", json={"caseId": case_id}, timeout=15)
        r.raise_for_status()
        result["steps"]["5_gap"] = {"status": "ok", "http": r.status_code, "data": r.json().get("data")}
        log(f"5) POST /api/analysis/gap → {r.status_code}, {r.json().get('data')}")
    except Exception as e:
        result["steps"]["5_gap"] = {"status": "error", "error": str(e)[:300], "http": getattr(r, "status_code", None)}
        log(f"5) gap FAIL: {e}")

    # 6) Get attack events (count by tactic)
    try:
        r = requests.get(f"{API}/api/analysis/attack", params={"caseId": case_id}, timeout=10)
        r.raise_for_status()
        atk = r.json()["data"]
        items = atk.get("items", []) if isinstance(atk, dict) else atk
        # tactic distribution
        from collections import Counter
        tac = Counter(it.get("tactic", "?") for it in items)
        result["steps"]["6_attack"] = {"status": "ok", "http": r.status_code, "total": len(items), "tactic_dist": dict(tac)}
        log(f"6) GET /api/analysis/attack → {r.status_code}, attack events={len(items)}, tactics={dict(tac)}")
    except Exception as e:
        result["steps"]["6_attack"] = {"status": "error", "error": str(e)[:300], "http": getattr(r, "status_code", None)}
        log(f"6) attack FAIL: {e}")

    # 7) Get board
    try:
        r = requests.get(f"{API}/api/board", params={"caseId": case_id}, timeout=10)
        r.raise_for_status()
        bd = r.json()["data"]
        result["steps"]["7_board"] = {"status": "ok", "http": r.status_code,
                                       "nodes": len(bd.get("nodes", [])), "edges": len(bd.get("edges", []))}
        log(f"7) GET /api/board → {r.status_code}, nodes={len(bd.get('nodes', []))}, edges={len(bd.get('edges', []))}")
    except Exception as e:
        result["steps"]["7_board"] = {"status": "error", "error": str(e)[:300], "http": getattr(r, "status_code", None)}
        log(f"7) board FAIL: {e}")

    # 8) Sherpa validate-incident-type — 핵심 검증: 사고유형 자동 분류 정확도
    try:
        r = requests.get(f"{API}/api/sherpa/validate-incident-type",
                         params={"caseId": case_id}, timeout=15)
        r.raise_for_status()
        v = r.json()["data"]
        result["steps"]["8_validate"] = {"status": "ok", "http": r.status_code, "data": v}
        ranked = v.get("ranked_hypotheses", []) or v.get("hypothesis_scores", [])
        verdict = v.get("verdict") or v.get("primary_incident_type")
        log(f"8) GET /api/sherpa/validate-incident-type → {r.status_code}")
        log(f"   verdict={verdict}, top hypotheses: {ranked[:3] if ranked else '(empty)'}")
    except Exception as e:
        result["steps"]["8_validate"] = {"status": "error", "error": str(e)[:300], "http": getattr(r, "status_code", None)}
        log(f"8) validate FAIL: {e}")

    return result


def main() -> None:
    print(f"E2E REMAP test — {len(SCENARIOS)} scenarios", flush=True)
    print(f"API: {API}", flush=True)
    print(f"Log dir: {LOG_DIR}", flush=True)

    # Health check
    try:
        h = requests.get(f"{API}/api/health", timeout=5).json()
        print(f"Health: {h.get('status')} server={h['data'].get('server')} db={h['data'].get('db')}", flush=True)
    except Exception as e:
        print(f"Health check FAIL: {e}", flush=True)
        sys.exit(1)

    results = []
    for s in SCENARIOS:
        results.append(run_scenario(s))
        time.sleep(0.5)

    # Summary
    print("\n\n=== SUMMARY ===", flush=True)
    for r in results:
        ok = sum(1 for s in r["steps"].values() if s.get("status") == "ok")
        total = len(r["steps"])
        print(f"  {r['chunk_id']:<40} steps={ok}/{total}", flush=True)
        if "8_validate" in r["steps"] and r["steps"]["8_validate"].get("status") == "ok":
            v = r["steps"]["8_validate"]["data"]
            verdict = v.get("verdict") or v.get("primary_incident_type") or "?"
            expected = r["expected"]
            match = "✓" if verdict == expected else "✗"
            print(f"     {match} expected={expected:<22} verdict={verdict}", flush=True)

    out = LOG_DIR / "e2e_report.json"
    out.write_text(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "results": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport: {out}", flush=True)


if __name__ == "__main__":
    main()
