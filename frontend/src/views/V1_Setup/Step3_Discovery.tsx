/**
 * V-1 Step 3 — Discovery Loop (M0-3, dev3).
 *
 * 단서 루프 전용 화면. 시스템 구성(M0-2)은 별도 스텝으로 분리됨 (2026-05-22).
 *
 * 좌측:  단서 입력 (CluesInput) ·  부분 로그 분석 ·  결정 트리 6단계
 * 우측: 신뢰도 게이지 + 가설 점수 + 트리 미니맵 + 다음 단서 + 비교 차트 + 추천
 *
 * 진입 시 가설 점수는 0 이 아니라 M0-2 시스템 구성의 environment_modifiers 가
 * 시딩한 값에서 출발한다 (POST /api/triage/start 가 case.system_config 평가).
 *
 * 학술 근거: docs/dev3/V1_재설계_청사진.md §2 Step 2
 */
import { useEffect, useState } from 'react';

import Card from '@/components/Card';
import Badge from '@/components/Badge';
import CluesInput from '@/components/CluesInput';
import ConfidenceGauge from '@/components/ConfidenceGauge';
import DecisionTreeQuestion from '@/components/DecisionTreeQuestion';
import HypothesisBreakdownChart from '@/components/HypothesisBreakdownChart';
import DiscoveryIntroModal, {
  hasDismissedDiscoveryIntro,
} from '@/components/DiscoveryIntroModal';
import HypothesisScoreBar from '@/components/HypothesisScoreBar';
import NextCluePanel from '@/components/NextCluePanel';
import PartialLogAnalysis from '@/components/PartialLogAnalysis';
import TriageStepper from '@/components/TriageStepper';
import TriageTreeMinimap from '@/components/TriageTreeMinimap';

import type { ClueType } from '@/types';
import { useCaseStore } from '@/stores/useCaseStore';
import { useToastStore } from '@/stores/useToastStore';
import { useTriageStore } from '@/stores/useTriageStore';
import { analyzeClue, getBreakdown, nextTriage, startTriage } from '@/api/triage';
import type { BreakdownResponse } from '@/api/triage';

import type {
  IncidentType,
  TriageRecommendation,
  TriageTreeNode,
} from '@/types';

// dev3 B-2 (2026-05-19): 클라이언트 측 TECH_WEIGHTS·applyTechniqueWeights 제거.
// 점수 산출은 백엔드 /api/triage/analyze-logs 응답으로만 — 결정성 100% 보장
// (청사진 §3 — 정적 weights.json 단일 소스). 학술 변호: 클라이언트 mock 가중치
// 잔존은 weights.json 과 어긋날 위험이 있어 일괄 제거.

interface Step3DiscoveryProps {
  onPrev: () => void;
  /** 사고유형 확정 → M0-4 초동 수집 가이드로 진행. */
  onConfirm: (confirmedIncidentType: IncidentType) => void;
  isSubmitting?: boolean;
}

const INCIDENT_TYPE_KO: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '자격증명 탈취',
  PRIVILEGE_ESCALATION: '권한 상승',
  DATA_EXFILTRATION: '데이터 유출',
  AUDIT_LOG_TAMPERING: '감사 로그 변조',
  //  dev3 C-1 신규 4종 (2026-05-19, MULTI_CSP_LATERAL 제거) 
  RANSOMWARE: '랜섬웨어',
  MISCONFIG_EXPOSURE: '설정 오류 노출',
  PHISH_INITIAL_ACCESS: '피싱 초기 침투',
  INSIDER_THREAT: '내부자 위협',
  UNCLASSIFIED: '미분류',
};

const OUTCOME_LABEL: Record<TriageRecommendation['outcome'], string> = {
  auto_confirm: ' 자동 확정',
  propose_single: ' 단일 가설 제시',
  propose_composite: ' 복합 가설 (주 + 부)',
  continue_or_skip: ' 추가 단서 또는 UNCLASSIFIED 진행',
};

const Step3_Discovery = ({
  onPrev,
  onConfirm,
  isSubmitting,
}: Step3DiscoveryProps) => {
  const caseId = useCaseStore((s) => s.caseId);
  const observables = useCaseStore((s) => s.observables);
  const addObservable = useCaseStore((s) => s.addObservable);
  const removeObservable = useCaseStore((s) => s.removeObservable);
  const showToast = useToastStore((s) => s.show);

  const {
    currentNodeId,
    completedPath,
    hypothesisScores,
    mappedTechniques,
    recommendation,
    isTerminal,
    startTriage: storeStart,
    recordAnswer,
    addMappedTechniques,
    setCurrentNode,
    setHypothesisScores,
    setRecommendation,
    setTerminal,
    reset: resetTriage,
  } = useTriageStore();

  const [currentNode, setCurrentNodeData] = useState<TriageTreeNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [introOpen, setIntroOpen] = useState(false);
  /** NextCluePanel 권장 단서 클릭 시 CluesInput 의 selectedType 동기화 (mount 시점 키) */
  const [preferredClueType, setPreferredClueType] = useState<ClueType | null>(null);
  // Q4 (2026-05-21): 트리 답변에서 자동 추출된 variant — CluesInput 토글 자동 선택
  const [preferredVariant, setPreferredVariant] = useState<string | null>(null);
  // E4 §4-8 (2026-05-22): 출처 트레이스 — breakdown 응답 캐시 + 로딩 상태
  const [breakdown, setBreakdown] = useState<BreakdownResponse | null>(null);
  const [breakdownLoading, setBreakdownLoading] = useState(false);

  // 진입 시 사전 안내 모달 표시 (영속화 체크)
  useEffect(() => {
    if (!hasDismissedDiscoveryIntro()) {
      setIntroOpen(true);
    }
  }, []);

  // E4 §4-8 (2026-05-22): 출처 트레이스 자동 갱신 — 트리 답변·단서·기법 변할 때.
  // 500ms 디바운스 — 연속 입력 시 API 호출 폭주 방지.
  // breakdown 은 결정성 100% 라 매 입력마다 재계산해도 같은 결과 (학술 변호).
  useEffect(() => {
    if (!caseId) {
      setBreakdown(null);
      return;
    }
    // 아무 입력도 없으면 breakdown 비움 (서버 호출 X)
    if (
      completedPath.length === 0 &&
      observables.length === 0 &&
      mappedTechniques.length === 0
    ) {
      setBreakdown(null);
      return;
    }
    let cancelled = false;
    setBreakdownLoading(true);
    const t = window.setTimeout(async () => {
      try {
        const data = await getBreakdown(
          caseId,
          completedPath,
          observables,
          mappedTechniques,
        );
        if (!cancelled) setBreakdown(data);
      } catch (e) {
        // breakdown 실패는 핵심 흐름 차단 X — 토스트는 띄우지 않고 콘솔만
        console.warn('[triage/breakdown] 실패:', e);
        if (!cancelled) setBreakdown(null);
      } finally {
        if (!cancelled) setBreakdownLoading(false);
      }
    }, 500);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [caseId, completedPath, observables, mappedTechniques]);

  // 트리 시작 — 케이스가 있고 currentNodeId 가 없을 때.
  // POST /api/triage/start 가 case.system_config 의 environment_modifiers 를
  // 평가하여 0 이 아닌 가설 점수를 시딩해 반환한다 (M0-2 → M0-3 연결).
  useEffect(() => {
    let cancelled = false;
    const initTree = async () => {
      if (!caseId || currentNodeId) return;
      setLoading(true);
      try {
        const res = await startTriage(caseId);
        if (cancelled) return;
        if (res.next_node) {
          storeStart(res.next_node.id);
          setCurrentNodeData(res.next_node);
          setHypothesisScores(res.hypothesis_scores);
          const seeded = Object.values(res.hypothesis_scores).some((v) => v > 0);
          if (seeded) {
            showToast(' 시스템 구성 기반 환경 가중치가 가설 점수에 반영됐습니다', 3200);
          }
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        showToast(`트리아주 시작 실패: ${msg}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    initTree();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  // Q4 (2026-05-21): 트리 답변 → 단서 힌트 매핑 — 답변 선택 시 CluesInput 의 type
  // + variant 자동 선택. 사용자가 단서를 직접 추가하면 가중치까지 함께 부여됨.
  // 학술 근거: 결정 트리·단서·가중치 3 자산의 단일 trace 형성 (재현성·일관성 보장).
  const ANSWER_TO_CLUE_HINT: Record<
    string,
    { clueType: ClueType; variant?: string; reason: string }
  > = {
    // Q2A 옵션
    non_korean_ip: { clueType: 'IP_ADDRESS', variant: 'non_korean', reason: 'CSP 알람의 비국내 IP — IP 단서 추가' },
    object_storage_burst: { clueType: 'SERVICE', variant: 'object_storage', reason: 'Object Storage 대량 활동 — 서비스 단서' },
    privilege_change: { clueType: 'ACCOUNT', variant: 'privilege_changed', reason: '권한 변경 알람 — 해당 계정 단서' },
    audit_log_disabled: { clueType: 'SERVICE', variant: 'cloud_trail', reason: '감사 로그 비활성 — Cloud Trail 단서' },
    off_hours: { clueType: 'TIME_WINDOW', variant: 'off_hours', reason: '비표준 시각 — 시각 윈도우 단서' },
    // Q2B 옵션
    identity_theft: { clueType: 'ACCOUNT', variant: 'inactive_to_active', reason: '신원 도용 — 해당 계정 단서' },
    multi_csp_suspicious: { clueType: 'IP_ADDRESS', variant: 'multi_csp_observed', reason: '멀티 CSP — IP 단서' },
    data_exposed: { clueType: 'SERVICE', variant: 'object_storage', reason: '데이터 노출 — 서비스 단서' },
    // Q2C 옵션
    iam_burst: { clueType: 'ACCOUNT', variant: 'newly_created', reason: '신규 IAM 다수 — 계정 단서' },
    permission_changes: { clueType: 'ACCOUNT', variant: 'privilege_changed', reason: '권한 변경 다수 — 계정 단서' },
    log_gap: { clueType: 'SERVICE', variant: 'cloud_trail', reason: '감사 로그 누락 — Cloud Trail 단서' },
    data_access: { clueType: 'SERVICE', variant: 'object_storage', reason: '비정상 데이터 액세스 — 서비스 단서' },
    // Q3 옵션 (Q3_additional_context — 호환 유지)
    fail_then_success: { clueType: 'ACCOUNT', variant: 'mfa_disabled', reason: '실패→성공 패턴 — MFA 미적용 계정 단서' },
    multi_region_concurrent: { clueType: 'IP_ADDRESS', variant: 'multi_account', reason: '동시 다지역 — IP 단서' },
    storage_policy_change: { clueType: 'SERVICE', variant: 'object_storage', reason: 'Object Storage 정책 변경 — 서비스 단서' },
    serverless_new: { clueType: 'SERVICE', variant: 'iam', reason: 'Serverless 신규 — IAM 단서' },
    // E4 2026-05-21 — Q3 variants
    non_korean_geographic: { clueType: 'IP_ADDRESS', variant: 'non_korean', reason: '비국내 지리 — IP 단서' },
    storage_policy_public: { clueType: 'SERVICE', variant: 'object_storage', reason: 'Object Storage public 변경 — 서비스 단서' },
    s3_credential_change: { clueType: 'SERVICE', variant: 'iam', reason: 'S3 credential 변경 — IAM 단서' },
    multi_csp_pivot: { clueType: 'IP_ADDRESS', variant: 'multi_csp_observed', reason: '멀티 CSP 횡적이동 — IP 단서' },
    billing_spike: { clueType: 'SERVICE', variant: 'iam', reason: '결제 spike — 자원 단서' },
    off_hours_priv: { clueType: 'TIME_WINDOW', variant: 'off_hours', reason: '비표준 시각 권한 변경 — 시각 단서' },
    multiple_iam_changes: { clueType: 'ACCOUNT', variant: 'privilege_changed', reason: '다수 IAM 변경 — 계정 단서' },
    gradual_priv_creep: { clueType: 'ACCOUNT', variant: 'privilege_changed', reason: '권한 점진 상승 — 계정 단서' },
    self_audit_disable: { clueType: 'SERVICE', variant: 'cloud_trail', reason: '본인 감사 비활성 — Cloud Trail 단서' },
    mass_encrypt: { clueType: 'SERVICE', variant: 'object_storage', reason: '대량 암호화 — Object Storage 단서' },
    backup_deletion: { clueType: 'SERVICE', variant: 'object_storage', reason: '백업 삭제 — Object Storage 단서' },
    ransom_extension: { clueType: 'HASH', variant: 'unknown', reason: '비표준 확장자 — 해시 단서 (unknown)' },
    storage_destruction: { clueType: 'SERVICE', variant: 'object_storage', reason: 'Object Storage 파괴 — 서비스 단서' },
    // E4 — Q4 옵션
    mfa_token_reuse: { clueType: 'ACCOUNT', variant: 'mfa_disabled', reason: 'MFA 토큰 재사용 — 해당 계정 단서' },
    mfa_registration_change: { clueType: 'ACCOUNT', variant: 'mfa_disabled', reason: 'MFA 등록 변경 — 계정 단서' },
    mfa_not_applied: { clueType: 'ACCOUNT', variant: 'mfa_disabled', reason: 'MFA 미적용 — 계정 단서' },
    audit_log_tampered: { clueType: 'SERVICE', variant: 'cloud_trail', reason: '인증 감사 로그 변조 — Cloud Trail 단서' },
    backup_destroyed: { clueType: 'SERVICE', variant: 'object_storage', reason: '백업 파괴 — Object Storage 단서' },
    short_term_public: { clueType: 'TIME_WINDOW', reason: '단기 공개 — 시각 윈도우 단서' },
    long_term_public: { clueType: 'TIME_WINDOW', reason: '장기 노출 — 시각 윈도우 단서' },
    scope_excess: { clueType: 'ACCOUNT', variant: 'privilege_changed', reason: '직무 초과 — 계정 단서' },
    partner_account: { clueType: 'ACCOUNT', variant: 'newly_created', reason: '협력사 계정 — 계정 단서' },
    // E4 — Q5 옵션
    tor_vpn: { clueType: 'IP_ADDRESS', variant: 'tor_vpn', reason: 'Tor/VPN exit — IP 단서' },
    internal_ip: { clueType: 'IP_ADDRESS', variant: 'multi_account', reason: '사내 IP — IP 단서' },
    internal_endpoint: { clueType: 'IP_ADDRESS', variant: 'multi_account', reason: '사내 단말 — IP 단서' },
    internal_vpn: { clueType: 'IP_ADDRESS', variant: 'multi_csp_observed', reason: '사내+VPN — IP 단서' },
    trace_deletion: { clueType: 'SERVICE', variant: 'cloud_trail', reason: '흔적 삭제 — Cloud Trail 단서' },
    storage_wide: { clueType: 'SERVICE', variant: 'object_storage', reason: 'Storage 광범위 — 서비스 단서' },
    multi_region: { clueType: 'IP_ADDRESS', variant: 'multi_account', reason: '멀티 리전 — IP 단서' },
    operator: { clueType: 'ACCOUNT', variant: 'privilege_changed', reason: '운영자 변경 — 계정 단서' },
    abnormal_ip: { clueType: 'IP_ADDRESS', variant: 'non_korean', reason: '비정상 IP — IP 단서' },
    automation_script: { clueType: 'ACCOUNT', variant: 'newly_created', reason: '자동화 스크립트 — 계정 단서' },
    // E4 — Q6 옵션
    priv_change: { clueType: 'ACCOUNT', variant: 'privilege_changed', reason: '권한 변경 — 계정 단서' },
    storage_download: { clueType: 'SERVICE', variant: 'object_storage', reason: '대량 다운로드 — Object Storage 단서' },
    function_persist: { clueType: 'SERVICE', variant: 'iam', reason: '신규 함수 지속성 — IAM 단서' },
    note_found: { clueType: 'HASH', variant: 'known_malicious', reason: '랜섬 노트 — 해시 단서' },
    double_extortion: { clueType: 'DOMAIN', variant: 'c2', reason: '이중 협박 도메인 — 도메인 단서' },
    pii: { clueType: 'SERVICE', variant: 'object_storage', reason: 'PII 데이터 — Object Storage 단서' },
    trade_secret: { clueType: 'SERVICE', variant: 'object_storage', reason: '영업비밀 — Object Storage 단서' },
    data_external: { clueType: 'IP_ADDRESS', variant: 'non_korean', reason: '데이터 외부 전송 — IP 단서' },
    iam_self_delete: { clueType: 'ACCOUNT', variant: 'privilege_changed', reason: 'IAM 자기 삭제 — 계정 단서' },
  };

  const handleSubmitAnswer = async (answerIds: string[]) => {
    if (!caseId || !currentNodeId) return;
    setLoading(true);
    try {
      const res = await nextTriage(
        {
          caseId,
          current_node_id: currentNodeId,
          answer_ids: answerIds,
        },
        hypothesisScores,
        completedPath,
      );
      recordAnswer(currentNodeId, answerIds);
      setHypothesisScores(res.hypothesis_scores);
      setRecommendation(res.recommendation ?? null);
      setTerminal(res.is_terminal);
      if (res.next_node) {
        setCurrentNode(res.next_node.id);
        setCurrentNodeData(res.next_node);
      } else {
        setCurrentNode(null);
        setCurrentNodeData(null);
      }
      // Q4: 답변 중 단서 힌트가 있는 것 — 첫 번째만 적용 (CluesInput 자동 선택)
      for (const ansId of answerIds) {
        const hint = ANSWER_TO_CLUE_HINT[ansId];
        if (hint) {
          setPreferredClueType(hint.clueType);
          setPreferredVariant(hint.variant ?? null);
          showToast(` ${hint.reason}`, 2800);
          break;
        }
      }
      // E4 §4-4 (2026-05-21): 격차 기반 진단 hint — 답변 직후 1·2위 격차 토스트
      const sorted = (Object.keys(res.hypothesis_scores) as IncidentType[])
        .filter((t) => t !== 'UNCLASSIFIED')
        .map((t) => res.hypothesis_scores[t] ?? 0)
        .sort((a, b) => b - a);
      const gap = sorted[0] - (sorted[1] ?? 0);
      const primary = sorted[0];
      if (primary >= 130 && gap >= 30) {
        showToast(' 명확 — 자동 확정 가능. 우측 “확정” 버튼으로 진행', 3500);
      } else if (gap >= 20) {
        showToast(` 명확해지는 중 (격차 ${gap}점)`, 2200);
      } else if (gap >= 10) {
        showToast(`가설 형성 중 (격차 ${gap}점) — Q4·Q5 진행 권장`, 2200);
      } else if (primary > 0) {
        showToast(` 여전히 모호 (격차 ${gap}점) — 추가 단서 또는 답변 권장`, 2500);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(`트리아주 진행 실패: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  const handleResetTree = async () => {
    if (!caseId) return;
    resetTriage();
    setCurrentNodeData(null);
    setLoading(true);
    try {
      const res = await startTriage(caseId);
      if (res.next_node) {
        storeStart(res.next_node.id);
        setCurrentNodeData(res.next_node);
        setHypothesisScores(res.hypothesis_scores);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(`트리 리셋 실패: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  // 추천 결과의 주 사고유형으로 확정 → M0-4 진행
  const handleConfirm = () => {
    onConfirm(recommendation?.primary?.incident_type ?? 'UNCLASSIFIED');
  };

  // 건너뛰기 — UNCLASSIFIED 로 진행 (Layer 2 분석 후 V-8 Sherpa 가 추론)
  const handleSkip = () => {
    onConfirm('UNCLASSIFIED');
  };

  return (
    <div className="space-y-4 animate-fade-up">
      {/* 진입 사전 안내 모달 — 첫 진입 시만 */}
      <DiscoveryIntroModal open={introOpen} onClose={() => setIntroOpen(false)} />

      {/* 헤더 — 가벼운 안내 */}
      <div className="panel p-3 border-l-[3px] border-l-brand-teal text-[11.5px]">
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <span className="eyebrow">Layer 0 · M0-3 · Discovery Loop</span>
          <Badge tone="purple" size="sm">
            UNCLASSIFIED
          </Badge>
          <span className="text-ink-400">
            단서·트리아주 누적으로 사고유형을 추정합니다
          </span>
          <button
            onClick={() => setIntroOpen(true)}
            className="ml-auto text-[10.5px] text-brand-blue hover:underline"
          >
             사전 안내 다시 보기
          </button>
        </div>
        <div className="text-ink-500 text-[10.5px]">
          TheHive·DFIR-IRIS·NIST 800-61r2 표준 흐름. 결정성 100% — 같은 답변 시퀀스는 같은 결과.
        </div>
      </div>

      {/* E4 (2026-05-21): 진단 타임라인 stepper — Q1~Q6 6단계 가시화 */}
      <TriageStepper
        completedPath={completedPath}
        currentNodeId={currentNodeId}
        isTerminal={isTerminal}
      />

      {/* 2-panel 레이아웃 — 좌측 단서 루프 / 우측 가설 점수 */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_minmax(360px,400px)] gap-4">
        {/* 좌측 — 단서·부분로그·결정트리 */}
        <div className="space-y-3 min-w-0">
          {/*  단서 입력 */}
          <Card
            title={<> 단서 입력 (Observable)</>}
            subtitle={
              preferredClueType
                ? `우측 권장 단서 — ${preferredClueType} 를 추가하세요`
                : 'DFIR-IRIS IOC + NIST 800-61r2 표 3-2 + Velociraptor artifact 기반 6종'
            }
          >
            <CluesInput
              key={`${preferredClueType ?? 'default'}-${preferredVariant ?? 'none'}`}
              observables={observables}
              preferredType={preferredClueType}
              preferredVariant={preferredVariant}
              onAdd={(o) => {
                addObservable(o);
                setPreferredClueType(null); // 권장 단서 추가 후 힌트 제거
                setPreferredVariant(null);
              }}
              onAfterAdd={async (o) => {
                // Q2 (2026-05-21): 단서 추가 시 즉시 백엔드 /api/triage/analyze 호출 →
                // weight_key 가 있으면 그 가중치, 없으면 generic fallback (Q1) 적용.
                if (!caseId) return;
                try {
                  const res = await analyzeClue(caseId, hypothesisScores, {
                    type: o.type,
                    value: o.value,
                    weight_key: o.weight_key,
                    note: o.note,
                    added_at: o.added_at,
                  });
                  setHypothesisScores(res.hypothesis_scores);
                  // 토스트는 첫 단서만 (스팸 방지 — variant 명시는 더 강한 가중치라 알림 가치 큼)
                  if (o.weight_key) {
                    showToast(`단서 가중치 적용 (${o.weight_key})`);
                  }
                } catch (e) {
                  // 분석 실패해도 단서는 누적 — 백엔드 미응답 시 store 만 유지
                  console.warn('[triage/analyze] 단서 분석 실패:', e);
                }
              }}
              onRemove={removeObservable}
              disabled={loading}
            />
          </Card>

          {/*  부분 로그 분석 (선택) */}
          <Card
            title={<> 부분 로그 분석 (선택)</>}
            subtitle="AWS Detective scope time + Microsoft Sentinel entity 표준 흐름"
          >
            <PartialLogAnalysis
              caseId={caseId}
              currentScores={hypothesisScores}
              mappedTechniques={mappedTechniques}
              onAnalyzed={(techIds, _filenames, newScores) => {
                // dev3 B-2: 백엔드 /api/triage/analyze-logs 가 권위 있는 점수 산출
                // — 클라이언트 응답을 그대로 적용 (학술 변호: 결정성 100%).
                addMappedTechniques(techIds);
                setHypothesisScores(newScores);
                showToast(`${techIds.length}개 기법 매핑 → 가설 점수 갱신`);
              }}
              disabled={loading}
            />
          </Card>

          {/*  결정 트리 질문 */}
          <Card
            title={<> 결정 트리 (KISA §2.4 + NIST 800-61r2 §3.2)</>}
            subtitle="질문 답변이 우측 가설 점수에 즉시 반영됩니다"
          >
            {!caseId ? (
              <p className="text-[12px] text-ink-400">
                케이스 ID 가 없습니다. 이전 단계에서 케이스를 생성해주세요.
              </p>
            ) : !currentNode ? (
              loading ? (
                <p className="text-[12px] text-ink-400">트리아주 로딩 중…</p>
              ) : (
                <div>
                  <p className="text-[12px] text-ink-300 mb-2">
                    트리가 종료되었습니다. 우측 추천을 확인하세요.
                  </p>
                  <button onClick={handleResetTree} className="btn-ghost btn-sm">
                    ↻ 처음부터
                  </button>
                </div>
              )
            ) : (
              <DecisionTreeQuestion
                node={currentNode}
                step={completedPath.length + 1}
                totalEstimated={6}
                loading={loading}
                onSubmit={handleSubmitAnswer}
                onReset={handleResetTree}
              />
            )}
          </Card>
        </div>

        {/* 우측 — 가설 점수 + 추천 + 액션 (sticky + 자체 스크롤) */}
        <div className="min-w-0">
          <div className="panel p-4 lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto space-y-4">
            {/* E4 (2026-05-21): 신뢰도 게이지 — primary score / auto_skip ratio + gap hint */}
            <ConfidenceGauge scores={hypothesisScores} />

            <HypothesisScoreBar
              scores={hypothesisScores}
              highlightPrimary={recommendation?.primary?.incident_type}
              highlightSecondary={recommendation?.secondary?.incident_type}
            />

            {/* 트리 미니맵 (react-flow) — 사용자 결정 #3 */}
            <div>
              <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-1.5">
                 결정 트리 진행
              </div>
              <TriageTreeMinimap
                currentNodeId={currentNodeId}
                completedNodeIds={completedPath.map((p) => p.node_id)}
                isTerminal={isTerminal}
              />
            </div>

            {/* 다음 단서 제안 — 클릭 시 좌측 CluesInput 활성 */}
            <NextCluePanel
              scores={hypothesisScores}
              onPickClueType={(type) => {
                setPreferredClueType(type);
                showToast(`좌측 단서 입력에서 ${type} 를 추가해주세요`);
                // 좌측 단서 입력 영역으로 자동 스크롤 — 컨테이너 미정의 시 무시
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            />

            {/* E4 §4-8 (2026-05-21): 사고유형 비교 차트 + 기여 요소 요약
                2026-05-22: 백엔드 /api/triage/breakdown 실 데이터 연동 — 출처 trace */}
            <HypothesisBreakdownChart
              scores={hypothesisScores}
              treeAnswerCount={completedPath.length}
              clueCount={observables.length}
              mappedTechniqueCount={mappedTechniques.length}
              breakdown={breakdown}
              breakdownLoading={breakdownLoading}
            />

            {/* 단서 누적 요약 */}
            {observables.length > 0 && (
              <div className="border-t border-ink-700/40 pt-3">
                <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-1.5">
                   단서 {observables.length}개
                </div>
                <ul className="space-y-0.5">
                  {observables.slice(0, 5).map((o, i) => (
                    <li key={i} className="text-[10.5px] text-ink-300 leading-5 truncate">
                      <span className="text-ink-500">{o.type}</span> · {o.value}
                    </li>
                  ))}
                  {observables.length > 5 && (
                    <li className="text-[10.5px] text-ink-500">… 외 {observables.length - 5}개</li>
                  )}
                </ul>
                <p className="text-[10px] text-ink-500 mt-1.5 leading-4">
                  ※ 단서 추가 시 백엔드 /api/triage/analyze 가 가설 점수에 즉시 반영합니다.
                </p>
              </div>
            )}

            {/* 트리 경로 요약 (간단) */}
            {completedPath.length > 0 && (
              <div>
                <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-1.5">
                   트리 경로
                </div>
                <ul className="space-y-0.5">
                  {completedPath.map((p) => (
                    <li
                      key={p.node_id}
                      className="text-[10.5px] text-ink-300 leading-5"
                    >
                      <code className="text-ink-500">{p.node_id}</code>
                      <span className="text-ink-400 ml-1">
                        → {p.selected_option_ids.length}개 선택
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* E4 §4-6 (2026-05-21): 조기 종료 인라인 카드 — auto_confirm 도달했으나
                트리가 아직 진행 중일 때 노출 (Q4·Q5·Q6 계속 vs 즉시 확정) */}
            {recommendation?.outcome === 'auto_confirm' &&
              !isTerminal &&
              currentNodeId && (
                <div className="border-l-[3px] border-l-brand-teal bg-brand-teal/10 rounded-md p-3">
                  <div className="text-[11px] text-brand-teal font-semibold mb-1">
                     {recommendation.primary
                      ? INCIDENT_TYPE_KO[recommendation.primary.incident_type]
                      : '사고유형'}{' '}
                    신뢰도 도달
                  </div>
                  <div className="text-[10.5px] text-ink-200 mb-2 leading-4">
                    1위 점수 {recommendation.primary?.score}점 — auto_skip 임계 도달.
                    Q4·Q5·Q6 진행 시 의외성(복합 사고) 추가 발견 가능.
                  </div>
                  <div className="flex gap-1.5">
                    <button
                      onClick={handleConfirm}
                      disabled={isSubmitting}
                      className="btn-primary btn-xs flex-1 disabled:opacity-50"
                    >
                       지금 확정
                    </button>
                    <button
                      onClick={() => {
                        showToast('Q4·Q5·Q6 계속 진행 — 추가 시그널 확인');
                      }}
                      className="btn-ghost btn-xs flex-1"
                    >
                      계속 진행
                    </button>
                  </div>
                </div>
              )}

            {/* 추천 결과 */}
            {recommendation && (
              <div className="border-t border-ink-700/40 pt-3">
                <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-1.5">
                   추천
                </div>
                <div className="text-[12px] mb-2">
                  <Badge
                    tone={
                      recommendation.outcome === 'auto_confirm'
                        ? 'teal'
                        : recommendation.outcome === 'propose_composite'
                        ? 'amber'
                        : recommendation.outcome === 'propose_single'
                        ? 'blue'
                        : 'gray'
                    }
                    size="sm"
                  >
                    {OUTCOME_LABEL[recommendation.outcome]}
                  </Badge>
                </div>

                {recommendation.primary && (
                  <div className="text-[11.5px] text-ink-200 mb-1">
                    주: <b>{INCIDENT_TYPE_KO[recommendation.primary.incident_type]}</b>{' '}
                    <code className="text-ink-500">
                      ({recommendation.primary.score}점)
                    </code>
                  </div>
                )}
                {recommendation.secondary && (
                  <div className="text-[11.5px] text-ink-300 mb-1">
                    부: {INCIDENT_TYPE_KO[recommendation.secondary.incident_type]}{' '}
                    <code className="text-ink-500">
                      ({recommendation.secondary.score}점)
                    </code>
                  </div>
                )}

                {recommendation.rationale.length > 0 && (
                  <ul className="text-[10.5px] text-ink-400 leading-5 mt-1.5 list-disc pl-4 space-y-0.5">
                    {recommendation.rationale.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                )}

                <p className="text-[10.5px] text-ink-300 mt-2 leading-5">
                  {recommendation.message}
                </p>
              </div>
            )}

            {/* 액션 — 추천이 나오면 확정 가능, 이전·건너뛰기는 항상 제공 */}
            <div className="border-t border-ink-700/40 pt-3 space-y-1.5">
              {recommendation?.primary &&
                recommendation.outcome !== 'continue_or_skip' && (
                  <button
                    onClick={handleConfirm}
                    disabled={isSubmitting}
                    className="btn-primary btn-sm w-full disabled:opacity-50"
                  >
                    {isSubmitting
                      ? '진행 중…'
                      : ` ${INCIDENT_TYPE_KO[recommendation.primary.incident_type]} 로 확정 → 수집 가이드`}
                  </button>
                )}
              <button
                onClick={handleSkip}
                disabled={isSubmitting}
                className="btn-ghost btn-sm w-full disabled:opacity-50"
              >
                건너뛰기 — UNCLASSIFIED 로 진행
              </button>
              <button
                onClick={onPrev}
                disabled={isSubmitting}
                className="btn-ghost btn-sm w-full text-ink-400 disabled:opacity-50"
              >
                ← 시스템 구성
              </button>
              {!recommendation && (
                <p className="text-[10px] text-ink-500 leading-4 pt-1">
                   결정 트리를 끝까지 진행하면 추천 사고유형이 산출됩니다.
                  단서만으로 진행하려면 “건너뛰기”.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Step3_Discovery;
