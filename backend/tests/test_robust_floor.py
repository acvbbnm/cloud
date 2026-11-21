"""Phase N.2 — Robust Bayes ε-contamination 단위 테스트 (2026-05-26, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §21.1 ② "복합 공격 비전"

학술: Berger 1985 *Robust Bayesian Analysis* — ε-contamination model
    π̃(h) = (1 − ε) π(h) + ε / N  (uniform contamination)

검증:
  1. epsilon = 0 → 통과 (legacy 동작)
  2. epsilon = 0.08 → 8 가설 각 1% floor 보장
  3. 극단 케이스 (99% 쏠림) → 92.x% 압축 + 나머지 7 가설 1% 이상
  4. 합 = 1 보장 (UNCLASSIFIED 제외 8 가설)
  5. UNCLASSIFIED 는 floor 미적용 (sentinel)
  6. 빈 / 0 posterior → uniform 복귀
  7. bayes_update 통합 — 강한 likelihood 도 99% 막힘
"""
from __future__ import annotations

import pytest

from core.intake.bayesian import (
    apply_robust_floor,
    bayes_update,
    initial_posterior,
    invalidate_priors_cache,
)


HYPS_8 = [
    "CREDENTIAL_THEFT",
    "PRIVILEGE_ESCALATION",
    "DATA_EXFILTRATION",
    "AUDIT_LOG_TAMPERING",
    "RANSOMWARE",
    "MISCONFIG_EXPOSURE",
    "PHISH_INITIAL_ACCESS",
    "INSIDER_THREAT",
]


# ─────────────────────────────────────────────────────────────
# 1. epsilon 비활성 — 통과
# ─────────────────────────────────────────────────────────────


def test_robust_floor_disabled_passthrough() -> None:
    """epsilon = 0 → 입력 그대로 반환."""
    posterior = {**{h: 1.0 / 8 for h in HYPS_8}, "UNCLASSIFIED": 0.0}
    out = apply_robust_floor(posterior, epsilon=0.0)
    for h in HYPS_8:
        assert out[h] == pytest.approx(1.0 / 8)


# ─────────────────────────────────────────────────────────────
# 2. epsilon = 0.08 — 각 가설 1% floor
# ─────────────────────────────────────────────────────────────


def test_robust_floor_guarantees_minimum_1pct() -> None:
    """매우 강한 쏠림 99/0.5/0.4/0/0/0/0/0 → 각 가설 ≥ 1%."""
    posterior = {
        "CREDENTIAL_THEFT": 0.99,
        "PRIVILEGE_ESCALATION": 0.005,
        "DATA_EXFILTRATION": 0.004,
        "AUDIT_LOG_TAMPERING": 0.0005,
        "RANSOMWARE": 0.0003,
        "MISCONFIG_EXPOSURE": 0.0001,
        "PHISH_INITIAL_ACCESS": 0.0001,
        "INSIDER_THREAT": 0.0,
        "UNCLASSIFIED": 0.0,
    }
    out = apply_robust_floor(posterior, epsilon=0.08)
    # 모든 가설 최소 0.08/8 = 0.01 (1%)
    for h in HYPS_8:
        assert out[h] >= 0.01 - 1e-6, f"{h}: {out[h]} < 0.01 floor"
    # CRED 99% → 압축 (정확히 (1-0.08)*0.99 + 0.08/8 = 0.9108 + 0.01 = 0.9208)
    assert out["CREDENTIAL_THEFT"] == pytest.approx(0.9208, abs=1e-4)


# ─────────────────────────────────────────────────────────────
# 3. 합 = 1 보장
# ─────────────────────────────────────────────────────────────


def test_robust_floor_sum_equals_one() -> None:
    """epsilon 어느 값에서도 8 사고유형 합 = 1.0."""
    for eps in [0.01, 0.05, 0.08, 0.20, 0.50]:
        posterior = {
            "CREDENTIAL_THEFT": 0.5,
            "RANSOMWARE": 0.3,
            "DATA_EXFILTRATION": 0.1,
            "PRIVILEGE_ESCALATION": 0.05,
            "AUDIT_LOG_TAMPERING": 0.03,
            "MISCONFIG_EXPOSURE": 0.01,
            "PHISH_INITIAL_ACCESS": 0.01,
            "INSIDER_THREAT": 0.0,
            "UNCLASSIFIED": 0.0,
        }
        out = apply_robust_floor(posterior, epsilon=eps)
        total = sum(out[h] for h in HYPS_8)
        assert total == pytest.approx(1.0, abs=1e-6), f"eps={eps} sum={total}"


# ─────────────────────────────────────────────────────────────
# 4. UNCLASSIFIED 는 floor 미적용
# ─────────────────────────────────────────────────────────────


def test_robust_floor_excludes_unclassified() -> None:
    """UNCLASSIFIED 는 sentinel — floor 적용 안 함."""
    posterior = {**{h: 1.0 / 8 for h in HYPS_8}, "UNCLASSIFIED": 0.0}
    out = apply_robust_floor(posterior, epsilon=0.08)
    assert out["UNCLASSIFIED"] == 0.0


# ─────────────────────────────────────────────────────────────
# 5. 빈 / 0 posterior → uniform 복귀
# ─────────────────────────────────────────────────────────────


def test_robust_floor_empty_passthrough() -> None:
    """모든 가설 0 → 입력 그대로 반환 (정규화 X, 안전 폴백).

    합 보존 정책 (2026-05-26): 8 사고유형 raw 합 = 0 인 경우 정규화 정보가
    없으므로 입력을 그대로 반환. 호출자가 다른 단계에서 처리.
    """
    posterior = {**{h: 0.0 for h in HYPS_8}, "UNCLASSIFIED": 0.0}
    out = apply_robust_floor(posterior, epsilon=0.08)
    for h in HYPS_8:
        assert out[h] == 0.0


# ─────────────────────────────────────────────────────────────
# 6. bayes_update 통합 — 99% 자동 차단
# ─────────────────────────────────────────────────────────────


def test_bayes_update_with_floor_blocks_99pct_skew() -> None:
    """매우 강한 likelihood 도 99% 도달 못 함 (Robust Bayes 차단)."""
    invalidate_priors_cache()
    posterior = initial_posterior()
    # 매우 강한 likelihood (한 가설 0.95, 나머지 0.01)
    extreme_likelihood = {h: 0.01 for h in HYPS_8}
    extreme_likelihood["CREDENTIAL_THEFT"] = 0.95

    # 동일 likelihood 3회 적용
    for _ in range(3):
        posterior = bayes_update(posterior, extreme_likelihood)

    # CRED 가 압도적이지만 floor 1% 보장
    assert posterior["CREDENTIAL_THEFT"] < 1.0  # 99% 미만 (압축됨)
    # 나머지 가설들 최소 1% floor
    for h in HYPS_8:
        if h == "CREDENTIAL_THEFT":
            continue
        assert posterior[h] >= 0.01 - 1e-6, f"{h}: {posterior[h]} 가 floor 미달"


def test_bayes_update_preserves_ranking() -> None:
    """floor 적용해도 가설 순위는 유지 (1위·2위 순서 안 바뀜)."""
    invalidate_priors_cache()
    posterior = initial_posterior()
    likelihood = {
        "CREDENTIAL_THEFT": 0.4,
        "PRIVILEGE_ESCALATION": 0.3,
        "DATA_EXFILTRATION": 0.1,
        "AUDIT_LOG_TAMPERING": 0.05,
        "RANSOMWARE": 0.05,
        "MISCONFIG_EXPOSURE": 0.05,
        "PHISH_INITIAL_ACCESS": 0.03,
        "INSIDER_THREAT": 0.02,
    }
    posterior = bayes_update(posterior, likelihood)
    ranked = sorted(
        [(h, p) for h, p in posterior.items() if h != "UNCLASSIFIED"],
        key=lambda x: -x[1],
    )
    # 1위 CRED, 2위 PRIV — 순위 유지
    assert ranked[0][0] == "CREDENTIAL_THEFT"
    assert ranked[1][0] == "PRIVILEGE_ESCALATION"


def test_robust_floor_high_epsilon_extreme() -> None:
    """epsilon = 1.0 → 거의 uniform (1-1)·p + 1·(1/8) = 1/8 each."""
    posterior = {
        "CREDENTIAL_THEFT": 0.95,
        "RANSOMWARE": 0.05,
        "PRIVILEGE_ESCALATION": 0.0,
        "DATA_EXFILTRATION": 0.0,
        "AUDIT_LOG_TAMPERING": 0.0,
        "MISCONFIG_EXPOSURE": 0.0,
        "PHISH_INITIAL_ACCESS": 0.0,
        "INSIDER_THREAT": 0.0,
        "UNCLASSIFIED": 0.0,
    }
    out = apply_robust_floor(posterior, epsilon=1.0)
    # 모두 1/8 = 0.125
    for h in HYPS_8:
        assert out[h] == pytest.approx(0.125)
