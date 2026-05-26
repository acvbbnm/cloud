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
  /**
   * Phase D — Google Chronicle Rule-to-Outcome 정형 Boolean/enum (PDF §17.A).
   * 예: { outcomeIsAnonymizedSource: true, outcomeSourceCategoryHint: 'tor_vpn' }
   */
  outcome_flags: Record<string, boolean | string | number>;
  /**
   * Phase H.4 — ATT&CK 기법 ID (clue_to_attack.json 매핑). 빈 배열 = 매핑 없음.
   * 예: ["T1556.006", "T1078"] — UI badge 로 노출. BN 모드 강조용.
   */
  techniques: string[];
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
  /** Phase H.4 — 백엔드 TRIAGE_MODE 값 ('bayes_net' 일 때 UI 가 ATT&CK badge 강조). */
  scoring_mode?: 'additive' | 'bayesian' | 'evidence_tree' | 'bayes_net';
}

/** explain_clue API 응답 (Phase H.4 + L.2 풍부 메타). */
export interface ExplainClueResponse {
  clue_key: string;
  techniques: string[];
  confidence: string;
  per_technique_likelihood?: Record<string, HypothesisScores>;
  aggregated_likelihood: HypothesisScores;
  source: 'bn' | 'legacy_fallback';

  // ── Phase L.2 (2026-05-26) — 풍부 메타 (clue_descriptions.json) ──
  /** 단서의 정의·의미 (한국어 풀어쓰기). */
  description?: string;
  /** CSP 콘솔에서 실제로 찾는 경로 (NCP·NHN·외부 검증). */
  how_to_find?: {
    ncp?: string;
    nhn?: string;
    verify?: string;
  };
  /** 카테고리별 대표 사례 (IP·해시·도메인 등). */
  examples?: string[];
  /** 사고유형 가중치 분석 → 한국어 변별 풀이. */
  discrimination_explanation?: string;
  /** 학술 인용 (MITRE T-id, KISA, CSA 등). */
  academic_source?: string;
  /** ISO/IEC 27035 단계 (Assess & Decide 등). */
  iso_framework?: string | null;
}

/** POST /api/clue-tree/expand 요청. */
export interface ClueExpandRequest {
  caseId: string;
  parent_node_id: string;
  clue_key: string;
  source?: 'tree_candidate' | 'direct_input' | 'log_analysis';
  /** 사용자 입력값을 트리 노드 라벨로 표시 (direct_input 가시성 강화). */
  label_override?: string;
}
