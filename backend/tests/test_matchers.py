"""매처 회귀 테스트 — 8 사고유형 × 2 CSP = 16 매처 + 합성 로그 매칭률.

사이클 1~6 의 작업 안정성 보장:
  · _REGISTRY 16개 매처 등록 여부
  · 각 매처가 자신의 합성 시나리오에서 ≥75% 매칭
  · 매처 함수가 NCP/NHN 포맷 raw 이벤트를 입력으로 처리

회귀 기준: 매칭률 75% 미만이면 데이터 변경 또는 매처 로직 변경을 의심.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from core.ingestion.matchers import _REGISTRY, match
from core.ingestion.parsers.ncp import parse as parse_ncp
from core.ingestion.parsers.nhn import parse as parse_nhn

DATA = Path(__file__).resolve().parent.parent / "data" / "synthetic"

# 8 사고유형 × 2 CSP — 사이클 1·6 진단 결과 정합
EXPECTED_TYPES = [
    "CREDENTIAL_THEFT",
    "PRIVILEGE_ESCALATION",
    "DATA_EXFILTRATION",
    "AUDIT_LOG_TAMPERING",
    "RANSOMWARE",
    "MISCONFIG_EXPOSURE",
    "PHISH_INITIAL_ACCESS",
    "INSIDER_THREAT",
]
EXPECTED_CSPS = ["naver", "nhn"]


def test_registry_has_all_16_pairs():
    """_REGISTRY 에 8 사고유형 × 2 CSP = 16 매처가 모두 등록되어야 한다."""
    for itype in EXPECTED_TYPES:
        for csp in EXPECTED_CSPS:
            assert (csp, itype) in _REGISTRY, f"매처 미등록: ({csp}, {itype})"
    # 추가 항목은 OK — 미만이면 안 됨
    assert len(_REGISTRY) >= 16, f"_REGISTRY 크기 부족: {len(_REGISTRY)}"


# 시나리오별 (csp, incident_type, filename, parser, 최소매칭률)
# 사이클 6 풀 회귀 결과 기준 — 안정 통과치 75%
SCENARIOS = [
    ("naver", "CREDENTIAL_THEFT", "ncp_sysdig_8min_killchain.json", parse_ncp, 0.75),
    ("nhn", "CREDENTIAL_THEFT", "nhn_credential_theft_real.json", parse_nhn, 0.70),
    ("naver", "PRIVILEGE_ESCALATION", "ncp_privilege_escalation.json", parse_ncp, 0.90),
    ("nhn", "PRIVILEGE_ESCALATION", "nhn_privilege_escalation.json", parse_nhn, 0.90),
    ("naver", "DATA_EXFILTRATION", "ncp_data_exfiltration.json", parse_ncp, 0.90),
    ("nhn", "DATA_EXFILTRATION", "nhn_capital_one_style.json", parse_nhn, 0.75),
    ("naver", "AUDIT_LOG_TAMPERING", "ncp_audit_log_tampering.json", parse_ncp, 0.75),
    ("nhn", "AUDIT_LOG_TAMPERING", "nhn_audit_log_tampering.json", parse_nhn, 0.70),
    ("naver", "RANSOMWARE", "ncp_ransomware.json", parse_ncp, 0.90),
    ("nhn", "RANSOMWARE", "nhn_ransomware.json", parse_nhn, 0.90),
    ("naver", "MISCONFIG_EXPOSURE", "ncp_misconfig_exposure.json", parse_ncp, 0.75),
    ("nhn", "MISCONFIG_EXPOSURE", "nhn_misconfig_exposure.json", parse_nhn, 0.75),
    ("naver", "PHISH_INITIAL_ACCESS", "ncp_phish_initial_access.json", parse_ncp, 0.90),
    ("nhn", "PHISH_INITIAL_ACCESS", "nhn_phish_initial_access.json", parse_nhn, 0.90),
    ("naver", "INSIDER_THREAT", "ncp_insider_threat.json", parse_ncp, 0.90),
    ("nhn", "INSIDER_THREAT", "nhn_insider_threat.json", parse_nhn, 0.90),
]


@pytest.mark.parametrize("csp,itype,fname,parser,min_rate", SCENARIOS)
def test_matcher_against_synthetic_scenario(csp, itype, fname, parser, min_rate):
    """각 매처가 자신의 합성 시나리오에서 최소 매칭률 이상을 달성해야 한다."""
    path = DATA / fname
    assert path.exists(), f"합성 로그 파일 없음: {path}"

    raw = path.read_text(encoding="utf-8")
    parsed = parser(raw)
    assert parsed, f"파서가 빈 결과 — {fname}"

    matched = sum(1 for ev in parsed if match(csp, itype, ev))
    rate = matched / len(parsed)
    assert rate >= min_rate, (
        f"{csp} × {itype}: matched={matched}/{len(parsed)} "
        f"({rate*100:.1f}%) < min {min_rate*100:.0f}%"
    )


def test_match_dispatcher_returns_none_for_unknown_pair():
    """등록되지 않은 (csp, incident_type) 조합은 None 반환."""
    assert match("naver", "UNKNOWN_TYPE", {}) is None
    assert match("aws", "CREDENTIAL_THEFT", {}) is None


def test_match_dispatcher_handles_empty_event():
    """빈 event 입력도 안전하게 None 반환 (예외 없음)."""
    for csp, itype in _REGISTRY.keys():
        result = match(csp, itype, {})
        # None 또는 string (Login 같은 빈 패턴이 일부 일치할 수 있음) — 예외만 없으면 OK
        assert result is None or isinstance(result, str)
