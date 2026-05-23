"""DB 데이터 갭 진단 — 9 사고유형 × 2 CSP 매트릭스 정밀 점검.

사용법: python scripts/data_gap_audit.py
출력: 5개 카테고리별 (collection_targets / matchers / attack_rules / KB / synthetic) 매트릭스.

설계 근거:
  · dev3 청사진 §5 (9 사고유형 enum 확정 — 5종 + UNCLASSIFIED + 4 신규)
  · CLAUDE.md "AI 는 판단 X — 정적 데이터 기반"
  · 시연 시 어떤 사고유형이든 시연 가능해야 함

본 진단은 결정성 100% — 같은 시드 상태 → 같은 결과.
"""
from __future__ import annotations

import json
import sys
import re
from pathlib import Path

# backend/data 디렉토리 기준 — script 는 cloud/scripts 에 위치
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "backend" / "data"
BACKEND = ROOT / "backend"

sys.path.insert(0, str(BACKEND))


# 9 사고유형 (dev3 §5.1 확정)
INCIDENT_TYPES = [
    "CREDENTIAL_THEFT",
    "PRIVILEGE_ESCALATION",
    "DATA_EXFILTRATION",
    "AUDIT_LOG_TAMPERING",
    "RANSOMWARE",
    "MISCONFIG_EXPOSURE",
    "PHISH_INITIAL_ACCESS",
    "INSIDER_THREAT",
    # UNCLASSIFIED 는 시드 대상 X (분류 전 fallback)
]
CSPS = ["naver", "nhn"]


def _safe_count_json(path: Path, key: str | None = None) -> int:
    """JSON 파일 안전하게 카운트. 없거나 에러 시 0."""
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict) and key:
        v = data.get(key)
        if isinstance(v, list):
            return len(v)
    return 0


def audit_collection_targets() -> dict:
    """collection_targets/{csp}_{TYPE}.json 의 row 수."""
    matrix: dict = {}
    for t in INCIDENT_TYPES:
        matrix[t] = {}
        for csp in CSPS:
            p = DATA / "collection_targets" / f"{csp}_{t}.json"
            matrix[t][csp] = _safe_count_json(p)
    return matrix


def audit_matchers() -> dict:
    """matchers.py 의 _REGISTRY 에 (csp, incident_type) 등록 여부."""
    try:
        from core.ingestion.matchers import _REGISTRY  # type: ignore
    except Exception as e:
        print(f"⚠ matchers import 실패: {e}", file=sys.stderr)
        return {t: {c: False for c in CSPS} for t in INCIDENT_TYPES}

    matrix: dict = {}
    for t in INCIDENT_TYPES:
        matrix[t] = {}
        for csp in CSPS:
            matrix[t][csp] = (csp, t) in _REGISTRY
    return matrix


def audit_attack_rules() -> dict:
    """rules.json 의 csp별 룰 수 + 9 사고유형 매핑 가능성 (heuristic).

    각 사고유형에 자주 등장하는 technique_id 셋으로 커버 추정.
    """
    p = DATA / "attack_rules" / "rules.json"
    if not p.exists():
        return {"_error": "rules.json 없음"}
    data = json.loads(p.read_text(encoding="utf-8"))
    rules = data.get("rules", [])
    by_csp_techs: dict[str, set[str]] = {"ncp": set(), "nhn": set()}
    for r in rules:
        csp = r.get("csp")
        if csp in by_csp_techs:
            by_csp_techs[csp].add(r.get("technique_id", ""))

    # 사고유형 → 기대 기법 셋 (학술 변호: weights.json 등에서 동일 매핑 사용)
    TYPE_TO_TECH = {
        "CREDENTIAL_THEFT": {"T1078", "T1078.004", "T1110", "T1552", "T1136", "T1098.001"},
        "PRIVILEGE_ESCALATION": {"T1098", "T1098.001", "T1098.003", "T1136", "T1136.003", "T1078"},
        "DATA_EXFILTRATION": {"T1537", "T1530", "T1567", "T1041", "T1048"},
        "AUDIT_LOG_TAMPERING": {"T1562", "T1562.008", "T1562.001", "T1531", "T1485", "T1070"},
        "RANSOMWARE": {"T1486", "T1490", "T1485"},
        "MISCONFIG_EXPOSURE": {"T1190", "T1530", "T1580", "T1190.001"},
        "PHISH_INITIAL_ACCESS": {"T1566", "T1556", "T1078", "T1078.004"},
        "INSIDER_THREAT": {"T1078", "T1078.004", "T1530", "T1562"},
    }

    matrix: dict = {}
    for t, expected in TYPE_TO_TECH.items():
        matrix[t] = {}
        for csp_rule, csp_db in (("ncp", "naver"), ("nhn", "nhn")):
            present = by_csp_techs.get(csp_rule, set())
            # sub-technique 정규화 — T1098.001 도 T1098 매칭으로 인정
            present_norm = {tid.split(".")[0] for tid in present} | present
            expected_norm = {tid.split(".")[0] for tid in expected} | expected
            matched = expected_norm & present_norm
            matrix[t][csp_db] = (len(matched), len(expected_norm), sorted(expected_norm - matched))
    return matrix


def audit_kb_chunks() -> dict:
    """KB JSON 청크 수 (4종)."""
    files = ["attack.json", "playbook.json", "csp_doc.json", "case_db.json"]
    out: dict = {}
    for f in files:
        p = DATA / "kb" / f
        out[f.replace(".json", "")] = _safe_count_json(p, key="chunks")
    out["total"] = sum(v for v in out.values() if isinstance(v, int))

    # 사고유형 키워드 출현 빈도 (간이)
    type_keywords = {
        "CREDENTIAL_THEFT": ["credential", "T1078", "iam", "자격증명"],
        "PRIVILEGE_ESCALATION": ["privilege", "T1098", "권한", "정책"],
        "DATA_EXFILTRATION": ["exfil", "T1537", "T1530", "유출", "object storage"],
        "AUDIT_LOG_TAMPERING": ["T1562", "T1485", "tamper", "로그 변조", "흔적 제거"],
        "RANSOMWARE": ["T1486", "랜섬", "ransom", "encrypt"],
        "MISCONFIG_EXPOSURE": ["T1190", "T1580", "misconfig", "설정"],
        "PHISH_INITIAL_ACCESS": ["T1566", "phish", "피싱"],
        "INSIDER_THREAT": ["insider", "내부자"],
    }

    by_type: dict = {}
    for t, kws in type_keywords.items():
        count = 0
        for f in files:
            p = DATA / "kb" / f
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8").lower()
            for kw in kws:
                if kw.lower() in text:
                    count += text.count(kw.lower())
        by_type[t] = count
    out["by_type_keyword_hits"] = by_type
    return out


def audit_synthetic_logs() -> dict:
    """data/synthetic/*.json 의 9 사고유형 × 2 CSP 커버리지."""
    matrix: dict = {}
    syn_dir = DATA / "synthetic"

    # 명명 규칙 매핑 (파일명 슬러그 → INCIDENT_TYPE)
    SLUG_MAP = {
        "credential": "CREDENTIAL_THEFT",
        "privilege": "PRIVILEGE_ESCALATION",
        "exfil": "DATA_EXFILTRATION",
        "audit": "AUDIT_LOG_TAMPERING",
        "ransom": "RANSOMWARE",
        "misconfig": "MISCONFIG_EXPOSURE",
        "phish": "PHISH_INITIAL_ACCESS",
        "insider": "INSIDER_THREAT",
        "sysdig": "CREDENTIAL_THEFT",  # 사실기반 시나리오 (CT 시작)
        "capital_one": "DATA_EXFILTRATION",
        "collection": None,  # 일반 시나리오
        "none": None,
    }

    for t in INCIDENT_TYPES:
        matrix[t] = {"naver": [], "nhn": []}

    if syn_dir.exists():
        for p in sorted(syn_dir.glob("*.json")):
            name = p.name.lower()
            csp = "naver" if name.startswith("ncp_") else ("nhn" if name.startswith("nhn_") else None)
            if csp is None:
                continue
            tag = None
            for slug, t in SLUG_MAP.items():
                if slug in name and t:
                    tag = t
                    break
            if tag and tag in matrix:
                events = _safe_count_json(p)
                matrix[tag][csp].append((p.name, events))
    return matrix


def _print_matrix(title: str, matrix: dict, fmt_cell):
    print(f"\n=== {title} ===")
    header = f"{'사고유형':25s} | {'NCP/naver':30s} | {'NHN/nhn':30s}"
    print(header)
    print("-" * len(header))
    for t in INCIDENT_TYPES:
        row = matrix.get(t, {})
        cells = [t]
        for csp in CSPS:
            cells.append(fmt_cell(row.get(csp)))
        print(f"{cells[0]:25s} | {cells[1]:30s} | {cells[2]:30s}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

    print("=" * 80)
    print("AI Sherpa — DB 데이터 갭 진단 (사이클 1)")
    print(f"기준: 9 사고유형 (UNCLASSIFIED 제외 8 + 시드 대상) × 2 CSP")
    print("=" * 80)

    # 1. collection_targets
    m1 = audit_collection_targets()
    _print_matrix(
        "1. collection_targets/*.json — DB 시드 row 수",
        m1,
        lambda v: f"{v} row" if v else "❌ 없음",
    )

    # 2. matchers
    m2 = audit_matchers()
    _print_matrix(
        "2. matchers.py _REGISTRY — (csp, incident_type) 등록 여부",
        m2,
        lambda v: "✓ 등록" if v else "❌ 미등록",
    )

    # 3. attack_rules
    m3 = audit_attack_rules()
    if "_error" in m3:
        print(f"\n3. attack_rules — {m3['_error']}")
    else:
        _print_matrix(
            "3. attack_rules — 사고유형별 기법 커버리지 (매칭/기대)",
            m3,
            lambda v: (
                f"{v[0]}/{v[1]} ({v[0]*100//v[1] if v[1] else 0}%) miss: {','.join(v[2][:2])}{'…' if len(v[2])>2 else ''}"
                if v else "—"
            ),
        )

    # 4. KB
    print("\n=== 4. KB 청크 — data/kb/*.json ===")
    kb = audit_kb_chunks()
    for k, v in kb.items():
        if k == "by_type_keyword_hits":
            continue
        print(f"  {k:20s}: {v}")
    print()
    print("  사고유형별 키워드 출현 (단순 grep — 본격 분포는 아님):")
    for t in INCIDENT_TYPES:
        hits = kb["by_type_keyword_hits"].get(t, 0)
        bar = "█" * min(hits, 50)
        marker = "✓" if hits >= 10 else ("⚠ 부족" if hits >= 3 else "❌ 거의 없음")
        print(f"    {t:25s}: {hits:4d}  {bar}  {marker}")

    # 5. synthetic logs
    m5 = audit_synthetic_logs()
    _print_matrix(
        "5. synthetic logs — 합성 시나리오 파일·이벤트 수",
        m5,
        lambda v: (
            ", ".join(f"{name}({n})" for name, n in v) if v else "❌ 없음"
        ),
    )

    # 6. 종합 갭 요약 (P0 후보)
    print("\n" + "=" * 80)
    print("📊 종합 — 시연 임팩트 큰 갭 (P0 후보)")
    print("=" * 80)

    p0: list[str] = []
    for t in INCIDENT_TYPES:
        for csp in CSPS:
            # 합산 갭 점수
            has_seed = m1.get(t, {}).get(csp, 0) > 0
            has_matcher = m2.get(t, {}).get(csp, False)
            atk = m3.get(t, {}).get(csp)
            has_atk = bool(atk and atk[0] >= 2)  # ≥2 기법 커버
            has_syn = bool(m5.get(t, {}).get(csp))

            missing = []
            if not has_seed:
                missing.append("seed")
            if not has_matcher:
                missing.append("matcher")
            if not has_atk:
                missing.append("attack_rules")
            if not has_syn:
                missing.append("synthetic")

            if len(missing) >= 2:
                p0.append(f"  🔴 {t} × {csp:5s} — {','.join(missing)} 부재")
            elif len(missing) == 1:
                p0.append(f"  🟡 {t} × {csp:5s} — {missing[0]} 만 부재")

    if not p0:
        print("  ✅ 모든 사고유형 × CSP 가 4 영역(시드/매처/룰/합성) 충족")
    else:
        for line in p0[:30]:
            print(line)
        if len(p0) > 30:
            print(f"  …외 {len(p0)-30}건")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
