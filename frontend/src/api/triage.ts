/**
 * Triage API wrapper — V-1 Step 2 Discovery Loop (dev3).
 *
 * 백엔드 미구현 상태에서는 mock 응답으로 동작. `VITE_USE_MOCK=true` 또는
 * 호출 실패 시 자동 fallback. mock 의 가중치 계산은 `decision_tree.json`+
 * `weights.json` 의 발췌본을 클라이언트에 임베드 (실제 백엔드 와 정합).
 *
 * 백엔드 라우터 (예정 — `backend/api/triage.py`):
 *   POST /api/triage/start    초기 트리 시작 (root node 반환)
 *   POST /api/triage/next     사용자 답변 → 다음 노드 + 점수 갱신
 *   POST /api/triage/analyze  단서/부분 로그 → 가설 점수 보강 (다음 사이클)
 *   POST /api/triage/confirm  사고유형 확정
 */
import axios from 'axios';

import client from './client';

import type {
  HypothesisScores,
  IncidentType,
  TriageNextRequest,
  TriageNextResponse,
  TriageRecommendation,
  TriageTreeNode,
} from '@/types';

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

// ─────────────────────────────────────────────────────────────
// Mock 데이터 — backend/data/triage/decision_tree.json 발췌 정합
// ─────────────────────────────────────────────────────────────

const MOCK_TREE: Record<string, TriageTreeNode> = {
  Q1_inception: {
    id: 'Q1_inception',
    type: 'question',
    question: '어떻게 사고를 알게 됐나요?',
    kisa_field: 'KISA §2.4 ① 사건 인지 경로',
    options: [
      {
        id: 'csp_alert',
        label: 'CSP 자체 알람 (Cloud Insight·Security Monitoring·자동 차단)',
        weight_key: 'Q1_inception:csp_alert',
        next: 'Q2A_alert_type',
      },
      {
        id: 'external_report',
        label: '외부 신고·제보',
        weight_key: 'Q1_inception:external_report',
        next: 'Q2B_report_content',
      },
      {
        id: 'audit',
        label: '정기 감사 중 발견',
        weight_key: 'Q1_inception:audit',
        next: 'Q2C_audit_pattern',
      },
      {
        id: 'service_anomaly',
        label: '서비스 이상 (장애·성능 저하)',
        weight_key: 'Q1_inception:service_anomaly',
        next: 'Q2D_anomaly_form',
      },
      {
        id: 'unknown',
        label: '출처 불명 / 모름',
        weight_key: 'Q1_inception:unknown',
        next: 'Q2E_minimal_checklist',
      },
    ],
  },
  Q2A_alert_type: {
    id: 'Q2A_alert_type',
    type: 'question',
    question: 'CSP 알람 내용은? (다중 선택 가능)',
    multi_select: true,
    options: [
      { id: 'abnormal_login', label: '비정상 로그인', weight_key: 'Q2A:abnormal_login', next: 'Q3_additional_context' },
      { id: 'non_korean_ip', label: '비국내 IP 접근', weight_key: 'Q2A:non_korean_ip', next: 'Q3_additional_context' },
      { id: 'privilege_change', label: '권한 변경 알람', weight_key: 'Q2A:privilege_change', next: 'Q3_additional_context' },
      { id: 'object_storage_burst', label: 'Object Storage 대량 활동', weight_key: 'Q2A:object_storage_burst', next: 'Q3_additional_context' },
      { id: 'audit_log_disabled', label: '감사 로그 비활성', weight_key: 'Q2A:audit_log_disabled', next: 'Q3_additional_context' },
      { id: 'api_burst', label: 'API 호출 burst', weight_key: 'Q2A:api_burst', next: 'Q3_additional_context' },
      { id: 'off_hours', label: '비표준 시각 작업', weight_key: 'Q2A:off_hours', next: 'Q3_additional_context' },
    ],
  },
  Q2B_report_content: {
    id: 'Q2B_report_content',
    type: 'question',
    question: '외부 신고 내용은?',
    options: [
      { id: 'data_exposed', label: '데이터 외부 노출 확인', weight_key: 'Q2B:data_exposed', next: 'Q3_additional_context' },
      { id: 'abnormal_billing', label: '비정상 결제·자원 사용', weight_key: 'Q2B:abnormal_billing', next: 'Q3_additional_context' },
      { id: 'identity_theft', label: '신원도용 의심', weight_key: 'Q2B:identity_theft', next: 'Q3_additional_context' },
      { id: 'multi_csp_suspicious', label: '멀티 CSP 의심 활동', weight_key: 'Q2B:multi_csp_suspicious', next: 'Q3_additional_context' },
    ],
  },
  Q2C_audit_pattern: {
    id: 'Q2C_audit_pattern',
    type: 'question',
    question: '정기 감사 비정상 패턴은?',
    options: [
      { id: 'iam_burst', label: '신규 IAM 계정 비정상 생성', weight_key: 'Q2C:iam_burst', next: 'Q3_additional_context' },
      { id: 'permission_changes', label: '권한 변경 이력 다수', weight_key: 'Q2C:permission_changes', next: 'Q3_additional_context' },
      { id: 'log_gap', label: '감사 로그 누락·삭제', weight_key: 'Q2C:log_gap', next: 'Q3_additional_context' },
      { id: 'data_access', label: '비정상 데이터 액세스', weight_key: 'Q2C:data_access', next: 'Q3_additional_context' },
    ],
  },
  Q2D_anomaly_form: {
    id: 'Q2D_anomaly_form',
    type: 'question',
    question: '서비스 이상 형태는?',
    options: [
      { id: 'data_destruction', label: '데이터 변조·파괴', weight_key: 'Q2D:data_destruction', next: 'Q3_additional_context' },
      { id: 'ddos', label: '서비스 장애·DDoS', weight_key: 'Q2D:ddos', next: 'Q3_additional_context' },
      { id: 'resource_abuse', label: '자원 비정상 소비 (암호화폐 채굴 등)', weight_key: 'Q2D:resource_abuse', next: 'Q3_additional_context' },
      { id: 'response_delay', label: '응답 지연', weight_key: 'Q2D:response_delay', next: 'Q3_additional_context' },
    ],
  },
  Q2E_minimal_checklist: {
    id: 'Q2E_minimal_checklist',
    type: 'terminal',
    action: 'skip_to_kisa_6_checklist',
    fallback_incident_type: 'UNCLASSIFIED',
    message:
      '사고 인지 단서가 부족합니다. KISA §2.4 6항목 점검표 모드로 진입합니다. 사고유형은 UNCLASSIFIED 로 시작하고 Layer 2 분석 후 V-8 Sherpa 가 추론합니다.',
  },
  Q3_additional_context: {
    id: 'Q3_additional_context',
    type: 'question',
    question: '추가 정황은?',
    kisa_field: 'KISA §2.4 ⑥ 네트워크 연결 지점',
    options: [
      { id: 'fail_then_success', label: '실패→성공 인증 패턴', weight_key: 'Q3:fail_then_success', next: 'T_evaluate' },
      { id: 'multi_region_concurrent', label: '동일 계정 동시 다지역 로그인', weight_key: 'Q3:multi_region_concurrent', next: 'T_evaluate' },
      { id: 'storage_policy_change', label: 'Object Storage 정책 변경', weight_key: 'Q3:storage_policy_change', next: 'T_evaluate' },
      { id: 'serverless_new', label: 'Cloud Function·Lambda 신규 생성', weight_key: 'Q3:serverless_new', next: 'T_evaluate' },
      { id: 'unknown_extra', label: '알 수 없음', weight_key: 'Q3:unknown_extra', next: 'T_evaluate' },
    ],
  },
  T_evaluate: {
    id: 'T_evaluate',
    type: 'terminal',
    action: 'evaluate_hypothesis',
    message: '단서 누적 결과를 평가합니다.',
  },
};

// weights.json 발췌 — 5/10/15/20/25/30/35/40 만 사용 (학술 변호)
const MOCK_WEIGHTS: Record<string, Partial<HypothesisScores>> = {
  'Q1_inception:csp_alert':        { CREDENTIAL_THEFT: 15, PRIVILEGE_ESCALATION: 10, DATA_EXFILTRATION: 5,  AUDIT_LOG_TAMPERING: 5 },
  'Q1_inception:external_report':  { CREDENTIAL_THEFT: 5,  PRIVILEGE_ESCALATION: 5,  DATA_EXFILTRATION: 30, AUDIT_LOG_TAMPERING: 20, MULTI_CSP_LATERAL: 5 },
  'Q1_inception:audit':            { CREDENTIAL_THEFT: 5,  PRIVILEGE_ESCALATION: 15, DATA_EXFILTRATION: 10, AUDIT_LOG_TAMPERING: 25, MULTI_CSP_LATERAL: 5 },
  'Q1_inception:service_anomaly':  { CREDENTIAL_THEFT: 5,  PRIVILEGE_ESCALATION: 10, DATA_EXFILTRATION: 15, AUDIT_LOG_TAMPERING: 10, MULTI_CSP_LATERAL: 5 },
  'Q1_inception:unknown':          {},
  'Q2A:abnormal_login':            { CREDENTIAL_THEFT: 25, PRIVILEGE_ESCALATION: 5 },
  'Q2A:non_korean_ip':             { CREDENTIAL_THEFT: 20, MULTI_CSP_LATERAL: 10 },
  'Q2A:privilege_change':          { CREDENTIAL_THEFT: 10, PRIVILEGE_ESCALATION: 30 },
  'Q2A:object_storage_burst':      { DATA_EXFILTRATION: 30, CREDENTIAL_THEFT: 5 },
  'Q2A:audit_log_disabled':        { AUDIT_LOG_TAMPERING: 35, PRIVILEGE_ESCALATION: 10 },
  'Q2A:api_burst':                 { CREDENTIAL_THEFT: 10, DATA_EXFILTRATION: 10, PRIVILEGE_ESCALATION: 10 },
  'Q2A:off_hours':                 { CREDENTIAL_THEFT: 15, DATA_EXFILTRATION: 10 },
  'Q2B:data_exposed':              { DATA_EXFILTRATION: 35 },
  'Q2B:abnormal_billing':          { CREDENTIAL_THEFT: 15, PRIVILEGE_ESCALATION: 10 },
  'Q2B:identity_theft':            { CREDENTIAL_THEFT: 25 },
  'Q2B:multi_csp_suspicious':      { MULTI_CSP_LATERAL: 30, CREDENTIAL_THEFT: 10 },
  'Q2C:iam_burst':                 { PRIVILEGE_ESCALATION: 25, CREDENTIAL_THEFT: 10 },
  'Q2C:permission_changes':        { PRIVILEGE_ESCALATION: 25, AUDIT_LOG_TAMPERING: 5 },
  'Q2C:log_gap':                   { AUDIT_LOG_TAMPERING: 30 },
  'Q2C:data_access':               { DATA_EXFILTRATION: 25 },
  'Q2D:data_destruction':          { AUDIT_LOG_TAMPERING: 20, DATA_EXFILTRATION: 15 },
  'Q2D:ddos':                      { DATA_EXFILTRATION: 5 },
  'Q2D:resource_abuse':            { CREDENTIAL_THEFT: 15, PRIVILEGE_ESCALATION: 15 },
  'Q2D:response_delay':            { AUDIT_LOG_TAMPERING: 10 },
  'Q3:fail_then_success':          { CREDENTIAL_THEFT: 25 },
  'Q3:multi_region_concurrent':    { CREDENTIAL_THEFT: 15, MULTI_CSP_LATERAL: 25 },
  'Q3:storage_policy_change':      { DATA_EXFILTRATION: 25 },
  'Q3:serverless_new':             { PRIVILEGE_ESCALATION: 15, DATA_EXFILTRATION: 10 },
  'Q3:unknown_extra':              {},
};

const MOCK_THRESHOLDS = {
  high_confidence: 70,
  auto_skip_tree: 90,
  gap_to_2nd: 20,
};

// 가중치 누적 → 새 hypothesis_scores 반환
const accumulateScores = (
  base: HypothesisScores,
  weightKey: string | null | undefined,
): HypothesisScores => {
  if (!weightKey) return { ...base };
  const delta = MOCK_WEIGHTS[weightKey];
  if (!delta) return { ...base };
  const next: HypothesisScores = { ...base };
  (Object.keys(delta) as IncidentType[]).forEach((t) => {
    next[t] = (next[t] ?? 0) + (delta[t] ?? 0);
  });
  return next;
};

// recommendation 산출 (T_evaluate 도달 시)
const evaluateRecommendation = (
  scores: HypothesisScores,
): TriageRecommendation => {
  const sorted = (Object.keys(scores) as IncidentType[])
    .filter((t) => t !== 'UNCLASSIFIED')
    .map((t) => ({ type: t, score: scores[t] }))
    .sort((a, b) => b.score - a.score);
  const primary = sorted[0];
  const secondary = sorted[1];
  const gap = primary.score - secondary.score;

  if (primary.score >= MOCK_THRESHOLDS.auto_skip_tree && gap >= MOCK_THRESHOLDS.gap_to_2nd) {
    return {
      outcome: 'auto_confirm',
      primary: { incident_type: primary.type, score: primary.score },
      rationale: [`${primary.type} ${primary.score}점 — 자동 확정 임계값 도달 (gap ${gap}점)`],
      message: '단일 사고유형 자동 확정',
    };
  }
  if (primary.score >= MOCK_THRESHOLDS.high_confidence && gap < MOCK_THRESHOLDS.gap_to_2nd) {
    return {
      outcome: 'propose_composite',
      primary: { incident_type: primary.type, score: primary.score },
      secondary: { incident_type: secondary.type, score: secondary.score },
      rationale: [
        `${primary.type} ${primary.score}점`,
        `${secondary.type} ${secondary.score}점 (gap ${gap}점 — 복합 가설)`,
      ],
      message: '복합 사고유형 제시 — 메인 + 부 사고유형',
    };
  }
  if (primary.score >= MOCK_THRESHOLDS.high_confidence) {
    return {
      outcome: 'propose_single',
      primary: { incident_type: primary.type, score: primary.score },
      rationale: [`${primary.type} ${primary.score}점 — 단일 가설 (사용자 수락 필요)`],
      message: '단일 사고유형 제시 (사용자 수락 필요)',
    };
  }
  return {
    outcome: 'continue_or_skip',
    primary: { incident_type: primary.type, score: primary.score },
    rationale: [`최상위 ${primary.type} ${primary.score}점 — 임계값 ${MOCK_THRESHOLDS.high_confidence}점 미달`],
    message: '임계값 미달 — 추가 단서 입력 또는 UNCLASSIFIED 진행',
  };
};

// ─────────────────────────────────────────────────────────────
// 공개 API
// ─────────────────────────────────────────────────────────────

const ROOT_NODE_ID = 'Q1_inception';

const INITIAL_SCORES = (): HypothesisScores => ({
  CREDENTIAL_THEFT: 0,
  PRIVILEGE_ESCALATION: 0,
  DATA_EXFILTRATION: 0,
  AUDIT_LOG_TAMPERING: 0,
  MULTI_CSP_LATERAL: 0,
  // dev3 C-1 신규 4종 (2026-05-19)
  RANSOMWARE: 0,
  MISCONFIG_EXPOSURE: 0,
  PHISH_INITIAL_ACCESS: 0,
  INSIDER_THREAT: 0,
  UNCLASSIFIED: 0,
});

/** Triage 시작 — root 노드 반환. 백엔드 미구현 시 mock fallback. */
export const startTriage = async (
  caseId: string,
): Promise<TriageNextResponse> => {
  if (USE_MOCK) {
    return {
      next_node: MOCK_TREE[ROOT_NODE_ID],
      hypothesis_scores: INITIAL_SCORES(),
      tree_path: [],
      is_terminal: false,
    };
  }
  try {
    const res = await client.post('/api/triage/start', { caseId });
    return res.data.data;
  } catch (e) {
    if (axios.isAxiosError(e) && (e.response?.status === 404 || !e.response)) {
      // 백엔드 미구현 — mock fallback
      console.warn('[triage] backend /api/triage/start not available, fallback to mock');
      return {
        next_node: MOCK_TREE[ROOT_NODE_ID],
        hypothesis_scores: INITIAL_SCORES(),
        tree_path: [],
        is_terminal: false,
      };
    }
    throw e;
  }
};

/** 사용자 답변 → 다음 노드 + 점수 갱신. */
export const nextTriage = async (
  req: TriageNextRequest,
  currentScores: HypothesisScores,
  currentPath: Array<{ node_id: string; selected_option_ids: string[] }>,
): Promise<TriageNextResponse> => {
  const realCall = async (): Promise<TriageNextResponse> => {
    const res = await client.post('/api/triage/next', req);
    return res.data.data;
  };
  const mockCall = (): TriageNextResponse => {
    const currentNode = MOCK_TREE[req.current_node_id];
    if (!currentNode || !currentNode.options) {
      return {
        next_node: null,
        hypothesis_scores: currentScores,
        tree_path: currentPath,
        is_terminal: true,
      };
    }
    // 선택된 옵션들의 weight 누적
    let nextScores = currentScores;
    let nextNodeId: string | null = null;
    for (const optId of req.answer_ids) {
      const opt = currentNode.options.find((o) => o.id === optId);
      if (!opt) continue;
      nextScores = accumulateScores(nextScores, opt.weight_key);
      if (!nextNodeId && opt.next) nextNodeId = opt.next;
    }
    const nextNode = nextNodeId ? MOCK_TREE[nextNodeId] : null;
    const isTerminal = !nextNode || nextNode.type === 'terminal';

    const newPath = [
      ...currentPath.filter((p) => p.node_id !== req.current_node_id),
      { node_id: req.current_node_id, selected_option_ids: req.answer_ids },
    ];

    let recommendation: TriageRecommendation | undefined;
    if (nextNode?.id === 'T_evaluate') {
      recommendation = evaluateRecommendation(nextScores);
    }
    return {
      next_node: nextNode,
      hypothesis_scores: nextScores,
      tree_path: newPath,
      is_terminal: isTerminal,
      recommendation,
    };
  };

  if (USE_MOCK) return mockCall();
  try {
    return await realCall();
  } catch (e) {
    if (axios.isAxiosError(e) && (e.response?.status === 404 || !e.response)) {
      console.warn('[triage] backend /api/triage/next not available, fallback to mock');
      return mockCall();
    }
    throw e;
  }
};
