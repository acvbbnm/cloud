"""Phase M 통합 e2e — 47 시나리오에서 zone/chain/regress 정량 검증 (2026-05-26, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §21·§22

목적
----
Phase M.1 의 4 신규 응답 필드 (`zone`/`attack_chain`/`core_clue_likelihood`/
`regress_suggested`) 가 실제 47 시나리오에서 어떻게 동작하는지 정량 측정.

단위 테스트 `tests/test_zone_logic.py` 12 케이스만으로는 47 시나리오의 실제
posterior 분포 + 단서 강도 조합에서 Zone 2 진입 빈도/chain 합리성/회귀 빈도가
시연 적합한지 알 수 없음. 본 스크립트가 그 갭을 메움.

검증 항목
---------
1. Zone 2 진입 비율 — 강한 시나리오 (RANSOM·INSIDER·CRED 등) 가 충분히 진입?
   기대: 47 중 ~70%+ (트리거 N=3, M=0.45 적정 여부 판단)
2. attack_chain Kill Chain 순서 정합 — 모든 chain 이 phase 오름차순?
   기대: 100% (알고리즘 보장)
3. attack_chain 필드 정합 — hypothesis/probability/kill_chain_phase 모두 존재?
4. core_clue_likelihood 범위 — 0 ≤ lk ≤ 1
5. should_regress 빈도 — uniform 근처 시나리오에서만 True?

출력
----
- 시나리오별 zone/chain depth/boss likelihood/regress 표
- 통계 — Zone 2 진입 비율 · 회귀 권고 · 부정합 시나리오 목록
- 시연 후 fit 권고 (paradigm §21.8 #1) — 임계값 조정 필요 시 안내

사용
----
    cd backend && .venv/Scripts/python.exe -X utf8 -m scripts.e2e_phase_m_zone_test
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from core.intake.bayesian import bayes_update, initial_posterior  # noqa: E402
from core.intake.clue_tree import (  # noqa: E402
    ClueTree,
    append_clue_node,
    make_root,
)
from core.intake.info_gain import load_catalog, weights_to_likelihood  # noqa: E402
from core.intake.zone_logic import (  # noqa: E402
    KILL_CHAIN_ORDER,
    TRIGGER_MIN_DEPTH,
    TRIGGER_MIN_LIKELIHOOD,
    compute_attack_chain,
    core_clue_likelihood,
    is_zone2_unlocked,
    should_regress,
)
from scripts.e2e_evidence_tree_test import (  # noqa: E402
    _all_scenarios,
    _scenario_to_clue_keys,
)


# ─────────────────────────────────────────────────────────────
# 헬퍼 — 단서 시퀀스 → ClueTree
# ─────────────────────────────────────────────────────────────


def _build_tree_from_clue_keys(
    case_id: str, clue_keys: list[str], catalog: dict
) -> ClueTree:
    """단서 시퀀스로 ClueTree 직접 빌드 (test_zone_logic.py 의 _build_tree 동일 패턴).

    카탈로그에 없거나 weights 없는 단서는 skip — e2e_evidence_tree_test 와 동일 정책.
    """
    tree = make_root(case_id, initial_posterior())
    clues = catalog.get("clues", {})
    parent_id = tree.root_id
    for ck in clue_keys:
        entry = clues.get(ck)
        if entry is None or not entry.get("has_weights"):
            continue
        weights = entry.get("weights", {})
        if not weights:
            continue
        likelihood = weights_to_likelihood(weights)
        if not likelihood:
            continue
        before = dict(tree.posterior_current)
        after = bayes_update(before, likelihood)
        node = append_clue_node(
            tree,
            parent_id=parent_id,
            clue_key=ck,
            category=entry.get("category", ""),
            value=entry.get("value", ""),
            label=entry.get("label", ck),
            source="e2e_test",
            posterior_before=before,
            posterior_after=after,
        )
        parent_id = node.node_id
    return tree


# ─────────────────────────────────────────────────────────────
# 검증 — attack_chain 필드/정렬 정합
# ─────────────────────────────────────────────────────────────


def _validate_chain(chain: list[dict]) -> tuple[bool, str]:
    """attack_chain 정합:
    1. 비어있지 않으면 hypothesis/probability/kill_chain_phase 3 필드 필수
    2. Kill Chain phase 오름차순 정렬
    3. probability 0 ≤ p ≤ 1 범위
    4. hypothesis 가 KILL_CHAIN_ORDER 등록 사고유형
    """
    if not chain:
        return True, "chain 비어있음 (UNCLASSIFIED 만 활성 등)"

    required = {"hypothesis", "probability", "kill_chain_phase"}
    for step in chain:
        if not required.issubset(step.keys()):
            return False, f"필드 누락 — required={required}, actual={set(step.keys())}"
        h = step["hypothesis"]
        p = step["probability"]
        phase = step["kill_chain_phase"]
        if h not in KILL_CHAIN_ORDER:
            return False, f"등록 안 된 사고유형: {h}"
        if not (0.0 <= p <= 1.0):
            return False, f"확률 범위 이상 — {h}: {p}"
        if phase != KILL_CHAIN_ORDER[h]:
            return False, f"phase 불일치 — {h}: expected {KILL_CHAIN_ORDER[h]}, got {phase}"

    # Kill Chain 시간순 — phase 오름차순
    phases = [step["kill_chain_phase"] for step in chain]
    if phases != sorted(phases):
        return False, f"Kill Chain 순서 깨짐: {phases}"

    return True, f"chain {len(chain)} 가설 · phases={phases}"


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────


def main() -> int:
    print("=" * 76)
    print(" Phase M 통합 e2e — 47 시나리오 zone/chain/regress 정량 검증")
    print(f" 실행 시각: {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 76)
    print(f" 트리거 임계값: depth ≥ {TRIGGER_MIN_DEPTH} AND P(c|h) ≥ {TRIGGER_MIN_LIKELIHOOD}")
    print()

    catalog = load_catalog()
    scenarios = _all_scenarios()

    # 통계
    zone2_count = 0
    regress_count = 0
    chain_valid = 0
    chain_field_errors: list[dict] = []
    coverage_misses: dict[str, int] = {}
    clues_in_cat = catalog.get("clues", {})

    # lane 별 zone 2 진입
    lane_zone2: dict[str, list[int]] = {}  # lane → [zone2_count, total]
    # 결과 행
    rows: list[dict] = []

    for sc in scenarios:
        lane = sc["id"].split("-")[0]
        lane_zone2.setdefault(lane, [0, 0])
        lane_zone2[lane][1] += 1

        clue_keys = _scenario_to_clue_keys(sc["steps"])

        # coverage 통계
        for ck in clue_keys:
            if ck not in clues_in_cat or not clues_in_cat[ck].get("has_weights"):
                coverage_misses[ck] = coverage_misses.get(ck, 0) + 1

        # 트리 빌드
        try:
            tree = _build_tree_from_clue_keys(sc["id"], clue_keys, catalog)
        except Exception as e:
            chain_field_errors.append(
                {"id": sc["id"], "reason": f"트리 빌드 실패: {e}"}
            )
            continue

        posterior = tree.posterior_current
        depth = max((n.depth for n in tree.nodes.values()), default=0)
        boss_lk = core_clue_likelihood(tree)
        zone2 = is_zone2_unlocked(tree, posterior)
        chain = compute_attack_chain(posterior)
        # 백엔드 _build_response 정합 — regress_suggested 는 zone 2 진입 시에만 의미
        # (Zone 1 일 땐 항상 False. UI 에 회귀 권고 표시 X)
        regress = zone2 and should_regress(posterior)
        final_zone = 1 if (not zone2 or regress) else 2

        # 통계 누적
        if final_zone == 2:
            zone2_count += 1
            lane_zone2[lane][0] += 1
        if regress:
            regress_count += 1

        ok, detail = _validate_chain(chain)
        if ok:
            chain_valid += 1
        else:
            chain_field_errors.append(
                {"id": sc["id"], "reason": detail, "chain": chain}
            )

        rows.append({
            "id": sc["id"],
            "name": sc.get("name", "")[:50],
            "depth": depth,
            "boss_lk": boss_lk,
            "zone": final_zone,
            "regress": regress,
            "chain_n": len(chain),
            "chain_phases": [s["kill_chain_phase"] for s in chain],
            "chain_ok": ok,
        })

    # ─ 상세 출력 ─
    print(f"{'시나리오':<28} {'depth':<7} {'boss_lk':<9} {'zone':<6} {'regress':<8} {'chain':<20}")
    print("-" * 76)
    for r in rows:
        z = "🗺 2" if r["zone"] == 2 else "1"
        reg = "⤺" if r["regress"] else ""
        chain_str = f"{r['chain_n']}: {r['chain_phases']}"
        print(
            f"{r['id']:<28} {r['depth']:<7} {r['boss_lk']:<9.3f} "
            f"{z:<6} {reg:<8} {chain_str}"
        )

    # ─ 통계 요약 ─
    total = len(scenarios)
    print()
    print("=" * 76)
    print(" 통계 요약")
    print("=" * 76)
    print(f" Zone 2 진입       : {zone2_count}/{total} ({zone2_count / total * 100:.1f}%)")
    print(f" 회귀 권고         : {regress_count}/{total} ({regress_count / total * 100:.1f}%)")
    print(f" chain 정합        : {chain_valid}/{total}")
    print()

    print(" lane 별 Zone 2 진입:")
    for lane in sorted(lane_zone2.keys()):
        z, t = lane_zone2[lane]
        print(f"   {lane:<10} {z}/{t} ({z / t * 100:.0f}%)")
    print()

    # 카탈로그 커버리지 (있으면 알림)
    if coverage_misses:
        print(f" ⚠ 카탈로그 미수록 단서 키: {len(coverage_misses)}개")
        for ck, cnt in sorted(coverage_misses.items(), key=lambda x: -x[1])[:5]:
            print(f"   {ck} (시나리오 {cnt}건)")
        print()

    # ─ 시연 후 fit 권고 (paradigm §21.8 #1) ─
    print("=" * 76)
    print(" 시연 후 fit 권고 (paradigm §21.8 #1)")
    print("=" * 76)
    zone2_pct = zone2_count / total * 100 if total else 0
    if zone2_pct < 30:
        print(f" ⚠ Zone 2 진입 비율 {zone2_pct:.0f}% 너무 낮음 — 트리거 완화 권장:")
        print(f"   TRIGGER_MIN_DEPTH={TRIGGER_MIN_DEPTH} → 2 또는")
        print(f"   TRIGGER_MIN_LIKELIHOOD={TRIGGER_MIN_LIKELIHOOD} → 0.40")
    elif zone2_pct > 90:
        print(f" ⚠ Zone 2 진입 비율 {zone2_pct:.0f}% 너무 높음 — 트리거 강화 권장:")
        print(f"   TRIGGER_MIN_LIKELIHOOD={TRIGGER_MIN_LIKELIHOOD} → 0.50")
    else:
        print(f" ✓ Zone 2 진입 비율 {zone2_pct:.0f}% 적정 (30~90% 권장 범위)")

    if regress_count > total * 0.10:
        print(f" ⚠ 회귀 권고 빈도 {regress_count}/{total} ({regress_count / total * 100:.0f}%) 높음 — REGRESS_GAP_THRESHOLD 완화 검토")
    else:
        print(f" ✓ 회귀 권고 빈도 {regress_count}/{total} ({regress_count / total * 100:.0f}%) 정상")

    # ─ 부정합 보고 ─
    print()
    print("=" * 76)
    if chain_field_errors:
        print(f" ❌ chain 부정합 {len(chain_field_errors)}건:")
        for f in chain_field_errors:
            print(f"   - {f['id']}: {f['reason']}")
        print("=" * 76)
        return 1

    print(f" ✓ 모든 {total} 시나리오 chain 정합 통과")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
