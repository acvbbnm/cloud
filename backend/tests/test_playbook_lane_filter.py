"""PLAYBOOK lane 필터 회귀 테스트 (2026-05-24 KB audit P1).

배경:
  사용자 KB citation audit 에서 B 지표(사고유형 정합) 47.6% 발견 —
  PLAYBOOK keyword 검색이 lane 과 다른 사고유형 plays 까지 회수.
  recommend_playbook(chain, incident_type=...) 으로 lane 필터 적용 후
  반환되는 청크의 incident_type 이 lane 또는 'ALL' 만이어야 한다.

검증 지점:
  1. incident_type 미지정 → 기존 동작 (전 카테고리 검색, 회귀 차단)
  2. incident_type 지정 → 필터된 청크만 (B 지표 개선)
  3. 매칭 청크 0건이어도 graceful — fallback 으로 top-3 반환 (UX 깨짐 방지)
"""
from __future__ import annotations

from core.sherpa.ai_sherpa import AISherpa


def test_lane_unspecified_keeps_legacy_behavior():
    """incident_type 미지정 시 기존 동작 — 회귀 차단."""
    result = AISherpa.recommend_playbook(["T1078.004", "T1098"])
    assert "playbooks" in result
    assert isinstance(result["playbooks"], list)
    # 미지정이므로 lane 필터링 안 됨 — 다양한 type 청크 회수 가능


def test_lane_filter_keeps_only_matching_lane():
    """incident_type 지정 시 반환되는 모든 청크가 lane 또는 ALL."""
    incident_type = "CREDENTIAL_THEFT"
    result = AISherpa.recommend_playbook(
        ["T1078.004", "T1098"],
        incident_type=incident_type,
    )
    for pb in result["playbooks"]:
        chunk_type = pb.get("incident_type")
        # lane 매칭 또는 ALL 또는 None(lane 미지정 KB 호환)만 허용
        assert chunk_type in (incident_type, "ALL", None), (
            f"lane 외 청크 회수됨: incident_type={chunk_type}, expected={incident_type}/ALL"
        )


def test_lane_filter_unknown_type_falls_back_to_common():
    """존재하지 않는 incident_type 지정 시 — 3-tier 폴백 (G2 결정, 2026-05-24).

    G2: NIST 공통 (tier2) 폴백 채택 — Wiz/NIST 패턴. 회의 결정 사항.
    이전 진규 안의 strict 빈 반환은 CLAUDE.md "AI 는 검색·요약·제안만" 원칙 상
    "제안 회피" 가 되므로, NIST 공통 5-Phase 절차를 항상 제공.

    검증: tier1 0건 + tier2 (NIST 공통) > 0건. tier1 항목은 없어야 함.
    """
    result = AISherpa.recommend_playbook(
        ["T1078.004", "T1098"],
        incident_type="NONEXISTENT_TYPE_FOR_TEST",
    )
    ts = result["tier_summary"]
    assert ts["tier1_exact"] == 0, (
        f"NONEXISTENT lane 에 tier1 매칭 발생 — 회귀: {ts}"
    )
    assert ts["tier2_common"] > 0, (
        f"NIST 공통 폴백 미작동 — 회귀: {ts}"
    )
    # 반환된 playbook 들은 모두 incident_type='ALL' (공통) 또는 키워드 매칭
    for pb in result["playbooks"]:
        assert pb["match_tier"] in ("tier2_common", "tier3_keyword"), (
            f"NONEXISTENT lane 에서 tier1 노출됨: {pb}"
        )


def test_lane_filter_response_includes_incident_type():
    """필터 작동 검증 — 각 playbook 응답에 incident_type 필드 노출."""
    result = AISherpa.recommend_playbook(
        ["T1530"],
        incident_type="DATA_EXFILTRATION",
    )
    for pb in result["playbooks"]:
        assert "incident_type" in pb, "playbook 응답에 incident_type 필드 누락"
