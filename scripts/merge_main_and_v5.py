"""메인 보고서 (1~10장) + v5 (Ⅶ/Ⅷ/Ⅸ 확장 단원) 병합.

전략: 단순 append
  - 메인 베이스 (Downloads 의 최종보고서_로그아웃_AI_Sherpa.docx) 유지
  - 메인 끝에 페이지 브레이크
  - v5 의 표지 (p0~6, 7 단락) 제거 후 본문 (Ⅶ → Ⅷ → Ⅸ) 통째로 append

결과: 1~10장 + Ⅶ + Ⅷ + Ⅸ
  사용자가 Word 에서:
    - 6장(구현)·8장(시험서)·9장(제한사항) 본문 중 중복 부분 자르기
    - 또는 Ⅶ/Ⅷ/Ⅸ 챕터 번호를 6/8/9 로 변경하고 기존 본문 제거
"""
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_BREAK
from docx.oxml.ns import qn
from docxcompose.composer import Composer

sys.stdout.reconfigure(encoding="utf-8")

MAIN = Path(r"C:\Users\User\Downloads\최종보고서_로그아웃_AI_Sherpa.docx")
EXT = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_v5.docx"
)
OUT = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_통합본.docx"
)

STRIP_COUNT = 7  # v5 표지 단락 수


def strip_leading(doc, count: int) -> int:
    body = doc.element.body
    removed = 0
    for child in list(body):
        if removed >= count:
            break
        if child.tag == qn("w:p"):
            body.remove(child)
            removed += 1
        elif child.tag == qn("w:tbl"):
            break
    return removed


def main() -> None:
    print(f"메인: {MAIN.name}")
    print(f"확장: {EXT.name}")
    print()

    main_doc = Document(str(MAIN))
    ext_doc = Document(str(EXT))

    print(f"메인: 단락 {len(main_doc.paragraphs)} / 표 {len(main_doc.tables)}")
    print(f"확장 (strip 전): 단락 {len(ext_doc.paragraphs)} / 표 {len(ext_doc.tables)}")
    removed = strip_leading(ext_doc, STRIP_COUNT)
    print(f"  → 표지 {removed} 단락 제거")
    print(f"확장 (strip 후): 단락 {len(ext_doc.paragraphs)} / 표 {len(ext_doc.tables)}")
    print()

    # 메인 끝에 페이지 브레이크
    last = main_doc.paragraphs[-1] if main_doc.paragraphs else main_doc.add_paragraph()
    last.add_run().add_break(WD_BREAK.PAGE)

    composer = Composer(main_doc)
    composer.append(ext_doc)
    composer.save(str(OUT))

    final = Document(str(OUT))
    img = sum(1 for r in final.part.related_parts.values() if r.content_type.startswith("image/"))
    print(f"✅ 저장: {OUT.name}")
    print(f"   최종 단락 {len(final.paragraphs)} / 표 {len(final.tables)} / 이미지 {img}")
    print(f"   파일 크기 {OUT.stat().st_size / 1024:.0f} KB")
    print()
    print("━━ 통합 후 H1 헤딩 ━━")
    for i, p in enumerate(final.paragraphs):
        st = p.style.name if p.style else ""
        if st == "Heading 1" and p.text.strip():
            print(f"  [p{i:3d}] {p.text.strip()[:60]}")


if __name__ == "__main__":
    main()
