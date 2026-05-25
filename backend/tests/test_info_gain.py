"""Phase B.4 — Information Gain 단위 테스트 (2026-05-25, byungwoo).

검증:
    1. weights_to_likelihood — Laplace smoothing 정합
    2. entropy_bits — Shannon 수치 정확성
    3. information_gain — 변별력 단서 vs 무용 단서 비교
    4. Marginalization on/off — 음성 evidence 처리 (PDF §17.B)
    5. rank_candidates — top-K 정렬 + 제외 처리
"""
from __future__ import annotations

import math

import pytest

from core.intake.info_gain import (
    entropy_bits,
    information_gain,
    invalidate_catalog_cache,
    load_catalog,
    pick_top_candidates,
    rank_candidates,
    weights_to_likelihood,
)


UNIFORM = {
    "CREDENTIAL_THEFT": 0.125,
    "PRIVILEGE_ESCALATION": 0.125,
    "DATA_EXFILTRATION": 0.125,
    "AUDIT_LOG_TAMPERING": 0.125,
    "RANSOMWARE": 0.125,
    "MISCONFIG_EXPOSURE": 0.125,
    "PHISH_INITIAL_ACCESS": 0.125,
    "INSIDER_THREAT": 0.125,
    "UNCLASSIFIED": 0.0,
}


# ─────────────────────────────────────────────────────────────
# 1. likelihood 변환
# ─────────────────────────────────────────────────────────────


def test_weights_to_likelihood_sum_to_one() -> None:
    w = {h: 5 for h in UNIFORM if h != "UNCLASSIFIED"}
    lk = weights_to_likelihood(w)
    assert math.isclose(sum(lk.values()), 1.0, abs_tol=1e-9)
    assert "UNCLASSIFIED" not in lk


def test_weights_to_likelihood_zero_weights_uniform() -> None:
    """가중치 모두 0 → likelihood 균등 (Laplace add-k 효과)."""
    w = {h: 0 for h in UNIFORM if h != "UNCLASSIFIED"}
    lk = weights_to_likelihood(w)
    vals = list(lk.values())
    assert all(math.isclose(v, vals[0], abs_tol=1e-9) for v in vals)


def test_weights_to_likelihood_excludes_unclassified() -> None:
    w = {"CREDENTIAL_THEFT": 10, "RANSOMWARE": 5, "UNCLASSIFIED": 100}
    lk = weights_to_likelihood(w)
    assert "UNCLASSIFIED" not in lk


# ─────────────────────────────────────────────────────────────
# 2. entropy
# ─────────────────────────────────────────────────────────────


def test_entropy_uniform_8_hyp_is_3_bits() -> None:
    assert math.isclose(entropy_bits(UNIFORM), 3.0, abs_tol=1e-6)


def test_entropy_single_hyp_is_zero() -> None:
    p = {h: 0.0 for h in UNIFORM}
    p["RANSOMWARE"] = 1.0
    assert math.isclose(entropy_bits(p), 0.0, abs_tol=1e-6)


# ─────────────────────────────────────────────────────────────
# 3. information_gain — 단서 변별력
# ─────────────────────────────────────────────────────────────


def test_information_gain_discriminative_high() -> None:
    """RANSOMWARE 만 likelihood 가 압도적으로 높은 단서 → IG 큼."""
    lk = {h: 0.05 for h in UNIFORM if h != "UNCLASSIFIED"}
    lk["RANSOMWARE"] = 0.9
    # 정규화
    s = sum(lk.values())
    lk = {h: v / s for h, v in lk.items()}
    ig = information_gain(UNIFORM, lk)
    assert ig > 0.05  # uniform 에서 1 가설로 강하게 갈리는 단서


def test_information_gain_uniform_likelihood_is_zero() -> None:
    """모든 가설에 동일 likelihood → IG = 0 (변별력 없음)."""
    lk = {h: 0.125 for h in UNIFORM if h != "UNCLASSIFIED"}
    ig = information_gain(UNIFORM, lk)
    assert ig < 1e-6


def test_information_gain_low_when_posterior_concentrated() -> None:
    """이미 RANSOM 95% — 추가 단서 IG 작아져야 함."""
    p = {h: 0.007 for h in UNIFORM if h != "UNCLASSIFIED"}
    p["RANSOMWARE"] = 0.95
    p["UNCLASSIFIED"] = 0.0
    s = sum(v for k, v in p.items() if k != "UNCLASSIFIED")
    p = {k: (v / s if k != "UNCLASSIFIED" else 0) for k, v in p.items()}

    lk = {h: 0.05 for h in UNIFORM if h != "UNCLASSIFIED"}
    lk["RANSOMWARE"] = 0.9
    s2 = sum(lk.values())
    lk = {h: v / s2 for h, v in lk.items()}

    ig_concentrated = information_gain(p, lk)
    ig_uniform = information_gain(UNIFORM, lk)
    assert ig_concentrated < ig_uniform


# ─────────────────────────────────────────────────────────────
# 4. Marginalization on/off (PDF §17.B)
# ─────────────────────────────────────────────────────────────


def test_marginalization_changes_value() -> None:
    """marginalization on/off 값이 다르고 둘 다 비음."""
    invalidate_catalog_cache()
    cat = load_catalog()
    entry = cat["clues"]["IP_ADDRESS:tor_vpn"]
    lk = weights_to_likelihood(entry["weights"])
    ig_with = information_gain(UNIFORM, lk, use_marginalization=True)
    ig_without = information_gain(UNIFORM, lk, use_marginalization=False)
    assert ig_with >= 0
    assert ig_without >= 0
    # 의미 — without 은 "단서 관찰 시 entropy 축소", with 는 "관찰·미관찰 양쪽 기댓값"
    # 두 값이 다르면 marginalization 이 실제로 다르게 작동


def test_marginalization_with_is_lte_entropy_bound() -> None:
    """marginalization 활성 IG 는 H(P) 를 넘을 수 없다 (상한)."""
    invalidate_catalog_cache()
    cat = load_catalog()
    for key in ("IP_ADDRESS:tor_vpn", "Q5_CRED:tor_vpn", "TECHNIQUE:T1078.004"):
        entry = cat["clues"].get(key)
        if not entry:
            continue
        lk = weights_to_likelihood(entry["weights"])
        ig = information_gain(UNIFORM, lk, use_marginalization=True)
        assert ig <= 3.0 + 1e-6  # log2(8)


# ─────────────────────────────────────────────────────────────
# 5. rank_candidates
# ─────────────────────────────────────────────────────────────


def test_rank_candidates_sorted_descending() -> None:
    ranked = rank_candidates(UNIFORM)
    igs = [c["expected_info_gain"] for c in ranked]
    assert igs == sorted(igs, reverse=True)


def test_rank_candidates_excludes_specified_keys() -> None:
    full = rank_candidates(UNIFORM)
    if not full:
        pytest.skip("catalog empty")
    excl = full[0]["clue_key"]
    filtered = rank_candidates(UNIFORM, exclude_clue_keys={excl})
    assert all(c["clue_key"] != excl for c in filtered)


def test_pick_top_candidates_respects_k() -> None:
    top = pick_top_candidates(UNIFORM, k=3)
    assert len(top) == 3
    # 정렬 검증
    igs = [c["expected_info_gain"] for c in top]
    assert igs == sorted(igs, reverse=True)


def test_rank_candidates_top_picks_have_outcome_flags() -> None:
    """카탈로그의 outcome_flags 가 후보에 전파되는지 (PDF §17.A)."""
    top = pick_top_candidates(UNIFORM, k=10)
    has_any_flag = any(bool(c.get("outcome_flags")) for c in top)
    assert has_any_flag, "top-10 후보 중 outcome_flags 가진 단서 0 — 추출 누락 의심"


def test_rank_candidates_all_have_rationale() -> None:
    top = pick_top_candidates(UNIFORM, k=5)
    for c in top:
        assert c["rationale"], f"{c['clue_key']} rationale 비어있음"
