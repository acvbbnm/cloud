"""attack_rules/rules.json 무결성 + 사이클 5 보강 회귀.

검증:
  · 모든 룰의 정규식 컴파일 (AttackMapper._load_rules)
  · rule_id 유일성
  · 필수 필드 (rule_id / csp / technique_id / tactic / activity_name_pattern)
  · csp 가 'ncp' 또는 'nhn'
  · 9 사고유형 기대 기법 셋이 모두 커버됨 (사이클 5 +16 룰 확인)
"""
from __future__ import annotations

import json
import re
import pytest
from pathlib import Path

from core.analysis.attack_mapper import _load_rules

DATA = Path(__file__).resolve().parent.parent / "data" / "attack_rules" / "rules.json"


def _all_rules():
    return json.loads(DATA.read_text(encoding="utf-8"))["rules"]


def test_rules_file_exists():
    assert DATA.exists(), "attack_rules/rules.json 없음"


def test_rules_compile_via_loader():
    """AttackMapper._load_rules() 가 모든 룰을 regex 컴파일하여 로드."""
    rules = _load_rules()
    assert rules, "컴파일된 룰 0 — 로더 또는 파일 오류"
    # 모든 룰이 _re 필드 (컴파일된 regex) 보유
    for r in rules:
        assert "_re" in r, f"룰 {r.get('rule_id')}: 정규식 컴파일 결과 없음"


def test_rule_id_unique():
    rules = _all_rules()
    ids = [r["rule_id"] for r in rules]
    assert len(ids) == len(set(ids)), "rule_id 중복 발견"


def test_rules_have_required_fields():
    REQUIRED = ["rule_id", "csp", "technique_id", "tactic", "activity_name_pattern"]
    for r in _all_rules():
        for f in REQUIRED:
            assert f in r and r[f], f"{r.get('rule_id','?')}: 필수 필드 '{f}' 부재"


def test_rule_csp_is_valid():
    """csp 는 'ncp' 또는 'nhn' 만 허용."""
    for r in _all_rules():
        assert r["csp"] in {"ncp", "nhn"}, f"{r['rule_id']}: csp={r['csp']}"


def test_rule_technique_id_format():
    """technique_id 는 'T\\d+' 또는 'T\\d+\\.\\d+' 형식."""
    pat = re.compile(r"^T\d+(\.\d+)?$")
    for r in _all_rules():
        assert pat.match(r["technique_id"]), (
            f"{r['rule_id']}: 잘못된 technique_id 형식 — {r['technique_id']}"
        )


def test_rule_regex_compiles_individually():
    """activity_name_pattern 이 모두 유효한 정규식이어야 한다."""
    for r in _all_rules():
        try:
            re.compile(r["activity_name_pattern"])
        except re.error as e:
            pytest.fail(f"{r['rule_id']}: regex error — {e}")


# 사이클 5 보강 — 9 사고유형의 기대 기법 (학술 변호 가능 매핑)
EXPECTED_TECHNIQUES = {
    "CREDENTIAL_THEFT": {"T1078", "T1078.004", "T1110", "T1552"},
    "PRIVILEGE_ESCALATION": {"T1098", "T1098.001", "T1098.003", "T1136.003"},
    "DATA_EXFILTRATION": {"T1537", "T1530", "T1567", "T1041", "T1048"},
    "AUDIT_LOG_TAMPERING": {"T1562.008", "T1531", "T1485", "T1070", "T1562.001"},
    "RANSOMWARE": {"T1486", "T1490", "T1485"},
    "MISCONFIG_EXPOSURE": {"T1190", "T1530", "T1580"},
    "PHISH_INITIAL_ACCESS": {"T1566", "T1556", "T1078.004"},
    "INSIDER_THREAT": {"T1078.004", "T1530"},
}


def _present_technique_set():
    rules = _all_rules()
    present = {r["technique_id"] for r in rules}
    # sub-technique normalize — T1078.004 도 T1078 으로 인정
    return present | {t.split(".")[0] for t in present}


def test_all_expected_techniques_covered():
    """사이클 5 보강 후 9 사고유형의 기대 기법이 attack_rules 에 모두 등장."""
    present = _present_technique_set()
    missing_map: dict[str, list[str]] = {}
    for itype, expected in EXPECTED_TECHNIQUES.items():
        expected_norm = expected | {t.split(".")[0] for t in expected}
        missing = sorted(expected_norm - present)
        if missing:
            missing_map[itype] = missing
    assert not missing_map, (
        f"미커버 기법 (사이클 5 보강 누락):\n"
        + "\n".join(f"  {k}: {v}" for k, v in missing_map.items())
    )


def test_minimum_total_rules():
    """사이클 5 종료 시점 룰 수 보장 — 회귀 시 줄면 즉시 감지."""
    rules = _all_rules()
    assert len(rules) >= 70, f"룰 수 부족 — {len(rules)} < 70 (사이클 5 종료 시 74)"


def test_minimum_per_csp_rules():
    """NCP/NHN 각 30 룰 이상 — 한 CSP 만 보강되어 균형 무너지는 회귀 차단."""
    rules = _all_rules()
    by_csp = {"ncp": 0, "nhn": 0}
    for r in rules:
        by_csp[r["csp"]] = by_csp.get(r["csp"], 0) + 1
    assert by_csp["ncp"] >= 30, f"NCP 룰 부족 — {by_csp['ncp']}"
    assert by_csp["nhn"] >= 30, f"NHN 룰 부족 — {by_csp['nhn']}"
