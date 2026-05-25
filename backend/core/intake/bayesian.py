"""베이지안 사고유형 분류 — Phase 2.5 실험 (byungwoo 브랜치, 2026-05-25).

설계서 5.4.4절 Triage 의 단순 누적 합산을 **베이즈 갱신** 으로 대체하는 실험 모듈.

핵심 수식
---------
    P(H|E) ∝ P(E|H) × P(H)            (베이즈 정리)
    posterior_new = normalize(prior × likelihood)   (정규화로 합 = 1)

데이터 소스
-----------
    data/triage/priors.json       — Verizon DBIR 2024 사전확률 P(H)
    data/triage/weights.json      — 기존 정수 점수 → likelihood 자동 변환

학술 변호
---------
    - 결정성 100% : 같은 답변 시퀀스 → 같은 사후확률 (베이즈 산술은 결정론적)
    - AI 비판단  : 베이즈 계산은 통계 산술, 추론·생성 없음
    - 외부 근거  : Verizon DBIR 통계 prior + 기존 weights.json source 정합

호환성
------
    - 기존 _initial_scores / _apply_weight 와 동일 시그니처 유지
    - 환경변수 TRIAGE_MODE=bayesian 또는 weights.json _meta.scoring_mode='bayesian'
    - 미설정 시 기존 누적 합산 모드 (테스트·시연 안정성)

참고
----
    - Bayesian Network for Cybersecurity Risk: arXiv 2505.09048 (2026)
    - k9 Security — Severity is no longer a triage input (2026.05)
    - Verizon DBIR 2024 — Top 4 patterns 통계
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from config import settings


# ── priors 로딩 ─────────────────────────────────────────────


_priors_cache: Optional[dict[str, float]] = None
_priors_meta_cache: Optional[dict] = None


def _priors_path() -> Path:
    return Path(settings.BASE_DIR) / "data" / "triage" / "priors.json"


def load_priors() -> dict[str, float]:
    """priors.json 로드 + 합 = 1 검증 + 캐시.

    합이 1 에서 ±0.001 벗어나면 ValueError. priors.json 의 _validation.tolerance 사용.
    """
    global _priors_cache
    if _priors_cache is not None:
        return _priors_cache

    path = _priors_path()
    if not path.exists():
        raise FileNotFoundError(f"priors.json 없음: {path}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    priors = data.get("priors", {})
    if not priors:
        raise ValueError("priors.json 의 'priors' 키가 비어있음")

    tolerance = data.get("_validation", {}).get("tolerance", 0.001)
    total = sum(priors.values())
    if abs(total - 1.0) > tolerance:
        raise ValueError(
            f"priors 합 = {total:.4f} (기대 1.0, tolerance {tolerance}). "
            f"priors.json 의 사전확률을 재확인하세요."
        )

    global _priors_meta_cache
    _priors_meta_cache = data.get("_meta", {})
    _priors_cache = priors
    return priors


def priors_meta() -> dict:
    """priors.json 의 _meta 반환 (학술 인용·발표 자료용)."""
    if _priors_meta_cache is None:
        load_priors()
    return _priors_meta_cache or {}


def invalidate_priors_cache() -> None:
    """테스트·핫리로드용 — priors 캐시 무효화."""
    global _priors_cache, _priors_meta_cache
    _priors_cache = None
    _priors_meta_cache = None


# ── 베이즈 갱신 ────────────────────────────────────────────


def initial_posterior() -> dict[str, float]:
    """베이즈 시작점 = priors 그대로 (사전확률).

    UNCLASSIFIED 는 0 로 별도 — 분류 안 된 잔여 가설 처리용.
    """
    priors = load_priors()
    return {**priors, "UNCLASSIFIED": 0.0}


def weights_to_likelihood(weights: dict[str, int]) -> dict[str, float]:
    """기존 weights.json 의 정수 점수 → likelihood P(E|H) 자동 변환.

    수식
    ----
        likelihood_h = (weight_h + smoothing) / (sum_weights + smoothing × num_types)

    smoothing 5 = Laplace add-k. 가중치 0 인 사고유형도 base 확률 보존
    (관측되지 않은 답변 → 0 곱하면 posterior 가 영구히 0 으로 수렴, 회복 불가).

    입력 weights 는 weights.json 의 한 답변 dict (예: 'Q5-CRED:tor_vpn' 의 8 사고유형 점수).
    """
    smoothing = 5.0
    # UNCLASSIFIED·source 키 등은 제외하고 사고유형 점수만
    sco = {k: float(v) for k, v in weights.items() if isinstance(v, (int, float))}
    if "UNCLASSIFIED" in sco:
        sco.pop("UNCLASSIFIED")  # UNCLASSIFIED 는 likelihood 대상 X

    n = len(sco)
    if n == 0:
        return {}
    total = sum(sco.values()) + smoothing * n
    return {h: (w + smoothing) / total for h, w in sco.items()}


def bayes_update(
    posterior: dict[str, float], likelihood: dict[str, float]
) -> dict[str, float]:
    """베이즈 1-step 갱신.

    posterior_new[h] = posterior[h] × likelihood[h]
    정규화 후 합 = 1.

    likelihood 에 없는 사고유형은 1.0 (변동 없음) 으로 처리 — UNCLASSIFIED 등.
    """
    raw: dict[str, float] = {}
    for h, p in posterior.items():
        lk = likelihood.get(h, 1.0)
        raw[h] = p * lk

    total = sum(raw.values())
    if total <= 0:
        # 모두 0 곱이면 prior 로 복귀 (안전)
        return initial_posterior()
    return {h: v / total for h, v in raw.items()}


def top_n(posterior: dict[str, float], n: int = 3) -> list[tuple[str, float]]:
    """사후확률 상위 n 개 사고유형 (UNCLASSIFIED 제외) — (사고유형, 확률) 튜플."""
    ranked = [
        (h, p) for h, p in posterior.items() if h != "UNCLASSIFIED"
    ]
    ranked.sort(key=lambda x: -x[1])
    return ranked[:n]


def confidence_level(posterior: dict[str, float]) -> dict:
    """현재 사후확률 기반 신뢰도 평가 — 임계값 정합.

    임계값
    ------
        high_confidence_prob : 0.70 (사고유형 제시)
        auto_confirm_prob    : 0.85 (자동 확정)
        gap_required         : 0.20 (1·2위 격차)

    반환:
        {primary, primary_prob, secondary, secondary_prob, gap, recommended_action}
    """
    ranked = top_n(posterior, n=2)
    if len(ranked) < 2:
        return {
            "primary": ranked[0][0] if ranked else None,
            "primary_prob": ranked[0][1] if ranked else 0.0,
            "secondary": None,
            "secondary_prob": 0.0,
            "gap": 0.0,
            "recommended_action": "continue_or_skip",
        }

    primary, primary_p = ranked[0]
    secondary, secondary_p = ranked[1]
    gap = primary_p - secondary_p

    if primary_p >= 0.85 and gap >= 0.20:
        action = "auto_confirm"
    elif primary_p >= 0.70 and gap >= 0.10:
        action = "propose_single"
    elif primary_p >= 0.50:
        action = "propose_composite"
    else:
        action = "continue_or_skip"

    return {
        "primary": primary,
        "primary_prob": primary_p,
        "secondary": secondary,
        "secondary_prob": secondary_p,
        "gap": gap,
        "recommended_action": action,
    }
