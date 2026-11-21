"""Phase N 통합 e2e — 프론트 액션별 백엔드 호출 정합 검증 (2026-05-26, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §22.5 + §23

각 액션 = 프론트의 버튼/이벤트 1개 → 백엔드 API 호출 정합 검증.
시연 직전 마지막 회귀 + 향후 추가 변경 시 사용.

검증 대상 (16 단계)
------------------
  1.  POST /api/cases                            — 케이스 생성
  2.  POST /api/clue-tree/start                  — 트리 시작 (cold-start)
  3.  GET  /api/clue-tree/recon-options          — N.1 정찰 옵션
  4.  POST /api/clue-tree/expand (direct_input)  — ReconClueCard 클릭
  5.  POST /api/clue-tree/expand (tree_candidate) — IG 후보 클릭 × 4
  6.  Phase M.1 응답 4 필드 정합 (zone/chain/lk/regress)
  7.  Phase N.4 응답 4 필드 정합 (stage/confirmed/multistage/desc)
  8.  N.2 Floor 1% 확인 — 모든 가설 ≥ 0.005
  9.  attack_chain Kill Chain phase 정합
  10. POST /api/clue-tree/suggest                — 후보 재계산
  11. GET  /api/clue-tree/explain/{clue_key}     — 추천 이유 expand
  12. POST /api/clue-tree/advance-stage          — N.4 Stage 2 진입
  13. POST /api/clue-tree/advance-stage          — Stage 3 (multistage)
  14. advance-stage duplicate → 400
  15. POST /api/report                           — 보고서 multi-stage 섹션
  16. POST /api/clue-tree/reset                  — 트리 초기화

사용
----
    백엔드 실행 중 상태에서:
    cd backend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.e2e_phase_n_buttons_test

종료 코드: 0 (전체 통과) / 1 (실패 1건 이상)
"""
from __future__ import annotations

import sys
from datetime import datetime
from typing import Any
from urllib.parse import quote

import requests


BASE = "http://127.0.0.1:8000"

# 결과 누적
_results: list[tuple[bool, str, str]] = []  # (passed, step_id, detail)
_fail_count = 0


def _log(step: str, passed: bool, detail: str = "") -> None:
    global _fail_count
    if not passed:
        _fail_count += 1
    _results.append((passed, step, detail))
    icon = "✓" if passed else "✗"
    color = "" if passed else "[FAIL] "
    print(f"  {color}{icon} {step:<48} {detail}")


def _check_keys(d: dict, *keys: str) -> tuple[bool, str]:
    missing = [k for k in keys if k not in d]
    if missing:
        return False, f"missing: {missing}"
    return True, ""


def main() -> int:
    print("=" * 80)
    print(" Phase N 통합 e2e — 프론트 액션별 백엔드 호출 정합 검증")
    print(f" 실행 시각: {datetime.now().isoformat(timespec='seconds')}")
    print(f" 대상: {BASE}")
    print("=" * 80)

    # ── 헬스 확인 ──
    try:
        h = requests.get(f"{BASE}/api/health", timeout=5).json()
        assert h["status"] == "ok"
    except Exception as e:
        print(f"[FATAL] 백엔드 헬스 실패: {e}")
        return 2

    # ── 1. 케이스 생성 ──
    print("\n── 1. 케이스 생성 ──")
    r = requests.post(
        f"{BASE}/api/cases",
        json={
            "title": "Phase N buttons e2e",
            "csp": "naver",
            "incident_type": "UNCLASSIFIED",
            "severity": "high",
            "occurred_at": "2026-05-26T15:00:00",
        },
        timeout=10,
    )
    if r.status_code not in (200, 201):
        _log("POST /api/cases", False, f"HTTP {r.status_code}")
        return 1
    case_id = r.json()["data"]["caseId"]
    _log("POST /api/cases", True, f"caseId={case_id[:8]}…  (HTTP {r.status_code})")

    # ── 2. 트리 시작 (cold-start) ──
    print("\n── 2~3. 트리 시작 + 정찰 옵션 ──")
    r = requests.post(
        f"{BASE}/api/clue-tree/start", json={"caseId": case_id}, timeout=10
    )
    data = r.json()["data"]
    ok, err = _check_keys(
        data,
        "tree", "current_leaf_id", "posterior_current", "confidence",
        "candidates", "path", "scoring_mode",
        "zone", "attack_chain", "core_clue_likelihood", "regress_suggested",
        "stage", "confirmed_hypotheses", "is_multistage", "chain_description",
    )
    _log("POST /api/clue-tree/start (응답 15 필드)", ok, err or f"scoring={data['scoring_mode']}")
    _log(
        "  cold-start 상태 (stage=1, confirmed=[], candidates=0)",
        data["stage"] == 1
        and data["confirmed_hypotheses"] == []
        and len(data["candidates"]) == 0,
    )

    # ── 3. recon-options ──
    r = requests.get(f"{BASE}/api/clue-tree/recon-options", timeout=10)
    groups = r.json()["data"]["groups"]
    _log(
        "GET /api/clue-tree/recon-options",
        len(groups) == 2 and groups[0]["node_id"] == "Q1_inception",
        f"{sum(len(g['options']) for g in groups)} 옵션",
    )

    # ── 4. ReconClueCard 클릭 시뮬 (direct_input 정찰 단서) ──
    print("\n── 4~5. ReconClueCard + IG 후보 누적 ──")
    recon_clue = groups[0]["options"][0]["clue_key"]  # Q1_inception:csp_alert
    r = requests.post(
        f"{BASE}/api/clue-tree/expand",
        json={
            "caseId": case_id,
            "parent_node_id": data["current_leaf_id"],
            "clue_key": recon_clue,
            "source": "direct_input",
        },
        timeout=10,
    )
    if r.status_code != 200:
        _log("POST /api/clue-tree/expand (ReconCard)", False, f"HTTP {r.status_code}")
        return 1
    data = r.json()["data"]
    _log(
        f"POST /api/clue-tree/expand (direct_input: {recon_clue})",
        len(data["path"]) == 2 and len(data["candidates"]) > 0,
        f"depth={len(data['path']) - 1}, 후보={len(data['candidates'])}",
    )

    # ── 5. IG 후보 클릭 × 4 ──
    for i in range(4):
        if not data["candidates"]:
            _log(f"  IG candidate #{i + 1}", False, "candidates 비어있음")
            break
        cand = data["candidates"][0]
        r = requests.post(
            f"{BASE}/api/clue-tree/expand",
            json={
                "caseId": case_id,
                "parent_node_id": data["current_leaf_id"],
                "clue_key": cand["clue_key"],
                "source": "tree_candidate",
            },
            timeout=10,
        )
        data = r.json()["data"]
    _log(
        "  IG 후보 클릭 × 4",
        len(data["path"]) >= 5,
        f"depth={len(data['path']) - 1}, zone={data['zone']}, boss_lk={data['core_clue_likelihood']:.3f}",
    )

    # ── 6. Phase M.1 응답 4 필드 정합 ──
    print("\n── 6~9. 응답 필드 정합 + Floor + chain ──")
    m1_ok = (
        isinstance(data["zone"], int)
        and data["zone"] in (1, 2)
        and isinstance(data["attack_chain"], list)
        and isinstance(data["core_clue_likelihood"], (int, float))
        and isinstance(data["regress_suggested"], bool)
    )
    _log(
        "Phase M.1 응답 4 필드 타입 정합",
        m1_ok,
        f"zone={data['zone']}, chain={len(data['attack_chain'])}, regress={data['regress_suggested']}",
    )

    # ── 7. Phase N.4 응답 4 필드 정합 ──
    n4_ok = (
        isinstance(data["stage"], int)
        and isinstance(data["confirmed_hypotheses"], list)
        and isinstance(data["is_multistage"], bool)
        and isinstance(data["chain_description"], str)
    )
    _log(
        "Phase N.4 응답 4 필드 타입 정합",
        n4_ok,
        f"stage={data['stage']}, confirmed={len(data['confirmed_hypotheses'])}",
    )

    # ── 8. N.2 Floor 1% 검증 ──
    posts = data["posterior_current"]
    hyps_8 = [h for h in posts if h != "UNCLASSIFIED"]
    min_p = min(posts[h] for h in hyps_8)
    max_p = max(posts[h] for h in hyps_8)
    _log(
        "N.2 Robust Floor 1% (모든 가설 ≥ 0.005)",
        min_p >= 0.005,
        f"min={min_p:.4f}, max={max_p:.4f}",
    )

    # ── 9. attack_chain Kill Chain 정합 ──
    if data["attack_chain"]:
        phases = [s["kill_chain_phase"] for s in data["attack_chain"]]
        _log(
            "attack_chain Kill Chain phase 오름차순",
            phases == sorted(phases),
            f"phases={phases}",
        )
    else:
        _log("attack_chain (chain 비어있음 — Top 3 없음)", True, "skip")

    # ── 10. suggest_candidates ──
    print("\n── 10~11. suggest + explain ──")
    r = requests.post(
        f"{BASE}/api/clue-tree/suggest", json={"caseId": case_id}, timeout=10
    )
    s_data = r.json()["data"]
    _log(
        "POST /api/clue-tree/suggest (재계산)",
        len(s_data["candidates"]) > 0
        and s_data["current_leaf_id"] == data["current_leaf_id"],
        f"후보={len(s_data['candidates'])}",
    )

    # ── 11. explain_clue ──
    if data["candidates"]:
        clue_key = data["candidates"][0]["clue_key"]
        # ':' 포함 — quote 로 인코딩
        r = requests.get(
            f"{BASE}/api/clue-tree/explain/{quote(clue_key, safe='')}",
            timeout=10,
        )
        if r.status_code == 200:
            ex = r.json()["data"]
            ok, err = _check_keys(ex, "clue_key", "techniques", "confidence", "source")
            _log(
                f"GET /api/clue-tree/explain/{clue_key[:20]}…",
                ok,
                err or f"source={ex['source']}, tech={len(ex['techniques'])}",
            )
        else:
            _log(f"GET /api/clue-tree/explain", False, f"HTTP {r.status_code}")
    else:
        _log("explain (skip — no candidates)", True, "skip")

    # ── 12. advance-stage Stage 2 ──
    print("\n── 12~14. N.4 advance-stage Stage 2·3·duplicate ──")
    # confidence.primary 가 없으면 posterior top 1 사용
    primary = (
        data["confidence"].get("primary")
        or max((h for h in hyps_8), key=lambda h: posts[h])
    )
    r = requests.post(
        f"{BASE}/api/clue-tree/advance-stage",
        json={"caseId": case_id, "confirmed_hypothesis": primary},
        timeout=10,
    )
    if r.status_code != 200:
        _log("POST /api/clue-tree/advance-stage Stage 2", False, f"HTTP {r.status_code}")
        return 1
    data = r.json()["data"]
    _log(
        f"POST /api/clue-tree/advance-stage (Stage 2, {primary})",
        data["stage"] == 2
        and data["confirmed_hypotheses"] == [primary]
        and data["is_multistage"] is False
        and data["posterior_current"][primary] == 0.0,
        f"chain='{data['chain_description']}', anchor freeze OK",
    )

    # ── 13. Stage 3 (multistage) ──
    # Stage 2 의 단서 1-2 채택 후 advance (또는 직접)
    primary2 = (
        data["confidence"].get("primary")
        or max(
            (h for h in data["posterior_current"] if h not in {"UNCLASSIFIED", primary}),
            key=lambda h: data["posterior_current"][h],
        )
    )
    r = requests.post(
        f"{BASE}/api/clue-tree/advance-stage",
        json={"caseId": case_id, "confirmed_hypothesis": primary2},
        timeout=10,
    )
    data = r.json()["data"]
    _log(
        f"POST /api/clue-tree/advance-stage (Stage 3, {primary2})",
        data["stage"] == 3
        and data["is_multistage"] is True
        and len(data["confirmed_hypotheses"]) == 2,
        f"chain='{data['chain_description']}'",
    )

    # ── 14. advance-stage duplicate (400 기대) ──
    r = requests.post(
        f"{BASE}/api/clue-tree/advance-stage",
        json={"caseId": case_id, "confirmed_hypothesis": primary},
        timeout=10,
    )
    _log(
        f"POST /api/clue-tree/advance-stage duplicate ({primary})",
        r.status_code == 400,
        f"HTTP {r.status_code}",
    )

    # ── 15. POST /api/report — multi-stage 섹션 확인 ──
    print("\n── 15. V-7 보고서 multi-stage 섹션 ──")
    # regenerate=True — 캐시 무시하고 새로 생성 (advance-stage 후 multi-stage 섹션 반영)
    r = requests.post(
        f"{BASE}/api/report",
        json={"caseId": case_id, "regenerate": True},
        timeout=15,
    )
    if r.status_code not in (200, 201):
        _log("POST /api/report", False, f"HTTP {r.status_code}")
    else:
        rep_data = r.json()["data"]
        # overview 가 dict 일 수도 / str 일 수도 — 보고서 구조 다양
        overview_blob = rep_data.get("overview", "") or rep_data.get("sections", {}).get(
            "overview", ""
        )
        # 모든 필드를 JSON 문자열화하여 검색 (안전)
        import json as _json
        full_text = _json.dumps(rep_data, ensure_ascii=False)
        has_chain = "다단계 공격" in full_text or "Multi-Stage" in full_text
        _log(
            "POST /api/report (multi-stage 섹션 포함)",
            has_chain,
            f"HTTP {r.status_code} · MultiStage 섹션 발견" if has_chain else f"HTTP {r.status_code} · 섹션 누락!",
        )

    # ── 16. reset 트리 ──
    print("\n── 16. reset 트리 ──")
    r = requests.post(
        f"{BASE}/api/clue-tree/reset", json={"caseId": case_id}, timeout=10
    )
    data = r.json()["data"]
    _log(
        "POST /api/clue-tree/reset (cold-start 복귀)",
        data["stage"] == 1
        and data["confirmed_hypotheses"] == []
        and len(data["candidates"]) == 0,
        f"stage={data['stage']}, depth={len(data['path']) - 1}",
    )

    # ── 추가: 잘못된 단서 키 → 400 ──
    r = requests.post(
        f"{BASE}/api/clue-tree/expand",
        json={
            "caseId": case_id,
            "parent_node_id": data["current_leaf_id"],
            "clue_key": "INVALID:nope",
        },
        timeout=10,
    )
    _log(
        "POST /api/clue-tree/expand invalid clue → 400",
        r.status_code == 400,
        f"HTTP {r.status_code}",
    )

    # ── 종합 ──
    print()
    print("=" * 80)
    print(" 종합 결과")
    print("=" * 80)
    total = len(_results)
    passed = total - _fail_count
    print(f" PASS: {passed}/{total}")
    if _fail_count > 0:
        print(f" FAIL: {_fail_count}")
        print()
        print(" 실패 상세:")
        for ok, step, detail in _results:
            if not ok:
                print(f"   ✗ {step} — {detail}")
        return 1

    print(" ✓ 모든 액션 정합 통과 — 시연 준비 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
