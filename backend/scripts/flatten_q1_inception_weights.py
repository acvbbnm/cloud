"""Q1_inception 가중치 평탄화 (V1.fix.4, 2026-05-31 byungwoo).

배경
----
"어떻게 사고를 알게 됐나요?" (Q1_inception:*) 는 사고 발견 경로 메타 정보이며
사고 유형 변별력이 없음. 그러나 기존 카탈로그는 옵션마다 가중치 5~10 가
사고유형별로 다르게 매겨져 있어 베이지안 사후확률에 의도치 않은 편향을 줌
(사용자 검증 2026-05-31).

조치
----
모든 Q1_inception:* 옵션의 weights 를 동일 균등값(=1)로 평탄화.
likelihood = (1+SMOOTHING) / (8 + 8*SMOOTHING) = 1/8 uniform → posterior 그대로.
posterior_new = normalize(prior × uniform) = prior. 베이지안 무영향.

weight_source 에 "[메타 단서 — 발견경로, 사고유형 변별 X — V1.fix.4 평탄화]" 표시.

근거
----
NIST SP 800-61r2 §3.2 — Sources of Precursors and Indicators 는 "발견 경로"
이며 "사고 종류" 와는 독립 변수. KISA §3.1 사고 기본 정보 항목.

사용
----
    cd backend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.flatten_q1_inception_weights
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
CATALOG_PATH = _BACKEND_DIR / "data" / "triage" / "clue_catalog.json"


HYPS = [
    "CREDENTIAL_THEFT", "PRIVILEGE_ESCALATION", "DATA_EXFILTRATION",
    "AUDIT_LOG_TAMPERING", "RANSOMWARE", "MISCONFIG_EXPOSURE",
    "PHISH_INITIAL_ACCESS", "INSIDER_THREAT",
]


def main() -> int:
    cat = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    clues = cat.get("clues", {})

    targets = [k for k in clues if k.startswith("Q1_inception:")]
    print(f"Q1_inception 평탄화 대상: {len(targets)}건")
    changed = 0
    for k in targets:
        e = clues[k]
        before = dict(e.get("weights", {}))
        # 모두 동일 값 1 (평탄화). smoothing 후 likelihood uniform.
        e["weights"] = {h: 1 for h in HYPS}
        src = e.get("weight_source", "") or ""
        marker = "[메타 단서 — 발견경로, 사고유형 변별 X — V1.fix.4 평탄화]"
        if marker not in src:
            e["weight_source"] = (src + " " + marker).strip()
        if before != e["weights"]:
            changed += 1
        print(f"  • {k}")
        print(f"    before: {before}")
        print(f"    after:  {e['weights']}")

    CATALOG_PATH.write_text(
        json.dumps(cat, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✓ 평탄화 완료 — {changed}건 변경")
    print(f"  → {CATALOG_PATH.relative_to(_BACKEND_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
