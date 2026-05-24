"""collection_targets 시드 무결성 + 사이클 6 풍부화 필드 회귀.

검증:
  · 16 시드 파일 모두 존재 (8 사고유형 × 2 CSP)
  · 각 row 의 필수 필드 (target_id / incident_type / csp / log_type / evidence_role)
  · evidence_role ∈ {REQUIRED, CORROBORATING}
  · csp 가 파일명과 일치
  · 사이클 6 풍부화 필드 5개 (layer/hint/cmd/auto_collectible/mitre_techniques) 존재
  · mitre_techniques 가 list[str] 형식
  · target_id 가 전체에서 unique
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "collection_targets"

INCIDENT_TYPES = [
    "CREDENTIAL_THEFT",
    "PRIVILEGE_ESCALATION",
    "DATA_EXFILTRATION",
    "AUDIT_LOG_TAMPERING",
    "RANSOMWARE",
    "MISCONFIG_EXPOSURE",
    "PHISH_INITIAL_ACCESS",
    "INSIDER_THREAT",
]
CSPS = ["naver", "nhn"]

REQUIRED_BASE_FIELDS = [
    "target_id",
    "incident_type",
    "csp",
    "log_type",
    "evidence_role",
]
ENRICHMENT_FIELDS = [
    "layer",
    "hint",
    "cmd",
    "auto_collectible",
    "mitre_techniques",
]


@pytest.mark.parametrize("itype", INCIDENT_TYPES)
@pytest.mark.parametrize("csp", CSPS)
def test_seed_file_exists(itype, csp):
    """모든 8 × 2 = 16 시드 파일이 존재해야 한다."""
    p = DATA / f"{csp}_{itype}.json"
    assert p.exists(), f"시드 파일 없음: {p}"


def _load_all_seeds():
    """16 시드 파일을 한꺼번에 로드 — fixture 없이 재사용."""
    out = []
    for itype in INCIDENT_TYPES:
        for csp in CSPS:
            p = DATA / f"{csp}_{itype}.json"
            if not p.exists():
                continue
            rows = json.loads(p.read_text(encoding="utf-8"))
            for r in rows:
                out.append((p.name, itype, csp, r))
    return out


def test_all_seeds_have_required_base_fields():
    """모든 시드 row 는 기본 5필드를 가져야 한다."""
    for fname, itype, csp, row in _load_all_seeds():
        for field in REQUIRED_BASE_FIELDS:
            assert field in row, f"{fname} {row.get('target_id')}: 필수 필드 '{field}' 부재"


def test_seed_incident_type_matches_filename():
    """row.incident_type 이 파일명과 일치해야 한다."""
    for fname, itype, csp, row in _load_all_seeds():
        assert row["incident_type"] == itype, (
            f"{fname}: row.incident_type={row['incident_type']} ≠ 파일명 {itype}"
        )


def test_seed_csp_matches_filename():
    """row.csp 가 파일명과 일치해야 한다."""
    for fname, itype, csp, row in _load_all_seeds():
        assert row["csp"] == csp, (
            f"{fname}: row.csp={row['csp']} ≠ 파일명 {csp}"
        )


def test_seed_evidence_role_is_valid():
    """evidence_role 은 REQUIRED 또는 CORROBORATING."""
    valid = {"REQUIRED", "CORROBORATING"}
    for fname, _, _, row in _load_all_seeds():
        assert row["evidence_role"] in valid, (
            f"{fname} {row['target_id']}: 잘못된 evidence_role={row['evidence_role']}"
        )


def test_seed_target_id_is_unique_globally():
    """target_id 가 전체에서 unique (16 파일 누적)."""
    ids: set[str] = set()
    duplicates: list[str] = []
    for _, _, _, row in _load_all_seeds():
        tid = row.get("target_id")
        if tid in ids:
            duplicates.append(tid)
        ids.add(tid)
    assert not duplicates, f"중복 target_id: {duplicates}"


def test_seed_has_enrichment_fields_or_audit_format():
    """사이클 6 풍부화 — 모든 시드가 5 신규 필드를 가져야 한다.

    AUDIT 시드는 이미 더 풍부한 형식 (cmd_path 등 추가). 둘 다 허용.
    """
    for fname, _, _, row in _load_all_seeds():
        for field in ENRICHMENT_FIELDS:
            assert field in row, (
                f"{fname} {row['target_id']}: 풍부화 필드 '{field}' 부재 "
                f"(scripts/enrich_collection_seeds.py 재실행 필요)"
            )


def test_seed_mitre_techniques_is_list_of_strings():
    """mitre_techniques 는 list[str] 형식 (빈 리스트 허용)."""
    for fname, _, _, row in _load_all_seeds():
        mt = row.get("mitre_techniques")
        assert isinstance(mt, list), f"{fname} {row['target_id']}: mitre_techniques 가 list 아님"
        for tid in mt:
            assert isinstance(tid, str), f"{fname} {row['target_id']}: 기법 항목이 str 아님 — {tid}"
            assert tid.startswith("T"), f"{fname}: 잘못된 기법 ID 형식 — {tid}"


def test_seed_priority_is_int_when_present():
    """priority 필드는 있으면 int."""
    for fname, _, _, row in _load_all_seeds():
        p = row.get("priority")
        if p is not None:
            assert isinstance(p, int), f"{fname} {row['target_id']}: priority 타입 오류 — {type(p)}"
