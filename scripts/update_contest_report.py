"""경진대회 최종발표 docx — 사이클 1~7 작업 반영 (2026-05-24).

대상 파일: C:\\Users\\User\\Desktop\\세종대\\2026-1학기\\Capstone\\
          경진대회 최종발표\\최종보고서_로그아웃_AI_Sherpa.docx

보강 항목 (병행):
  1. § 1.2.1 V-1 본문 끝 — Step 4 시드 가이드 UI 추가 문장
  2. § 6.3 끝에 6.3.4 — recommend_playbook RAG + LLM 결합
  3. § 6.4 끝에 6.4.6 — 데이터 사이클 보강 (시드 77 + 매처 16 + 룰 74 + 합성 16)
  4. § 6.4 끝에 6.4.7 — pytest 129 회귀 + GitHub Actions CI + pre-commit hook
  5. § 8 끝에 8.6 — pytest 회귀 시험 (5 모듈 129 케이스)

방식: python-docx 로 특정 헤딩 다음에 새 헤딩 + 본문 단락 + 표 삽입.
백업: git 으로 자연 보존 (커밋 전 원본 그대로).
"""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

sys.stdout.reconfigure(encoding="utf-8")

CONTEST_DOCX = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종보고서_로그아웃_AI_Sherpa.docx"
)


def _find_heading_index(doc, text_prefix: str) -> int:
    """헤딩 prefix 로 단락 인덱스 찾기. 못 찾으면 -1."""
    for i, p in enumerate(doc.paragraphs):
        st = (p.style.name or "")
        if st.startswith("Heading") and p.text.strip().startswith(text_prefix):
            return i
    return -1


def _insert_after(doc, anchor_para, style_name: str, text: str):
    """anchor_para 다음에 새 단락 삽입 + 반환."""
    new_p = anchor_para.insert_paragraph_before("")  # placeholder
    # placeholder 를 anchor 뒤로 이동
    anchor_elem = anchor_para._p
    new_elem = new_p._p
    anchor_elem.addnext(new_elem)
    # 텍스트·스타일 설정
    if text:
        run = new_p.add_run(text)
    try:
        new_p.style = doc.styles[style_name]
    except KeyError:
        pass
    return new_p


def insert_block_after(doc, anchor_para, blocks: list[tuple[str, str]]):
    """anchor_para 뒤에 (style_name, text) 리스트를 순서대로 삽입.

    style_name 예: 'Heading 3' / 'Normal'.
    """
    current = anchor_para
    for style, text in blocks:
        current = _insert_after(doc, current, style, text)
    return current


def _last_para_of_section(doc, section_heading_text_prefix: str) -> int:
    """특정 헤딩 시작 후 다음 동급/상위 헤딩 직전 단락 인덱스."""
    start = _find_heading_index(doc, section_heading_text_prefix)
    if start < 0:
        return -1
    start_p = doc.paragraphs[start]
    start_style = start_p.style.name  # 예: 'Heading 2'
    # 동급/상위 = 같은 숫자 또는 더 큰 숫자
    try:
        start_level = int(start_style.replace("Heading ", ""))
    except (ValueError, AttributeError):
        return start
    # 그 뒤 단락 순회 — 동급 이상 헤딩 만나면 그 직전 인덱스
    for i in range(start + 1, len(doc.paragraphs)):
        st = doc.paragraphs[i].style.name or ""
        if st.startswith("Heading"):
            try:
                lvl = int(st.replace("Heading ", ""))
                if lvl <= start_level:
                    return i - 1
            except ValueError:
                continue
    return len(doc.paragraphs) - 1


def main() -> None:
    if not CONTEST_DOCX.exists():
        print(f"❌ 파일 없음: {CONTEST_DOCX}")
        return

    print(f"열기: {CONTEST_DOCX}")
    doc = Document(str(CONTEST_DOCX))
    print(f"   현재 단락 수: {len(doc.paragraphs)}, 표: {len(doc.tables)}\n")

    # ─── 1. § 1.2.1 V-1 본문 끝에 Step 4 시드 UI 단락 추가 ───
    # 1.2.1 다음 동급 헤딩 (1.2.2) 직전에 삽입
    idx_122 = _find_heading_index(doc, "1.2.2")
    if idx_122 > 0:
        anchor = doc.paragraphs[idx_122 - 1]
        insert_block_after(doc, anchor, [
            ("Normal", (
                "V-1 Step 4 정밀 가이드 화면은 사고유형 + CSP 기준으로 매칭되는 시드 카탈로그를 "
                "별도 패널로 노출한다. 각 시드 카드는 target_id(예: CT-NCP-IAM-001), 로그 유형, "
                "REQUIRED·CORROBORATING 역할, 우선순위와 함께 수집 가이드 hint(콘솔 메뉴 경로), "
                "자동 수집을 위한 CLI 명령(복사 가능), 연관 MITRE ATT&CK 기법 칩(예: T1078.004, T1110), "
                "원본 storage_path 까지 한 화면에서 보여준다. 수사관은 '어떤 로그를, 어디서, 어떻게 "
                "수집할지'를 별도 문서 참조 없이 즉시 확인할 수 있다."
            )),
        ])
        print("✓ 1단계: § 1.2.1 V-1 본문 끝에 Step 4 시드 UI 단락 추가")
    else:
        print("⚠ § 1.2.2 헤딩을 찾지 못함 — 1단계 skip")

    # ─── 2. § 6.3 끝에 6.3.4 recommend_playbook RAG+LLM ───
    # 6.3 의 마지막 부분(현재 6.3.3 KB 임베딩) 뒤에 추가.
    # 다음 동급(6.4) 직전 위치 찾기
    idx_64 = _find_heading_index(doc, "6.4")
    if idx_64 > 0:
        anchor = doc.paragraphs[idx_64 - 1]
        insert_block_after(doc, anchor, [
            ("Heading 3", "6.3.4 recommend_playbook — RAG 검색과 LLM 맥락화의 결합"),
            ("Normal", (
                "AI 셰르파의 플레이북 추천 기능은 두 단계로 구성된다. 1단계는 결정성 100%의 RAG 검색 — "
                "사용자가 식별한 ATT&CK 기법 chain (예: T1078.004 → T1098 → T1537) 을 검색어로 "
                "PLAYBOOK 카테고리 KB 청크를 cosine similarity 기준으로 상위 3건 반환한다. "
                "각 청크는 KB 원문 그대로 playbooks 배열에 포함되어 사용자가 출처를 직접 확인 가능하다."
            )),
            ("Normal", (
                "2단계는 LLM 맥락화 요약 — 1단계의 KB 청크만 컨텍스트로 LLMEngine.generate() 를 호출하여 "
                "현재 attack chain 에 맞게 우선순위·핵심 3 단계·각 단계의 목적을 정리해 summary 필드로 "
                "반환한다. LLM 응답은 출처 [N] 자동 인용 + '최종 판단은 수사관께서 직접 수행해 주세요' "
                "문구가 자동 부착되어 환각 위험을 줄이고 책임 소재를 명확히 한다. Ollama 미연결 등 "
                "LLM 호출 실패 시 summary=None 으로 graceful degrade — 결정성 영역(playbooks)은 "
                "항상 보장된다."
            )),
            ("Normal", (
                "본 구조는 결정성 영역(playbooks)과 보조 LLM 영역(summary)을 명확히 분리해, '결정은 "
                "정적 규칙, AI 는 정렬·요약만'이라는 본 시스템의 핵심 원칙을 유지한다."
            )),
        ])
        print("✓ 2단계: § 6.3.4 recommend_playbook RAG+LLM 결합 절 추가")
    else:
        print("⚠ § 6.4 헤딩을 찾지 못함 — 2단계 skip")

    # ─── 3·4. § 6.4 끝에 6.4.6 (데이터 사이클) + 6.4.7 (pytest+CI) 추가 ───
    # 7장 헤딩 직전에 삽입
    idx_7 = _find_heading_index(doc, "7.")
    if idx_7 > 0:
        anchor = doc.paragraphs[idx_7 - 1]
        insert_block_after(doc, anchor, [
            ("Heading 3", "6.4.6 데이터 사이클 보강 — 9 사고유형 풀세트 + 시드 풍부화"),
            ("Normal", (
                "초기 5 사고유형 (CREDENTIAL_THEFT / PRIVILEGE_ESCALATION / DATA_EXFILTRATION / "
                "AUDIT_LOG_TAMPERING / MULTI_CSP_LATERAL) 에서 dev3 C-1 단계로 4 종 (RANSOMWARE, "
                "MISCONFIG_EXPOSURE, PHISH_INITIAL_ACCESS, INSIDER_THREAT) 을 추가해 8 사고유형 + "
                "UNCLASSIFIED = 9 종 enum 으로 확장하였다. 매트릭스의 모든 16 셀(8 사고유형 × 2 CSP) "
                "에서 시드 / 매처 / attack_rules / 합성 로그의 4 영역이 모두 충족되도록 단계적으로 "
                "보강하였다."
            )),
            ("Normal", (
                "scripts/data_gap_audit.py 진단 도구는 5 영역(collection_targets / matchers / "
                "attack_rules / KB / synthetic) 매트릭스를 출력하고 P0/P1 갭을 자동 분류한다. "
                "초기 P0 8 건(신규 4 종 × 2 CSP)이 모두 해소되어 최종 P0/P1 = 0/0 을 달성하였다. "
                "scripts/enrich_collection_seeds.py 는 휴리스틱 매핑으로 61/61 시드 row 에 "
                "layer / hint / cmd / cmd_path / auto_collectible / mitre_techniques 등 6 신규 "
                "필드를 일괄 추가하였다."
            )),
            ("Normal", (
                "최종 매트릭스 — 시드 77 행 (10 필드 포함), 매처 16/16, attack_rules 74 룰 "
                "(NCP 39 / NHN 35, 19 기법 커버), 합성 로그 16 시나리오 (사실기반 Sysdig 2024 "
                "8-min Killchain · Capital One 2019 S3 유출 포함), KB 130 청크. 8 사고유형 × 2 CSP "
                "풀 회귀 매처 매칭률 누적 92.2% (16/16 시나리오 ≥ 75%)."
            )),

            ("Heading 3", "6.4.7 pytest 회귀 시험 + GitHub Actions CI + pre-commit hook"),
            ("Normal", (
                "사이클 보강 작업의 결과가 추후 회귀로 깨지지 않도록 backend/tests/ 디렉토리에 5 모듈 "
                "129 케이스의 자동 시험을 구축하였다. test_matchers.py 는 16 매처 등록 + 시나리오별 "
                "매칭률, test_seeds.py 는 16 시드 무결성 + 풍부화 필드, test_attack_rules.py 는 "
                "74 룰의 정규식 컴파일 + 9 사고유형 기대 기법 커버리지, test_collection_guide_v2.py "
                "는 Phase G completion_rate 헬퍼와 seed_targets 로더, test_data_gap.py 는 P0/P1 = "
                "0 유지를 보장한다."
            )),
            ("Normal", (
                ".github/workflows/backend-tests.yml 워크플로우는 dev3 / main / 작업 브랜치 push 와 "
                "PR 시 자동 실행되어 Python 3.13 / Ubuntu 환경에서 129 케이스를 모두 통과시킨다. "
                "heavy AI 의존성(chromadb / sentence-transformers / Ollama)을 설치하지 않더라도 "
                "RAGRetriever 의 키워드 fallback 과 LLMEngine 의 stub 응답으로 동일한 시험이 통과되어, "
                "오프라인 환경 검증과 CI 환경 안정성을 동시에 보장한다."
            )),
            ("Normal", (
                ".githooks/pre-commit hook 은 로컬 커밋 시점에 Python AST / JSON 유효성 / TypeScript "
                "tsc --noEmit 검사에 더해 backend/{core,api,data,tests} 변경 시 pytest 회귀를 -x 옵션 "
                "(첫 실패 즉시 종료) 으로 실행한다. 흔한 회귀 패턴 (rule_id 중복, 시드 필드 누락, "
                "매처 매칭률 하락) 이 커밋 단계에서 즉시 차단된다. 활성화는 'bash scripts/setup-hooks.sh' "
                "1 회 실행으로 완료된다."
            )),
        ])
        print("✓ 3·4단계: § 6.4.6 데이터 사이클 + 6.4.7 pytest/CI 절 추가")
    else:
        print("⚠ § 7 헤딩을 찾지 못함 — 3·4단계 skip")

    # ─── 5. § 8 끝에 8.6 pytest 회귀 시험 추가 ───
    idx_9 = _find_heading_index(doc, "9.")
    if idx_9 > 0:
        anchor = doc.paragraphs[idx_9 - 1]
        insert_block_after(doc, anchor, [
            ("Heading 2", "8.6 pytest 자동 회귀 시험 (5 모듈 129 케이스)"),
            ("Normal", (
                "backend/tests/ 디렉토리에 구축한 자동 시험은 사이클 보강 작업의 결과를 회귀로부터 "
                "보호한다. 시험 모듈 5 종 — test_matchers.py(19), test_seeds.py(24), "
                "test_attack_rules.py(10), test_collection_guide_v2.py(38), test_data_gap.py(6), "
                "test_recommend_playbook.py(5) 및 통합 케이스로 총 129 케이스가 등록되었으며, 모든 "
                "케이스가 성공한다 (129 / 129 passed)."
            )),
            ("Normal", (
                "각 모듈은 독립적 결정성 단위 시험으로 설계되어 DB / 외부 서비스 의존성 없이 빠르게 "
                "실행되며, 합성 로그를 직접 파싱·매칭하여 실 운영 시나리오와 동일한 검증을 수행한다. "
                "특히 test_data_gap.py 는 9 사고유형 × 2 CSP 매트릭스의 4 영역 (시드 / 매처 / 룰 / "
                "합성) 충족 여부를 자동 점검해 신규 사고유형 추가 시 누락 영역을 즉시 잡아낸다."
            )),
            ("Normal", (
                "본 시험은 .github/workflows/backend-tests.yml GitHub Actions 워크플로우와 "
                ".githooks/pre-commit 로컬 hook 양쪽에서 자동 실행되어 로컬·원격 양 측 회귀 차단을 "
                "보장한다. CI 환경에서는 heavy AI 의존성 없이도 RAG / LLM fallback 으로 동일한 "
                "129 케이스가 통과된다."
            )),
        ])
        print("✓ 5단계: § 8.6 pytest 회귀 시험 절 추가")
    else:
        print("⚠ § 9 헤딩을 찾지 못함 — 5단계 skip")

    # 저장 — 원본 덮어쓰기 (git 으로 백업 보존)
    doc.save(str(CONTEST_DOCX))
    print(f"\n✅ 저장 완료: {CONTEST_DOCX}")
    print(f"   변경 후 단락 수: {len(doc.paragraphs)}")


if __name__ == "__main__":
    main()
