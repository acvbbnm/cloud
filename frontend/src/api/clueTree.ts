/**
 * Evidence Tree API wrapper — Phase C (2026-05-25, byungwoo).
 *
 * 백엔드 라우터 `backend/api/clue_tree.py` 와 1:1 정합:
 *   POST /api/clue-tree/start    — uniform prior + 초기 5 후보 (idempotent)
 *   POST /api/clue-tree/expand   — 단서 채택 → 베이즈 갱신 + 다음 후보 (entropy 동적 K)
 *   POST /api/clue-tree/suggest  — 현 leaf 후보 재계산 (트리는 그대로)
 *   GET  /api/clue-tree?caseId=  — 트리 상태 조회
 *
 * 설계 원칙 (docs/evidence_tree_paradigm.md §6):
 *   - 모든 베이즈 산술은 서버. 클라이언트는 시각화 + 상태 동기화만.
 *   - 영속화는 DB (`incident_cases.triage_state.evidence_tree`) + sessionStorage 캐시.
 *   - `outcome_flags` 정형 Boolean (Google Chronicle Rule-to-Outcome, PDF §17.A)
 *     은 응답에 동봉됨 — Phase D 의 NextCluePanel 강조 UI 에서 활용.
 */
import client from './client';

import type {
  ClueTreeResponse,
  ClueExpandRequest,
  ExplainClueResponse,
  ReconOptionsResponse,
} from '@/types/clueTree';

/** POST /api/clue-tree/start — 빈 트리 시작 (idempotent). */
export const startClueTree = async (
  caseId: string,
): Promise<ClueTreeResponse> => {
  const res = await client.post('/api/clue-tree/start', { caseId });
  return res.data.data;
};

/**
 * POST /api/clue-tree/expand — 단서 채택 → 트리 자라기.
 *
 * source:
 *   - 'tree_candidate' (기본) : 현 leaf 의 children_candidates 중 클릭
 *   - 'direct_input'          : 좌측 CluesInput 자유 입력
 *   - 'log_analysis'          : PartialLogAnalysis 결과로 추가된 후보
 */
export const expandClueTree = async (
  req: ClueExpandRequest,
): Promise<ClueTreeResponse> => {
  const res = await client.post('/api/clue-tree/expand', req);
  return res.data.data;
};

/** POST /api/clue-tree/suggest — 현 leaf 의 후보를 재계산. */
export const suggestClueCandidates = async (
  caseId: string,
): Promise<ClueTreeResponse> => {
  const res = await client.post('/api/clue-tree/suggest', { caseId });
  return res.data.data;
};

/** GET /api/clue-tree?caseId= — 영속화된 트리 로드. */
export const getClueTree = async (
  caseId: string,
): Promise<ClueTreeResponse> => {
  const res = await client.get('/api/clue-tree', { params: { caseId } });
  return res.data.data;
};

/** POST /api/clue-tree/reset — 기존 트리 폐기 + cold-start 로 재시작. */
export const resetClueTree = async (
  caseId: string,
): Promise<ClueTreeResponse> => {
  const res = await client.post('/api/clue-tree/reset', { caseId });
  return res.data.data;
};

/**
 * POST /api/clue-tree/retract — 채택된 단서 1개 철회.
 *
 * 선형 트리에서 단서 제거 → 결정성을 이용해 cold-start 후 남은 단서 replay.
 * 응답은 삭제 반영된 최신 트리 — 트리·컴퍼스 모두 갱신됨 (2026-06-03).
 */
export const retractClue = async (
  caseId: string,
  nodeId: string,
): Promise<ClueTreeResponse> => {
  const res = await client.post('/api/clue-tree/retract', {
    caseId,
    node_id: nodeId,
  });
  return res.data.data;
};

/**
 * GET /api/clue-tree/explain/{clue_key} — Phase H.4.
 *
 * BN 추론 trace 조회. 후보 hover/click 시 ATT&CK 매핑·per-technique likelihood·
 * aggregated likelihood 노출 (PDF §17.B BAN 학술 설명).
 */
export const explainClue = async (
  clueKey: string,
): Promise<ExplainClueResponse> => {
  // clue_key 는 ':' 포함 ("IP_ADDRESS:tor_vpn") — encodeURIComponent
  const res = await client.get(
    `/api/clue-tree/explain/${encodeURIComponent(clueKey)}`,
  );
  return res.data.data;
};

/**
 * GET /api/clue-tree/recon-options — Phase N.1 정찰 단서 옵션.
 *
 * NIST SP 800-86 §4.1 Initial Triage 정합. cold-start 시 사용자가 사고유형
 * 무관 약한 신호 (Q1 inception / Q2A alert_type) 2-4개 채택하여 posterior 를
 * 약하게 비균등하게 만든 후 자체 단서 입력 — 한 쪽 사고유형 쏠림 차단.
 */
export const getReconOptions = async (): Promise<ReconOptionsResponse> => {
  const res = await client.get('/api/clue-tree/recon-options');
  return res.data.data;
};

/**
 * POST /api/clue-tree/advance-stage — Phase N.4 다단계 공격 chain 진입.
 *
 * 확정된 사고유형을 anchor 로 freeze 하고 다음 stage 의 새 baseline (STAGE_TRANSITION_MATRIX
 * 의 연관 가중치) 으로 진행. paradigm §23 정합.
 */
export const advanceClueTreeStage = async (
  caseId: string,
  confirmedHypothesis: string,
): Promise<ClueTreeResponse> => {
  const res = await client.post('/api/clue-tree/advance-stage', {
    caseId,
    confirmed_hypothesis: confirmedHypothesis,
  });
  return res.data.data;
};
