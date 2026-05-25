/**
 * Evidence Tree 타입 — Phase C (2026-05-25, byungwoo).
 *
 * 백엔드 `backend/core/intake/clue_tree.py` (ClueTreeNode·ClueTree·ClueCandidate)
 * 와 1:1 매핑. `backend/core/intake/clue_tree_service.py:_build_response()` 의
 * 응답 스키마와 정합.
 */
import type { HypothesisScores, IncidentType } from '.';

/** 다음 후보 (트리 leaf 의 dashed children). */
export interface ClueCandidate {
  candidate_id: string;
  clue_key: string;
  label: string;
  category: string;
  value: string;
  /** Information Gain (KL divergence, Shannon 1948, bits). */
  expected_info_gain: number;
  rationale: string;
}

/** 채택된 단서 노드 1개 (path 표현). */
export interface ClueTreePathNode {
  node_id: string;
  depth: number;
  clue_key: string;
  label: string;
  category: string;
  value: string;
  source: 'system' | 'tree_candidate' | 'direct_input' | 'log_analysis';
  posterior_after: HypothesisScores;
}

/** 트리 직렬화 (DB JSON 영속화 — paradigm doc §5). */
export interface SerializedClueTreeNode {
  node_id: string;
  parent_id: string | null;
  depth: number;
  clue_key: string;
  category: string;
  value: string;
  label: string;
  source: string;
  score_delta: HypothesisScores;
  posterior_after: HypothesisScores;
  accepted_at: string;
  children_candidates: ClueCandidate[];
}

export interface SerializedClueTree {
  case_id: string;
  root_id: string;
  current_leaf_id: string;
  posterior_current: HypothesisScores;
  confidence_reached: boolean;
  incident_type_recommendation: IncidentType | null;
  created_at: string;
  updated_at: string;
  nodes: Record<string, SerializedClueTreeNode>;
}

/** Confidence 평가 결과 (paradigm doc §16 — 도달 시 notify_user_confirm). */
export interface ClueTreeConfidence {
  primary: IncidentType | null;
  primary_prob: number;
  secondary: IncidentType | null;
  secondary_prob: number;
  gap: number;
  confidence_reached: boolean;
  recommended_action:
    | 'notify_user_confirm'
    | 'propose_single'
    | 'propose_composite'
    | 'continue_collecting';
  /** Shannon entropy (bits) — 동적 후보 K 결정 기준 (5/3/2). */
  entropy_bits: number;
}

/** 4 엔드포인트 공통 응답 스키마. */
export interface ClueTreeResponse {
  tree: SerializedClueTree;
  current_leaf_id: string;
  posterior_current: HypothesisScores;
  confidence: ClueTreeConfidence;
  candidates: ClueCandidate[];
  path: ClueTreePathNode[];
}

/** POST /api/clue-tree/expand 요청. */
export interface ClueExpandRequest {
  caseId: string;
  parent_node_id: string;
  clue_key: string;
  source?: 'tree_candidate' | 'direct_input' | 'log_analysis';
}
