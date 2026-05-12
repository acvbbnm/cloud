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

export interface RawEventItem {
  event_id: string;
  case_id: string;
  csp: CSP;
  event_time: string;
  event_name: string;
  source_file: string;
  matched_target_id: string | null;
  sha256_hash: string;
  created_at: string;
}

export interface OCSFEventItem {
  ocsf_id: string;
  event_id: string;
  class_uid: number;
  category_uid: number;
  activity_id: number;
  activity_name: string;
  time: number;
  actor: { user: { name: string; type: string; account_uid: string } };
  src_endpoint: { ip: string };
  status_code: string;
  severity_id: number;
  unmapped: Record<string, unknown>;
}

export interface AttackEventItem {
  attack_id: string;
  ocsf_id: string;
  technique_id: string;
  technique_name: string;
  tactic: string;
  rule_id: string;
  risk_score: number;
  event_time: string;
  activity_name: string;
}

export interface GapResultResponse {
  gap_id: string;
  case_id: string;
  gap_type: GapType;
  missing: { target_id: string; log_type: string; evidence_role: EvidenceRole; priority: number }[];
  summary: string;
  recommendation: string;
  completionRate: number;
  created_at: string;
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

export interface ChatResponse {
  sessionId: string;
  response: string;
  sources: { source_id: string; type: string; title: string }[];
}
