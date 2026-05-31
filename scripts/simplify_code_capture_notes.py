"""최종_AI_Sherpa_보고서.docx 의 13 개 H4 핵심코드 섹션을 정리.

작업:
1. '※ 코드 캡처 안내 — ...' 단락 (290~400자) 을 한 줄 (~90자) 로 단축
   원본: 캡처 대상 파일 + 캡처 범위 + 캡처 위치 안내 + 비고
   단축: ▶ 캡처: <파일> <줄 범위> (<주요 식별자>)
2. 그 외 단락은 유지 (설명·동작 단계 리스트는 미술관 패턴에 부합)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor

sys.stdout.reconfigure(encoding="utf-8")

DOCX = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서.docx"
)
OUT = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_정리.docx"
)


def extract_capture_meta(text: str) -> tuple[str, str]:
    """※ 코드 캡처 안내 텍스트에서 파일 경로 + 범위 키워드 추출.

    반환: (파일경로, 범위설명)
    """
    # "캡처 대상 파일: backend/api/intake.py" 추출
    file_match = re.search(r"캡처 대상 파일:\s*(\S+)", text)
    file_path = file_match.group(1).rstrip(".") if file_match else "(파일)"

    # "캡처 범위: ..." 추출 (다음 문장 마침표 또는 줄바꿈까지)
    range_match = re.search(r"캡처 범위:\s*([^.]+)", text)
    range_desc = range_match.group(1).strip() if range_match else "(범위)"

    # 범위 설명에서 핵심만 — "약 48~120행 — class CreateCaseRequest(BaseModel) 선언부터 ..."
    # 처음 80자만 자르고 "..." 추가
    if len(range_desc) > 80:
        range_desc = range_desc[:78].rstrip() + "…"

    return file_path, range_desc


def replace_capture_note(p, file_path: str, range_desc: str) -> None:
    """단락 내용을 짧은 캡처 가이드로 교체."""
    # 모든 run 비우기
    for r in list(p.runs):
        r.text = ""
    # 첫 run 에 새 텍스트
    new_text = f"▶ 캡처: {file_path}  ({range_desc})"
    if p.runs:
        p.runs[0].text = new_text
        # 회색 italic 9pt 로 마무리
        p.runs[0].italic = True
        p.runs[0].font.size = Pt(9)
        p.runs[0].font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    else:
        run = p.add_run(new_text)
        run.italic = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)


def main() -> None:
    doc = Document(str(DOCX))
    print(f"열기: 단락 {len(doc.paragraphs)}\n")
    changed = 0

    for i, p in enumerate(doc.paragraphs):
        txt = p.text.strip()
        if not txt.startswith("※ 코드 캡처 안내"):
            continue
        before_len = len(txt)
        file_path, range_desc = extract_capture_meta(txt)
        replace_capture_note(p, file_path, range_desc)
        after_len = len(f"▶ 캡처: {file_path}  ({range_desc})")
        print(f"  ✓ [p{i:3d}] {before_len:3d}ch → {after_len:3d}ch")
        print(f"     {file_path}")
        changed += 1

    doc.save(str(OUT))
    print(f"\n✅ 저장: {OUT.name}")
    print(f"   {changed} 개 캡처 안내 단축 완료 (평균 350자 → 90자)")


if __name__ == "__main__":
    main()
