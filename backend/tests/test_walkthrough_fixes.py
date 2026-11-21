"""Walkthrough 후속 보강 회귀 테스트 (2026-05-24).

검증 항목:
  · gap_detector — required_ids 비어있으면 completion_rate=None (UNCLASSIFIED 케이스)
  · report_generator — UNCLASSIFIED 케이스에 경고 메시지 노출 (구 placeholder 차단)
  · ingestion — UNCLASSIFIED_CASE / NO_MATCH 경고 코드가 코드 베이스에 존재
  · main.py — /api/health 가 LLMEngine.health() / RAGRetriever.backend_info() 실호출

각 항목은 walkthrough 에서 발견된 실 사용자 영향 이슈에 대응. 회귀 시 시연 깨짐.
"""
from __future__ import annotations

from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def test_gap_completion_rate_returns_none_when_no_requirements():
    """gap_detector — required_ids 없으면 completion_rate=None 반환 (UNCLASSIFIED 보호).

    2026-05-28 (geunhyung GapDetector v2 머지 후): 다른 비율 계산 (percent, mapping_rate)
    의 `else 0.0` 까지 잘못 검출되던 패턴 → completion_rate 라인만 정확히 검사.
    """
    src = (BACKEND / "core" / "analysis" / "gap_detector.py").read_text(encoding="utf-8")
    # completion_rate 블록만 정확히 추출 (앞뒤 5 라인 컨텍스트)
    lines = src.split("\n")
    block_lines: list[str] = []
    for i, line in enumerate(lines):
        if "completion_rate" in line and "=" in line:
            # 다음 5 라인까지 블록으로 포함 (round/else 표현식)
            block_lines.extend(lines[i : i + 6])
    block = "\n".join(block_lines)
    # completion_rate 블록에 else None 있어야 함 (UNCLASSIFIED 안전 표시)
    assert "else None" in block, "completion_rate None fallback 누락"
    # completion_rate 블록에 else 0.0 잔존 차단 (0% vs 미정의 혼동)
    assert "else 0.0" not in block, (
        "completion_rate 가 여전히 0.0 fallback — UNCLASSIFIED 케이스 표시 깨짐"
    )


def test_report_evidence_replaces_legacy_placeholder():
    """report_generator — '(대상 카탈로그 비어 있음)' 구 placeholder 제거 + UNCLASSIFIED 경고."""
    src = (BACKEND / "core" / "board" / "report_generator.py").read_text(encoding="utf-8")
    assert "(대상 카탈로그 비어 있음)" not in src, (
        "구 placeholder 잔존 — 외부 보고서에 미완성 텍스트 노출 위험"
    )
    assert "UNCLASSIFIED 상태로 수집 대상 카탈로그가 정의되지 않았습니다" in src, (
        "UNCLASSIFIED 경고 메시지 누락"
    )


def test_ingestion_has_unclassified_and_nomatch_warnings():
    """ingestion.py — upload 응답에 UNCLASSIFIED_CASE / NO_MATCH 경고 코드 포함."""
    src = (BACKEND / "api" / "ingestion.py").read_text(encoding="utf-8")
    assert "UNCLASSIFIED_CASE" in src, "UNCLASSIFIED_CASE 경고 코드 누락 — silent failure 회귀"
    assert "NO_MATCH" in src, "NO_MATCH 경고 코드 누락 — incident_type 확정인데도 매칭 0건일 때 침묵"


def test_health_endpoint_calls_real_engines():
    """main.py — /api/health 가 LLMEngine.health() / RAGRetriever.backend_info() 실호출."""
    src = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert "LLMEngine.health()" in src, "/api/health 가 LLMEngine.health() 미호출 — ollama 'unknown' 회귀"
    assert "RAGRetriever.backend_info()" in src, "/api/health 가 RAGRetriever 미호출 — chromadb 'unknown' 회귀"
    assert "ollama_detail" in src, "ollama_detail 필드 누락"
    assert "chromadb_detail" in src, "chromadb_detail 필드 누락"
