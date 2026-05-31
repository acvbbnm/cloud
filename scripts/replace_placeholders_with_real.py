"""back2 (1).docx 의 placeholder 이미지를 진짜 캡처로 강제 교체.

back2 에는 같은 placeholder 이미지 (rId15, rId19 등) 가 33 캡션 위에
반복 참조되어 있음. 이를 우리 capture_NN.png 로 교체.

방식:
  1. 각 캡션 위 단락 찾기
  2. 단락의 모든 run 비움
  3. 새 run 에 add_picture(width=15cm)
  4. 캡처 파일 없으면 (25/29/31) 단락 자체를 빈 채로 두고 캡션은 검정 유지
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Cm, RGBColor
from docx.oxml.ns import qn

sys.stdout.reconfigure(encoding="utf-8")

SRC = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_v3.docx"
)
OUT = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_v4.docx"
)
CAPTURE_DIR = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\캡처"
)

# jingyu UI 자동 매핑 11장 — 검정 유지 (사용자가 빨강 지움)
AUTO_INSERTED: set[int] = set()
# 사용자가 직접 캡처한 20장 — 초록 (UI 7 + CODE 13)
USER_DONE = {2, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 16, 20, 21, 22, 25, 26, 27, 32, 33}
# 캡처 대기 2장 — 검정
USER_TODO = {29, 31}

RED   = RGBColor(0xC0, 0x00, 0x00)
GREEN = RGBColor(0x00, 0x80, 0x00)
BLACK = RGBColor(0, 0, 0)


def clear_paragraph_runs(p) -> None:
    """단락의 모든 run + drawing 요소 제거 (텍스트·이미지 다 비움)."""
    # 모든 자식 요소 제거 (단락 properties pPr 는 보존)
    for child in list(p._p):
        if child.tag != qn("w:pPr"):
            p._p.remove(child)


def main() -> None:
    doc = Document(str(SRC))
    print(f"베이스 열기: 단락 {len(doc.paragraphs)} / 표 {len(doc.tables)}\n")

    n_replaced = 0
    n_kept_empty = 0

    # 캡션 단락 인덱스 + 그림 번호 매핑 (단락 삭제·추가 없으므로 인덱스 변동 없음)
    cap_positions: list[tuple[int, int]] = []
    for i, p in enumerate(doc.paragraphs):
        m = re.match(r"^<그림\s*(\d+)\b", p.text.strip())
        if m:
            cap_positions.append((i, int(m.group(1))))

    print(f"━━ Placeholder 33 곳을 진짜 캡처로 교체 ━━")
    for idx, num in cap_positions:
        png = CAPTURE_DIR / f"capture_{num:02d}.png"
        if idx == 0:
            print(f"  ✗ [그림 {num:2d}] 캡션이 첫 단락 — 스킵")
            continue
        prev_para = doc.paragraphs[idx - 1]

        if not png.exists():
            # 캡처 없음 → placeholder 비우고 빈 자리로 둠
            clear_paragraph_runs(prev_para)
            print(f"  · [그림 {num:2d}] 캡처 없음 → 빈 자리 (placeholder 제거)")
            n_kept_empty += 1
            continue

        # placeholder 단락 비우고 새 이미지 삽입
        clear_paragraph_runs(prev_para)
        prev_para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        run = prev_para.add_run()
        run.add_picture(str(png), width=Cm(15))
        print(f"  ✓ [그림 {num:2d}] capture_{num:02d}.png 교체 완료")
        n_replaced += 1

    print()
    print(f"━━ 3색 캡션 마킹 ━━")
    n_red = n_green = n_black = 0
    for p in doc.paragraphs:
        m = re.match(r"^<그림\s*(\d+)\b", p.text.strip())
        if not m:
            continue
        num = int(m.group(1))
        if num in AUTO_INSERTED:
            for r in p.runs:
                r.font.color.rgb = RED
            n_red += 1
        elif num in USER_DONE:
            for r in p.runs:
                r.font.color.rgb = GREEN
            n_green += 1
        elif num in USER_TODO:
            for r in p.runs:
                r.font.color.rgb = BLACK
            n_black += 1

    doc.save(str(OUT))
    print()
    print(f"✅ 저장: {OUT.name}")
    print()
    print(f"  ━━ 이미지 ━━")
    print(f"  ✓ 진짜 캡처로 교체: {n_replaced} 장")
    print(f"  · 빈 자리 유지:    {n_kept_empty} 장 (25/29/31)")
    print()
    print(f"  ━━ 캡션 색상 ━━")
    print(f"  🔴 빨강 (자동): {n_red} 장")
    print(f"  🟢 초록 (사용자): {n_green} 장")
    print(f"  ⚫ 검정 (대기): {n_black} 장")


if __name__ == "__main__":
    main()
