"""합성 로그 21종 전수 E2E — 각 사고유형 × CSP 조합별 파이프라인 검증 (2026-05-24).

backend/data/synthetic/ 의 21개 .json 합성 로그를 각각 신규 케이스로 업로드 →
OCSF 정규화 → ATT&CK 매핑 → 갭 감지까지 통과시키고 핵심 지표를 수집한다.

사용 전제:
  - uvicorn 백엔드(http://localhost:8000) 가 떠 있어야 함.
  - 각 케이스는 독립된 caseId 로 분리되어 결과가 서로 간섭하지 않음.

실행:
  cd backend && .venv/Scripts/python.exe -X utf8 -m scripts.e2e_synthetic_logs_test
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import requests

B = "http://localhost:8000"
SYNTH_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic"


def _csp_of(name: str) -> str:
    if name.startswith("ncp_"):
        return "naver"
    if name.startswith("nhn_"):
        return "nhn"
    return "all"


def _expected_incident_hint(name: str) -> str:
    """파일명에서 사고유형 힌트 추출 (검증용 가벼운 라벨)."""
    stem = name.replace("ncp_", "").replace("nhn_", "").replace(".json", "")
    mapping = {
        "audit_log_tampering": "AUDIT_LOG_TAMPERING",
        "data_exfiltration": "DATA_EXFILTRATION",
        "privilege_escalation": "PRIVILEGE_ESCALATION",
        "insider_threat": "INSIDER_THREAT",
        "misconfig_exposure": "MISCONFIG_EXPOSURE",
        "phish_initial_access": "PHISH_INITIAL_ACCESS",
        "ransomware": "RANSOMWARE",
        "credential_theft_real": "CREDENTIAL_THEFT",
        "sysdig_8min_killchain": "RANSOMWARE",  # sysdig 시연 시나리오는 ransomware 변종
        "capital_one_style": "DATA_EXFILTRATION",
        "collection": "MIXED",  # 다중 사고유형 혼합 시드
        "none": "NONE",  # 정상 트래픽
    }
    return mapping.get(stem, "UNKNOWN")


def _post_json(path: str, body: dict) -> requests.Response:
    return requests.post(B + path, json=body, timeout=60)


def _run_one(file_path: Path) -> dict:
    """합성 로그 1개를 새 케이스에 업로드 + 정규화 + 매핑 + 갭."""
    name = file_path.name
    csp = _csp_of(name)
    hint = _expected_incident_hint(name)
    out: dict = {"file": name, "csp": csp, "hint": hint, "ok": True, "errors": []}

    # 1) 케이스 생성
    r = _post_json("/api/cases", {
        "incident_type": "UNCLASSIFIED",
        "csp": csp,
        "severity": "high",
        "occurred_at": "2026-05-13T02:30:00",
        "tlp": "AMBER",
        "observables": [],
    })
    if r.status_code not in (200, 201):
        out["ok"] = False
        out["errors"].append(f"케이스 생성 실패 {r.status_code}")
        return out
    cid = r.json()["data"]["caseId"]
    out["caseId"] = cid

    # 2) 로그 업로드
    with open(file_path, "rb") as f:
        r = requests.post(
            f"{B}/api/logs/upload",
            data={"caseId": cid},
            files={"file": (name, f, "application/json")},
            timeout=60,
        )
    if r.status_code not in (200, 201):
        out["ok"] = False
        out["errors"].append(f"업로드 실패 {r.status_code}")
        return out
    upload_data = r.json().get("data", {})
    # API 실제 응답: {totalEvents, matched, unmatched, byTarget, sha256, sourceFile}
    out["raw_inserted"] = upload_data.get("totalEvents", 0)
    out["raw_matched"] = upload_data.get("matched", 0)

    # 3) OCSF 정규화
    r = _post_json("/api/analysis/normalize", {"caseId": cid})
    if r.status_code != 200:
        out["ok"] = False
        out["errors"].append(f"정규화 실패 {r.status_code}")
        return out
    norm = r.json().get("data", {})
    out["normalized"] = norm.get("normalized", 0)
    out["norm_failed"] = norm.get("failed", 0)
    out["norm_rate"] = norm.get("normalizationRate") or norm.get("normalization_rate")

    # 4) ATT&CK 매핑
    r = _post_json("/api/analysis/map", {"caseId": cid})
    if r.status_code != 200:
        out["ok"] = False
        out["errors"].append(f"매핑 실패 {r.status_code}")
        return out
    mp = r.json().get("data", {})
    # API 실제 응답: {total_ocsf, mapped, unmapped, mappingRate, events:[{technique_id, tactic, ...}]}
    out["mapped"] = mp.get("mapped", 0)
    out["map_rate"] = mp.get("mappingRate", 0)
    events = mp.get("events", [])
    out["techniques"] = len({e.get("technique_id") for e in events if e.get("technique_id")})
    out["tactics"] = len({e.get("tactic") for e in events if e.get("tactic")})

    # 5) 갭 감지
    r = _post_json("/api/analysis/gap", {"caseId": cid})
    if r.status_code != 200:
        out["ok"] = False
        out["errors"].append(f"갭 실패 {r.status_code}")
        return out
    gp = r.json().get("data", {})
    # API 실제 응답: {gap_id, gap_type, missing:[...], summary, recommendation, completionRate}
    out["gap_type"] = gp.get("gap_type", "?")
    out["gap_missing"] = len(gp.get("missing", []))
    out["completion"] = gp.get("completionRate", 0)

    return out


def main() -> int:
    if not SYNTH_DIR.exists():
        print(f"[ERROR] 합성 로그 디렉토리 없음: {SYNTH_DIR}")
        return 2

    files = sorted(SYNTH_DIR.glob("*.json"))
    if not files:
        print(f"[ERROR] 합성 로그 파일 없음 ({SYNTH_DIR})")
        return 2

    # 백엔드 라이브니스
    try:
        r = requests.get(B + "/api/health", timeout=3)
        if r.status_code != 200:
            print(f"[ERROR] 백엔드 헬스 실패 ({r.status_code}). uvicorn 기동 후 재시도.")
            return 2
    except Exception as e:
        print(f"[ERROR] 백엔드 미연결 ({e}). cd backend && uvicorn main:app --reload")
        return 2

    print("=" * 88)
    print(f" 합성 로그 21종 전수 E2E — {len(files)}개 파일 · {B}")
    print("=" * 88)
    print(
        f"  {'#':>2}  {'파일':<42} {'CSP':<6} {'사고유형힌트':<22} "
        f"{'raw':>4} {'OCSF':>5} {'mapd':>4} {'tech':>4} {'tac':>3} {'gap':<14} 결과"
    )
    print("  " + "─" * 92)

    passed = 0
    failed_runs: list[dict] = []
    for i, fp in enumerate(files, 1):
        try:
            out = _run_one(fp)
        except Exception as e:
            out = {"file": fp.name, "ok": False, "errors": [f"예외: {e}"]}
        mark = "PASS" if out.get("ok") else "FAIL"
        print(
            f"  {i:>2}  {out['file']:<42} {out.get('csp', '?'):<6} "
            f"{out.get('hint', '?'):<22} "
            f"{out.get('raw_inserted', 0):>4} {out.get('normalized', 0):>5} "
            f"{out.get('mapped', 0):>4} {out.get('techniques', 0):>4} "
            f"{out.get('tactics', 0):>3} {out.get('gap_type', '?'):<14} [{mark}]"
        )
        if out.get("ok"):
            passed += 1
        else:
            failed_runs.append(out)

    print()
    print("=" * 88)
    print(f" 결과: {passed}/{len(files)} PASS")

    # CSP × 사고유형 별 통계
    by_csp: dict[str, list[int]] = {}
    by_hint: dict[str, list[int]] = {}
    for fp in files:
        csp = _csp_of(fp.name)
        hint = _expected_incident_hint(fp.name)
        by_csp.setdefault(csp, [0, 0])
        by_hint.setdefault(hint, [0, 0])

    # (간략화 — 정확한 카운트는 위 루프에서 가능하지만 결과만 빠르게 출력)
    print(" CSP 별 파일 수: " + ", ".join(
        f"{c}={sum(1 for f in files if _csp_of(f.name) == c)}" for c in sorted({_csp_of(f.name) for f in files})
    ))
    print(" 사고유형힌트 별 파일 수: " + ", ".join(
        f"{h}={sum(1 for f in files if _expected_incident_hint(f.name) == h)}"
        for h in sorted({_expected_incident_hint(f.name) for f in files})
    ))

    if failed_runs:
        print(" 실패 항목:")
        for r in failed_runs:
            print(f"   - {r['file']}: {'; '.join(r.get('errors', ['?']))}")
    print("=" * 88)
    return 0 if not failed_runs else 1


if __name__ == "__main__":
    sys.exit(main())
