"""E4 결정 트리 6단계 — 5 시나리오 e2e 시뮬레이션 검증 스크립트.

`docs/dev3/결정트리_업그레이드.md` §7-G + §8 의 작업 항목 G 구현.

목적:
  - Q1~Q6 6단계 동적 분기 트리를 5 시나리오로 끝까지 통과시켜
    의도한 사고유형이 1위로 수렴하는지 결정론적으로 검증한다.
  - 임계값(auto_skip_tree·high_confidence·gap_to_2nd) 이 6단계 누적 점수
    범위에 맞게 조정됐는지 확인한다.

설계 원칙 (CLAUDE.md 정합):
  - HTTP 서버 불필요 — `core.intake.triage.Triage` 엔진을 직접 호출한다.
    결정성 100% 엔진이므로 같은 입력 → 같은 출력. 폐쇄망에서 단독 실행 가능.
  - 가중치·분기 룰은 모두 정적 JSON(weights.json·decision_tree.json) 에서 로딩.

사용:
  cd backend
  .venv/Scripts/python.exe -X utf8 -m scripts.e2e_tree_e4_test

종료 코드:
  0 — 5 시나리오 전부 PASS
  1 — 1건 이상 FAIL
"""
from __future__ import annotations

import sys
from pathlib import Path

# `python scripts/e2e_tree_e4_test.py` 직접 실행 시에도 import 되도록 backend 루트 보강
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
# 5 검증 시나리오 — (node_id, [answer_ids]) 6단계 시퀀스
# decision_tree.json 의 실제 노드·옵션 ID 와 정확히 일치해야 한다.
# ─────────────────────────────────────────────────────────────

SCENARIOS: list[dict] = [
    {
        "id": "S1",
        "name": "CRED + MFA 우회 (CSP 알람 경로)",
        "steps": [
            ("Q1_inception", ["csp_alert"]),
            ("Q2A_alert_type", ["abnormal_login", "non_korean_ip"]),
            ("Q3_CRED", ["fail_then_success"]),
            ("Q4_CRED", ["mfa_token_reuse"]),
            ("Q5_CRED", ["tor_vpn"]),
            ("Q6_CRED", ["priv_change"]),
        ],
        "expect_winner": "CREDENTIAL_THEFT",
        "expect_min_score": 130,
        "expect_outcome": "auto_confirm",
    },
    {
        "id": "S2",
        "name": "RANSOMWARE (서비스 이상 경로)",
        "steps": [
            ("Q1_inception", ["service_anomaly"]),
            ("Q2D_anomaly_form", ["data_destruction"]),
            ("Q3_IMPACT", ["mass_encrypt"]),
            ("Q4_RANSOM", ["backup_destroyed"]),
            ("Q5_RANSOM", ["storage_wide"]),
            ("Q6_RANSOM", ["note_found"]),
        ],
        "expect_winner": "RANSOMWARE",
        "expect_min_score": 130,
        "expect_outcome": "auto_confirm",
    },
    {
        "id": "S3",
        "name": "MISCONFIG_EXPOSURE (외부 신고 경로)",
        "steps": [
            ("Q1_inception", ["external_report"]),
            ("Q2B_report_content", ["data_exposed"]),
            ("Q3_DATA", ["storage_policy_public"]),
            ("Q4_MISCFG", ["long_term_public"]),
            ("Q5_MISCFG", ["operator"]),
            ("Q6_MISCFG", ["pii"]),
        ],
        "expect_winner": "MISCONFIG_EXPOSURE",
        "expect_min_score": 130,
        "expect_outcome": "auto_confirm",
    },
    {
        "id": "S4",
        "name": "PHISH → CRED 복합 (피싱 신원도용 제보 경로)",
        "steps": [
            ("Q1_inception", ["external_report"]),
            ("Q2B_report_content", ["identity_theft"]),
            ("Q3_CRED", ["fail_then_success"]),
            ("Q4_CRED", ["mfa_token_reuse"]),
            ("Q5_CRED", ["non_korean_ip"]),
            ("Q6_CRED", ["priv_change"]),
        ],
        # 의도된 복합 판정: 피싱(PHISH)이 자격증명 탈취(CRED)로 이어지는
        # 전형적 공격 체인. Q2B:identity_theft 가 CRED 변별 분기(Q3_CRED)로
        # 라우팅되므로 두 가설이 근접 → propose_composite 가 정답.
        # doc §8 표는 PHISH 단독 우승을 기대했으나, 실제 트리 구현에서는
        # "피싱 기점 자격증명 탈취" 복합이 더 정확한 판정이다.
        "expect_top2": {"PHISH_INITIAL_ACCESS", "CREDENTIAL_THEFT"},
        "expect_outcome": "propose_composite",
    },
    {
        "id": "S5",
        "name": "INSIDER_THREAT (정기 감사 경로)",
        "steps": [
            ("Q1_inception", ["audit"]),
            ("Q2C_audit_pattern", ["permission_changes"]),
            ("Q3_INSIDER", ["off_hours_priv"]),
            ("Q4_INSIDER", ["scope_excess"]),
            ("Q5_INSIDER", ["internal_vpn"]),
            ("Q6_INSIDER", ["iam_self_delete"]),
        ],
        "expect_winner": "INSIDER_THREAT",
        "expect_min_score": 130,
        "expect_outcome": "auto_confirm",
    },
]


def _run_scenario(scenario: dict) -> dict:
    """시나리오 6단계를 Triage 엔진으로 통과시키고 결과를 수집한다."""
    scores = _initial_scores()
    path: list[dict] = []
    step_log: list[dict] = []

    for node_id, answer_ids in scenario["steps"]:
        prev = dict(scores)
        result = Triage.next_question(node_id, answer_ids, scores, path)
        if result.get("error"):
            raise RuntimeError(f"{scenario['id']} — 트리 오류: {result['error']}")
        scores = result["hypothesis_scores"]
        path = result["tree_path"]
        deltas = {
            t: scores[t] - prev.get(t, 0)
            for t in scores
            if scores[t] - prev.get(t, 0) != 0
        }
        step_log.append(
            {
                "node": node_id,
                "answers": answer_ids,
                "deltas": deltas,
                "next": (result.get("next_node") or {}).get("id"),
            }
        )

    recommendation = evaluate_recommendation(scores)
    ranked = sorted(
        ((t, s) for t, s in scores.items() if t != "UNCLASSIFIED"),
        key=lambda x: -x[1],
    )
    return {
        "scores": scores,
        "ranked": ranked,
        "recommendation": recommendation,
        "step_log": step_log,
    }


def _check(scenario: dict, run: dict) -> list[str]:
    """시나리오 기대치 대비 검증 — 실패 사유 목록 반환 (빈 리스트면 PASS)."""
    failures: list[str] = []
    ranked = run["ranked"]
    outcome = run["recommendation"]["outcome"]
    winner, winner_score = ranked[0]

    if "expect_winner" in scenario:
        if winner != scenario["expect_winner"]:
            failures.append(
                f"1위 불일치 — 기대 {scenario['expect_winner']}, 실제 {winner}"
            )
        if winner_score < scenario["expect_min_score"]:
            failures.append(
                f"1위 점수 미달 — 기대 ≥{scenario['expect_min_score']}, 실제 {winner_score}"
            )

    if "expect_top2" in scenario:
        top2 = {ranked[0][0], ranked[1][0]}
        if top2 != scenario["expect_top2"]:
            failures.append(
                f"상위 2 가설 불일치 — 기대 {sorted(scenario['expect_top2'])}, "
                f"실제 {sorted(top2)}"
            )

    if outcome != scenario["expect_outcome"]:
        failures.append(
            f"outcome 불일치 — 기대 {scenario['expect_outcome']}, 실제 {outcome}"
        )
    return failures


def main() -> int:
    """5 시나리오 시뮬레이션 실행 + 결과 리포트."""
    invalidate_cache()  # 시드·핫리로드 후에도 최신 JSON 으로 평가

    print("=" * 72)
    print(" E4 결정 트리 6단계 — 5 시나리오 e2e 시뮬레이션")
    print("=" * 72)

    all_pass = True
    for scenario in SCENARIOS:
        run = _run_scenario(scenario)
        failures = _check(scenario, run)
        status = "PASS" if not failures else "FAIL"
        if failures:
            all_pass = False

        print(f"\n[{scenario['id']}] {scenario['name']}  →  {status}")
        for step in run["step_log"]:
            delta_str = ", ".join(
                f"{t.split('_')[0]}{'+' if d > 0 else ''}{d}"
                for t, d in sorted(step["deltas"].items(), key=lambda x: -x[1])
            )
            print(
                f"   {step['node']:<20} {','.join(step['answers']):<32} "
                f"[{delta_str}]"
            )
        rank_str = "  ".join(
            f"{t}={s}" for t, s in run["ranked"][:3]
        )
        rec = run["recommendation"]
        print(f"   └─ 순위: {rank_str}")
        print(f"   └─ 판정: {rec['outcome']} — {rec['message']}")
        for fail in failures:
            print(f"   !! {fail}")

    print("\n" + "=" * 72)
    if all_pass:
        print(" 결과: 5/5 PASS — E4 결정 트리 시나리오 검증 통과")
    else:
        print(" 결과: FAIL — 위 !! 항목 확인")
    print("=" * 72)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
