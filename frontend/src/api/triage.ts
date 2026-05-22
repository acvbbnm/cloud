/**
 * Triage API wrapper — V-1 Step 2 Discovery Loop (dev3).
 *
 * 백엔드 라우터 `backend/api/triage.py` 와 1:1 정합:
 *   POST /api/triage/start        초기 트리 시작 (root node 반환)
 *   POST /api/triage/next         사용자 답변 → 다음 노드 + 점수 갱신
 *   POST /api/triage/analyze      단서 → 가설 점수 보강 (JSON)
 *   POST /api/triage/analyze-logs 부분 로그 → ATT&CK 매핑 + 점수 보강 (multipart)
 *
 * 설계 원칙 (CLAUDE.md + 청사진 §3):
 *   - 점수 산출은 백엔드 정적 weights.json 단일 소스. 결정성 100%.
 *   - 클라이언트 측 mock 가중치·mock 트리는 두지 않는다 — weights.json·
 *     decision_tree.json 과 어긋나면 잘못된 사고유형을 산출하기 때문.
 *     (2026-05-21: E4 6단계 트리 도입 후 구식 3단계 mock 일괄 제거)
 *   - API 실패는 호출부(Step2_Discovery)의 try/catch + 토스트로 표면화한다.
 */
import client from './client';

import type {
  HypothesisScores,
  TriageNextRequest,
  TriageNextResponse,
} from '@/types';

/** Triage 시작 — root 노드 + 초기 점수 반환. */
export const startTriage = async (
  caseId: string,
): Promise<TriageNextResponse> => {
  const res = await client.post('/api/triage/start', { caseId });
  return res.data.data;
};

/**
 * 사용자 답변 → 다음 노드 + 점수 갱신.
 *
 * 백엔드 TriageNextRequest 는 hypothesis_scores + tree_path 를 필수 요구
 * (stateless 정책 — 청사진 §3). 프론트 타입 호환을 위해 페이로드 조합
 * 시점에 두 필드를 합쳐 전송한다.
 */
export const nextTriage = async (
  req: TriageNextRequest,
  currentScores: HypothesisScores,
  currentPath: Array<{ node_id: string; selected_option_ids: string[] }>,
): Promise<TriageNextResponse> => {
  const res = await client.post('/api/triage/next', {
    ...req,
    hypothesis_scores: currentScores,
    tree_path: currentPath,
  });
  return res.data.data;
};

// ─────────────────────────────────────────────────────────────
// 부분 로그 분석 — POST /api/triage/analyze-logs (multipart)
// dev3 B-2 — Step 2 Discovery Loop ② 부분 로그 분석.
// ─────────────────────────────────────────────────────────────

export interface AnalyzeLogsResponse {
  caseId: string;
  hypothesis_scores: HypothesisScores;
  mapped_events: Array<{
    attack_id: string;
    ocsf_id: string;
    technique_id: string;
    technique_name: string | null;
    tactic: string;
    rule_id: string;
    time: string | null;
    actor_user_name: string | null;
    src_endpoint_ip: string | null;
    activity_name: string | null;
  }>;
  ingestion?: Record<string, unknown>;
  normalization?: Record<string, unknown>;
  mapping?: Record<string, unknown>;
}

/**
 * POST /api/triage/analyze-logs (multipart) — 부분 로그 → ATT&CK 매핑 + 가설 점수 갱신.
 *
 * 백엔드 흐름:
 *   UploadFile → LogIngestor.ingest → OCSFNormalizer.normalize_case
 *   → AttackMapper.map_case → clue_time ±window_minutes 윈도우 필터
 *   → Triage.analyze 로 점수 누적
 */
export const analyzeLogs = async (
  caseId: string,
  file: File,
  currentScores: HypothesisScores,
  clueTime?: string | null,
  windowMinutes: number = 5,
): Promise<AnalyzeLogsResponse> => {
  const fd = new FormData();
  fd.append('caseId', caseId);
  fd.append('hypothesis_scores', JSON.stringify(currentScores));
  if (clueTime) fd.append('clue_time', clueTime);
  fd.append('window_minutes', String(windowMinutes));
  fd.append('file', file);
  const res = await client.post('/api/triage/analyze-logs', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data.data;
};

// ─────────────────────────────────────────────────────────────
// 단서 입력 시 가설 점수 보강 — POST /api/triage/analyze (JSON)
// ─────────────────────────────────────────────────────────────

export interface AnalyzeClueResponse {
  caseId: string;
  hypothesis_scores: HypothesisScores;
  mapped_techniques: string[];
  next_clues: unknown[];
}

/**
 * POST /api/triage/analyze (JSON) — 단서 입력 → 가설 점수 보강.
 *
 * CluesInput 이 weight_key 부착한 Observable 을 보내면 백엔드가
 * weights.clue_types 에서 직접 조회. weight_key 없으면 백엔드가 자동 fallback
 * (f"{type}:generic" 조회 → 일반 단서 가중치 부여).
 */
export const analyzeClue = async (
  caseId: string,
  currentScores: HypothesisScores,
  clue: {
    type: string;
    value: string;
    weight_key?: string | null;
    note?: string;
    added_at?: string;
  },
): Promise<AnalyzeClueResponse> => {
  const res = await client.post('/api/triage/analyze', {
    caseId,
    hypothesis_scores: currentScores,
    clue,
  });
  return res.data.data;
};

// ─────────────────────────────────────────────────────────────
// 출처 트레이스 — POST /api/triage/breakdown (JSON)
//
// HypothesisBreakdownChart "왜 이 가설인가" 출처 분해.
// 5개 소스(environment / tree / combo / clues / techniques) × 8 사고유형.
// 학술 변호: 결정성 100% — 같은 입력 시 같은 분해 (weights.json 단일 소스).
// ─────────────────────────────────────────────────────────────

export type BreakdownSource =
  | 'environment'
  | 'tree'
  | 'combo'
  | 'clue'
  | 'technique';

export interface BreakdownItem {
  source: BreakdownSource;
  /** weight_key / modifier id / technique_id 등 원본 키. */
  key: string;
  /** 화면 표시용 한국어 라벨 (질문+옵션 / 단서명 / 기법 등). */
  label: string;
  /** 사고유형별 기여 점수. */
  weights: HypothesisScores;
  /** weights.json 의 source 필드 (학술 인용·표준). */
  rationale?: string | null;
}

export interface BreakdownResponse {
  caseId: string;
  totals: HypothesisScores;
  by_source: {
    environment: HypothesisScores;
    tree: HypothesisScores;
    combo: HypothesisScores;
    clues: HypothesisScores;
    techniques: HypothesisScores;
  };
  items: BreakdownItem[];
}

/**
 * POST /api/triage/breakdown — 가설 점수 소스별·항목별 분해.
 *
 * `system_config` 는 caseId 로 백엔드가 DB 조회. 클라이언트는 누적 상태
 * (tree_path + observables + technique_ids) 만 전달.
 */
export const getBreakdown = async (
  caseId: string,
  treePath: Array<{ node_id: string; selected_option_ids: string[] }>,
  observables: Array<Record<string, unknown>>,
  techniqueIds: string[],
): Promise<BreakdownResponse> => {
  const res = await client.post('/api/triage/breakdown', {
    caseId,
    tree_path: treePath,
    observables,
    technique_ids: techniqueIds,
  });
  return res.data.data;
};
