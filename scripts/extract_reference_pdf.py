"""레퍼런스 PDF (세종NFT미술관) 와 우리 docx 구조 추출.

용도: 보고서 작성 시 항목 대조 매트릭스 작성 + 시연 세일링 포인트 설계.
"""
import sys
from pathlib import Path

import pdfplumber
import docx

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PDF = Path(r"C:\Users\User\Downloads\참고 자료 (1)\정보보호학과_3조_세종NFT미술관_최종보고서.pdf")
DOCX = Path(r"C:\Users\User\Downloads\최종보고서_로그아웃_AI_Sherpa_v2.docx")


def extract_pdf_outline(page_range: tuple[int, int] | None = None) -> None:
    """PDF 의 각 페이지 첫 줄·헤더 + 길이를 출력 — 목차 식별용."""
    print(f"\n{'='*80}\nPDF: {PDF.name}\n{'='*80}")
    with pdfplumber.open(PDF) as pdf:
        total = len(pdf.pages)
        print(f"총 {total} 페이지\n")
        start, end = page_range or (1, total)
        for i in range(start - 1, min(end, total)):
            page = pdf.pages[i]
            text = page.extract_text() or ""
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if not lines:
                print(f"--- p.{i+1} (빈 페이지) ---")
                continue
            print(f"\n--- p.{i+1} ({len(text)} chars, {len(lines)} lines) ---")
            # 첫 5 줄만 (제목·헤더)
            for line in lines[:5]:
                print(f"  {line[:100]}")
            if len(lines) > 5:
                print(f"  ... +{len(lines)-5} lines")


def extract_pdf_page_full(page_num: int) -> None:
    """특정 페이지 전체 텍스트."""
    print(f"\n{'='*80}\nPDF p.{page_num} 전체\n{'='*80}")
    with pdfplumber.open(PDF) as pdf:
        if page_num > len(pdf.pages):
            print(f"페이지 초과 (총 {len(pdf.pages)})")
            return
        text = pdf.pages[page_num - 1].extract_text() or ""
        print(text[:3000])


def extract_docx_structure() -> None:
    """docx 의 headings + paragraph 수 출력 — 구조 매핑."""
    print(f"\n{'='*80}\nDOCX: {DOCX.name}\n{'='*80}")
    if not DOCX.exists():
        print(f"파일 없음: {DOCX}")
        return
    d = docx.Document(DOCX)
    print(f"총 paragraphs: {len(d.paragraphs)}, tables: {len(d.tables)}\n")
    print("=== 헤딩 구조 ===")
    for i, p in enumerate(d.paragraphs):
        st = (p.style.name or "")
        text = p.text.strip()
        if not text:
            continue
        if st.startswith("Heading") or st in {"Title", "Subtitle"}:
            level = st.replace("Heading ", "").strip()
            indent = "  " * (int(level) if level.isdigit() else 0)
            print(f"  [p{i:3d}] {indent}{st}: {text[:80]}")
        elif i < 5:  # 첫 5 단락은 전체 출력
            print(f"  [p{i:3d}] {text[:80]}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "outline"
    if cmd == "outline":
        extract_pdf_outline()
    elif cmd == "outline_range":
        s, e = int(sys.argv[2]), int(sys.argv[3])
        extract_pdf_outline((s, e))
    elif cmd == "page":
        extract_pdf_page_full(int(sys.argv[2]))
    elif cmd == "docx":
        extract_docx_structure()
    elif cmd == "all":
        extract_pdf_outline()
        extract_docx_structure()
    else:
        print(f"사용법: python {sys.argv[0]} [outline|outline_range S E|page N|docx|all]")


if __name__ == "__main__":
    main()
