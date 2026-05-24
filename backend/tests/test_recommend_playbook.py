"""recommend_playbook LLM 보강 회귀 테스트 (2026-05-24 마지막 깡통 해소).

검증:
  · 빈 chain 입력 시 안전한 빈 응답 (예외 X)
  · 정상 chain 입력 시 응답 스키마 정합 (playbooks/summary/summary_sources/chain)
  · KB 검색이 작동하면 playbooks 반환 (PLAYBOOK 카테고리 한정)

LLM 호출 자체는 Ollama 미연결 시 fallback 으로 summary=None 반환되어 테스트 안정.
실 LLM 응답 품질은 E2E 시 검증 (CI 환경에선 unit test 만).
"""
from __future__ import annotations

from core.sherpa.ai_sherpa import AISherpa


def test_recommend_playbook_empty_chain_returns_empty():
    """빈 chain 입력 → 빈 playbooks + summary=None (예외 X)."""
    result = AISherpa.recommend_playbook([])
    assert result["playbooks"] == []
    assert result["summary"] is None


def test_recommend_playbook_response_schema():
    """정상 chain 입력 시 응답 스키마 4 필드 (playbooks/summary/summary_sources/chain)."""
    result = AISherpa.recommend_playbook(["T1078.004", "T1098"])
    assert "playbooks" in result
    assert "summary" in result
    # chain 보존 — 빈 응답 시에도 추가됐는지 확인 (개선된 응답이 chain 키를 항상 보유해야 함)
    # 빈 chain 케이스에선 chain 키 없을 수 있으므로 정상 chain 일 때만 검증
    if result["playbooks"]:
        assert "summary_sources" in result
        assert "chain" in result
        assert result["chain"] == ["T1078.004", "T1098"]


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
