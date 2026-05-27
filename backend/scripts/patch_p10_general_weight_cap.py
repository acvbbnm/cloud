"""Phase P.10 — 일반 단서 weight cap (2026-05-27 byungwoo).

사용자 피드백 (2026-05-27 시연):
  "하나의 단서만으로 너무 많이 쏠림. 쏠리는 정도를 낮춰야 할 듯함.
   다시 페이즈1 페이즈2 진행해야 하지 않나 싶음"

P.1 (정찰 단서 cap=10) 후속:
  · 본격 단서 49건이 max_w ≥ 30 → 단서 1개만으로도 사후확률 한 anchor 로 급격 쏠림
  · 일반 단서 cap=GENERAL_CAP=20 적용
  · 정찰 단서(Q1_inception:* + Q2A:*)는 P.1 의 cap=10 유지 (이미 적용)

학술 정합:
  · Pearl 1988 — likelihood 가 너무 강하면 베이즈 갱신이 prior 무시
  · Robust Bayes (Berger 1985) — 단일 evidence 가 1.0 으로 압축되지 않도록 floor/ceil

idempotent — 이미 cap 적용된 단서는 무변경.

사용:
    cd backend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/patch_p10_general_weight_cap.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
CATALOG_PATH = _BACKEND / "data" / "triage" / "clue_catalog.json"

# 본격 단서 cap — 단서 1개의 강도를 정찰의 2배 (= weight 비율)로 유지
GENERAL_WEIGHT_CAP = 20

# 정찰 prefix (P.1 cap=10 유지) — 본 패치는 *그 외* 단서만 처리
RECON_PREFIXES = ("Q1_inception:", "Q2A:")


def patch() -> int:
    if not CATALOG_PATH.exists():
        print(f"[error] {CATALOG_PATH} 없음", file=sys.stderr)
        return 1

    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    clues = data.get("clues", {})

    affected: list[tuple[str, int, int]] = []
    cells_capped = 0

    for clue_key, entry in clues.items():
        # 정찰 단서 skip (P.1 에서 이미 cap=10)
        if any(clue_key.startswith(p) for p in RECON_PREFIXES):
            continue
        weights = entry.get("weights")
        if not isinstance(weights, dict):
            continue
        before_max = max(weights.values()) if weights else 0
        if before_max <= GENERAL_WEIGHT_CAP:
            continue  # 이미 충분히 낮음
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
        print(f"[skip] 모든 일반 단서가 이미 cap≤{GENERAL_WEIGHT_CAP} — 변경 없음")
        return 0

    meta = data.setdefault("_meta", {})
    meta["last_patched"] = datetime.utcnow().isoformat() + "Z"
    meta["last_patch_op"] = (
        f"Phase P.10 — 일반 단서 weight cap={GENERAL_WEIGHT_CAP} "
        f"({len(affected)} 단서 / {cells_capped} cell 압축)"
    )

    CATALOG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[ok] Phase P.10 일반 단서 weight cap={GENERAL_WEIGHT_CAP} 적용")
    print(f"     영향 단서: {len(affected)}건 / cell 압축: {cells_capped}")
    print()
    # 압축 크기 순 정렬 (변경 폭 큰 것부터)
    for ck, before, after in sorted(affected, key=lambda x: -x[1])[:25]:
        print(f"  ✓ {ck:<42} max_w: {before:3d} → {after:2d}")
    if len(affected) > 25:
        print(f"  ... 외 {len(affected) - 25}건")
    return 0


if __name__ == "__main__":
    sys.exit(patch())
