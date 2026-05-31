"""Phase P.26 — 일반 단서 cap 강화 20→15 (2026-05-31 byungwoo).

사용자 피드백:
  "단 두세개의 단서만으로 80퍼센트확률로 데이터 유출쪽으로 가다가
   갑자기 두세개 더 입력하면 랜섬웨어가 되고 이게 맞는 흐름이 맞을까?"
  → 옵션 A: cap 더 강화 (단서 1개의 사후확률 영향 축소)

P.10 (cap=20) 후속:
  · cap=20 → max_lk 0.30 ~ 0.54 (1개 단서로도 54% 도달 가능)
  · cap=15 → max_lk 0.30 ~ 0.47 (휘청 완화 + 학술 정합 유지)

학술 정합:
  · Berger 1985 Robust Bayes — likelihood 상한 설정으로 단일 evidence 의 과도한 영향 차단
  · Pearl 1988 — 베이즈 갱신은 보존 (likelihood 만 calibration)
  · Mandiant 정설 (DATA→RANSOM 0.50) — 다단계 chain 으로 자연 전이는 유지

대상:
  · Q1_inception:* + Q2A:* 정찰 단서는 P.1 cap=10 유지
  · 그 외 모든 단서 cap=15 (P.10 의 cap=20 보다 강화)

idempotent.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
CATALOG_PATH = _BACKEND / "data" / "triage" / "clue_catalog.json"

GENERAL_WEIGHT_CAP = 15  # P.10 의 20 → 15 (사용자 피드백 옵션 A)
RECON_PREFIXES = ("Q1_inception:", "Q2A:")  # P.1 cap=10 유지 (skip)


def patch() -> int:
    if not CATALOG_PATH.exists():
        print(f"[error] {CATALOG_PATH} 없음", file=sys.stderr)
        return 1

    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    clues = data.get("clues", {})

    affected: list[tuple[str, int, int]] = []
    cells_capped = 0

    for clue_key, entry in clues.items():
        if any(clue_key.startswith(p) for p in RECON_PREFIXES):
            continue
        weights = entry.get("weights")
        if not isinstance(weights, dict):
            continue
        before_max = max(weights.values()) if weights else 0
        if before_max <= GENERAL_WEIGHT_CAP:
            continue
        new_weights: dict[str, int] = {}
        for h, w in weights.items():
            if not isinstance(w, (int, float)):
                new_weights[h] = w
                continue
            new_w = min(int(w), GENERAL_WEIGHT_CAP) if w > 0 else int(w)
            if new_w != w:
                cells_capped += 1
            new_weights[h] = new_w
        after_max = max(new_weights.values()) if new_weights else 0
        entry["weights"] = new_weights
        affected.append((clue_key, before_max, after_max))

    if not affected:
        print(f"[skip] 모든 일반 단서가 이미 cap≤{GENERAL_WEIGHT_CAP}")
        return 0

    meta = data.setdefault("_meta", {})
    meta["last_patched"] = datetime.utcnow().isoformat() + "Z"
    meta["last_patch_op"] = (
        f"Phase P.26 — 일반 단서 cap={GENERAL_WEIGHT_CAP} 강화 "
        f"({len(affected)} 단서 / {cells_capped} cell 압축)"
    )

    CATALOG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[ok] Phase P.26 일반 단서 cap={GENERAL_WEIGHT_CAP} 강화 적용")
    print(f"     영향 단서: {len(affected)}건 / cell 압축: {cells_capped}")
    print()
    for ck, before, after in sorted(affected, key=lambda x: -x[1])[:15]:
        print(f"  ✓ {ck:<42} max_w: {before:3d} → {after:2d}")
    if len(affected) > 15:
        print(f"  ... 외 {len(affected) - 15}건")
    return 0


if __name__ == "__main__":
    sys.exit(patch())
