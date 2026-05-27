"""Phase P.1 — 정찰 단계 단서 weight cap (2026-05-26 byungwoo).

사용자 피드백 (2026-05-26):
  "Q1_inception 단서 weight 가 너무 큰것같아서 매우 줄여주면 좋겠고"

paradigm doc §16 정합 — 정찰 단계 (사고 인지 / 알람 종류) 는 약 신호여야 함.
한 단서 채택으로 사후확률이 크게 기울지 않도록 max 10 으로 cap.

대상:
  · Q1_inception:* (5개) — "어떻게 사고를 알게 됐나"
  · Q2A:*           (10개) — "어떤 이상이 있었나"

동작:
  · clue_catalog.json 의 해당 단서들의 weights dict 의 모든 값을 min(w, CAP) 으로 압축
  · 0 인 값은 그대로 (음성/무관계 신호 유지)
  · weight_source 는 변경 안 함 (학술 근거 보존)
  · _meta.last_patched 기록

idempotent — 이미 cap 적용된 단서는 무변경 (검증 시 PASS).

사용:
    cd backend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/patch_p1_recon_weight_cap.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
CATALOG_PATH = _BACKEND / "data" / "triage" / "clue_catalog.json"

# 정찰 단계 cap — 가장 강한 변별 신호도 10 으로 압축
RECON_WEIGHT_CAP = 10

# cap 대상 카테고리 (clue_key prefix)
RECON_PREFIXES = ("Q1_inception:", "Q2A:")


def patch() -> int:
    if not CATALOG_PATH.exists():
        print(f"[error] {CATALOG_PATH} 없음", file=sys.stderr)
        return 1

    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    clues = data.get("clues", {})

    affected: list[tuple[str, int, int]] = []  # (clue_key, before_max, after_max)
    cells_capped = 0

    for clue_key, entry in clues.items():
        if not any(clue_key.startswith(p) for p in RECON_PREFIXES):
            continue
        weights = entry.get("weights")
        if not isinstance(weights, dict):
            continue
        before_max = max(weights.values()) if weights else 0
        new_weights: dict[str, int] = {}
        for h, w in weights.items():
            if not isinstance(w, (int, float)):
                new_weights[h] = w
                continue
            new_w = min(int(w), RECON_WEIGHT_CAP) if w > 0 else int(w)
            if new_w != w:
                cells_capped += 1
            new_weights[h] = new_w
        after_max = max(new_weights.values()) if new_weights else 0
        if new_weights != weights:
            entry["weights"] = new_weights
            affected.append((clue_key, before_max, after_max))

    if not affected:
        print(f"[skip] 모든 정찰 단서가 이미 cap≤{RECON_WEIGHT_CAP} — 변경 없음")
        return 0

    # _meta 기록
    meta = data.setdefault("_meta", {})
    meta["last_patched"] = datetime.utcnow().isoformat() + "Z"
    meta["last_patch_op"] = (
        f"Phase P.1 — 정찰 단계 단서 weight cap={RECON_WEIGHT_CAP} "
        f"({len(affected)} 단서 / {cells_capped} cell 압축)"
    )

    CATALOG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[ok] Phase P.1 정찰 단계 weight cap={RECON_WEIGHT_CAP} 적용")
    print(f"     영향 단서: {len(affected)}건 / cell 압축: {cells_capped}")
    print()
    for ck, before, after in sorted(affected):
        marker = "✓" if before > RECON_WEIGHT_CAP else "·"
        print(f"  {marker} {ck:<42} max_w: {before:3d} → {after:2d}")
    return 0


if __name__ == "__main__":
    sys.exit(patch())
