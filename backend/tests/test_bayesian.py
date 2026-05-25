"""베이지안 가설 분류 모듈 단위 테스트 — Phase 2.5 실험 (byungwoo, 2026-05-25).

검증 범위:
  · priors.json 합 = 1.0 (정규화)
  · weights.json 모든 답변 key 의 likelihood 변환 결정성 + 합 = 1.0
  · bayes_update 누적성 (같은 입력 시퀀스 → 같은 사후확률)
  · 신뢰도 분류 (auto_confirm / propose_single / propose_composite / continue_or_skip)
"""
import json
from pathlib import Path

import pytest

from core.intake.bayesian import (
    bayes_update,
    confidence_level,
    initial_posterior,
    invalidate_priors_cache,
    load_priors,
    top_n,
    weights_to_likelihood,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    """매 테스트마다 priors 캐시 초기화 — 격리 보장."""
    invalidate_priors_cache()
    yield
    invalidate_priors_cache()


def _weights_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "triage" / "weights.json"


# ── priors.json 정합 ────────────────────────────────────────


def test_priors_sum_to_one():
    """Verizon DBIR prior 합 = 1.0 (±0.001)."""
    priors = load_priors()
    total = sum(priors.values())
    assert abs(total - 1.0) < 0.001, f"priors 합 {total} != 1.0"


def test_priors_8_incident_types_present():
    """8 사고유형 모두 prior 정의."""
    priors = load_priors()
    expected = {
        "CREDENTIAL_THEFT", "PRIVILEGE_ESCALATION", "DATA_EXFILTRATION",
        "AUDIT_LOG_TAMPERING", "RANSOMWARE", "MISCONFIG_EXPOSURE",
        "PHISH_INITIAL_ACCESS", "INSIDER_THREAT",
    }
    assert set(priors.keys()) == expected, (
        f"priors 키 불일치: {set(priors.keys()) ^ expected}"
    )


def test_initial_posterior_includes_unclassified():
    """베이즈 시작점은 priors + UNCLASSIFIED=0 포함."""
    post = initial_posterior()
    assert "UNCLASSIFIED" in post
    assert post["UNCLASSIFIED"] == 0.0
    # priors 합 = 1.0 + UNCLASSIFIED 0 → 전체 합도 1.0
    assert abs(sum(post.values()) - 1.0) < 0.001


# ── likelihood 변환 ────────────────────────────────────────


def test_likelihood_sum_to_one():
    """weights → likelihood 변환 결과 합 = 1.0 (정규화)."""
    weights = {
        "CREDENTIAL_THEFT": 30,
        "PRIVILEGE_ESCALATION": 0,
        "DATA_EXFILTRATION": 0,
        "AUDIT_LOG_TAMPERING": 0,
        "RANSOMWARE": 0,
        "MISCONFIG_EXPOSURE": 0,
        "PHISH_INITIAL_ACCESS": 15,
        "INSIDER_THREAT": 0,
        "UNCLASSIFIED": 0,
        "source": "test",  # 비숫자 키 — 변환에서 무시되어야
    }
    lk = weights_to_likelihood(weights)
    assert "UNCLASSIFIED" not in lk, "UNCLASSIFIED 는 likelihood 변환에서 제외"
    assert "source" not in lk, "비숫자 키는 likelihood 변환에서 제외"
    assert abs(sum(lk.values()) - 1.0) < 0.001


def test_likelihood_zero_weight_gets_smoothing():
    """가중치 0 인 사고유형도 smoothing 으로 base 확률 보존."""
    weights = {h: 0 for h in [
        "CREDENTIAL_THEFT", "PRIVILEGE_ESCALATION", "DATA_EXFILTRATION",
        "AUDIT_LOG_TAMPERING", "RANSOMWARE", "MISCONFIG_EXPOSURE",
        "PHISH_INITIAL_ACCESS", "INSIDER_THREAT",
    ]}
    weights["CREDENTIAL_THEFT"] = 30
    lk = weights_to_likelihood(weights)
    # 모든 사고유형의 likelihood > 0 (0 곱하면 posterior 영구 0 되는 것 방지)
    for h, p in lk.items():
        assert p > 0, f"{h} likelihood 가 0 — smoothing 미적용"


def test_all_weights_json_keys_normalize():
    """weights.json 의 모든 답변 key 가 likelihood 변환 후 합 = 1.0."""
    with _weights_path().open(encoding="utf-8") as f:
        W = json.load(f)["decision_tree_answers"]
    failed = []
    for key, weights in W.items():
        lk = weights_to_likelihood(weights)
        if not lk:
            failed.append(f"{key}: empty likelihood")
            continue
        total = sum(lk.values())
        if abs(total - 1.0) > 0.001:
            failed.append(f"{key}: 합 {total:.4f}")
    assert not failed, f"likelihood 변환 실패 {len(failed)}건: {failed[:5]}"


# ── bayes_update ────────────────────────────────────────────


def test_bayes_update_deterministic():
    """같은 입력 → 같은 사후확률 (결정성 100%)."""
    post = initial_posterior()
    lk = {"CREDENTIAL_THEFT": 0.5, "RANSOMWARE": 0.3, "INSIDER_THREAT": 0.2}
    p1 = bayes_update(post, lk)
    p2 = bayes_update(post, lk)
    for h in p1:
        assert p1[h] == p2[h], f"{h} 결정성 위반: {p1[h]} != {p2[h]}"


def test_bayes_update_sum_preserved():
    """베이즈 갱신 후 사후확률 합 = 1.0 (정규화)."""
    post = initial_posterior()
    lk = {"CREDENTIAL_THEFT": 0.6, "PHISH_INITIAL_ACCESS": 0.3, "RANSOMWARE": 0.1}
    new_post = bayes_update(post, lk)
    assert abs(sum(new_post.values()) - 1.0) < 0.001


def test_bayes_update_strengthens_evidence():
    """관측된 증거의 사고유형 사후확률이 prior 보다 증가."""
    post = initial_posterior()
    cred_prior = post["CREDENTIAL_THEFT"]  # 0.12
    # CRED 강한 likelihood
    lk = {h: (0.5 if h == "CREDENTIAL_THEFT" else 0.06) for h in post if h != "UNCLASSIFIED"}
    new_post = bayes_update(post, lk)
    assert new_post["CREDENTIAL_THEFT"] > cred_prior, (
        f"CRED 사후확률 {new_post['CREDENTIAL_THEFT']:.3f} 이 prior {cred_prior:.3f} 보다 낮음"
    )


def test_bayes_update_zero_likelihood_safe_fallback():
    """모든 likelihood 가 0 이면 prior 로 안전 복귀 (분모 0 방지)."""
    post = initial_posterior()
    lk = {h: 0.0 for h in post if h != "UNCLASSIFIED"}
    new_post = bayes_update(post, lk)
    # prior 와 같아야 함
    for h in post:
        assert abs(new_post[h] - post[h]) < 0.001


# ── confidence_level ────────────────────────────────────────


def test_confidence_auto_confirm():
    """1위 ≥85% + gap ≥20% → auto_confirm."""
    post = {h: 0.0 for h in [
        "CREDENTIAL_THEFT", "PRIVILEGE_ESCALATION", "DATA_EXFILTRATION",
        "AUDIT_LOG_TAMPERING", "RANSOMWARE", "MISCONFIG_EXPOSURE",
        "PHISH_INITIAL_ACCESS", "INSIDER_THREAT", "UNCLASSIFIED",
    ]}
    post["RANSOMWARE"] = 0.90
    post["DATA_EXFILTRATION"] = 0.05
    cl = confidence_level(post)
    assert cl["primary"] == "RANSOMWARE"
    assert cl["recommended_action"] == "auto_confirm"


def test_confidence_propose_single():
    """1위 ≥70% + gap ≥10% → propose_single."""
    post = {h: 0.0 for h in [
        "CREDENTIAL_THEFT", "PRIVILEGE_ESCALATION", "DATA_EXFILTRATION",
        "AUDIT_LOG_TAMPERING", "RANSOMWARE", "MISCONFIG_EXPOSURE",
        "PHISH_INITIAL_ACCESS", "INSIDER_THREAT", "UNCLASSIFIED",
    ]}
    post["INSIDER_THREAT"] = 0.75
    post["CREDENTIAL_THEFT"] = 0.60  # gap 15%p
    cl = confidence_level(post)
    # 1위 ≥85% + gap ≥20% 미달이라 propose_single 또는 propose_composite
    assert cl["primary"] == "INSIDER_THREAT"
    assert cl["recommended_action"] in ("propose_single", "propose_composite")


def test_confidence_continue_or_skip():
    """모두 50% 미만 → continue_or_skip."""
    post = initial_posterior()  # prior 그대로 — 최대 27% (RANSOM)
    cl = confidence_level(post)
    assert cl["recommended_action"] == "continue_or_skip"


# ── top_n ──────────────────────────────────────────────────


def test_top_n_excludes_unclassified():
    """top_n 은 UNCLASSIFIED 제외."""
    post = initial_posterior()
    post["UNCLASSIFIED"] = 0.99  # 의도적으로 1위 만듦
    top = top_n(post, n=3)
    for h, _ in top:
        assert h != "UNCLASSIFIED"


def test_top_n_sorted_descending():
    """top_n 결과는 사후확률 내림차순."""
    post = initial_posterior()
    top = top_n(post, n=5)
    for i in range(len(top) - 1):
        assert top[i][1] >= top[i + 1][1], f"정렬 위반: {top[i]} vs {top[i+1]}"
