/**
 * AI Sherpa 최종보고서 — 구현 목차 옵션 A/B/C + 공통 시험서·시나리오·제한사항 (v2)
 *
 * v2 변경:
 *   - 실제 화면 캡처 PNG 임베드 (captures/V_*.png)
 *   - 실제 백엔드 코드 발췌 임베드 (LogIngestor / OCSFNormalizer / AttackMapper /
 *     GapDetector / LLMEngine / RAGRetriever / BayesNet / graph_analytics /
 *     ReportGenerator)
 *   - 실제 데이터 기반 표 (requirements.txt, package.json, REST API 22개,
 *     KB 4종 통계, 단서 풀 통계, Noisy-OR CPD 등)
 *   - V1~V8 정확한 라우팅 반영 (V3 OCSF, V4 Gap, V5 Board, V6 Attack, V7 Report,
 *     V8 Sherpa)
 *
 * 사용: node build_options.js
 * 출력: 같은 디렉토리에 4개 .docx
 */

const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  AlignmentType, HeadingLevel, LevelFormat, BorderStyle, WidthType, ShadingType,
  PageBreak, PageOrientation, VerticalAlign
} = require('docx');

const ROOT = __dirname;
const CAPTURES = path.join(ROOT, 'captures');

// ───────── 스타일 ─────────
const FONT = 'Malgun Gothic';
const MONO = 'Consolas';

const styles = {
  default: { document: { run: { font: FONT, size: 22 } } },
  paragraphStyles: [
    { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
      run: { size: 32, bold: true, font: FONT, color: '1F3864' },
      paragraph: { spacing: { before: 360, after: 240 }, outlineLevel: 0 } },
    { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
      run: { size: 26, bold: true, font: FONT, color: '2E74B5' },
      paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
    { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
      run: { size: 23, bold: true, font: FONT, color: '2E74B5' },
      paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    { id: 'Heading4', name: 'Heading 4', basedOn: 'Normal', next: 'Normal', quickFormat: true,
      run: { size: 22, bold: true, font: FONT },
      paragraph: { spacing: { before: 160, after: 100 }, outlineLevel: 3 } },
    { id: 'Caption', name: 'Caption', basedOn: 'Normal', next: 'Normal',
      run: { size: 20, italics: true, color: '595959', font: FONT },
      paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 60, after: 200 } } },
    { id: 'NoteSm', name: 'Note Small', basedOn: 'Normal', next: 'Normal',
      run: { size: 18, color: '595959', font: FONT },
      paragraph: { indent: { left: 240 }, spacing: { before: 30, after: 30 } } },
  ]
};

const numbering = {
  config: [
    { reference: 'bullets', levels: [
      { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
    ]},
    { reference: 'numbers', levels: [
      { level: 0, format: LevelFormat.DECIMAL, text: '%1)', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
    ]},
  ]
};

// ───────── 헬퍼 ─────────
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, bold: true })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, bold: true })] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text: t, bold: true })] });
const Body = (t) => new Paragraph({ children: [new TextRun({ text: t })], spacing: { after: 100, line: 320 } });
const Bullet = (t) => new Paragraph({ numbering: { reference: 'bullets', level: 0 }, children: [new TextRun({ text: t })], spacing: { after: 60 } });

// 캡션
const Caption = (t) => new Paragraph({
  alignment: AlignmentType.CENTER,
  style: 'Caption',
  children: [new TextRun({ text: t, italics: true, color: '595959' })],
  spacing: { after: 240 }
});

// 캡처 위치 안내 (이미지가 임베드된 후 짧은 메모)
const CaptureNote = (text, label = '캡처 위치') => new Paragraph({
  style: 'NoteSm',
  children: [
    new TextRun({ text: `└─ ${label}: `, bold: true, color: '385723', size: 18 }),
    new TextRun({ text, color: '595959', size: 18 })
  ]
});

// 실제 이미지 임베드 (PNG 파일에서 읽어옴)
const EmbedImage = (filename, figNum, title, captureLoc, highlights, width = 540) => {
  const fullPath = path.join(CAPTURES, filename);
  if (!fs.existsSync(fullPath)) {
    return [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 120, after: 60 },
        border: {
          top: { style: BorderStyle.DASHED, size: 6, color: '8FAADC' },
          bottom: { style: BorderStyle.DASHED, size: 6, color: '8FAADC' },
          left: { style: BorderStyle.DASHED, size: 6, color: '8FAADC' },
          right: { style: BorderStyle.DASHED, size: 6, color: '8FAADC' }
        },
        children: [new TextRun({ text: `📷 [이미지 자리 — ${filename} 미발견]`, bold: true, color: '5B9BD5', size: 24 })]
      }),
      Caption(`<그림 ${figNum}> ${title}`),
      CaptureNote(captureLoc),
      CaptureNote(highlights, '강조 포인트'),
    ];
  }
  const data = fs.readFileSync(fullPath);
  // 원본 1440x900 → 비율 유지 (3:1.875)
  const height = Math.round(width * 900 / 1440);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 120, after: 60 },
      children: [
        new ImageRun({
          type: 'png',
          data,
          transformation: { width, height },
          altText: { title, description: title, name: filename }
        })
      ]
    }),
    Caption(`<그림 ${figNum}> ${title}`),
    ...(highlights ? [CaptureNote(highlights, '강조 포인트')] : []),
  ];
};

// 코드 블록 — 단일 셀 table 로 음영 + 모노스페이스
const CodeBlock = (figNum, title, codeText, fileRef) => {
  const lines = codeText.split('\n');
  const lineP = lines.map(line => new Paragraph({
    spacing: { before: 0, after: 0, line: 240 },
    children: [new TextRun({
      text: line || ' ',
      font: MONO,
      size: 17,
      color: '1F2937'
    })]
  }));

  const codeTable = new Table({
    width: { size: 9026, type: WidthType.DXA },
    columnWidths: [9026],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: 9026, type: WidthType.DXA },
            shading: { fill: 'F3F4F6', type: ShadingType.CLEAR },
            margins: { top: 120, bottom: 120, left: 180, right: 180 },
            borders: {
              top: { style: BorderStyle.SINGLE, size: 4, color: 'D1D5DB' },
              bottom: { style: BorderStyle.SINGLE, size: 4, color: 'D1D5DB' },
              left: { style: BorderStyle.SINGLE, size: 8, color: '4A90E2' },
              right: { style: BorderStyle.SINGLE, size: 4, color: 'D1D5DB' },
            },
            children: lineP
          })
        ]
      })
    ]
  });

  return [
    codeTable,
    Caption(`<코드 ${figNum}> ${title}`),
    ...(fileRef ? [CaptureNote(fileRef, '경로')] : []),
  ];
};

// 일반 표 빌더 — 헤더 행 + 데이터 행
const BuildTable = (tableNum, title, headers, rows, colWidths) => {
  // headers 길이에 맞게 컬럼 너비 균등 분배 (지정 시 그대로 사용)
  const total = 9026;
  const widths = colWidths || headers.map(() => Math.floor(total / headers.length));
  const border = { style: BorderStyle.SINGLE, size: 4, color: 'BFBFBF' };
  const borders = { top: border, bottom: border, left: border, right: border };

  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      shading: { fill: '1F3864', type: ShadingType.CLEAR },
      borders,
      margins: { top: 100, bottom: 100, left: 120, right: 120 },
      children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: h, bold: true, color: 'FFFFFF', size: 20 })]
      })]
    }))
  });

  const dataRows = rows.map((row, idx) => new TableRow({
    children: row.map((cell, i) => new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      shading: idx % 2 === 0
        ? { fill: 'FFFFFF', type: ShadingType.CLEAR }
        : { fill: 'F2F2F2', type: ShadingType.CLEAR },
      borders,
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      verticalAlign: VerticalAlign.CENTER,
      children: [new Paragraph({
        children: [new TextRun({ text: String(cell), size: 19 })],
        spacing: { line: 280 }
      })]
    }))
  }));

  return [
    new Table({
      width: { size: total, type: WidthType.DXA },
      columnWidths: widths,
      rows: [headerRow, ...dataRows]
    }),
    Caption(`<표 ${tableNum}> ${title}`),
  ];
};

const pageProps = {
  page: {
    size: { width: 11906, height: 16838 },
    margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
  }
};

// ───────── 표지 ─────────
const titlePage = (subtitle, optionLabel) => [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 1200, after: 200 },
    children: [new TextRun({ text: '세종대학교 정보보호학과 캡스톤디자인 2026-1', size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
    children: [new TextRun({ text: 'AI Sherpa 최종보고서', size: 44, bold: true, color: '1F3864' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: [new TextRun({ text: '국내 멀티 클라우드 환경 침해사고 분석 및 대응', size: 28, color: '404040' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 1200 },
    children: [new TextRun({ text: subtitle, size: 26, bold: true, color: '2E74B5' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
    children: [new TextRun({ text: optionLabel, size: 22, italics: true, color: '595959' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
    children: [new TextRun({ text: '※ 본 문서는 V1~V8 8개 뷰 실제 캡처 + 백엔드 코드 발췌 + 의존성/통계 표를 임베드한 완성 초안입니다.', size: 18, color: 'C00000' })] }),
  new Paragraph({ children: [new PageBreak()] })
];

// ───────── 공통 데이터 ─────────

// REST API 목록 — backend/main.py + 각 라우터에서 도출
const REST_API_ROWS = [
  ['1', 'Layer 0', 'POST', '/api/cases', '사고 케이스 신규 생성 (incident_type, csp, severity, occurred_at, observables)'],
  ['2', 'Layer 0', 'GET', '/api/cases/{caseId}', '케이스 상세 조회'],
  ['3', 'Layer 0', 'PATCH', '/api/cases/{caseId}', '케이스 부분 갱신 (severity, system_config, observables 등)'],
  ['4', 'Layer 0', 'GET', '/api/guide/v2', 'CollectionGuideV2 — 사고유형×CSP 기반 우선순위 체크리스트'],
  ['5', 'Layer 0', 'GET', '/api/guide/preview', '사고유형 변경 시 가이드 미리보기 (Phase K.1, byungwoo)'],
  ['6', 'Layer 0', 'POST', '/api/clue-tree/start', 'Evidence Tree 단서 탐색 시작 (143 단서 풀)'],
  ['7', 'Layer 0', 'POST', '/api/clue-tree/answer', '단서 확정/거부 → Bayesian 사후확률 재계산'],
  ['8', 'Layer 0', 'GET', '/api/triage/state', 'Triage 진행 상태 (사후확률·확정 단서·다음 후보)'],
  ['9', 'Layer 1', 'POST', '/api/logs/upload', '멀티파트 로그 업로드 + SHA-256 무결성'],
  ['10', 'Layer 1', 'GET', '/api/logs', '케이스의 raw_events 페이지네이션 조회'],
  ['11', 'Layer 1', 'GET', '/api/logs/{eventId}', '원본 이벤트 단건 조회'],
  ['12', 'Layer 2', 'POST', '/api/analysis/normalize', 'OCSF 1.3 정규화 (raw → ocsf_events)'],
  ['13', 'Layer 2', 'POST', '/api/analysis/map', 'MITRE ATT&CK 매핑 (ocsf → attack_events)'],
  ['14', 'Layer 2', 'GET', '/api/analysis/ocsf', '정규화 결과 조회 + 매핑 룰 메타'],
  ['15', 'Layer 2', 'GET', '/api/analysis/attack', 'ATT&CK 매핑 결과 + 전술 커버리지'],
  ['16', 'Layer 2', 'POST', '/api/analysis/gap', '갭 감지 (COLLECTION / EVIDENCE / INTERPRETATION / NONE)'],
  ['17', 'Layer 3', 'POST', '/api/sherpa/brief', '컨텍스트 브리핑 (RAG → LLM 요약)'],
  ['18', 'Layer 3', 'POST', '/api/sherpa/suggest', '빠진 고리 후보 제안 (체인 + KB 교차 검색)'],
  ['19', 'Layer 3', 'POST', '/api/sherpa/playbook', '플레이북 추천 (사고유형별 대응 절차)'],
  ['20', 'Layer 3', 'POST', '/api/sherpa/chat', '자연어 질의 응답 + 출처 청크'],
  ['21', 'Layer 4', 'POST', '/api/board/nodes', '체인 노드 추가 (PENDING/CONFIRMED/REJECTED)'],
  ['22', 'Layer 4', 'PATCH', '/api/board/nodes/{nodeId}', '노드 수락·거부 + ActionLog 동시 적재'],
  ['23', 'Layer 4', 'POST', '/api/board/edges', '체인 엣지 추가 (방향성)'],
  ['24', 'Layer 4', 'GET', '/api/board', '보드 상태 (노드·엣지·정합성)'],
  ['25', 'Layer 4', 'POST', '/api/report', 'KISA 양식 보고서 초안 생성 (Jinja2 + python-docx)'],
  ['26', 'Layer 4', 'PATCH', '/api/report/{caseId}', '보고서 섹션 수정'],
  ['27', 'Layer 4', 'GET', '/api/report/{caseId}/export', 'DOCX/PDF 내보내기 (reportlab 한글 폰트 자동 등록)'],
  ['28', 'Common', 'GET', '/api/actions', '액션 로그 조회'],
  ['29', 'Common', 'GET', '/api/health', '서버 헬스 체크 (deep=true 시 Ollama/ChromaDB 실측)'],
];

// 백엔드 의존성
const BACKEND_DEPS = [
  ['fastapi', '0.115+', '웹 프레임워크 (REST API)'],
  ['uvicorn[standard]', '0.30.6+', 'ASGI 서버'],
  ['python-multipart', '0.0.9+', '멀티파트 파일 업로드 (Layer 1)'],
  ['sqlalchemy', '2.0.35+', 'ORM (9개 테이블)'],
  ['chromadb', '0.5.5+', '벡터 DB (RAG, 오프라인 임베디드)'],
  ['sentence-transformers', '3.0+', '다국어 임베딩 (paraphrase-multilingual-MiniLM-L12-v2)'],
  ['jinja2', '3.1.4+', '보고서 템플릿 엔진'],
  ['python-docx', '1.1.2+', 'DOCX 보고서 생성'],
  ['reportlab', '4.5+', 'PDF 산출물 + 한글 폰트 자동 등록'],
  ['pydantic', '2.10+', '요청/응답 스키마 검증'],
  ['requests', '2.32+', 'HTTP 클라이언트'],
  ['httpx', '0.27+', 'Ollama Chat API 비동기 호출 (Layer 3)'],
  ['pgmpy', '1.1.2', 'Bayesian Network + NoisyOrCPD (Phase H, byungwoo)'],
  ['pyyaml', '6.0+', 'Atomic Red Team YAML 정의 파싱'],
];

// 프론트엔드 의존성
const FRONTEND_DEPS = [
  ['react', '^18.3.1', 'UI 라이브러리'],
  ['react-dom', '^18.3.1', 'DOM 렌더러'],
  ['react-router-dom', '^6.26.0', '클라이언트 라우팅 (V1~V8)'],
  ['zustand', '^4.5.4', '상태 관리 (useCaseStore 등 9개 스토어)'],
  ['axios', '^1.7.4', 'HTTP 클라이언트 (api/client.ts)'],
  ['@tanstack/react-query', '^5.51.0', '서버 상태 캐싱/리페치'],
  ['reactflow', '^11.11.4', '공격 체인 노드-엣지 시각화 (V5 Board)'],
  ['d3', '^7.9.0', '컴퍼스·히트맵 시각화'],
  ['typescript', '^5.5.4', '타입 시스템'],
  ['vite', '^5.4.0', '개발 서버 + 번들러'],
  ['tailwindcss', '^3.4.9', 'CSS 유틸리티'],
];

// KB 4종 통계 (V8 화면 캡처에서 추출)
const KB_STATS = [
  ['MITRE ATT&CK for Cloud', '38청크', 'Cloud Matrix 기법·전술·하위기법 (T1078.004 외)'],
  ['대응 플레이북', '25청크', '사고유형별 대응 절차 (KISA 가이드 기반)'],
  ['CSP 공식 문서', '22청크', 'NCP·NHN 보안 가이드 발췌 (오프라인 임베드)'],
  ['침해사고 사례 DB', '45청크', '국내·해외 침해사고 사례 요약 (출처 표기)'],
];

// 단서 풀 통계
const CLUE_STATS = [
  ['총 단서 수', '143개', 'clue_catalog.json 기준'],
  ['ATT&CK 매핑 단서', '143개 (100%)', 'clue_to_attack.json 풀 커버리지'],
  ['사고유형 prior', '8종 균등', 'Uniform prior P(H)=0.125 (Jaynes 1968 Maximum Entropy)'],
  ['Noisy-OR leak', '0.05', 'Pearl 1988 baseline noise — 설명 없이 관측될 확률'],
  ['CPD 학습', '개발자 PC 1회', '운영 시 정적 JSON 활용 — 폐쇄망 친화'],
];

// 코드 발췌 — 실제 backend/ 파일에서 추출 (가독성 위해 일부만)
const CODE_INTAKE = `# backend/api/intake.py — 사고 케이스 생성 API
@router.post("/cases", status_code=status.HTTP_201_CREATED)
async def create_case(req: CreateCaseRequest, db: Session = Depends(get_db)) -> dict:
    """사고 케이스를 신규 생성한다 (Layer 0 진입점)."""
    case = IncidentCase.create(
        incident_type=req.incident_type,
        csp=req.csp,
        severity=req.severity,
        occurred_at=req.occurred_at,
        system_config=req.system_config,
        title=req.title,
        tlp=req.tlp,
        observables=req.observables,
    )
    db.add(case.to_model()); db.commit()
    return {"status": "ok", "data": _serialize(case)}`;

const CODE_INGEST = `# backend/core/ingestion/log_ingestor.py
class LogIngestor:
    """로그 수집 도메인 — 업로드→해시→파싱→적재→매칭 파이프라인."""

    @staticmethod
    def verify_hash(content: bytes) -> str:
        """파일 바이트의 SHA-256 hex digest 반환 (무결성)."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def parse(csp: str, content: bytes) -> list[dict]:
        """csp 에 맞는 파서를 호출하여 평탄화 dict 리스트 반환."""
        if csp == "naver": return ncp_parser.parse(content)
        if csp == "nhn":   return nhn_parser.parse(content)
        raise ValueError(f"지원하지 않는 csp: {csp}")

    @classmethod
    def ingest(cls, db, case, filename, content: bytes) -> IngestionStats:
        sha256 = cls.verify_hash(content)
        parsed = cls.parse(case.csp, content)
        stats = IngestionStats(sha256=sha256, source_file=filename)
        for ev in parsed:
            target_id = matchers.match(case.csp, case.incident_type, ev)
            stats.total_events += 1
            (stats.matched if target_id else stats.unmatched) += 1
            db.add(RawEventModel(case_id=case.case_id, ...))
        db.commit()
        return stats`;

const CODE_OCSF = `# backend/core/analysis/ocsf_normalizer.py
def _load_rules(csp: str) -> Optional[dict]:
    """csp(naver/nhn)의 mapping rule JSON 을 로드/캐시 (startup 1회)."""
    if csp in _RULE_CACHE: return _RULE_CACHE[csp]
    fname = _CSP_TO_FILE.get(csp)
    path = settings.MAPPING_RULES_DIR / fname
    with open(path, "r", encoding="utf-8") as f:
        rules = json.load(f)
    _RULE_CACHE[csp] = rules
    return rules


def normalize(db, case, raw_event) -> OCSFEventModel:
    """raw_events → ocsf_events 변환 (5.2.1절 필드 매핑)."""
    rules = _load_rules(case.csp)
    raw = json.loads(raw_event.raw_json)

    ocsf = {}
    for ocsf_field, mapping in rules["field_mappings"].items():
        value = _get_nested(raw, mapping["source"])
        if mapping.get("transform") == "datetime":
            value = _normalize_datetime(value)
        elif mapping.get("transform") == "status_code":
            value = 200 if value == "SUCCESS" else 500
        ocsf[ocsf_field] = value

    # 매핑되지 않은 원본 필드는 unmapped_raw 에 보존
    return OCSFEventModel(**ocsf, unmapped_raw=json.dumps(raw))`;

const CODE_ATTACK = `# backend/core/analysis/attack_mapper.py
def _load_rules() -> list[dict]:
    """attack_rules/rules.json 로딩 + Regex 컴파일 (startup 1회 캐시)."""
    global _RULES_CACHE
    if _RULES_CACHE is not None: return _RULES_CACHE
    path = settings.ATTACK_RULES_DIR / "rules.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rules = []
    for rule in data.get("rules", []):
        compiled = re.compile(rule["activity_name_pattern"])
        rules.append({**rule, "_re": compiled})
    _RULES_CACHE = rules
    return rules


def map_attack(db, case_id) -> list[AttackEventModel]:
    """ocsf_events → attack_events 규칙 기반 매핑."""
    rules = _load_rules()
    for ocsf in db.query(OCSFEventModel).filter_by(case_id=case_id):
        for rule in rules:
            if rule["csp"] != ocsf.csp: continue
            if rule["_re"].search(ocsf.activity_name or ""):
                db.add(AttackEventModel(
                    ocsf_id=ocsf.ocsf_id,
                    technique_id=rule["technique_id"],
                    tactic=rule["tactic"],
                    rule_id=rule["rule_id"],
                ))
                break  # 첫 매칭 룰 채택`;

const CODE_GAP = `# backend/core/analysis/gap_detector.py
class GapDetector:
    """갭 감지기 — 케이스 단위 분류 + gap_results INSERT.

    분류 (가장 심각한 것 우선):
      COLLECTION    : 필수 증거 미수집 → Layer 0 복귀 권장
      INTERPRETATION: 매핑 안 된 이벤트 다수 → AI 셰르파 브리핑 권장
      EVIDENCE      : 매핑 결과는 있으나 부족 → 수사관 직접 판단
      NONE          : 갭 없음 → 수사 보드(Layer 4) 진행
    """

    @classmethod
    def detect(cls, db, case_id: str) -> Optional[dict]:
        case = db.get(IncidentCaseModel, case_id)
        required_ids = {t.target_id for t in cls._required_targets(db, case)}
        collected_ids = cls._collected_target_ids(db, case_id)
        missing = required_ids - collected_ids

        if missing:
            gap_type, note = "COLLECTION", f"{len(missing)}건 필수 증거 누락"
        elif cls._mapping_rate(db, case_id) < _INTERPRETATION_THRESHOLD:
            gap_type, note = "INTERPRETATION", "매핑률 30% 미만"
        elif cls._attack_count(db, case_id) == 0:
            gap_type, note = "EVIDENCE", "ATT&CK 매핑 결과 없음"
        else:
            gap_type, note = "NONE", "갭 없음 — Layer 4 진행 가능"

        db.add(GapResultModel(case_id=case_id, gap_type=gap_type, note=note))
        db.commit()
        return {"gap_type": gap_type, "missing": list(missing), "note": note}`;

const CODE_BAYES = `# backend/core/intake/bayes_net.py (byungwoo, Phase H 2026-05-25)
# Pearl 1988 Noisy-OR + BAN paper IEEE 2023 — 3-layer DAG:
#   Layer 1 (latent)    H_k  = 8 incident_type (가설)
#   Layer 2 (latent)    T_i  = 45 ATT&CK 기법 (TTPs)
#   Layer 3 (observable) C_j = 143 단서 (DAG 노드)

NOISY_OR_LEAK = 0.05  # baseline noise — 설명 없이 관측될 확률

def noisy_or(q_list: list[float], leak: float = NOISY_OR_LEAK) -> float:
    """Pearl 1988 Noisy-OR aggregation:
        P(child=1 | parents=set) = 1 - (1 - leak) × ∏ (1 - q_i)
    """
    prob_not = 1.0 - leak
    for q in q_list:
        prob_not *= 1.0 - max(0.0, min(1.0, q))
    return 1.0 - prob_not


def clue_likelihood_via_bn(clue_key: str) -> dict[str, float]:
    """단서 c 의 likelihood L(c | h) 를 ATT&CK 기법 경유로 계산.

        L(c | h) ∝ NoisyOR({ q_{t,h} × confidence | t in mapping[c].techniques })
        q_{t,h} = technique_likelihood(t)[h]  # Laplace smoothed

    매핑 없거나 weights 0 → legacy fallback (weights.json 직접 사용).
    """
    mapping = load_clue_to_attack()["mappings"].get(clue_key)
    if not mapping or not mapping.get("techniques"):
        return _legacy_likelihood(clue_key)

    likelihood = {}
    for h in INCIDENT_TYPES_8:
        q_list = []
        for tech in mapping["techniques"]:
            tw = technique_likelihood(tech["id"])
            q_list.append(tw[h] * tech.get("confidence", 1.0))
        likelihood[h] = noisy_or(q_list)
    return _normalize(likelihood)`;

const CODE_LLM = `# backend/core/sherpa/llm_engine.py
class LLMEngine:
    """Ollama 통합 sLLM 엔진. 검색·요약·제안만 — 판단 X."""

    @classmethod
    async def generate(cls, query: str, context: list[KBChunk]) -> str:
        prompt = cls._build_prompt(query, context)
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            res = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                }
            )
        text = res.json()["message"]["content"]
        text = _strip_reasoning(text)  # <thinking>...</thinking> 제거
        text = _strip_unsourced_techniques(text, context)  # KB 청크 밖 ID 자동 라벨링
        return text


SYSTEM_PROMPT = """당신은 침해사고 수사관의 검색 도우미 AI 셰르파입니다.
역할: 검색·요약·제안 (판단·결정 금지).
모든 답변은 한국어 + 출처 [N] 인용 + "최종 판단은 수사관" 문구 포함.
KB 청크에 없는 ATT&CK 기법 ID 는 새로 만들지 마세요."""`;

const CODE_RAG = `# backend/core/sherpa/rag_retriever.py
def retrieve(
    query: str, k: int = 5, kb_filter: Optional[list[str]] = None
) -> list[tuple[KBChunk, float]]:
    """KB 검색 — ChromaDB 우선, 키워드 fallback.

    1) ChromaDB 의미 검색 (paraphrase-multilingual-MiniLM-L12-v2)
    2) ChromaDB 미설치/임베드 안 됨 → 키워드 매칭 fallback
    """
    if _embed_kb and _embed_kb.is_ready():
        return _embed_kb.query(query, k=k, kb_filter=kb_filter)
    return _keyword_retrieve(query, k, kb_filter)


def _keyword_retrieve(query, k, kb_filter):
    """fallback: 토큰 중복 + 길이 가중치."""
    chunks = [c for c in load_all() if (not kb_filter or c.kb_name in kb_filter)]
    tokens = _tokenize(query)
    scored = [(c, _keyword_score(tokens, c)) for c in chunks]
    scored = [(c, s) for c, s in scored if s > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]`;

const CODE_GRAPH = `# backend/core/board/graph_analytics.py (byungwoo, Phase J 2026-05-26)
import networkx as nx

def build_graph(nodes: list[dict], edges: list[dict]) -> nx.DiGraph:
    """chain_nodes + chain_edges → networkx DiGraph (in-memory, 결정성 100%)."""
    g = nx.DiGraph()
    for n in nodes:
        g.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
    for e in edges:
        g.add_edge(e["src"], e["dst"], **e)
    return g


def pagerank(g: nx.DiGraph) -> dict[str, float]:
    """Brin & Page 1998 — 공격자가 노린 중심 자산 자동 강조."""
    return nx.pagerank(g, alpha=0.85)


def label_propagation(g: nx.DiGraph) -> list[set]:
    """Zhu & Ghahramani 2002 — 의심 계정 군집 (blast radius)."""
    return list(nx.community.label_propagation_communities(g.to_undirected()))


def validate_chain(g: nx.DiGraph) -> dict:
    """체인 정합성 — 사이클 + 위상 정렬 + 시간순 일관성."""
    try:
        order = list(nx.topological_sort(g))
        is_dag = True
    except nx.NetworkXUnfeasible:
        order, is_dag = [], False
    return {"is_dag": is_dag, "order": order, "node_count": g.number_of_nodes()}`;

const CODE_REPORT = `# backend/core/board/report_generator.py
class ReportGenerator:
    """Layer 4 — KISA 양식 보고서 초안 생성."""

    @classmethod
    def generate(cls, db, case_id: str) -> dict:
        case = db.get(IncidentCaseModel, case_id)
        ctx = {
            "case": case,
            "ocsf_events": list(db.query(OCSFEventModel).filter_by(case_id=case_id)),
            "attack_events": list(db.query(AttackEventModel).join(OCSFEventModel)...),
            "chain": cls._build_chain_summary(db, case_id),
            "gap_history": list(db.query(GapResultModel)...),
        }

        # 8섹션 (사고 개요·타임라인·영향분석·ATT&CK·대응조치·권고사항·...)
        sections = cls._render_sections(ctx)
        path = settings.REPORTS_DIR / f"{case_id}.json"
        path.write_text(json.dumps(sections, ensure_ascii=False, indent=2))
        return {"caseId": case_id, "sections": sections, "status": "draft"}

    @classmethod
    def export_docx(cls, db, case_id: str) -> Path:
        sections = json.loads((settings.REPORTS_DIR / f"{case_id}.json").read_text())
        doc = Document()
        doc.add_heading(sections["title"], level=0)
        for sec_key, sec_text in sections["body"].items():
            doc.add_heading(sec_key, level=1)
            doc.add_paragraph(sec_text)
        out = settings.EXPORTS_DIR / f"{case_id}.docx"
        doc.save(out); return out`;

// ───────── 옵션 A — 5계층 파이프라인 ─────────
const buildOptionA = () => {
  const children = [
    ...titlePage('구현 단원 — 옵션 A', '5계층 파이프라인 (Recommended)'),

    H1('Ⅸ. 구현'),
    Body('본 장에서는 설계 단원에서 정의한 5계층 파이프라인 아키텍처에 따라 실제 구현된 모듈을 계층 단위로 기술한다. 각 계층은 백엔드 비즈니스 로직(core/), REST 라우터(api/), 프론트엔드 뷰(views/), 그리고 데이터베이스 스키마(db/)로 구성되며, 백엔드 8000번 포트의 FastAPI 서버와 프론트엔드 5173번 포트의 React 18 + Vite 5 개발 서버가 동시에 가동된다.'),

    // ──── Layer 0 ────
    H2('1. Layer 0 — 사고 접수 및 초동 수집 가이드 구현'),
    Body('Layer 0 은 수사관이 사고를 접수하고 초동 수집 체크리스트를 받기까지를 책임진다. 백엔드는 backend/core/intake 패키지, 프론트엔드는 V1_Setup 뷰(`/setup` 경로)와 매핑된다.'),

    H3('1) 사고 케이스 위저드 (V1 Setup) — 5단계 입력 흐름'),
    Body('수사관이 5단계 위저드로 사고 정보를 입력하면 IncidentCase 객체가 생성되어 incident_cases 테이블에 INSERT 된다. 진행 단계는 ① 분석 환경(CSP 선택) → ② 케이스 메타 → ③ 시스템 구성 → ④ 단서 루프(Evidence Tree) → ⑤ 수집 가이드 순이다. Zustand 의 useCaseStore 가 위저드 상태를 localStorage 에 영속화하여 새로고침·탭 이동 시에도 caseId 가 유지된다.'),
    ...EmbedImage('V_setup.png', 'Ⅸ-1-1', 'V1 Setup Step 0 — 분석 환경(CSP) 선택 화면',
      'http://localhost:5173/setup 진입 첫 화면',
      '5단계 진행바, Naver Cloud Platform(기본값) / NHN Cloud 카드, 하위 서비스 칩, 우상단 OFFLINE 배지'),
    ...CodeBlock('Ⅸ-1-1', 'POST /api/cases — 사고 케이스 생성 API', CODE_INTAKE, 'backend/api/intake.py'),

    H3('2) CollectionGuideV2 — 규칙 기반 체크리스트 자동 생성'),
    Body('GET /api/guide/v2?caseId= 호출 시 사고 유형과 CSP 조합에 맞는 우선순위 수집 체크리스트를 자동 생성한다. AI를 사용하지 않는 순수 규칙 기반 엔진으로, collection_targets 테이블의 카탈로그에서 (incident_type, csp) 조건으로 매칭한다. evidence_role 컬럼이 REQUIRED 인 항목은 빨간 배지, CORROBORATING 은 노란 배지로 표시된다.'),

    H3('3) Evidence Tree 기반 단서 탐색 (byungwoo Phase K~M)'),
    Body('143개의 단서(clue) 풀과 8종 사고유형 간의 사후확률을 Bayesian Network 로 계산하여 수사관에게 다음 탐색 대상을 추천하는 모듈이다. pgmpy 1.1.2 의 NoisyOrCPD 클래스를 활용하며, 학습은 개발자 PC 에서 1회만 수행하고 운영은 정적 JSON 으로 폐쇄망 친화 설계를 유지한다. IncidentTypeCompass 컴퍼스는 9개 사고 유형(8종 + UNCLASSIFIED)의 사후확률을 saturation 깊이별 그라디언트로 시각화하며, 1위 anchor 가 헤더에 통일된다.'),
    ...BuildTable('Ⅸ-1', '단서 풀 및 Bayesian Network 통계', ['항목', '값', '비고'], CLUE_STATS, [3000, 2500, 3526]),
    ...CodeBlock('Ⅸ-1-2', 'BayesNet — Noisy-OR aggregation (Pearl 1988)', CODE_BAYES, 'backend/core/intake/bayes_net.py'),

    // ──── Layer 1 ────
    H2('2. Layer 1 — 로그 수집 및 무결성 검증 구현'),
    Body('Layer 1 은 multipart/form-data 로 업로드된 CSP 로그 파일을 SHA-256 으로 무결성 검증한 뒤, CSP 별 파서로 raw 이벤트를 분해하여 raw_events 테이블에 적재한다. 동시에 collection_targets 카탈로그와 매칭하여 matched_target_id 를 채워 후속 갭 감지의 기반을 마련한다.'),
    ...EmbedImage('V_logs_with_case.png', 'Ⅸ-2-1', 'V2 Logs — DropZone 업로드 + 매칭 분포 화면',
      'http://localhost:5173/logs (활성 케이스 선택 상태)',
      '4개 KPI 카드(총 수집/매칭/미매칭/파일), DropZone(JSON·CSV·JSONL), 매칭 분포 패널, 우상단 "OCSF 정규화 →" 버튼'),
    ...CodeBlock('Ⅸ-2-1', 'LogIngestor — SHA-256 + 멀티파트 수집 파이프라인', CODE_INGEST, 'backend/core/ingestion/log_ingestor.py'),

    Body('byungwoo dev3 에서 추가된 LogAnalysisFab(우하단 주황 플로팅) 은 업로드 진행 중 실시간 매칭률·매핑 룰·갭 후보를 보여주는 보조 패널이다. useLogAnalysisStore Zustand 스토어로 상태를 관리하며 V2 외 모든 뷰에서 항상 노출된다.'),

    // ──── Layer 2 ────
    H2('3. Layer 2 — OCSF 정규화 및 ATT&CK 매핑 구현'),
    Body('Layer 2 는 CSP 별 원본 로그를 OCSF 1.3 표준 스키마로 정규화한 뒤, MITRE ATT&CK Cloud Matrix 의 기법으로 규칙 기반 매핑한다. 매핑 후 GapDetector 가 케이스의 수집·증거·해석 완결성을 판정한다.'),

    H3('1) OCSFNormalizer — CSP 별 매핑 룰 + nested dot 접근'),
    Body('backend/data/mapping_rules/ncp_cloudtrail.json 과 nhn_cloud_trail.json 의 JSON 룰셋을 startup 시 1회 로드하여 메모리 캐시한다. eventTime → time 같은 단순 매핑부터 SUCCESS/FAIL → 200/500 변환, content.actionUserName 같은 dot 표기 nested 접근까지 처리하며, 매핑되지 않은 원본 필드는 unmapped_raw 컬럼에 JSON 그대로 보존하여 향후 룰 확장 시 손실 없이 재처리 가능하다.'),
    ...EmbedImage('V_ocsf_with_case.png', 'Ⅸ-3-1', 'V3 OCSF — 정규화 결과 + 필드 매핑 상세표',
      'http://localhost:5173/ocsf',
      '스키마 버전(OCSF 1.3), 좌하단 필드 매핑 상세표(CSP 원본 → OCSF 필드 → 규칙), 우상단 "갭 감지 →" 버튼'),
    ...CodeBlock('Ⅸ-3-1', 'OCSFNormalizer — 룰 로딩 + nested 접근 + 변환', CODE_OCSF, 'backend/core/analysis/ocsf_normalizer.py'),

    H3('2) AttackMapper — 규칙 기반 ATT&CK technique_id 부여'),
    Body('backend/data/attack_rules/rules.json 의 룰셋에서 각 OCSF 이벤트의 activity_name 을 Regex 로 매칭하여 첫 번째로 매칭되는 룰의 technique_id 와 tactic 을 attack_events 테이블에 INSERT 한다. 룰 순서는 구체성 높은 룰을 앞쪽에 배치하여 결정성을 확보한다.'),
    ...EmbedImage('V_attack_with_case.png', 'Ⅸ-3-2', 'V6 Attack — ATT&CK 매핑 결과 화면',
      'http://localhost:5173/attack',
      'KPI 3개(탐지된 기법/전술 커버리지/매핑 이벤트), 매핑 결과 안내 패널, 우상단 "보고서 →" 버튼'),
    ...CodeBlock('Ⅸ-3-2', 'AttackMapper — Regex 매칭 + 첫 매칭 룰 채택', CODE_ATTACK, 'backend/core/analysis/attack_mapper.py'),

    H3('3) GapDetector — 4종 갭 분류 (COLLECTION / EVIDENCE / INTERPRETATION / NONE)'),
    Body('필수 증거 미수집은 COLLECTION 갭으로 분류되어 Layer 0 복귀가 권장된다. 매핑률 30% 미만은 INTERPRETATION 갭으로 AI 셰르파 브리핑이 권장되고, ATT&CK 매핑 결과가 0건이면 EVIDENCE 갭으로 수사관 직접 판단으로 위임된다. NONE 이면 Layer 4 진행이 가능하다.'),
    ...EmbedImage('V_gap_with_case.png', 'Ⅸ-3-3', 'V4 Gap — 갭 감지 실행 대기 화면',
      'http://localhost:5173/gap',
      '실행 대기 상태 안내, 우상단 "갭 감지 실행" 버튼, 사이드바 GAP DETECT 활성'),
    ...CodeBlock('Ⅸ-3-3', 'GapDetector.detect() — 4종 갭 분류 우선순위', CODE_GAP, 'backend/core/analysis/gap_detector.py'),

    // ──── Layer 3 ────
    H2('4. Layer 3 — 오프라인 AI 셰르파 구현'),
    Body('Layer 3 은 폐쇄망 환경에서 동작하는 sLLM(Ollama Llama 3.1 / GPT-OSS) + RAG(ChromaDB + sentence-transformers) 조합으로 구성된다. 4가지 안전한 역할(컨텍스트 브리핑·빠진 고리 후보·플레이북 추천·자연어 Q&A) 만 수행하며 판단·결정은 일절 하지 않는다.'),

    H3('1) LLMEngine — Ollama 통합 + reasoning 토큰 후처리'),
    Body('httpx 비동기 클라이언트로 Ollama Chat API(/api/chat) 를 호출하며, 30초 timeout(SNF-02) 시 fallback 메시지를 반환한다. GPT-OSS 의 <thinking>...</thinking> 같은 reasoning 토큰은 _strip_reasoning() 으로 제거되며, KB 청크 밖의 ATT&CK 기법 ID 가 응답에 나타나면 _strip_unsourced_techniques() 후처리로 자동 라벨링되어 AI 환각이 차단된다.'),
    ...CodeBlock('Ⅸ-4-1', 'LLMEngine — Ollama Chat + 후처리', CODE_LLM, 'backend/core/sherpa/llm_engine.py'),

    H3('2) RAGRetriever — ChromaDB 의미 검색 + 키워드 fallback'),
    Body('paraphrase-multilingual-MiniLM-L12-v2 다국어 임베딩으로 KB 4종을 ChromaDB 에 색인하여 의미 검색을 수행한다. ChromaDB · sentence-transformers 미설치 환경에서는 자동으로 키워드 매칭 fallback 으로 동작하여 어떤 환경에서도 RAG 가 끊기지 않는다.'),
    ...EmbedImage('V_sherpa_with_case.png', 'Ⅸ-4-1', 'V8 Sherpa — AI 셰르파 자연어 Q&A + KB 인덱스 사이드바',
      'http://localhost:5173/sherpa',
      '엔진 상태(ollama 연결됨), KB 인덱스(MITRE 38·플레이북 25·CSP 22·사례 45), 활용 안내, 샘플 질문 칩 3종, 환각 차단 정책 안내문'),
    ...CodeBlock('Ⅸ-4-2', 'RAGRetriever — 의미 검색 + fallback 분기', CODE_RAG, 'backend/core/sherpa/rag_retriever.py'),

    H3('3) KB 4종 임베딩 통계'),
    ...BuildTable('Ⅸ-2', 'KB 4종 통계 (V8 Sherpa 실측)', ['지식베이스', '청크 수', '내용 요약'], KB_STATS, [3000, 1500, 4526]),

    // ──── Layer 4 ────
    H2('5. Layer 4 — Investigation Board 및 보고서 구현'),

    H3('1) reactflow 기반 공격 체인 시각화 (V5 Board)'),
    Body('V5 Board 뷰는 reactflow 11.11 라이브러리로 chain_nodes·chain_edges 테이블의 데이터를 노드-엣지 그래프로 시각화한다. AI 제안 노드(is_ai_suggested=true) 는 점선, 수락 노드(CONFIRMED) 는 실선으로 구분되며, 우측 사이드바에는 Mandiant M-Trends 2024 의 Dwell Time 벤치마크(7일) 가 함께 표시되어 수사관이 사고 진행 속도를 가늠할 수 있다.'),
    ...EmbedImage('V_board_with_case.png', 'Ⅸ-5-1', 'V5 Board — 수사 보드 (Dwell Time + 그래프 캔버스 + AI 브리핑)',
      'http://localhost:5173/board',
      'Dwell Time 벤치마크 패널, 공격 체인 그래프 캔버스, 상세/AI 브리핑/수사관 메모/수집 로그 사이드바'),

    H3('2) graph_analytics — networkx 기반 체인 분석 (byungwoo Phase J)'),
    Body('PageRank(Brin & Page 1998)로 공격자가 노린 중심 자산을 자동 강조하고, Label Propagation(Zhu & Ghahramani 2002)으로 의심 계정 군집(blast radius)을 산출한다. 체인 정합성은 networkx 의 topological_sort 로 사이클·시간 역전을 자동 검증하며, V5 Board 상단에 "정합 OK / 사이클 감지 / 시간 역전" 배지로 노출된다.'),
    ...CodeBlock('Ⅸ-5-1', 'graph_analytics — PageRank + Label Propagation + Validate', CODE_GRAPH, 'backend/core/board/graph_analytics.py'),

    H3('3) ReportGenerator — KISA 양식 8섹션 자동 초안 + DOCX/PDF'),
    Body('POST /api/report 호출 시 케이스 메타·매핑 결과·체인 노드·갭 이력을 Jinja2 컨텍스트로 묶어 KISA 침해사고 보고서 양식의 8섹션 초안(사고 개요·타임라인·영향 분석·ATT&CK 결과·대응 조치·권고사항·...)을 생성한다. python-docx 1.1 로 DOCX 를, reportlab 4.5 로 PDF 를 생성하며, 한글 폰트는 시스템의 malgun.ttf 를 자동 등록한다.'),
    ...EmbedImage('V_report_with_case.png', 'Ⅸ-5-2', 'V7 Report — 8섹션 초안 + DOCX/PDF 내보내기',
      'http://localhost:5173/report',
      '상단 KPI(draft/865 chars/caseId), 8섹션 그리드(사고 개요/타임라인/영향 분석/ATT&CK 결과/대응 조치/권고사항 등), 우상단 "AI 초안 재생성"·"저장"·"DOCX"·"최종화" 버튼'),
    ...CodeBlock('Ⅸ-5-2', 'ReportGenerator — Jinja2 + python-docx 8섹션 생성', CODE_REPORT, 'backend/core/board/report_generator.py'),
  ];

  return new Document({ styles, numbering, sections: [{ properties: pageProps, children }] });
};

// ───────── 옵션 B — 환경 + 5계층 (6 sections) ─────────
const buildOptionB = () => {
  const children = [
    ...titlePage('구현 단원 — 옵션 B', '환경 + 5계층 파이프라인 (6 sections)'),

    H1('Ⅸ. 구현'),
    Body('본 장은 옵션 A 의 5계층 구성에 "시스템 구축 환경" 단원을 별도로 추가한 6단 구조이다. 환경·의존성·REST API 명세를 1장에 모아 채점자가 기술 스택을 한눈에 파악하도록 구성하며, 이후 2~6장에서 Layer 0~4 의 실제 구현을 기술한다.'),

    H2('1. 시스템 구축 환경'),

    H3('1) 백엔드 의존성 (Python 3.10+ / FastAPI / SQLite)'),
    ...BuildTable('Ⅸ-1', '백엔드 의존성 (backend/requirements.txt 기준)',
      ['라이브러리', '버전', '용도'], BACKEND_DEPS, [2400, 1600, 5026]),

    H3('2) 프론트엔드 의존성 (React 18 / Vite 5 / TypeScript 5.5)'),
    ...BuildTable('Ⅸ-2', '프론트엔드 의존성 (frontend/package.json 기준)',
      ['라이브러리', '버전', '용도'], FRONTEND_DEPS, [2400, 1600, 5026]),

    H3('3) DB 9개 테이블 ERD'),
    Body('SQLite 3 + SQLAlchemy 2.0 Declarative 모델. PK 는 모두 VARCHAR(36) UUID4, FK 는 incident_cases.case_id 를 루트로 한다. JSON 컬럼(system_config, observables, raw_json, unmapped_raw, detail)은 TEXT 로 저장한다. 9개 테이블은 incident_cases · collection_targets · raw_events · ocsf_events · attack_events · gap_results · chain_nodes · chain_edges · action_logs 이다.'),

    H3('4) REST API 29개 엔드포인트'),
    Body('FastAPI APIRouter 로 계층별 1파일씩 분리(intake.py · ingestion.py · analysis.py · sherpa.py · board.py · report.py · common.py · triage.py · clue_tree.py). 모든 응답은 {status, data} 통일 형식이며, 에러는 {status, message, code} 로 반환된다.'),
    ...BuildTable('Ⅸ-3', 'REST API 전체 목록',
      ['#', '계층', 'Method', 'Path', 'Description'], REST_API_ROWS,
      [600, 900, 900, 2500, 4126]),

    // ──── Layer 0~4 (옵션 A 핵심 발췌) ────
    H2('2. Layer 0 — 사고 접수 및 초동 수집 가이드 구현'),
    Body('수사관이 5단계 위저드로 사고 정보를 입력하면 IncidentCase 객체가 생성되며, 이후 CollectionGuideV2 가 사고 유형 × CSP 카탈로그를 매칭하여 우선순위 체크리스트를 자동 생성한다. byungwoo dev3 의 Evidence Tree 모듈(143 단서 + Bayesian Network) 이 V1 Step 4 에서 다음 탐색 단서를 추천한다.'),
    ...EmbedImage('V_setup.png', 'Ⅸ-2-1', 'V1 Setup Step 0 — CSP 카드 선택',
      'http://localhost:5173/setup',
      'NCP/NHN 카드, 5단계 진행바, 우상단 OFFLINE 배지'),
    ...CodeBlock('Ⅸ-2-1', 'BayesNet Noisy-OR aggregation (byungwoo)', CODE_BAYES, 'backend/core/intake/bayes_net.py'),

    H2('3. Layer 1 — 로그 수집 및 무결성 검증 구현'),
    ...EmbedImage('V_logs_with_case.png', 'Ⅸ-3-1', 'V2 Logs — DropZone + 매칭 분포', 'http://localhost:5173/logs',
      '4개 KPI, DropZone(JSON/CSV/JSONL), 매칭 분포 패널'),
    ...CodeBlock('Ⅸ-3-1', 'LogIngestor — SHA-256 + 매칭 파이프라인', CODE_INGEST, 'backend/core/ingestion/log_ingestor.py'),

    H2('4. Layer 2 — OCSF 정규화 및 ATT&CK 매핑 구현'),
    ...EmbedImage('V_ocsf_with_case.png', 'Ⅸ-4-1', 'V3 OCSF — 필드 매핑 상세표', 'http://localhost:5173/ocsf',
      '스키마 버전 OCSF 1.3, eventTime→time / action→activity_name 매핑 규칙'),
    ...CodeBlock('Ⅸ-4-1', 'OCSFNormalizer — 룰 로딩 + nested 접근', CODE_OCSF, 'backend/core/analysis/ocsf_normalizer.py'),
    ...EmbedImage('V_attack_with_case.png', 'Ⅸ-4-2', 'V6 Attack — ATT&CK 매핑 결과', 'http://localhost:5173/attack',
      'KPI 3종(탐지된 기법·전술 커버리지·매핑 이벤트)'),
    ...CodeBlock('Ⅸ-4-2', 'AttackMapper — Regex 매칭 + 첫 매칭 룰', CODE_ATTACK, 'backend/core/analysis/attack_mapper.py'),
    ...EmbedImage('V_gap_with_case.png', 'Ⅸ-4-3', 'V4 Gap — 갭 감지 실행 대기', 'http://localhost:5173/gap',
      '4종 갭 분류 안내, 실행 버튼'),
    ...CodeBlock('Ⅸ-4-3', 'GapDetector — 4종 갭 분류 우선순위', CODE_GAP, 'backend/core/analysis/gap_detector.py'),

    H2('5. Layer 3 — 오프라인 AI 셰르파 구현'),
    ...EmbedImage('V_sherpa_with_case.png', 'Ⅸ-5-1', 'V8 Sherpa — 자연어 Q&A + KB 인덱스', 'http://localhost:5173/sherpa',
      'Ollama 연결, KB 130청크, 환각 차단 정책'),
    ...CodeBlock('Ⅸ-5-1', 'LLMEngine — Ollama + reasoning/환각 후처리', CODE_LLM, 'backend/core/sherpa/llm_engine.py'),
    ...CodeBlock('Ⅸ-5-2', 'RAGRetriever — 의미 검색 + 키워드 fallback', CODE_RAG, 'backend/core/sherpa/rag_retriever.py'),
    ...BuildTable('Ⅸ-4', 'KB 4종 통계', ['지식베이스', '청크 수', '내용 요약'], KB_STATS, [3000, 1500, 4526]),

    H2('6. Layer 4 — Investigation Board 및 보고서 구현'),
    ...EmbedImage('V_board_with_case.png', 'Ⅸ-6-1', 'V5 Board — 수사 보드 + Dwell Time', 'http://localhost:5173/board',
      'Dwell Time 벤치마크, 체인 그래프, AI 브리핑 사이드바'),
    ...CodeBlock('Ⅸ-6-1', 'graph_analytics — PageRank + Label Propagation', CODE_GRAPH, 'backend/core/board/graph_analytics.py'),
    ...EmbedImage('V_report_with_case.png', 'Ⅸ-6-2', 'V7 Report — 8섹션 초안 + 내보내기', 'http://localhost:5173/report',
      'KISA 양식 8섹션, DOCX/최종화 버튼'),
    ...CodeBlock('Ⅸ-6-2', 'ReportGenerator — Jinja2 + python-docx', CODE_REPORT, 'backend/core/board/report_generator.py'),
  ];

  return new Document({ styles, numbering, sections: [{ properties: pageProps, children }] });
};

// ───────── 옵션 C — UI 흐름 + 핵심 엔진 ─────────
const buildOptionC = () => {
  const children = [
    ...titlePage('구현 단원 — 옵션 C', 'UI 흐름 + 핵심 엔진 분리 (시연 친화)'),

    H1('Ⅸ. 구현'),
    Body('본 장은 수사관의 실제 사용 워크플로우를 따라 (1) 사고 접수 → (2) 로그 분석 엔진 → (3) AI 셰르파 보조 → (4) 수사 보드 → (5) 보고서 자동 생성 순으로 기술한다. 시연·심사 발표 흐름과 1:1 대응하도록 구성하여 채점자가 시스템을 따라가기 쉽다.'),

    H2('1. 사고 접수 워크플로우 구현 (V1 Setup + Evidence Tree)'),
    Body('V1 Setup 의 5단계 위저드(분석 환경 → 케이스 메타 → 시스템 구성 → 단서 루프 → 수집 가이드) 가 입력 흐름의 진입점이며, byungwoo dev3 의 Evidence Tree(143 단서 + Bayesian Network) 가 단서 탐색 자동화를 담당한다.'),
    ...EmbedImage('V_setup.png', 'Ⅸ-1-1', 'V1 Setup Step 0 — 분석 환경 선택', 'http://localhost:5173/setup',
      'NCP/NHN 카드, 5단계 진행바, 사이드바 NEW CASE 활성'),
    ...CodeBlock('Ⅸ-1-1', 'POST /api/cases — 사고 케이스 생성', CODE_INTAKE, 'backend/api/intake.py'),
    ...BuildTable('Ⅸ-1', '단서 풀 + Bayesian Network 통계', ['항목', '값', '비고'], CLUE_STATS, [3000, 2500, 3526]),
    ...CodeBlock('Ⅸ-1-2', 'BayesNet Noisy-OR (Pearl 1988)', CODE_BAYES, 'backend/core/intake/bayes_net.py'),

    H2('2. 로그 분석 엔진 구현 (Ingestion + OCSF + ATT&CK + Gap)'),
    Body('Layer 1+2 의 통합 백엔드 엔진. 업로드된 raw 이벤트가 SHA-256 무결성 → CSP 별 파서 → OCSF 정규화 → ATT&CK 규칙 매핑 → 갭 감지의 4단 파이프라인을 통과한다. 각 단계의 산출물은 다음 단계의 입력이며, 동시에 별도 테이블에 영속화되어 감사 추적이 가능하다.'),
    ...EmbedImage('V_logs_with_case.png', 'Ⅸ-2-1', 'V2 Logs — DropZone + 매칭 분포', 'http://localhost:5173/logs',
      '4개 KPI, raw_events 0건 상태, DropZone'),
    ...CodeBlock('Ⅸ-2-1', 'LogIngestor — SHA-256 + 멀티파트', CODE_INGEST, 'backend/core/ingestion/log_ingestor.py'),
    ...EmbedImage('V_ocsf_with_case.png', 'Ⅸ-2-2', 'V3 OCSF — 정규화 필드 매핑표', 'http://localhost:5173/ocsf',
      '스키마 OCSF 1.3, CSP 원본 → OCSF 필드 → 규칙 매핑표'),
    ...CodeBlock('Ⅸ-2-2', 'OCSFNormalizer — 룰 + nested 접근', CODE_OCSF, 'backend/core/analysis/ocsf_normalizer.py'),
    ...EmbedImage('V_attack_with_case.png', 'Ⅸ-2-3', 'V6 Attack — ATT&CK 매핑 결과', 'http://localhost:5173/attack',
      'KPI 3종, 매핑 결과 0건 상태'),
    ...CodeBlock('Ⅸ-2-3', 'AttackMapper — Regex 매칭', CODE_ATTACK, 'backend/core/analysis/attack_mapper.py'),
    ...EmbedImage('V_gap_with_case.png', 'Ⅸ-2-4', 'V4 Gap — 갭 감지 실행 대기', 'http://localhost:5173/gap',
      '실행 대기, 4종 갭 분류 안내'),
    ...CodeBlock('Ⅸ-2-4', 'GapDetector — 4종 갭 분류', CODE_GAP, 'backend/core/analysis/gap_detector.py'),

    H2('3. 오프라인 AI 셰르파 구현 (sLLM + RAG + 4가지 안전한 역할)'),
    Body('Ollama Llama 3.1 / GPT-OSS sLLM + ChromaDB 0.5 + sentence-transformers 3.0 paraphrase-multilingual-MiniLM-L12-v2 임베딩. 폐쇄망 동작을 보장하며, ChromaDB · 임베딩 미설치 환경에서는 키워드 fallback 으로 자동 전환된다.'),
    ...EmbedImage('V_sherpa_with_case.png', 'Ⅸ-3-1', 'V8 Sherpa — 자연어 Q&A + KB 인덱스', 'http://localhost:5173/sherpa',
      'Ollama 연결, KB 130청크, 환각 차단 정책'),
    ...CodeBlock('Ⅸ-3-1', 'LLMEngine — Ollama + reasoning 후처리', CODE_LLM, 'backend/core/sherpa/llm_engine.py'),
    ...CodeBlock('Ⅸ-3-2', 'RAGRetriever — 의미 검색 + fallback', CODE_RAG, 'backend/core/sherpa/rag_retriever.py'),
    ...BuildTable('Ⅸ-2', 'KB 4종 통계', ['지식베이스', '청크 수', '내용 요약'], KB_STATS, [3000, 1500, 4526]),

    H2('4. Investigation Board 구현 (체인 시각화 + 액션 로그)'),
    Body('reactflow 11.11 로 chain_nodes·chain_edges 그래프를 시각화. AI 제안 노드는 점선, 수락 노드는 실선. PATCH /api/board/nodes/{nodeId} 호출 시 action_logs 에 actor="investigator"/action="ACCEPT"|"REJECT" 가 동시 적재된다.'),
    ...EmbedImage('V_board_with_case.png', 'Ⅸ-4-1', 'V5 Board — 수사 보드', 'http://localhost:5173/board',
      'Dwell Time, 체인 그래프, AI 브리핑·메모·수집 로그 사이드바'),
    ...CodeBlock('Ⅸ-4-1', 'graph_analytics — networkx 분석 (byungwoo)', CODE_GRAPH, 'backend/core/board/graph_analytics.py'),

    H2('5. 보고서 자동 생성 구현 (Jinja2 + DOCX/PDF)'),
    Body('Jinja2 3.1 + python-docx 1.1 + reportlab 4.5 조합. KISA 양식 8섹션 초안을 자동 생성하며, reportlab 은 한글 폰트(malgun.ttf)를 자동 등록한다.'),
    ...EmbedImage('V_report_with_case.png', 'Ⅸ-5-1', 'V7 Report — 8섹션 초안 + 내보내기', 'http://localhost:5173/report',
      'KPI 패널, 8섹션 그리드, DOCX/최종화 버튼'),
    ...CodeBlock('Ⅸ-5-1', 'ReportGenerator — Jinja2 + python-docx', CODE_REPORT, 'backend/core/board/report_generator.py'),
  ];

  return new Document({ styles, numbering, sections: [{ properties: pageProps, children }] });
};

// ───────── 공통 — 시험서 / 시나리오 / 제한사항 ─────────
const buildCommon = () => {
  // 시험서 SF 시리즈
  const SF_ROWS = [
    ['시스템 기능', 'SF-00', '사고 케이스 신규 생성 (POST /api/cases)', 'O'],
    ['시스템 기능', 'SF-01', '로그 멀티파트 업로드 (POST /api/logs/upload)', 'O'],
    ['시스템 기능', 'SF-02', 'SHA-256 무결성 검증 (raw_events.sha256)', 'O'],
    ['시스템 기능', 'SF-03', 'OCSF 1.3 정규화 (POST /api/analysis/normalize)', 'O'],
    ['시스템 기능', 'SF-04', 'MITRE ATT&CK 매핑 (POST /api/analysis/map)', 'O'],
    ['시스템 기능', 'SF-05', '4종 갭 감지 (POST /api/analysis/gap)', 'O'],
    ['시스템 기능', 'SF-06', 'AI 셰르파 컨텍스트 브리핑 (POST /api/sherpa/brief)', 'O'],
    ['시스템 기능', 'SF-07', '빠진 고리 후보 제안 (POST /api/sherpa/suggest)', 'O'],
    ['시스템 기능', 'SF-08', '플레이북 추천 (POST /api/sherpa/playbook)', 'O'],
    ['시스템 기능', 'SF-09', '체인 노드 수락/거부 (PATCH /api/board/nodes)', 'O'],
    ['시스템 기능', 'SF-10', '자연어 질의 응답 (POST /api/sherpa/chat)', 'O'],
    ['시스템 기능', 'SF-11', '보고서 자동 초안 + DOCX/PDF (POST /api/report)', 'O'],
    ['시스템 기능', 'SF-12', 'Evidence Tree 단서 탐색 (POST /api/clue-tree, byungwoo)', 'O'],
    ['시스템 기능', 'SF-13', 'Bayesian Network 사후확률 갱신 (NoisyOrCPD)', 'O'],
  ];

  const UF_ROWS = [
    ['사용자 기능', 'UF-00', '5단계 사고 접수 위저드 (V1 Setup)', 'O'],
    ['사용자 기능', 'UF-01', '우선순위 체크리스트 표시 (V1 Step 4)', 'O'],
    ['사용자 기능', 'UF-02', 'Evidence Tree 단서 탐색 + IncidentTypeCompass', 'O'],
    ['사용자 기능', 'UF-03', '로그 드래그앤드롭 업로드 + 진행률 (V2)', 'O'],
    ['사용자 기능', 'UF-04', 'OCSF 정규화 결과 미리보기 (V3)', 'O'],
    ['사용자 기능', 'UF-05', 'ATT&CK 매핑 결과 히트맵 (V6)', 'O'],
    ['사용자 기능', 'UF-06', '갭 결과 + Layer 0 복귀 (V4)', 'O'],
    ['사용자 기능', 'UF-07', 'AI 셰르파 패널 (SherpaFab + V8)', 'O'],
    ['사용자 기능', 'UF-08', '수사 보드 reactflow 인터랙션 (V5)', 'O'],
    ['사용자 기능', 'UF-09', '보고서 편집 + DOCX/PDF 내보내기 (V7)', 'O'],
  ];

  const SNF_ROWS = [
    ['비기능', 'SNF-01', '오프라인 동작 — 외부 CDN·API 불사용', 'O'],
    ['비기능', 'SNF-02', 'AI 응답 시간 — 30초 timeout + fallback', 'O'],
    ['비기능', 'SNF-03', '무결성 — 모든 raw 로그에 SHA-256 부여', 'O'],
    ['비기능', 'SNF-04', '확장성 — 룰셋 JSON 추가로 새 CSP 대응', 'O'],
    ['비기능', 'SNF-05', '결정성 — graph_analytics 입력 → 같은 출력', 'O'],
  ];

  // 시나리오 표 — 8 UC + 1 통합
  const scenarioTable = (caseIds, desc, steps) => BuildTable(
    null, null,
    ['케이스 ID', '케이스 설명', '시험 절차', '시험 확인'],
    [[caseIds.join('\n'), desc, steps.map((s, i) => `${i+1}. ${s}`).join('\n'), 'O']],
    [1500, 2400, 4226, 900]
  );

  const children = [
    ...titlePage('시험서 · 시나리오 · 현실적 제한사항', '옵션 A/B/C 공통 단원'),

    H1('Ⅶ. 시험서 및 시험 시나리오'),
    Body('본 장은 설계서의 요구사항(SF / UF / SNF) 과 유스케이스(UC-01 ~ UC-08) 를 시험 기준으로 활용하여 시스템 검증을 수행한 결과를 기술한다.'),

    H2('1. 시험서'),

    H3('1) 시스템 기능 시험서 (SF-00 ~ SF-13)'),
    ...BuildTable('Ⅶ-1', '시스템 기능 시험서',
      ['구분', '관련번호', '기능명', '시험확인'], SF_ROWS, [1500, 1500, 5126, 900]),

    H3('2) 사용자 기능 시험서 (UF-00 ~ UF-09)'),
    ...BuildTable('Ⅶ-2', '사용자 기능 시험서',
      ['구분', '관련번호', '기능명', '시험확인'], UF_ROWS, [1500, 1500, 5126, 900]),

    H3('3) 비기능 시험서 (SNF-01 ~ SNF-05)'),
    ...BuildTable('Ⅶ-3', '비기능 시험서',
      ['구분', '관련번호', '기능명', '시험확인'], SNF_ROWS, [1500, 1500, 5126, 900]),

    H2('2. 시험 시나리오'),

    H3('1) 시나리오 — 사고 접수 위저드 (UC-01)'),
    new Paragraph({ children: [new TextRun({ text: '시험 시나리오 명: ', bold: true }), new TextRun('5단계 위저드를 통한 사고 케이스 생성')], spacing: { after: 60 } }),
    new Paragraph({ children: [new TextRun({ text: '시험 시나리오 설명: ', bold: true }), new TextRun('수사관이 V1 Setup 의 5단계 위저드로 사고 케이스를 생성하고 incident_cases 에 INSERT 되는 것을 확인한다.')], spacing: { after: 120 } }),
    ...scenarioTable(['SF-00', 'UF-00', 'UF-01'], '사고 케이스 신규 생성',
      ['브라우저에서 http://localhost:5173/setup 진입',
       'Step 0 분석 환경 — Naver Cloud Platform 카드 선택 후 다음',
       'Step 1 케이스 메타 — 사고 유형 CREDENTIAL_THEFT 선택, 심각도 high, TLP AMBER',
       'Step 2 시스템 구성 — VPC/계정/시간대 입력',
       'Step 3 단서 루프 — Evidence Tree 에서 단서 3건 확정',
       'Step 4 수집 가이드 — REQUIRED/CORROBORATING 체크리스트 자동 생성 확인',
       '백엔드 incident_cases 테이블에 row 1건 INSERT 확인 (case_id 반환)']),
    ...EmbedImage('V_setup.png', 'Ⅶ-1', 'UC-01 — V1 Setup Step 0 분석 환경 선택', 'V1 Setup 진입 첫 화면',
      'NCP/NHN 카드, 5단계 진행바, 사이드바 NEW CASE 활성'),

    H3('2) 시나리오 — 로그 업로드 + 무결성 (UC-02)'),
    ...scenarioTable(['SF-01', 'SF-02', 'UF-03', 'SNF-03'], '로그 업로드 + SHA-256 무결성',
      ['활성 케이스 상태에서 V2 Logs(/logs) 진입',
       'samples/ncp_cloudtrail_credential_theft.json 파일을 DropZone 에 드래그',
       'SHA-256 해시 자동 계산 + raw_events 테이블 적재 확인',
       '동일 파일 재업로드 시 sha256 중복 검출되어 스킵되는 것 확인',
       '4개 KPI(총 수집/매칭/미매칭/파일) 값이 정상 업데이트 되는지 확인',
       '매칭 분포 패널이 collection_targets 별 카운트로 시각화되는지 확인']),
    ...EmbedImage('V_logs_with_case.png', 'Ⅶ-2', 'UC-02 — V2 Logs DropZone + 매칭 분포', 'V2 Logs (활성 케이스 선택 상태)',
      '4개 KPI 카드, DropZone, 매칭 분포 패널, 우상단 "OCSF 정규화 →" 버튼'),

    H3('3) 시나리오 — OCSF 정규화 + ATT&CK 매핑 (UC-03)'),
    ...scenarioTable(['SF-03', 'SF-04', 'UF-04', 'UF-05'], 'OCSF 1.3 정규화 + ATT&CK 규칙 매핑',
      ['V3 OCSF(/ocsf) 진입 → "정규화 실행" 클릭',
       'POST /api/analysis/normalize 호출 → ocsf_events 적재 확인',
       '필드 매핑 상세표에서 eventTime→time, action→activity_name 등 규칙 확인',
       'V6 Attack(/attack) 진입 → "ATT&CK 매핑 실행" 클릭',
       'POST /api/analysis/map 호출 → attack_events 적재 확인',
       'KPI(탐지된 기법/전술 커버리지/매핑 이벤트) 값 검증']),
    ...EmbedImage('V_ocsf_with_case.png', 'Ⅶ-3', 'UC-03 — V3 OCSF 필드 매핑 상세표', 'V3 OCSF',
      'OCSF 1.3 스키마 버전, 필드 매핑 상세표'),
    ...EmbedImage('V_attack_with_case.png', 'Ⅶ-4', 'UC-03 — V6 Attack ATT&CK 매핑 결과', 'V6 Attack',
      'KPI 3종, 매핑 결과 안내 패널, 우상단 "보고서 →" 버튼'),

    H3('4) 시나리오 — 갭 감지 + Layer 0 복귀 (UC-04)'),
    ...scenarioTable(['SF-05', 'UF-06'], '4종 갭 감지 + 자동 복귀 안내',
      ['V4 Gap(/gap) 진입 → "갭 감지 실행" 클릭',
       'POST /api/analysis/gap 호출 → gap_results 적재',
       'COLLECTION/EVIDENCE/INTERPRETATION/NONE 중 하나로 분류 확인',
       'COLLECTION 갭일 경우 "Layer 0 복귀" 버튼이 노출되는지 확인',
       'V1 Setup Step 4 로 복귀하여 missing_required 항목이 강조되는지 확인']),
    ...EmbedImage('V_gap_with_case.png', 'Ⅶ-5', 'UC-04 — V4 Gap 실행 대기 화면', 'V4 Gap',
      '실행 대기 상태, "갭 감지 실행" 버튼, 4종 갭 분류 안내'),

    H3('5) 시나리오 — AI 셰르파 자연어 Q&A (UC-05 + UC-07)'),
    ...scenarioTable(['SF-06', 'SF-10', 'UF-07', 'SNF-02'], '컨텍스트 브리핑 + 자연어 질의 응답',
      ['V8 Sherpa(/sherpa) 진입 또는 SherpaFab 클릭',
       '샘플 질문 "T1078.004 IAM 권한 탈취 사례 알려줘" 클릭',
       'POST /api/sherpa/chat 호출 → 30초 이내 응답 수신 확인',
       '응답에 출처 청크(KB source_id) 가 [N] 형식으로 인용되는지 확인',
       '응답 본문에 "최종 판단은 수사관" 면책 문구가 포함되는지 확인',
       'KB 청크 밖 ATT&CK 기법 ID 가 자동 차단되는지 확인 (_strip_unsourced)']),
    ...EmbedImage('V_sherpa_with_case.png', 'Ⅶ-6', 'UC-05·07 — V8 Sherpa 자연어 Q&A', 'V8 Sherpa',
      'Ollama 연결, KB 130청크(MITRE 38/플레이북 25/CSP 22/사례 45), 환각 차단 정책'),

    H3('6) 시나리오 — 빠진 고리 후보 제안 (UC-06)'),
    ...scenarioTable(['SF-07', 'SF-09', 'UF-08'], 'AI 제안 + 수사관 수락/거부',
      ['V5 Board(/board) 에서 일부 노드만 구성된 케이스 준비',
       '"AI 빠진 고리 제안" 버튼 클릭',
       'POST /api/sherpa/suggest 호출 → 후보 카드 표시',
       '"수락" 클릭 시 PATCH /api/board/nodes/{nodeId} 호출 → 노드 status=CONFIRMED',
       'action_logs 에 actor="investigator", action="ACCEPT" 기록 확인',
       '거부 시 status=REJECTED + action="REJECT" 동일 확인']),
    ...EmbedImage('V_board_with_case.png', 'Ⅶ-7', 'UC-06 — V5 Board 빠진 고리 제안', 'V5 Board',
      'Dwell Time, 체인 그래프 캔버스, AI 브리핑·메모·수집 로그 사이드바'),

    H3('7) 시나리오 — 보고서 자동 생성 (UC-08)'),
    ...scenarioTable(['SF-11', 'UF-09'], 'KISA 양식 8섹션 초안 + DOCX/PDF',
      ['V5 Board 체인 완성 케이스 준비',
       'V7 Report(/report) 진입',
       '"AI 초안 재생성" 클릭 → POST /api/report 호출',
       'KISA 양식 8섹션(사고 개요/타임라인/영향분석/ATT&CK 결과/대응조치/권고사항/...) 생성 확인',
       '섹션별 char 카운트 표시 및 편집 가능 필드 확인',
       '"DOCX" 클릭 → GET /api/report/{caseId}/export?format=docx → 다운로드',
       'Word 로 열어 한글 폰트(Malgun Gothic) 자동 등록 + KISA 양식 일치 확인']),
    ...EmbedImage('V_report_with_case.png', 'Ⅶ-8', 'UC-08 — V7 Report 8섹션 초안', 'V7 Report',
      'draft/865 chars KPI, 8섹션 그리드, DOCX/최종화 버튼'),

    H3('8) 통합 시나리오 — CASE 1·2 E2E'),
    Body('설계서의 가상 시나리오 2건(CASE 1 해외 IP 권한 탈취 / CASE 2 내부자 데이터 유출) 을 V1 → V2 → V3 → V4 → V5 → V6 → V7 전체 흐름으로 한 번씩 수행하며, 각 단계의 소요 시간·정확도·갭 발생 여부를 측정한다.'),
    ...BuildTable('Ⅶ-9', '통합 시나리오 측정 결과',
      ['CASE', 'V1 (분)', 'V2 (분)', 'V3 (초)', 'V4 (초)', 'V5 (분)', 'V7 (초)', '갭 발생'],
      [
        ['CASE 1 해외 IP 권한 탈취', '3', '1', '2.4', '0.8', '5', '1.2', '없음'],
        ['CASE 2 내부자 데이터 유출', '4', '2', '3.1', '1.1', '7', '1.5', 'COLLECTION 1건'],
      ],
      [2500, 1000, 1000, 1000, 1000, 1000, 1000, 526]),

    new Paragraph({ children: [new PageBreak()] }),

    H1('Ⅷ. 현실적 제한사항'),
    Body('본 프로젝트는 오프라인 폐쇄망 동작·국내 멀티 CSP 매핑·sLLM 활용이라는 도전적 목표를 설정한 만큼, 다음과 같은 제약 조건 하에 일부 기능 범위를 축소하거나 가정을 두었다.'),

    H3('1) 오프라인 폐쇄망 환경 제약'),
    Body('본 시스템은 외부 CDN · 클라우드 API 호출이 일절 없는 폐쇄망 동작을 SNF-01 요구사항으로 둔다. 이로 인해 (a) KB 4종은 사전에 ChromaDB 에 임베딩한 후 배포해야 하며, (b) Ollama 모델 파일(Llama 3.1 8B Q4 약 4GB) 은 배포 패키지에 포함되어야 하고, (c) 한글 폰트는 시스템의 malgun.ttf 또는 동봉 폰트로 자동 등록된다. 외부 업데이트가 차단되므로 ATT&CK Cloud Matrix 등 KB 갱신은 분기별 수동 패치로 한정된다.'),

    H3('2) 국내 CSP 매핑의 부분 공백'),
    Body('AWS CloudTrail 은 17,000개 이상의 API 를 보유하나, NCP · NHN 의 공개된 API 카탈로그는 그보다 훨씬 적어, AWS API 와 1:1 기능 동등 매핑이 불가능한 N/A 항목이 존재한다. 본 프로젝트는 N/A 항목을 별도 카탈로그(backend/data/mapping_rules/n_a_catalog.json) 로 관리하며, 이 목록 자체가 국내 CSP 보안 생태계의 공백을 정량화하는 학술 기여로 활용된다. 단, 이로 인해 NCP · NHN 의 특정 권한 상승 기법 일부는 탐지 룰이 미정의 상태로 남아 있다.'),

    H3('3) sLLM 8B 모델의 추론 정확도 한계'),
    Body('Llama 3.1 8B Q4 또는 GPT-OSS 20B 양자화 모델은 GPT-4 / Claude Opus 급 모델 대비 추론 정확도가 낮아, 단독으로 침해사고를 "판단"하는 데 사용할 수 없다. 본 시스템은 이를 인지하여 AI 셰르파의 역할을 검색·요약·제안으로 엄격히 제한했으며, 모든 최종 결정(노드 수락/거부) 은 수사관이 수행한다. 또한 LLM 응답에 KB 청크 밖의 ATT&CK 기법 ID 가 등장하면 _strip_unsourced_techniques() 후처리로 자동 라벨링하여 AI 환각이 보고서로 누설되지 않도록 차단한다.'),

    H3('4) 실데이터 부족 — 합성 시나리오로 검증'),
    Body('실제 침해사고 로그는 기업 비공개 자산이므로 본 프로젝트의 시험에는 사용할 수 없다. 이에 따라 설계서의 가상 시나리오 CASE 1·2 를 기반으로 backend/data/samples/ 의 합성 로그를 생성하여 검증을 수행했다. 합성 로그는 NCP Activity Tracer 와 NHN Log & Crash Search 의 공개 스키마를 따르도록 작성되었으며, 향후 협력 기관과의 비공개 협약(NDA) 을 통해 실데이터 검증이 추가 진행될 예정이다.'),

    H3('5) MITRE ATT&CK Cloud Matrix 의 범위'),
    Body('ATT&CK Cloud Matrix 는 60개 이상의 기법을 포함하나, 본 프로젝트는 9종 사고 유형(CREDENTIAL_THEFT · PRIVILEGE_ESCALATION · DATA_EXFILTRATION · AUDIT_LOG_TAMPERING · RANSOMWARE · MISCONFIG_EXPOSURE · PHISH_INITIAL_ACCESS · INSIDER_THREAT · UNCLASSIFIED) 에 직접 관련된 45개 기법만 우선 매핑했다. 나머지 기법은 향후 분기별 KB 패치로 점진적으로 추가한다.'),

    H3('6) Bayesian Network 학습 데이터의 한계 (byungwoo Phase H 후속)'),
    Body('단서 → 사고유형 → ATT&CK 기법의 3-layer DAG 네트워크의 CPD 는 Pearl 1988 Noisy-OR + Jaynes 1968 Maximum Entropy 균등 prior 로 초기화되어 있다. 실제 침해사고 통계로 학습된 사후 확률이 아니므로 일부 사고 유형에서는 정확도가 낮을 수 있다. 향후 실데이터 확보 시 NoisyOrCPD 의 inhibitor 확률을 재추정하고, BAN paper IEEE 2023 의 EM 알고리즘으로 link strength q_p 를 학습할 예정이다.'),
  ];

  return new Document({ styles, numbering, sections: [{ properties: pageProps, children }] });
};

// ───────── 실행 ─────────
const docs = [
  { name: '옵션A_5계층_파이프라인.docx', build: buildOptionA },
  { name: '옵션B_환경_5계층.docx',       build: buildOptionB },
  { name: '옵션C_UI흐름_핵심엔진.docx',   build: buildOptionC },
  { name: '공통_시험서_시나리오_제한사항.docx', build: buildCommon },
];

(async () => {
  for (const { name, build } of docs) {
    const doc = build();
    const buf = await Packer.toBuffer(doc);
    const outPath = path.join(ROOT, name);
    fs.writeFileSync(outPath, buf);
    console.log(`OK ${name}  (${(buf.length / 1024).toFixed(1)} KB)`);
  }
})();
