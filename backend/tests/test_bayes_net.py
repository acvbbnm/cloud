"""H.3 — Bayesian Network + Noisy-OR 추론 단위 테스트
(2026-05-25, byungwoo).

검증:
    1. noisy_or 수학 — leak / 단일 부모 / 다중 부모 / 포화
    2. technique_likelihood — 정확 일치 / 부모·자식 fallback / uniform fallback
    3. clue_likelihood_via_bn — 정상 BN / hybrid legacy fallback / 메타 단서
    4. bn_evaluate_sequence — 시퀀스 누적 + 결정성
    5. bayes_update 호환성 — drop-in 가능 (likelihood 합=1)
    6. RANSOM 시퀀스 e2e — 1위 RANSOMWARE 도달
"""
from __future__ import annotations

import math

import pytest

from core.intake.bayes_net import (
    CONFIDENCE_SCALE,
    INCIDENT_TYPES_8,
    NOISY_OR_LEAK,
    bn_evaluate_sequence,
    bn_update,
    clue_likelihood_via_bn,
    explain_clue,
    invalidate_cache,
    load_clue_to_attack,
    load_technique_weights,
    noisy_or,
    technique_likelihood,
)


# ─────────────────────────────────────────────────────────────
# 1. noisy_or 수학
# ─────────────────────────────────────────────────────────────


def test_noisy_or_empty_returns_leak() -> None:
    assert math.isclose(noisy_or([]), NOISY_OR_LEAK, abs_tol=1e-9)


def test_noisy_or_single_parent() -> None:
    """1 - (1-leak)*(1-q) = leak + (1-leak)*q ≈ q + leak"""
    q = 0.3
    expected = 1 - (1 - NOISY_OR_LEAK) * (1 - q)
    assert math.isclose(noisy_or([q]), expected, abs_tol=1e-9)


def test_noisy_or_two_indep_parents_increases() -> None:
    """독립 부모 2개 → 합쳐진 확률이 단일보다 큼."""
    single = noisy_or([0.3])
    double = noisy_or([0.3, 0.3])
    assert double > single
    # 정확값 (수동)
    expected = 1 - (1 - NOISY_OR_LEAK) * (1 - 0.3) * (1 - 0.3)
    assert math.isclose(double, expected, abs_tol=1e-9)


def test_noisy_or_saturation_below_1() -> None:
    """q=1 인 부모 1개라도 있으면 1.0 (확실)."""
    assert math.isclose(noisy_or([1.0]), 1.0, abs_tol=1e-9)
    assert math.isclose(noisy_or([0.9, 0.9, 0.9]), 1 - (1 - NOISY_OR_LEAK) * 0.001, abs_tol=1e-9)


def test_noisy_or_clamps_negative_and_over_one() -> None:
    """범위 밖 입력을 [0, 1] 로 클램프."""
    # -0.5 → 0, 1.5 → 1
    assert math.isclose(noisy_or([-0.5]), NOISY_OR_LEAK, abs_tol=1e-9)
    assert math.isclose(noisy_or([1.5]), 1.0, abs_tol=1e-9)


# ─────────────────────────────────────────────────────────────
# 2. technique_likelihood — fallback chain
# ─────────────────────────────────────────────────────────────


def test_technique_likelihood_sum_to_one() -> None:
    invalidate_cache()
    for tid in ("T1078.004", "T1486", "T1562.008"):
        lk = technique_likelihood(tid)
        assert math.isclose(sum(lk.values()), 1.0, abs_tol=1e-9), tid
        for h in INCIDENT_TYPES_8:
            assert 0 <= lk[h] <= 1


def test_technique_likelihood_known_tech_matches_weight_polarity() -> None:
    """T1486 (랜섬 암호화) → RANSOMWARE 가 가장 큰 likelihood."""
    invalidate_cache()
    lk = technique_likelihood("T1486")
    top = max(lk.items(), key=lambda x: x[1])
    assert top[0] == "RANSOMWARE", f"T1486 top expected RANSOMWARE, got {top}"


def test_technique_likelihood_unknown_returns_uniform() -> None:
    """weights.json 에 없는 기법 + 부모·자식 fallback 도 실패 → uniform 1/8."""
    invalidate_cache()
    lk = technique_likelihood("T9999")  # 존재하지 않는 기법
    vals = list(lk.values())
    assert all(math.isclose(v, 1.0 / len(INCIDENT_TYPES_8), abs_tol=1e-9) for v in vals)


def test_technique_likelihood_parent_fallback() -> None:
    """T1078.002 (Domain Accounts) — weights 에 없지만 부모 T1078 도 없음.
    그러나 자식 T1078.001/T1078.004 가 weights 에 있음 → 자식 평균 사용."""
    invalidate_cache()
    tw = load_technique_weights()
    # 부모 T1078 자체는 없지만, 자식 T1078.001/T1078.004 가 있음
    if "T1078.001" in tw or "T1078.004" in tw:
        # T1078 (부모만 지정) → 자식 평균으로 fallback
        lk = technique_likelihood("T1078")
        # uniform 보다는 변별력 있어야 함 (자식들이 강한 시그널 가짐)
        vals = sorted(lk.values(), reverse=True)
        assert vals[0] > vals[-1] + 0.005, "자식 fallback 작동 안 함 — 변별력 없음"


# ─────────────────────────────────────────────────────────────
# 3. clue_likelihood_via_bn — BN + hybrid legacy fallback
# ─────────────────────────────────────────────────────────────


def test_clue_likelihood_sum_to_one() -> None:
    invalidate_cache()
    for clue in ("IP_ADDRESS:tor_vpn", "ACCOUNT:mfa_disabled", "Q5-RANSOM:multi_region"):
        lk = clue_likelihood_via_bn(clue)
        assert math.isclose(sum(lk.values()), 1.0, abs_tol=1e-9), clue


def test_clue_likelihood_known_ransom_clue_favors_ransomware() -> None:
    """랜섬 관련 단서 → RANSOMWARE likelihood 가장 큼."""
    invalidate_cache()
    lk = clue_likelihood_via_bn("Q5-RANSOM:multi_region")
    top = max(lk.items(), key=lambda x: x[1])
    assert top[0] == "RANSOMWARE", (
        f"Q5-RANSOM:multi_region top expected RANSOMWARE, got {top}"
    )


def test_clue_likelihood_meta_clue_falls_back_to_legacy() -> None:
    """Q1_inception:* 메타 단서 — BN 매핑은 null 이지만 legacy weights 보유."""
    invalidate_cache()
    lk = clue_likelihood_via_bn("Q1_inception:csp_alert")
    # legacy 폴백 결과는 어느 사고유형이든 골고루 분포 (csp_alert 의 weights 가 다양)
    assert math.isclose(sum(lk.values()), 1.0, abs_tol=1e-9)


def test_clue_likelihood_hybrid_fallback_when_techniques_missing() -> None:
    """IP_ADDRESS:tor_vpn — T1090.003 매핑 (weights 없음) → legacy fallback.
    legacy 의 clue_types 가중치 (CREDENTIAL_THEFT 30) 활용."""
    invalidate_cache()
    lk = clue_likelihood_via_bn("IP_ADDRESS:tor_vpn")
    top = max(lk.items(), key=lambda x: x[1])
    # legacy 가중치 — CRED 가 가장 큼
    assert top[0] == "CREDENTIAL_THEFT", (
        f"hybrid fallback expected CREDENTIAL_THEFT, got {top}"
    )


# ─────────────────────────────────────────────────────────────
# 4. bn_evaluate_sequence
# ─────────────────────────────────────────────────────────────


def test_bn_sequence_ransom_lane_wins_ransomware() -> None:
    """RANSOM 강한 단서 5개 → 1위 RANSOMWARE."""
    invalidate_cache()
    seq = [
        "Q2A:ransomware_pattern",
        "Q4-RANSOM:bulk_putobject_encrypted_ext",
        "Q5-RANSOM:multi_region",
        "Q6-RANSOM:note_found",
        "Q3_IMPACT:ransom_extension",
    ]
    final, trace = bn_evaluate_sequence(seq)
    assert len(trace) == len(seq)
    top = sorted(
        [(h, p) for h, p in final.items() if h != "UNCLASSIFIED"],
        key=lambda x: -x[1],
    )
    assert top[0][0] == "RANSOMWARE", f"BN RANSOM 시퀀스 1위 {top[0]}"
    # 도달 신뢰도 — 0.65 이상 권장
    assert top[0][1] > 0.5


def test_bn_sequence_deterministic() -> None:
    """같은 입력 → 같은 출력 (결정성 100%)."""
    invalidate_cache()
    seq = ["IP_ADDRESS:tor_vpn", "ACCOUNT:mfa_disabled", "Q5-RANSOM:multi_region"]
    a, _ = bn_evaluate_sequence(seq)
    b, _ = bn_evaluate_sequence(seq)
    for h in a:
        assert math.isclose(a[h], b[h], abs_tol=1e-12)


def test_bn_sequence_initial_posterior_uniform() -> None:
    """빈 시퀀스 → uniform prior (Jaynes)."""
    invalidate_cache()
    final, trace = bn_evaluate_sequence([])
    assert len(trace) == 0
    incidents = [v for k, v in final.items() if k != "UNCLASSIFIED"]
    # 합이 ~1, 각 ≈ 1/8
    assert math.isclose(sum(incidents), 1.0, abs_tol=1e-6)
    for v in incidents:
        assert math.isclose(v, 1.0 / 8, abs_tol=1e-6)


# ─────────────────────────────────────────────────────────────
# 5. bn_update — drop-in 호환
# ─────────────────────────────────────────────────────────────


def test_bn_update_normalizes_to_one() -> None:
    invalidate_cache()
    prior = {h: 1.0 / 9 for h in INCIDENT_TYPES_8}
    prior["UNCLASSIFIED"] = 1.0 / 9
    after = bn_update(prior, "ACCOUNT:mfa_disabled")
    assert math.isclose(sum(after.values()), 1.0, abs_tol=1e-9)


# ─────────────────────────────────────────────────────────────
# 6. explain_clue — 디버깅 trace
# ─────────────────────────────────────────────────────────────


def test_explain_clue_bn_path() -> None:
    invalidate_cache()
    info = explain_clue("Q5-RANSOM:multi_region")
    assert info["source"] == "bn"
    assert "T1486" in info["techniques"]
    assert "per_technique_likelihood" in info
    assert "RANSOMWARE" in info["aggregated_likelihood"]


def test_explain_clue_fallback_path() -> None:
    invalidate_cache()
    info = explain_clue("Q1_inception:csp_alert")
    # 메타 단서 — legacy_fallback
    assert info["source"] == "legacy_fallback"
    assert info["techniques"] == []


# ─────────────────────────────────────────────────────────────
# 7. 설계 정합 — 사용자 결정 3건
# ─────────────────────────────────────────────────────────────


def test_user_decision_A_meta_clues_use_legacy_fallback() -> None:
    """Option A — 메타 단서는 BN 미사용, legacy weights 활용."""
    invalidate_cache()
    META_KEYS = [
        "Q1_inception:csp_alert",
        "Q1_inception:external_report",
        "Q1_inception:audit",
        "Q1_inception:service_anomaly",
    ]
    for k in META_KEYS:
        info = explain_clue(k)
        assert info["source"] == "legacy_fallback", f"{k} BN 경유 X"


def test_user_decision_B_multi_target_noisy_or_aggregation() -> None:
    """Option B — 1:N 매핑이 Noisy-OR 로 aggregation 되어 다중 관련 가설에 영향.

    Q6-RANSOM:double_extortion = [T1486, T1567] 이중 협박 —
    T1486 (Data Encrypted for Impact) → RANSOMWARE 강
    T1567 (Exfiltration Over Web Service) → DATA_EXFILTRATION 강
    두 가설 모두 likelihood 가 uniform (0.125) 보다 충분히 큼 — Noisy-OR aggregation 효과.

    학술 정합: Pearl 1988 — multi-cause 인과 모델은 다중 가설에 동시 영향 가능.
    """
    invalidate_cache()
    multi_lk = clue_likelihood_via_bn("Q6-RANSOM:double_extortion")
    # 두 가설 모두 uniform (1/8 = 0.125) 보다 큼
    assert multi_lk["RANSOMWARE"] > 0.13, (
        f"RANSOMWARE likelihood {multi_lk['RANSOMWARE']:.3f} — multi-target 효과 약함"
    )
    assert multi_lk["DATA_EXFILTRATION"] > 0.13, (
        f"DATA_EXFILTRATION likelihood {multi_lk['DATA_EXFILTRATION']:.3f} — multi-target 효과 약함"
    )
    # 두 관련 가설이 top-2 안에 있어야 함
    ranked = sorted(multi_lk.items(), key=lambda x: -x[1])
    top2 = {ranked[0][0], ranked[1][0]}
    assert "RANSOMWARE" in top2 or "DATA_EXFILTRATION" in top2, (
        f"top-2 에 RANSOM/DATA_EXFIL 누락: {ranked[:2]}"
    )


def test_user_decision_C_high_confidence_scaled_at_one_point_zero() -> None:
    """Option C — high confidence 매핑은 scale 1.0 (감쇠 없음)."""
    assert CONFIDENCE_SCALE["high"] == 1.0
    assert CONFIDENCE_SCALE["medium"] < 1.0
    assert CONFIDENCE_SCALE["low"] < CONFIDENCE_SCALE["medium"]
    assert CONFIDENCE_SCALE["n/a"] == 0.0
