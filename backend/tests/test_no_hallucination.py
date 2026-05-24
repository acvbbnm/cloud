"""환각 차단 회귀 테스트 — _strip_unsourced_techniques.

배경:
  2026-05-24 KB citation audit (사용자 보고) 에서 chat 응답에 컨텍스트 밖
  ATT&CK 기법 ID 가 12 건 도입된 사례 발견 (D 지표 85.7%).
  CLAUDE.md "AI 는 판단하지 않음" 원칙 위반 — 본 테스트로 회귀 차단.

검증 사례 (사용자 audit 결과):
  CRED         : T1552.001
  PRIVESC      : T1068, T1069, T1078.004
  DATA_EXFIL   : T1071.001
  MISCFG       : T1114.001, T1135, T1210
  PHISH        : T1190, T1218
  INSIDER      : T1078.004, T1550.003

전략:
  llm_engine._strip_unsourced_techniques(text, context) 가
  context 청크 밖 T-id 를 모두 [KB외:...] 라벨로 치환하는지 검증.
"""
import pytest

from core.sherpa.knowledge_base import KBChunk
from core.sherpa.llm_engine import (
    _extract_allowed_techniques,
    _strip_unsourced_techniques,
)


def _make_chunk(text: str, title: str = "Test", technique_id: str | None = None) -> KBChunk:
    """테스트용 KBChunk 빌더."""
    return KBChunk(
        chunk_id="test-001",
        kb_name="TEST",
        title=title,
        text=text,
        source="test",
        url=None,
        meta={"technique_id": technique_id} if technique_id else {},
    )


class TestExtractAllowedTechniques:
    """화이트리스트 추출 — context 의 모든 T-id 를 수집해야 한다."""

    def test_extract_from_text(self):
        chunks = [_make_chunk("T1078.004 는 자격증명 남용입니다.")]
        assert _extract_allowed_techniques(chunks) == {"T1078.004"}

    def test_extract_from_title(self):
        chunks = [_make_chunk("본문", title="T1098.001 Account Manipulation")]
        assert "T1098.001" in _extract_allowed_techniques(chunks)

    def test_extract_from_meta(self):
        chunks = [_make_chunk("본문", technique_id="T1530")]
        assert "T1530" in _extract_allowed_techniques(chunks)

    def test_extract_multiple(self):
        chunks = [
            _make_chunk("T1078.004 와 T1098.001 관련."),
            _make_chunk("T1530 데이터 유출."),
        ]
        result = _extract_allowed_techniques(chunks)
        assert {"T1078.004", "T1098.001", "T1530"} <= result

    def test_empty_context(self):
        assert _extract_allowed_techniques([]) == set()
        assert _extract_allowed_techniques(None) == set()


class TestStripUnsourcedTechniques:
    """필터 본체 — 허용 T-id 는 통과, 외부 T-id 는 라벨링."""

    def test_allowed_technique_passes(self):
        chunks = [_make_chunk("T1078.004 는 자격증명 남용입니다.")]
        resp = "T1078.004 는 자격증명 남용입니다."
        assert _strip_unsourced_techniques(resp, chunks) == resp

    def test_unsourced_technique_labeled(self):
        chunks = [_make_chunk("T1078.004 는 자격증명 남용입니다.")]
        resp = "T1552.001 도 같이 확인해야 합니다."
        result = _strip_unsourced_techniques(resp, chunks)
        assert "[KB외:T1552.001]" in result

    def test_subtechnique_allowed_when_base_in_chunks(self):
        """base T1098 이 화이트리스트면 sub T1098.001 도 통과 (관용 허용)."""
        chunks = [_make_chunk("T1098 은 계정 조작입니다.")]
        resp = "T1098.001 은 자격증명 변경입니다."
        result = _strip_unsourced_techniques(resp, chunks)
        assert "[KB외:" not in result
        assert "T1098.001" in result

    def test_mixed_response(self):
        """허용·금지 T-id 가 섞인 응답 — 금지만 라벨링."""
        chunks = [_make_chunk("T1078.004 자격증명, T1530 데이터 유출.")]
        resp = "T1078.004 와 T1552.001 이 함께 관측. T1530 도 발견."
        result = _strip_unsourced_techniques(resp, chunks)
        assert "T1078.004 와" in result  # 허용 통과
        assert "T1530 도" in result       # 허용 통과
        assert "[KB외:T1552.001]" in result  # 금지 라벨

    def test_empty_context_skips(self):
        """context 비면 검증 skip — fallback 경로 보호."""
        resp = "T1190 으로 진입했습니다."
        assert _strip_unsourced_techniques(resp, []) == resp
        assert _strip_unsourced_techniques(resp, None) == resp

    def test_empty_text(self):
        chunks = [_make_chunk("T1078 자격증명.")]
        assert _strip_unsourced_techniques("", chunks) == ""

    def test_no_techniques_in_response(self):
        """T-id 없는 일반 텍스트는 변형 없이 통과."""
        chunks = [_make_chunk("T1078.004 는 자격증명 남용입니다.")]
        resp = "관련 로그를 V-2 화면에서 업로드하세요."
        assert _strip_unsourced_techniques(resp, chunks) == resp


# ── 사용자 audit (2026-05-24) 에서 발견된 12 환각 사례 회귀 차단 ──


KNOWN_HALLUCINATIONS = [
    # (사고유형, 환각 T-id) — 모두 sources 밖 T-id 였음
    ("CRED", "T1552.001"),
    ("PRIVESC", "T1068"),
    ("PRIVESC", "T1069"),
    ("PRIVESC", "T1078.004"),
    ("DATA_EXFIL", "T1071.001"),
    ("MISCFG", "T1114.001"),
    ("MISCFG", "T1135"),
    ("MISCFG", "T1210"),
    ("PHISH", "T1190"),
    ("PHISH", "T1218"),
    ("INSIDER", "T1078.004"),
    ("INSIDER", "T1550.003"),
]


@pytest.mark.parametrize("incident_type,tid", KNOWN_HALLUCINATIONS)
def test_known_hallucination_labeled(incident_type, tid):
    """사용자 audit (2026-05-24) 12 환각 사례 — 모두 라벨링되는지 회귀 차단.

    context 에는 환각과 무관한 다른 T-id 만 두고, 환각 T-id 가 응답에 들어가면
    [KB외:...] 라벨이 부착되어야 한다.
    """
    # 환각과 다른 무관 T-id 만 context 에 둠 (sub 관용 허용에 걸리지 않도록 base 분리)
    chunks = [_make_chunk("T9999 는 테스트 전용 무관 기법입니다.")]
    resp = f"{incident_type} 케이스에서 {tid} 가 관찰되었습니다."
    result = _strip_unsourced_techniques(resp, chunks)
    assert f"[KB외:{tid}]" in result, (
        f"{incident_type} 의 환각 T-id {tid} 가 라벨링되지 않음 — 회귀 발생"
    )
