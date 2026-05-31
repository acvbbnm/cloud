"""공통_시험서_시나리오_제한사항.docx 의 시나리오 표 9 개 시험 절차를
미술관 보고서 패턴 (3 단계 간결) 으로 단축.

미술관 예시 (<표 31> 파일 업로드 및 이미지 모니터링 실행):
    1. 이미지 모니터링 페이지 접속
    2. 파일 업로드 및 이미지 모니터링 실행
    3. 이미지 모니터링 결과값 출력

현재: 7 단계 / 280~460자 → 단축 후: 3 단계 / 60~100자.

대상 셀: 시험 절차 셀 (r3c2 ~ 마지막 행 c2, 병합되어 같은 값).
"""
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt

sys.stdout.reconfigure(encoding="utf-8")

DOCX = Path(r"C:\Users\User\Downloads\공통_시험서_시나리오_제한사항.docx")
OUT = Path(r"C:\Users\User\Downloads\공통_시험서_시나리오_제한사항_간결.docx")

# 9 개 시나리오 표 (표 4 ~ 12) 의 새 시험 절차 — 3 단계 간결
NEW_PROCEDURES: list[tuple[int, str, list[str]]] = [
    (4, "사고 케이스 접수 5단계 위저드 (UC-01)", [
        "V-1 Setup 진입 후 5단계 위저드 입력 완료",
        "POST /api/cases 호출 → case_id 발급",
        "incident_cases INSERT 확인",
    ]),
    (5, "Evidence Tree 단서 트리 추적 (UC-01 확장)", [
        "UNCLASSIFIED 진입 후 단서 채택",
        "Bayesian Network 사후확률 갱신 + IG 후보 추천",
        "임계 도달 시 사고유형 확정",
    ]),
    (6, "로그 업로드 및 무결성 검증 (UC-02)", [
        "V-2 DropZone 에 NCP/NHN 로그 업로드",
        "SHA-256 해시 계산 + raw_events INSERT",
        "KPI 4종 및 매칭 분포 갱신 확인",
    ]),
    (7, "OCSF 정규화 + ATT&CK 매핑 (UC-03)", [
        "V-3 OCSF 정규화 실행 → ocsf_events INSERT",
        "V-6 Attack 매핑 실행 → attack_events INSERT",
        "KPI 3종 및 매핑 결과 확인",
    ]),
    (8, "갭 감지 + Layer 0 복귀 (UC-04)", [
        "V-4 갭 감지 실행 → gap_results INSERT",
        "4종 갭 분류 결과 확인",
        "갭 발생 시 Layer 0 복귀 또는 다음 단계 진행",
    ]),
    (9, "AI 셰르파 자연어 Q&A (UC-05+07)", [
        "V-8 Sherpa 진입 후 자연어 질의 입력",
        "RAG 검색 + sLLM 응답 + 인용 청크 노출",
        "KB 외 ATT&CK 기법 ID 자동 unsourced 라벨 확인",
    ]),
    (10, "수사 보드 빠진 고리 제안 + 체인 구성 (UC-06)", [
        "V-5 Board 진입 후 attack_events 노드 드래그",
        "빠진 고리 후보 제안 + 노드 수락",
        "AI 브리핑 및 chain_nodes 갱신 확인",
    ]),
    (11, "보고서 자동 생성 + 내보내기 (UC-08)", [
        "V-7 Report 진입 후 [보고서 생성] 클릭 → 8섹션 초안",
        "인라인 편집 후 [최종화] 클릭",
        "DOCX 또는 PDF 내보내기 실행",
    ]),
    (12, "통합 시나리오 CASE 1·2 E2E 측정", [
        "CASE 1 (해외 IP 권한 탈취) V-1 → V-7 전체 순회 측정",
        "CASE 2 (내부자 데이터 유출) V-1 → V-7 전체 순회 측정",
        "action_logs 작업 이력 카운트 검증",
    ]),
]


def set_cell_text(cell, lines: list[str]) -> None:
    """셀의 모든 단락 삭제 후 새 줄 추가."""
    # 첫 단락 재사용 + 나머지 단락 비우기
    paras = list(cell.paragraphs)
    if paras:
        # 첫 단락 텍스트 초기화
        p = paras[0]
        for r in list(p.runs):
            r.text = ""
        # 첫 줄
        run = p.add_run(f"1. {lines[0]}")
        run.font.size = Pt(10)
        # 나머지 단락 비우기 (병합셀 텍스트 영향 최소화)
        for extra in paras[1:]:
            for r in list(extra.runs):
                r.text = ""
        # 나머지 줄은 새 단락으로 추가
        for i, line in enumerate(lines[1:], 2):
            new_p = cell.add_paragraph()
            r = new_p.add_run(f"{i}. {line}")
            r.font.size = Pt(10)


def main() -> None:
    doc = Document(str(DOCX))
    print(f"열기: 단락 {len(doc.paragraphs)} / 표 {len(doc.tables)}\n")
    changed = 0

    for table_idx, label, lines in NEW_PROCEDURES:
        if table_idx > len(doc.tables):
            print(f"  ✗ 표 {table_idx} 없음")
            continue
        t = doc.tables[table_idx - 1]
        # 시험 절차 셀은 r=3 (4번째 행) 부터 마지막 행까지의 c=2 (3번째 칸)
        # 셀이 병합되어 있으므로 r3c2 만 갱신해도 모든 행에 반영됨
        cell = t.rows[3].cells[2]
        before_len = len(cell.text.strip())
        set_cell_text(cell, lines)
        after_len = sum(len(line) for line in lines) + len(lines) * 3
        print(f"  ✓ 표 {table_idx} ({label})")
        print(f"     {before_len} ch → {after_len} ch")
        changed += 1

    doc.save(str(OUT))
    print(f"\n✅ 저장: {OUT.name}")
    print(f"   {changed} 개 표 시험 절차 단축 완료")


if __name__ == "__main__":
    main()
