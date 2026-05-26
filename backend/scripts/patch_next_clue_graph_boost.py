"""next_clue_graph.json hypothesis_boost 보강 (2026-05-26 byungwoo).

이지호 PoC 보고서 §3.1 갭 발견: 8 사고유형 중 4개만 boost (CRED·PRIV·DATA·AUDIT).
누락: RANSOM · MISCONFIG · PHISH · INSIDER (dev3 추가분).

각 pivot 의 next_clue 에 도메인 정합 boost 추가. weights.json 단위 정책 (5/10/15/20/25/30) 유지.

사용: cd backend && .venv/Scripts/python.exe scripts/patch_next_clue_graph_boost.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


_BACKEND = Path(__file__).resolve().parents[1]
NCG_PATH = _BACKEND / "data" / "triage" / "next_clue_graph.json"


# (pivot.clue_type, next_clue.priority) → boost dict 추가
# 도메인 판단 — 사용자 시연·논리 정합
ADDITIONS: dict[tuple[str, int], dict[str, int]] = {
    # ── IP_ADDRESS ──
    ("IP_ADDRESS", 1): {"PHISH_INITIAL_ACCESS": 5, "INSIDER_THREAT": 5},  # 시각 패턴 — 피싱 후 재방문·내부자 베이스라인
    ("IP_ADDRESS", 2): {"INSIDER_THREAT": 10},  # 멀티 CSP — 내부자 횡적 이동 시그널
    ("IP_ADDRESS", 3): {"INSIDER_THREAT": 10},  # 권한 변경 — 내부자도 가능
    ("IP_ADDRESS", 4): {"PHISH_INITIAL_ACCESS": 15, "INSIDER_THREAT": 5},  # MFA 우회 — 피싱·AitM 강함

    # ── ACCOUNT ──
    ("ACCOUNT", 1): {"INSIDER_THREAT": 15},  # 권한 변경 — 내부자 시그널
    ("ACCOUNT", 2): {"RANSOMWARE": 15, "INSIDER_THREAT": 10},  # Object Storage 비정상 — 랜섬 암호화·내부자 다운로드
    ("ACCOUNT", 3): {"INSIDER_THREAT": 10, "PHISH_INITIAL_ACCESS": 10},  # IP 분포 — 사내 IP=내부자, 외부=피싱
    ("ACCOUNT", 4): {"MISCONFIG_EXPOSURE": 20, "PHISH_INITIAL_ACCESS": 15},  # MFA 미적용 — 설정 오류 + 피싱 표면

    # ── HASH ──
    ("HASH", 1): {"RANSOMWARE": 20, "PHISH_INITIAL_ACCESS": 15},  # EDR/VT 매칭 — 랜섬 payload·피싱 dropper
    ("HASH", 2): {"RANSOMWARE": 25, "INSIDER_THREAT": 10},  # Object Storage 업로드 — .locked·내부자 반출

    # ── DOMAIN ──
    ("DOMAIN", 1): {"PHISH_INITIAL_ACCESS": 15},  # 통신 내부 IP·계정 — 피싱 클릭자 식별
    ("DOMAIN", 2): {"RANSOMWARE": 20, "PHISH_INITIAL_ACCESS": 15},  # C2/DGA — 랜섬 C2·피싱 인프라

    # ── TIME_WINDOW ──
    ("TIME_WINDOW", 1): {"PHISH_INITIAL_ACCESS": 10},  # 비국내 IP — 피싱 외부 침투
    ("TIME_WINDOW", 2): {"INSIDER_THREAT": 15},  # 권한 변경 — 내부자 야간 작업
    ("TIME_WINDOW", 3): {"RANSOMWARE": 25},  # Object Storage 대량 — 랜섬 암호화 burst
    ("TIME_WINDOW", 4): {"INSIDER_THREAT": 15},  # 감사 로그 변경 — 내부자 흔적 인멸

    # ── SERVICE ──
    ("SERVICE", 1): {"INSIDER_THREAT": 10},  # 계정 목록 — 내부자 추적
    ("SERVICE", 2): {"INSIDER_THREAT": 15, "MISCONFIG_EXPOSURE": 10},  # 정책 변경 — 내부자·실수 misconfig
    ("SERVICE", 3): {"INSIDER_THREAT": 20, "MISCONFIG_EXPOSURE": 15},  # 로그 비활성 — 내부자 인멸·운영 미설계
}


def patch() -> int:
    if not NCG_PATH.exists():
        print(f"[error] {NCG_PATH} 없음", file=sys.stderr)
        return 1

    data = json.loads(NCG_PATH.read_text(encoding="utf-8"))
    pivots = data.get("pivots", [])

    patched = 0
    for pivot in pivots:
        ctype = pivot.get("clue_type", "")
        for nc in pivot.get("next_clues", []):
            prio = nc.get("priority")
            key = (ctype, prio)
            if key not in ADDITIONS:
                continue
            boost = nc.setdefault("hypothesis_boost", {})
            for hyp, val in ADDITIONS[key].items():
                if hyp not in boost:  # 기존 값 덮어쓰지 않음
                    boost[hyp] = val
                    patched += 1

    # _meta 갱신 — 보강 이력
    data["_meta"]["last_patched"] = "2026-05-26 byungwoo"
    data["_meta"]["status"] = (
        "v1-skeleton-patched — 4 사고유형 (RANSOM·MISCONFIG·PHISH·INSIDER) "
        "hypothesis_boost 보강 (이지호 PoC 보고서 §3.1 갭 발견 후속)"
    )

    NCG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[ok] next_clue_graph.json hypothesis_boost 보강: +{patched} 가중치")
    print(f"     출력: {NCG_PATH.relative_to(_BACKEND)}")
    return 0


if __name__ == "__main__":
    sys.exit(patch())
