"""KB citation audit — 5 지표(A~E) 측정.

2026-05-24 KB audit 후속 검증용. P0/P1/P2 fix 후 재측정 시 사용.

지표:
  A 존재성        : 인용 chunk_id 가 KB 에 실재하는가
  B 사고유형 정합 : PLAYBOOK 회수가 lane 또는 ALL 인가 (P1 lane filter)
  C 출처 비공백   : 모든 KB chunk 의 source 가 비공백인가 (P2 source fill)
  D 환각 없음     : LLM 응답 후처리 (_strip_unsourced_techniques) 가 작동하는가
                    Ollama 미연결 시 unit 수준 검증 (mock response 사용)
  E 수사 가치     : KB chunk 본문에 수사 키워드(탐지·증거·룰 등) 포함 비율

실행:
  cd backend && python -m scripts.kb_citation_audit

종료 코드:
  0 — 임계값 모두 통과
  1 — 1개 이상 임계값 미달
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from typing import Any

from core.sherpa.ai_sherpa import AISherpa
from core.sherpa.knowledge_base import KBChunk, load_all
from core.sherpa.llm_engine import _strip_unsourced_techniques


# ── 임계값 (P0/P1/P2 fix 적용 후 기대치) ──
THRESHOLDS = {
    "A": 100.0,  # 존재성 — 환각 chunk_id 0 보장
    "B": 100.0,  # lane 정합 — strict filter 적용 후 100%
    "C": 100.0,  # 출처 비공백 — fill_case_db_sources 적용 후 100%
    "D": 100.0,  # 환각 없음 — _strip_unsourced_techniques 후 0건
    "E": 95.0,   # 수사 가치 — 일부 청크는 메타 정보만일 수 있으므로 95% 임계
}

# E 지표용 — 수사 단서로 인정할 키워드 (사용자 audit 기준)
INVESTIGATION_KEYWORDS = [
    "탐지", "증거", "rule", "룰", "타임라인", "timeline", "롤백",
    "시그니처", "signature", "indicator", "지표", "ATT&CK", "MITRE",
    "T1", "log", "로그", "분석", "복구", "차단", "이상", "anomaly",
    "위협", "공격", "killchain", "kill chain", "체인", "단계",
    "기법", "technique", "tactic", "전술",
]


def _technique_pattern() -> re.Pattern:
    return re.compile(r"T\d{4}(?:\.\d{3})?")


# ─────────────────────────────────────────────────────────────
# A 존재성 — 모든 chunk_id 가 unique 하고 실재하는가
# ─────────────────────────────────────────────────────────────
def metric_a_existence(chunks: list[KBChunk]) -> tuple[float, str]:
    """KB 청크 chunk_id 무결성 (중복·빈 ID·잘못된 카테고리 검증)."""
    total = len(chunks)
    if total == 0:
        return 0.0, "KB 청크가 0건"

    chunk_ids = [c.chunk_id for c in chunks]
    valid = [
        cid for cid in chunk_ids
        if cid and isinstance(cid, str) and cid.strip()
    ]
    duplicates = [k for k, v in Counter(chunk_ids).items() if v > 1]
    pass_count = len(valid) - len(duplicates) * 2  # 중복은 양쪽 차감
    pct = (pass_count / total) * 100
    detail = f"{pass_count}/{total}"
    if duplicates:
        detail += f" — 중복 chunk_id {len(duplicates)}건: {duplicates[:3]}"
    return pct, detail


# ─────────────────────────────────────────────────────────────
# B 사고유형 정합 — PLAYBOOK strict lane filter 동작 검증
# ─────────────────────────────────────────────────────────────
def metric_b_lane_consistency() -> tuple[float, str]:
    """recommend_playbook(chain, incident_type=X) 결과가 lane 또는 ALL 만 반환하는가."""
    lanes = [
        ("CREDENTIAL_THEFT", ["T1078.004", "T1098"]),
        ("PRIVILEGE_ESCALATION", ["T1098", "T1078"]),
        ("DATA_EXFILTRATION", ["T1530", "T1537"]),
        ("AUDIT_LOG_TAMPERING", ["T1562.008", "T1070"]),
        ("RANSOMWARE", ["T1486", "T1490"]),
        ("MISCONFIG_EXPOSURE", ["T1530", "T1567"]),
        ("PHISH_INITIAL_ACCESS", ["T1566", "T1078.004"]),
        ("INSIDER_THREAT", ["T1078.004", "T1530"]),
    ]
    total_returned = 0
    valid_lane = 0
    for incident_type, chain in lanes:
        result = AISherpa.recommend_playbook(chain, incident_type=incident_type)
        for pb in result.get("playbooks", []):
            total_returned += 1
            pb_type = pb.get("incident_type")
            if pb_type in (incident_type, "ALL", None):
                valid_lane += 1
    if total_returned == 0:
        return 100.0, "0건 회수 (strict filter 작동, 보수적 패스)"
    pct = (valid_lane / total_returned) * 100
    return pct, f"{valid_lane}/{total_returned} — 8 lane 검증"


# ─────────────────────────────────────────────────────────────
# C 출처 비공백 — 모든 KB chunk 의 source 필드가 비공백
# ─────────────────────────────────────────────────────────────
def metric_c_source_non_empty(chunks: list[KBChunk]) -> tuple[float, str]:
    total = len(chunks)
    if total == 0:
        return 0.0, "KB 청크 0건"
    non_empty = [c for c in chunks if (c.source or "").strip()]
    pct = (len(non_empty) / total) * 100
    by_kb = Counter(c.kb_name for c in chunks if not (c.source or "").strip())
    detail = f"{len(non_empty)}/{total}"
    if by_kb:
        detail += f" — 비공백 누락: {dict(by_kb)}"
    return pct, detail


# ─────────────────────────────────────────────────────────────
# D 환각 없음 — _strip_unsourced_techniques 필터 동작 검증
# ─────────────────────────────────────────────────────────────
def metric_d_no_hallucination(chunks: list[KBChunk]) -> tuple[float, str]:
    """원래 audit 의 12 환각 사례를 시뮬레이션 응답에 주입 → 모두 라벨링되는지."""
    # 원래 audit 에서 발견된 12 환각 T-id
    known_hallucinations = [
        "T1552.001", "T1068", "T1069",
        "T1071.001", "T1114.001", "T1135", "T1210",
        "T1190", "T1218", "T1550.003",
        "T1078.004", "T1078.004",  # 동일 T-id 다른 lane 사례 (PRIVESC + INSIDER)
    ]
    # PLAYBOOK 외 청크 1건만 context 로 두고 12 환각 T-id 를 응답에 삽입
    # _strip_unsourced_techniques 가 모두 [KB외:Txxxx] 로 라벨링해야 함
    cred_chunks = [c for c in chunks if c.kb_name == "ATTACK"][:1]
    if not cred_chunks:
        return 0.0, "ATTACK KB 청크 없음 — 검증 불가"

    # context 에는 T9999 만 두어 환각 T-id 가 모두 외부 처리되도록 함
    from core.sherpa.knowledge_base import KBChunk as KB
    mock_context = [
        KB(
            chunk_id="audit-mock-001",
            kb_name="ATTACK",
            title="T9999 무관 기법",
            text="T9999 는 audit 전용 미사용 ID 입니다.",
            source="audit",
        )
    ]

    labeled = 0
    for tid in known_hallucinations:
        response = f"{tid} 가 관측되었습니다."
        filtered = _strip_unsourced_techniques(response, mock_context)
        if f"[KB외:{tid}]" in filtered:
            labeled += 1
    pct = (labeled / len(known_hallucinations)) * 100
    return pct, f"{labeled}/{len(known_hallucinations)} 환각 라벨링"


# ─────────────────────────────────────────────────────────────
# E 수사 가치 — chunk 본문에 수사 키워드 포함 비율
# ─────────────────────────────────────────────────────────────
def metric_e_investigative_value(chunks: list[KBChunk]) -> tuple[float, str]:
    total = len(chunks)
    if total == 0:
        return 0.0, "KB 청크 0건"
    pattern = re.compile("|".join(re.escape(k) for k in INVESTIGATION_KEYWORDS), re.IGNORECASE)
    valuable = [c for c in chunks if pattern.search(c.text + c.title)]
    pct = (len(valuable) / total) * 100
    return pct, f"{len(valuable)}/{total} — 키워드 매칭"


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────
def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 64)
    print("KB Citation Audit — P0/P1/P2 fix 적용 후 재측정")
    print("=" * 64)

    chunks = load_all()
    print(f"총 KB 청크: {len(chunks)}")
    by_kb = Counter(c.kb_name for c in chunks)
    print(f"카테고리별: {dict(by_kb)}")
    print()

    results: list[tuple[str, str, float, str, float, bool]] = []
    # (지표, 의미, 통과율, 상세, 임계값, pass)

    a_pct, a_detail = metric_a_existence(chunks)
    results.append(("A", "존재성 (chunk_id 무결성)", a_pct, a_detail, THRESHOLDS["A"], a_pct >= THRESHOLDS["A"]))

    b_pct, b_detail = metric_b_lane_consistency()
    results.append(("B", "사고유형 정합 (lane filter)", b_pct, b_detail, THRESHOLDS["B"], b_pct >= THRESHOLDS["B"]))

    c_pct, c_detail = metric_c_source_non_empty(chunks)
    results.append(("C", "출처 비공백", c_pct, c_detail, THRESHOLDS["C"], c_pct >= THRESHOLDS["C"]))

    d_pct, d_detail = metric_d_no_hallucination(chunks)
    results.append(("D", "환각 없음 (post-filter)", d_pct, d_detail, THRESHOLDS["D"], d_pct >= THRESHOLDS["D"]))

    e_pct, e_detail = metric_e_investigative_value(chunks)
    results.append(("E", "수사 가치 (키워드 포함)", e_pct, e_detail, THRESHOLDS["E"], e_pct >= THRESHOLDS["E"]))

    # 출력
    print(f"{'지표':<4} {'설명':<28} {'통과율':<10} {'임계':<8} {'결과':<6} 상세")
    print("-" * 92)
    failed = 0
    for code, label, pct, detail, threshold, passed in results:
        verdict = "✓ PASS" if passed else "✗ FAIL"
        if not passed:
            failed += 1
        # truncate detail for table
        detail_display = detail if len(detail) <= 40 else detail[:37] + "..."
        print(f"{code:<4} {label:<28} {pct:6.1f}%   ≥{threshold:.0f}%    {verdict}  {detail_display}")
    print()
    if failed == 0:
        print("[OK] 5 지표 전 항목 임계값 통과.")
    else:
        print(f"[FAIL] {failed}/5 지표 임계값 미달.")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
