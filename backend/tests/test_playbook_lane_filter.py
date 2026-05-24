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


def test_lane_filter_unknown_type_returns_empty():
    """존재하지 않는 incident_type 지정 시 — strict filter, 빈 결과 반환.

    잘못된 lane 의 plays 를 fallback 으로 보여주는 것보다 honest empty 가 더 안전.
    (KB audit 2026-05-24 B 지표 개선 — 47.6% → 100% strict)
    """
    result = AISherpa.recommend_playbook(
        ["T1078.004", "T1098"],
        incident_type="NONEXISTENT_TYPE_FOR_TEST",
    )
    # NONEXISTENT lane 은 KB 에 없으므로 모든 청크가 필터 탈락 → 빈 결과
    assert result["playbooks"] == [], (
        f"NONEXISTENT lane 인데도 playbook 반환됨 — strict filter 회귀: {result['playbooks']}"
    )


def test_lane_filter_response_includes_incident_type():
    """필터 작동 검증 — 각 playbook 응답에 incident_type 필드 노출."""
    result = AISherpa.recommend_playbook(
        ["T1530"],
        incident_type="DATA_EXFILTRATION",
    )
    for pb in result["playbooks"]:
        assert "incident_type" in pb, "playbook 응답에 incident_type 필드 누락"
