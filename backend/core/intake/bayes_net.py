"""H.3 — Bayesian Network + Noisy-OR 추론 (2026-05-25, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §17.B (BAN paper IEEE 2023 정합)

3-layer 인과 모델
================
    Layer 1 (latent)     H_k = 8 incident_type (가설)
            ↓
    Layer 2 (latent)     T_i = 45 ATT&CK 기법 (TTPs)
            ↓
    Layer 3 (observable) C_j = 125 매핑 단서 (DAG 노드)

조건부 의존성:
    P(T_i | H)  : 기법 i 가 가설 h 일 때 관측될 확률 — weights.json 에서 도출
    P(C_j | T)  : 단서 j 가 기법 t 의 결과로 관측될 확률 — clue_to_attack 매핑 + 신뢰도

Noisy-OR CPT (Pearl 1988, BAN paper)
====================================
    P(child=1 | parents=set) = 1 - (1 - leak) × ∏_{p in set} (1 - q_p)
    where:
        leak  = 0.05 (baseline noise — 설명 없이 관측될 확률)
        q_p   = per-parent link strength (Laplace-smoothed 확률)

PDF §17.B 차용
==============
    > "베이지안 네트워크는 MITRE ATT&CK 의 TTP 와 위협 행위자 그룹 간의 상관관계를
    >  방향성 비순환 그래프(DAG) 형태로 모델링한다. ... 한계화(Marginalization) 를 통해
    >  관찰되지 않은 변수들의 가능한 모든 상태를 합산함으로써 불확실성을 내포하면서도
    >  신뢰할 수 있는 확률론적 예측 결과를 도출한다."

추론 알고리즘 (1-step Bayes update)
==================================
    posterior_new[h] ∝ posterior[h] × L(c | h)
    L(c | h) = NoisyOR aggregation across c's mapped techniques

사용자 결정 정합 (H.2)
=====================
    ① Option C 자동+수동 매핑 — clue_to_attack.json (143 단서 100% 커버)
    ② Option A 메타 null    — 메타 단서는 BN 외부 처리, 기존 likelihood 폴백
    ③ Option B 1:N 보존     — Noisy-OR 가 다중 부모 자연 처리

학술 참조
=========
    - Pearl 1988    : Noisy-OR Bayesian Network
    - BAN IEEE 2023 : DAG + CPT + Marginalization
    - Jaynes 1968   : Uniform prior
    - Shannon 1948  : Information Gain (별도, info_gain.py)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from core.intake.bayesian import bayes_update, initial_posterior
from core.intake.info_gain import (
    SMOOTHING,
    load_catalog,
    weights_to_likelihood,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────────


INCIDENT_TYPES_8 = [
    "CREDENTIAL_THEFT",
    "PRIVILEGE_ESCALATION",
    "DATA_EXFILTRATION",
    "AUDIT_LOG_TAMPERING",
    "RANSOMWARE",
    "MISCONFIG_EXPOSURE",
    "PHISH_INITIAL_ACCESS",
    "INSIDER_THREAT",
]

# Noisy-OR leak — 단서·기법이 부모 없이 관측될 baseline noise (Pearl 1988)
NOISY_OR_LEAK = 0.05

# 매핑 신뢰도별 스케일 — Noisy-OR 링크 강도에 곱해짐
CONFIDENCE_SCALE: dict[str, float] = {
    "high": 1.0,
    "medium": 0.7,
    "low": 0.4,
    "n/a": 0.0,
}


# ─────────────────────────────────────────────────────────────
# 캐시 로딩
# ─────────────────────────────────────────────────────────────


_clue_to_attack_cache: Optional[dict] = None
_technique_weights_cache: Optional[dict] = None


def _data_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "triage"


def load_clue_to_attack() -> dict:
    """clue_to_attack.json 로드 + 캐시 (H.2 산출물)."""
    global _clue_to_attack_cache
    if _clue_to_attack_cache is not None:
        return _clue_to_attack_cache
    path = _data_dir() / "clue_to_attack.json"
    if not path.exists():
        raise FileNotFoundError(
            f"clue_to_attack.json 없음 — scripts/build_clue_attack_mapping.py 실행 필요: {path}"
        )
    _clue_to_attack_cache = json.loads(path.read_text(encoding="utf-8"))
    return _clue_to_attack_cache


def load_technique_weights() -> dict:
    """weights.json:partial_analysis_techniques 로드 + 캐시.

    27 ATT&CK 기법별 8 사고유형 가중치 — P(T | H) 계산 입력.
    """
    global _technique_weights_cache
    if _technique_weights_cache is not None:
        return _technique_weights_cache
    path = _data_dir() / "weights.json"
    if not path.exists():
        raise FileNotFoundError(f"weights.json 없음: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    _technique_weights_cache = data.get("partial_analysis_techniques", {})
    return _technique_weights_cache


def invalidate_cache() -> None:
    """테스트·핫리로드용."""
    global _clue_to_attack_cache, _technique_weights_cache
    _clue_to_attack_cache = None
    _technique_weights_cache = None


# ─────────────────────────────────────────────────────────────
# P(T | H) — 기법 likelihood
# ─────────────────────────────────────────────────────────────


def _extract_hypothesis_weights(weights: dict) -> dict[str, float]:
    """weights dict 에서 사고유형 키만 float 추출 (tactic·source 등 메타 제거)."""
    return {h: float(weights.get(h, 0)) for h in INCIDENT_TYPES_8 if h in weights}


def technique_likelihood(technique_id: str) -> dict[str, float]:
    """기법 T 의 사고유형별 likelihood P(T 관측 | H) — Laplace add-k=5 smoothing.

    Fallback 체인 (weights.json 에 27개만 존재, referenced 45 중 18 누락):
        1. 정확 일치 (T1078.004)
        2. 부모 기법 (T1078) — subtechnique 일 때
        3. 자식 기법 평균 — 부모 ID 일 때 모든 sub 평균
        4. uniform 1/8 — 어떤 fallback 도 실패 시

    반환 — 사고유형별 likelihood (합 = 1).
    """
    tw = load_technique_weights()

    # 1. 정확 일치
    raw = tw.get(technique_id, {})
    weights = _extract_hypothesis_weights(raw) if raw else {}

    # 2. 부모 기법 (서브 → 부모)
    if not weights and "." in technique_id:
        parent_id = technique_id.split(".")[0]
        raw = tw.get(parent_id, {})
        weights = _extract_hypothesis_weights(raw) if raw else {}

    # 3. 자식 기법 평균 (부모 → 모든 서브 평균)
    if not weights:
        prefix = technique_id + "."
        sub_weights = []
        for k, v in tw.items():
            if k.startswith(prefix):
                hw = _extract_hypothesis_weights(v)
                if hw:
                    sub_weights.append(hw)
        if sub_weights:
            weights = {}
            for h in INCIDENT_TYPES_8:
                weights[h] = sum(sw.get(h, 0) for sw in sub_weights) / len(sub_weights)

    # 4. 모두 실패 — uniform 1/8
    if not weights:
        return {h: 1.0 / len(INCIDENT_TYPES_8) for h in INCIDENT_TYPES_8}

    # Laplace smoothing — bayesian.py 정책 정합
    total = sum(weights.values()) + SMOOTHING * len(INCIDENT_TYPES_8)
    return {h: (weights.get(h, 0) + SMOOTHING) / total for h in INCIDENT_TYPES_8}


# ─────────────────────────────────────────────────────────────
# Noisy-OR — P(C | T) aggregation
# ─────────────────────────────────────────────────────────────


def noisy_or(q_list: list[float], leak: float = NOISY_OR_LEAK) -> float:
    """Pearl 1988 Noisy-OR:
        P(child=1 | parents=set) = 1 - (1 - leak) × ∏ (1 - q_i)

    q_list 가 비어있으면 leak (baseline) 만 반환.
    q_i 를 [0, 1] 로 클램프.
    """
    prob_not = 1.0 - leak
    for q in q_list:
        prob_not *= 1.0 - max(0.0, min(1.0, q))
    return 1.0 - prob_not


# ─────────────────────────────────────────────────────────────
# 단서 → likelihood (DAG 경유)
# ─────────────────────────────────────────────────────────────


def _legacy_likelihood(clue_key: str) -> dict[str, float]:
    """Fallback — weights.json:clue_types / decision_tree_answers 의 가중치를
    직접 likelihood 로 변환 (bayesian.py 와 동일 정책)."""
    catalog = load_catalog()
    entry = catalog.get("clues", {}).get(clue_key)
    if not entry or not entry.get("has_weights"):
        return {h: 1.0 / len(INCIDENT_TYPES_8) for h in INCIDENT_TYPES_8}
    return weights_to_likelihood(entry["weights"])


def _is_uniform_likelihood(lk: dict[str, float], tolerance: float = 1e-3) -> bool:
    """likelihood 가 사실상 균등 (변별력 0) 인지 판정."""
    vals = list(lk.values())
    if not vals:
        return True
    return max(vals) - min(vals) < tolerance


def _technique_has_weights(technique_id: str) -> bool:
    """기법이 weights.json:partial_analysis_techniques 에 (또는 부모/자식 fallback) 존재하는지."""
    tw = load_technique_weights()
    if technique_id in tw and tw[technique_id]:
        return True
    if "." in technique_id:
        parent = technique_id.split(".")[0]
        if tw.get(parent):
            return True
    # 자식 fallback
    prefix = technique_id + "."
    for k, v in tw.items():
        if k.startswith(prefix) and v:
            return True
    return False


def clue_likelihood_via_bn(clue_key: str) -> dict[str, float]:
    """Noisy-OR aggregation across c's mapped techniques.

    Hybrid Fallback 정책 (2026-05-25):
        1. 매핑 없음 또는 techniques=null/empty → legacy weights.json 폴백
        2. 매핑된 기법 중 weights 보유한 게 하나도 없음 → legacy fallback
           (T1071, T1090.003 등 18 기법은 weights.json 미수록 — BN 결과 uniform 화)
        3. 기법 1개라도 weights 보유 → BN Noisy-OR aggregation 사용

    수식:
        L(c | h) ∝ NoisyOR({q_{t,h} × confidence | t in mapping[c].techniques})
        q_{t,h} = technique_likelihood(t)[h]  # P(T 관측 | H), Laplace smoothed
    """
    mapping_root = load_clue_to_attack()
    mapping = mapping_root.get("mappings", {}).get(clue_key)
    if not mapping:
        return _legacy_likelihood(clue_key)

    techs = mapping.get("techniques")
    if techs is None or not techs:
        # 메타 (null) 또는 no_ttp — legacy 사용
        return _legacy_likelihood(clue_key)

    # weights 보유한 기법이 하나도 없으면 BN 가치 없음 → legacy fallback
    if not any(_technique_has_weights(t) for t in techs):
        return _legacy_likelihood(clue_key)

    conf_scale = CONFIDENCE_SCALE.get(mapping.get("confidence", "high"), 1.0)

    # 각 H 에 대해 Noisy-OR aggregation
    raw: dict[str, float] = {}
    for h in INCIDENT_TYPES_8:
        q_list: list[float] = []
        for t in techs:
            t_lk = technique_likelihood(t)
            q_list.append(t_lk[h] * conf_scale)
        raw[h] = noisy_or(q_list)

    # BN 결과가 사실상 uniform 이면 legacy 시도 (variant 미상 등)
    if _is_uniform_likelihood(raw):
        return _legacy_likelihood(clue_key)

    # 정규화 (likelihood 합 = 1, bayes_update 와 호환)
    total = sum(raw.values())
    if total <= 0:
        return {h: 1.0 / len(INCIDENT_TYPES_8) for h in INCIDENT_TYPES_8}
    return {h: v / total for h, v in raw.items()}


# ─────────────────────────────────────────────────────────────
# 추론 — 단서 시퀀스 → 사후확률
# ─────────────────────────────────────────────────────────────


def bn_update(
    posterior: dict[str, float], clue_key: str
) -> dict[str, float]:
    """1-step BN 갱신 — Noisy-OR likelihood × prior, 정규화.

    bayes_update(posterior, lk) 와 동일 시그너처 — drop-in 가능.
    UNCLASSIFIED 키 보존 (likelihood=1.0 처리).
    """
    lk = clue_likelihood_via_bn(clue_key)
    return bayes_update(posterior, lk)


def bn_evaluate_sequence(
    clue_keys: list[str],
) -> tuple[dict[str, float], list[dict]]:
    """단서 시퀀스 → 최종 사후확률 + per-step trace.

    bayesian.py·info_gain.py 의 시뮬레이션 흐름과 동일 — 폴백 호환.

    반환:
        (final_posterior, trace)
        trace = [{clue_key, likelihood, posterior_before, posterior_after}, ...]
    """
    posterior = initial_posterior()
    trace: list[dict] = []
    for ck in clue_keys:
        lk = clue_likelihood_via_bn(ck)
        prev = dict(posterior)
        posterior = bayes_update(posterior, lk)
        trace.append(
            {
                "clue_key": ck,
                "likelihood": lk,
                "posterior_before": prev,
                "posterior_after": dict(posterior),
            }
        )
    return posterior, trace


def explain_clue(clue_key: str) -> dict:
    """단서의 BN 추론 trace 반환 — 디버깅·UI 설명용.

    {
      "clue_key": str,
      "techniques": [...],         # 매핑된 ATT&CK 기법
      "confidence": str,
      "per_technique_likelihood": {tid: {h: prob, ...}, ...},
      "aggregated_likelihood": {h: prob, ...},
      "source": str,               # bn | legacy_fallback
    }
    """
    mapping_root = load_clue_to_attack()
    mapping = mapping_root.get("mappings", {}).get(clue_key)
    lk = clue_likelihood_via_bn(clue_key)

    out: dict = {
        "clue_key": clue_key,
        "aggregated_likelihood": lk,
    }
    if not mapping or not mapping.get("techniques"):
        out["techniques"] = []
        out["confidence"] = mapping.get("confidence", "n/a") if mapping else "n/a"
        out["source"] = "legacy_fallback"
        return out

    out["techniques"] = mapping["techniques"]
    out["confidence"] = mapping.get("confidence", "high")
    out["per_technique_likelihood"] = {
        t: technique_likelihood(t) for t in mapping["techniques"]
    }
    out["source"] = "bn"
    return out
