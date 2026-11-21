"""E4 결정 트리 종합 시나리오 검증 — 30+ 경우의 수 (2026-05-24 확장).

E4 6단계 결정 트리의 모든 분기·진입 경로·종착 사고유형 조합을 결정론적으로 검증.
각 사고유형 lane (CRED/RANSOM/MISCFG/INSIDER) 마다 다중 Q1 진입 × 다중 Q4-6 조합.

설계 원칙:
  - HTTP 서버 불필요 — `core.intake.triage.Triage` 직접 호출 (폐쇄망·고속).
  - 결정성 100% — 같은 답변 시퀀스 → 같은 점수.
  - lane 별 기대 우승 사고유형 + outcome 검증.

사용: cd backend && .venv/Scripts/python.exe -X utf8 -m scripts.e2e_tree_e4_test
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from core.intake.triage import (  # noqa: E402
    Triage,
    _initial_scores,
    evaluate_recommendation,
    invalidate_cache,
)

# ─────────────────────────────────────────────────────────────
# Lane × 진입경로 × 종착경로 매트릭스
# ─────────────────────────────────────────────────────────────

# CRED lane — Q1 다양한 진입에서 Q3_CRED 로 수렴, Q4-6 자격증명 패턴
CRED_ENTRIES = [
    ("CSP알람·비정상로그인+비국내IP", [
        ("Q1_inception", ["csp_alert"]),
        ("Q2A_alert_type", ["abnormal_login", "non_korean_ip"]),
        ("Q3_CRED", ["fail_then_success"]),
    ]),
    ("CSP알람·권한변경", [
        ("Q1_inception", ["csp_alert"]),
        ("Q2A_alert_type", ["privilege_change"]),
        ("Q3_CRED", ["multi_region_concurrent"]),
    ]),
    ("외부신고·신원도용", [
        ("Q1_inception", ["external_report"]),
        ("Q2B_report_content", ["identity_theft"]),
        ("Q3_CRED", ["fail_then_success"]),
    ]),
    ("외부신고·피싱제보", [
        ("Q1_inception", ["external_report"]),
        ("Q2B_report_content", ["phishing_report"]),
        ("Q3_CRED", ["non_korean_geographic"]),
    ]),
]
CRED_TAILS = [
    ("MFA토큰재사용→Tor→권한변경", [
        ("Q4_CRED", ["mfa_token_reuse"]),
        ("Q5_CRED", ["tor_vpn"]),
        ("Q6_CRED", ["priv_change"]),
    ]),
    ("MFA등록변경→비국내IP→다운로드", [
        ("Q4_CRED", ["mfa_registration_change"]),
        ("Q5_CRED", ["non_korean_ip"]),
        ("Q6_CRED", ["storage_download"]),
    ]),
    ("MFA미적용→사내IP→후속없음", [
        ("Q4_CRED", ["mfa_not_applied"]),
        ("Q5_CRED", ["internal_ip"]),
        ("Q6_CRED", ["no_follow"]),
    ]),
]

# RANSOM lane — 서비스이상 또는 외부 랜섬노트 제보 → Q3_IMPACT → RANSOM 종착
RANSOM_ENTRIES = [
    ("서비스이상·데이터파괴", [
        ("Q1_inception", ["service_anomaly"]),
        ("Q2D_anomaly_form", ["data_destruction"]),
        ("Q3_IMPACT", ["mass_encrypt"]),
    ]),
    ("서비스이상·대량암호화", [
        ("Q1_inception", ["service_anomaly"]),
        ("Q2D_anomaly_form", ["mass_encryption"]),
        ("Q3_IMPACT", ["backup_deletion"]),
    ]),
    ("외부신고·랜섬노트", [
        ("Q1_inception", ["external_report"]),
        ("Q2B_report_content", ["ransom_note_visible"]),
        ("Q3_IMPACT", ["mass_encrypt"]),
    ]),
]
RANSOM_TAILS = [
    ("백업파괴→스토리지전체→노트발견", [
        ("Q4_RANSOM", ["backup_destroyed"]),
        ("Q5_RANSOM", ["storage_wide"]),
        ("Q6_RANSOM", ["note_found"]),
    ]),
    ("백업정상→단일인스턴스→이중협박", [
        ("Q4_RANSOM", ["backup_intact"]),
        ("Q5_RANSOM", ["single_instance"]),
        ("Q6_RANSOM", ["double_extortion"]),
    ]),
    ("백업없음→멀티리전→노트없음", [
        ("Q4_RANSOM", ["backup_missing"]),
        ("Q5_RANSOM", ["multi_region"]),
        ("Q6_RANSOM", ["no_note"]),
    ]),
]

# MISCFG lane — 외부 신고·데이터 노출 → Q3_DATA → Q4_MISCFG → MISCFG 종착
MISCFG_ENTRIES = [
    ("외부신고·데이터노출·정책public", [
        ("Q1_inception", ["external_report"]),
        ("Q2B_report_content", ["data_exposed"]),
        ("Q3_DATA", ["storage_policy_public"]),
    ]),
    ("외부신고·데이터노출·S3credential변경", [
        ("Q1_inception", ["external_report"]),
        ("Q2B_report_content", ["data_exposed"]),
        ("Q3_DATA", ["s3_credential_change"]),
    ]),
]
MISCFG_TAILS = [
    ("장기노출→운영자→PII", [
        ("Q4_MISCFG", ["long_term_public"]),
        ("Q5_MISCFG", ["operator"]),
        ("Q6_MISCFG", ["pii"]),
    ]),
    ("단기노출→비정상IP→영업비밀", [
        ("Q4_MISCFG", ["short_term_public"]),
        ("Q5_MISCFG", ["abnormal_ip"]),
        ("Q6_MISCFG", ["trade_secret"]),
    ]),
    ("시점불명→자동화스크립트→일반", [
        ("Q4_MISCFG", ["timing_unknown"]),
        ("Q5_MISCFG", ["automation_script"]),
        ("Q6_MISCFG", ["general"]),
    ]),
]

# INSIDER lane — 정기 감사 또는 내부자 의심 제보 → Q3_INSIDER → INSIDER 종착
INSIDER_ENTRIES = [
    ("정기감사·권한변경다수", [
        ("Q1_inception", ["audit"]),
        ("Q2C_audit_pattern", ["permission_changes"]),
        ("Q3_INSIDER", ["off_hours_priv"]),
    ]),
    ("정기감사·IAM신규다수", [
        ("Q1_inception", ["audit"]),
        ("Q2C_audit_pattern", ["iam_burst"]),
        ("Q3_INSIDER", ["multiple_iam_changes"]),
    ]),
    ("정기감사·로그누락", [
        ("Q1_inception", ["audit"]),
        ("Q2C_audit_pattern", ["log_gap"]),
        ("Q3_INSIDER", ["self_audit_disable"]),
    ]),
    ("외부신고·내부자익명제보", [
        ("Q1_inception", ["external_report"]),
        ("Q2B_report_content", ["insider_complaint"]),
        ("Q3_INSIDER", ["gradual_priv_creep"]),
    ]),
]
INSIDER_TAILS = [
    ("직무초과→사내+VPN→IAM자기삭제", [
        ("Q4_INSIDER", ["scope_excess"]),
        ("Q5_INSIDER", ["internal_vpn"]),
        ("Q6_INSIDER", ["iam_self_delete"]),
    ]),
    ("협력사계정→흔적삭제→외부전송", [
        ("Q4_INSIDER", ["partner_account"]),
        ("Q5_INSIDER", ["trace_deletion"]),
        ("Q6_INSIDER", ["data_external"]),
    ]),
    ("직무내(정상)→사내단말→정상종료", [
        ("Q4_INSIDER", ["scope_within"]),
        ("Q5_INSIDER", ["internal_endpoint"]),
        ("Q6_INSIDER", ["normal_exit"]),
    ]),
]

# ─────────────────────────────────────────────────────────────
# 시나리오 빌더 — lane × entry × tail 카르테시안 곱
# ─────────────────────────────────────────────────────────────


def _build_lane_scenarios(
    lane: str,
    entries: list[tuple[str, list]],
    tails: list[tuple[str, list]],
    expected_winner: str,
) -> list[dict]:
    """lane 의 entry × tail 곱 → 시나리오 리스트.

    Tail 인덱스로 outcome 강도 분류:
      - T1 (강): 결정적 시그널 → auto_confirm/propose_composite
      - T2 (중): 보조 시그널 → auto_confirm OR propose_single OR propose_composite
      - T3 (약): 약한·정상 시그널 → propose_single OR continue_or_skip OR propose_composite
    """
    # T1 = 가장 강한 tail, T3 = 가장 약한 tail (정상·후속없음 등)
    TAIL_STRENGTH_OUTCOMES = {
        1: {"auto_confirm", "propose_composite"},
        2: {"auto_confirm", "propose_single", "propose_composite"},
        # T3 (약한 tail) — 단, RANSOM 은 파괴적 영향이 본질이므로 weak tail 도 auto_confirm 가능
        3: {"auto_confirm", "propose_single", "continue_or_skip", "propose_composite"},
    }
    scenarios = []
    for ei, (ename, esteps) in enumerate(entries, 1):
        for ti, (tname, tsteps) in enumerate(tails, 1):
            scenarios.append({
                "id": f"{lane}-E{ei}T{ti}",
                "name": f"{lane}: {ename} + {tname}",
                "steps": esteps + tsteps,
                "expect_winner": expected_winner,
                "expect_outcomes": TAIL_STRENGTH_OUTCOMES[ti],
            })
    return scenarios


# ─────────────────────────────────────────────────────────────
# 특수 경로 시나리오 (짧은 경로·terminal·UNCLASSIFIED)
# ─────────────────────────────────────────────────────────────

SPECIAL_SCENARIOS: list[dict] = [
    {
        "id": "SHORT-CRED-unknown",
        "name": "CRED 단축경로 (Q3 unknown_extra)",
        "steps": [
            ("Q1_inception", ["csp_alert"]),
            ("Q2A_alert_type", ["abnormal_login"]),
            ("Q3_CRED", ["unknown_extra"]),
        ],
        # 짧은 경로는 점수 낮음 — outcome 무관, 그저 에러 없이 통과 확인
        "expect_no_error": True,
    },
    {
        "id": "SHORT-DATA-unknown",
        "name": "DATA 단축경로 (Q3_DATA unknown_extra)",
        "steps": [
            ("Q1_inception", ["external_report"]),
            ("Q2B_report_content", ["data_exposed"]),
            ("Q3_DATA", ["unknown_extra"]),
        ],
        "expect_no_error": True,
    },
    {
        "id": "SHORT-INSIDER-unknown",
        "name": "INSIDER 단축경로 (Q3_INSIDER unknown_extra)",
        "steps": [
            ("Q1_inception", ["audit"]),
            ("Q2C_audit_pattern", ["permission_changes"]),
            ("Q3_INSIDER", ["unknown_extra"]),
        ],
        "expect_no_error": True,
    },
    {
        "id": "SHORT-IMPACT-unknown",
        "name": "IMPACT 단축경로 (Q3_IMPACT unknown_extra)",
        "steps": [
            ("Q1_inception", ["service_anomaly"]),
            ("Q2D_anomaly_form", ["data_destruction"]),
            ("Q3_IMPACT", ["unknown_extra"]),
        ],
        "expect_no_error": True,
    },
    {
        "id": "TERM-unknown",
        "name": "출처 불명 → Q2E (terminal · UNCLASSIFIED)",
        "steps": [
            ("Q1_inception", ["unknown"]),
        ],
        "expect_terminal": True,
    },
    {
        "id": "ROUTER-DATA→MISCFG",
        "name": "Q3_DATA 라우터: storage_policy → Q4_MISCFG 경로",
        "steps": [
            ("Q1_inception", ["external_report"]),
            ("Q2B_report_content", ["data_exposed"]),
            ("Q3_DATA", ["storage_policy_public"]),
            ("Q4_MISCFG", ["long_term_public"]),
            ("Q5_MISCFG", ["operator"]),
            ("Q6_MISCFG", ["pii"]),
        ],
        "expect_winner": "MISCONFIG_EXPOSURE",
        "expect_outcomes": {"auto_confirm", "propose_single", "propose_composite"},
    },
    {
        "id": "ROUTER-DATA→INSIDER",
        "name": "Q3_DATA 라우터: multi_csp_pivot → Q4_INSIDER 경로",
        "steps": [
            ("Q1_inception", ["external_report"]),
            ("Q2B_report_content", ["data_exposed"]),
            ("Q3_DATA", ["multi_csp_pivot"]),
            ("Q4_INSIDER", ["scope_excess"]),
            ("Q5_INSIDER", ["internal_vpn"]),
            ("Q6_INSIDER", ["iam_self_delete"]),
        ],
        "expect_winner": "INSIDER_THREAT",
        "expect_outcomes": {"auto_confirm", "propose_single", "propose_composite"},
    },
    {
        "id": "ROUTER-DATA→RANSOM",
        "name": "Q3_DATA 라우터: billing_spike → Q4_RANSOM 경로",
        "steps": [
            ("Q1_inception", ["external_report"]),
            ("Q2B_report_content", ["abnormal_billing"]),
            ("Q3_DATA", ["billing_spike"]),
            ("Q4_RANSOM", ["backup_destroyed"]),
            ("Q5_RANSOM", ["storage_wide"]),
            ("Q6_RANSOM", ["note_found"]),
        ],
        "expect_winner": "RANSOMWARE",
        "expect_outcomes": {"auto_confirm", "propose_single", "propose_composite"},
    },
]


def _all_scenarios() -> list[dict]:
    out: list[dict] = []
    out += _build_lane_scenarios("CRED", CRED_ENTRIES, CRED_TAILS, "CREDENTIAL_THEFT")
    out += _build_lane_scenarios("RANSOM", RANSOM_ENTRIES, RANSOM_TAILS, "RANSOMWARE")
    out += _build_lane_scenarios("MISCFG", MISCFG_ENTRIES, MISCFG_TAILS, "MISCONFIG_EXPOSURE")
    out += _build_lane_scenarios("INSIDER", INSIDER_ENTRIES, INSIDER_TAILS, "INSIDER_THREAT")
    out += SPECIAL_SCENARIOS
    return out


# ─────────────────────────────────────────────────────────────
# 실행 + 검증
# ─────────────────────────────────────────────────────────────


def _run_scenario(scenario: dict) -> dict:
    """시나리오 단계 차례로 Triage 엔진 호출. 에러 시 raise."""
    scores = _initial_scores()
    path: list[dict] = []
    last_result: dict = {}
    for node_id, ans in scenario["steps"]:
        last_result = Triage.next_question(node_id, ans, scores, path)
        if last_result.get("error"):
            raise RuntimeError(f"엔진 오류: {last_result['error']}")
        scores = last_result["hypothesis_scores"]
        path = last_result["tree_path"]
    recommendation = evaluate_recommendation(scores)
    ranked = sorted(
        ((t, s) for t, s in scores.items() if t != "UNCLASSIFIED"),
        key=lambda x: -x[1],
    )
    return {
        "scores": scores,
        "ranked": ranked,
        "recommendation": recommendation,
        "is_terminal": last_result.get("is_terminal", False),
        "next_node": last_result.get("next_node"),
    }


def _check(scenario: dict, run: dict) -> list[str]:
    failures: list[str] = []
    # 특수 케이스: 에러만 없으면 PASS
    if scenario.get("expect_no_error"):
        return failures
    if scenario.get("expect_terminal"):
        nn = run.get("next_node") or {}
        if nn.get("type") != "terminal":
            failures.append(f"terminal 예상이나 next_node.type={nn.get('type')}")
        return failures
    # 우승 사고유형 검증
    if "expect_winner" in scenario:
        ranked = run["ranked"]
        winner = ranked[0][0]
        if winner != scenario["expect_winner"]:
            # 복합 가설 허용? — top-2 안에 있으면 약한 PASS
            top2 = {ranked[0][0], ranked[1][0]} if len(ranked) >= 2 else {winner}
            if scenario["expect_winner"] in top2:
                # composite 인 경우 outcome 도 propose_composite 인지 확인
                if run["recommendation"]["outcome"] == "propose_composite":
                    return failures  # 의도된 복합
            failures.append(
                f"1위 불일치 — 기대 {scenario['expect_winner']}, 실제 {winner} "
                f"(2위 {ranked[1][0] if len(ranked) >= 2 else '—'})"
            )
    # outcome 검증
    if "expect_outcomes" in scenario:
        actual = run["recommendation"]["outcome"]
        allowed = scenario["expect_outcomes"]
        if actual not in allowed:
            failures.append(
                f"outcome 불일치 — 기대 {'/'.join(sorted(allowed))}, 실제 {actual}"
            )
    return failures


def main() -> int:
    invalidate_cache()
    scenarios = _all_scenarios()
    print("=" * 76)
    print(f" E4 결정 트리 종합 시나리오 — {len(scenarios)} 건")
    print("=" * 76)

    passed = 0
    failed_list: list[tuple[str, str, list[str]]] = []
    by_lane: dict[str, list[int]] = {}  # lane → [pass, fail]

    for sc in scenarios:
        sid = sc["id"]
        lane = sid.split("-")[0]
        by_lane.setdefault(lane, [0, 0])
        try:
            run = _run_scenario(sc)
            fails = _check(sc, run)
        except Exception as e:
            fails = [f"실행 예외: {e}"]
            run = {}
        if fails:
            failed_list.append((sid, sc["name"], fails))
            by_lane[lane][1] += 1
            mark = "FAIL"
        else:
            passed += 1
            by_lane[lane][0] += 1
            mark = "PASS"
        # 1위·outcome 요약
        if run.get("ranked"):
            top = run["ranked"][0]
            oc = run["recommendation"]["outcome"]
            tail = f" | {top[0]}={top[1]} · {oc}"
        else:
            tail = ""
        print(f"  [{mark}] {sid:18} {sc['name'][:50]:50}{tail}")

    print()
    print("=" * 76)
    print(f" 결과: {passed}/{len(scenarios)} PASS")
    print(" lane 별: " + ", ".join(
        f"{l} {p}/{p + f}" for l, (p, f) in sorted(by_lane.items())
    ))
    if failed_list:
        print(" 실패 항목:")
        for sid, name, fails in failed_list:
            print(f"   - {sid} ({name})")
            for fmsg in fails:
                print(f"       · {fmsg}")
    print("=" * 76)
    return 0 if not failed_list else 1


if __name__ == "__main__":
    sys.exit(main())
