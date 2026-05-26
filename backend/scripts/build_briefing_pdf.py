"""dev3 → byungwoo 브리핑 PDF 생성 (2026-05-26 byungwoo).

reportlab + Malgun Gothic 한국어 폰트로 팀원 브리핑 PDF 산출.

내용 (동작 중심):
    1. 표지 + 한 줄 요약
    2. 무엇이 바뀌었나 (dev3 vs byungwoo 비교 표)
    3. 동작 흐름 5단계 (Cold start → 첫 단서 → IG 추천 → 가이드 미리보기 → 확정)
    4. 핵심 알고리즘 3종 (IG · Noisy-OR · depth 임계)
    5. 학술 근거 + 검증 결과
    6. 팀원 합의 필요 사항

출력: exports/dev3_vs_byungwoo_브리핑.pdf
사용: cd backend && .venv/Scripts/python.exe scripts/build_briefing_pdf.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


_BACKEND = Path(__file__).resolve().parents[1]
EXPORTS = _BACKEND / "exports"
EXPORTS.mkdir(exist_ok=True)
OUT_PDF = EXPORTS / "dev3_vs_byungwoo_브리핑.pdf"


# ─────────────────────────────────────────────────────────────
# 폰트 등록 — Malgun Gothic
# ─────────────────────────────────────────────────────────────


def register_fonts() -> tuple[str, str]:
    """시스템 Malgun Gothic 등록. 반환: (regular, bold) 이름."""
    win_fonts = Path("C:/Windows/Fonts")
    reg = win_fonts / "malgun.ttf"
    bold = win_fonts / "malgunbd.ttf"
    if not reg.exists():
        raise FileNotFoundError(f"Malgun Gothic 폰트 없음: {reg}")
    pdfmetrics.registerFont(TTFont("Malgun", str(reg)))
    pdfmetrics.registerFont(TTFont("Malgun-Bold", str(bold) if bold.exists() else str(reg)))
    return "Malgun", "Malgun-Bold"


# ─────────────────────────────────────────────────────────────
# 스타일
# ─────────────────────────────────────────────────────────────


def build_styles(font_reg: str, font_bold: str) -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName=font_bold,
            fontSize=22,
            textColor=colors.HexColor("#1a3a52"),
            spaceAfter=10,
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontName=font_reg,
            fontSize=11,
            textColor=colors.HexColor("#666666"),
            spaceAfter=4,
            alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName=font_bold,
            fontSize=15,
            textColor=colors.HexColor("#1a3a52"),
            spaceBefore=14,
            spaceAfter=6,
            leftIndent=0,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName=font_bold,
            fontSize=12,
            textColor=colors.HexColor("#26726E"),
            spaceBefore=10,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName=font_reg,
            fontSize=10,
            leading=15,
            spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["BodyText"],
            fontName=font_reg,
            fontSize=10,
            leading=14,
            leftIndent=16,
            bulletIndent=4,
            spaceAfter=2,
        ),
        "code": ParagraphStyle(
            "code",
            parent=base["Code"],
            fontName="Courier",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#333333"),
            backColor=colors.HexColor("#f4f4f4"),
            borderColor=colors.HexColor("#cccccc"),
            borderPadding=6,
            spaceBefore=4,
            spaceAfter=6,
        ),
        "callout": ParagraphStyle(
            "callout",
            parent=base["BodyText"],
            fontName=font_reg,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#664000"),
            backColor=colors.HexColor("#fff8e1"),
            borderColor=colors.HexColor("#ffc107"),
            borderPadding=8,
            spaceBefore=6,
            spaceAfter=6,
            leftIndent=4,
            rightIndent=4,
        ),
    }


# ─────────────────────────────────────────────────────────────
# 표 빌더
# ─────────────────────────────────────────────────────────────


def make_table(data: list[list], col_widths: list, font_reg: str, font_bold: str) -> Table:
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        # 헤더
        ("FONTNAME", (0, 0), (-1, 0), font_bold),
        ("FONTSIZE", (0, 0), (-1, 0), 9.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a52")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        # 본문
        ("FONTNAME", (0, 1), (-1, -1), font_reg),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#222222")),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#26726E")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafbfc")]),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


# ─────────────────────────────────────────────────────────────
# 본문 빌더
# ─────────────────────────────────────────────────────────────


def build_story(styles: dict, font_reg: str, font_bold: str) -> list:
    s = []

    def p(text: str, style: str = "body") -> Paragraph:
        return Paragraph(text, styles[style])

    # ── 표지 ──
    s.append(Spacer(1, 60))
    s.append(p("dev3 → byungwoo 브리핑", "title"))
    s.append(p("Evidence Tree 패러다임 전환 — 새 기능 동작 가이드", "subtitle"))
    s.append(Spacer(1, 24))
    s.append(p(f"작성: 2026-05-26 byungwoo · 39 commits · 56 files · +15,396 / −135", "subtitle"))
    s.append(p("대상: 로그아웃팀 (jingyu · geunhyung · jinkyu)", "subtitle"))
    s.append(Spacer(1, 40))

    s.append(p(
        '<b>핵심 변화</b>: dev3 의 정적 결정 트리 + 누적 합산 점수 →<br/>'
        'Evidence Tree (단서 트리) + Bayesian Network (Noisy-OR) 인과 추론.<br/><br/>'
        '<b>사용자 비전</b>: "어두운 맵을 단서로 밝혀가는 수사."<br/>'
        '<b>학술 청사진</b>: BAN paper (IEEE 2023) Bayesian Network + MITRE 합성 데이터.',
        "callout",
    ))

    s.append(PageBreak())

    # ── 1. 무엇이 바뀌었나 ──
    s.append(p("1. 무엇이 바뀌었나 — 4가지 알고리즘", "h1"))
    s.append(p(
        "팀원이 가장 먼저 알아야 할 4가지 변경. dev3 의 결정 트리는 그대로 보존되며 "
        "(TRIAGE_MODE=additive 기본값), evidence_tree 모드는 환경변수로만 활성화.",
        "body",
    ))

    table1 = make_table([
        ["항목", "dev3 (기존)", "byungwoo (신규)"],
        ["사전확률", "Verizon DBIR 통계 (RANSOM 27% 등)", "Uniform 1/8 (Jaynes Max Entropy)"],
        ["점수 누적", "score[h] += weight  (0 ~ 180)", "P(h|c) ∝ P(h) × P(c|h)  (0 ~ 1)"],
        ["다음 단서", "결정 트리 정적 옵션 5개", "Information Gain 동적 정렬 (143 풀)"],
        ["확정 정책", "score 임계값 도달 시 자동", "depth ≥ 3 + 임계 도달 시 알림만"],
    ], [3.2 * cm, 6.4 * cm, 6.4 * cm], font_reg, font_bold)
    s.append(table1)
    s.append(Spacer(1, 10))

    s.append(p(
        '<b>왜 바꿨나?</b> dev3 의 결정 트리는 "한 답변 = 한 lane" 으로 다른 사고유형 변별을 차단했다. '
        '사용자 비전은 <i>"단서 하나를 시작으로 가능성의 트리가 자라난다"</i> — 모든 가설을 '
        '동시에 추적하는 베이즈 모델이 필요했다.',
        "body",
    ))

    # ── 2. 동작 흐름 ──
    s.append(p("2. 동작 흐름 — V-1 Step 3 에서 어떻게 보이나", "h1"))
    s.append(p(
        "환경변수 TRIAGE_MODE=evidence_tree 설정 시 V-1 Step3 가 새 화면으로 분기. "
        "기존 흐름은 TRIAGE_MODE=additive (기본값) 으로 그대로 보존.",
        "body",
    ))

    s.append(p("2.1 진입 — Cold Start (빈 트리 + 횃불)", "h2"))
    s.append(p(
        "처음 V-1 Step 3 에 진입하면 트리에 <b>채택된 단서 0개</b>, 후보도 0개. "
        '"🔦 어두운 맵 — 첫 단서를 입력하세요" 안내만 노출.<br/><br/>'
        "<b>근거</b>: Uniform prior 에서 모든 단서의 변별력이 균등 → 추천 의미 미약. "
        "첫 단서가 횃불을 켜야 변별력 있는 후보가 등장한다.",
        "body",
    ))
    s.append(p(
        '<font color="#26726E"><b>UI 표시:</b></font> 트리 화면 중앙에 횃불 아이콘 + 좌측 '
        '"단서 직접 입력" / "부분 로그 분석" / 우측 플로팅 ✛ "LogAnalysisFab" 으로 진입.',
        "body",
    ))

    s.append(p("2.2 첫 단서 채택 → 트리 자라기", "h2"))
    s.append(p(
        "사용자가 직접 입력 (예: IP=Tor 출구) 하면 POST /api/clue-tree/expand 호출. "
        "백엔드:<br/>"
        "① 카탈로그 lookup → likelihood 변환<br/>"
        "② posterior 베이즈 갱신 (Uniform 1/8 → 첫 단서 후 50% 등)<br/>"
        "③ 다음 후보 IG 정렬<br/>"
        "④ DB 영속화 (incident_cases.triage_state JSON)<br/><br/>"
        "프론트는 응답 받아서 트리에 채택 노드 추가 (실선 brand-teal) + 우측 IG 후보 노출.",
        "body",
    ))

    s.append(p("2.3 IG 후보 추천 (Shannon Information Gain)", "h2"))
    s.append(p(
        "각 후보의 expected information gain 계산:<br/>"
        "IG(c) = H(P) − E[H(P|c)]<br/><br/>"
        "Marginalization 활성 (Pearl 1988) → 음성 evidence 도 계산. "
        "entropy 가 높을수록 (모호) 후보 5개, 낮을수록 (수렴) 2개 노출 (사용자 결정).<br/><br/>"
        '각 후보 카드에는 IG 게이지 막대 + 추천 이유 + outcome_flags 정형 Boolean badge (Google '
        'Chronicle 패턴) + ATT&CK 기법 ID badge.',
        "body",
    ))

    s.append(p("2.4 가설 가이드 미리보기 (신규 Phase K)", "h2"))
    s.append(p(
        "사용자 비전: <i>\"오른쪽에 상위 2개 뜨는거 클릭하면 수집가이드도 엿보는게 가능하면\"</i>.<br/><br/>"
        "우측 HypothesisScoreBar 의 가설 행 클릭 → GET /api/guide/preview?incidentType=RANSOMWARE 호출 → "
        "행 아래 inline expand (max-h-80 + 스크롤). Phase 별 Top 3 수집 대상 + REQUIRED red/CORROBORATING amber dot. "
        "[전체 가이드 보기 →] 클릭 → 트리 위 풀 모달 (팝업) — 전체 phases + 환경 경고 + 학술 인용 6종.<br/><br/>"
        "+ 가이드 기반 단서 후보 [+] 버튼 2개 — 휴리스틱 매핑 (14 룰) 으로 단서 카탈로그 추가 채택.",
        "body",
    ))

    s.append(p("2.5 사고유형 확정 가능 알림 (depth 차등 임계)", "h2"))
    s.append(p(
        "사용자 피드백 반영: <i>\"단서 2-3개 만으로 너무 빠른 확정\"</i>. "
        "depth 별 차등 임계값:",
        "body",
    ))

    table_thr = make_table([
        ["depth (채택 단서 수)", "auto_confirm", "gap", "정책"],
        ["1 ~ 2", "1.01 (차단)", "1.01 (차단)", "단서 부족 — 절대 도달 불가"],
        ["3", "0.80", "0.30", "엄격 — 충분히 확실해야 알림"],
        ["4", "0.75", "0.25", "중간"],
        ["5 이상", "0.65", "0.20", "표준 (Phase 3.5 fitted)"],
    ], [3.5 * cm, 2.8 * cm, 2.2 * cm, 7.5 * cm], font_reg, font_bold)
    s.append(table_thr)
    s.append(Spacer(1, 8))

    s.append(p(
        "도달 시 자동 종료 X — 우측에 \"사고유형 확정 가능 — RANSOMWARE 97.6%\" 카드 노출. "
        "[확정하고 다음 단계로] 또는 [단서 더 채택] 사용자 선택 (paradigm §16 정합).",
        "body",
    ))

    s.append(PageBreak())

    # ── 3. 핵심 알고리즘 ──
    s.append(p("3. 핵심 알고리즘 3종 — 학술 정합", "h1"))

    s.append(p("3.1 Information Gain (Shannon 1948)", "h2"))
    s.append(p(
        "단서 c 채택 시 사후확률 entropy 가 얼마나 줄어드는지 (= 변별력) 계산.",
        "body",
    ))
    s.append(Paragraph(
        "H_before = H(P) = −Σ p(h) log₂ p(h)<br/>"
        "P(c=1) = Σ p(h) × P(c|h)<br/>"
        "IG(c) = H(P) − P(c=1)·H(P|c=1) − P(c=0)·H(P|c=0)",
        styles["code"],
    ))
    s.append(p(
        "Marginalization (Pearl 1988) — 미관찰 단서 (c=0) 도 합산. "
        "BAN paper IEEE 2023 정합.",
        "body",
    ))

    s.append(p("3.2 Noisy-OR Bayesian Network (Pearl 1988)", "h2"))
    s.append(p(
        "PDF 청사진의 BN+CPT 핵심. 풀 CPT 는 143 단서 × 2^143 조합 = 계산 불가능 → "
        "Noisy-OR 가 부모 노드 독립 가정으로 파라미터를 <b>지수 → 선형</b> 스케일로 축소.",
        "body",
    ))
    s.append(Paragraph(
        "P(child=1 | parents) = 1 − Π (1 − p_i × parent_i × (1 − inhibitor_i))<br/><br/>"
        "p_leak       — 부모 없을 때 자발 발생 확률<br/>"
        "p_inhibitor  — 부모 활성화 시 자식 활성화 차단 확률",
        styles["code"],
    ))
    s.append(p(
        "구현: pgmpy 라이브러리의 NoisyOrCPD 클래스. UC Berkeley·CMU 학술 표준 (Ankan & Panda 2015). "
        "5MB pip 설치 — 폐쇄망 친화.",
        "body",
    ))

    s.append(p("3.3 합성 데이터 (PDF §17.B 보강)", "h2"))
    s.append(p(
        "기업 기밀 침해 데이터 대신 MITRE 공개 자원 3종 학습:",
        "body",
    ))
    table_data = make_table([
        ["소스", "용량", "정보"],
        ["Atomic Red Team", "160 MB / 334 YAML", "ATT&CK 기법 prerequisite 64% (~210 edge)"],
        ["ATT&CK Flow", "22 MB / 40 .afb", "실제 사고 시퀀스 (Black Basta, Conti, Equifax 등)"],
        ["ATT&CK STIX", "51 MB / 25,843 obj", "189 APT × 18,220 group→technique uses"],
    ], [3.5 * cm, 3.5 * cm, 9.0 * cm], font_reg, font_bold)
    s.append(table_data)
    s.append(Spacer(1, 6))
    s.append(p(
        "<b>총 ~수만 transition signal</b> = PDF 의 \"수만 침해사고 데이터\" 학술적 등가. "
        "1회 학습 후 정적 JSON (data/triage/clue_dag.json) 운영 — 폐쇄망 정합.",
        "body",
    ))

    s.append(PageBreak())

    # ── 4. 새 컴포넌트 ──
    s.append(p("4. 새 컴포넌트 — 어디에 있나", "h1"))

    table_comp = make_table([
        ["파일", "줄수", "역할"],
        ["core/intake/clue_tree.py", "384", "ClueTreeNode + entropy + depth 차등 임계"],
        ["core/intake/clue_tree_service.py", "402", "start/expand/suggest/get/reset + DB 영속화"],
        ["core/intake/info_gain.py", "283", "KL divergence + Marginalization"],
        ["core/intake/bayes_net.py", "384", "pgmpy NoisyOrCPD 추론"],
        ["api/clue_tree.py", "222", "REST 5종 + reset + explain"],
        ["data/triage/clue_catalog.json", "143 단서", "decision_tree + clue_types + ATT&CK 통합"],
        ["data/triage/clue_to_attack.json", "1216 매핑", "단서 → ATT&CK 자동 + 수동 보강"],
        ["components/ClueTreeView.tsx", "481", "react-flow 단서 트리 (drift anchor)"],
        ["components/IncidentTypeCompass.tsx", "501", "360° 컴퍼스 시각화 (탭 토글)"],
        ["components/LogAnalysisFab.tsx", "408", "플로팅 실시간 로그 분석"],
        ["components/NextCluePanel.tsx", "+381", "IG 모드 + ATT&CK badge + 추천 이유"],
        ["components/GuidePreviewModal.tsx", "276", "Phase K 풀 가이드 팝업"],
        ["components/HypothesisScoreBar.tsx", "+363", "inline 가이드 미리보기"],
        ["utils/guideToClueMatcher.ts", "133", "가이드 → 단서 14 룰 매핑"],
    ], [6.5 * cm, 2.0 * cm, 7.5 * cm], font_reg, font_bold)
    s.append(table_comp)

    # ── 5. 검증 결과 ──
    s.append(p("5. 검증 결과", "h1"))

    s.append(p("5.1 e2e 회귀 — 3 모드 모두 47/47 통과", "h2"))
    table_e2e = make_table([
        ["TRIAGE_MODE", "결과", "lane 분포"],
        ["additive (dev3 호환)", "47/47", "CRED 12, INSIDER 12, MISCFG 6, RANSOM 9, ROUTER 3, SHORT 4, TERM 1"],
        ["bayesian", "47/47", "동일 (composite 가설 허용)"],
        ["evidence_tree", "47/47", "47 시나리오 단서 시퀀스 학술 정합 입증"],
    ], [3.5 * cm, 2.0 * cm, 10.5 * cm], font_reg, font_bold)
    s.append(table_e2e)

    s.append(p("5.2 pytest — 137 신규 + 기존 fail 7건 동시 해결", "h2"))
    s.append(p(
        "<b>신규 모듈 테스트</b>:<br/>"
        "• test_clue_tree.py — 21 (자료구조·entropy·depth throttle)<br/>"
        "• test_clue_tree_service.py — 14 (DB 영속화·cold-start)<br/>"
        "• test_info_gain.py — 16 (KL divergence·Marginalization)<br/>"
        "• test_bayes_net.py — pgmpy NoisyOrCPD 추론<br/>"
        "• test_clue_to_attack.py — 단서 → ATT&CK 매핑 무결성<br/>"
        "• test_bayesian.py — 베이즈 갱신 + Laplace smoothing<br/>"
        "• test_collection_guide_v2.py — 65 (preview 회귀 0)<br/><br/>"
        "<b>기존 fail 7건 해결</b> (commit aef5cd9):<br/>"
        "• matchers 3건 (naver DATA/PHISH, nhn PHISH)<br/>"
        "• INSIDER T3 4건 (composite 가설 허용 정책)",
        "body",
    ))

    s.append(PageBreak())

    # ── 6. 학술 인용 ──
    s.append(p("6. 학술 인용 — 발표·논문용", "h1"))

    s.append(p("기본 패러다임", "h2"))
    bullets = [
        "<b>Pearl 1988</b> — Probabilistic Reasoning in Intelligent Systems (Bayesian Belief Propagation + Noisy-OR §3.2.2)",
        "<b>Peirce 1903</b> — Abductive Reasoning (Hypothesis Selection)",
        "<b>Shannon 1948</b> — A Mathematical Theory of Communication (Information Gain)",
        "<b>Jaynes 1968</b> — Prior Probabilities (Maximum Entropy)",
    ]
    for b in bullets:
        s.append(Paragraph(f"• {b}", styles["bullet"]))

    s.append(p("도메인 표준", "h2"))
    bullets2 = [
        "<b>MITRE ATT&CK Cloud Matrix v14</b> — 단서 → 사고유형 매핑",
        "<b>MITRE Atomic Red Team</b> (Red Canary) — TTP YAML 정의, 합성 데이터 표준",
        "<b>MITRE ATT&CK Flow</b> (Center for Threat-Informed Defense) — 실제 사고 시퀀스",
        "<b>Verizon DBIR 2024</b> — 침해사고 통계",
    ]
    for b in bullets2:
        s.append(Paragraph(f"• {b}", styles["bullet"]))

    s.append(p("외부 청사진", "h2"))
    bullets3 = [
        "<b>BAN paper</b> — Predicting APT Attack Based on Bayesian Network With MITRE ATT&CK (IEEE Xplore 2023)",
        "<b>Microsoft Security Blog</b> — Automating threat actor tracking (2021)",
        "<b>Google Chronicle</b> — Rule-to-Outcome Workflow (Outcome Contract 패턴)",
        "<b>Palo Alto</b> — Cloud Token Theft Response Playbook (Verdict Decision Tree)",
    ]
    for b in bullets3:
        s.append(Paragraph(f"• {b}", styles["bullet"]))

    s.append(p("라이브러리", "h2"))
    bullets4 = [
        "<b>pgmpy</b> (Ankan & Panda 2015) — Python Library for Probabilistic Graphical Models (UC Berkeley·CMU 표준)",
        "<b>networkx</b> — Phase J GDS (PageRank·Label Propagation, V-7 보드 강화)",
    ]
    for b in bullets4:
        s.append(Paragraph(f"• {b}", styles["bullet"]))

    s.append(Spacer(1, 16))

    # ── 7. 합의 필요 ──
    s.append(p("7. 팀원 합의 필요 사항", "h1"))

    bullets_5 = [
        "<b>dev3 → byungwoo 머지</b>: additive 호환 보장 (TRIAGE_MODE 기본값) 확인 필요",
        "<b>의존성 추가</b>: pgmpy ≥ 0.1.25 + pyyaml ≥ 6.0 + networkx ≥ 3.0 → requirements.txt 반영",
        "<b>외부 데이터</b>: backend/data/triage/external_sources/ (250 MB) — zip 별도 전달 (gitignore)",
        "<b>DB 스키마 무변경</b>: incident_cases.triage_state JSON 컬럼 sub-key 만 추가 — 마이그레이션 불필요",
    ]
    for b in bullets_5:
        s.append(Paragraph(f"• {b}", styles["bullet"]))

    s.append(p("다음 단계 후보 (사용자 확정 대기)", "h2"))
    s.append(p(
        "<b>L.</b> Negative evidence UI — Marginalization 음성 단서 명시 입력<br/>"
        "<b>M.</b> CPT 학습 데이터 보강 — Atomic 외 KISA 사례·DBIR 통계 통합<br/>"
        "<b>N.</b> V-7 수사보드 연동 — Evidence Tree → ChainNode 자동 시드",
        "body",
    ))

    s.append(Spacer(1, 12))
    s.append(p(
        '<font color="#888888">문의: byungwoo (팀장). 다음 회의: dev3 머지 합의 + L/M/N 선택.<br/>'
        f'생성: {datetime.now().isoformat(timespec="seconds")} — reportlab + Malgun Gothic.</font>',
        "subtitle",
    ))

    return s


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────


def main() -> int:
    font_reg, font_bold = register_fonts()
    styles = build_styles(font_reg, font_bold)
    story = build_story(styles, font_reg, font_bold)

    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="dev3 → byungwoo 브리핑",
        author="byungwoo",
    )

    # 페이지 번호 footer
    def _footer(canvas, doc):  # noqa: ARG001
        canvas.saveState()
        canvas.setFont(font_reg, 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(18 * mm, 8 * mm, "dev3 → byungwoo 브리핑 · Evidence Tree 패러다임")
        canvas.drawRightString(
            A4[0] - 18 * mm, 8 * mm, f"{doc.page}"
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    size_kb = OUT_PDF.stat().st_size / 1024
    print(f"[ok] PDF 생성 완료 → {OUT_PDF}")
    print(f"     크기: {size_kb:.1f} KB · 페이지: ~{doc.page}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
