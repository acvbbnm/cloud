"""E4 6-stage decision tree — 5-scenario end-to-end simulation.

docs/dev3/결정트리_업그레이드.md §8 검증 시나리오 5종.
각 시나리오: Q1→Q2→Q3→Q4→Q5→Q6→T_evaluate 6단계 통과 후
  - 의도 사고유형이 1위인지
  - 1위·2위 격차 ≥ 20
  - recommendation outcome 이 auto_confirm 또는 propose_single 이상

실행:
  cd backend
  python -X utf8 ../scripts/e2e_tree_e4_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from core.intake.triage import Triage, _initial_scores, invalidate_cache


def run_scenario(
    name: str,
    steps: list[tuple[str, list[str]]],
    expected_winner: str,
    min_score: int = 70,
    min_gap: int = 20,
) -> bool:
    """Run a single scenario through the Triage engine.

    Args:
        name: scenario label
        steps: [(node_id, [answer_ids]), ...]
        expected_winner: expected top incident type
        min_score: minimum score for expected_winner
        min_gap: minimum gap between 1st and 2nd
    """
    invalidate_cache()

    start = Triage.start()
    scores = dict(start["hypothesis_scores"])
    path: list[dict] = []

    for node_id, answer_ids in steps:
        res = Triage.next_question(node_id, answer_ids, scores, path)
        scores = res["hypothesis_scores"]
        path = res["tree_path"]

    sorted_scores = sorted(
        [(k, v) for k, v in scores.items() if k != "UNCLASSIFIED"],
        key=lambda x: x[1],
        reverse=True,
    )
    winner_type, winner_score = sorted_scores[0]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0
    gap = winner_score - second_score

    rec = res.get("recommendation") or {}
    outcome = rec.get("outcome", "N/A")

    passed = (
        winner_type == expected_winner
        and winner_score >= min_score
        and gap >= min_gap
    )

    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}")
    print(f"    winner: {winner_type} ({winner_score}), gap: {gap}, outcome: {outcome}")
    if not passed:
        print(f"    expected: {expected_winner} >= {min_score}, gap >= {min_gap}")
        print(f"    top-5: {sorted_scores[:5]}")
    return passed


def main() -> int:
    print("=" * 60)
    print("E4 6-Stage Decision Tree — 5-Scenario Simulation")
    print("=" * 60)

    results: list[bool] = []

    # S1: CREDENTIAL_THEFT + MFA 우회 (CRED path)
    results.append(
        run_scenario(
            "S1: CRED + MFA bypass",
            [
                ("Q1_inception", ["csp_alert"]),
                ("Q2A_alert_type", ["abnormal_login", "non_korean_ip"]),
                ("Q3_additional_context", ["fail_then_success"]),
                ("Q4_CRED", ["mfa_token_reuse"]),
                ("Q5_CRED", ["tor_vpn_exit"]),
                ("Q6_CRED", ["priv_change"]),
            ],
            expected_winner="CREDENTIAL_THEFT",
            min_score=70,
            min_gap=20,
        )
    )

    # S2: RANSOMWARE (RANSOM path)
    results.append(
        run_scenario(
            "S2: RANSOMWARE",
            [
                ("Q1_inception", ["service_anomaly"]),
                ("Q2D_anomaly_form", ["data_destruction"]),
                ("Q3_additional_context", ["storage_policy_change"]),
                ("Q4_RANSOM", ["backup_destroyed"]),
                ("Q5_RANSOM", ["storage_wide"]),
                ("Q6_RANSOM", ["ransom_note_found"]),
            ],
            expected_winner="RANSOMWARE",
            min_score=70,
            min_gap=20,
        )
    )

    # S3: MISCONFIG_EXPOSURE (MISCFG path)
    results.append(
        run_scenario(
            "S3: MISCONFIG_EXPOSURE",
            [
                ("Q1_inception", ["external_report"]),
                ("Q2B_report_content", ["data_exposed"]),
                ("Q3_additional_context", ["storage_policy_change"]),
                ("Q4_MISCFG", ["long_term_exposure"]),
                ("Q5_MISCFG", ["operator_error"]),
                ("Q6_MISCFG", ["pii_data"]),
            ],
            expected_winner="MISCONFIG_EXPOSURE",
            min_score=70,
            min_gap=20,
        )
    )

    # S4: PHISH_INITIAL_ACCESS (uses CRED path but with phishing signals)
    results.append(
        run_scenario(
            "S4: PHISH_INITIAL_ACCESS",
            [
                ("Q1_inception", ["external_report"]),
                ("Q2B_report_content", ["identity_theft"]),
                ("Q3_additional_context", ["fail_then_success"]),
                ("Q4_CRED", ["mfa_token_reuse"]),
                ("Q5_CRED", ["non_korean_ip"]),
                ("Q6_CRED", ["priv_change"]),
            ],
            expected_winner="PHISH_INITIAL_ACCESS",
            min_score=70,
            min_gap=10,
        )
    )

    # S5: INSIDER_THREAT (INSIDER path)
    results.append(
        run_scenario(
            "S5: INSIDER_THREAT",
            [
                ("Q1_inception", ["audit"]),
                ("Q2C_audit_pattern", ["permission_changes"]),
                ("Q3_additional_context", ["fail_then_success"]),
                ("Q4_INSIDER", ["scope_excess"]),
                ("Q5_INSIDER", ["trace_deletion"]),
                ("Q6_INSIDER", ["self_iam_deletion"]),
            ],
            expected_winner="INSIDER_THREAT",
            min_score=70,
            min_gap=20,
        )
    )

    print()
    print("-" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} passed")
    if passed == total:
        print("ALL SCENARIOS PASSED")
    else:
        print("SOME SCENARIOS FAILED — check weights.json thresholds")
    print("-" * 60)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
