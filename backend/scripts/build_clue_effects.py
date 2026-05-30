"""단서 효과 사전 표 자동 생성 (2026-05-28, byungwoo).

각 단서별 (P(c|h) Top 2 가설 + uniform prior 기준 IG) 산출 → JSON 사전.

목적
----
    143 단서 각각이 "어느 사고유형에 얼마나 강한 단서인지" 통합 표.
    paradigm doc + 발표 자료 + 사용자 질문 ("이 단서 왜 추천?") 즉시 답변 가능.

산출
----
    data/triage/clue_effects_summary.json:
    {
      "generated_at": "...",
      "smoothing": 2.0,
      "total_clues": 143,
      "summary_stats": {
        "max_lk_avg": 0.356,
        ">0.40 강한_단서": 57,
        ...
      },
      "by_clue": {
        "TECHNIQUE:T1552.005": {
          "label": "...",
          "weight_source": "MITRE T1552.005 [ISO 27035-1]",
          "primary": "CREDENTIAL_THEFT",
          "primary_lk": 0.500,
          "secondary": "PRIVILEGE_ESCALATION",
          "secondary_lk": 0.286,
          "ig_from_uniform": 0.085,
          "category": "TECHNIQUE",
          "is_strong": true   // primary_lk >= 0.30
        },
        ...
      },
      "by_hypothesis": {
        "CREDENTIAL_THEFT": {
          "strong_clues": ["TECHNIQUE:T1552.005", "Q3:fail_then_success", ...],
          "count": 18
        },
        ...
      }
    }

사용
----
    cd backend && PYTHONIOENCODING=utf-8 python -m scripts.build_clue_effects
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from core.intake.info_gain import (
    SMOOTHING,
    entropy_bits,
    information_gain,
    weights_to_likelihood,
)


CATALOG_PATH = _BACKEND_DIR / "data" / "triage" / "clue_catalog.json"
OUT_PATH = _BACKEND_DIR / "data" / "triage" / "clue_effects_summary.json"

STRONG_THRESHOLD = 0.30  # primary_lk ≥ 이면 강한 단서


def main() -> int:
    cat = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    clues = cat.get("clues", {})

    # uniform 1/8 prior — IG 계산 기준
    HYPS = [
        "PHISH_INITIAL_ACCESS", "CREDENTIAL_THEFT", "PRIVILEGE_ESCALATION",
        "INSIDER_THREAT", "MISCONFIG_EXPOSURE", "AUDIT_LOG_TAMPERING",
        "DATA_EXFILTRATION", "RANSOMWARE",
    ]
    uniform = {h: 1.0 / 8 for h in HYPS}

    by_clue: dict[str, dict] = {}
    by_hypothesis: dict[str, list[str]] = defaultdict(list)
    lk_max_list: list[float] = []

    for clue_key, entry in clues.items():
        weights = entry.get("weights", {})
        if not weights:
            continue
        lk = weights_to_likelihood(weights)
        if not lk:
            continue
        # Top 2 likelihood
        ranked = sorted(lk.items(), key=lambda kv: -kv[1])
        primary_h, primary_lk = ranked[0]
        secondary_h = ranked[1][0] if len(ranked) > 1 else None
        secondary_lk = ranked[1][1] if len(ranked) > 1 else 0.0

        # IG from uniform
        ig = information_gain(uniform, lk, use_marginalization=True)

        is_strong = primary_lk >= STRONG_THRESHOLD
        rec = {
            "label": entry.get("label") or entry.get("short_label") or clue_key,
            "short_label": entry.get("short_label", ""),
            "category": entry.get("category", ""),
            "weight_source": entry.get("weight_source", ""),
            "primary": primary_h,
            "primary_lk": round(primary_lk, 4),
            "secondary": secondary_h,
            "secondary_lk": round(secondary_lk, 4),
            "ig_from_uniform": round(ig, 4),
            "is_strong": is_strong,
        }
        by_clue[clue_key] = rec
        if is_strong:
            by_hypothesis[primary_h].append(clue_key)
        lk_max_list.append(primary_lk)

    # 가설별 강한 단서 IG 내림차순 정렬
    by_hyp_sorted = {}
    for h in HYPS:
        strong = by_hypothesis.get(h, [])
        strong.sort(key=lambda k: -by_clue[k]["ig_from_uniform"])
        by_hyp_sorted[h] = {
            "count": len(strong),
            "strong_clues": strong,
        }

    bins = {">0.40": 0, "0.30-0.40": 0, "0.25-0.30": 0, "0.20-0.25": 0, "<0.20": 0}
    for x in lk_max_list:
        if x > 0.40: bins[">0.40"] += 1
        elif x >= 0.30: bins["0.30-0.40"] += 1
        elif x >= 0.25: bins["0.25-0.30"] += 1
        elif x >= 0.20: bins["0.20-0.25"] += 1
        else: bins["<0.20"] += 1

    out = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "smoothing": SMOOTHING,
        "total_clues": len(by_clue),
        "strong_threshold": STRONG_THRESHOLD,
        "summary_stats": {
            "max_lk_avg": round(sum(lk_max_list) / len(lk_max_list), 4) if lk_max_list else 0,
            "max_lk_max": round(max(lk_max_list), 4) if lk_max_list else 0,
            "max_lk_min": round(min(lk_max_list), 4) if lk_max_list else 0,
            "distribution": bins,
            "strong_count": bins[">0.40"] + bins["0.30-0.40"],
        },
        "by_hypothesis": by_hyp_sorted,
        "by_clue": by_clue,
    }

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {len(by_clue)} clues 사전 표 생성")
    print(f"  → {OUT_PATH.relative_to(_BACKEND_DIR)}")
    print(f"  · max_lk 평균: {out['summary_stats']['max_lk_avg']}")
    print(f"  · 강한 단서 (lk ≥ {STRONG_THRESHOLD}): {out['summary_stats']['strong_count']} / {len(by_clue)}")
    print()
    print("  가설별 강한 단서 수:")
    for h, info in by_hyp_sorted.items():
        print(f"    {h:<24} {info['count']:>3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
