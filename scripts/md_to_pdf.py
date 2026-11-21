"""Markdown → PDF 변환기 (한국어 지원, 2026-05-31, byungwoo).

설계서: 시스템 플로우 상세 보고서 PDF 출력용.

의존성
-------
    pip install markdown beautifulsoup4 lxml reportlab

폰트
----
    Windows: C:/Windows/Fonts/malgun.ttf (Malgun Gothic)
    Bold:    C:/Windows/Fonts/malgunbd.ttf

사용
----
    python scripts/md_to_pdf.py <input.md> <output.pdf>
"""
from __future__ import annotations

import sys
from pathlib import Path

import markdown
from bs4 import BeautifulSoup, NavigableString
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    Preformatted,
)

# ── 폰트 등록 ────────────────────────────────────────────────
FONT_REGULAR = "MalgunGothic"
FONT_BOLD = "MalgunGothic-Bold"
FONT_MONO = "Consolas"

pdfmetrics.registerFont(TTFont(FONT_REGULAR, "C:/Windows/Fonts/malgun.ttf"))
pdfmetrics.registerFont(TTFont(FONT_BOLD, "C:/Windows/Fonts/malgunbd.ttf"))
try:
    pdfmetrics.registerFont(TTFont(FONT_MONO, "C:/Windows/Fonts/consola.ttf"))
except Exception:
    FONT_MONO = FONT_REGULAR  # fallback


# ── 스타일 ───────────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()["Normal"]
    return {
        "h1": ParagraphStyle(
            "H1", parent=base, fontName=FONT_BOLD, fontSize=20, leading=26,
            textColor=colors.HexColor("#1a365d"),
            spaceBefore=18, spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base, fontName=FONT_BOLD, fontSize=15, leading=20,
            textColor=colors.HexColor("#2c5282"),
            spaceBefore=14, spaceAfter=8,
            borderPadding=(2, 0, 4, 0),
        ),
        "h3": ParagraphStyle(
            "H3", parent=base, fontName=FONT_BOLD, fontSize=12.5, leading=17,
            textColor=colors.HexColor("#2d3748"),
            spaceBefore=10, spaceAfter=6,
        ),
        "h4": ParagraphStyle(
            "H4", parent=base, fontName=FONT_BOLD, fontSize=11, leading=15,
            textColor=colors.HexColor("#4a5568"),
            spaceBefore=8, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body", parent=base, fontName=FONT_REGULAR, fontSize=9.5, leading=14,
            textColor=colors.HexColor("#1a202c"),
            alignment=TA_LEFT, spaceAfter=4,
        ),
        "li": ParagraphStyle(
            "Li", parent=base, fontName=FONT_REGULAR, fontSize=9.5, leading=14,
            textColor=colors.HexColor("#1a202c"),
            leftIndent=14, bulletIndent=4, spaceAfter=2,
        ),
        "code": ParagraphStyle(
            "Code", parent=base, fontName=FONT_MONO, fontSize=8.5, leading=11,
            textColor=colors.HexColor("#1a202c"),
            backColor=colors.HexColor("#f7fafc"),
            borderColor=colors.HexColor("#cbd5e0"),
            borderWidth=0.5, borderPadding=6,
            leftIndent=4, rightIndent=4,
            spaceBefore=4, spaceAfter=6,
        ),
        "quote": ParagraphStyle(
            "Quote", parent=base, fontName=FONT_REGULAR, fontSize=9.5, leading=14,
            textColor=colors.HexColor("#4a5568"),
            leftIndent=12, spaceAfter=6,
            borderColor=colors.HexColor("#cbd5e0"),
            borderWidth=0, borderPadding=0,
        ),
    }


# ── 인라인 변환 (b/i/code) ───────────────────────────────────
def _inline(node) -> str:
    """BS4 노드 → reportlab Paragraph 인라인 마크업 (<b>, <i>, <font>)."""
    if isinstance(node, NavigableString):
        # ReportLab 의 Paragraph 는 &, <, > 만 escape 필요
        return (
            str(node)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
    name = node.name
    inner = "".join(_inline(c) for c in node.children)
    if name in ("strong", "b"):
        return f'<font name="{FONT_BOLD}">{inner}</font>'
    if name in ("em", "i"):
        return f"<i>{inner}</i>"
    if name == "code":
        return (
            f'<font name="{FONT_MONO}" color="#c53030" backColor="#fff5f5">'
            f"&nbsp;{inner}&nbsp;</font>"
        )
    if name == "a":
        href = node.get("href", "")
        return f'<link href="{href}" color="blue"><u>{inner}</u></link>'
    if name == "br":
        return "<br/>"
    return inner


def _para_inline(node) -> str:
    return "".join(_inline(c) for c in node.children)


# ── 블록 변환 ────────────────────────────────────────────────
def md_to_flowables(md_text: str):
    html = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br"],
    )
    soup = BeautifulSoup(html, "lxml")
    st = _styles()
    flow = []

    body = soup.body if soup.body else soup
    for el in body.children:
        if isinstance(el, NavigableString):
            text = str(el).strip()
            if text:
                flow.append(Paragraph(text, st["body"]))
            continue

        tag = el.name
        if tag == "h1":
            flow.append(Paragraph(_para_inline(el), st["h1"]))
        elif tag == "h2":
            flow.append(Paragraph(_para_inline(el), st["h2"]))
        elif tag == "h3":
            flow.append(Paragraph(_para_inline(el), st["h3"]))
        elif tag in ("h4", "h5", "h6"):
            flow.append(Paragraph(_para_inline(el), st["h4"]))
        elif tag == "p":
            txt = _para_inline(el).strip()
            if txt:
                flow.append(Paragraph(txt, st["body"]))
        elif tag in ("ul", "ol"):
            for i, li in enumerate(el.find_all("li", recursive=False), 1):
                bullet = "• " if tag == "ul" else f"{i}. "
                flow.append(Paragraph(bullet + _para_inline(li), st["li"]))
        elif tag == "pre":
            code = el.find("code")
            text = code.get_text() if code else el.get_text()
            # Preformatted 는 escape 불필요
            flow.append(Preformatted(text.rstrip(), st["code"]))
        elif tag == "blockquote":
            txt = _para_inline(el).strip()
            if txt:
                flow.append(Paragraph(txt, st["quote"]))
        elif tag == "hr":
            flow.append(Spacer(1, 8))
        elif tag == "table":
            tbl = _convert_table(el, st)
            if tbl:
                flow.append(tbl)
                flow.append(Spacer(1, 4))

    return flow


def _convert_table(el, st):
    rows = []
    head = el.find("thead")
    if head:
        for tr in head.find_all("tr"):
            rows.append([
                Paragraph(_para_inline(td), st["body"])
                for td in tr.find_all(["th", "td"])
            ])
    body = el.find("tbody") or el
    for tr in body.find_all("tr"):
        if tr.find("th") and head:
            continue  # thead 의 행 skip
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        rows.append([Paragraph(_para_inline(c), st["body"]) for c in cells])
    if not rows:
        return None
    t = Table(rows, repeatRows=1 if head else 0)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf2f7")),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


# ── 헤더/푸터 ────────────────────────────────────────────────
def _header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT_REGULAR, 8)
    canvas.setFillColor(colors.HexColor("#718096"))
    # Header
    canvas.drawString(20 * mm, A4[1] - 12 * mm, "AI Sherpa — 시스템 플로우 상세 보고서")
    canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm, "byungwoo · 2026-05-31")
    canvas.setStrokeColor(colors.HexColor("#cbd5e0"))
    canvas.line(20 * mm, A4[1] - 14 * mm, A4[0] - 20 * mm, A4[1] - 14 * mm)
    # Footer
    canvas.drawCentredString(A4[0] / 2, 10 * mm, f"- {doc.page} -")
    canvas.restoreState()


# ── 메인 ────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 3:
        print("Usage: python md_to_pdf.py <input.md> <output.pdf>")
        sys.exit(1)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    md_text = src.read_text(encoding="utf-8")
    flow = md_to_flowables(md_text)

    doc = SimpleDocTemplate(
        str(dst),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=15 * mm,
        title="AI Sherpa 시스템 플로우 상세 보고서",
        author="byungwoo",
    )
    doc.build(flow, onFirstPage=_header_footer, onLaterPages=_header_footer)
    print(f"✓ PDF 생성: {dst} ({dst.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
