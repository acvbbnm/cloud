//  공통 Enum 타입 (백엔드 DB enum과 정확히 일치) 

// 백엔드 Pydantic Literal + types/index.ts 정책과 일치
// dev3 (2026-05-18): UNCLASSIFIED 추가 — 빈 케이스 시작 패턴 (TheHive·IRIS·NIST 800-61r2)
// dev3 C-1 (2026-05-19): 신규 4종 추가 — RANSOMWARE·MISCONFIG_EXPOSURE·PHISH_INITIAL_ACCESS·INSIDER_THREAT
// 2026-05-19 (재결정): MULTI_CSP_LATERAL 제거 — 사용자 명시. 환경 변수 multi_cloud 만 보존.
// 최종 8종 + UNCLASSIFIED (CSA Pandemic Eleven #1~7 + KISA §3.3 분류표 정합)
export type IncidentType =
  //  4종 기존 
  | 'CREDENTIAL_THEFT'
  | 'PRIVILEGE_ESCALATION'
  | 'DATA_EXFILTRATION'
  | 'AUDIT_LOG_TAMPERING'
  //  dev3 C-1 신규 4종 
  | 'RANSOMWARE'
  | 'MISCONFIG_EXPOSURE'
  | 'PHISH_INITIAL_ACCESS'
  | 'INSIDER_THREAT'
  //  미분류
  | 'UNCLASSIFIED';

/**
 * R.2 (hard, 2026-05-28) — 사고유형 Kill Chain 시계방향 배치 단일 소스.
 *
 * 하드코딩 감사 #5 해결: IncidentTypeCompass.tsx 가 같은 배열을 자체 정의해서
 * 사고유형 추가/순서 변경 시 두 파일 동기화 부담이 있었음. types/index.ts 단일
 * 소스로 통일.
 *
 * 12시부터 시계방향으로 MITRE Cloud Kill Chain 시간순 (Initial Access → Impact).
 * UNCLASSIFIED 는 Kill Chain 매핑 없으므로 제외 (Exclude<...> 로 타입 narrowing).
 *
 *     12  PHISH_INITIAL_ACCESS    (Phase 1, Initial Access)
 *   1:30  CREDENTIAL_THEFT        (Phase 2, Credential Access)
 *      3  PRIVILEGE_ESCALATION    (Phase 3, Privilege Esc.)
 *   4:30  INSIDER_THREAT          (Phase 4, Discovery/Lateral)
 *      6  MISCONFIG_EXPOSURE      (Phase 4, Discovery/Lateral)
 *   7:30  AUDIT_LOG_TAMPERING     (Phase 5, Defense Evasion)
 *      9  DATA_EXFILTRATION       (Phase 6, Exfiltration)
 *  10:30  RANSOMWARE              (Phase 7, Impact)
 */
export const INCIDENT_TYPES_KILL_CHAIN_ORDER: ReadonlyArray<
  Exclude<IncidentType, 'UNCLASSIFIED'>
> = [
  'PHISH_INITIAL_ACCESS',
  'CREDENTIAL_THEFT',
  'PRIVILEGE_ESCALATION',
  'INSIDER_THREAT',
  'MISCONFIG_EXPOSURE',
  'AUDIT_LOG_TAMPERING',
  'DATA_EXFILTRATION',
  'RANSOMWARE',
] as const;

// dev3 신규 — TheHive 5 차용 (정보 공유 등급)
export type TLP = 'RED' | 'AMBER' | 'GREEN' | 'WHITE';

// dev3 신규 — Discovery Loop 단서 6종 (DFIR-IRIS IOC + NIST 800-61r2 표 3-2)
export type ClueType =
  | 'IP_ADDRESS'
  | 'ACCOUNT'
  | 'HASH'
  | 'DOMAIN'
  | 'TIME_WINDOW'
  | 'SERVICE';
// dev3 (2026-05-19): 'all' 제거 — MULTI_CSP_LATERAL 삭제와 함께. naver/nhn 만.
export type CSP = 'naver' | 'nhn';
export type Severity = 'critical' | 'high' | 'medium' | 'low';
export type EvidenceRole = 'REQUIRED' | 'CORROBORATING';
export type GapType = 'NONE' | 'COLLECTION' | 'EVIDENCE' | 'INTERPRETATION';
export type NodeStatus = 'CONFIRMED' | 'REJECTED';
export type ActionType = 'ACCEPT' | 'REJECT' | 'EDIT_REPORT' | 'FINALIZE_REPORT' | 'EXPORT_REPORT';

//  API 요청 

export interface CreateCaseReq {
  incident_type: IncidentType;
  csp: CSP;
  severity: Severity;
  occurred_at: string;
  system_config?: Record<string, unknown>;
  //  dev3 신규 (Step 1 케이스 메타) 
  title?: string;
  tlp?: TLP;
  observables?: Observable[];
}

//  API 응답 

export interface CaseResponse {
  caseId: string;
  incident_type: IncidentType;
  csp: CSP;
  severity: Severity;
  occurred_at: string;
  system_config: Record<string, unknown> | null;
  created_at: string;
  closed_at: string | null;
  //  dev3 신규 
  title?: string;
  tlp?: TLP;
  observables?: Observable[];
  secondary_incident_types?: IncidentType[]; // V-8 사후 검증으로 추가된 부 사고유형
  triage_state?: TriageState | null;          // 결정 트리 진행 상태 영속화
}

// v1 CollectionTargetItem · GuideResponse 는 2026-05-18 회의 결정으로 제거.
// V2 가이드(GuideV2Target / GuideV2Response) 가 유일한 가이드 타입.

// Layer 1 — 백엔드 응답 형식과 일치 (camelCase, 2026-05-14 이근형 작업 기준)
export interface RawEventItem {
  eventId: string;
  caseId: string;
  csp: CSP;
  sha256: string;
  matchedTargetId: string | null;
  ingestedAt: string;
  sourceFile: string;
  raw?: Record<string, unknown>; // 단건 조회 시만 포함
}

// POST /api/logs/upload 응답 data
export interface IngestionStats {
  totalEvents: number;
  matched: number;
  unmatched: number;
  byTarget: Record<string, number>;
  sha256: string;
  sourceFile: string;
}

// GET /api/logs 응답 data (envelope 안의 페이지네이션)
export interface LogsListData {
  items: RawEventItem[];
  total: number;
  page: number;
  pageSize: number;
}

// Layer 2 — 백엔드 응답 형식과 일치 (평탄화 OCSF + Attack join 결과)
export interface OCSFEventItem {
  ocsf_id: string;
  event_id: string;
  time: string; // ISO datetime
  actor_user_name: string | null;
  src_endpoint_ip: string | null;
  activity_name: string;
  status_code: number | null;
  unmapped_raw: Record<string, unknown> | null;
}

export interface AttackEventItem {
  attack_id: string;
  ocsf_id: string;
  technique_id: string;
  technique_name: string | null;
  tactic: string;
  rule_id: string;
  // risk_score 제거 (산출 근거 부재). 정렬·시각화는 mapped_at·count 기반.
  mapped_at: string;
  event_time: string | null;
  activity_name: string | null;
}

export interface NormalizeStats {
  total: number;
  normalized: number;
  failed: number;
  normalizationRate: number;
  failedEvents: { event_id: string; reason: string }[];
}

export interface MapStats {
  total_ocsf: number;
  mapped: number;
  unmapped: number;
  mappingRate: number;
  events: AttackEventItem[];
}

export interface GapMissingTarget {
  target_id: string;
  log_type: string;
  evidence_role: EvidenceRole;
  priority: number;
}

// multi-type (2026-05-31): 단서 루프에서 2개 이상 확정된 사고유형별 독립 갭.
export interface GapPerType {
  incident_type: IncidentType;
  gap_type: GapType;
  missing: GapMissingTarget[];
  summary: string;
  recommendation: string;
  completionRate: number | null;
}

export interface GapResultResponse {
  gap_id: string;
  case_id: string;
  gap_type: GapType;
  missing: GapMissingTarget[];
  summary: string;
  recommendation: string;
  completionRate: number | null;
  created_at: string;
  // v2 (2026-05-15) — 4개 참고자료 반영 부가 진단. backend 가 항상 포함하므로 optional 처리.
  /** [R4 Naver Cloud 실무] priority 가중 수집 점수 (P1=10, P2=7, P3=3, P4=1) */
  priorityScore?: {
    collected: number;
    missing: number;
    total: number;
    /** 0~100 */
    percent: number;
  };
  /** [R1 ATT&CK 매트릭스 논문] kill-chain 단계 커버리지 */
  tacticCoverage?: {
    covered: number;
    total: number;
    byTactic: Record<string, number>;
    missingTactics: string[];
  };
  /** [R3 SentinelOne anti-forensics] 시간 축 비정상 공백 — 로그 삭제 후보 */
  timeGaps?: {
    from: string;
    to: string;
    durationMinutes: number;
    suspicion: 'anti_forensic_candidate' | string;
  }[];
  /** [R2 Google Cloud bad log config] REQUIRED vs CORROBORATING 비대칭 등 수집 구성 경고 */
  badConfigSignals?: string[];
  // multi-type — 확정 사고유형 목록 + 유형별 갭 판정 (단일 유형이면 1개 항목)
  // P.24 (2026-05-31 jingyu d39b1e0 흡수) — confirmed_hypotheses 다중 시 활용.
  incidentTypes?: IncidentType[];
  perType?: GapPerType[];
}

export interface PaginatedData<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

/** Phase O — 단서 노드 meta (chain_nodes.meta JSON). */
export interface ClueNodeMeta {
  type: 'clue';
  clue_key: string;
  stage: number;
  source: string; // 'manual_drag' | 'manual_bulk' | 'auto_seed' | 'user_added' | ...
  hypothesis?: string | null;
  tree_node_id?: string;
  tree_depth?: number;
  tree_source?: string;
  [key: string]: unknown;
}

/** Phase O — ATT&CK 노드 meta (옵션, 보드 보강용). */
export interface AttackNodeMeta {
  type: 'attack';
  [key: string]: unknown;
}

export type BoardNodeMeta = ClueNodeMeta | AttackNodeMeta | null;

export interface BoardNode {
  node_id: string;
  attack_id: string | null;
  label: string;
  status: NodeStatus;
  is_ai_suggested: boolean;
  pos_x: number;
  pos_y: number;
  /** Phase O — 노드 종류 ('attack' | 'clue'). 백엔드가 meta.type 또는 기본 'attack' 추론. */
  type?: 'attack' | 'clue';
  /** Phase O — 단서 노드 부가 정보 (type='clue' 시 ClueNodeMeta). */
  meta?: BoardNodeMeta;
}

export interface BoardEdge {
  edge_id: string;
  from_node_id: string;
  to_node_id: string;
  label: string;
}

/**
 * Phase 2.5 (P6, 2026-05-25) — Dwell Time KPI.
 * PDF 결론 (Mandiant M-Trends 2024 median dwell 7d) 벤치마크 비교용.
 * 백엔드 InvestigationBoard.compute_kpi 와 동기.
 */
export interface BoardKpi {
  earliestEventTime: string | null;
  rawEarliestEventTime?: string | null;
  latestEventTime?: string | null;
  rawLatestEventTime?: string | null;
  detectedAt?: string | null;
  caseCreatedAt: string | null;
  caseClosedAt: string | null;
  dwellTimeSeconds: number | null;
  /** OCSF 이벤트 spread (latest - earliest). 합성 로그 보정 시 dwellTimeSeconds 와 같음. */
  signalSpreadSeconds?: number | null;
  containmentSeconds: number | null;
  totalSeconds: number | null;
  benchmarkSeconds: number;
  benchmarkSource: string;
  dwellSource?: string;
  /** 합성 로그 자동 감지 → dwellTime 을 spread 로 보정함. */
  syntheticAdjusted?: boolean;
}

export interface BoardResponse {
  caseId: string;
  nodes: BoardNode[];
  edges: BoardEdge[];
  kpi?: BoardKpi;
}

export interface ReportSections {
  overview: string;
  timeline: string;
  impact: string;
  attack_analysis: string;
  response: string;
  recommendation: string;
  evidence: string;
  comments: string;
}

export interface ReportResponse {
  caseId: string;
  sections: ReportSections;
  status: string;
  created_at: string;
}

export interface BriefingResponse {
  technique_id: string;
  technique_name: string;
  tactic: string;
  briefing: string;
  sources: { source_id: string; type: string; title: string }[];
  relatedTechniques: string[];
  confidence: string;
}

export interface SherpaSource {
  source_id: string;
  type: string; // ATTACK / PLAYBOOK / CSP_DOC / CASE_DB
  title: string;
  url?: string | null;
}

export interface ChatHistoryItem {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  caseId?: string | null;
  sessionId?: string | null;
  query: string;
  history?: ChatHistoryItem[];
}

export interface ChatResponse {
  sessionId: string;
  response: string;
  sources: SherpaSource[];
}

export interface SuggestRequest {
  caseId: string;
  nodeA: string;
  nodeB: string;
}

export interface SuggestionItem {
  technique_id: string;
  technique_name: string;
  tactic: string;
  reason: string;
  candidateEvents: string[];
  confidence: string;
  sources: SherpaSource[];
}

export interface SuggestResponse {
  suggestions: SuggestionItem[];
}

export interface PlaybookRequest {
  caseId?: string | null;
  chain: string[];
}

export interface PlaybookItem {
  playbook_id: string;
  title: string;
  steps: string[];
  tactics_addressed: string[];
  sources: SherpaSource[];
}

export interface PlaybookResponse {
  playbooks: PlaybookItem[];
}

export interface KbEngineHealth {
  engine: string; // 'stub' | 'ollama' 등
  model: string;
  note: string;
  base_url?: string;
}

export interface RagBackendInfo {
  backend: 'chromadb' | 'keyword';
  model?: string;
  collection_size?: number;
  reason?: string;
}

export interface KbStatsResponse {
  total: number;
  byKb: Record<string, number>;
  engine: KbEngineHealth;
  rag?: RagBackendInfo;
}

// 
// /api/guide/v2 응답 (dev2 청사진  5 정합)
// 

export interface GuideV2SourceRef {
  std: string | null;
  ref: string | null;
  title: string | null;
  url: string | null;
}

export interface GuideV2CollectionMethod {
  log_source: string;
  patterns: string[];
  pattern_kind: 'action' | 'eventId' | '';
  collection_steps: string[];
  cli_hint: string;
  field_locations: Record<string, string>;
  example_raw: Record<string, unknown>;
  note: string;
}

export interface GuideV2Target {
  category_id: string;
  category_name: string;
  evidence_role: 'REQUIRED' | 'CORROBORATING' | string;
  priority: number;
  priority_basis: string;
  rationale: string;
  use_cases: string[];
  csp_specific: Record<string, string>;
  collection_methods: Record<string, GuideV2CollectionMethod>;
  sources: GuideV2SourceRef[];
  collected: boolean;
  // Phase L (2026-05-31) — 단서 루프 신호(전술)와 연관되어 부스트된 단계인지
  clue_relevant?: boolean;
}

export interface GuideV2PhaseGroup {
  phase_id: string | null;
  phase_name: string | null; // 한국어 (예: "초기 침투")
  phase_description: string;
  mitre_url: string;
  kisa_reference: string;
  targets: GuideV2Target[];
}

export interface GuideV2EnvWarning {
  category_id: string;
  category_name: string;
  evidence_role: string;
  priority: number;
  rationale: string;
  from_modifier: string | null;
}

export interface GuideV2AppliedModifier {
  id: string;
  field?: string;
  matched_value?: unknown;
  effect: string;
  category_id?: string | null;
  kill_chain_phase?: string | null;
  boost?: number | null;
  secondary?: Array<{
    effect: string;
    category_id?: string | null;
    kill_chain_phase?: string | null;
    boost?: number | null;
  }>;
  reason: string;
  source: string;
}

// Phase L (2026-05-31) — 단서 루프 신호 요약 (UI 강조·배지·근거 표시용)
export interface GuideV2ObservableSummary {
  type: string;
  count: number;
}

export interface GuideV2ClueObservable {
  type: string;
  value: string;
  confidence?: string | null;
  source?: string | null;
}

export interface GuideV2ClueSignals {
  has_signal: boolean;
  clue_techniques: string[]; // 채택 단서 유래 ATT&CK 기법 ID
  evidenced_techniques: string[]; // 업로드 로그(attack_events) 유래 기법 ID
  signal_techniques: string[]; // 위 둘의 합집합
  signal_tactics: string[]; // 기법 → 전술 환산 (부스트 기준)
  boosted_category_ids: string[]; // 단서 연관으로 우선순위 부스트된 카테고리
  observables: GuideV2ClueObservable[];
  observable_summary: GuideV2ObservableSummary[];
}

export interface GuideV2Response {
  caseId: string;
  incidentType: string;
  csp: string;
  completionRate: number;
  phases: Record<string, GuideV2PhaseGroup>;
  environment_warnings: GuideV2EnvWarning[];
  applied_modifiers: GuideV2AppliedModifier[];
  source_standards: string[];
  version: 'v2';
  // 2026-05-23 사이클 6 — V-1 Step 4 시드 풍부 메타
  seed_targets?: Array<Record<string, unknown>>;
  // Phase L (2026-05-31) — 단서 루프 신호 요약
  clue_signals?: GuideV2ClueSignals;
  // Phase K (2026-05-26 byungwoo) — preview 응답 식별 마커
  preview?: boolean;
}

// 
// dev3 — Triage / Discovery Loop 타입
// 청사진: docs/dev3/V1_재설계_청사진.md
// 가중치: backend/data/triage/weights.json
// 

// 단서 (Observable) — Step 2 단서 입력
export interface Observable {
  type: ClueType;
  value: string;
  added_at?: string;
  note?: string;
  // 가중치 키 (예: "IP_ADDRESS:non_korean") — 백엔드에서 매핑
  weight_key?: string | null;
}

// 사고유형별 가설 점수
export type HypothesisScores = Record<IncidentType, number>;

// 결정 트리 노드 (decision_tree.json 의 단일 노드)
export interface TriageTreeOption {
  id: string;
  label: string;
  weight_key: string | null;
  next?: string | null;
}

export interface TriageTreeNode {
  id: string;
  type: 'question' | 'terminal';
  question?: string;
  options?: TriageTreeOption[];
  multi_select?: boolean;
  action?: string;
  message?: string;
  fallback_incident_type?: IncidentType;
  kisa_field?: string;
  dynamic_next?: Record<string, string>;
}

// 결정 트리 경로 엔트리 (E4 2026-05-21: TriageStepper 등 다수 컴포넌트 공유)
export interface TriagePathEntry {
  node_id: string;
  selected_option_ids: string[];
}

// 결정 트리 진행 상태 (DB triage_state JSON 칼럼)
export interface TriageState {
  current_node_id: string;
  completed_path: TriagePathEntry[];
  hypothesis_scores: HypothesisScores;
  is_terminal: boolean;
  recommendation?: TriageRecommendation | null;
}

// 종합 판정 결과
export interface TriageRecommendation {
  outcome: 'auto_confirm' | 'propose_single' | 'propose_composite' | 'continue_or_skip';
  primary?: { incident_type: IncidentType; score: number };
  secondary?: { incident_type: IncidentType; score: number };
  rationale: string[]; // "단서 비국내 IP → +25 CRED" 등 트레이스
  message: string;
}

// 다음 단서 제안 (next_clue_graph.json)
export interface NextClueSuggestion {
  priority: number;
  question: string;
  action: string;
  hint_clue_type?: ClueType | null;
  hint_value?: string | null;
  hypothesis_boost: Partial<Record<IncidentType, number>>;
  source: string;
}

// AI 보조 패널 KB 검색 결과
export interface TriageKbResult {
  case_db: SherpaSource[];
  attack: SherpaSource[];
  playbook: SherpaSource[];
  csp_doc: SherpaSource[];
}

//  API 요청 / 응답 

// POST /api/triage/analyze — 단서 + 부분 로그 → 가설 갱신
// dev3 (2026-05-19): stateless 정책 (청사진 §3) — 클라이언트가 hypothesis_scores 매 요청 전달
export interface TriageAnalyzeRequest {
  caseId: string;
  hypothesis_scores: HypothesisScores; // 백엔드 필수
  clue?: Observable;
  technique_ids?: string[]; // 백엔드 partial_analysis_techniques 가중치 키
  partial_log_filename?: string;
}

export interface TriageAnalyzeResponse {
  caseId: string;
  hypothesis_scores: HypothesisScores;
  mapped_techniques: string[]; // 부분 분석 결과 ATT&CK 기법 ID
  next_clues: NextClueSuggestion[];
  kb_results: TriageKbResult;
}

// POST /api/triage/next — 결정 트리 다음 질문
// dev3 (2026-05-19): 백엔드 stateless 정책 — hypothesis_scores·tree_path 필수.
// nextTriage 함수가 호출 시점에 별도 인자(currentScores, currentPath)로 받아
// 페이로드에 합쳐 전송하므로, 본 인터페이스에서는 옵셔널 (?: ) 로 둠.
export interface TriageNextRequest {
  caseId: string;
  current_node_id: string;
  answer_ids: string[]; // multi_select 지원
  hypothesis_scores?: HypothesisScores;
  tree_path?: Array<{ node_id: string; selected_option_ids: string[] }>;
}

export interface TriageNextResponse {
  next_node: TriageTreeNode | null;
  hypothesis_scores: HypothesisScores;
  tree_path: Array<{ node_id: string; selected_option_ids: string[] }>;
  is_terminal: boolean;
  recommendation?: TriageRecommendation | null;
}

// POST /api/triage/confirm — 사고유형 확정
// dev3 (2026-05-19): 백엔드 stateless 정책 — hypothesis_scores 필수 (청사진 §3)
// 현재 시연 흐름은 V1Setup index.tsx 의 updateCase (PATCH /api/cases) 로 우회.
// 본 타입은 향후 직접 호출 함수 도입 시 정합 보호.
export interface TriageConfirmRequest {
  caseId: string;
  incident_type: IncidentType;
  hypothesis_scores: HypothesisScores; // 백엔드 필수
  secondary_incident_types?: IncidentType[];
  triage_state?: TriageState | null;
  observables?: Observable[];
}

// GET /api/triage/tree?caseId= — 시각화용 트리 전체 + 진행 상태
export interface TriageTreeResponse {
  caseId: string;
  nodes: TriageTreeNode[];
  current_node_id: string;
  completed_path: Array<{ node_id: string; selected_option_ids: string[] }>;
  hypothesis_scores: HypothesisScores;
}

//  V-8 사후 검증 
// GET /api/sherpa/validate-incident-type?caseId=
export interface IncidentTypeValidation {
  caseId: string;
  status: 'CONSISTENT' | 'REVIEW_NEEDED';
  current_incident_type: IncidentType;
  current_secondary?: IncidentType[];
  extra_techniques: string[]; // 매핑됐지만 현 사고유형으로 설명 안 되는 ATT&CK ID
  candidate_types: Array<{
    incident_type: IncidentType;
    score: number;
    reason: string;
  }>;
  message: string;
}
