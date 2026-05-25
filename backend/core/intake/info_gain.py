"""Phase B.1 — Information Gain 알고리즘 (Evidence Tree, 2026-05-25, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §7 + §17.B

핵심 수식 (KL divergence 기반)
----------------------------
    expected_posterior(c) = sum_h P(h) × P(c|h)               # 단서 c 의 사전 marginal
    posterior_given_c(c, h') = P(h') × P(c|h') / expected_posterior(c)
    H(P)        = -sum_h P(h) × log2(P(h))                    # Shannon entropy
    IG(c) = H(P) − E[H(P|c)]
          = H(P) − P(c=1) × H(P|c=1) − P(c=0) × H(P|c=0)      # 이항 단서 (관찰 vs 미관찰)

해석
----
- IG(c) 가 클수록 단서 c 의 변별력이 큼 (어느 가설로 수렴할지 가장 명확)
- IG = 0 이면 이미 사후확률이 단서 c 에 무관 (모든 h 가 동일 P(c|h)) → 무용
- 최대값 = log2(N) (N 가설 → 완전 결정)

Marginalization (PDF §17.B 채택, BAN paper 정합)
----------------------------------------------
"기대됐는데 미관찰" 단서 — Pearl 1988 marginalization.
P(c=0 | h) = 1 − P(c=1 | h) 로 음성 evidence 처리.

학술
----
- Shannon 1948 — Information Gain (entropy)
- Pearl 1988 — Bayesian Belief Propagation
- BAN (IEEE 2023) — TTP DAG + CPT + Marginalization
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────
# 카탈로그 로딩
# ─────────────────────────────────────────────────────────────


_catalog_cache: Optional[dict] = None


def _catalog_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "triage" / "clue_catalog.json"


def load_catalog() -> dict:
    """clue_catalog.json 로드 + 캐시. Phase A 생성물."""
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache
    path = _catalog_path()
    if not path.exists():
        raise FileNotFoundError(
            f"clue_catalog.json 없음 — scripts/build_clue_catalog.py 실행 필요: {path}"
        )
    with path.open(encoding="utf-8") as f:
        _catalog_cache = json.load(f)
    return _catalog_cache


def invalidate_catalog_cache() -> None:
    """테스트·핫리로드용."""
    global _catalog_cache
    _catalog_cache = None


# ─────────────────────────────────────────────────────────────
# Likelihood 변환 (bayesian.py 와 동일 정책 — Laplace add-k=5)
# ─────────────────────────────────────────────────────────────


SMOOTHING = 5.0


def weights_to_likelihood(weights: dict[str, float]) -> dict[str, float]:
    """단서 가중치 dict → 사고유형별 P(c|h) likelihood.

    Laplace smoothing add-k=5. weights 가 모두 0 이라도 1/N 균등 likelihood.
    UNCLASSIFIED 와 'source'·문자열 키 제외.

    동일 정책 — `core/intake/bayesian.py:weights_to_likelihood` 와 일치.
    """
    # numeric only
    pure = {k: float(v) for k, v in weights.items() if isinstance(v, (int, float))}
    pure.pop("UNCLASSIFIED", None)
    if not pure:
        return {}
    total = sum(pure.values()) + SMOOTHING * len(pure)
    return {h: (w + SMOOTHING) / total for h, w in pure.items()}


# ─────────────────────────────────────────────────────────────
# Shannon entropy
# ─────────────────────────────────────────────────────────────


def entropy_bits(distribution: dict[str, float]) -> float:
    """이산 분포의 Shannon entropy (bits). UNCLASSIFIED 제외."""
    p = [v for k, v in distribution.items() if k != "UNCLASSIFIED" and v > 0]
    s = sum(p)
    if s <= 0:
        return 0.0
    p = [x / s for x in p]
    return -sum(x * math.log2(x) for x in p if x > 0)


# ─────────────────────────────────────────────────────────────
# Information Gain (단일 단서)
# ─────────────────────────────────────────────────────────────


def information_gain(
    posterior: dict[str, float],
    likelihood: dict[str, float],
    *,
    use_marginalization: bool = True,
) -> float:
    """단서 c (likelihood = P(c|h)) 의 expected information gain.

    수식
    ----
        H_before = H(P)
        P(c=1)   = sum_h P(h) × P(c|h)
        P(c=0)   = 1 − P(c=1)
        P(h | c=1) = P(h) × P(c|h) / P(c=1)
        P(h | c=0) = P(h) × (1 − P(c|h)) / P(c=0)
        IG = H_before − P(c=1) × H(P|c=1) − P(c=0) × H(P|c=0)

    use_marginalization=False 이면 음성 항(c=0)을 무시 (단순 정방향만).
    PDF §17.B BAN paper 정합 — 기본 True.
    """
    # 사고유형 키만 (UNCLASSIFIED 제외)
    keys = [h for h in posterior if h != "UNCLASSIFIED" and h in likelihood]
    if not keys:
        return 0.0

    # 정규화된 prior
    p = {h: posterior[h] for h in keys}
    s = sum(p.values())
    if s <= 0:
        return 0.0
    p = {h: v / s for h, v in p.items()}

    H_before = entropy_bits(p)

    # marginal P(c=1) = sum_h P(h) × P(c|h)
    p_c1 = sum(p[h] * likelihood[h] for h in keys)
    p_c0 = 1.0 - p_c1

    # P(h | c=1) — 베이즈 갱신
    if p_c1 > 1e-12:
        post_c1 = {h: p[h] * likelihood[h] / p_c1 for h in keys}
        H_c1 = entropy_bits(post_c1)
    else:
        H_c1 = 0.0

    if not use_marginalization:
        # marginalization 비활성 → 단서가 관찰됐다고 가정한 정보 이득만
        # (Pearl 1988 의 "given observation" 표준 conditional entropy 축소)
        return max(0.0, H_before - H_c1)

    if p_c0 <= 1e-12:
        # 음성 케이스 확률 0 → c=1 만 반영
        return max(0.0, H_before - p_c1 * H_c1)

    # P(h | c=0) — 음성 evidence (Marginalization, PDF §17.B BAN paper)
    post_c0 = {h: p[h] * (1.0 - likelihood[h]) / p_c0 for h in keys}
    H_c0 = entropy_bits(post_c0)

    ig = H_before - p_c1 * H_c1 - p_c0 * H_c0
    return max(0.0, ig)  # 부동소수 오차 가드


# ─────────────────────────────────────────────────────────────
# 다음 후보 선정 — 전체 카탈로그 IG 정렬
# ─────────────────────────────────────────────────────────────


def rank_candidates(
    posterior: dict[str, float],
    *,
    exclude_clue_keys: Optional[set[str]] = None,
    exclude_categories: Optional[set[str]] = None,
    use_marginalization: bool = True,
    catalog: Optional[dict] = None,
) -> list[dict]:
    """단서 카탈로그 전체에서 IG 내림차순 후보 리스트 반환.

    각 항목
    --------
        {
          "clue_key": str,
          "category": str,
          "value": str,
          "label": str,
          "short_label": str,
          "expected_info_gain": float,
          "outcome_flags": dict,
          "rationale": str  # 어느 가설에 가장 유리한지
        }

    파라미터
    ----------
        posterior            : 현재 사후확률 (uniform 시작점 또는 직전 단계 결과)
        exclude_clue_keys    : 이미 채택된 단서 제외
        exclude_categories   : 카테고리 단위 제외 (예: 같은 Q-노드 옵션 중복 차단)
        use_marginalization  : True (기본) — 음성 evidence 도 계산
        catalog              : 외부 주입 (테스트용). 기본은 load_catalog()
    """
    excl_keys = exclude_clue_keys or set()
    excl_cats = exclude_categories or set()
    cat = catalog if catalog is not None else load_catalog()
    clues: dict = cat.get("clues", {})

    out: list[dict] = []
    for clue_key, entry in clues.items():
        if clue_key in excl_keys:
            continue
        if entry.get("category") in excl_cats:
            continue
        if not entry.get("has_weights"):
            continue

        weights = entry.get("weights", {})
        likelihood = weights_to_likelihood(weights)
        if not likelihood:
            continue

        ig = information_gain(
            posterior, likelihood, use_marginalization=use_marginalization
        )

        # rationale — 가장 likelihood 가 높은 가설 (변별 방향)
        top_h, top_lk = max(likelihood.items(), key=lambda kv: kv[1])
        rationale = f"{top_h} 변별력 최고 (P(c|h)={top_lk:.2f})"

        out.append({
            "clue_key": clue_key,
            "category": entry.get("category", ""),
            "value": entry.get("value", ""),
            "label": entry.get("label", clue_key),
            "short_label": entry.get("short_label", clue_key),
            "expected_info_gain": ig,
            "outcome_flags": entry.get("outcome_flags", {}),
            "rationale": rationale,
        })

    out.sort(key=lambda x: -x["expected_info_gain"])
    return out


def pick_top_candidates(
    posterior: dict[str, float],
    k: int,
    *,
    exclude_clue_keys: Optional[set[str]] = None,
    use_marginalization: bool = True,
) -> list[dict]:
    """rank_candidates 상위 k 개만 반환 (편의 함수)."""
    ranked = rank_candidates(
        posterior,
        exclude_clue_keys=exclude_clue_keys,
        use_marginalization=use_marginalization,
    )
    return ranked[:k]
