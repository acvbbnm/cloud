// AI Sherpa 최종보고서 — 마지막 챕터 초안 (§6 구현 · §8 시험서 · §9 현실적 제한사항 · §10 참고 자료)
// 레퍼런스: 정보보호 3조 세종NFT미술관 최종보고서 pp.71-113 (Ⅶ 시험서 · Ⅷ 제한사항 · Ⅸ 구현 · 참고문헌) 패턴 차용.
// 산출: 같은 폴더에 AI_Sherpa_최종보고서_마지막섹션_초안.docx

const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, PageOrientation, LevelFormat,
  ExternalHyperlink, HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageNumber, PageBreak, TabStopType, TabStopPosition,
} = require('docx');

// ── 공통 설정 ──
const FONT = '맑은 고딕';
const FONT_CODE = 'Consolas';

const border = (color = 'BFBFBF') => ({ style: BorderStyle.SINGLE, size: 6, color });
const allBorders = (color = 'BFBFBF') => ({
  top: border(color), bottom: border(color), left: border(color), right: border(color),
  insideHorizontal: border(color), insideVertical: border(color),
});

// 페이지 폭(A4, 좌우 여백 2.54cm 가정): 11906 - 2 * 1440 = 9026 DXA
const CONTENT_W = 9026;

// ── 빌더 헬퍼 ──
const p = (text, opts = {}) => new Paragraph({
  spacing: { before: 60, after: 60, line: 320 },
  ...opts,
  children: [new TextRun({ text, font: opts.font || FONT, size: opts.size || 22, bold: opts.bold, italics: opts.italics, color: opts.color })],
});

const h = (text, level) => new Paragraph({
  heading: level === 1 ? HeadingLevel.HEADING_1 : level === 2 ? HeadingLevel.HEADING_2 : level === 3 ? HeadingLevel.HEADING_3 : HeadingLevel.HEADING_4,
  spacing: { before: level === 1 ? 360 : 240, after: 120 },
  children: [new TextRun({ text, font: FONT, size: level === 1 ? 36 : level === 2 ? 30 : level === 3 ? 26 : 24, bold: true })],
});

const bullet = (text) => new Paragraph({
  numbering: { reference: 'bullets', level: 0 },
  spacing: { before: 40, after: 40, line: 300 },
  children: [new TextRun({ text, font: FONT, size: 22 })],
});

const codeP = (text) => new Paragraph({
  spacing: { before: 60, after: 60, line: 280 },
  shading: { fill: 'F2F2F2', type: ShadingType.CLEAR },
  border: { left: { style: BorderStyle.SINGLE, size: 12, color: '4472C4', space: 4 } },
  indent: { left: 200 },
  children: [new TextRun({ text, font: FONT_CODE, size: 20 })],
});

const caption = (text) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 80, after: 160 },
  children: [new TextRun({ text, font: FONT, size: 20, italics: true, color: '595959' })],
});

// 표 헬퍼
const cell = (text, opts = {}) => new TableCell({
  borders: allBorders('BFBFBF'),
  width: { size: opts.width, type: WidthType.DXA },
  shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
  margins: { top: 80, bottom: 80, left: 120, right: 120 },
  verticalAlign: 'center',
  children: [new Paragraph({
    alignment: opts.align || AlignmentType.LEFT,
    spacing: { line: 280 },
    children: [new TextRun({ text: String(text ?? ''), font: FONT, size: 20, bold: opts.bold })],
  })],
});

const makeTable = (columnWidths, headerRow, dataRows, headerFill = 'D9E1F2') => {
  const rows = [
    new TableRow({
      tableHeader: true,
      children: headerRow.map((t, i) => cell(t, { width: columnWidths[i], fill: headerFill, bold: true, align: AlignmentType.CENTER })),
    }),
    ...dataRows.map(r => new TableRow({
      children: r.map((t, i) => cell(t, { width: columnWidths[i], align: i === 0 ? AlignmentType.CENTER : AlignmentType.LEFT })),
    })),
  ];
  return new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths, rows });
};

// ───────────────────────── 본문 ─────────────────────────
const body = [];

// 표지 라인 (간이)
body.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 240, after: 120 },
  children: [new TextRun({ text: '정보보호 캡스톤디자인 최종 보고서', font: FONT, size: 32, bold: true })],
}));
body.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 0, after: 120 },
  children: [new TextRun({ text: '— AI Sherpa: 국내 멀티 클라우드 침해사고 분석 시스템 —', font: FONT, size: 26 })],
}));
body.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 0, after: 80 },
  children: [new TextRun({ text: '본 초안은 레퍼런스 보고서(NFT 미술관 3조, pp.71-113) 패턴에 맞춘 §6 · §8 · §9 · §10 초안입니다.', font: FONT, size: 20, italics: true, color: '595959' })],
}));
body.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 0, after: 360 },
  children: [new TextRun({ text: '팀 로그아웃 · 세종대학교 정보보호학과 · 2026', font: FONT, size: 22 })],
}));

// ───────────────────────── §6 구현 ─────────────────────────
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(h('Ⅵ. 구현', 1));
body.push(p('본 장에서는 5장에서 도출된 5계층 아키텍처(L0~L4)의 실제 구현을 기술한다. 레퍼런스의 §Ⅸ 구조(유저 앱 · 트랜잭션 서버 · 핵심 분석 · 관리자 웹)와 동일한 흐름을 따르되, 본 시스템은 침해사고 분석 도메인에 맞춰 “8개 뷰 · 30 REST API · 5계층 핵심 분석 · 데이터/회귀 사이클” 4개 묶음으로 재편한다. 모든 코드 경로는 저장소 dev3 브랜치를 기준으로 한다.'));

// 6.1
body.push(h('6.1 백엔드 공통 (FastAPI · SQLAlchemy · 9 테이블)', 2));
body.push(p('백엔드는 Python 3.10+ / FastAPI 0.115 / SQLAlchemy 2.0 / SQLite 로 구성된다. 라우터는 계층별 단일 파일(intake · ingestion · analysis · sherpa · board · report · common)로 분리되며, main.py 는 라우터 등록과 startup 훅만 보유한다(비즈니스 로직 금지).'));
body.push(p('DB 모델은 backend/db/models.py 에 9개 테이블이 선언되어 있으며 PK는 모두 VARCHAR(36) UUID, FK는 동일 타입으로 ForeignKey 명시한다.'));
body.push(makeTable(
  [900, 2300, 5826],
  ['#', '테이블', '핵심 역할'],
  [
    ['1', 'incident_cases', '사고 케이스 메타 (incident_type · csp · severity · tlp · observables · secondary_incident_types · triage_state)'],
    ['2', 'collection_targets', '수집 대상 카탈로그 77 행 (10 풍부 필드 — hint · cmd · mitre_techniques 등)'],
    ['3', 'raw_events', '원본 로그 + SHA-256 해시 (Layer 1 무결성)'],
    ['4', 'ocsf_events', 'OCSF 정규화 이벤트 (Layer 2)'],
    ['5', 'attack_events', 'ATT&CK 매핑 결과 (rule_id · technique_id · confidence)'],
    ['6', 'gap_results', '갭 판정 결과 (gap_type · completion_rate)'],
    ['7', 'chain_nodes', '공격 체인 노드 (label 컬럼 추가 — 보드 UI 표시용)'],
    ['8', 'chain_edges', '체인 엣지 (방향성 · 시간 정렬)'],
    ['9', 'action_logs', '수사관 조작 이력 (actor 고정 라벨 “investigator”)'],
  ]
));
body.push(caption('<표 6-1> AI Sherpa 9개 DB 테이블 일람'));

// 6.2 8개 뷰
body.push(h('6.2 8개 화면 일람 (V-1 ~ V-8)', 2));
body.push(p('프론트엔드는 React 18 + TypeScript + Tailwind + Zustand + React Query 기반이며, 단일 페이지 내 사이드바 라우팅으로 8개 뷰가 분리되어 있다. 각 뷰의 구현 위치는 frontend/src/views/V[1-8]_*/index.tsx 이다.'));
body.push(makeTable(
  [1100, 2400, 5526],
  ['뷰', '제목', '핵심 인터랙션 및 구현 포인트'],
  [
    ['V-1', '사고 접수 (Setup)', '4-step Wizard. Step 0 CSP 선택 → Step 1 사고유형 9종 카드 → Step 2 시스템 구성 3-tab → Step 3 Discovery 결정 트리 24 노드 88 엣지 → Step 4 시드 가이드(hint · CLI · MITRE)'],
    ['V-2', '로그 수집', '드래그 앤 드롭 업로드, SHA-256 자동 산출, 이벤트 미리보기 + 페이지네이션 + raw JSON 펼침'],
    ['V-3', 'OCSF 정규화', '정규화 실행 → raw/OCSF 양면 비교 테이블. 미매칭 행은 unmapped_raw 객체 보유'],
    ['V-4', 'Gap 감지', 'gap_type (NONE/COLLECTION/EVIDENCE/INTERPRETATION) + completionRate 시각화'],
    ['V-5', '수사 보드', 'react-flow 기반 ChainGraph. PENDING/CONFIRMED/REJECTED 노드 상태 + Dwell Time KPI 카드'],
    ['V-6', 'ATT&CK 매핑', '룰 74개 적용 결과를 technique × tactic 매트릭스로 시각화'],
    ['V-7', '보고서', '8 섹션 자동 초안. Jinja2 → DOCX/PDF 다운로드(python-docx · reportlab)'],
    ['V-8', 'AI 셰르파', '플로팅 FAB + 채팅 패널. 브리핑 · 빠진 고리 제안 · 플레이북 추천 · 사후검증 4 모드, 출처 칩 항상 표시'],
  ]
));
body.push(caption('<표 6-2> 8개 화면 일람'));

// 6.3 Layer 3 AI 셰르파
body.push(h('6.3 Layer 3 — AI 셰르파 구현', 2));
body.push(p('AI 셰르파는 본 시스템의 가장 차별화된 모듈로, “AI는 판단·결정하지 않고 검색·요약·제안만 수행한다”는 원칙을 코드 수준에서 강제한다. 구현은 core/sherpa/ 패키지 4 모듈로 분리되어 있다.'));

body.push(h('6.3.1 LLMEngine — Ollama 호출 어댑터', 3));
body.push(bullet('파일: backend/core/sherpa/llm_engine.py'));
body.push(bullet('백엔드: Ollama 로컬 서버(http://localhost:11434), 모델 gpt-oss:20b (또는 llama3.1:8b 폴백)'));
body.push(bullet('HTTP 클라이언트: httpx 0.27+ 비동기, LLM_TIMEOUT (기본 30초, CPU/8B+ 환경은 .env 로 120초 상향)'));
body.push(bullet('완전 오프라인 보장 (SNF-01): 모든 외부 CDN 호출 금지, 임베딩·LLM 모두 로컬'));

body.push(h('6.3.2 RAGRetriever — 다국어 임베딩 + ChromaDB', 3));
body.push(bullet('파일: backend/core/sherpa/rag_retriever.py'));
body.push(bullet('임베딩: sentence-transformers paraphrase-multilingual-MiniLM-L12-v2 (~120MB, 한국어 KB 청크 검색)'));
body.push(bullet('벡터 DB: ChromaDB 로컬 영속 모드 (CHROMA_PERSIST_DIR)'));
body.push(bullet('KB 청크 130 — ATTACK 38 / PLAYBOOK 25 / CSP_DOC 22 / CASE_DB 45'));
body.push(bullet('Fallback: chromadb/sentence-transformers 미설치 시 키워드 매칭으로 자동 전환'));

body.push(h('6.3.3 _strip_unsourced_techniques — 환각 차단 후처리', 3));
body.push(p('LLM 응답에 RAG 청크에 없는 ATT&CK 기법 ID(예: T1078.004)가 새로 도입되면 자동 라벨링(“⚠ 출처 미확인”)하여 표시한다. 2026-05-24 KB audit P0 사이클에서 도입된 안전장치로, CLAUDE.md §금지사항 5-1에 명시되어 있다.'));

body.push(h('6.3.4 recommend_playbook — RAG + LLM 결합 라우팅', 3));
body.push(p('마지막까지 “깡통”으로 남아 있던 플레이북 추천 모듈을 사고유형 기반 3-tier 라우팅 + RAG 컨텍스트 조립 + LLM 합성으로 완성하였다(Phase 2.5, PR #11/#12).'));
body.push(bullet('Tier 1: 사고유형(9종)으로 PLAYBOOK 청크 lane 필터'));
body.push(bullet('Tier 2: 현재 케이스의 attack_events 로 technique 기반 재순위'));
body.push(bullet('Tier 3: LLM 요약 시 RAG 청크 인용 강제 (출처 미인용 시 후처리 차단)'));

// 6.4 데이터 사이클
body.push(h('6.4 데이터 / 회귀 사이클 (사이클 1~6 종합)', 2));
body.push(p('본 시스템의 데이터 신뢰도는 6 사이클에 걸친 풍부화·회귀로 확보하였다. 시드 부족·룰 누락·매처 충돌 등 발견된 결함을 매 사이클마다 자동 검증 스크립트와 회귀 테스트로 잠궈 둔다.'));
body.push(makeTable(
  [800, 2200, 6026],
  ['사이클', '대상', '성과'],
  [
    ['1', 'collection_targets 시드 enrichment', '7 → 77 행 / 10 풍부 필드(hint · cmd · mitre_techniques 등) 자동 보강'],
    ['2', '매처 룰 16/16 매트릭스', '8 사고유형 × 2 CSP = 16 매트릭스, OCSF 필드 매핑 누락 0건 보장'],
    ['3', 'ATT&CK 룰 74 보강', 'NCP 39 / NHN 35, 기법 19종 분포 — Exfiltration · DNS 룰 6건 추가(P3)'],
    ['4', '합성 시나리오 16종', '8 사고유형 × 2 CSP + Sysdig 8min Killchain · Capital One 2019 사실 기반 2건'],
    ['5', 'KB 청크 130', 'ATTACK 38 / PLAYBOOK 25 / CSP_DOC 22 / CASE_DB 45 — KB audit E=100% 달성'],
    ['6', 'pytest + GitHub Actions CI', '129 케이스 / 5 모듈, pre-commit hook 통합 (PR #11·12)'],
  ]
));
body.push(caption('<표 6-3> 데이터·회귀 사이클 1~6 종합'));

body.push(h('6.4.7 pytest 회귀 + GitHub Actions 자동 CI', 3));
body.push(p('백엔드 회귀 테스트는 5 모듈 129 케이스로 구성되며, GitHub Actions backend-tests.yml 워크플로우가 PR마다 자동 실행된다. 또한 pre-commit hook 단계에서 동일 회귀를 실행하여 누락 커밋을 차단한다.'));
body.push(makeTable(
  [3000, 2000, 4026],
  ['모듈', '케이스 수', '커버 사고유형 / 범위'],
  [
    ['test_attack_rules.py', '32', 'ATT&CK 룰 74 — NCP·NHN 양 CSP 매핑'],
    ['test_collection_guide_v2.py', '24', 'v2 가이드 매트릭스 — 5 phases · 11 targets'],
    ['test_data_gap.py', '18', 'completion_rate · gap_type 4종'],
    ['test_matchers.py', '36', 'OCSF 정규화 매처 16/16 매트릭스'],
    ['test_no_hallucination.py', '8', 'LLM 응답 _strip_unsourced_techniques 후처리'],
    ['test_playbook_lane_filter.py', '6', '플레이북 lane 필터 + RAG 결합'],
    ['test_recommend_playbook.py', '5', 'Phase 2.5 마지막 깡통 — 사고유형 라우팅'],
  ]
));
body.push(caption('<표 6-4> pytest 회귀 5 + 신규 2 모듈 129 케이스 분포'));

// 6.5 30 REST API 명세
body.push(h('6.5 REST API 명세 (30 엔드포인트)', 2));
body.push(p('백엔드는 8 라우터에 30개 엔드포인트를 정의하며, 모든 응답은 통일 포맷 { status: "ok", data: {...} } 또는 { status: "error", message, code } 형식이다. 페이지네이션 응답은 { items, total, page, pageSize } 별도 포맷을 사용한다.'));

body.push(h('6.5.1 Layer 0 — 사고 접수', 3));
body.push(makeTable(
  [600, 1100, 2800, 4526],
  ['ID', 'Method', 'Path', '설명'],
  [
    ['1', 'POST', '/api/cases', '케이스 생성 — incident_type · csp · severity · system_config 입력 → caseId 발급'],
    ['2', 'GET', '/api/cases/{caseId}', '상세 조회 (dev3 5 컬럼 — title · tlp · observables · secondary_incident_types · triage_state 포함)'],
    ['3', 'PATCH', '/api/cases/{caseId}', '시스템 구성 부분 수정 + secondary_incident_types 추가/제거'],
    ['4', 'GET', '/api/guide', 'Step 3 초동 수집 체크리스트(v1)'],
    ['5', 'GET', '/api/guide/v2', 'v2 가이드 매트릭스 — 5 phases · 11 targets · Kill Chain'],
  ]
));

body.push(h('6.5.2 Layer 1 — 로그 수집', 3));
body.push(makeTable(
  [600, 1100, 2800, 4526],
  ['ID', 'Method', 'Path', '설명'],
  [
    ['6', 'POST', '/api/logs/upload', 'multipart 업로드(caseId Form 필드 필수) + SHA-256 산출'],
    ['7', 'GET', '/api/logs', '페이지네이션 (caseId · page · pageSize)'],
    ['8', 'GET', '/api/logs/{eventId}', 'raw 객체 단건 조회'],
  ]
));

body.push(h('6.5.3 Layer 2 — 분석', 3));
body.push(makeTable(
  [600, 1100, 2800, 4526],
  ['ID', 'Method', 'Path', '설명'],
  [
    ['9', 'POST', '/api/analysis/normalize', 'OCSF 정규화 실행'],
    ['10', 'POST', '/api/analysis/map', 'ATT&CK 매핑(74 룰 적용)'],
    ['11', 'GET', '/api/analysis/ocsf', '정규화 결과 조회'],
    ['12', 'GET', '/api/analysis/attack', 'ATT&CK 결과 조회'],
    ['13', 'POST', '/api/analysis/gap', 'gap_type + completion_rate 산출'],
  ]
));

body.push(h('6.5.4 Layer 3 — AI 셰르파', 3));
body.push(makeTable(
  [600, 1100, 2800, 4526],
  ['ID', 'Method', 'Path', '설명'],
  [
    ['14', 'POST', '/api/sherpa/brief', '컨텍스트 브리핑 — KB 출처 인용 강제'],
    ['15', 'POST', '/api/sherpa/suggest', '빠진 고리 후보 제안'],
    ['16', 'POST', '/api/sherpa/playbook', 'recommend_playbook RAG+LLM 결합'],
    ['17', 'POST', '/api/sherpa/chat', '자연어 질의 — 출처 칩 항상 동반'],
    ['18', 'GET', '/api/sherpa/kb', 'KB 상태 — engine · model · 청크 수 보고'],
  ]
));

body.push(h('6.5.5 Layer 4 — 보드 / 보고서', 3));
body.push(makeTable(
  [600, 1100, 2800, 4526],
  ['ID', 'Method', 'Path', '설명'],
  [
    ['19', 'POST', '/api/board/nodes', '체인 노드 추가 (PENDING 상태로 생성)'],
    ['20', 'PATCH', '/api/board/nodes/{nodeId}', 'CONFIRMED / REJECTED 상태 전이'],
    ['21', 'POST', '/api/board/edges', '엣지 추가 (방향성 + 시간 정렬)'],
    ['22', 'GET', '/api/board', '현재 보드 상태 일괄 조회'],
    ['23', 'POST', '/api/report', '보고서 초안 자동 생성 (8 섹션)'],
    ['24', 'PATCH', '/api/report/{caseId}', '섹션 부분 수정'],
    ['25', 'GET', '/api/report/{caseId}/export', 'DOCX / PDF 내보내기'],
  ]
));

body.push(h('6.5.6 공통', 3));
body.push(makeTable(
  [600, 1100, 2800, 4526],
  ['ID', 'Method', 'Path', '설명'],
  [
    ['26', 'GET', '/api/actions', '수사관 조작 로그 (caseId · limit · offset · action 필터)'],
    ['27', 'GET', '/api/health', 'server · db · ollama · chromadb 상태 보고'],
    ['28', 'GET', '/api/health/ping', '가벼운 ping(외부 의존성 체크 없음)'],
    ['29', 'POST', '/api/triage/decision', 'Step 3 결정 트리 평가 + posterior 점수'],
    ['30', 'GET', '/api/triage/weights', '가중치 매트릭스 조회(weights.json 9 사고유형)'],
  ]
));
body.push(caption('<표 6-5> REST API 30 엔드포인트 일람'));

// ───────────────────────── §7 시험서(원래 §8) ─────────────────────────
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(h('Ⅶ. 시험서 및 시험 시나리오', 1));
body.push(p('레퍼런스의 §Ⅶ 시험서/시험 시나리오 패턴을 차용하여, 본 시스템은 ① 기능 시험서(SFR / WSR), ② API 통합 시험, ③ E2E 합성 로그 시험, ④ pytest 자동 회귀, ⑤ 시험 시나리오(수동) 다섯 묶음으로 시험 결과를 기술한다.'));

body.push(h('7.1 시스템 기능 시험서', 2));
body.push(makeTable(
  [1100, 1700, 4900, 1326],
  ['구분', '관련번호', '기능명', '시험 확인'],
  [
    ['L0-Intake', 'SFR-001', '사고 케이스 생성 (incident_type · csp · severity 입력)', 'O'],
    ['L0-Intake', 'SFR-002', '사고 케이스 단건 조회', 'O'],
    ['L0-Intake', 'SFR-003', '사고 케이스 부분 수정 (PATCH)', 'O'],
    ['L0-Intake', 'SFR-004', '초동 수집 가이드 v1 / v2 매트릭스 조회', 'O'],
    ['L1-Ingestion', 'SFR-005', '로그 파일 업로드 + SHA-256 무결성 산출', 'O'],
    ['L1-Ingestion', 'SFR-006', '원본 이벤트 페이지네이션 조회', 'O'],
    ['L2-Analysis', 'SFR-007', 'OCSF 정규화 (16/16 매처 매트릭스)', 'O'],
    ['L2-Analysis', 'SFR-008', 'ATT&CK 매핑 (룰 74 적용)', 'O'],
    ['L2-Analysis', 'SFR-009', 'Gap 감지 (gap_type · completion_rate 산출)', 'O'],
    ['L3-Sherpa', 'SFR-010', 'AI 컨텍스트 브리핑 (출처 인용 강제)', 'O'],
    ['L3-Sherpa', 'SFR-011', '빠진 고리 후보 제안', 'O'],
    ['L3-Sherpa', 'SFR-012', '플레이북 추천 (RAG + LLM 결합)', 'O'],
    ['L3-Sherpa', 'SFR-013', '자연어 질의 채팅 (출처 칩 동반)', 'O'],
    ['L3-Sherpa', 'SFR-014', 'LLM 응답 환각 차단 (_strip_unsourced_techniques)', 'O'],
    ['L4-Board', 'SFR-015', '체인 노드 / 엣지 추가 · 상태 전이', 'O'],
    ['L4-Board', 'SFR-016', 'Dwell Time KPI 산출', 'O'],
    ['L4-Report', 'SFR-017', '보고서 초안 8 섹션 자동 생성', 'O'],
    ['L4-Report', 'SFR-018', 'DOCX / PDF 내보내기', 'O'],
    ['Common', 'SFR-019', 'action_logs 수사관 조작 이력', 'O'],
    ['Common', 'SFR-020', '/api/health · /api/health/ping 헬스체크', 'O'],
    ['Triage', 'SFR-021', 'Step 3 결정 트리 24 노드 평가', 'O'],
    ['Triage', 'SFR-022', '가중치 매트릭스(weights.json 9 사고유형) 조회', 'O'],
  ]
));
body.push(caption('<표 7-1> 시스템 기능 시험서 (SFR-001 ~ SFR-022)'));

body.push(h('7.2 웹 서비스 시험서 (V-1 ~ V-8)', 2));
body.push(makeTable(
  [1100, 1700, 4900, 1326],
  ['구분', '관련번호', '기능명', '시험 확인'],
  [
    ['V-1', 'WSR-001', '4-step Wizard 흐름 (CSP → 사고유형 → 시스템 구성 → Discovery)', 'O'],
    ['V-1', 'WSR-002', '결정 트리 24 노드 — 동일 답변 시 동일 점수(재현성)', 'O'],
    ['V-1', 'WSR-003', 'Step 4 시드 가이드 hint · CLI · MITRE 노출', 'O'],
    ['V-2', 'WSR-004', '드래그 앤 드롭 업로드 + SHA-256 자동 산출', 'O'],
    ['V-3', 'WSR-005', 'raw / OCSF 양면 비교 테이블', 'O'],
    ['V-4', 'WSR-006', 'completionRate · gap_type 시각화', 'O'],
    ['V-5', 'WSR-007', 'ChainGraph 노드 상태 전이 + Dwell Time KPI 카드', 'O'],
    ['V-6', 'WSR-008', 'ATT&CK technique × tactic 매트릭스', 'O'],
    ['V-7', 'WSR-009', '8 섹션 초안 + DOCX/PDF 다운로드', 'O'],
    ['V-8', 'WSR-010', 'FAB 채팅 패널 · 출처 칩 표시 · 사후검증 카드', 'O'],
  ]
));
body.push(caption('<표 7-2> 웹 서비스 시험서 (WSR-001 ~ WSR-010)'));

body.push(h('7.3 API 통합 시험 결과 (화이트박스)', 2));
body.push(p('백엔드 30 엔드포인트 + 에러 분기를 포함하여 30/30 PASS(100%)를 달성하였다. 정적 검증은 Python AST 48 파일 0 error, TypeScript tsc --noEmit 0 error, Vite production build 188 modules 393KB 통과를 확인하였다.'));
body.push(makeTable(
  [3000, 2500, 3526],
  ['영역', '검증 항목', '결과'],
  [
    ['백엔드 정적', 'SyntaxError + 모듈 import (48 파일)', '100% (에러 0)'],
    ['프론트 정적', 'TypeScript tsc --noEmit', '통과'],
    ['프론트 빌드', 'Vite production build', '188 모듈 / 393KB / 2.5초'],
    ['백엔드 API', '30 테스트 (30 API + 에러 분기)', '30 PASS / 0 FAIL (100%)'],
  ]
));
body.push(caption('<표 7-3> 정적·동적 통합 시험 결과 요약'));

body.push(h('7.4 E2E 합성 로그 시험', 2));
body.push(p('합성 시나리오 16종(8 사고유형 × 2 CSP) + 사실 기반 2건(Sysdig 2024 8 분 침투 · Capital One 2019)을 backend/scripts/e2e_synthetic_logs_test.py 로 자동 검증한다. 대표 결과는 다음과 같다.'));
body.push(makeTable(
  [3000, 1500, 1500, 3026],
  ['시나리오', '매칭률', 'ATT&CK 매핑률', '커버 기법'],
  [
    ['S1 — NCP 자격증명 탈취 (Sysdig 사실)', '13/13 (100%)', '10/13 (77%)', 'T1078.004 · T1098 · T1098.001 · T1136.003 · T1537 ×3 · T1531'],
    ['S1’ — NHN 자격증명 탈취 + MFA 우회', '6/8 (75%)', '6/8 (75%)', 'T1078 · T1556 · T1098.001'],
    ['S2 — 랜섬웨어 (Capital One 변형)', '16/16 (100%)', '12/16 (75%)', 'T1486 · T1490 · T1562.001'],
    ['S3 — 설정 오류 노출 (S3 SSRF)', '11/11 (100%)', '9/11 (82%)', 'T1190 · T1552.005'],
    ['S4 — 피싱 초기 침투', '8/10 (80%)', '6/10 (60%)', 'T1566.002 · T1078 · T1136'],
    ['S5 — 내부자 위협', '9/9 (100%)', '7/9 (78%)', 'T1078 · T1083 · T1537'],
  ]
));
body.push(caption('<표 7-4> 대표 합성 시나리오 검증 결과'));

body.push(h('7.5 pytest 자동 회귀 시험', 2));
body.push(p('5 + 신규 2 = 7 모듈 / 129 케이스로 구성되며, GitHub Actions backend-tests.yml 워크플로우가 PR마다 자동 실행하여 회귀를 차단한다. 또한 pre-commit hook 단계에서도 동일 회귀를 강제 실행한다.'));
body.push(codeP('$ cd backend && python -m pytest tests/ -v\n========================== 129 passed in 18.43s =========================='));
body.push(p('대표 GitHub Actions 실행: run 26355406474. 모든 모듈 PASS / 0 FAIL.'));

body.push(h('7.6 시험 시나리오 (수동)', 2));
body.push(p('수동 시험 시나리오는 사고유형별 5계층 전체 흐름(L0→L4)을 검증한다. 본 보고서는 가장 대표적인 시나리오 A(NCP 자격증명 탈취)만 기술하며, 나머지는 docs/수동_테스트_시나리오.md 에 수록되어 있다.'));

body.push(h('시험 시나리오 A — NCP 자격증명 탈취 (Sysdig 8분 침투)', 4));
body.push(makeTable(
  [2300, 6726],
  ['항목', '내용'],
  [
    ['시험 시나리오 명', 'NCP 자격증명 탈취 + Object Storage 유출'],
    ['시험 시나리오 설명', 'NCP attack-sim 계정이 MFA 미적용 상태에서 외부 IP로 침투 → 권한 변경 → Server Console 접근 → Object Storage 유출'],
    ['관련 번호', 'SFR-001 ~ SFR-018 · WSR-001 ~ WSR-010'],
    ['시험 절차', '1. V-1 Step 0 NCP 선택 → Step 1 CREDENTIAL_THEFT → Step 2 MFA 미적용 → Step 3 Discovery 결정 트리 완료\n2. V-2 ncp_none.json (16건) 드래그 업로드 → SHA-256 산출 확인\n3. V-3 정규화 실행 → 16건 100% OCSF 변환\n4. V-6 ATT&CK 매핑 → 10/13 (77%) 매칭, T1078.004 등 7 기법 확인\n5. V-4 갭 감지 → completionRate 100%\n6. V-5 ChainGraph 노드 자동 생성 + 수사관 CONFIRMED 채택\n7. V-8 사후검증 카드 → "PE 확정 정합 + CT·DE 추가 제안"\n8. V-7 보고서 DOCX 다운로드'],
    ['시험 확인', 'O'],
    ['예상 소요', '약 15분'],
  ]
));
body.push(caption('<표 7-5> 시험 시나리오 A — NCP 자격증명 탈취'));

// ───────────────────────── §8 현실적 제한사항 ─────────────────────────
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(h('Ⅷ. 현실적 제한사항', 1));
body.push(p('본 시스템은 학사 캡스톤 범위(약 4 개월) 내에서 “결정성 보장 + 학술 변호 가능 + 오프라인 동작”의 세 원칙을 모두 달성하는 데 자원을 집중하였다. 그 결과 다음과 같은 한계가 남는다.'));

body.push(h('8.1 단일 수사관 가정 — 인증·권한 분리 미적용', 2));
body.push(p('CLAUDE.md §5.1 영속화 정책에 따라 MVP는 단일 수사관 로컬 데스크톱 배포를 가정한다. 따라서 User 클래스가 존재하지 않으며 action_logs.actor 컬럼에 고정 라벨 "investigator" 가 기록된다. 다중 사용자 · 역할 분리 · SSO 연동은 Phase 2 확장 범위로 분리하였다.'));

body.push(h('8.2 AI / LLM 응답 지연 — 폐쇄망 + 로컬 sLLM의 본질적 비용', 2));
body.push(p('Ollama gpt-oss:20b 모델은 CPU 전용 환경에서 첫 응답까지 30~120초가 소요될 수 있다. 본 시스템은 SNF-01 “오프라인(폐쇄망) 동작 필수” 요구사항을 만족시키기 위해 외부 클라우드 LLM(GPT/Claude API)을 사용할 수 없으며, 그 대가로 응답 지연을 감수한다. LLM_TIMEOUT 환경변수를 통해 사용자가 환경에 맞춰 30 ~ 120초 사이로 조정한다.'));

body.push(h('8.3 환각 차단의 보수성 — 출처 미인용 결과는 표시 차단', 2));
body.push(p('LLM 응답에 KB 청크 밖의 ATT&CK 기법 ID가 포함되면 _strip_unsourced_techniques 후처리가 자동으로 라벨링(“⚠ 출처 미확인”)한다. 이는 환각으로 인한 오분류를 차단하는 안전장치이나, 그 대가로 LLM의 사고 외 보완 능력이 줄어든다. 수사관은 화면에서 라벨이 부착된 항목을 검토 후 KB에 직접 추가하여 향후 인용 풀을 확장할 수 있다.'));

body.push(h('8.4 합성 데이터 의존 — 실제 CSP 침해사고 raw 로그 접근 제한', 2));
body.push(p('국내 CSP(NCP · NHN)의 실제 침해사고 raw 로그는 보안상 외부 접근이 제한되므로, 본 시스템은 합성 16 시나리오 + 사실 기반 2건(Sysdig 2024 NCP 8 분 침투 · Capital One 2019 AWS S3 SSRF)으로 검증을 보강하였다. 합성 데이터는 실제 침해사고의 분포를 완전히 대표하지 못한다는 한계가 있으나, MITRE ATT&CK Cloud Matrix v14 의 19 기법을 모두 커버하도록 설계되어 학술적 검증 가능성을 확보한다.'));

body.push(h('8.5 지원 CSP 범위 제한 — NCP · NHN 2 사', 2));
body.push(p('본 시스템은 국내 클라우드 보안인증(CSAP) 인증을 보유한 NCP · NHN 2 사만 지원한다. KT Cloud · Samsung SDS · 카카오엔터프라이즈 등 추가 CSP는 OCSF 필드 매핑 룰(backend/data/mapping_rules/) 과 ATT&CK 룰(backend/data/attack_rules/) 을 확장하면 추가 가능하나, 본 MVP 범위에는 포함되지 않는다.'));

body.push(h('8.6 사고유형 9종 분류 — Verizon DBIR 통계의 클라우드 특화 보정', 2));
body.push(p('가중치(weights.json)는 Verizon DBIR 2024 통계 + CSA Top Threats to Cloud Computing 2024 의 두 출처를 1:1 가중치로 결합하였다. Verizon DBIR 은 모든 산업 사고를 포함하므로 클라우드 특화 보정이 추가로 필요하나, 국내 클라우드 침해사고 표본이 부족하여 현 단계에서는 위 두 출처에 의존한다. Phase 2 확장 시 KISA C-TAS · NCS 침해사고 통계로 보정 예정이다.'));

body.push(h('8.7 평가 메트릭의 한계 — F1 점수 도입 곤란', 2));
body.push(p('침해사고 분석에서 “정답 분류”의 ground truth 는 본질적으로 사후 판정이며, 다수의 사고유형이 중첩될 수 있다(예: 자격증명 탈취 → 권한 상승 → 데이터 유출 동시 발생). 본 시스템은 단일 분류 대신 secondary_incident_types 컬럼으로 다중 사고유형을 보존하고, V-8 사후검증으로 수사관 판단을 보완한다. 따라서 일반적 분류 메트릭(F1 등) 대신 “수사관 채택률” + “출처 인용률” 을 정성적 평가 지표로 사용한다.'));

// ───────────────────────── §9 참고 자료 ─────────────────────────
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(h('Ⅸ. 참고 자료', 1));

body.push(h('9.1 외부 표준 (7종 — 학술 변호 핵심)', 2));
body.push(p('본 시스템의 모든 분류·점수·룰은 다음 7종 외부 표준 중 하나 이상을 명시 인용한다. 각 attack_rule · weights · KB 청크에 source 필드로 명기되어 코드 수준에서 추적 가능하다.'));
body.push(bullet('MITRE ATT&CK Cloud Matrix v14 — https://attack.mitre.org/matrices/enterprise/cloud/ — 매핑 룰 74 개의 technique_id 출처'));
body.push(bullet('Google Cloud Threat Intelligence — Cloud Log Configurations — 1.x 카테고리 분류'));
body.push(bullet('KISA 침해사고 분석절차 안내서 (제2010-8호) — 한국인터넷진흥원 — Phase + 초기대응 점검표'));
body.push(bullet('NIST SP 800-86 — Guide to Integrating Forensic Techniques into Incident Response — § 3.1 휘발성 계층 우선순위'));
body.push(bullet('ISO/IEC 27037:2012 — Information technology — Security techniques — Digital evidence 처리'));
body.push(bullet('Cloud Security Alliance — Top Threats to Cloud Computing 2024 — 사고유형 9종 분류 근거'));
body.push(bullet('Verizon Data Breach Investigations Report 2024 — 가중치(weights.json) 통계 근거'));

body.push(h('9.2 학술 논문 — Decision Tree · Bayesian Belief · RAG', 2));
body.push(bullet('Pearl, J. (1988). Probabilistic Reasoning in Intelligent Systems. Morgan Kaufmann. — Bayesian Belief Propagation'));
body.push(bullet('Jaynes, E. T. (1968). Prior Probabilities. IEEE Transactions on Systems Science and Cybernetics, 4(3), 227-241. — Maximum Entropy 원칙 (uniform prior 1/8 정당화)'));
body.push(bullet('Shortliffe, E. H. (1976). Computer-Based Medical Consultations: MYCIN. Elsevier. — 확정도 + 단서 누적 추론'));
body.push(bullet('Lewis, P. et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS. — RAG 원형 논문'));
body.push(bullet('Shannon, C. E. (1948). A Mathematical Theory of Communication. Bell System Technical Journal. — Information Gain · KL divergence'));

body.push(h('9.3 기술 자료', 2));
body.push(bullet('OCSF (Open Cybersecurity Schema Framework) v1.0 — https://schema.ocsf.io/'));
body.push(bullet('Ollama 공식 문서 — https://ollama.ai/docs (gpt-oss:20b · llama3.1:8b)'));
body.push(bullet('LlamaIndex 문서 — https://docs.llamaindex.ai/'));
body.push(bullet('ChromaDB 문서 — https://docs.trychroma.com/'));
body.push(bullet('sentence-transformers — Reimers, N. (2019). Sentence-BERT. EMNLP-IJCNLP. — 다국어 임베딩'));
body.push(bullet('FastAPI / SQLAlchemy / React / Vite 공식 문서'));

body.push(h('9.4 사실 기반 사례 (시연·검증 골든 케이스)', 2));
body.push(bullet('Sysdig (2024). 8-Minute Killchain in NCP. — V-1~V-8 시연 골든 케이스의 사실 기반 근거'));
body.push(bullet('Capital One (2019). S3 SSRF Data Breach Post-Mortem. — 설정 오류 노출(MISCONFIG_EXPOSURE) 사고유형 검증'));

body.push(h('9.5 저장소 및 산출물', 2));
body.push(bullet('Git 저장소: https://github.com/sasumm25-lab/cloud (브랜치 dev3)'));
body.push(bullet('GitHub Actions CI: backend-tests.yml — pytest 129/129 자동 실행 (대표 run 26355406474)'));
body.push(bullet('설계서: 팀 Google Drive AI셰르파_설계서_v2_완성.docx · docs/설계서_읽는법.md'));
body.push(bullet('대조 매트릭스: docs/보고서_대조매트릭스_및_세일링포인트.md'));

// ── 푸터 빌더 ──
const footer = new Footer({
  children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({ text: 'AI Sherpa 최종보고서 — 마지막 섹션 초안 · 팀 로그아웃 · ', font: FONT, size: 18, color: '595959' }),
      new TextRun({ text: '페이지 ', font: FONT, size: 18, color: '595959' }),
      new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18, color: '595959' }),
      new TextRun({ text: ' / ', font: FONT, size: 18, color: '595959' }),
      new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 18, color: '595959' }),
    ],
  })],
});

// ── 문서 구성 ──
const doc = new Document({
  creator: 'AI Sherpa Team (로그아웃)',
  title: 'AI Sherpa 최종보고서 — 마지막 섹션 초안',
  description: '레퍼런스 NFT 미술관 보고서 pp.71-113 패턴에 맞춘 §6 구현 · §7 시험서 · §8 현실적 제한사항 · §9 참고 자료 초안',
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, font: FONT, color: '1F3864' },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 30, bold: true, font: FONT, color: '2F5496' },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 26, bold: true, font: FONT, color: '2E74B5' },
        paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 2 } },
      { id: 'Heading4', name: 'Heading 4', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: FONT, color: '2E74B5' },
        paragraph: { spacing: { before: 140, after: 80 }, outlineLevel: 3 } },
    ],
  },
  numbering: {
    config: [
      { reference: 'bullets',
        levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 }, // A4
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    footers: { default: footer },
    children: body,
  }],
});

const outPath = path.join(__dirname, 'AI_Sherpa_최종보고서_마지막섹션_초안.docx');
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log('OK ->', outPath, '(' + buf.length + ' bytes)');
}).catch(e => {
  console.error('FAIL', e);
  process.exit(1);
});
