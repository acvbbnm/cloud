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
import { useToastStore } from '@/stores/useToastStore';

import type {
  HypothesisScores,
  IncidentType,
  TriageNextRequest,
  TriageNextResponse,
  TriageRecommendation,
  TriageTreeNode,
} from '@/types';

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

/**
 * dev3 (2026-05-19): mock fallback 진입 시 사용자에게 토스트로 명시.
 * 같은 호출 사이클에서 토스트가 폭주하지 않도록 함수당 최대 1회만 발화 (모듈 레벨 flag).
 */
const _mockToastFired: Record<string, number> = {};
const notifyMockFallback = (label: string): void => {
  const now = Date.now();
  const last = _mockToastFired[label] ?? 0;
  // 동일 라벨 5초 내 중복 발화 억제
  if (now - last < 5000) return;
  _mockToastFired[label] = now;
  try {
    useToastStore.getState().show(`⚠ 백엔드 미응답 — ${label} mock 모드 진행`, 3000);
  } catch {
    // 토스트 미초기화 등 비상 — console.warn 만
  }
  // eslint-disable-next-line no-console
  console.warn(`[triage] ${label} backend unavailable → fallback to mock`);
};

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
    dynamic_next: {
      Q2A_alert_type: 'Q4_CRED',
      Q2B_report_content: 'Q4_MISCFG',
      Q2C_audit_pattern: 'Q4_INSIDER',
      Q2D_anomaly_form: 'Q4_RANSOM',
      default: 'T_evaluate',
    },
    options: [
      { id: 'fail_then_success', label: '실패→성공 인증 패턴', weight_key: 'Q3:fail_then_success' },
      { id: 'multi_region_concurrent', label: '동일 계정 동시 다지역 로그인', weight_key: 'Q3:multi_region_concurrent' },
      { id: 'storage_policy_change', label: 'Object Storage 정책 변경', weight_key: 'Q3:storage_policy_change' },
      { id: 'serverless_new', label: 'Cloud Function·Lambda 신규 생성', weight_key: 'Q3:serverless_new' },
      { id: 'unknown_extra', label: '알 수 없음', weight_key: 'Q3:unknown_extra', next: 'T_evaluate' },
    ],
  },
  // ── E4 Q4 노드 (증거 무결성·시간축) ──
  Q4_CRED: {
    id: 'Q4_CRED',
    type: 'question',
    question: '증거 무결성 + MFA 상태를 확인해주세요.',
    options: [
      { id: 'mfa_token_reuse', label: 'MFA 토큰 재사용 (피싱/0ktapus 시그널)', weight_key: 'Q4_CRED:mfa_token_reuse', next: 'Q5_CRED' },
      { id: 'mfa_register_change', label: 'MFA 등록 변경 (사용자 직접 우회)', weight_key: 'Q4_CRED:mfa_register_change', next: 'Q5_CRED' },
      { id: 'mfa_not_applied', label: 'MFA 미적용', weight_key: 'Q4_CRED:mfa_not_applied', next: 'Q5_CRED' },
      { id: 'audit_log_deleted', label: '감사 로그 비활성·삭제 흔적', weight_key: 'Q4_CRED:audit_log_deleted', next: 'Q5_CRED' },
    ],
  },
  Q4_RANSOM: {
    id: 'Q4_RANSOM',
    type: 'question',
    question: '백업 무결성을 확인해주세요.',
    options: [
      { id: 'backup_destroyed', label: '백업 삭제·암호화 (T1490)', weight_key: 'Q4_RANSOM:backup_destroyed', next: 'Q5_RANSOM' },
      { id: 'backup_intact', label: '백업 정상', weight_key: 'Q4_RANSOM:backup_intact', next: 'Q5_RANSOM' },
      { id: 'backup_none', label: '백업 없음', weight_key: 'Q4_RANSOM:backup_none', next: 'Q5_RANSOM' },
    ],
  },
  Q4_MISCFG: {
    id: 'Q4_MISCFG',
    type: 'question',
    question: '공개 변경 시점을 확인해주세요.',
    options: [
      { id: 'intentional_recent', label: '외부 신고 직전 (의도적)', weight_key: 'Q4_MISCFG:intentional_recent', next: 'Q5_MISCFG' },
      { id: 'long_term_exposure', label: '사고 발견 이전 장기 노출 (실수)', weight_key: 'Q4_MISCFG:long_term_exposure', next: 'Q5_MISCFG' },
      { id: 'unknown_timing', label: '미상', weight_key: 'Q4_MISCFG:unknown_timing', next: 'Q5_MISCFG' },
    ],
  },
  Q4_INSIDER: {
    id: 'Q4_INSIDER',
    type: 'question',
    question: '사용자 직무 범위를 확인해주세요.',
    options: [
      { id: 'scope_excess', label: '직무 범위 초과', weight_key: 'Q4_INSIDER:scope_excess', next: 'Q5_INSIDER' },
      { id: 'scope_normal', label: '직무 범위 내 (정상)', weight_key: 'Q4_INSIDER:scope_normal', next: 'Q5_INSIDER' },
      { id: 'vendor_account', label: '협력사 계정', weight_key: 'Q4_INSIDER:vendor_account', next: 'Q5_INSIDER' },
    ],
  },
  // ── E4 Q5 노드 (영향 범위·행위자) ──
  Q5_CRED: {
    id: 'Q5_CRED',
    type: 'question',
    question: '행위자를 추정해주세요.',
    options: [
      { id: 'non_korean_ip', label: '비국내 IP (외부)', weight_key: 'Q5_CRED:non_korean_ip', next: 'Q6_CRED' },
      { id: 'internal_ip', label: '내부 사내 IP', weight_key: 'Q5_CRED:internal_ip', next: 'Q6_CRED' },
      { id: 'tor_vpn_exit', label: 'Tor·VPN exit', weight_key: 'Q5_CRED:tor_vpn_exit', next: 'Q6_CRED' },
    ],
  },
  Q5_RANSOM: {
    id: 'Q5_RANSOM',
    type: 'question',
    question: '영향 범위를 확인해주세요.',
    options: [
      { id: 'single_instance', label: '단일 인스턴스', weight_key: 'Q5_RANSOM:single_instance', next: 'Q6_RANSOM' },
      { id: 'storage_wide', label: 'Object Storage 전체', weight_key: 'Q5_RANSOM:storage_wide', next: 'Q6_RANSOM' },
      { id: 'multi_region_account', label: '멀티 리전·계정', weight_key: 'Q5_RANSOM:multi_region_account', next: 'Q6_RANSOM' },
    ],
  },
  Q5_MISCFG: {
    id: 'Q5_MISCFG',
    type: 'question',
    question: '변경 주체를 확인해주세요.',
    options: [
      { id: 'operator_error', label: '운영자 권한 (실수)', weight_key: 'Q5_MISCFG:operator_error', next: 'Q6_MISCFG' },
      { id: 'suspicious_ip', label: '비정상 IP (침해)', weight_key: 'Q5_MISCFG:suspicious_ip', next: 'Q6_MISCFG' },
      { id: 'automation_script', label: '자동화 스크립트', weight_key: 'Q5_MISCFG:automation_script', next: 'Q6_MISCFG' },
    ],
  },
  Q5_INSIDER: {
    id: 'Q5_INSIDER',
    type: 'question',
    question: '행위자 가시성을 확인해주세요.',
    options: [
      { id: 'internal_device', label: '사내 단말', weight_key: 'Q5_INSIDER:internal_device', next: 'Q6_INSIDER' },
      { id: 'internal_vpn', label: '사내 IP + 외부 VPN', weight_key: 'Q5_INSIDER:internal_vpn', next: 'Q6_INSIDER' },
      { id: 'trace_deletion', label: '자기 흔적 삭제 (s3credential.delete)', weight_key: 'Q5_INSIDER:trace_deletion', next: 'Q6_INSIDER' },
    ],
  },
  // ── E4 Q6 노드 (후속 시그널·의도) ──
  Q6_CRED: {
    id: 'Q6_CRED',
    type: 'question',
    question: '후속 시그널을 확인해주세요.',
    options: [
      { id: 'priv_change', label: '즉시 권한 변경 → CRED + PRIV 복합', weight_key: 'Q6_CRED:priv_change', next: 'T_evaluate' },
      { id: 'storage_download', label: 'Object Storage 다운로드 → CRED→DATA', weight_key: 'Q6_CRED:storage_download', next: 'T_evaluate' },
      { id: 'cloud_function_new', label: 'Cloud Function 신규 → PERSIST', weight_key: 'Q6_CRED:cloud_function_new', next: 'T_evaluate' },
      { id: 'no_followup', label: '후속 시그널 없음 (CRED 단독)', weight_key: 'Q6_CRED:no_followup', next: 'T_evaluate' },
    ],
  },
  Q6_RANSOM: {
    id: 'Q6_RANSOM',
    type: 'question',
    question: '랜섬 노트·협박 메시지를 확인해주세요.',
    options: [
      { id: 'ransom_note_found', label: '노트 발견 (확정 RANSOM)', weight_key: 'Q6_RANSOM:ransom_note_found', next: 'T_evaluate' },
      { id: 'double_extortion', label: '데이터 유출 동반 (Double Extortion)', weight_key: 'Q6_RANSOM:double_extortion', next: 'T_evaluate' },
      { id: 'simple_destruction', label: '노트 없음 (T1485 단순 파괴)', weight_key: 'Q6_RANSOM:simple_destruction', next: 'T_evaluate' },
    ],
  },
  Q6_MISCFG: {
    id: 'Q6_MISCFG',
    type: 'question',
    question: '데이터 민감도를 확인해주세요.',
    options: [
      { id: 'pii_data', label: '개인정보 (GDPR·개보법)', weight_key: 'Q6_MISCFG:pii_data', next: 'T_evaluate' },
      { id: 'trade_secret', label: '영업비밀', weight_key: 'Q6_MISCFG:trade_secret', next: 'T_evaluate' },
      { id: 'general_data', label: '일반 공개 데이터', weight_key: 'Q6_MISCFG:general_data', next: 'T_evaluate' },
    ],
  },
  Q6_INSIDER: {
    id: 'Q6_INSIDER',
    type: 'question',
    question: '사후 행동을 확인해주세요.',
    options: [
      { id: 'normal_exit', label: '정상 종료', weight_key: 'Q6_INSIDER:normal_exit', next: 'T_evaluate' },
      { id: 'data_exfil', label: '데이터 외부 전송', weight_key: 'Q6_INSIDER:data_exfil', next: 'T_evaluate' },
      { id: 'self_iam_deletion', label: '자기 IAM 삭제', weight_key: 'Q6_INSIDER:self_iam_deletion', next: 'T_evaluate' },
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
  // MULTI_CSP_LATERAL 키 2026-05-19 일괄 제거. Q2B:multi_csp_suspicious 옵션
  // 자체는 weights.json 에서도 0 점 처리되어 화면에 표시되어도 영향 없음.
  'Q1_inception:csp_alert':        { CREDENTIAL_THEFT: 15, PRIVILEGE_ESCALATION: 10, DATA_EXFILTRATION: 5,  AUDIT_LOG_TAMPERING: 5 },
  'Q1_inception:external_report':  { CREDENTIAL_THEFT: 5,  PRIVILEGE_ESCALATION: 5,  DATA_EXFILTRATION: 30, AUDIT_LOG_TAMPERING: 20 },
  'Q1_inception:audit':            { CREDENTIAL_THEFT: 5,  PRIVILEGE_ESCALATION: 15, DATA_EXFILTRATION: 10, AUDIT_LOG_TAMPERING: 25 },
  'Q1_inception:service_anomaly':  { CREDENTIAL_THEFT: 5,  PRIVILEGE_ESCALATION: 10, DATA_EXFILTRATION: 15, AUDIT_LOG_TAMPERING: 10 },
  'Q1_inception:unknown':          {},
  'Q2A:abnormal_login':            { CREDENTIAL_THEFT: 25, PRIVILEGE_ESCALATION: 5 },
  'Q2A:non_korean_ip':             { CREDENTIAL_THEFT: 20 },
  'Q2A:privilege_change':          { CREDENTIAL_THEFT: 10, PRIVILEGE_ESCALATION: 30 },
  'Q2A:object_storage_burst':      { DATA_EXFILTRATION: 30, CREDENTIAL_THEFT: 5 },
  'Q2A:audit_log_disabled':        { AUDIT_LOG_TAMPERING: 35, PRIVILEGE_ESCALATION: 10 },
  'Q2A:api_burst':                 { CREDENTIAL_THEFT: 10, DATA_EXFILTRATION: 10, PRIVILEGE_ESCALATION: 10 },
  'Q2A:off_hours':                 { CREDENTIAL_THEFT: 15, DATA_EXFILTRATION: 10 },
  'Q2B:data_exposed':              { DATA_EXFILTRATION: 35 },
  'Q2B:abnormal_billing':          { CREDENTIAL_THEFT: 15, PRIVILEGE_ESCALATION: 10 },
  'Q2B:identity_theft':            { CREDENTIAL_THEFT: 25 },
  'Q2B:multi_csp_suspicious':      { CREDENTIAL_THEFT: 10 },
  'Q2C:iam_burst':                 { PRIVILEGE_ESCALATION: 25, CREDENTIAL_THEFT: 10 },
  'Q2C:permission_changes':        { PRIVILEGE_ESCALATION: 25, AUDIT_LOG_TAMPERING: 5 },
  'Q2C:log_gap':                   { AUDIT_LOG_TAMPERING: 30 },
  'Q2C:data_access':               { DATA_EXFILTRATION: 25 },
  'Q2D:data_destruction':          { AUDIT_LOG_TAMPERING: 20, DATA_EXFILTRATION: 15 },
  'Q2D:ddos':                      { DATA_EXFILTRATION: 5 },
  'Q2D:resource_abuse':            { CREDENTIAL_THEFT: 15, PRIVILEGE_ESCALATION: 15 },
  'Q2D:response_delay':            { AUDIT_LOG_TAMPERING: 10 },
  'Q3:fail_then_success':          { CREDENTIAL_THEFT: 25 },
  'Q3:multi_region_concurrent':    { CREDENTIAL_THEFT: 15 },
  'Q3:storage_policy_change':      { DATA_EXFILTRATION: 25 },
  'Q3:serverless_new':             { PRIVILEGE_ESCALATION: 15, DATA_EXFILTRATION: 10 },
  'Q3:unknown_extra':              {},
  // ── E4 Q4 가중치 ──
  'Q4_CRED:mfa_token_reuse':       { CREDENTIAL_THEFT: 10, PRIVILEGE_ESCALATION: 5, PHISH_INITIAL_ACCESS: 25 },
  'Q4_CRED:mfa_register_change':   { CREDENTIAL_THEFT: 20, PRIVILEGE_ESCALATION: 5, PHISH_INITIAL_ACCESS: 5 },
  'Q4_CRED:mfa_not_applied':       { CREDENTIAL_THEFT: 15, RANSOMWARE: 5, MISCONFIG_EXPOSURE: 10, PHISH_INITIAL_ACCESS: 10 },
  'Q4_CRED:audit_log_deleted':     { CREDENTIAL_THEFT: 5, AUDIT_LOG_TAMPERING: 20, RANSOMWARE: 5, INSIDER_THREAT: 10 },
  'Q4_RANSOM:backup_destroyed':    { RANSOMWARE: 30, DATA_EXFILTRATION: 5 },
  'Q4_RANSOM:backup_intact':       { DATA_EXFILTRATION: 15, INSIDER_THREAT: 5 },
  'Q4_RANSOM:backup_none':         { RANSOMWARE: 15, DATA_EXFILTRATION: 5, MISCONFIG_EXPOSURE: 5 },
  'Q4_MISCFG:intentional_recent':  { MISCONFIG_EXPOSURE: 20, CREDENTIAL_THEFT: 5, DATA_EXFILTRATION: 10, INSIDER_THREAT: 5 },
  'Q4_MISCFG:long_term_exposure':  { MISCONFIG_EXPOSURE: 35, DATA_EXFILTRATION: 10 },
  'Q4_MISCFG:unknown_timing':      { MISCONFIG_EXPOSURE: 10, DATA_EXFILTRATION: 5 },
  'Q4_INSIDER:scope_excess':       { INSIDER_THREAT: 30, PRIVILEGE_ESCALATION: 10, DATA_EXFILTRATION: 5 },
  'Q4_INSIDER:scope_normal':       { INSIDER_THREAT: -5 },
  'Q4_INSIDER:vendor_account':     { INSIDER_THREAT: 25, CREDENTIAL_THEFT: 5, PRIVILEGE_ESCALATION: 5, DATA_EXFILTRATION: 5 },
  // ── E4 Q5 가중치 ──
  'Q5_CRED:non_korean_ip':         { CREDENTIAL_THEFT: 25, PHISH_INITIAL_ACCESS: 10 },
  'Q5_CRED:internal_ip':           { INSIDER_THREAT: 20, CREDENTIAL_THEFT: 5, PRIVILEGE_ESCALATION: 5 },
  'Q5_CRED:tor_vpn_exit':          { CREDENTIAL_THEFT: 30, DATA_EXFILTRATION: 5, RANSOMWARE: 5, PHISH_INITIAL_ACCESS: 10 },
  'Q5_RANSOM:single_instance':     { RANSOMWARE: 10, DATA_EXFILTRATION: 5 },
  'Q5_RANSOM:storage_wide':        { RANSOMWARE: 25, PRIVILEGE_ESCALATION: 5, DATA_EXFILTRATION: 10 },
  'Q5_RANSOM:multi_region_account': { RANSOMWARE: 35, PRIVILEGE_ESCALATION: 10, DATA_EXFILTRATION: 10 },
  'Q5_MISCFG:operator_error':      { MISCONFIG_EXPOSURE: 25, DATA_EXFILTRATION: 5 },
  'Q5_MISCFG:suspicious_ip':       { CREDENTIAL_THEFT: 20, MISCONFIG_EXPOSURE: 5, DATA_EXFILTRATION: 5, PHISH_INITIAL_ACCESS: 10 },
  'Q5_MISCFG:automation_script':   { MISCONFIG_EXPOSURE: 15, DATA_EXFILTRATION: 5, INSIDER_THREAT: 5 },
  'Q5_INSIDER:internal_device':    { INSIDER_THREAT: 25, PRIVILEGE_ESCALATION: 5, DATA_EXFILTRATION: 5 },
  'Q5_INSIDER:internal_vpn':       { INSIDER_THREAT: 30, CREDENTIAL_THEFT: 5, PRIVILEGE_ESCALATION: 5, DATA_EXFILTRATION: 5 },
  'Q5_INSIDER:trace_deletion':     { INSIDER_THREAT: 35, AUDIT_LOG_TAMPERING: 15 },
  // ── E4 Q6 가중치 ──
  'Q6_CRED:priv_change':           { PRIVILEGE_ESCALATION: 25, CREDENTIAL_THEFT: 10, INSIDER_THREAT: 5 },
  'Q6_CRED:storage_download':      { DATA_EXFILTRATION: 20, CREDENTIAL_THEFT: 5 },
  'Q6_CRED:cloud_function_new':    { PRIVILEGE_ESCALATION: 15, CREDENTIAL_THEFT: 5 },
  'Q6_CRED:no_followup':           { CREDENTIAL_THEFT: 10 },
  'Q6_RANSOM:ransom_note_found':   { RANSOMWARE: 35, DATA_EXFILTRATION: 5 },
  'Q6_RANSOM:double_extortion':    { RANSOMWARE: 30, DATA_EXFILTRATION: 20 },
  'Q6_RANSOM:simple_destruction':  { RANSOMWARE: 15, DATA_EXFILTRATION: 10, AUDIT_LOG_TAMPERING: 5, INSIDER_THREAT: 5 },
  'Q6_MISCFG:pii_data':            { DATA_EXFILTRATION: 25, MISCONFIG_EXPOSURE: 10 },
  'Q6_MISCFG:trade_secret':        { DATA_EXFILTRATION: 20, MISCONFIG_EXPOSURE: 10, INSIDER_THREAT: 5 },
  'Q6_MISCFG:general_data':        { MISCONFIG_EXPOSURE: 5 },
  'Q6_INSIDER:normal_exit':        { INSIDER_THREAT: 10 },
  'Q6_INSIDER:data_exfil':         { DATA_EXFILTRATION: 20, INSIDER_THREAT: 15 },
  'Q6_INSIDER:self_iam_deletion':  { AUDIT_LOG_TAMPERING: 20, INSIDER_THREAT: 15 },
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
      // 백엔드 미구현·미응답 — mock fallback (사용자 알림 + console.warn)
      notifyMockFallback('triage/start');
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
    // dev3 fix (2026-05-19): 백엔드 TriageNextRequest 가 hypothesis_scores +
    // tree_path 를 필수 요구 (stateless 정책 — 청사진 §3). 프론트 타입은 호환을
    // 위해 보존하고 페이로드 조합 시점에 두 필드를 합쳐 전송.
    const res = await client.post('/api/triage/next', {
      ...req,
      hypothesis_scores: currentScores,
      tree_path: currentPath,
    });
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
    // E4 dynamic_next — Q2 경로에 따라 Q4 분기 결정
    if (!nextNodeId && currentNode.dynamic_next) {
      const dynNext = currentNode.dynamic_next;
      const q2Entry = currentPath.find((p) => p.node_id.startsWith('Q2'));
      if (q2Entry && dynNext[q2Entry.node_id]) {
        nextNodeId = dynNext[q2Entry.node_id];
      } else {
        nextNodeId = dynNext.default ?? null;
      }
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
      notifyMockFallback('triage/next');
      return mockCall();
    }
    throw e;
  }
};

// ─────────────────────────────────────────────────────────────
// 부분 로그 분석 — POST /api/triage/analyze-logs (multipart)
// dev3 B-2 (jingyu 머지) — Step 2 Discovery Loop ② 부분 로그 분석.
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
// 단서 입력 시 가설 점수 보강 — POST /api/triage/analyze (Q2, 2026-05-21)
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
 * Q2 (2026-05-21): CluesInput 이 weight_key 부착한 Observable 을 보내면 백엔드가
 * weights.clue_types 에서 직접 조회. weight_key 없으면 백엔드가 자동 fallback
 * (Q1: f"{type}:generic" 조회 → 5점 가중치 부여).
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
