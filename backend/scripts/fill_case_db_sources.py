"""CASE_DB 출처 보강 (2026-05-24 KB audit P2).

배경:
  KB citation audit C 지표(출처 비공백) 81.0% 발견 — case_db.json 의 45 청크 중 30 개의
  source 필드가 비어있음. 환각은 아니지만 출처 신뢰도 평가에 약점.

전략:
  1. REMAP* — 역매핑 사례. _origin_case + 공개 보고서 URL 결합
  2. SYNTHETIC* 또는 "가설 모델" — 합성/가설 시나리오 라벨
  3. 그 외 (attack-sim 내부 케이스) — 내부 테스트 라벨

실행:
  cd backend && python -m scripts.fill_case_db_sources
멱등 (이미 source 가 비공백이면 skip).

후속:
  ChromaDB 사용 시 `python -m core.sherpa.embed_kb` 재실행으로 재임베딩 필요.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ── 역매핑 사례별 공개 출처 URL ────────────────────────────────
# 검증 가능한 공개 보고서(Wikipedia / 회사 공식 블로그 / 공인 매체) 우선.
REMAP_SOURCES: dict[str, str] = {
    "CASE-REMAP-NCP-CRED-001": (
        "Capital One Public Incident Report 2019 — "
        "https://en.wikipedia.org/wiki/2019_Capital_One_data_breach"
    ),
    "CASE-REMAP-NHN-CRED-001": (
        "Uber Data Breach 2016 — "
        "https://en.wikipedia.org/wiki/Uber_data_breach"
    ),
    "CASE-REMAP-NCP-PRIVESC-001": (
        "Rhino Security Labs CloudGoat iam_privesc_by_attachment — "
        "https://github.com/RhinoSecurityLabs/cloudgoat"
    ),
    "CASE-REMAP-NHN-PRIVESC-001": (
        "LastPass Security Incident 2022 — "
        "https://blog.lastpass.com/2022/12/notice-of-recent-security-incident/"
    ),
    "CASE-REMAP-NCP-EXFIL-001": (
        "Imperva Security Incident 2019 — "
        "https://www.imperva.com/blog/ceoblog/"
    ),
    "CASE-REMAP-NHN-EXFIL-001": (
        "Capital One 2019 (S3 download focus) — "
        "https://en.wikipedia.org/wiki/2019_Capital_One_data_breach"
    ),
    "CASE-REMAP-NCP-AUDIT-001": (
        "Code Spaces Incident 2014 — "
        "https://www.computerworld.com/article/2476082/aws-and-the-code-spaces-saga.html"
    ),
    "CASE-REMAP-NHN-AUDIT-001": (
        "Tesla Cryptojacking 2018 (RedLock) — "
        "https://redlock.io/blog/cryptojacking-tesla"
    ),
    "CASE-REMAP-NCP-RANSOM-001": (
        "Colonial Pipeline Ransomware 2021 (DarkSide) — "
        "https://en.wikipedia.org/wiki/Colonial_Pipeline_ransomware_attack"
    ),
    "CASE-REMAP-NHN-RANSOM-001": (
        "MGM Resorts Cyberattack 2023 (ALPHV/Scattered Spider) — "
        "https://en.wikipedia.org/wiki/2023_MGM_Resorts_cyberattack"
    ),
    "CASE-REMAP-NCP-MISCFG-001": (
        "Capital One 2019 (Misconfig perspective) — "
        "https://en.wikipedia.org/wiki/2019_Capital_One_data_breach"
    ),
    "CASE-REMAP-NHN-MISCFG-001": (
        "Verkada Camera Hack 2021 — "
        "https://en.wikipedia.org/wiki/2021_Verkada_camera_hack"
    ),
    "CASE-REMAP-NCP-PHISH-001": (
        "Twilio 0ktapus Incident 2022 — "
        "https://www.twilio.com/blog/august-2022-social-engineering-attack"
    ),
    "CASE-REMAP-NHN-PHISH-001": (
        "Twitter Bitcoin Scam 2020 — "
        "https://en.wikipedia.org/wiki/2020_Twitter_account_hijacking"
    ),
    "CASE-REMAP-NCP-INSIDER-001": (
        "Tesla Sabotage Allegation 2018 (Martin Tripp) — "
        "https://www.cnbc.com/2018/06/20/elon-musk-tells-employees-tesla-was-sabotaged-internally.html"
    ),
    "CASE-REMAP-NHN-INSIDER-001": (
        "Coinbase Social Engineering 2023 — "
        "https://www.coinbase.com/blog/social-engineering-a-coordinated-attack-against-coinbase"
    ),
}

# ── 카테고리 분류 라벨 ────────────────────────────────────────
LABEL_SYNTHETIC = "(가설 시나리오, 학습용 — KB Synthetic v1)"
LABEL_INTERNAL_SIM = "(내부 attack-sim 결과, 학습용 — KB Internal Test v1)"


def classify(chunk_id: str, title: str) -> str:
    """카테고리별 source 라벨 결정.

    우선순위:
      1. REMAP_SOURCES 명시 → 공개 사건 URL
      2. SYNTHETIC* 또는 title 에 '가설 모델' → 합성 라벨
      3. 그 외 → 내부 attack-sim 라벨
    """
    if chunk_id in REMAP_SOURCES:
        return REMAP_SOURCES[chunk_id]
    if "SYNTHETIC" in chunk_id or "가설 모델" in title:
        return LABEL_SYNTHETIC
    return LABEL_INTERNAL_SIM


def main() -> int:
    case_db_path = Path(__file__).resolve().parent.parent / "data" / "kb" / "case_db.json"
    if not case_db_path.exists():
        print(f"[ERROR] case_db.json not found: {case_db_path}", file=sys.stderr)
        return 1

    with case_db_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = data.get("chunks", [])
    total = len(chunks)
    filled = 0
    skipped_with_source = 0

    for c in chunks:
        existing = (c.get("source") or "").strip()
        if existing:
            skipped_with_source += 1
            continue
        new_source = classify(c["chunk_id"], c.get("title", ""))
        c["source"] = new_source
        filled += 1

    # ── 결과 출력 (utf-8) ──
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"[OK] CASE_DB sources 보강 완료")
    print(f"  - 전체 청크: {total}")
    print(f"  - 기존 비공백 (skip): {skipped_with_source}")
    print(f"  - 신규 채움: {filled}")

    if filled == 0:
        print("[SKIP] 변경 사항 없음 — 파일 미수정")
        return 0

    # 저장 (멱등 — 같은 파일에 덮어쓰기)
    with case_db_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] 저장 완료: {case_db_path}")
    print()
    print("후속 작업: ChromaDB 사용 시 `python -m core.sherpa.embed_kb` 재실행")
    return 0


if __name__ == "__main__":
    sys.exit(main())
