"""코드 캡처 14 장 자동 생성.

각 파일에서 핵심 식별자 위치를 자동 탐지하여 약 50~80 줄 분량을 추출,
Pillow 로 1920x1080 PNG (다크 테마, 줄 번호, Consolas) 렌더링.

산출: 경진대회 최종발표/캡처/capture_06.png ~ 33.png 중 코드 14 장
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

CAPTURE_DIR = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\캡처"
)

# 14 개 코드 캡처 정의 — (번호, 파일경로, 시작 식별자 패턴, 최대 줄수)
CODE_CAPTURES = [
    # (num, path, anchor_regex, max_lines, title)
    (6,  "backend/api/intake.py",
        r"class CreateCaseRequest|@router\.post\([\"']/cases", 60,
        "POST /api/cases 라우터 + Pydantic 스키마"),
    (7,  "backend/data/collection_targets/naver_CREDENTIAL_THEFT.json",
        r"^\s*\{", 40,
        "data/collection_targets/naver_CREDENTIAL_THEFT.json 일부"),
    (10, "backend/core/intake/clue_tree_service.py",
        r"def expand_tree\b", 55,
        "ClueTreeService.expand_tree() 본체"),
    (11, "backend/core/intake/bayesian.py",
        r"def bayes_update\b", 45,
        "bayesian.bayes_update() — 베이즈 정리 구현"),
    (15, "backend/core/ingestion/log_ingestor.py",
        r"class LogIngestor\b", 60,
        "LogIngestor — verify_hash + parse + ingest"),
    (16, "backend/core/ingestion/parsers/nhn.py",
        r"def parse\(|def _parse_event_time\(", 55,
        "NHN 파서 — eventTime 정규화"),
    (20, "backend/core/analysis/ocsf_normalizer.py",
        r"class OCSFNormalizer|def normalize\(", 55,
        "OCSFNormalizer.normalize() — JSON 룰 평탄화"),
    (21, "backend/core/analysis/attack_mapper.py",
        r"def map_events\(|class AttackMapper", 50,
        "AttackMapper.map_events() — Regex 매핑"),
    (22, "backend/core/analysis/gap_detector.py",
        r"def detect\(", 60,
        "GapDetector.detect() — 3종 갭 + completion_rate"),
    (26, "backend/core/sherpa/rag_retriever.py",
        r"def retrieve\(", 55,
        "RAGRetriever — ChromaDB + fallback"),
    (27, "backend/core/sherpa/llm_engine.py",
        r"_THINKING_TAG|def _strip_reasoning\(", 50,
        "LLMEngine._strip_reasoning() — 정규식 3종"),
    (32, "backend/core/board/investigation_board.py",
        r"def get_state\(", 55,
        "InvestigationBoard.get_state() — 한 방 쿼리"),
    (33, "backend/core/board/report_generator.py",
        r"_KOREAN_FONT_CANDIDATES|class ReportGenerator", 60,
        "ReportGenerator — 한글 폰트 4종 + DOCX/PDF"),
]


# ── 신타이팅 색상 (VS Code Dark+ 풍) ─────────────────────────────
COLOR_BG       = (30, 30, 30)        # 배경
COLOR_LINE_NUM = (133, 133, 133)     # 줄 번호
COLOR_TEXT     = (212, 212, 212)     # 일반 텍스트
COLOR_KEYWORD  = (197, 134, 192)     # def class if for return ...
COLOR_STRING   = (206, 145, 120)     # 'string' "string"
COLOR_COMMENT  = (106, 153, 85)      # # comment
COLOR_FUNCTION = (220, 220, 170)     # 함수명
COLOR_NUMBER   = (181, 206, 168)     # 숫자
COLOR_DECORATOR= (78, 201, 176)      # @decorator

PY_KEYWORDS = {
    "def", "class", "if", "elif", "else", "for", "while", "return", "import",
    "from", "as", "try", "except", "finally", "raise", "with", "yield",
    "pass", "break", "continue", "lambda", "in", "not", "and", "or", "is",
    "None", "True", "False", "self", "cls", "async", "await", "global",
    "nonlocal",
}


def colorize_line(line: str) -> list[tuple[str, tuple[int, int, int]]]:
    """파이썬 라인을 (텍스트, 색) 튜플 리스트로 분해. 단순 토큰 단위."""
    # 주석 통째 우선 처리
    comment_match = re.search(r"#.*$", line)
    if comment_match:
        code_part = line[:comment_match.start()]
        comment_part = line[comment_match.start():]
        return colorize_line(code_part) + [(comment_part, COLOR_COMMENT)]
    # 문자열 (단순) — 한 줄 single/double quotes
    parts: list[tuple[str, tuple[int, int, int]]] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch in ('"', "'"):
            # 닫는 따옴표
            j = i + 1
            while j < len(line) and line[j] != ch:
                if line[j] == "\\" and j + 1 < len(line):
                    j += 2
                    continue
                j += 1
            j = min(j + 1, len(line))
            parts.append((line[i:j], COLOR_STRING))
            i = j
        elif ch.isalpha() or ch == "_":
            j = i
            while j < len(line) and (line[j].isalnum() or line[j] == "_"):
                j += 1
            word = line[i:j]
            if word in PY_KEYWORDS:
                parts.append((word, COLOR_KEYWORD))
            elif j < len(line) and line[j] == "(":
                parts.append((word, COLOR_FUNCTION))
            else:
                parts.append((word, COLOR_TEXT))
            i = j
        elif ch.isdigit():
            j = i
            while j < len(line) and (line[j].isdigit() or line[j] == "."):
                j += 1
            parts.append((line[i:j], COLOR_NUMBER))
            i = j
        elif ch == "@":
            j = i + 1
            while j < len(line) and (line[j].isalnum() or line[j] in "._"):
                j += 1
            parts.append((line[i:j], COLOR_DECORATOR))
            i = j
        else:
            parts.append((ch, COLOR_TEXT))
            i += 1
    return parts


def find_anchor_line(content: str, pattern: str) -> int:
    """파일 내용에서 anchor regex 첫 매치 줄 번호 (0-based)."""
    pat = re.compile(pattern, re.MULTILINE)
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if pat.search(line):
            return i
    return 0


def render_code_image(
    code_lines: list[str], start_lineno: int, title: str, file_path: str,
    width: int = 1920, height: int = 1080,
) -> Image.Image:
    """코드 줄들을 PNG 이미지로 렌더링 (VS Code Dark+ 풍)."""
    img = Image.new("RGB", (width, height), COLOR_BG)
    draw = ImageDraw.Draw(img)

    # 폰트
    try:
        font_code = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 18)
        font_title = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 16)
        font_path = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 13)
    except OSError:
        font_code = ImageFont.load_default()
        font_title = ImageFont.load_default()
        font_path = ImageFont.load_default()

    # 상단 타이틀 바
    draw.rectangle([(0, 0), (width, 50)], fill=(45, 45, 48))
    draw.text((20, 12), title, font=font_title, fill=(220, 220, 220))
    draw.text((20, 32), f"▶ {file_path}", font=font_path, fill=(150, 150, 150))

    # 줄 번호 영역 너비
    last_lineno = start_lineno + len(code_lines)
    lineno_width = len(str(last_lineno)) * 12 + 30

    # 본문
    y = 65
    line_height = 24
    for offset, line in enumerate(code_lines):
        if y + line_height > height:
            break
        lineno = start_lineno + offset + 1
        # 줄 번호
        draw.text((10, y), f"{lineno:>4}", font=font_code, fill=COLOR_LINE_NUM)
        # 본문 토큰
        x = lineno_width
        for token, color in colorize_line(line.rstrip("\n")):
            draw.text((x, y), token, font=font_code, fill=color)
            bbox = font_code.getbbox(token)
            x += bbox[2] - bbox[0]
            if x > width - 20:
                break
        y += line_height

    return img


def main() -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"코드 캡처 자동 생성 시작 ({len(CODE_CAPTURES)} 장)\n")
    generated = 0
    skipped = []

    for num, rel_path, anchor, max_lines, title in CODE_CAPTURES:
        src = Path(rel_path)
        if not src.exists():
            print(f"  ✗ capture_{num:02d}.png — 파일 없음: {rel_path}")
            skipped.append(num)
            continue

        content = src.read_text(encoding="utf-8")
        lines = content.split("\n")
        anchor_idx = find_anchor_line(content, anchor)
        # anchor 위로 3 줄 컨텍스트
        start = max(0, anchor_idx - 3)
        end = min(len(lines), start + max_lines)
        code_lines = lines[start:end]

        img = render_code_image(code_lines, start, title, rel_path)
        out_path = CAPTURE_DIR / f"capture_{num:02d}.png"
        img.save(out_path, "PNG", optimize=True)
        print(f"  ✓ capture_{num:02d}.png — {rel_path}  (줄 {start+1}~{end}, {end-start}줄)")
        generated += 1

    print(f"\n✅ 생성 완료: {generated} 장")
    if skipped:
        print(f"⚠ 누락: {skipped} (파일 경로 확인 필요)")


if __name__ == "__main__":
    main()
