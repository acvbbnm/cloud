"""전체 파이프라인 통합 진단 — L0~L4 + 공통 엔드포인트 전수 점검.

uvicorn 백엔드(http://localhost:8000) 가 떠 있어야 한다.
각 엔드포인트 호출 결과를 PASS/FAIL 로 수집해 진단 리포트를 출력한다.

사용:  cd backend && .venv/Scripts/python.exe -X utf8 -m scripts.e2e_full_pipeline
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

B = "http://localhost:8000"
SYNTH = Path(__file__).resolve().parents[1] / "data" / "synthetic"

results: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")


def main() -> int:
    print("=" * 72)
    print(" AI Sherpa — 전체 파이프라인 통합 진단 (L0~L4)")
    print("=" * 72)

    # ── Layer 0 — 케이스 ──────────────────────────────────────
    print("\n[Layer 0] 사고 접수")
    r = requests.post(B + "/api/cases", json={
        "incident_type": "UNCLASSIFIED", "csp": "naver", "severity": "high",
        "occurred_at": "2026-05-13T02:30:00", "tlp": "AMBER", "observables": [],
    })
    ok = r.status_code in (200, 201)
    check("POST /api/cases", ok, f"{r.status_code}")
    if not ok:
        print("  케이스 생성 실패 — 중단")
        return 1
    cid = r.json()["data"]["caseId"]

    r = requests.get(f"{B}/api/cases/{cid}")
    check("GET /api/cases/{id}", r.status_code == 200, f"{r.status_code}")

    r = requests.patch(f"{B}/api/cases/{cid}", json={"severity": "critical"})
    check("PATCH /api/cases/{id}", r.status_code == 200, f"{r.status_code}")

    r = requests.get(f"{B}/api/guide/v2", params={"caseId": cid})
    check("GET /api/guide/v2", r.status_code == 200, f"{r.status_code}")

    # ── Layer 1 — 로그 수집 ───────────────────────────────────
    print("\n[Layer 1] 로그 수집")
    log_file = SYNTH / "ncp_collection.json"
    with open(log_file, "rb") as f:
        r = requests.post(f"{B}/api/logs/upload", data={"caseId": cid},
                          files={"file": (log_file.name, f, "application/json")})
    ok = r.status_code in (200, 201)
    check("POST /api/logs/upload", ok, f"{r.status_code}")
    raw_count = 0
    if ok:
        d = r.json().get("data", {})
        raw_count = d.get("inserted") or d.get("total") or d.get("raw_count") or 0

    r = requests.get(f"{B}/api/logs", params={"caseId": cid, "page": 1, "pageSize": 20})
    ok = r.status_code == 200
    items = r.json().get("data", {}).get("items", []) if ok else []
    check("GET /api/logs", ok and len(items) > 0, f"{r.status_code} · {len(items)}건")

    if items:
        ev_id = items[0].get("eventId") or items[0].get("event_id")
        r = requests.get(f"{B}/api/logs/{ev_id}")
        check("GET /api/logs/{id}", r.status_code == 200, f"{r.status_code}")

    # ── Layer 2 — 분석 ────────────────────────────────────────
    print("\n[Layer 2] 분석")
    r = requests.post(B + "/api/analysis/normalize", json={"caseId": cid})
    check("POST /api/analysis/normalize", r.status_code == 200, f"{r.status_code}")

    r = requests.get(B + "/api/analysis/ocsf", params={"caseId": cid})
    check("GET /api/analysis/ocsf", r.status_code == 200, f"{r.status_code}")

    r = requests.post(B + "/api/analysis/map", json={"caseId": cid})
    ok = r.status_code == 200
    check("POST /api/analysis/map", ok, f"{r.status_code}")

    r = requests.get(B + "/api/analysis/attack", params={"caseId": cid})
    ok = r.status_code == 200
    attack_items = r.json().get("data", {}).get("items", []) if ok else []
    check("GET /api/analysis/attack", ok, f"{r.status_code} · {len(attack_items)}건")

    r = requests.post(B + "/api/analysis/gap", json={"caseId": cid})
    check("POST /api/analysis/gap", r.status_code == 200, f"{r.status_code}")

    # ── Layer 4 — 보드 ────────────────────────────────────────
    print("\n[Layer 4] 수사 보드")
    node_ids: list[str] = []
    for i, lbl in enumerate(["초기 침투", "권한 상승"]):
        r = requests.post(B + "/api/board/nodes", json={
            "caseId": cid, "label": lbl, "tactic": "TA0001",
            "technique_id": "T1078", "status": "PENDING",
        })
        ok = r.status_code in (200, 201)
        if ok:
            node_ids.append(r.json()["data"].get("nodeId") or r.json()["data"].get("node_id"))
        check(f"POST /api/board/nodes #{i+1}", ok, f"{r.status_code}")

    if node_ids:
        r = requests.patch(f"{B}/api/board/nodes/{node_ids[0]}", json={"status": "CONFIRMED"})
        check("PATCH /api/board/nodes/{id}", r.status_code == 200, f"{r.status_code}")

    if len(node_ids) >= 2:
        r = requests.post(B + "/api/board/edges", json={
            "caseId": cid, "from_node_id": node_ids[0], "to_node_id": node_ids[1],
        })
        check("POST /api/board/edges", r.status_code in (200, 201), f"{r.status_code}")

    r = requests.get(B + "/api/board", params={"caseId": cid})
    check("GET /api/board", r.status_code == 200, f"{r.status_code}")

    # ── Layer 4 — 보고서 ──────────────────────────────────────
    print("\n[Layer 4] 보고서")
    r = requests.post(B + "/api/report", json={"caseId": cid})
    check("POST /api/report", r.status_code in (200, 201), f"{r.status_code}")

    r = requests.get(f"{B}/api/report/{cid}")
    check("GET /api/report/{id}", r.status_code == 200, f"{r.status_code}")

    r = requests.patch(f"{B}/api/report/{cid}", json={
        "section": "summary", "content": "통합 진단 테스트 요약",
    })
    check("PATCH /api/report/{id}", r.status_code == 200, f"{r.status_code}")

    for fmt in ("docx", "pdf"):
        r = requests.get(f"{B}/api/report/{cid}/export", params={"format": fmt})
        check(f"GET /api/report/export?format={fmt}", r.status_code == 200, f"{r.status_code}")

    # ── Layer 3 — 셰르파 ──────────────────────────────────────
    print("\n[Layer 3] AI 셰르파")
    r = requests.post(B + "/api/sherpa/brief", json={"caseId": cid})
    check("POST /api/sherpa/brief", r.status_code == 200, f"{r.status_code}")

    r = requests.post(B + "/api/sherpa/chat", json={
        "caseId": cid, "query": "이 사고의 초기 침투 경로는?",
    })
    check("POST /api/sherpa/chat", r.status_code == 200, f"{r.status_code}")

    r = requests.post(B + "/api/sherpa/suggest", json={
        "caseId": cid, "nodeA": "n1", "nodeB": "n2",
    })
    check("POST /api/sherpa/suggest", r.status_code == 200, f"{r.status_code}")

    r = requests.post(B + "/api/sherpa/playbook", json={"chain": ["T1078", "T1098"]})
    check("POST /api/sherpa/playbook", r.status_code == 200, f"{r.status_code}")

    r = requests.get(B + "/api/sherpa/kb")
    ok = r.status_code == 200
    kb_n = r.json().get("data", {}).get("total") if ok else None
    check("GET /api/sherpa/kb", ok, f"{r.status_code} · {kb_n} chunks")

    r = requests.get(B + "/api/sherpa/validate-incident-type", params={"caseId": cid})
    check("GET /api/sherpa/validate-incident-type", r.status_code == 200, f"{r.status_code}")

    # ── 공통 ──────────────────────────────────────────────────
    print("\n[공통]")
    r = requests.get(B + "/api/actions", params={"caseId": cid})
    check("GET /api/actions", r.status_code == 200, f"{r.status_code}")

    # ── 결과 요약 ─────────────────────────────────────────────
    print("\n" + "=" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    failed = [(lbl, d) for lbl, ok, d in results if not ok]
    print(f" 결과: {passed}/{total} PASS")
    if failed:
        print(" 실패 항목:")
        for lbl, d in failed:
            print(f"   - {lbl} ({d})")
    print(f" 진단 케이스 ID: {cid}")
    print("=" * 72)
    return 0 if not failed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except requests.exceptions.ConnectionError:
        print("백엔드 연결 실패 — uvicorn 이 http://localhost:8000 에 떠 있는지 확인")
        sys.exit(2)
