"""data_gap_audit.py 통합 — P0/P1 갭 0 유지 회귀.

사이클 6 종료 시점:
  · P0 0건 (모든 사고유형 × CSP 가 4 영역 충족)
  · P1 0건 (CT-NHN 합성 + attack_rules 보강 후)

회귀 시 즉시 감지:
  · 누가 새 사고유형 추가하고 매처/시드/합성 안 만들면 fail
  · 시드 삭제·매처 삭제 회귀도 fail
"""
from __future__ import annotations

import sys
from pathlib import Path

# scripts 경로 추가 — data_gap_audit 임포트용
ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

# data_gap_audit 의 module-level main() 은 print 만 함.
# 검증용 함수들을 직접 import 해서 매트릭스 결과 검사.
import data_gap_audit as audit  # noqa: E402


def test_audit_module_loads():
    """data_gap_audit.py 모듈이 임포트되어야 한다."""
    assert hasattr(audit, "audit_collection_targets")
    assert hasattr(audit, "audit_matchers")
    assert hasattr(audit, "audit_attack_rules")
    assert hasattr(audit, "audit_synthetic_logs")


def test_all_seeds_present_for_8_types_x_2_csps():
    """16 시드 매트릭스 — 모든 셀에 row ≥ 3건."""
    m = audit.audit_collection_targets()
    failures = []
    for itype in audit.INCIDENT_TYPES:
        for csp in audit.CSPS:
            cnt = m.get(itype, {}).get(csp, 0)
            if cnt < 3:
                failures.append(f"{itype} × {csp}: {cnt} row")
    assert not failures, "시드 부족:\n  " + "\n  ".join(failures)


def test_all_matchers_registered_for_8_types_x_2_csps():
    """16 매처 매트릭스 — 모든 (csp, incident_type) 등록."""
    m = audit.audit_matchers()
    failures = []
    for itype in audit.INCIDENT_TYPES:
        for csp in audit.CSPS:
            if not m.get(itype, {}).get(csp, False):
                failures.append(f"{itype} × {csp}")
    assert not failures, "매처 미등록:\n  " + "\n  ".join(failures)


def test_attack_rules_cover_each_type_at_least_2_techniques():
    """각 사고유형이 ≥2 기법 매칭 (사이클 5 보강 후 기준)."""
    m = audit.audit_attack_rules()
    if "_error" in m:
        import pytest
        pytest.fail(m["_error"])
    failures = []
    for itype in audit.INCIDENT_TYPES:
        for csp in audit.CSPS:
            cell = m.get(itype, {}).get(csp)
            # cell = (matched_count, expected_count, missing_list)
            if not cell or cell[0] < 2:
                failures.append(f"{itype} × {csp}: matched={cell[0] if cell else 0}")
    assert not failures, "기법 커버리지 부족:\n  " + "\n  ".join(failures)


def test_synthetic_logs_present_for_each_type():
    """각 사고유형이 ≥1 합성 로그 보유 (NCP 또는 NHN 중 최소 하나)."""
    m = audit.audit_synthetic_logs()
    failures = []
    for itype in audit.INCIDENT_TYPES:
        row = m.get(itype, {})
        total_files = len(row.get("naver", [])) + len(row.get("nhn", []))
        if total_files == 0:
            failures.append(f"{itype}: 합성 로그 0건")
    assert not failures, "합성 로그 부족:\n  " + "\n  ".join(failures)


def test_p0_gap_count_is_zero():
    """P0 갭 (시드/매처 동시 부재 + 기법 ≥2 + 합성 ≥1) 이 0건이어야 한다.

    사이클 6 종료 기준 상태 유지. 회귀 시 즉시 감지.
    """
    seeds = audit.audit_collection_targets()
    matchers = audit.audit_matchers()
    attacks = audit.audit_attack_rules()
    syn = audit.audit_synthetic_logs()

    p0 = []
    for itype in audit.INCIDENT_TYPES:
        for csp in audit.CSPS:
            has_seed = seeds.get(itype, {}).get(csp, 0) > 0
            has_matcher = matchers.get(itype, {}).get(csp, False)
            atk_cell = attacks.get(itype, {}).get(csp)
            has_atk = bool(atk_cell and atk_cell[0] >= 2)
            has_syn = bool(syn.get(itype, {}).get(csp))

            missing = []
            if not has_seed: missing.append("seed")
            if not has_matcher: missing.append("matcher")
            if not has_atk: missing.append("attack_rules")
            if not has_syn: missing.append("synthetic")
            if len(missing) >= 2:
                p0.append(f"  🔴 {itype} × {csp}: {','.join(missing)}")

    assert not p0, f"P0 갭 {len(p0)}건 발견:\n" + "\n".join(p0)
