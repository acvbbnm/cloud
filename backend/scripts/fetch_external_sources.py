"""Phase H.1 — 외부 학습 데이터 수집 (2026-05-25, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §18.7 의논 결정 ①·②·③

수집 대상 (우선순위 순):
    1. Atomic Red Team — 700+ ATT&CK 기법별 atomic YAML 정의
       (prerequisite_techniques 필드로 transition edge 직접 추출)
    2. ATT&CK Flow Corpus — 30+ 실제 사고 ATT&CK 시퀀스 JSON
    3. ATT&CK STIX — Enterprise Matrix Techniques + Groups

저장 위치:
    backend/data/triage/external_sources/
      ├─ atomic-red-team/atomics/T{id}/T{id}.yaml × 700+
      ├─ attack-flow/corpus/*.json × 30+
      └─ attack-stix/enterprise-attack.json (Techniques + Groups)

저장 정책:
    .gitignore — 데이터 자체는 git 외부. 팀원에게 zip 별도 전달.
    학습 산출물 (clue_dag.json 등) 만 commit.

사용:
    cd backend && .venv/Scripts/python.exe scripts/fetch_external_sources.py
    (1회 실행 — 폐쇄망 진입 전 개발자 PC 에서)
"""
from __future__ import annotations

import io
import json
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen


_BACKEND_DIR = Path(__file__).resolve().parents[1]
TARGET_DIR = _BACKEND_DIR / "data" / "triage" / "external_sources"


# ─────────────────────────────────────────────────────────────
# 다운로드 헬퍼
# ─────────────────────────────────────────────────────────────


def _http_get(url: str, *, timeout: int = 60) -> bytes:
    """GitHub raw·archive URL 다운. requests 의존 X (stdlib only)."""
    req = Request(url, headers={"User-Agent": "ai-sherpa-fetch/1.0"})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def _extract_zip(data: bytes, dest: Path, *, strip_top: bool = True) -> int:
    """ZIP 압축 해제 + 최상위 디렉토리 제거 옵션. 반환: 추출된 파일 수."""
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = zf.namelist()
        # 공통 최상위 prefix 자동 감지 (예: "atomic-red-team-master/")
        top = ""
        if strip_top and members:
            parts = members[0].split("/", 1)
            if len(parts) == 2:
                top = parts[0] + "/"
                # 모든 멤버가 같은 top 인지 확인
                if not all(m.startswith(top) or m == top.rstrip("/") for m in members):
                    top = ""

        for m in members:
            if m.endswith("/"):
                continue
            rel = m[len(top):] if top and m.startswith(top) else m
            if not rel:
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(m) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
            count += 1
    return count


# ─────────────────────────────────────────────────────────────
# 1. Atomic Red Team (Red Canary)
# ─────────────────────────────────────────────────────────────


ATOMIC_URL = "https://github.com/redcanaryco/atomic-red-team/archive/refs/heads/master.zip"
ATOMIC_DIR = TARGET_DIR / "atomic-red-team"


def fetch_atomic_red_team() -> int:
    """Atomic Red Team master.zip 다운 → atomics/ 만 추출."""
    print(f"[1/3] Atomic Red Team 다운: {ATOMIC_URL}")
    if ATOMIC_DIR.exists() and (ATOMIC_DIR / "atomics").exists():
        files = list((ATOMIC_DIR / "atomics").rglob("T*.yaml"))
        if files:
            print(f"      ✓ 이미 존재: {len(files)} YAML — 스킵 (덮어쓰려면 폴더 삭제)")
            return len(files)

    data = _http_get(ATOMIC_URL, timeout=180)
    print(f"      다운 완료 ({len(data) / 1024 / 1024:.1f} MB)")
    count = _extract_zip(data, ATOMIC_DIR, strip_top=True)
    yaml_files = list((ATOMIC_DIR / "atomics").rglob("T*.yaml"))
    print(f"      ✓ 추출 {count} 파일, atomic YAML {len(yaml_files)}")
    return len(yaml_files)


# ─────────────────────────────────────────────────────────────
# 2. ATT&CK Flow Corpus
# ─────────────────────────────────────────────────────────────


ATTACK_FLOW_URL = (
    "https://github.com/center-for-threat-informed-defense/attack-flow"
    "/archive/refs/heads/main.zip"
)
FLOW_DIR = TARGET_DIR / "attack-flow"


def fetch_attack_flow() -> int:
    """ATT&CK Flow 저장소 → corpus/*.afb (JSON 형식, attack_flow_v2 스키마)."""
    print(f"[2/3] ATT&CK Flow 다운: {ATTACK_FLOW_URL}")

    def _count_corpus() -> int:
        corp = FLOW_DIR / "corpus"
        if not corp.exists():
            return 0
        # .afb (JSON 형식) + .json 모두 카운트
        return len(list(corp.glob("*.afb"))) + len(list(corp.glob("*.json")))

    if FLOW_DIR.exists() and _count_corpus() > 0:
        n = _count_corpus()
        print(f"      ✓ 이미 존재: {n} flow files — 스킵")
        return n

    data = _http_get(ATTACK_FLOW_URL, timeout=180)
    print(f"      다운 완료 ({len(data) / 1024 / 1024:.1f} MB)")
    count = _extract_zip(data, FLOW_DIR, strip_top=True)
    flow_n = _count_corpus()
    print(f"      ✓ 추출 {count} 파일, flow corpus {flow_n} (.afb)")
    return flow_n


# ─────────────────────────────────────────────────────────────
# 3. ATT&CK STIX Enterprise (Techniques + Groups)
# ─────────────────────────────────────────────────────────────


STIX_URL = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data"
    "/master/enterprise-attack/enterprise-attack.json"
)
STIX_DIR = TARGET_DIR / "attack-stix"


def fetch_attack_stix() -> int:
    """ATT&CK Enterprise Matrix STIX 단일 JSON 다운."""
    print(f"[3/3] ATT&CK STIX 다운: {STIX_URL}")
    target_file = STIX_DIR / "enterprise-attack.json"
    if target_file.exists():
        size_mb = target_file.stat().st_size / 1024 / 1024
        print(f"      ✓ 이미 존재 ({size_mb:.1f} MB) — 스킵")
        return 1

    STIX_DIR.mkdir(parents=True, exist_ok=True)
    data = _http_get(STIX_URL, timeout=180)
    target_file.write_bytes(data)
    # 검증: 유효한 JSON 이고 STIX bundle 형식인지
    obj = json.loads(data)
    n_objects = len(obj.get("objects", []))
    print(f"      ✓ STIX {n_objects} objects ({len(data) / 1024 / 1024:.1f} MB)")
    return 1


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────


def main() -> int:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    print(f"외부 데이터 수집 시작 → {TARGET_DIR}")
    print(f"※ 1회 실행 후 정적 활용. 학술 변호: paradigm doc §18 참조.\n")

    try:
        n_atomic = fetch_atomic_red_team()
    except Exception as e:
        print(f"[1/3] Atomic 실패: {e}", file=sys.stderr)
        n_atomic = 0

    try:
        n_flow = fetch_attack_flow()
    except Exception as e:
        print(f"[2/3] Flow 실패: {e}", file=sys.stderr)
        n_flow = 0

    try:
        n_stix = fetch_attack_stix()
    except Exception as e:
        print(f"[3/3] STIX 실패: {e}", file=sys.stderr)
        n_stix = 0

    print()
    print("=" * 60)
    print(f"수집 결과 — atomic YAML {n_atomic} · flow JSON {n_flow} · STIX {n_stix}")
    print("=" * 60)
    print()
    print("다음 단계 (H.2): scripts/build_clue_attack_mapping.py 로")
    print("143 단서 → ATT&CK 매핑 + clue_to_attack.json 생성")

    return 0 if (n_atomic and n_flow and n_stix) else 1


if __name__ == "__main__":
    sys.exit(main())
