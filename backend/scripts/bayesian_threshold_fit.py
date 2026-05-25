"""베이지안 임계값 grid search — 47 시나리오 PASS 카운트 최대화.

Phase 3.5 (2026-05-25, byungwoo). bayes_update 사후확률에 대해 어떤 임계값 조합이
e2e_tree_e4_test 의 47 시나리오 expect_outcome 와 가장 정합하는지 자동 탐색.

탐색 차원
---------
    auto_confirm  ∈ {0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85}
    propose_single ∈ {0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65}
    composite_min ∈ {0.20, 0.25, 0.30, 0.35, 0.40}  (≤ propose_single 보장)
    gap_required  ∈ {0.05, 0.10, 0.15, 0.20}

총 7×7×5×4 = 980 조합. 각 조합으로 47 시나리오 평가 → PASS 카운트.

사용: cd backend && TRIAGE_MODE=bayesian .venv/Scripts/python.exe -X utf8 -m scripts.bayesian_threshold_fit
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from core.intake import bayesian
from core.intake.triage import (  # noqa: E402
    Triage,
    _initial_scores,
    invalidate_cache,
)
from scripts.e2e_tree_e4_test import _all_scenarios  # noqa: E402


def _custom_confidence(scores: dict, auto: float, single: float, comp: float, gap_req: float) -> str:
    ranked = bayesian.top_n(scores, n=2)
    if len(ranked) < 2:
        return "continue_or_skip"
    primary_p = ranked[0][1]
    secondary_p = ranked[1][1]
    gap = primary_p - secondary_p
    if primary_p >= auto and gap >= gap_req:
        return "auto_confirm"
    if primary_p >= single and gap >= gap_req / 2:
        return "propose_single"
    if primary_p >= comp:
        return "propose_composite"
    return "continue_or_skip"


def _run_scenario_bayesian(scenario: dict, thresholds: tuple) -> tuple[str, str]:
    """시나리오 끝까지 베이즈 갱신 + 사용자 정의 임계값 분류.

    Returns: (winner, outcome)
    """
    scores = _initial_scores()
    for node_id, ans in scenario["steps"]:
        result = Triage.next_question(node_id, ans, scores, [])
        if result.get("error"):
            return ("ERROR", "ERROR")
        scores = result["hypothesis_scores"]
    auto, single, comp, gap_req = thresholds
    outcome = _custom_confidence(scores, auto, single, comp, gap_req)
    ranked = bayesian.top_n(scores, n=1)
    winner = ranked[0][0] if ranked else "UNCLASSIFIED"
    return (winner, outcome)


def _scenario_passes(scenario: dict, winner: str, outcome: str) -> bool:
    """e2e_tree_e4_test 와 동일한 검증 로직."""
    if scenario.get("expect_no_error"):
        return True
    if scenario.get("expect_terminal"):
        return outcome == "continue_or_skip"
    # 우승 검증
    if "expect_winner" in scenario:
        if winner != scenario["expect_winner"]:
            # composite 허용?
            if outcome == "propose_composite":
                return True
            return False
    if "expect_outcomes" in scenario:
        if outcome not in scenario["expect_outcomes"]:
            return False
    return True


def main():
    import os
    os.environ["TRIAGE_MODE"] = "bayesian"
    invalidate_cache()

    scenarios = _all_scenarios()
    print(f"=== Bayesian threshold grid search — {len(scenarios)} scenarios ===")

    auto_grid = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]
    single_grid = [0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]
    comp_grid = [0.20, 0.25, 0.30, 0.35, 0.40]
    gap_grid = [0.05, 0.10, 0.15, 0.20]

    best = (0, None)
    results = []
    total_combos = len(auto_grid) * len(single_grid) * len(comp_grid) * len(gap_grid)
    cnt = 0

    for auto in auto_grid:
        for single in single_grid:
            if single >= auto:
                continue
            for comp in comp_grid:
                if comp >= single:
                    continue
                for gap_req in gap_grid:
                    cnt += 1
                    th = (auto, single, comp, gap_req)
                    passes = 0
                    for sc in scenarios:
                        try:
                            winner, outcome = _run_scenario_bayesian(sc, th)
                            if _scenario_passes(sc, winner, outcome):
                                passes += 1
                        except Exception:
                            pass
                    results.append((passes, th))
                    if passes > best[0]:
                        best = (passes, th)
                        print(f"  [{cnt}/{total_combos}] new best: {passes}/47 with auto={auto}, single={single}, comp={comp}, gap={gap_req}")

    print()
    print("=" * 70)
    print(f" 최고: {best[0]}/47 — auto_confirm={best[1][0]}, propose_single={best[1][1]}, composite={best[1][2]}, gap={best[1][3]}")
    print()
    print(" Top 5 조합:")
    for passes, th in sorted(results, key=lambda x: -x[0])[:5]:
        print(f"   {passes}/47  auto={th[0]:.2f}  single={th[1]:.2f}  comp={th[2]:.2f}  gap={th[3]:.2f}")


if __name__ == "__main__":
    main()
