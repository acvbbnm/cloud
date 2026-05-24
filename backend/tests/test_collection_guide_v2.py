"""CollectionGuideV2 헬퍼 단위 + seed_targets 풍부 메타 노출 회귀.

검증:
  · _action_matches (NCP substring/equal 매칭)
  · _event_id_matches (NHN prefix + 와일드카드)
  · _load_v1_seed_targets (사이클 6+) — 시드 슬림화 응답
  · 8 사고유형 × 2 CSP 모두 seed_targets ≥ 3건

DB 의존성 없는 순수 단위 테스트 — 빠르고 결정성 100%.
"""
from __future__ import annotations

import pytest

from core.intake.collection_guide_v2 import (
    _action_matches,
    _event_id_matches,
    _load_v1_seed_targets,
)


# ─── _action_matches ───────────────────────────────────────────


@pytest.mark.parametrize(
    "action,patterns,expected",
    [
        ("Login", ["Login"], True),
        ("Login", ["MFA Login", "Console Login"], True),  # substring 양방향
        ("Console Login", ["Login"], True),  # pattern in action
        ("CreateAccessKey", ["Create AccessKey"], False),  # 공백 차이 — 정확
        ("Random", ["Login", "Logout"], False),
        ("", ["Login"], False),  # 빈 action
        ("Login", [], False),  # 빈 patterns
        ("Login", None, False),  # None patterns
    ],
)
def test_action_matches(action, patterns, expected):
    assert _action_matches(action, patterns) == expected


def test_action_matches_case_insensitive():
    """매칭은 case-insensitive."""
    assert _action_matches("LOGIN", ["login"]) is True
    assert _action_matches("Login", ["LOGIN"]) is True


# ─── _event_id_matches ─────────────────────────────────────────


@pytest.mark.parametrize(
    "event_id,patterns,expected",
    [
        ("event_id.iam.login", ["event_id.iam.login"], True),
        ("event_id.iam.member.role.update", ["event_id.iam.member.role"], True),  # prefix
        ("event_id.cloud_trail.disable", ["event_id.cloud_trail.*"], True),  # wildcard
        ("event_id.iaas.s3credential.delete", ["event_id.iaas.s3credential.*"], True),
        ("event_id.other", ["event_id.iam.login"], False),
        ("", ["event_id.iam.login"], False),
        ("event_id.iam.login", [], False),
    ],
)
def test_event_id_matches(event_id, patterns, expected):
    assert _event_id_matches(event_id, patterns) == expected


# ─── _load_v1_seed_targets (사이클 6) ──────────────────────────


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


@pytest.mark.parametrize("itype", INCIDENT_TYPES)
@pytest.mark.parametrize("csp", CSPS)
def test_load_v1_seed_targets_returns_at_least_three(itype, csp):
    """각 (incident_type, csp) 조합에서 최소 3개 시드 노출."""
    seeds = _load_v1_seed_targets(itype, csp)
    assert len(seeds) >= 3, f"{csp} × {itype}: 시드 {len(seeds)} < 3"


@pytest.mark.parametrize("itype", INCIDENT_TYPES)
@pytest.mark.parametrize("csp", CSPS)
def test_load_v1_seed_targets_slim_response_fields(itype, csp):
    """슬림 응답에 12 필드 모두 있어야 한다 (frontend SeedTarget interface 정합)."""
    EXPECTED = {
        "target_id", "log_type", "description", "evidence_role", "priority",
        "storage_path", "retention_days", "layer", "hint", "cmd",
        "auto_collectible", "mitre_techniques",
    }
    seeds = _load_v1_seed_targets(itype, csp)
    for s in seeds:
        missing = EXPECTED - set(s.keys())
        assert not missing, f"{csp} × {itype} 시드 {s.get('target_id')}: 필드 누락 — {missing}"


@pytest.mark.parametrize("itype", INCIDENT_TYPES)
@pytest.mark.parametrize("csp", CSPS)
def test_load_v1_seed_targets_required_first(itype, csp):
    """REQUIRED 가 CORROBORATING 보다 먼저 나와야 (UI 우선순위)."""
    seeds = _load_v1_seed_targets(itype, csp)
    saw_corroborating = False
    for s in seeds:
        if s["evidence_role"] == "CORROBORATING":
            saw_corroborating = True
        elif s["evidence_role"] == "REQUIRED" and saw_corroborating:
            pytest.fail(
                f"{csp} × {itype}: REQUIRED 가 CORROBORATING 뒤에 나옴 "
                f"({s['target_id']})"
            )


def test_load_v1_seed_targets_unknown_returns_empty():
    """존재하지 않는 (incident_type, csp) 조합은 빈 리스트 반환."""
    assert _load_v1_seed_targets("UNKNOWN_TYPE", "naver") == []
    assert _load_v1_seed_targets("CREDENTIAL_THEFT", "aws") == []
