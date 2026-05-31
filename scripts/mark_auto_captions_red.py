"""자동 삽입된 24 장 캡처의 캡션 텍스트를 빨간 글씨로 표시.

빨강: 자동 채워진 이미지 (jingyu captures 11 + Pillow 코드 렌더링 13 = 24장)
검정 유지: 사용자가 직접 캡처할 9 장 (2, 4, 5, 8, 9, 14, 25, 29, 31)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.shared import RGBColor

sys.stdout.reconfigure(encoding="utf-8")

DOCX = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_캡처완성.docx"
)
OUT = DOCX  # 같은 파일 덮어쓰기

AUTO_INSERTED = {1, 3, 6, 7, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20, 21,
                 22, 23, 24, 26, 27, 28, 30, 32, 33}
USER_DONE = {2, 4, 5, 8, 9, 14}      # 사용자 직접 캡처 완료
USER_TODO = {25, 29, 31}             # 아직 캡처 대기

RED   = RGBColor(0xC0, 0x00, 0x00)   # 자동
GREEN = RGBColor(0x00, 0x80, 0x00)   # 사용자 직접


def main() -> None:
    doc = Document(str(DOCX))
    print(f"열기: 단락 {len(doc.paragraphs)}\n")
    n_red = n_green = n_black = 0

    for p in doc.paragraphs:
        txt = p.text.strip()
        m = re.match(r"^<그림\s*(\d+)\b", txt)
        if not m:
            continue
        num = int(m.group(1))
        if num in AUTO_INSERTED:
            for r in p.runs:
                r.font.color.rgb = RED
            n_red += 1
            print(f"  🔴 [그림 {num:2d}] 빨강 (자동): {txt[:55]}")
        elif num in USER_DONE:
            for r in p.runs:
                r.font.color.rgb = GREEN
            n_green += 1
            print(f"  🟢 [그림 {num:2d}] 초록 (사용자): {txt[:55]}")
        elif num in USER_TODO:
            # 검정 명시적 적용 (이전 색 잔존 제거)
            for r in p.runs:
                r.font.color.rgb = RGBColor(0, 0, 0)
            n_black += 1
            print(f"  ⚫ [그림 {num:2d}] 검정 (캡처 대기): {txt[:55]}")

    doc.save(str(OUT))
    print(f"\n✅ 저장: {OUT.name}")
    print(f"   🔴 빨강 (자동 삽입): {n_red} 장")
    print(f"   🟢 초록 (사용자 직접): {n_green} 장")
    print(f"   ⚫ 검정 (캡처 대기):   {n_black} 장")


if __name__ == "__main__":
    main()
