// ── 공통 Enum 타입 (백엔드 DB enum과 정확히 일치) ──

// 백엔드 Pydantic Literal + types/index.ts 정책과 일치 (5종, 2026-05-12 확정)
export type IncidentType =
  | 'CREDENTIAL_THEFT'
  | 'PRIVILEGE_ESCALATION'
  | 'DATA_EXFILTRATION'
  | 'AUDIT_LOG_TAMPERING'
  | 'MULTI_CSP_LATERAL';
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
}

export interface CollectionTargetItem {
  target_id: string;
  log_type: string;
  evidence_role: EvidenceRole;
  priority: number;
  description: string;
  collected: boolean;
}

export interface GuideResponse {
  caseId: string;
  completionRate: number;
  targets: CollectionTargetItem[];
}

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
  risk_score: number | null;
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
