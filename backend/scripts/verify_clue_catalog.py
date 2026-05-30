"""단서 카탈로그 무결성 검증 (2026-05-28, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §14 단서 카탈로그

검증 항목 (8가지)
-----------------
    1. weight_source 누락 단서 0건
    2. 가중치 cap 위반 (정찰 ≤10 / 본격 ≤20) 0건
    3. 학술 라벨 누락 (MITRE/NIST/KISA/CSA/ISO 1개 이상) 0건
    4. 중복 slug (동일 value 가 다른 prefix 로) 보고
    5. prefix 표준 위반 (#1 표준화 후) — 현재 6 종 패턴 분포 보고
    6. 카테고리 분포 (143 단서 prefix 별)
    7. likelihood max P(c|h) 분포 — 강·약 단서 균형
    8. has_weights=False 단서 0건

사용
----
    cd backend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.verify_clue_catalog

종료 코드
--------
    0  통과 (모든 단서 무결성 ✓)
    1  실패 (1건 이상 위반)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from core.intake.info_gain import weights_to_likelihood


CATALOG_PATH = _BACKEND_DIR / "data" / "triage" / "clue_catalog.json"

# 학술/산업 표준 라벨 (weight_source 에 1개 이상 포함되어야)
ACADEMIC_LABELS = [
    "MITRE", "T1", "ATT&CK",          # MITRE ATT&CK
    "NIST", "SP 800",                  # NIST
    "KISA", "KrCERT",                  # KISA
    "CSA",                             # Cloud Security Alliance
    "ISO 27035", "ISO 27037",          # ISO
    "Mandiant", "Verizon DBIR",        # 산업 보고서
    "Berger",                          # Robust Bayes
]

# 가중치 cap (Phase P.1+P.10): 정찰 단서는 약하게, 본격 단서는 ≤20
CAP_RECON_PREFIXES = ("Q1_inception:", "Q2A:", "Q2B:", "Q2C:")  # 정찰
CAP_RECON = 10
CAP_GENERAL = 20

# 정찰 prefix vs 본격 prefix
RECON_PREFIXES = ("Q1_inception:",)  # Q1 만 진짜 정찰. Q2 류는 본격으로 분류


def _classify_prefix(clue_key: str) -> str:
    """prefix 패턴 분류 — 표준화 진행 시 매핑 대상."""
    if clue_key.startswith("Q1_inception:"):
        return "decision.Q1.inception (snake+colon)"
    if re.match(r"^Q2[A-D]:", clue_key):
        return "decision.Q2X (camel+colon)"
    if re.match(r"^Q[3-6]-[A-Z]+:", clue_key):
        return "decision.QN-LANE (dash+lane)"
    if re.match(r"^Q[3-6]_[A-Z]+:", clue_key):
        return "decision.QN_LANE (underscore+lane)"
    if re.match(r"^Q[3-6]:", clue_key):
        return "decision.QN (plain)"
    if clue_key.startswith("TECHNIQUE:"):
        return "attack.technique"
    if re.match(r"^(IP_ADDRESS|ACCOUNT|HASH|DOMAIN|TIME_WINDOW|SERVICE):", clue_key):
        return "ioc.{type} (DFIR-IRIS)"
    return "기타/미분류"


def _cap_for(clue_key: str) -> int:
    return CAP_RECON if clue_key.startswith(RECON_PREFIXES) else CAP_GENERAL


def main() -> int:
    if not CATALOG_PATH.exists():
        print(f"[FATAL] 카탈로그 없음: {CATALOG_PATH}")
        return 2

    cat = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    clues = cat.get("clues", {})
    total = len(clues)
    print("=" * 78)
    print(f" 단서 카탈로그 무결성 검증 — {total} clues")
    print("=" * 78)

    fail = 0
    warn = 0

    # ── 1. weight_source 누락 ──
    no_src = [k for k, v in clues.items() if not v.get("weight_source")]
    print(f"\n[1] weight_source 누락: {len(no_src)}건", "✓" if not no_src else "✗")
    if no_src:
        fail += 1
        for k in no_src[:10]:
            print(f"     - {k}")
        if len(no_src) > 10:
            print(f"     ... +{len(no_src)-10}개")

    # ── 2. 가중치 cap 위반 ──
    overs = []
    for k, v in clues.items():
        w = v.get("weights", {})
        if not w:
            continue
        max_w = max(w.values())
        cap = _cap_for(k)
        if max_w > cap:
            overs.append((k, max_w, cap))
    print(f"\n[2] 가중치 cap 위반 (정찰 ≤{CAP_RECON} / 본격 ≤{CAP_GENERAL}): {len(overs)}건", "✓" if not overs else "✗")
    if overs:
        fail += 1
        for k, mw, cap in overs[:10]:
            print(f"     - {k}: max={mw} > {cap}")

    # ── 3. 학술 라벨 누락 ──
    no_label = []
    for k, v in clues.items():
        src = v.get("weight_source", "") or ""
        if not any(lb in src for lb in ACADEMIC_LABELS):
            no_label.append(k)
    print(f"\n[3] 학술 라벨 누락 (MITRE/NIST/KISA/CSA/ISO 등): {len(no_label)}건", "✓" if not no_label else "⚠")
    if no_label:
        warn += 1
        for k in no_label[:10]:
            print(f"     - {k}  (src='{(clues[k].get('weight_source') or '')[:50]}')")
        if len(no_label) > 10:
            print(f"     ... +{len(no_label)-10}개")

    # ── 4. 중복 slug — weights/label 비교로 "진짜 동일" vs "의도된 별개" 구분 ──
    slug_map = defaultdict(list)
    for k in clues:
        if ":" in k:
            slug = k.split(":", 1)[1]
            slug_map[slug].append(k)
    dup_slugs = {s: ks for s, ks in slug_map.items() if len(ks) > 1}

    real_dup = []      # weights·label 모두 동일 → 진짜 중복 (FAIL 대상)
    intended = []      # weights 다름 → 의도된 별개 (INFO)
    for s, ks in dup_slugs.items():
        first = clues[ks[0]]
        all_same = all(
            clues[k].get("weights") == first.get("weights")
            and clues[k].get("label") == first.get("label")
            for k in ks[1:]
        )
        if all_same:
            real_dup.append((s, ks))
        else:
            intended.append((s, ks))

    print(f"\n[4] slug 중복 검사 ({len(dup_slugs)} slug 가 다중 prefix):")
    print(f"     · 진짜 중복 (weights·label 동일): {len(real_dup)}건", "✓" if not real_dup else "✗")
    if real_dup:
        fail += 1
        for s, ks in real_dup[:5]:
            print(f"       - slug='{s}': {ks}")
    print(f"     · 의도된 별개 (weights 다름 — false-positive): {len(intended)}건", "(INFO)")
    for s, ks in intended[:5]:
        # 어느 weights 가 다른지 1-라인 차이 표시
        ws = [(k, max(clues[k].get("weights", {}).values() or [0])) for k in ks]
        print(f"       - slug='{s}': {[f'{k}(max={mw})' for k, mw in ws]}")

    # ── 5. prefix 표준 분포 ──
    prefix_cnt = Counter(_classify_prefix(k) for k in clues)
    print(f"\n[5] prefix 표준 분포 ({len(prefix_cnt)} 종):")
    for pref, n in prefix_cnt.most_common():
        marker = "  " if "미분류" not in pref else "⚠ "
        print(f"   {marker}{pref:<40} {n:>4}")
    if len(prefix_cnt) > 4:
        print(f"   ⚠ {len(prefix_cnt)} 종 prefix — #1 표준화 시 4 종 (decision/attack/ioc/recon) 으로 통합 목표")

    # ── 6. has_weights=False ──
    nw = [k for k, v in clues.items() if not v.get("has_weights")]
    print(f"\n[6] has_weights=False (사용 불가 단서): {len(nw)}건", "✓" if not nw else "⚠")
    if nw:
        warn += 1

    # ── 7. likelihood max P(c|h) 분포 ──
    print(f"\n[7] max P(c|h) 분포 (SMOOTHING={2.0} 적용):")
    lk_max = []
    for k, v in clues.items():
        w = v.get("weights", {})
        if not w:
            continue
        lk = weights_to_likelihood(w)
        if lk:
            lk_max.append(max(lk.values()))
    if lk_max:
        bins = {">0.40": 0, "0.30-0.40": 0, "0.25-0.30": 0, "0.20-0.25": 0, "<0.20": 0}
        for x in lk_max:
            if x > 0.40: bins[">0.40"] += 1
            elif x >= 0.30: bins["0.30-0.40"] += 1
            elif x >= 0.25: bins["0.25-0.30"] += 1
            elif x >= 0.20: bins["0.20-0.25"] += 1
            else: bins["<0.20"] += 1
        for b, n in bins.items():
            print(f"     {b:<12} {n:>4} clues")
        print(f"     평균: {sum(lk_max)/len(lk_max):.3f}, 최대: {max(lk_max):.3f}, 최소: {min(lk_max):.3f}")

    # ── 종합 ──
    print()
    print("=" * 78)
    print(f" 종합: FAIL {fail} · WARN {warn} · 총 단서 {total}")
    print("=" * 78)
    if fail:
        print(" ✗ 무결성 검증 실패 — 위 FAIL 항목 보강 필요")
        return 1
    if warn:
        print(" ⚠ 통과 (경고 있음) — 위 WARN 항목 검토 권장")
    else:
        print(" ✓ 모든 단서 무결성 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
