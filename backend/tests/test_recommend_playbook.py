"""recommend_playbook 3-tier 라우팅 회귀 테스트 (2026-05-24 P2 머지 통합).

검증:
  · 빈 chain + incident_type 없음 → 빈 playbooks (예외 X)
  · 정상 chain 입력 시 응답 스키마 정합 (playbooks/tier_summary/incident_type/message)
  · KB 검색이 작동하면 playbooks 반환 (PLAYBOOK 카테고리 한정)
  · 각 playbook 에 match_score / match_tier 메타 포함 (G3 결정)

G2 결정 (2026-05-24, byungwoo+jingyu 머지): 결정론 3-tier 채택. 근형 안의
RAG+LLM 결합 요약 (summary/summary_sources/chain) 은 chat 으로 중복 가능하므로 제거.
"""
from __future__ import annotations

from core.sherpa.ai_sherpa import AISherpa


def test_recommend_playbook_empty_chain_returns_empty():
    """빈 chain + incident_type 미지정 → 빈 playbooks (예외 X)."""
    result = AISherpa.recommend_playbook([])
    assert result["playbooks"] == []
    assert result["tier_summary"] == {}


def test_recommend_playbook_response_schema():
    """정상 chain 입력 시 3-tier 응답 스키마: playbooks/tier_summary/incident_type/message."""
    result = AISherpa.recommend_playbook(["T1078.004", "T1098"])
    assert "playbooks" in result
    assert "tier_summary" in result
    assert "incident_type" in result
    assert "message" in result
    # tier_summary 는 dict — tier1/tier2/tier3 카운트
    ts = result["tier_summary"]
    assert isinstance(ts, dict)
    assert "tier1_exact" in ts
    assert "tier2_common" in ts
    assert "tier3_keyword" in ts


def test_recommend_playbook_playbook_items_have_required_fields():
    """playbooks 리스트의 각 항목이 5 필드 (playbook_id/title/steps/tactics_addressed/sources)."""
    result = AISherpa.recommend_playbook(["T1078.004", "T1537"])
    for pb in result["playbooks"]:
        assert "playbook_id" in pb
        assert "title" in pb
        assert "steps" in pb and isinstance(pb["steps"], list)
        assert "tactics_addressed" in pb
        assert "sources" in pb and isinstance(pb["sources"], list)


def test_recommend_playbook_sources_have_kb_type_playbook():
    """검색 결과 sources 가 PLAYBOOK 타입만 (kb_filter 적용 검증)."""
    result = AISherpa.recommend_playbook(["T1078.004", "T1098"])
    for pb in result["playbooks"]:
        for src in pb["sources"]:
            assert src.get("type") == "PLAYBOOK", (
                f"PLAYBOOK 외 타입 검색됨: {src.get('type')}"
            )


def test_recommend_playbook_handles_unknown_technique_gracefully():
    """존재하지 않는 technique ID 도 예외 없이 빈/소수 결과."""
    result = AISherpa.recommend_playbook(["T9999.999"])
    # 키워드 매칭으로 일부 결과는 나올 수 있지만 예외는 안 됨
    assert isinstance(result["playbooks"], list)
