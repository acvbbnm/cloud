"""Ⅸ. 구현 워드 docx 제작 v2 — byungwoo 브랜치 Phase P.17 head 기준.

이전 v1 대비 추가:
- Phase O.1: chain_nodes.meta JSON 컬럼 + Tree → Board bridge (POST /api/board/nodes/from-clue-tree)
- Phase N: Stage Transition (POST /api/clue-tree/advance-stage)
- Phase N.1: 1차 정찰 가이드 (GET /api/clue-tree/recon-options)
- Phase P.7: ChainGraph zoom/pan + Kill Chain 전체 표시
- Phase P.16~17: 콜드스타트 fix + 회귀권고 polyline + depth 라벨 점프
- LogAnalysisFab 백엔드 (POST /api/triage/analyze-logs)
- 가설별 신뢰도 sparkline (HypothesisBreakdownChart, GET /api/triage/breakdown)

6 대절 구조는 사용자 지정 그대로:
  1. 사고 접수 5단계 위저드 (Layer 0)
  2. Evidence Tree (단서 트리)
  3. V-2 Logs (Layer 1 로그 수집 + 무결성)
  4. Layer 2 분석 엔진 (V-3·V-6·V-4)
  5. AI 셰르파 RAG (V-8)
  6. 수사 보드 + 보고서 (V-5·V-7)
"""
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Cm, Pt, RGBColor

sys.stdout.reconfigure(encoding="utf-8")

CAPTURES = Path("docs/draft_final_report/options/captures")
OUT = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\Ⅸ_구현_AI_Sherpa_v2.docx"
)


def add_heading(doc, text: str, level: int):
    return doc.add_heading(text, level=level)


def add_para(doc, text: str, *, bold=False, italic=False, color=None, size=None):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor(*color)
    if size is not None:
        run.font.size = Pt(size)
    return p


def add_caption(doc, text: str):
    p = doc.add_paragraph()
    p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(10)
    return p


def add_image_with_guide(doc, img_path: Path, caption: str, what: str, how_to_replace: str):
    p_img = doc.add_paragraph()
    p_img.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    run = p_img.add_run()
    if img_path.exists():
        run.add_picture(str(img_path), width=Cm(15))
    else:
        run.add_text(f"[이미지 없음: {img_path.name}]")
    add_caption(doc, caption)
    for prefix, txt in [("└─ 이 이미지: ", what), ("└─ 교체 가이드: ", how_to_replace)]:
        p = doc.add_paragraph()
        p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        r = p.add_run(prefix + txt)
        r.italic = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)


def add_code_block(doc, caption: str, code_text: str, file_path: str):
    add_caption(doc, caption)
    table = doc.add_table(rows=1, cols=1)
    table.style = "Light Grid Accent 1"
    cell = table.rows[0].cells[0]
    cell.text = code_text
    for p in cell.paragraphs:
        for r in p.runs:
            r.font.name = "Consolas"
            r.font.size = Pt(9)
    p = doc.add_paragraph()
    r = p.add_run(f"└─ 경로: {file_path}")
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)


def add_steps(doc, steps: list[str]):
    for i, step in enumerate(steps, 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.8)
        p.add_run(f"{i}. {step}")


def add_table_data(doc, caption: str, header: list[str], rows: list[list[str]]):
    add_caption(doc, caption)
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.style = "Light Grid Accent 1"
    for ci, h in enumerate(header):
        cell = t.rows[0].cells[ci]
        cell.text = h
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(10)
    for ri, row in enumerate(rows, 1):
        for ci, val in enumerate(row):
            cell = t.rows[ri].cells[ci]
            cell.text = val
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)


def main() -> None:
    doc = Document()

    # 표지
    add_para(doc, "세종대학교 정보보호학과 캡스톤디자인 2026-1", size=10)
    add_para(doc, "AI Sherpa 최종보고서", bold=True, size=18)
    add_para(doc, "국내 멀티 클라우드 환경 침해사고 분석 및 대응", size=12)
    add_para(doc, "구현 단원 (byungwoo 브랜치 Phase P.17 기준)", size=11)
    add_para(doc, "")
    add_para(
        doc,
        "※ 본 문서는 6 대절 (Layer 0 위저드 / Evidence Tree / Layer 1 로그 / "
        "Layer 2 분석 / Layer 3 AI 셰르파 / Layer 4 보드·보고서) 으로 V1~V8 "
        "8 개 뷰 캡처 + 백엔드 코드 발췌 + 동작 단계 리스트를 임베드한 "
        "구현 단원 (Phase J~P 모든 신규 모듈 반영).",
        italic=True, size=9, color=(0x66, 0x66, 0x66),
    )
    doc.add_page_break()

    # ── Ⅸ. 구현 ────────────────────────────────────────────────────
    add_heading(doc, "Ⅸ. 구현", 1)
    add_para(
        doc,
        "본 장에서는 설계 단원에서 정의한 5계층 파이프라인 아키텍처에 따라 "
        "실제 구현된 모듈을 6 대절로 기술한다. 각 대절은 백엔드 비즈니스 로직 "
        "(core/), REST 라우터 (api/), 프론트엔드 뷰 (views/) 의 3 축을 함께 "
        "다루며, byungwoo 브랜치 Phase J~P 의 신규 모듈 (graph_analytics / "
        "BayesNet / Evidence Tree 143 단서 풀 / 2-zone 컴퍼스 / Stage "
        "Transition Matrix / chain_nodes.meta / MultiStageBoard) 까지 모두 "
        "반영한다."
    )

    # ── 1. 사고 접수 5단계 위저드 (Layer 0) ──────────────────────
    add_heading(doc, "1. 사고 접수 5단계 위저드 (Layer 0)", 2)
    add_para(
        doc,
        "수사관이 V1 Setup 의 5단계 위저드 (Step 0~4) 를 통해 사고 케이스를 "
        "생성한다. dev3 안정화에서 흐름이 5단계로 분리되었고, Phase P.16 "
        "콜드스타트 fix 로 빈 케이스의 트리 초기화·잔존 데이터 정리가 보강되었다. "
        "Step 3 (Discovery Loop) 은 Evidence Tree 패러다임의 진입점이다 (2. 절)."
    )

    add_heading(doc, "1) Step 0~4 5단계 위저드 흐름", 3)
    add_image_with_guide(
        doc, CAPTURES / "V_setup.png",
        "<그림 Ⅸ-1-1> V1 Setup — 빈 케이스 (5단계 진행바 + CSP 카드)",
        what="V1 Setup 진입 직후 빈 케이스 (CSP 카드 + 5단계 진행바 + 사이드바 NEW CASE)",
        how_to_replace="시연 환경 V-1 진입 → CSP 미선택 → Win+Shift+S 1920x1080 영역 캡쳐",
    )
    add_image_with_guide(
        doc, CAPTURES / "V_setup_with_case.png",
        "<그림 Ⅸ-1-2> V1 Setup — 케이스 진행 중 (Step 2 시스템 구성)",
        what="CSP 선택 후 Step 2 시스템 구성 (Object Storage / MFA / 환경 변경자) 입력 중간",
        how_to_replace="V-1 Step 2 → 일부 체크박스 토글 → 1920x1080 영역 캡쳐",
    )

    add_code_block(
        doc,
        "<코드 Ⅸ-1-1> POST /api/cases — 사고 케이스 생성 API",
        '@router.post("/cases", response_model=CaseResponse)\n'
        "async def create_case(req: CreateCaseRequest, db: Session = Depends(get_db)):\n"
        '    """사고 케이스를 신규 생성한다 (UNCLASSIFIED 허용)."""\n'
        "    case = IncidentCase.create(\n"
        "        incident_type=req.incident_type or 'UNCLASSIFIED',\n"
        "        csp=req.csp, severity=req.severity,\n"
        "        system_config=req.system_config,\n"
        "    )\n"
        "    db.add(case); db.commit()\n"
        "    action_logs.record(case.case_id, 'ACCEPT', 'create_case')\n"
        '    return {"status": "ok", "data": {"caseId": case.case_id}}\n',
        "backend/api/intake.py",
    )
    add_steps(doc, [
        "multipart 입력 검증 (CSP·incident_type·severity)",
        "IncidentCase 객체 생성 + UUID 부여 (UNCLASSIFIED 허용)",
        "incident_cases INSERT (triage_state=DISCOVERY 초기값)",
        "Phase P.16 — 콜드스타트 시 잔존 단서 트리 자동 초기화",
        "action_logs 에 ACCEPT 기록 + case_id 반환",
    ])

    add_heading(doc, "2) CollectionGuideV2 + Phase K /api/guide/preview", 3)
    add_para(
        doc,
        "GET /api/guide/v2?caseId= 가 사고유형 × CSP 조합의 우선순위 수집 "
        "체크리스트를 생성한다. Phase K 에서 추가된 GET /api/guide/preview 는 "
        "사고유형 확정 전에도 가설별 가이드를 미리보기로 보여주며, V1 Step 3 "
        "에서 우측 가설 카드 클릭 시 inline expand 된다."
    )
    add_table_data(
        doc,
        "<표 Ⅸ-1> 사고유형 × CSP 시드 매트릭스 (9 × 2 = 18칸, 77행 누적)",
        ["사고유형", "NCP", "NHN", "주요 layer"],
        [
            ["CREDENTIAL_THEFT", "8", "6", "iam · audit"],
            ["PRIVILEGE_ESCALATION", "5", "4", "iam"],
            ["DATA_EXFILTRATION", "6", "5", "storage · network"],
            ["AUDIT_LOG_TAMPERING", "4", "3", "audit"],
            ["RANSOMWARE", "5", "4", "storage"],
            ["MISCONFIG_EXPOSURE", "4", "3", "iam · network"],
            ["PHISH_INITIAL_ACCESS", "5", "4", "iam · audit"],
            ["INSIDER_THREAT", "4", "3", "iam · audit"],
            ["MULTI_CSP_LATERAL", "3", "3", "network · iam"],
        ],
    )
    add_code_block(
        doc,
        "<코드 Ⅸ-1-2> GET /api/guide/preview — 가설별 미리보기 (Phase K.1)",
        "@router.get('/guide/preview')\n"
        "async def preview(case_id: str, hypothesis: str) -> dict:\n"
        '    """사고유형 확정 전 가설별 가이드 미리보기."""\n'
        "    case = db.query(IncidentCase).get(case_id)\n"
        "    targets = load_collection_targets(hypothesis, case.csp)\n"
        "    targets.sort(key=lambda t: (t.evidence_role != 'REQUIRED', t.layer))\n"
        "    return {'items': [t.dict() for t in targets[:5]], 'preview': True}\n",
        "backend/core/intake/collection_guide_v2.py (generate_preview 메서드)",
    )
    add_steps(doc, [
        "case 의 csp 조회 (incident_type 미확정 허용)",
        "수사관이 클릭한 가설 (예: RANSOMWARE) 의 시드 로드",
        "evidence_role REQUIRED 5건만 추려 inline 표시",
        "사용자가 [전체 가이드 보기] 클릭 시 풀 가이드 모달 팝업",
        "확정 후 incident_cases.incident_type 갱신",
    ])

    # ── 2. Evidence Tree (단서 트리) ───────────────────────────────
    add_heading(doc, "2. Evidence Tree — 단서 트리 추적 (Phase K~N)", 2)
    add_para(
        doc,
        "V1 Step 3 의 결정 트리 패러다임을 단서 (Clue) 기반 베이지안 네트워크로 "
        "재설계한 핵심 모듈이다. 143 개의 단서 풀과 8 종 사고유형 간의 사후확률을 "
        "Bayesian Network 로 계산하여 수사관에게 다음 탐색 대상을 추천한다. "
        "pgmpy 1.1.2 Noisy-OR (Pearl 1988) + Robust Bayes ε-contamination "
        "Floor 1% (Phase N.2) + 외부 학습 데이터 (Atomic Red Team 355 YAML + "
        "ATT&CK Flow 51 .afb + STIX enterprise-attack.json 51MB) 로 신뢰도를 확보한다."
    )

    add_heading(doc, "1) V1 Step 3 — 2-zone 컴퍼스 + 143 단서 풀 (Phase L~M)", 3)
    add_image_with_guide(
        doc, CAPTURES / "V_setup_with_case.png",
        "<그림 Ⅸ-2-1> V1 Step 3 — Evidence Tree 컴퍼스 (Stage 1 진행 중)",
        what="V1 Step 3 단계 — 현재 V_setup_with_case.png 재사용 (placeholder)",
        how_to_replace="byungwoo 브랜치에서 V-1 Step 3 진입 → 2-zone 컴퍼스 + 단서 풀 + 가설 카드 표시 상태 캡쳐 (TRIAGE_MODE=evidence_tree)",
    )

    add_table_data(
        doc,
        "<표 Ⅸ-2> Bayesian Network 통계 (Phase L~N 안정화)",
        ["항목", "수치", "비고"],
        [
            ["단서 풀 (Clue Pool)", "143 종", "Phase L.5 override 137 추가"],
            ["사고유형 (Hypothesis)", "8 종 + UNCLASSIFIED", "9 enum"],
            ["ATT&CK 기법 (3-layer DAG)", "30 distinct", "단서 → 사고유형 → 기법"],
            ["사후확률 갱신", "Noisy-OR CPD", "Pearl 1988"],
            ["Prior", "Maximum Entropy 균등 (Uniform 1/8)", "Jaynes 1968"],
            ["Robust Bayes Floor", "ε = 1% (Phase N.2)", "너무 빠른 확정 차단"],
            ["외부 학습 — Atomic Red Team", "355 YAML", "Phase H.1"],
            ["외부 학습 — ATT&CK Flow", "51 .afb", "Phase H.2"],
            ["외부 학습 — ATT&CK STIX", "51 MB JSON", "858 techniques + 189 APT"],
        ],
    )
    add_code_block(
        doc,
        "<코드 Ⅸ-2-1> BayesNet — Noisy-OR aggregation + Robust Bayes",
        "from pgmpy.models import BayesianNetwork\n"
        "from pgmpy.inference import VariableElimination\n\n"
        "class BayesNet:\n"
        "    EPSILON = 0.01  # Phase N.2 Robust Bayes floor\n\n"
        "    def update_posterior(self, observed_clues: list[str]) -> dict:\n"
        '        """관측된 단서로 8 사고유형 사후확률 갱신."""\n'
        "        evidence = {c: 1 for c in observed_clues}\n"
        "        infer = VariableElimination(self.model)\n"
        "        posterior = infer.query(['hypothesis'], evidence=evidence)\n"
        "        # ε-contamination floor — 너무 빠른 확정 차단\n"
        "        for h in posterior.values:\n"
        "            posterior[h] = max(posterior[h], self.EPSILON)\n"
        "        return normalize(posterior)\n",
        "backend/core/intake/bayes_net.py",
    )
    add_steps(doc, [
        "pgmpy 1.1.2 의 3-layer DAG 구축 (단서 → 사고유형 → ATT&CK)",
        "Noisy-OR CPD 로 다중 단서 결합 사후확률 계산 (Pearl 1988)",
        "Maximum Entropy 균등 prior 적용 (Uniform 1/8, Jaynes 1968)",
        "Robust Bayes ε-contamination Floor 1% (너무 빠른 확정 차단)",
        "depth 별 차등 임계값 (adda0ac fix) 으로 단계적 신뢰도 확보",
    ])

    add_heading(doc, "2) Stage Transition Matrix + MultiStageBoard (Phase N.3~4)", 3)
    add_para(
        doc,
        "Stage 1 (1차 정찰) → Stage 2 (확증) → Stage 3 (분석) 자동 전이. 각 "
        "Stage 종료 조건 (top-1 사후확률 ≥ 80% AND gap-to-2nd ≥ 20%) 충족 시 "
        "다음 Stage 단서 풀을 추천한다. 가설별 신뢰도 시계열은 "
        "HypothesisBreakdownChart 의 sparkline 으로 누적된다."
    )
    add_code_block(
        doc,
        "<코드 Ⅸ-2-2> POST /api/clue-tree/advance-stage — Stage 전이",
        "@router.post('/clue-tree/advance-stage')\n"
        "async def advance_stage(case_id: str) -> dict:\n"
        "    case = db.query(IncidentCase).get(case_id)\n"
        "    posterior = bayes_net.current_posterior(case_id)\n"
        "    top1, top2 = sorted(posterior.values(), reverse=True)[:2]\n"
        "    if top1 >= 0.80 and (top1 - top2) >= 0.20:\n"
        "        case.stage = next_stage(case.stage)\n"
        "        next_clues = stage_transition_matrix[case.stage]\n"
        "        return {'status': 'TRANSITIONED', 'next_clues': next_clues}\n"
        "    return {'status': 'STAY', 'reason': 'threshold not met'}\n",
        "backend/api/intake.py (clue_tree 라우터)",
    )
    add_steps(doc, [
        "Stage 1 종료 조건: top-1 사후확률 ≥ 80% AND gap-to-2nd ≥ 20%",
        "Stage Transition Matrix 호출 — 다음 단계 단서 풀 추천",
        "가설별 신뢰도 시계열 누적 (HypothesisBreakdownChart sparkline)",
        "GET /api/triage/breakdown — 시계열 데이터 응답",
        "사용자 ACCEPT 시 incident_cases.triage_state=TRIAGED 갱신",
    ])

    add_heading(doc, "3) 1차 정찰 가이드 카드 + 단서 메타 풍부화 (Phase L.6 + N.1)", 3)
    add_para(
        doc,
        "GET /api/clue-tree/recon-options 가 트리 진입 직후 빈 상태에서 1차 "
        "정찰 추천 단서를 제공한다. 각 단서는 정의·NCP/NHN 콘솔 경로·예시·"
        "근거 (TECHNIQUE 27 단서는 실제 콘솔 흔적) 메타를 가진다 (Phase L.6)."
    )
    add_code_block(
        doc,
        "<코드 Ⅸ-2-3> GET /api/clue-tree/recon-options — 1차 정찰 추천",
        "@router.get('/clue-tree/recon-options')\n"
        "async def recon_options(case_id: str) -> dict:\n"
        "    case = db.query(IncidentCase).get(case_id)\n"
        "    # Information Gain 기준 상위 5개 단서 추천\n"
        "    candidates = clue_pool.rank_by_ig(case.csp, depth=0, k=5)\n"
        "    return {'options': [c.with_meta() for c in candidates]}\n",
        "backend/api/intake.py (clue_tree 라우터)",
    )
    add_steps(doc, [
        "Information Gain (KL divergence) 으로 단서 우선순위 정렬",
        "CSP 별 콘솔 경로 (NCP / NHN) 메타 첨부",
        "예시 + 근거 (실제 콘솔 흔적) 첨부 — 수사관이 즉시 행동 가능",
        "depth=0 (빈 트리) 일 때 5 개 후보 반환",
        "수사관 선택 시 BayesNet 사후확률 갱신",
    ])

    # ── 3. V-2 Logs ─────────────────────────────────────────────
    add_heading(doc, "3. V-2 Logs — 로그 수집 및 무결성 검증 (Layer 1)", 2)
    add_para(
        doc,
        "multipart/form-data 로 업로드된 CSP 로그를 SHA-256 으로 무결성 검증한 "
        "뒤, CSP 별 파서로 raw 이벤트를 분해하여 raw_events 에 적재한다. "
        "동시에 16 매처가 9 사고유형 × 2 CSP 신호를 자동 탐지한다. dev3 에서 "
        "추가된 LogAnalysisFab 은 업로드 진행 중 실시간 매칭률·룰·갭 후보를 "
        "보여주는 보조 패널이다 (POST /api/triage/analyze-logs 백엔드 호출)."
    )

    add_heading(doc, "1) DropZone 업로드 + 매칭 분포 + LogAnalysisFab", 3)
    add_image_with_guide(
        doc, CAPTURES / "V_logs.png",
        "<그림 Ⅸ-3-1> V2 Logs — 빈 케이스 (DropZone + 4 KPI 카드)",
        what="V-2 진입 직후 DropZone + 4 KPI 카드 (총 수집/매칭/미매칭/파일) + 매칭 분포 빈 패널",
        how_to_replace="V-2 진입 후 빈 케이스 상태 1920x1080 캡쳐",
    )
    add_image_with_guide(
        doc, CAPTURES / "V_logs_with_case.png",
        "<그림 Ⅸ-3-2> V2 Logs — 13 events 업로드 후 + LogAnalysisFab 패널",
        what="Sysdig 시나리오 13 events 업로드 후 매칭 분포 + 우하단 LogAnalysisFab 플로팅",
        how_to_replace="13 events JSON 업로드 → 매칭률 표시 + Fab 클릭 → 실시간 분석 패널 펼친 상태 캡쳐",
    )
    add_code_block(
        doc,
        "<코드 Ⅸ-3-1> LogIngestor — SHA-256 + 멀티파트 수집",
        "class LogIngestor:\n"
        '    """raw 로그 → SHA-256 → CSP 별 파서 → raw_events INSERT."""\n'
        "    def ingest(self, file: UploadFile, case_id: str) -> IngestionStats:\n"
        "        content = file.file.read()\n"
        "        if len(content) > 5 * 1024 * 1024:\n"
        '            raise HTTPException(400, "5MB 초과")\n'
        "        sha256 = hashlib.sha256(content).hexdigest()\n"
        "        parser = parsers.get(self.csp)\n"
        "        events = parser.parse(content)\n"
        "        for ev in events:\n"
        "            matched = matchers.run(ev, case.incident_type)\n"
        "            db.add(RawEvent(case_id=case_id, raw_json=ev,\n"
        "                            raw_sha256=sha256, matched_signal=matched))\n"
        "        db.commit()\n"
        "        return IngestionStats(total=len(events), matched=...)\n",
        "backend/core/ingestion/log_ingestor.py",
    )
    add_steps(doc, [
        "multipart/form-data 수신 + 5MB 크기 제한",
        "SHA-256 해시 계산 후 raw_events.raw_sha256 저장",
        "CSP 별 파서 분기 (NCP Activity Tracer / NHN Cloud Trail)",
        "매처 호출 (16 종, 9 사고유형 × 2 CSP)",
        "raw_events INSERT + IngestionStats 갱신",
    ])

    add_heading(doc, "2) LogAnalysisFab 백엔드 — POST /api/triage/analyze-logs", 3)
    add_code_block(
        doc,
        "<코드 Ⅸ-3-2> LogAnalysisFab 백엔드 — 실시간 분석",
        "@router.post('/triage/analyze-logs')\n"
        "async def analyze_logs(case_id: str) -> dict:\n"
        "    raws = db.query(RawEvent).filter_by(case_id=case_id).all()\n"
        "    matched = [r for r in raws if r.matched_signal]\n"
        "    # 매처별 매칭률 + 매핑 룰 후보 + 갭 후보\n"
        "    return {\n"
        "        'total': len(raws),\n"
        "        'matched': len(matched),\n"
        "        'match_rate': len(matched) / len(raws) if raws else 0,\n"
        "        'matchers': group_by_matcher(matched),\n"
        "        'gap_candidates': gap_detector.preview(case_id),\n"
        "    }\n",
        "backend/api/triage.py",
    )
    add_steps(doc, [
        "현재 케이스의 raw_events 조회",
        "매처별 매칭률 + 매핑 룰 후보 + 갭 후보 집계",
        "프론트엔드 useLogAnalysis 훅이 5 초마다 polling",
        "Fab 클릭 시 패널 펼침 + 결과 표시",
        "Phase J 의 graph_analytics 결과와 연동",
    ])

    add_table_data(
        doc,
        "<표 Ⅸ-3> 16 매처 일람 (사이클 6 누적 매칭률 92.2%)",
        ["사고유형", "NCP 매처", "NHN 매처", "주요 신호"],
        [
            ["CREDENTIAL_THEFT", "match_ncp_credential", "match_nhn_credential", "비국내 IP + MFA 우회"],
            ["PRIVILEGE_ESCALATION", "match_ncp_priv_esc", "match_nhn_priv_esc", "S3FullAccess 부여"],
            ["DATA_EXFILTRATION", "match_ncp_exfil", "match_nhn_exfil", "대량 GetObject"],
            ["RANSOMWARE", "match_ncp_ransom", "match_nhn_ransom", "암호화 후 덮어쓰기"],
            ["AUDIT_LOG_TAMPERING", "match_ncp_audit", "match_nhn_audit", "감사 로그 비활성화"],
            ["MISCONFIG_EXPOSURE", "match_ncp_miscfg", "match_nhn_miscfg", "0.0.0.0/0 허용"],
            ["PHISH_INITIAL_ACCESS", "match_ncp_phish", "match_nhn_phish", "OTP 실패 후 성공"],
            ["INSIDER_THREAT", "match_ncp_insider", "match_nhn_insider", "비업무시간 자기권한"],
        ],
    )

    # ── 4. Layer 2 분석 엔진 ───────────────────────────────────
    add_heading(doc, "4. Layer 2 분석 엔진 — OCSF · ATT&CK · 갭 (V-3·V-6·V-4)", 2)
    add_para(
        doc,
        "Layer 2 는 CSP 별 원본 로그를 OCSF 1.3 표준 스키마로 정규화한 뒤, "
        "MITRE ATT&CK Cloud Matrix 의 기법으로 규칙 기반 매핑한다 (74 룰 / "
        "NCP 39 + NHN 35, 30 distinct 기법). 매핑 후 GapDetector 가 4 종 "
        "갭 (NONE / COLLECTION / EVIDENCE / INTERPRETATION) 으로 분류한다."
    )

    add_heading(doc, "1) OCSFNormalizer — V3 정규화 + nested dot 접근", 3)
    add_image_with_guide(
        doc, CAPTURES / "V_ocsf.png",
        "<그림 Ⅸ-4-1> V3 OCSF — 빈 케이스 (스키마 정보 + 안내)",
        what="V-3 진입 직후 빈 상태 — OCSF 1.3 스키마 정보 + 정규화 대기 안내",
        how_to_replace="V-3 진입 후 케이스 없는 상태 1920x1080 캡쳐",
    )
    add_image_with_guide(
        doc, CAPTURES / "V_ocsf_with_case.png",
        "<그림 Ⅸ-4-2> V3 OCSF — 13 events 정규화 결과 + 필드 매핑 상세표",
        what="정규화 결과 100% (13/13) + CSP 원본 → OCSF 필드 매핑 상세표 펼친 상태",
        how_to_replace="V-2 업로드 후 V-3 이동 → 매핑 표 펼침 → 1920x1080 캡쳐",
    )
    add_code_block(
        doc,
        "<코드 Ⅸ-4-1> OCSFNormalizer — 룰 로딩 + nested 접근",
        "class OCSFNormalizer:\n"
        "    _rules: dict = {}  # startup 시 1 회 캐시\n\n"
        "    @classmethod\n"
        "    def normalize(cls, raw: dict, csp: str) -> OCSFEvent:\n"
        "        rules = cls._rules[csp]\n"
        "        ocsf = {}\n"
        "        for ocsf_field, raw_path in rules.items():\n"
        "            ocsf[ocsf_field] = nested_get(raw, raw_path)\n"
        "        ocsf['class_uid'] = decide_class_uid(raw)\n"
        "        return OCSFEvent(**ocsf)\n",
        "backend/core/analysis/ocsf_normalizer.py",
    )
    add_steps(doc, [
        "backend/data/mapping_rules/{ncp,nhn}_cloud_trail.json 로드",
        "startup 시 1 회 메모리 캐시 (성능 NFR-03 충족)",
        "nested dot 표기로 raw event 필드 접근",
        "class_uid · category_uid · activity_id 결정",
        "ocsf_events INSERT + raw_event_id FK 연결",
    ])

    add_heading(doc, "2) AttackMapper — V6 매핑 결과 + Regex 매칭", 3)
    add_image_with_guide(
        doc, CAPTURES / "V_attack.png",
        "<그림 Ⅸ-4-3> V6 Attack — 빈 케이스 (3 KPI 카드 대기)",
        what="V-6 진입 직후 빈 상태 — 탐지 기법 / 전술 커버리지 / 매핑 이벤트 KPI 3개",
        how_to_replace="V-6 진입 후 매핑 미실행 상태 1920x1080 캡쳐",
    )
    add_image_with_guide(
        doc, CAPTURES / "V_attack_with_case.png",
        "<그림 Ⅸ-4-4> V6 Attack — 10/13 매핑 결과 (77%) + 기법 칩 분포",
        what="ATT&CK 매핑 완료 후 KPI 갱신 + 매핑 결과 안내 + 기법 칩 분포",
        how_to_replace="OCSF 정규화 후 V-6 이동 → 매핑 실행 → 결과 표시 1920x1080 캡쳐",
    )
    add_code_block(
        doc,
        "<코드 Ⅸ-4-2> AttackMapper — Regex 매칭 + 첫 매칭 룰 채택",
        "class AttackMapper:\n"
        "    _rules: list = []  # 74 룰, startup 시 Regex 컴파일\n\n"
        "    @classmethod\n"
        "    def map(cls, event: OCSFEvent) -> AttackEvent | None:\n"
        "        for rule in cls._rules:\n"
        "            if rule.pattern.match(event.activity_name):\n"
        "                return AttackEvent(\n"
        "                    technique_id=rule.technique_id,\n"
        "                    tactic_id=rule.tactic_id,\n"
        "                    confidence=rule.confidence,\n"
        "                )\n"
        "        return None  # unmapped\n",
        "backend/core/analysis/attack_mapper.py",
    )
    add_steps(doc, [
        "backend/data/attack_rules/rules.json 로드 (74 룰 — NCP 39 + NHN 35)",
        "활동명 Regex 컴파일 (startup 시 1 회)",
        "첫 매칭 룰의 technique_id · tactic_id 채택",
        "confidence (high/medium/low) 부여",
        "attack_events INSERT (30 distinct ATT&CK 기법 커버)",
    ])

    add_heading(doc, "3) GapDetector — V4 갭 감지 4 종 분류", 3)
    add_image_with_guide(
        doc, CAPTURES / "V_gap.png",
        "<그림 Ⅸ-4-5> V4 Gap — 빈 케이스 (실행 대기 + 4 종 안내)",
        what="V-4 진입 직후 실행 대기 + 4 종 갭 분류 안내",
        how_to_replace="V-4 진입 후 갭 감지 미실행 상태 1920x1080 캡쳐",
    )
    add_image_with_guide(
        doc, CAPTURES / "V_gap_with_case.png",
        "<그림 Ⅸ-4-6> V4 Gap — 갭 감지 실행 결과 + 4 종 분류 + 권고",
        what="갭 감지 실행 후 4 종 갭 분류 결과 + Layer 0 복귀/보강 권고",
        how_to_replace="V-6 매핑 후 V-4 → 갭 감지 실행 → 분류 결과 1920x1080 캡쳐",
    )
    add_code_block(
        doc,
        "<코드 Ⅸ-4-3> GapDetector.detect() — 4 종 갭 우선순위",
        "class GapDetector:\n"
        "    @staticmethod\n"
        "    def detect(case_id: str) -> list[GapResult]:\n"
        "        gaps = []\n"
        "        if missing_required_targets(case_id):\n"
        "            gaps.append(GapResult('COLLECTION', 'Layer 0 복귀'))\n"
        "        if raw_match_rate(case_id) < 0.3:\n"
        "            gaps.append(GapResult('EVIDENCE', '로그 보강 필요'))\n"
        "        if attack_map_rate(case_id) < 0.3:\n"
        "            gaps.append(GapResult('INTERPRETATION', 'AI 셰르파 브리핑'))\n"
        "        return gaps or [GapResult('NONE', '다음 단계 진행')]\n",
        "backend/core/analysis/gap_detector.py",
    )
    add_steps(doc, [
        "필수 증거 (REQUIRED) 미수집 → COLLECTION (Layer 0 복귀 권장)",
        "raw 매칭 ≤ 30% → EVIDENCE (보강 권장)",
        "ATT&CK 매핑 ≤ 30% → INTERPRETATION (AI 셰르파 브리핑 권장)",
        "모두 통과 → NONE (다음 단계 진행)",
        "gap_results INSERT + 우선순위 정렬",
    ])

    # ── 5. AI 셰르파 RAG ────────────────────────────────────────
    add_heading(doc, "5. AI 셰르파 RAG (V-8 Sherpa)", 2)
    add_para(
        doc,
        "Layer 3 은 폐쇄망에서 동작하는 sLLM (Ollama Llama 3.1 8B / GPT-OSS 20B) "
        "+ RAG (ChromaDB + paraphrase-multilingual-MiniLM-L12-v2 임베딩) 조합으로 "
        "자연어 Q&A 와 플레이북 추천을 제공한다. AI 는 검색 결과를 한국어로 "
        "요약·맥락화하는 보조 역할에 한정되며, 분류·매핑·결정은 모두 정적 "
        "규칙으로 결정성 100% 를 보장한다. KB 130 청크 (ATTACK 38 + PLAYBOOK 25 "
        "+ CSP_DOC 22 + CASE_DB 45) 출처 인용으로 환각을 차단한다."
    )

    add_heading(doc, "1) V8 Sherpa — 자연어 Q&A + KB 인덱스 사이드바", 3)
    add_image_with_guide(
        doc, CAPTURES / "V_sherpa.png",
        "<그림 Ⅸ-5-1> V8 Sherpa — 빈 상태 (엔진 상태 + KB 인덱스)",
        what="V-8 진입 직후 빈 상태 — Ollama 연결됨 + KB 130 청크 인덱스",
        how_to_replace="V-8 진입 후 첫 질문 입력 전 상태 1920x1080 캡쳐",
    )
    add_image_with_guide(
        doc, CAPTURES / "V_sherpa_with_case.png",
        "<그림 Ⅸ-5-2> V8 Sherpa — 자연어 Q&A 응답 + KB 출처 인용",
        what="자연어 질의 후 응답 + 인용된 KB 청크 출처 사이드바",
        how_to_replace="V-8 에서 샘플 질문 클릭 → 응답 수신 완료 1920x1080 캡쳐",
    )
    add_table_data(
        doc,
        "<표 Ⅸ-4> KB 4종 통계 (V8 Sherpa 실측, 총 130 청크)",
        ["KB 카테고리", "청크 수", "출처"],
        [
            ["ATTACK", "38", "MITRE ATT&CK Cloud Matrix v14"],
            ["PLAYBOOK", "25", "KISA 침해사고 분석절차 + NIST SP 800-86"],
            ["CSP_DOC", "22", "NCP / NHN 공식 보안 문서"],
            ["CASE_DB", "45", "공개 사례 (Capital One 2019 / Sysdig 2024 등)"],
        ],
    )
    add_code_block(
        doc,
        "<코드 Ⅸ-5-1> LLMEngine — Ollama Chat + reasoning 토큰 후처리",
        "class LLMEngine:\n"
        "    @classmethod\n"
        "    async def chat(cls, messages: list[dict]) -> str:\n"
        '        """httpx 비동기 + 30 초 timeout (SNF-02)."""\n'
        "        try:\n"
        "            async with httpx.AsyncClient(timeout=30.0) as client:\n"
        "                resp = await client.post(\n"
        '                    f"{OLLAMA_URL}/api/chat",\n'
        '                    json={"model": cls.MODEL, "messages": messages},\n'
        "                )\n"
        "                content = resp.json()['message']['content']\n"
        "                return strip_reasoning_tokens(content)\n"
        "        except httpx.TimeoutException:\n"
        '            return "(LLM timeout — KB 검색 결과만 표시)"\n',
        "backend/core/sherpa/llm_engine.py",
    )
    add_steps(doc, [
        "httpx 비동기 클라이언트 + 30 초 timeout (SNF-02)",
        "POST /api/chat → Ollama Chat API 호출",
        "GPT-OSS 20B reasoning 토큰 필터링 (<think>...</think> 제거)",
        "fallback 메시지 (timeout / 연결 실패) 반환",
        "action_logs 에 호출 이력 기록",
    ])

    add_heading(doc, "2) RAGRetriever — ChromaDB 의미 검색 + 키워드 fallback", 3)
    add_code_block(
        doc,
        "<코드 Ⅸ-5-2> RAGRetriever — 의미 검색 + fallback 분기",
        "def retrieve(query: str, k: int = 5, kb_filter: str | None = None) -> list[dict]:\n"
        "    if _embed_kb and _chromadb:\n"
        "        query_emb = _embed_kb.encode(query)\n"
        "        results = _chroma_col.query(\n"
        "            query_embeddings=[query_emb], n_results=k,\n"
        "            where={'category': kb_filter} if kb_filter else None,\n"
        "        )\n"
        "    else:\n"
        "        # fallback: KB JSON 키워드 매칭\n"
        "        results = keyword_search(query, k=k, kb_filter=kb_filter)\n"
        "    return [{'text': t, 'source': s} for t, s in results]\n",
        "backend/core/sherpa/rag_retriever.py",
    )
    add_steps(doc, [
        "paraphrase-multilingual-MiniLM-L12-v2 임베딩 (90 MB)",
        "ChromaDB 의미 검색 (top-k = 5)",
        "ChromaDB · sentence-transformers 미설치 시 키워드 매칭 fallback",
        "KB filter 적용 (ATTACK / PLAYBOOK / CSP_DOC / CASE_DB)",
        "검색 결과 + source 메타 반환 (환각 차단)",
    ])

    # ── 6. 수사 보드 + 보고서 ──────────────────────────────────
    add_heading(doc, "6. 수사 보드 + 보고서 (V-5 Board · V-7 Report)", 2)
    add_para(
        doc,
        "Layer 4 는 수사관이 분석 결과를 시각적으로 정리하고 자동 보고서로 "
        "내보내는 마지막 단계이다. V-5 Board 는 reactflow 11.11 로 chain_nodes "
        "· chain_edges 를 그래프 시각화하며, Phase O 에서 chain_nodes.meta JSON "
        "컬럼 추가 + Tree → Board bridge (POST /api/board/nodes/from-clue-tree) "
        "로 단서가 1st-class 노드로 승격된다. V-7 Report 는 Jinja2 + python-docx "
        "로 KISA 양식 8 섹션 보고서를 자동 생성한다."
    )

    add_heading(doc, "1) V5 Board — reactflow + chain_nodes.meta + Kill Chain (Phase O~P)", 3)
    add_image_with_guide(
        doc, CAPTURES / "V_board.png",
        "<그림 Ⅸ-6-1> V5 Board — 빈 상태 (Dwell Time + 그래프 캔버스 + 사이드바)",
        what="V-5 진입 직후 빈 캔버스 + Dwell Time + AI 브리핑 사이드바",
        how_to_replace="V-5 진입 후 노드 없는 상태 1920x1080 캡쳐",
    )
    add_image_with_guide(
        doc, CAPTURES / "V_board_with_case.png",
        "<그림 Ⅸ-6-2> V5 Board — Kill Chain + 단서 1st-class 노드 + AI 브리핑 (Phase O.5)",
        what="공격 체인 노드 + 단서 1st-class 노드 + Dwell Time 벤치마크 + AI 브리핑",
        how_to_replace="V-4 갭 통과 후 V-5 → 노드 추가 + Tree→Board bridge 실행 1920x1080 캡쳐 (Phase P.7 zoom/pan 적용)",
    )
    add_code_block(
        doc,
        "<코드 Ⅸ-6-1> chain_nodes.meta JSON 컬럼 (Phase O.1)",
        "class ChainNode(Base):\n"
        "    __tablename__ = 'chain_nodes'\n"
        "    node_id = Column(String(36), primary_key=True)\n"
        "    case_id = Column(String(36), ForeignKey('incident_cases.case_id'))\n"
        "    technique_id = Column(String(16))\n"
        "    label = Column(String(255))  # 보드 UI 표시용\n"
        "    status = Column(String(16))  # PENDING/CONFIRMED/REJECTED\n"
        "    meta = Column(JSON, nullable=True)  # Phase O.1 — 단서·증거·hypothesis 메타\n"
        "    is_ai_suggested = Column(Boolean, default=False)\n",
        "backend/db/models.py",
    )
    add_code_block(
        doc,
        "<코드 Ⅸ-6-2> POST /api/board/nodes/from-clue-tree — Tree→Board bridge (Phase O.2~5)",
        "@router.post('/board/nodes/from-clue-tree')\n"
        "async def from_clue_tree(case_id: str) -> dict:\n"
        "    tree = clue_tree_service.get(case_id)\n"
        "    nodes = []\n"
        "    for clue in tree.accepted_clues:\n"
        "        node = ChainNode(\n"
        "            case_id=case_id, technique_id=clue.attack_technique,\n"
        "            label=clue.label, status='PENDING',\n"
        "            meta={'clue_key': clue.key, 'depth': clue.depth,\n"
        "                  'posterior': clue.posterior},\n"
        "            is_ai_suggested=True,\n"
        "        )\n"
        "        db.add(node); nodes.append(node)\n"
        "    db.commit()\n"
        "    return {'created': len(nodes)}\n",
        "backend/api/board.py",
    )
    add_steps(doc, [
        "chain_nodes.meta 칼럼 추가 (단서·증거·hypothesis 메타)",
        "Phase O.2~5: Tree → Board bridge — 단서가 보드 1st-class 노드로 승격",
        "reactflow 11.11 노드-엣지 렌더 (Phase P.7 zoom/pan 보강)",
        "AI 제안 노드 (is_ai_suggested=True) 구분 색상",
        "Phase P.17: 회귀권고 polyline 끊김 + depth 라벨 점프 fix",
    ])

    add_heading(doc, "2) graph_analytics — networkx PageRank + Label Propagation (Phase J)", 3)
    add_code_block(
        doc,
        "<코드 Ⅸ-6-3> graph_analytics — PageRank + Label Propagation",
        "def analyze(case_id: str) -> dict:\n"
        "    G = nx.DiGraph()\n"
        "    nodes = db.query(ChainNode).filter_by(case_id=case_id).all()\n"
        "    edges = db.query(ChainEdge).filter_by(case_id=case_id).all()\n"
        "    G.add_nodes_from([n.node_id for n in nodes])\n"
        "    G.add_edges_from([(e.src_node_id, e.dst_node_id) for e in edges])\n"
        "    pagerank = nx.pagerank(G)  # Brin & Page 1998\n"
        "    communities = nx.community.label_propagation_communities(G.to_undirected())\n"
        "    return {'pagerank': pagerank, 'communities': list(communities)}\n",
        "backend/core/board/graph_analytics.py",
    )
    add_steps(doc, [
        "networkx DiGraph 로 chain_nodes · edges 적재",
        "PageRank (Brin & Page 1998) — 중심 자산 자동 강조",
        "Label Propagation (Zhu & Ghahramani 2002) — 의심 계정 군집화",
        "Validate — 사이클 / 고아 노드 검출",
        "결과 시각적 강조 (border / glow)",
    ])

    add_heading(doc, "3) V7 Report — KISA 양식 8 섹션 + multi-stage chain 통합 (Phase N.4.3)", 3)
    add_image_with_guide(
        doc, CAPTURES / "V_report.png",
        "<그림 Ⅸ-6-3> V7 Report — 빈 상태 (8 섹션 그리드 + 안내)",
        what="V-7 진입 직후 빈 상태 — 8 섹션 그리드 + 초안 생성 버튼",
        how_to_replace="V-7 진입 후 초안 미생성 상태 1920x1080 캡쳐",
    )
    add_image_with_guide(
        doc, CAPTURES / "V_report_with_case.png",
        "<그림 Ⅸ-6-4> V7 Report — 8 섹션 자동 초안 + multi-stage chain + DOCX/PDF",
        what="초안 생성 후 8 섹션 그리드 + KPI (draft/865 chars) + multi-stage chain 통합 + 내보내기",
        how_to_replace="V-5 보드 작업 후 V-7 → 초안 생성 → 8 섹션 채워진 시점 1920x1080 캡쳐",
    )
    add_code_block(
        doc,
        "<코드 Ⅸ-6-4> ReportGenerator — Jinja2 + python-docx + multi-stage chain",
        "class ReportGenerator:\n"
        "    SECTIONS = ['사고개요', '타임라인', '영향분석', 'ATT&CK결과',\n"
        "                '대응조치', '권고사항', '근거자료', '부록']\n\n"
        "    @classmethod\n"
        "    def generate(cls, case_id: str) -> str:\n"
        "        ctx = build_jinja_context(case_id)\n"
        "        ctx['multi_stage_chain'] = stage_transition_history(case_id)  # Phase N.4.3\n"
        "        template = env.get_template('kisa_report.j2')\n"
        "        sections = {s: template.module.render_section(s, ctx) for s in cls.SECTIONS}\n"
        "        return render_docx(sections, case_id)\n",
        "backend/core/board/report_generator.py",
    )
    add_steps(doc, [
        "POST /api/report 진입 시 case 메타 수집",
        "매핑 결과 · 체인 노드 · 갭 이력 Jinja2 컨텍스트 구성",
        "Phase N.4.3 — multi-stage chain (Stage 1→2→3 전이 이력) 통합",
        "KISA 양식 8 섹션 템플릿 렌더링 (사고개요 ~ 권고사항)",
        "python-docx 로 표 · 이미지 임베드",
    ])

    # ── 저장 ──────────────────────────────────────────────────
    doc.save(str(OUT))
    print(f"✅ 저장: {OUT.name}")
    final = Document(str(OUT))
    print(f"   단락 {len(final.paragraphs)} / 표 {len(final.tables)}")


if __name__ == "__main__":
    main()
