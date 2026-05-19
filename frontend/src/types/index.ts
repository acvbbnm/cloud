// ── 공통 Enum 타입 (백엔드 DB enum과 정확히 일치) ──

// 백엔드 Pydantic Literal + types/index.ts 정책과 일치
// dev3 (2026-05-18): UNCLASSIFIED 추가 — 빈 케이스 시작 패턴 (TheHive·IRIS·NIST 800-61r2)
// dev3 C-1 (2026-05-19): 신규 4종 추가 — RANSOMWARE·MISCONFIG_EXPOSURE·PHISH_INITIAL_ACCESS·INSIDER_THREAT
// 2026-05-19 (재결정): MULTI_CSP_LATERAL 제거 — 사용자 명시. 환경 변수 multi_cloud 만 보존.
// 최종 8종 + UNCLASSIFIED (CSA Pandemic Eleven #1~7 + KISA §3.3 분류표 정합)
export type IncidentType =
  // ── 4종 기존 ──
  | 'CREDENTIAL_THEFT'
  | 'PRIVILEGE_ESCALATION'
  | 'DATA_EXFILTRATION'
  | 'AUDIT_LOG_TAMPERING'
  // ── dev3 C-1 신규 4종 ──
  | 'RANSOMWARE'
  | 'MISCONFIG_EXPOSURE'
  | 'PHISH_INITIAL_ACCESS'
  | 'INSIDER_THREAT'
  // ── 미분류 ──
  | 'UNCLASSIFIED';

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
export type CSP = 'naver' | 'nhn' | 'all';
export type Severity = 'critical' | 'high' | 'medium' | 'low';
export type EvidenceRole = 'REQUIRED' | 'CORROBORATING';
export type GapType = 'NONE' | 'COLLECTION' | 'EVIDENCE' | 'INTERPRETATION';
export type NodeStatus = 'CONFIRMED' | 'REJECTED';
export type ActionType = 'ACCEPT' | 'REJECT' | 'EDIT_REPORT' | 'FINALIZE_REPORT' | 'EXPORT_REPORT';

// ── API 요청 ──

export interface CreateCaseReq {
  incident_type: IncidentType;
  csp: CSP;
  severity: Severity;
  occurred_at: string;
  system_config?: Record<string, unknown>;
  // ── dev3 신규 (Step 1 케이스 메타) ──
  title?: string;
  tlp?: TLP;
  observables?: Observable[];
}

// ── API 응답 ──

export interface CaseResponse {
  caseId: string;
  incident_type: IncidentType;
  csp: CSP;
  severity: Severity;
  occurred_at: string;
  system_config: Record<string, unknown> | null;
  created_at: string;
  closed_at: string | null;
  // ── dev3 신규 ──
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

export interface GapResultResponse {
  gap_id: string;
  case_id: string;
  gap_type: GapType;
  missing: {
    target_id: string;
    log_type: string;
    evidence_role: EvidenceRole;
    priority: number;
  }[];
  summary: string;
  recommendation: string;
  completionRate: number;
  created_at: string;
}

export interface PaginatedData<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export interface BoardNode {
  node_id: string;
  attack_id: string | null;
  label: string;
  status: NodeStatus;
  is_ai_suggested: boolean;
  pos_x: number;
  pos_y: number;
}

export interface BoardEdge {
  edge_id: string;
  from_node_id: string;
  to_node_id: string;
  label: string;
}

export interface BoardResponse {
  caseId: string;
  nodes: BoardNode[];
  edges: BoardEdge[];
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

// ─────────────────────────────────────────────────────────
// /api/guide/v2 응답 (dev2 청사진  5 정합)
// ─────────────────────────────────────────────────────────

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
}

// ─────────────────────────────────────────────────────────
// dev3 — Triage / Discovery Loop 타입
// 청사진: docs/dev3/V1_재설계_청사진.md
// 가중치: backend/data/triage/weights.json
// ─────────────────────────────────────────────────────────

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
}

// 결정 트리 진행 상태 (DB triage_state JSON 칼럼)
export interface TriageState {
  current_node_id: string;
  completed_path: Array<{
    node_id: string;
    selected_option_ids: string[];
  }>;
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

// ─── API 요청 / 응답 ───

// POST /api/triage/analyze — 단서 + 부분 로그 → 가설 갱신
export interface TriageAnalyzeRequest {
  caseId: string;
  clue?: Observable;
  // 부분 로그 분석은 multipart/form-data 로 별도 호출 가능
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
export interface TriageNextRequest {
  caseId: string;
  current_node_id: string;
  answer_ids: string[]; // multi_select 지원
}

export interface TriageNextResponse {
  next_node: TriageTreeNode | null;
  hypothesis_scores: HypothesisScores;
  tree_path: Array<{ node_id: string; selected_option_ids: string[] }>;
  is_terminal: boolean;
  recommendation?: TriageRecommendation | null;
}

// POST /api/triage/confirm — 사고유형 확정
export interface TriageConfirmRequest {
  caseId: string;
  incident_type: IncidentType;
  secondary_incident_types?: IncidentType[];
}

// GET /api/triage/tree?caseId= — 시각화용 트리 전체 + 진행 상태
export interface TriageTreeResponse {
  caseId: string;
  nodes: TriageTreeNode[];
  current_node_id: string;
  completed_path: Array<{ node_id: string; selected_option_ids: string[] }>;
  hypothesis_scores: HypothesisScores;
}

// ─── V-8 사후 검증 ───
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
