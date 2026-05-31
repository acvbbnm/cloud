"""캡처 도우미 — 33 개 그림 자리 분석 + 자동 매핑 + 사용자 캡처 안내 + 자동 삽입.

3 가지 동작:
  python capture_helper.py prep   — 캡처 체크리스트 + 빈 폴더 생성 + 자동 매핑 적용
  python capture_helper.py status — 현재 캡처 진행률 확인
  python capture_helper.py fill   — captures/ 폴더의 모든 PNG 자동 삽입

캡처 폴더: 경진대회 최종발표/캡처/  (파일명: capture_01.png ~ capture_33.png)
산출 docx: 경진대회 최종발표/최종_AI_Sherpa_보고서_캡처완성.docx
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Cm, Pt, RGBColor

sys.stdout.reconfigure(encoding="utf-8")

SRC = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_back.docx"
)
OUT = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종_AI_Sherpa_보고서_캡처완성.docx"
)
CAPTURE_DIR = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\캡처"
)
CHECKLIST_MD = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\캡처_체크리스트.md"
)
JINGYU_CAPTURES = Path("docs/draft_final_report/options/captures")

# 33 개 그림 정의 — (번호, 종류, 화면/파일, 상태/줄범위, 자동매핑 후보 .png)
CAPTURES: list[dict] = [
    # 1. 사고 접수 5단계 위저드 ── UI 5장 (V-1 Step 0~4)
    {"num": 1, "kind": "UI",   "title": "Step 0 — CSP 선택", "where": "브라우저 V-1 → 첫 진입 화면", "how": "Win+Shift+S 1920x1080 영역", "auto": "V_setup.png"},
    {"num": 2, "kind": "UI",   "title": "Step 1 — 케이스 메타데이터 입력", "where": "V-1 → CSP 선택 후 [다음]", "how": "Step 1 진행바 활성 상태", "auto": None},
    {"num": 3, "kind": "UI",   "title": "Step 2 — 시스템 구성 입력", "where": "V-1 → Step 2 (계정 ID·리전·인스턴스·버킷)", "how": "일부 체크박스 토글 후 캡처", "auto": "V_setup_with_case.png"},
    {"num": 4, "kind": "UI",   "title": "Step 3 — Discovery (단서 입력 + 후보 갱신)", "where": "V-1 → Step 3 Evidence Tree", "how": "TRIAGE_MODE=evidence_tree 모드, 단서 1건 입력 직후", "auto": None},
    {"num": 5, "kind": "UI",   "title": "Step 4 — 수집 가이드 체크리스트", "where": "V-1 → Step 4 (REQUIRED/CORROBORATING 배지)", "how": "체크리스트 표시 상태 캡처", "auto": None},
    # 1) 핵심 코드 2장
    {"num": 6, "kind": "CODE", "title": "POST /api/cases 라우터", "where": "VS Code backend/api/intake.py", "how": "48~120행 (CreateCaseRequest → @router.post)", "auto": None},
    {"num": 7, "kind": "CODE", "title": "data/collection_targets/*.json 일부", "where": "VS Code data/collection_targets/credential_theft_ncp.json", "how": "JSON 1~40행", "auto": None},
    # 2. Evidence Tree ── UI 2장
    {"num": 8, "kind": "UI",   "title": "Evidence Tree — 단서 1건 후 트리", "where": "V-1 Step 3 → 단서 1건 입력 직후", "how": "uniform prior → 1단계 분기 트리 표시", "auto": None},
    {"num": 9, "kind": "UI",   "title": "Evidence Tree — 단서 3건 누적 수렴", "where": "V-1 Step 3 → 단서 3건 입력 후", "how": "confidence ≥ 0.65 수렴 상태", "auto": None},
    # 핵심 코드 2장
    {"num": 10, "kind": "CODE", "title": "ClueTreeService.expand_tree() 본체", "where": "VS Code backend/core/intake/clue_tree_service.py", "how": "expand_tree 메서드 전체", "auto": None},
    {"num": 11, "kind": "CODE", "title": "bayesian.bayes_update() — 베이즈 정리 구현", "where": "VS Code backend/core/intake/bayesian.py", "how": "bayes_update 함수 + docstring", "auto": None},
    # 3. V-2 Logs ── UI 3장
    {"num": 12, "kind": "UI",   "title": "V-2 Logs — DropZone 빈 상태", "where": "브라우저 V-2 진입 직후", "how": "DropZone + 4 KPI 카드 빈 상태", "auto": "V_logs.png"},
    {"num": 13, "kind": "UI",   "title": "V-2 Logs — 업로드 직후 이벤트 미리보기", "where": "V-2 → JSON 업로드 후", "how": "matched/unmatched 통계 포함 이벤트 테이블", "auto": "V_logs_with_case.png"},
    {"num": 14, "kind": "UI",   "title": "V-2 Logs — 행 클릭 시 우측 드로어", "where": "V-2 → 이벤트 행 클릭", "how": "raw_blob + SHA-256 + 무결성 ✓ 드로어", "auto": None},
    # 핵심 코드 2장
    {"num": 15, "kind": "CODE", "title": "LogIngestor — verify_hash + parse + ingest", "where": "VS Code backend/core/ingestion/log_ingestor.py", "how": "class LogIngestor 전체", "auto": None},
    {"num": 16, "kind": "CODE", "title": "NHN 파서 — eventTime 정규화", "where": "VS Code backend/core/ingestion/parsers/nhn.py", "how": "parse() + _parse_event_time() 헬퍼", "auto": None},
    # 4. Layer 2 분석 ── UI 3장 (V-3, V-6, V-4)
    {"num": 17, "kind": "UI",   "title": "V-3 OCSF — 정규화 결과 테이블", "where": "V-2 업로드 후 V-3 이동 → 정규화 실행", "how": "OCSF 표준 컬럼 표시 상태", "auto": "V_ocsf_with_case.png"},
    {"num": 18, "kind": "UI",   "title": "V-6 ATT&CK — Tactics × Techniques 칸반", "where": "V-3 후 V-6 → 매핑 실행", "how": "Tactics × Techniques 칸반 보드 표시", "auto": "V_attack_with_case.png"},
    {"num": 19, "kind": "UI",   "title": "V-4 Gap — 갭 유형별 카드", "where": "V-6 후 V-4 → 갭 감지", "how": "COLLECTION/EVIDENCE/INTERPRETATION 카드", "auto": "V_gap_with_case.png"},
    # 핵심 코드 3장
    {"num": 20, "kind": "CODE", "title": "OCSFNormalizer.normalize() — JSON 룰 평탄화", "where": "VS Code backend/core/analysis/ocsf_normalizer.py", "how": "normalize() + _load_rules()", "auto": None},
    {"num": 21, "kind": "CODE", "title": "AttackMapper.map_events() — Regex 매핑", "where": "VS Code backend/core/analysis/attack_mapper.py", "how": "map_events() 본체", "auto": None},
    {"num": 22, "kind": "CODE", "title": "GapDetector.detect() — 3종 갭 + completion_rate", "where": "VS Code backend/core/analysis/gap_detector.py", "how": "classmethod detect() 전체", "auto": None},
    # 5. V-8 셰르파 ── UI 3장
    {"num": 23, "kind": "UI",   "title": "V-8 셰르파 — 우측 도크 + 4 액션 버튼", "where": "V-8 진입 직후", "how": "엔진 상태 + KB 인덱스 사이드바", "auto": "V_sherpa.png"},
    {"num": 24, "kind": "UI",   "title": "V-8 셰르파 — 컨텍스트 브리핑 응답", "where": "V-8 → [컨텍스트 브리핑] 버튼 클릭", "how": "KB 인용 칩 + ATT&CK 자동 라벨", "auto": "V_sherpa_with_case.png"},
    {"num": 25, "kind": "UI",   "title": "V-8 셰르파 — 자유 질의 채팅 (2턴)", "where": "V-8 → 자연어 질의 2회 연속", "how": "ChatSession 2턴 이상 유지 상태", "auto": None},
    # 핵심 코드 2장
    {"num": 26, "kind": "CODE", "title": "RAGRetriever — ChromaDB + fallback", "where": "VS Code backend/core/sherpa/rag_retriever.py", "how": "retrieve() + _chroma_retrieve() + _keyword_*", "auto": None},
    {"num": 27, "kind": "CODE", "title": "LLMEngine._strip_reasoning() — 정규식 3종", "where": "VS Code backend/core/sherpa/llm_engine.py", "how": "_THINKING_TAG 상수 + _strip_reasoning 메서드", "auto": None},
    # 6. V-5 Board · V-7 Report ── UI 4장
    {"num": 28, "kind": "UI",   "title": "V-5 수사 보드 — 노드/엣지 캔버스", "where": "V-5 진입 → 노드 일부 배치 후", "how": "react-flow 캔버스 + AI 브리핑 사이드바", "auto": "V_board_with_case.png"},
    {"num": 29, "kind": "UI",   "title": "V-5 — 회귀 권고 polyline 4단계", "where": "V-5 → AI 빠진 고리 제안 후", "how": "단서→유형→기법→자산 polyline 표시", "auto": None},
    {"num": 30, "kind": "UI",   "title": "V-7 보고서 — 초안 미리보기 + 섹션 편집", "where": "V-7 → [보고서 생성] 후", "how": "좌 미리보기 + 우 섹션 편집기", "auto": "V_report_with_case.png"},
    {"num": 31, "kind": "UI",   "title": "V-7 보고서 — DOCX 내보내기 직후 Word 화면", "where": "V-7 → [DOCX 내보내기] 후 Word 자동 실행", "how": "Word 에서 생성된 docx 열린 상태", "auto": None},
    # 핵심 코드 2장
    {"num": 32, "kind": "CODE", "title": "InvestigationBoard.get_state() — 한 방 쿼리", "where": "VS Code backend/core/board/investigation_board.py", "how": "classmethod get_state() 전체", "auto": None},
    {"num": 33, "kind": "CODE", "title": "ReportGenerator — 한글 폰트 4종 + DOCX/PDF", "where": "VS Code backend/core/board/report_generator.py", "how": "_KOREAN_FONT_CANDIDATES + ReportGenerator", "auto": None},
]


def cmd_prep() -> None:
    """체크리스트 생성 + 캡처 폴더 생성 + 자동 매핑 적용."""
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

    # 1) 자동 매핑 — jingyu captures 16 장을 capture_NN.png 로 미리 복사
    auto_count = 0
    if JINGYU_CAPTURES.exists():
        import shutil
        for cap in CAPTURES:
            if cap["auto"]:
                src = JINGYU_CAPTURES / cap["auto"]
                dst = CAPTURE_DIR / f"capture_{cap['num']:02d}.png"
                if src.exists() and not dst.exists():
                    shutil.copy(src, dst)
                    auto_count += 1

    # 2) 체크리스트 .md 생성
    lines = [
        "# AI Sherpa 캡처 체크리스트",
        "",
        f"총 33 개 그림 자리 (UI {sum(1 for c in CAPTURES if c['kind']=='UI')} + CODE {sum(1 for c in CAPTURES if c['kind']=='CODE')})",
        "",
        f"**저장 위치**: `{CAPTURE_DIR}\\capture_NN.png`",
        "",
        f"**자동 채움**: 이미 {auto_count} 장 (jingyu captures) 복사됨 → 마음에 안 들면 같은 파일명으로 덮어쓰기",
        "",
        "## 캡처 도구 안내",
        "- **Win + Shift + S** → 영역 선택 → 클립보드에 복사",
        "- 또는 PowerShell 에서 `clip` 으로 붙여넣은 뒤 그림판/Snipping Tool 로 저장",
        "- 권장 해상도: **1920 × 1080** (16:9, 워드에 깔끔하게 맞음)",
        "- 파일명: `capture_01.png` ~ `capture_33.png` (번호 그대로)",
        "",
        "## 진행 순서 (백엔드 + 프론트 기동 후)",
        "```powershell",
        "# 백엔드 (PowerShell 1)",
        "cd backend; $env:TRIAGE_MODE='evidence_tree'",
        ".venv\\Scripts\\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload",
        "",
        "# 프론트엔드 (PowerShell 2)",
        "cd frontend; npm run dev",
        "# 브라우저: http://localhost:5173/",
        "```",
        "",
        "## 체크리스트",
        "",
        "| ☐ | # | 종류 | 제목 | 어디서 | 어떻게 | 자동 채움 |",
        "|---|---|------|------|--------|--------|-----------|",
    ]
    for cap in CAPTURES:
        auto_mark = f"✓ {cap['auto']}" if cap["auto"] else "—"
        lines.append(
            f"| ☐ | {cap['num']:02d} | {cap['kind']} | {cap['title']} | "
            f"{cap['where']} | {cap['how']} | {auto_mark} |"
        )
    lines += [
        "",
        "## 캡처 끝난 후",
        "",
        "```powershell",
        "python scripts/capture_helper.py status   # 진행률 확인",
        "python scripts/capture_helper.py fill     # docx 자동 삽입",
        "```",
    ]
    CHECKLIST_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"✅ 체크리스트 생성: {CHECKLIST_MD}")
    print(f"✅ 캡처 폴더 생성: {CAPTURE_DIR}")
    print(f"✅ 자동 매핑: {auto_count} 장 jingyu captures → capture_NN.png 복사")
    print()
    print(f"다음 단계:")
    print(f"  1. {CHECKLIST_MD.name} 열어두고 옆에 띄움")
    print(f"  2. 백엔드 + 프론트 기동 → 브라우저 1920x1080")
    print(f"  3. Win+Shift+S 로 캡처 → {CAPTURE_DIR.name}\\capture_NN.png 저장")
    print(f"  4. python scripts/capture_helper.py status 로 진행률 확인")


def cmd_status() -> None:
    """현재 캡처 진행률 확인."""
    if not CAPTURE_DIR.exists():
        print(f"❌ 캡처 폴더 없음 — 먼저 prep 실행")
        return
    done, missing = [], []
    for cap in CAPTURES:
        f = CAPTURE_DIR / f"capture_{cap['num']:02d}.png"
        (done if f.exists() else missing).append(cap)
    total = len(CAPTURES)
    print(f"진행률: {len(done)}/{total} ({len(done)*100//total}%)")
    print()
    if missing:
        print(f"━━ 남은 캡처 {len(missing)} 장 ━━")
        for cap in missing:
            print(f"  ☐ capture_{cap['num']:02d}.png — [{cap['kind']}] {cap['title']}")
            print(f"     · {cap['where']}")
    else:
        print("✅ 모든 캡처 완료! python scripts/capture_helper.py fill 실행")


def cmd_fill() -> None:
    """캡처 폴더의 PNG 모두 docx 에 자동 삽입."""
    if not CAPTURE_DIR.exists():
        print(f"❌ 캡처 폴더 없음 — 먼저 prep 실행")
        return
    doc = Document(str(SRC))
    inserted = 0
    skipped = []

    # 그림 캡션 단락 찾고 직전 단락에 이미지 삽입
    for cap in CAPTURES:
        png = CAPTURE_DIR / f"capture_{cap['num']:02d}.png"
        if not png.exists():
            skipped.append(cap["num"])
            continue
        # 본문에서 해당 캡션 단락 찾기
        caption_pat = re.compile(rf"^<그림\s*{cap['num']}\b")
        for i, p in enumerate(doc.paragraphs):
            if caption_pat.match(p.text.strip()):
                # 캡션 바로 위 단락에 이미지 삽입 (또는 캡션 단락에 이미지 + 캡션 분리)
                # 안전한 방법: 캡션 위에 새 단락 + 이미지
                new_p = p.insert_paragraph_before("")
                new_p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                run = new_p.add_run()
                run.add_picture(str(png), width=Cm(15))
                inserted += 1
                break

    doc.save(str(OUT))
    print(f"✅ 저장: {OUT.name}")
    print(f"   삽입 {inserted} 장 / 누락 {len(skipped)} 장: {skipped}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prep"
    if cmd == "prep":
        cmd_prep()
    elif cmd == "status":
        cmd_status()
    elif cmd == "fill":
        cmd_fill()
    else:
        print(f"사용법: python {sys.argv[0]} [prep|status|fill]")


if __name__ == "__main__":
    main()
