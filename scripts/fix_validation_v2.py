"""정리완성.docx 검증 결함 자동 수정.

1. CLAUDE.md → AGENTS.md 일괄 치환 (본문 + 표 셀)
2. 시나리오 표 번호 fix: <표 Ⅶ-1>~<표 Ⅶ-9> (시나리오) → <표 Ⅶ-4>~<표 Ⅶ-12>
   (시험서 <표 Ⅶ-1>~<표 Ⅶ-3>과 충돌 해결)
3. 진실값 본문 보강 (진실 수치 누락 1~2 곳 추가)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt

sys.stdout.reconfigure(encoding="utf-8")

DOCX = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_정리완성.docx"
)
OUT = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_정리완성_v2.docx"
)


def replace_in_paragraph(p, old: str, new: str) -> bool:
    """단락 내 모든 run 에서 치환. run 경계 가로지름도 처리."""
    full = p.text
    if old not in full:
        return False
    for run in p.runs:
        if old in run.text:
            run.text = run.text.replace(old, new)
            return True
    # run 경계 가로지름 — 첫 run 에 통합
    new_full = full.replace(old, new)
    if p.runs:
        p.runs[0].text = new_full
        for r in p.runs[1:]:
            r.text = ""
        return True
    return False


def replace_in_cell(cell, old: str, new: str) -> bool:
    changed = False
    for p in cell.paragraphs:
        if replace_in_paragraph(p, old, new):
            changed = True
    return changed


def replace_global(doc, old: str, new: str) -> int:
    cnt = 0
    for p in doc.paragraphs:
        if replace_in_paragraph(p, old, new):
            cnt += 1
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                if replace_in_cell(cell, old, new):
                    cnt += 1
    return cnt


def renumber_scenario_tables(doc) -> int:
    """<표 Ⅶ-N> 시리즈 중 시나리오 9 개를 Ⅶ-4 ~ Ⅶ-12 로 재번호.

    전략: 등장 순서로 추적
      - 첫 3 개 등장 = 시험서 (Ⅶ-1, Ⅶ-2, Ⅶ-3) → 유지
      - 이후 9 개 = 시나리오 (Ⅶ-1 ~ Ⅶ-9) → 각각 +3 ⇒ Ⅶ-4 ~ Ⅶ-12

    구현: paragraph 텍스트만 처리 (시나리오 표 캡션은 paragraph 단락임).
      seen counter 로 같은 라벨이 N 번째 등장인지 추적.
    """
    # 1차 패스: 모든 <표 Ⅶ-N> 등장 위치 + 라벨 수집
    pattern = re.compile(r"<표\s*Ⅶ-(\d+)>")
    seen_count: dict[int, int] = {}  # 원본 번호 → 등장 횟수
    positions = []  # (paragraph_idx, run_idx 안 함, 원본 N, occurrence)
    for p_idx, p in enumerate(doc.paragraphs):
        for m in pattern.finditer(p.text):
            n = int(m.group(1))
            seen_count[n] = seen_count.get(n, 0) + 1
            positions.append((p_idx, n, seen_count[n]))

    # 2차 패스: 시나리오 (occurrence ≥ 2 인 경우만) 만 +3
    # 시험서는 occurrence == 1 (첫 등장), 시나리오는 occurrence == 2
    # 단 Ⅶ-1, Ⅶ-2, Ⅶ-3 만 시험서 후보 — 시나리오 Ⅶ-4~9 는 occurrence 1 이지만 시나리오임
    # 정확한 구분: paragraph 위치 기준 — 시험서 표 3 개는 가장 앞쪽 위치
    # 시나리오 표 캡션의 paragraph 인덱스는 시험서 캡션 뒤에 위치

    # 시험서 캡션 3 개의 paragraph 인덱스 추출 (Ⅶ-1, Ⅶ-2, Ⅶ-3 의 첫 등장)
    scenario_first_idx = None
    test_caption_idx = []
    for p_idx, n, occ in positions:
        if n in (1, 2, 3) and occ == 1:
            test_caption_idx.append(p_idx)
        else:
            if scenario_first_idx is None or p_idx < scenario_first_idx:
                scenario_first_idx = p_idx

    if scenario_first_idx is None:
        # 시나리오 표가 모두 occurrence 1 (Ⅶ-4~Ⅶ-9 미사용 케이스)
        # 그러면 Ⅶ-1, Ⅶ-2, Ⅶ-3 의 occurrence 2 가 시나리오
        scenario_first_idx = min(
            (p_idx for p_idx, n, occ in positions if n in (1, 2, 3) and occ == 2),
            default=None,
        )

    if scenario_first_idx is None:
        print("  · 시나리오 표 위치 식별 실패 — 스킵")
        return 0

    # 시나리오 캡션 paragraph 들의 번호를 +3
    # 시나리오의 Ⅶ-1 (occ 2) → Ⅶ-4, Ⅶ-2 (occ 2) → Ⅶ-5, ..., Ⅶ-9 (occ 1) → Ⅶ-12
    changed = 0
    # 큰 수부터 처리 (치환 충돌 방지) — 9 → 12, 8 → 11, ..., 1 → 4
    # 단 시나리오 라벨만 — paragraph 인덱스가 scenario_first_idx 이상이어야 함

    # 단락 인덱스 → 새 라벨 매핑 사전 빌드
    new_label_map: dict[int, dict[str, str]] = {}  # p_idx → {old: new}
    for p_idx, n, occ in positions:
        if p_idx < scenario_first_idx:
            continue
        old_label = f"<표 Ⅶ-{n}>"
        new_label = f"<표 Ⅶ-{n + 3}>"
        new_label_map.setdefault(p_idx, {})[old_label] = new_label

    # 실제 치환 — 큰 수부터 (Ⅶ-9 → Ⅶ-12 먼저, Ⅶ-1 → Ⅶ-4 마지막)
    for n in range(9, 0, -1):
        old_label = f"<표 Ⅶ-{n}>"
        new_label = f"<표 Ⅶ-{n + 3}>"
        for p_idx, mapping in new_label_map.items():
            if old_label in mapping:
                p = doc.paragraphs[p_idx]
                if replace_in_paragraph(p, old_label, new_label):
                    changed += 1
                    print(f"  ✓ [p{p_idx:3d}] {old_label} → {new_label}")

    return changed


def append_truth_paragraph(doc, anchor_prefix: str, body: str) -> bool:
    """anchor_prefix 로 시작하는 H1/H2 헤딩 찾아 그 다음 빈 단락에 진실값 추가."""
    for i, p in enumerate(doc.paragraphs):
        st = p.style.name if p.style else ""
        if not st.startswith("Heading"):
            continue
        if p.text.strip().startswith(anchor_prefix):
            # 헤딩 다음 단락에 새 단락 추가 (헤딩 직후 위치)
            if i + 1 < len(doc.paragraphs):
                next_p = doc.paragraphs[i + 1]
                new_p = next_p.insert_paragraph_before("")
                run = new_p.add_run(body)
                run.font.size = Pt(10)
                return True
    return False


def main() -> None:
    doc = Document(str(DOCX))
    print(f"열기: 단락 {len(doc.paragraphs)} / 표 {len(doc.tables)}\n")

    # 1. CLAUDE.md → AGENTS.md
    print("━━ 1) CLAUDE.md → AGENTS.md ━━")
    n = replace_global(doc, "CLAUDE.md", "AGENTS.md")
    print(f"  ✓ {n} 곳 치환\n")

    # 2. 시나리오 표 번호 +3
    print("━━ 2) 시나리오 표 번호 충돌 fix (Ⅶ-1~9 → Ⅶ-4~12) ━━")
    n = renumber_scenario_tables(doc)
    print(f"  ✓ {n} 캡션 번호 갱신\n")

    # 3. 진실값 보강 — 3 곳
    print("━━ 3) 진실값 본문 보강 ━━")

    truth_lines = [
        # (앵커 헤딩 prefix, 추가 단락)
        ("6.", "본 단원의 핵심 수치 — collection_targets 시드 16 파일 / 77 행 (사고유형 9 종 × CSP 2 개 매트릭스), 매처 16 종 (NCP 8 + NHN 8) 사이클 6 누적 매칭률 92.2%, ATT&CK 매핑 룰 74 룰 (NCP 39 + NHN 35) — 30 distinct 기법 커버, KB 130 청크 (ATTACK 38 + PLAYBOOK 25 + CSP_DOC 22 + CASE_DB 45)."),
        ("8.", "본 단원의 자동 회귀 시험 — backend/tests/ 에 5 모듈 129 케이스 (parametrize 펼침 기준): test_matchers (19) / test_seeds (24) / test_attack_rules (10) / test_collection_guide_v2 (38) / test_data_gap (6) / test_recommend_playbook. GitHub Actions CI + 로컬 pre-commit hook 이중화로 매 PR 마다 자동 실행."),
    ]
    for anchor, body in truth_lines:
        if append_truth_paragraph(doc, anchor, body):
            print(f"  ✓ § {anchor}* 진실값 단락 추가")
        else:
            print(f"  ✗ § {anchor}* 헤딩 미발견")
    print()

    doc.save(str(OUT))
    print(f"✅ 저장: {OUT.name}")


if __name__ == "__main__":
    main()
