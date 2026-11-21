"""H.3 — Bayesian Network 47 시나리오 e2e 회귀 (2026-05-25, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §17.B (BAN paper 정합)

evidence_tree e2e (Phase F) 와 동일 47 시나리오를 BN Noisy-OR 추론으로 재실행.
clue_to_attack.json 매핑 + Noisy-OR aggregation + Laplace smoothing 적용.

비교 기준:
    - additive   (legacy):  47/47 PASS
    - bayesian   (Phase 5): 43/47 PASS (4 INSIDER T3 약한 시그널)
    - evidence_tree (F):    43/47 PASS (동일 한계)
    - bayes_net  (H.3):     ?/47 — BN 모델이 얼마나 더 신뢰도 향상하나

검증 정책 (legacy bayesian e2e 와 동일):
    1위 일치 → PASS
    1위 불일치 but top-2 + p1<0.65 → composite 허용 PASS

사용:
    cd backend && .venv/Scripts/python.exe -X utf8 -m scripts.e2e_bayes_net_test
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from core.intake.bayes_net import bn_evaluate_sequence, invalidate_cache  # noqa: E402
from core.intake.bayesian import invalidate_priors_cache  # noqa: E402

# 기존 47 시나리오 매트릭스 재사용 (Phase F 와 동일)
from scripts.e2e_evidence_tree_test import (  # noqa: E402
    _all_scenarios,
    _scenario_to_clue_keys,
    _top_n,
)


def _check_scenario(sc: dict, posterior: dict[str, float]) -> tuple[bool, str]:
    """Phase F 와 동일 정책 — 1위 OR (top-2 + p1<0.65) composite."""
    if sc.get("expect_terminal"):
        return True, "terminal scenario"
    if sc.get("expect_no_error"):
        return True, "no_error scenario"

    expected = sc.get("expect_winner")
    if not expected:
        return True, "no winner constraint"

    top = _top_n(posterior, n=2)
    if not top:
        return False, "posterior 비어있음"

    actual, p1 = top[0]
    p2 = top[1][1] if len(top) >= 2 else 0.0
    second = top[1][0] if len(top) >= 2 else None
    gap = p1 - p2

    if actual == expected:
        return True, (
            f"1위 {actual} {p1:.3f}"
            + (f" · 2위 {second} {p2:.3f} · 격차 {gap:.3f}" if second else "")
        )
    # composite 허용 (Phase F 정합)
    top2 = {actual, second} if second else {actual}
    if expected in top2 and p1 < 0.65:
        return True, (
            f"composite — 1위 {actual} {p1:.3f}, 기대 {expected} top-2"
        )
    return False, (
        f"1위 불일치 — 기대 {expected}, 실제 {actual} {p1:.3f}"
        + (f" (2위 {second} {p2:.3f})" if second else "")
    )


def main() -> int:
    print("=" * 76)
    print(" Bayesian Network e2e — 47 시나리오 Noisy-OR 추론 회귀")
    print(f" 실행 시각: {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 76)

    invalidate_priors_cache()
    invalidate_cache()

    scenarios = _all_scenarios()
    print(f" 시나리오 수: {len(scenarios)}")
    print()

    pass_n = 0
    fail_n = 0
    lane_stats: dict[str, list[int]] = {}
    failures: list[dict] = []

    for sc in scenarios:
        lane = sc["id"].split("-")[0]
        lane_stats.setdefault(lane, [0, 0])
        lane_stats[lane][1] += 1

        clue_keys = _scenario_to_clue_keys(sc["steps"])
        try:
            posterior, _trace = bn_evaluate_sequence(clue_keys)
        except Exception as e:
            fail_n += 1
            failures.append({"id": sc["id"], "name": sc["name"], "reason": f"engine 오류 {e}"})
            print(f"  [FAIL-ERR] {sc['id']} — {e}")
            continue

        ok, detail = _check_scenario(sc, posterior)
        if ok:
            pass_n += 1
            lane_stats[lane][0] += 1
            print(f"  [PASS] {sc['id']:24} {sc['name'][:46]:46} | {detail}")
        else:
            fail_n += 1
            failures.append({"id": sc["id"], "name": sc["name"], "reason": detail})
            print(f"  [FAIL] {sc['id']:24} {sc['name'][:46]:46} | {detail}")

    print()
    print("=" * 76)
    print(f" 결과: {pass_n}/{len(scenarios)} PASS")
    lanes_str = " ".join(f"{l} {s[0]}/{s[1]}" for l, s in sorted(lane_stats.items()))
    print(f" lane 별: {lanes_str}")
    print("=" * 76)

    if failures:
        print()
        print(" FAIL 사유:")
        for f in failures[:10]:
            print(f"   - {f['id']} ({f['name'][:60]})")
            print(f"       · {f['reason']}")

    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
