"""통합본 챕터 정리 + 자동 목차 삽입.

작업:
1. body element 순회로 메인 6장(구현)·8장(시험서)·9장(제한사항) 본문 element 삭제
   (다음 H1 직전까지 — paragraph + table 모두)
2. 부록 Ⅸ.구현 본문 → 메인 6장 H1 직후에 이동 (Ⅸ H1 헤딩 자체는 제거)
3. 부록 Ⅶ.시험서 본문 → 메인 8장 H1 직후에 이동
4. 부록 Ⅷ.현실적 제한사항 본문 → 메인 9장 H1 직후에 이동
5. 자동 목차 (TOC field) 를 문서 처음 부분 (목차 자리) 에 삽입
6. 저장
"""
from __future__ import annotations

import re
import sys
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

sys.stdout.reconfigure(encoding="utf-8")

SRC = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_통합본.docx"
)
OUT = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_정리완성.docx"
)


def is_paragraph(el) -> bool:
    return el.tag == qn("w:p")


def is_table(el) -> bool:
    return el.tag == qn("w:tbl")


def get_paragraph_text(el) -> str:
    if not is_paragraph(el):
        return ""
    # w:t 텍스트 모두 합치기
    runs = el.findall(".//" + qn("w:t"))
    return "".join(r.text or "" for r in runs).strip()


def get_paragraph_style(el) -> str:
    if not is_paragraph(el):
        return ""
    pStyle = el.find(".//" + qn("w:pStyle"))
    if pStyle is None:
        return ""
    return pStyle.get(qn("w:val")) or ""


def find_element_index_with_text(body, text_prefix: str, style_must_be: str = "") -> int:
    """body 자식 element 중 paragraph 텍스트가 prefix 로 시작하는 첫 위치."""
    for i, el in enumerate(body):
        if not is_paragraph(el):
            continue
        txt = get_paragraph_text(el)
        if not txt.startswith(text_prefix):
            continue
        if style_must_be and get_paragraph_style(el) != style_must_be:
            continue
        return i
    return -1


def extract_section_elements(body, start_idx: int) -> tuple[int, list]:
    """start_idx (H1 헤딩) 다음 element 부터 다음 H1 (또는 끝) 직전까지 추출.

    반환: (다음 H1 위치 또는 len(body), 추출된 element 리스트)
    """
    elements = []
    i = start_idx + 1
    while i < len(body):
        el = body[i]
        if is_paragraph(el) and get_paragraph_style(el) == "Heading1":
            break
        elements.append(el)
        i += 1
    return i, elements


def remove_section_body(body, start_idx: int) -> int:
    """start_idx (H1) 다음부터 다음 H1 직전까지 element 삭제. 다음 H1 위치 반환."""
    h1_text = get_paragraph_text(body[start_idx])
    i = start_idx + 1
    removed = 0
    while i < len(body):
        el = body[i]
        if is_paragraph(el) and get_paragraph_style(el) == "Heading1":
            break
        body.remove(el)
        removed += 1
    print(f"     {removed} 개 element 제거")
    return i  # 다음 H1 (또는 끝) 의 새 위치


def insert_elements_after(body, after_idx: int, elements: list) -> None:
    """after_idx 다음 위치에 elements 리스트 삽입."""
    anchor = body[after_idx]
    for el in reversed(elements):
        anchor.addnext(deepcopy(el))


def remove_section_with_heading(body, h1_text_prefix: str) -> int:
    """H1 헤딩 + 본문 모두 삭제. 삭제된 element 수 반환."""
    idx = find_element_index_with_text(body, h1_text_prefix, "Heading1")
    if idx < 0:
        return 0
    removed = 0
    # H1 자체 + 다음 H1 직전까지 모두 삭제
    el = body[idx]
    while True:
        next_el = body[idx + 1] if idx + 1 < len(body) else None
        body.remove(el)
        removed += 1
        if next_el is None:
            break
        if is_paragraph(next_el) and get_paragraph_style(next_el) == "Heading1":
            break
        el = next_el
    return removed


def add_toc_field(doc) -> None:
    """문서 시작 부분 (Heading 1 '정보보호 캡스톤디자인 최종보고서' 다음) 에 자동 목차 TOC field 삽입."""
    body = doc.element.body
    # 첫 H1 찾고 그 다음 위치에 TOC 삽입
    for i, el in enumerate(body):
        if is_paragraph(el) and get_paragraph_style(el) == "Heading1":
            # TOC paragraph 생성
            toc_para = OxmlElement("w:p")
            # 페이지 브레이크 (TOC 다음에)
            # TOC field 시작
            r1 = OxmlElement("w:r")
            fldChar1 = OxmlElement("w:fldChar")
            fldChar1.set(qn("w:fldCharType"), "begin")
            r1.append(fldChar1)
            toc_para.append(r1)

            r2 = OxmlElement("w:r")
            instrText = OxmlElement("w:instrText")
            instrText.set(qn("xml:space"), "preserve")
            instrText.text = r' TOC \o "1-3" \h \z \u '
            r2.append(instrText)
            toc_para.append(r2)

            r3 = OxmlElement("w:r")
            fldChar2 = OxmlElement("w:fldChar")
            fldChar2.set(qn("w:fldCharType"), "separate")
            r3.append(fldChar2)
            toc_para.append(r3)

            # placeholder 텍스트
            r4 = OxmlElement("w:r")
            t4 = OxmlElement("w:t")
            t4.text = "[목차는 Word 에서 F9 키로 갱신하세요]"
            r4.append(t4)
            toc_para.append(r4)

            r5 = OxmlElement("w:r")
            fldChar3 = OxmlElement("w:fldChar")
            fldChar3.set(qn("w:fldCharType"), "end")
            r5.append(fldChar3)
            toc_para.append(r5)

            el.addnext(toc_para)

            # 페이지 브레이크 추가
            br_para = OxmlElement("w:p")
            br_r = OxmlElement("w:r")
            br = OxmlElement("w:br")
            br.set(qn("w:type"), "page")
            br_r.append(br)
            br_para.append(br_r)
            toc_para.addnext(br_para)
            return


def main() -> None:
    doc = Document(str(SRC))
    body = doc.element.body
    print(f"열기: 본문 element {len(body)} 개")
    print()

    # ── 1) 부록 Ⅸ/Ⅶ/Ⅷ 본문 추출 ────────────────────────────
    print("━━ 부록 본문 추출 ━━")
    extracted = {}
    for prefix, key in [("Ⅸ. 구현", "9_impl"), ("Ⅶ. 시험서", "7_test"), ("Ⅷ. 현실적", "8_limit")]:
        idx = find_element_index_with_text(body, prefix, "Heading1")
        if idx < 0:
            print(f"  ✗ {prefix} 미발견")
            extracted[key] = []
            continue
        _, els = extract_section_elements(body, idx)
        # 원본 element 를 deepcopy 로 미리 저장 (원본 삭제 대비)
        extracted[key] = [deepcopy(el) for el in els]
        print(f"  ✓ {prefix} 추출: {len(els)} 개 element")

    # ── 2) 부록 H1 + 본문 모두 삭제 (메인 끝의 Ⅶ/Ⅷ/Ⅸ 제거) ──
    print()
    print("━━ 부록 단원 통째로 제거 ━━")
    for prefix in ["Ⅸ. 구현", "Ⅷ. 현실적", "Ⅶ. 시험서"]:
        n = remove_section_with_heading(body, prefix)
        print(f"  ✓ {prefix} 제거: {n} 개 element")

    # ── 3) 메인 6/8/9장 본문 제거 후 부록 본문 삽입 ────────
    print()
    print("━━ 메인 6/8/9장 본문 교체 ━━")
    for main_prefix, extract_key in [("6. 구현", "9_impl"), ("8. 시험서", "7_test"), ("9. 현실적 제한사항", "8_limit")]:
        idx = find_element_index_with_text(body, main_prefix, "Heading1")
        if idx < 0:
            print(f"  ✗ '{main_prefix}' H1 미발견")
            continue
        print(f"  · '{main_prefix}' H1 @ {idx} — 본문 제거")
        # 본문 제거
        remove_section_body(body, idx)
        # 부록 본문 삽입
        if extracted[extract_key]:
            insert_elements_after(body, idx, extracted[extract_key])
            print(f"     {len(extracted[extract_key])} 개 element 삽입")
        else:
            print(f"     (부록 element 없음)")

    # ── 4) 자동 목차 TOC field 삽입 ─────────────────────────
    print()
    print("━━ 자동 목차 TOC field 삽입 ━━")
    add_toc_field(doc)
    print("  ✓ 문서 시작 (정보보호 캡스톤디자인 최종보고서 H1 다음) 에 TOC field 삽입")
    print("  ⚠ Word 에서 열어 F9 키로 목차 갱신 필요")

    doc.save(str(OUT))
    print()
    print(f"✅ 저장: {OUT.name}")
    # H1 일람 확인
    final = Document(str(OUT))
    print()
    print("━━ 최종 H1 챕터 ━━")
    for i, p in enumerate(final.paragraphs):
        st = p.style.name if p.style else ""
        if st == "Heading 1" and p.text.strip():
            print(f"  [p{i:3d}] {p.text.strip()[:55]}")


if __name__ == "__main__":
    main()
