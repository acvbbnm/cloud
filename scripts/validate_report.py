"""보고서 docx 맞춤법·내용 검증.

C1. 한국어 맞춤법·띄어쓰기 (의존명사·이중피동·구식)
C2. 수치 정합성 (74룰 / 129케이스 / 9사고유형 / 30API / 16시드)
C3. 헤딩 번호 연속성 (1.1·1.2·… 누락·중복)
C4. 표 캡션 번호 ([표 N] 연속성·중복)
C5. 금지 단어·AI 활용 메타 (TODO/FIXME/Claude/ChatGPT)
C6. 중복 단락 (50자 이상 동일 본문 2회+)
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

from docx import Document

sys.stdout.reconfigure(encoding="utf-8")

DOCX = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_정리완성.docx"
)


SPELLING_PATTERNS = [
    (r"되여\b", "되어", "구식 표기"),
    (r"되였\b", "되었", "구식 표기"),
    (r"\b할수\s*있", "할 수 있", "의존명사 '수'"),
    (r"\b할것", "할 것", "의존명사 '것'"),
    (r"\b하는것", "하는 것", "의존명사 '것'"),
    (r"\b되는것", "되는 것", "의존명사 '것'"),
    (r"있을것", "있을 것", "의존명사 '것'"),
    (r"하였슴", "하였음", "오타"),
    (r"이루어 졌", "이루어졌", "띄어쓰기"),
    (r"\b및\s*및\b", "및", "중복 접속사"),
    (r"\b또한\s*또한\b", "또한", "중복 접속사"),
    (r"\.\.\.\s*\.", "…", "말줄임표"),
    (r"\s{4,}", " ", "연속 공백 4 개+"),  # 3은 ASCII 다이어그램에서 거짓 양성 많음
]


EXPECTED_NUMBERS = {
    "사고유형 9 종": ["9 사고유형", "9종 사고유형", "사고유형 9", "9 가지 사고유형"],
    "ATT&CK 74 룰": ["74 룰", "74룰", "74 개 룰", "74개 룰"],
    "pytest 129 케이스": ["129 케이스", "129 테스트", "129개"],
    "REST 30 엔드포인트": ["30 엔드포인트", "30개 엔드포인트", "30 API"],
    "8 라우터": ["8 라우터", "8개 라우터"],
    "KB 130 청크": ["130 청크", "130개 청크"],
    "시드 16/77": ["16 시드", "77 행", "77행", "16 파일"],
    "결정트리 24/143": ["24 노드", "143 단서"],
    "외부 표준 7 종": ["7 종", "7종"],
}

OLD_BAD = {
    "124 테스트": "129 테스트",
    "124 케이스": "129 케이스",
    "73 룰": "74 룰",
    "5 사고유형 (현재)": "9 사고유형",
    "8 사고유형": "9 사고유형 (UNCLASSIFIED 포함)",
    "29 엔드포인트": "30 엔드포인트",
}


FORBIDDEN = [
    (r"\bTODO\b", "미완료"),
    (r"\bFIXME\b", "미완료"),
    (r"\bXXX\b", "미완료"),
    (r"\bTBD\b", "미완료"),
    (r"lorem\s*ipsum", "더미"),
    (r"\bplaceholder\b", "placeholder"),
    (r"\bClaude\b", "AI 메타"),
    (r"\bChatGPT\b", "AI 메타"),
    (r"\bCursor\b", "AI 메타"),
    (r"\bCopilot\b", "AI 메타"),
    (r"사용자\s*요청", "AI 메타"),
    (r"프롬프트\s*엔지니어링", "AI 메타"),
]


def collect_paragraphs(doc):
    return [(i, p.style.name if p.style else "", p.text.strip())
            for i, p in enumerate(doc.paragraphs) if p.text.strip()]


def collect_table_cells(doc):
    rows = []
    for ti, t in enumerate(doc.tables):
        for ri, row in enumerate(t.rows):
            for ci, cell in enumerate(row.cells):
                txt = cell.text.strip()
                if txt:
                    rows.append((ti, ri, ci, txt))
    return rows


def check_c1_spelling(paras):
    out = []
    for idx, _st, text in paras:
        for pat, sugg, reason in SPELLING_PATTERNS:
            m = re.search(pat, text)
            if m:
                snip = text[max(0, m.start()-15):min(len(text), m.end()+15)]
                out.append(f"  [p{idx:3d}] '{m.group(0)}' → '{sugg}' ({reason}) · …{snip}…")
    return out


def check_c2_numbers(paras, cells):
    all_text = "\n".join(t for _, _, t in paras) + "\n" + "\n".join(t for _, _, _, t in cells)
    out = []
    for label, allowed in EXPECTED_NUMBERS.items():
        if not any(v in all_text for v in allowed):
            out.append(f"  ✗ '{label}' 진실값 미발견 — 허용: {allowed}")
    for old, new in OLD_BAD.items():
        for idx, _st, text in paras:
            if old in text:
                out.append(f"  ⚠ [p{idx:3d}] 옛 수치 '{old}' → '{new}' 권장")
    return out


def check_c3_headings(paras):
    out = []
    seen = {}
    headings = []
    for idx, st, text in paras:
        if not st.startswith("Heading"):
            continue
        m = re.match(r"^(\d+(?:\.\d+)*)", text)
        if not m:
            continue
        num = m.group(1)
        headings.append((idx, num))
        if num in seen:
            out.append(f"  ✗ 중복 헤딩 번호 '{num}' [p{seen[num]}] vs [p{idx}]")
        seen[num] = idx
    children = {}
    for idx, num in headings:
        parts = num.split(".")
        if len(parts) < 2:
            continue
        parent = ".".join(parts[:-1])
        try:
            children.setdefault(parent, []).append(int(parts[-1]))
        except ValueError:
            continue
    for parent, lst in children.items():
        nums = sorted(set(lst))
        expected = list(range(min(nums), max(nums)+1))
        missing = set(expected) - set(nums)
        if missing:
            out.append(f"  ⚠ § {parent}.X 누락: {sorted(missing)} (현재: {nums})")
    return out


def check_c4_table_captions(paras):
    out = []
    caps = []
    for idx, _st, text in paras:
        for m in re.finditer(r"\[표\s*(\d+)\]|<표\s*([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ\d-]+)>", text):
            label = m.group(1) or m.group(2)
            caps.append((label, idx))
    nums = [n for n, _ in caps]
    if not nums:
        return ["  (표 캡션 없음)"]
    dup = [n for n, c in Counter(nums).items() if c > 1]
    for d in dup:
        idxs = [i for n, i in caps if n == d]
        out.append(f"  ⚠ [표 {d}] 중복 캡션 — 단락 {idxs}")
    return out


def check_c5_forbidden(paras, cells):
    out = []
    for idx, _st, text in paras:
        for pat, reason in FORBIDDEN:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                snip = text[max(0, m.start()-20):min(len(text), m.end()+20)]
                out.append(f"  ✗ [p{idx:3d}] '{m.group(0)}' ({reason}) · …{snip}…")
    for ti, ri, ci, text in cells:
        for pat, reason in FORBIDDEN:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                out.append(f"  ✗ [표 {ti+1}/r{ri}c{ci}] '{m.group(0)}' ({reason})")
    return out


def check_c6_duplicates(paras):
    out = []
    seen = {}
    for idx, _st, text in paras:
        if len(text) < 50:
            continue
        seen.setdefault(text, []).append(idx)
    for text, idxs in seen.items():
        if len(idxs) > 1:
            out.append(f"  ⚠ 동일 단락 {len(idxs)} 회 (p{idxs}) — {text[:30]}…")
    return out


def main():
    doc = Document(str(DOCX))
    paras = collect_paragraphs(doc)
    cells = collect_table_cells(doc)
    print(f"검증: {DOCX.name}")
    print(f"  단락 {len(paras)} / 표 {len(doc.tables)} / 셀 {len(cells)}\n")

    sections = [
        ("C1 맞춤법·띄어쓰기", check_c1_spelling(paras)),
        ("C2 수치 정합성", check_c2_numbers(paras, cells)),
        ("C3 헤딩 번호 연속성", check_c3_headings(paras)),
        ("C4 표 캡션 번호", check_c4_table_captions(paras)),
        ("C5 금지 단어·AI 메타", check_c5_forbidden(paras, cells)),
        ("C6 중복 단락", check_c6_duplicates(paras)),
    ]
    total = 0
    for name, findings in sections:
        print(f"━━━ {name} ━━━")
        if not findings:
            print("  ✅ PASS")
        else:
            for f in findings:
                print(f)
            total += len(findings)
        print()
    print("=" * 60)
    if total == 0:
        print("✅ 전체 PASS")
    else:
        print(f"⚠ 총 {total} 건 검토 필요")


if __name__ == "__main__":
    main()
