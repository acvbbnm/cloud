"""외부 학습 데이터를 팀원 전달용 zip 으로 패키징 (2026-05-26 byungwoo).

문제: Windows Defender 가 Atomic Red Team 의 실행 스크립트 (.ps1, .bat, .sh)
를 악성으로 차단. PowerShell Compress-Archive 실패.

해결: 우리에 필요한 메타데이터만 화이트리스트 압축:
    - Atomic Red Team: *.yaml 만 (prerequisite_techniques 정보)
    - ATT&CK Flow: *.afb, *.json 만 (시퀀스)
    - ATT&CK STIX: enterprise-attack.json (전체)

위험 파일 제외 — .ps1 / .bat / .sh / .exe / .dll / .py 등 실행 가능 파일 차단.

출력: exports/external_sources_2026-05-26.zip
사용: cd backend && .venv/Scripts/python.exe scripts/package_external_sources.py
"""
from __future__ import annotations

import sys
import zipfile
from datetime import datetime
from pathlib import Path


_BACKEND = Path(__file__).resolve().parents[1]
SRC = _BACKEND / "data" / "triage" / "external_sources"
EXPORTS = _BACKEND / "exports"
EXPORTS.mkdir(exist_ok=True)
OUT_ZIP = EXPORTS / "external_sources_2026-05-26.zip"


# ─────────────────────────────────────────────────────────────
# 화이트리스트 패턴
# ─────────────────────────────────────────────────────────────


# 위험 확장자 (Windows Defender 차단 회피)
BLOCKED_EXTS = {
    ".ps1", ".psm1", ".psd1",     # PowerShell
    ".bat", ".cmd",                # Batch
    ".sh", ".bash", ".zsh",        # Shell
    ".exe", ".dll", ".msi",        # Windows 실행
    ".py", ".pyc",                 # Python 실행 (학습 메타에 불필요)
    ".vbs", ".wsf", ".hta",        # 스크립트
    ".dmg", ".pkg",                # macOS 실행
}


# 허용 확장자 (소스별)
ALLOWED_BY_SOURCE: dict[str, set[str]] = {
    "atomic-red-team": {".yaml", ".yml", ".md"},  # YAML + README
    "attack-flow": {".afb", ".json", ".md"},      # AFB + JSON
    "attack-stix": {".json"},                     # 단일 JSON
}


def is_blocked(path: Path) -> bool:
    """확장자가 위험 목록이면 차단."""
    return path.suffix.lower() in BLOCKED_EXTS


def is_allowed(path: Path, source: str) -> bool:
    """소스별 화이트리스트 통과 여부."""
    allowed = ALLOWED_BY_SOURCE.get(source, set())
    return path.suffix.lower() in allowed


# ─────────────────────────────────────────────────────────────
# 압축
# ─────────────────────────────────────────────────────────────


def package() -> dict:
    """3 소스를 zip 으로 압축. 반환: 통계 dict."""
    if not SRC.exists():
        print(f"[error] 소스 디렉토리 없음: {SRC}", file=sys.stderr)
        print(f"        먼저 scripts/fetch_external_sources.py 실행하세요.")
        return {}

    stats: dict[str, dict] = {}
    blocked_total = 0
    total_files = 0
    total_size = 0

    print(f"패키징 시작 → {OUT_ZIP.name}")
    print(f"  소스: {SRC.relative_to(_BACKEND)}")
    print()

    started = datetime.now()
    with zipfile.ZipFile(
        OUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zf:
        for source_name in sorted(ALLOWED_BY_SOURCE.keys()):
            src_root = SRC / source_name
            if not src_root.exists():
                print(f"  [skip] {source_name}: 디렉토리 없음")
                continue

            n_added = 0
            n_blocked = 0
            n_filtered = 0
            size_added = 0

            for f in src_root.rglob("*"):
                if not f.is_file():
                    continue
                # 위험 차단
                if is_blocked(f):
                    n_blocked += 1
                    continue
                # 화이트리스트
                if not is_allowed(f, source_name):
                    n_filtered += 1
                    continue
                # 추가
                arcname = f.relative_to(SRC).as_posix()
                zf.write(f, arcname=arcname)
                n_added += 1
                size_added += f.stat().st_size

            stats[source_name] = {
                "added": n_added,
                "blocked": n_blocked,
                "filtered": n_filtered,
                "size_mb": size_added / 1024 / 1024,
            }
            blocked_total += n_blocked
            total_files += n_added
            total_size += size_added

            print(
                f"  [{source_name:18}] +{n_added:4} 파일 ({size_added / 1024 / 1024:.1f} MB) "
                f"· 차단 {n_blocked} · 필터 {n_filtered}"
            )

    elapsed = (datetime.now() - started).total_seconds()
    zip_size = OUT_ZIP.stat().st_size / 1024 / 1024

    print()
    print("=" * 60)
    print(f"완료 — {OUT_ZIP.name} ({zip_size:.1f} MB)")
    print(f"  총 {total_files} 파일 · 원본 {total_size / 1024 / 1024:.1f} MB → "
          f"압축 {zip_size:.1f} MB (압축률 {(1 - zip_size / (total_size / 1024 / 1024)) * 100:.0f}%)")
    print(f"  위험 파일 차단: {blocked_total} 개 (.ps1/.bat/.exe 등)")
    print(f"  소요: {elapsed:.1f} 초")
    print("=" * 60)
    print()
    print(f"팀원 안내:")
    print(f"  1. {OUT_ZIP.name} 받아서 cloud/backend/data/triage/ 아래 압축 해제")
    print(f"  2. 결과: backend/data/triage/external_sources/")
    print(f"     ├─ atomic-red-team/  (YAML 만)")
    print(f"     ├─ attack-flow/      (.afb + JSON)")
    print(f"     └─ attack-stix/      (enterprise-attack.json)")

    return {
        "sources": stats,
        "total_files": total_files,
        "zip_size_mb": zip_size,
        "blocked": blocked_total,
    }


if __name__ == "__main__":
    result = package()
    sys.exit(0 if result else 1)
