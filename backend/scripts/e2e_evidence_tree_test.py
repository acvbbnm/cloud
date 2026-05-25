"""Phase F — Evidence Tree 47 시나리오 e2e 회귀 (2026-05-25, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §10 + §11

기존 47 시나리오 (legacy `e2e_tree_e4_test.py`) 의 (Q_node, [option_ids])
시퀀스를 단서 시퀀스 [clue_key, ...] 로 변환하여 evidence_tree 흐름 검증.

매핑 규칙:
    (Q_node, [opt_a, opt_b]) → [f"{Q_node}:{opt_a}", f"{Q_node}:{opt_b}"]
    (clue_catalog.json 의 키 = decision_tree.json option.weight_key 와 동형)

검증:
    1. start_tree → uniform prior
    2. expand_tree 시퀀스 적용 (각 option → clue_key)
    3. 최종 posterior 1위 사고유형 == expect_winner

사용:
    cd backend && .venv/Scripts/python.exe -X utf8 -m scripts.e2e_evidence_tree_test

학술 변호:
    - 결정성 100% — 같은 단서 시퀀스 → 같은 사후확률
    - bayesian e2e 와 동일 결과 기대 (단서 카탈로그 likelihood 가 weights.json 정합)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from core.intake.bayesian import bayes_update, initial_posterior, invalidate_priors_cache  # noqa: E402
from core.intake.info_gain import load_catalog, weights_to_likelihood  # noqa: E402

# 기존 시나리오 데이터 재사용 — legacy e2e_tree_e4_test 의 매트릭스 import
from scripts.e2e_tree_e4_test import (  # noqa: E402
    SPECIAL_SCENARIOS,
    CRED_ENTRIES,
    CRED_TAILS,
    RANSOM_ENTRIES,
    RANSOM_TAILS,
    MISCFG_ENTRIES,
    MISCFG_TAILS,
    INSIDER_ENTRIES,
    INSIDER_TAILS,
    _build_lane_scenarios,
)


# ─────────────────────────────────────────────────────────────
# 시나리오 변환 — (Q_node, [option_ids]) → [clue_key]
# ─────────────────────────────────────────────────────────────


_TREE_LOOKUP_CACHE: dict[tuple[str, str], str] | None = None


def _build_tree_lookup() -> dict[tuple[str, str], str]:
    """decision_tree.json 의 각 (node_id, option.id) → option.weight_key 매핑.

    weight_key 형식은 노드별로 다름 (Q2A_alert_type 의 option.weight_key
    는 "Q2A:abnormal_login" 형태). 카탈로그는 weight_key 그대로 사용하므로
    이 매핑이 필요.
    """
    tree_path = _BACKEND_DIR / "data" / "triage" / "decision_tree.json"
    tree = json.loads(tree_path.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], str] = {}
    for nid, node in tree.get("nodes", {}).items():
        if node.get("type") != "question":
            continue
        for opt in node.get("options", []):
            wk = opt.get("weight_key") or f"{nid}:{opt.get('id', '')}"
            out[(nid, opt.get("id", ""))] = wk
    return out


def _tree_lookup() -> dict[tuple[str, str], str]:
    global _TREE_LOOKUP_CACHE
    if _TREE_LOOKUP_CACHE is None:
        _TREE_LOOKUP_CACHE = _build_tree_lookup()
    return _TREE_LOOKUP_CACHE


def _scenario_to_clue_keys(steps: list[tuple[str, list[str]]]) -> list[str]:
    """결정 트리 단계 → 단서 키 평탄화.

    decision_tree.json 의 weight_key 매핑 사용 (Q2A_alert_type:abnormal_login
    → Q2A:abnormal_login 같은 별칭 처리).
    """
    lookup = _tree_lookup()
    out: list[str] = []
    for node_id, options in steps:
        for opt in options:
            key = lookup.get((node_id, opt)) or f"{node_id}:{opt}"
            out.append(key)
    return out


# ─────────────────────────────────────────────────────────────
# 시뮬레이션 — DB 없이 in-memory bayes_update 만 (빠른 회귀)
# ─────────────────────────────────────────────────────────────


def _simulate(clue_keys: list[str], catalog: dict) -> dict[str, float]:
    """단서 시퀀스 → 최종 posterior (uniform prior → bayes_update 누적)."""
    posterior = initial_posterior()
    clues = catalog.get("clues", {})
    for ck in clue_keys:
        entry = clues.get(ck)
        if entry is None or not entry.get("has_weights"):
            # 카탈로그에 없는 단서는 skip (시그널 없음)
            continue
        likelihood = weights_to_likelihood(entry["weights"])
        if not likelihood:
            continue
        posterior = bayes_update(posterior, likelihood)
    return posterior


def _top_n(posterior: dict[str, float], n: int = 2) -> list[tuple[str, float]]:
    ranked = [(h, p) for h, p in posterior.items() if h != "UNCLASSIFIED"]
    ranked.sort(key=lambda x: -x[1])
    return ranked[:n]


# ─────────────────────────────────────────────────────────────
# 검증
# ─────────────────────────────────────────────────────────────


def _check_scenario(sc: dict, posterior: dict[str, float]) -> tuple[bool, str]:
    """시나리오 1건 검증.

    legacy e2e_tree_e4_test 의 `_check()` 와 동일 정책:
      - 1위 일치 → 무조건 PASS
      - 1위 불일치 but top-2 안에 expected + outcome 가 propose_composite 인 경우
        → 의도된 복합 가설로 PASS (legacy 와 동일 학술 정합)
      - 그 외 1위 불일치 → FAIL
    """
    if sc.get("expect_terminal"):
        return True, "terminal scenario — bayes 갱신 1단계 통과"
    if sc.get("expect_no_error"):
        return True, "no_error scenario — 단서 누적 통과"

    expected_winner = sc.get("expect_winner")
    if not expected_winner:
        return True, "no winner constraint"

    top = _top_n(posterior, n=2)
    if not top:
        return False, "posterior 비어있음"

    actual, p1 = top[0]
    p2 = top[1][1] if len(top) >= 2 else 0.0
    second = top[1][0] if len(top) >= 2 else None
    gap = p1 - p2

    if actual == expected_winner:
        return True, (
            f"1위 {actual} {p1:.3f}"
            + (f" · 2위 {second} {p2:.3f} · 격차 {gap:.3f}" if second else "")
        )

    # 복합 가설 허용 — legacy bayesian e2e 와 동일 정책
    # top-2 안에 expected_winner 가 있고, 1위가 "압도적이지 않음" (≤ 0.55 등)
    # → propose_composite 영역으로 간주.
    top2_set = {actual, second} if second else {actual}
    if expected_winner in top2_set and p1 < 0.65:
        return True, (
            f"composite — 1위 {actual} {p1:.3f}, 기대 {expected_winner} 가 top-2"
            + (f" (격차 {gap:.3f})" if second else "")
        )

    return False, (
        f"1위 불일치 — 기대 {expected_winner}, 실제 {actual} {p1:.3f}"
        + (f" (2위 {second} {p2:.3f})" if second else "")
    )


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────


def _all_scenarios() -> list[dict]:
    out: list[dict] = []
    out += _build_lane_scenarios("CRED", CRED_ENTRIES, CRED_TAILS, "CREDENTIAL_THEFT")
    out += _build_lane_scenarios("RANSOM", RANSOM_ENTRIES, RANSOM_TAILS, "RANSOMWARE")
    out += _build_lane_scenarios("MISCFG", MISCFG_ENTRIES, MISCFG_TAILS, "MISCONFIG_EXPOSURE")
    out += _build_lane_scenarios("INSIDER", INSIDER_ENTRIES, INSIDER_TAILS, "INSIDER_THREAT")
    out += SPECIAL_SCENARIOS
    return out


def main() -> int:
    print("=" * 76)
    print(" Evidence Tree e2e — 47 시나리오 단서 시퀀스 회귀")
    print(f" 실행 시각: {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 76)

    invalidate_priors_cache()  # priors.json 최신
    catalog = load_catalog()
    print(f" 카탈로그 단서 수: {len(catalog.get('clues', {}))}")
    print()

    scenarios = _all_scenarios()
    print(f" 시나리오 수: {len(scenarios)}")
    print()

    pass_n = 0
    fail_n = 0
    lane_stats: dict[str, list[int]] = {}  # lane → [pass, total]
    failures: list[dict] = []
    coverage_misses: dict[str, int] = {}  # 카탈로그 미수록 단서 키 카운트
    clues_in_cat = catalog.get("clues", {})

    for sc in scenarios:
        lane = sc["id"].split("-")[0]
        lane_stats.setdefault(lane, [0, 0])
        lane_stats[lane][1] += 1

        clue_keys = _scenario_to_clue_keys(sc["steps"])
        # 카탈로그 커버리지 통계
        for ck in clue_keys:
            if ck not in clues_in_cat or not clues_in_cat[ck].get("has_weights"):
                coverage_misses[ck] = coverage_misses.get(ck, 0) + 1

        try:
            posterior = _simulate(clue_keys, catalog)
        except Exception as e:
            fail_n += 1
            failures.append({"id": sc["id"], "name": sc["name"], "reason": f"엔진 오류 {e}"})
            print(f"  [FAIL-ERR] {sc['id']} — {e}")
            continue

        ok, detail = _check_scenario(sc, posterior)
        if ok:
            pass_n += 1
            lane_stats[lane][0] += 1
            print(f"  [PASS] {sc['id']:24} {sc['name'][:50]:50} | {detail}")
        else:
            fail_n += 1
            failures.append({"id": sc["id"], "name": sc["name"], "reason": detail})
            print(f"  [FAIL] {sc['id']:24} {sc['name'][:50]:50} | {detail}")

    print()
    print("=" * 76)
    print(f" 결과: {pass_n}/{len(scenarios)} PASS")
    lanes_str = " ".join(f"{l} {s[0]}/{s[1]}" for l, s in sorted(lane_stats.items()))
    print(f" lane 별: {lanes_str}")
    print("=" * 76)

    if coverage_misses:
        print()
        print(f" ⚠ 카탈로그 미수록 단서 키 ({len(coverage_misses)}종):")
        for ck, n in sorted(coverage_misses.items(), key=lambda x: -x[1])[:10]:
            print(f"    {ck} (×{n} 시나리오)")

    if failures:
        print()
        print(" FAIL 사유:")
        for f in failures[:10]:
            print(f"   - {f['id']} ({f['name'][:60]})")
            print(f"       · {f['reason']}")

    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
