"""jingyu v2 (Ⅸ.구현) + 공통_간결 (Ⅶ.시험서 + Ⅷ.제한사항) → 단일 보고서.

미술관 보고서 챕터 순서 그대로:
  Ⅶ. 시험서 및 시험 시나리오  ← 공통_간결.docx
  Ⅷ. 현실적 제한사항            ← 공통_간결.docx
  Ⅸ. 구현                        ← jingyu v2 (표지·목차 제외하고 본문만)

베이스: 공통_간결.docx (표지 보유)
추가: jingyu v2 의 p17 (Ⅸ. 구현 H1) 부터 끝까지
"""
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_BREAK
from docx.oxml.ns import qn
from docxcompose.composer import Composer

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"C:\Users\User\Downloads\공통_시험서_시나리오_제한사항_수정.docx")
ADD = Path(r"C:\Users\User\Downloads\AI_Sherpa_구현_보고서_v2.docx")
OUT = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서.docx"
)

# jingyu v2 에서 제거할 단락 수 (표지 + 목차 = p0~16, 17개)
STRIP_COUNT = 17


def strip_leading_paragraphs(doc, count: int) -> int:
    """본문 시작 부분의 단락 N 개 제거."""
    body = doc.element.body
    removed = 0
    direct = list(body)
    for child in direct:
        if removed >= count:
            break
        if child.tag == qn("w:p"):
            body.remove(child)
            removed += 1
        elif child.tag == qn("w:tbl"):
            # 표가 나오면 중단 — 표는 본문이라 가정
            break
    return removed


def main() -> None:
    print(f"베이스: {BASE.name}")
    print(f"추가: {ADD.name}")
    print()

    base = Document(str(BASE))
    print(f"베이스 본문: 단락 {len(base.paragraphs)} / 표 {len(base.tables)}")

    add = Document(str(ADD))
    print(f"추가 본문 (strip 전): 단락 {len(add.paragraphs)} / 표 {len(add.tables)}")
    removed = strip_leading_paragraphs(add, STRIP_COUNT)
    print(f"  → 표지·목차 {removed} 단락 제거")
    print(f"추가 본문 (strip 후): 단락 {len(add.paragraphs)} / 표 {len(add.tables)}")
    print()

    # 베이스 마지막에 페이지 브레이크
    last = base.paragraphs[-1] if base.paragraphs else base.add_paragraph()
    last.add_run().add_break(WD_BREAK.PAGE)

    # 합치기
    composer = Composer(base)
    composer.append(add)
    composer.save(str(OUT))

    # 결과 확인
    final = Document(str(OUT))
    print(f"✅ 저장: {OUT.name}")
    print(f"   최종 단락 {len(final.paragraphs)} / 표 {len(final.tables)}")
    print()
    print("━━ 통합 후 H1 헤딩 ━━")
    for i, p in enumerate(final.paragraphs):
        st = p.style.name if p.style else ""
        txt = p.text.strip()
        if st == "Heading 1" and txt:
            print(f"  [p{i:3d}] H1: {txt[:60]}")


if __name__ == "__main__":
    main()
