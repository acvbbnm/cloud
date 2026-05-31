"""back2 (1).docx 베이스로 30장 캡처 삽입 + 3색 캡션 마킹.

기존 이미지 위치는 보존하고, 그림 캡션 위에만 이미지를 추가.
같은 캡션 위에 이미 이미지가 있어도 중복 삽입은 하지 않음.
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

SRC = Path(r"C:\Users\User\Downloads\최종_AI_Sherpa_보고서_back2 (1).docx")
OUT = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_back2_캡처반영.docx"
)
CAPTURE_DIR = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\캡처"
)

AUTO_INSERTED = {1, 3, 6, 7, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20, 21,
                 22, 23, 24, 26, 27, 28, 30, 32, 33}
USER_DONE = {2, 4, 5, 8, 9, 14}
USER_TODO = {25, 29, 31}

RED   = RGBColor(0xC0, 0x00, 0x00)
GREEN = RGBColor(0x00, 0x80, 0x00)
BLACK = RGBColor(0, 0, 0)


def has_image_before(doc, caption_para_idx: int) -> bool:
    """캡션 단락 바로 위 단락에 이미지(drawing) 가 있는지."""
    if caption_para_idx == 0:
        return False
    prev = doc.paragraphs[caption_para_idx - 1]
    # w:drawing 요소가 있으면 이미지
    return prev._p.find(".//" + qn("w:drawing")) is not None


def main() -> None:
    doc = Document(str(SRC))
    print(f"베이스 열기: 단락 {len(doc.paragraphs)} / 표 {len(doc.tables)}\n")

    n_inserted = 0
    n_skipped_dup = 0
    n_missing_png = 0

    # 캡션 단락 인덱스 + 그림 번호 매핑
    cap_positions: list[tuple[int, int]] = []  # (paragraph_idx, num)
    for i, p in enumerate(doc.paragraphs):
        m = re.match(r"^<그림\s*(\d+)\b", p.text.strip())
        if m:
            cap_positions.append((i, int(m.group(1))))

    print(f"━━ 캡션 33 개 처리 ━━")
    for idx, num in cap_positions:
        png = CAPTURE_DIR / f"capture_{num:02d}.png"
        if not png.exists():
            print(f"  · [그림 {num:2d}] 캡처 파일 없음 → 빈 자리 유지")
            n_missing_png += 1
            continue
        # 이미 위에 이미지가 있으면 스킵
        if has_image_before(doc, idx):
            print(f"  - [그림 {num:2d}] 이미 이미지 있음 → 중복 삽입 안함")
            n_skipped_dup += 1
            continue
        # 캡션 위에 이미지 단락 삽입
        cap_para = doc.paragraphs[idx]
        new_p = cap_para.insert_paragraph_before("")
        new_p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        run = new_p.add_run()
        run.add_picture(str(png), width=Cm(15))
        print(f"  ✓ [그림 {num:2d}] 이미지 삽입: capture_{num:02d}.png")
        n_inserted += 1

    print()
    print(f"━━ 3색 캡션 마킹 ━━")
    # 캡션 단락 위치 다시 찾기 (단락 인덱스 변동됨)
    n_red = n_green = n_black = 0
    for p in doc.paragraphs:
        m = re.match(r"^<그림\s*(\d+)\b", p.text.strip())
        if not m:
            continue
        num = int(m.group(1))
        if num in AUTO_INSERTED:
            color, label, cnt = RED, "🔴 빨강", "n_red"
            n_red += 1
        elif num in USER_DONE:
            color, label, cnt = GREEN, "🟢 초록", "n_green"
            n_green += 1
        elif num in USER_TODO:
            color, label, cnt = BLACK, "⚫ 검정", "n_black"
            n_black += 1
        else:
            continue
        for r in p.runs:
            r.font.color.rgb = color

    doc.save(str(OUT))
    print()
    print(f"✅ 저장: {OUT.name}")
    print()
    print(f"  ━━ 이미지 ━━")
    print(f"  ✓ 신규 삽입: {n_inserted} 장")
    print(f"  - 중복 스킵: {n_skipped_dup} 장 (이미 있음)")
    print(f"  · 캡처 없음: {n_missing_png} 장")
    print()
    print(f"  ━━ 캡션 색상 ━━")
    print(f"  🔴 빨강 (자동): {n_red} 장")
    print(f"  🟢 초록 (사용자): {n_green} 장")
    print(f"  ⚫ 검정 (대기): {n_black} 장")


if __name__ == "__main__":
    main()
