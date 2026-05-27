import { useNavigate } from 'react-router-dom';

import { useMutation } from '@tanstack/react-query';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import { useCaseStore } from '@/stores/useCaseStore';
import { useTriageStore } from '@/stores/useTriageStore';
import { useClueTreeStore } from '@/stores/useClueTreeStore';
import { useToastStore } from '@/stores/useToastStore';
import { createCase, updateCase } from '@/api/intake';
import type { CSP, IncidentType, Severity } from '@/types';

import Step0_CSPCards from './Step0_CSPCards';
import Step1_CaseMetadata from './Step1_CaseMetadata';
import Step2_SystemConfig from './Step2_SystemConfig';
import Step3_Discovery from './Step3_Discovery';
import Step4_GuideChecklist_V2 from './Step4_GuideChecklist_V2';

// 2026-05-22: V-1 흐름 5단계 분리 — 시스템 구성(M0-2)과 단서 루프(M0-3)를
// 별도 스텝으로 분리. 시스템 구성을 먼저 받아 environment_modifiers 가 단서
// 루프의 가설 점수를 시딩하도록 순서를 고정한다 (사용자 결정 2026-05-22).
const stepLabels = [
  { code: 'M0-0', title: '분석 환경' },
  { code: 'M0-1', title: '케이스 메타' },
  { code: 'M0-2', title: '시스템 구성' },
  { code: 'M0-3', title: '단서 루프' },
  { code: 'M0-4', title: '수집 가이드' },
];

const V1Setup = () => {
  const navigate = useNavigate();
  const {
    csp,
    incidentType,
    caseId,
    title,
    tlp,
    severity,
    setCsp,
    setSeverity,
    setCaseId,
    setIncidentType,
  } = useCaseStore();
  const showToast = useToastStore((s) => s.show);
  const resetCase = useCaseStore((s) => s.reset);
  const resetTriage = useTriageStore((s) => s.reset);
  const resetClueTree = useClueTreeStore((s) => s.reset);

  // 2026-05-26 (사용자 피드백): intake 진행 상황을 다른 뷰 왕복에도 유지.
  //   - V-1 step 을 useCaseStore.currentStep 과 동기화 → localStorage 영속화
  //   - 이전 mount-시-auto-reset 동작 제거 (다른 뷰에서 돌아오면 그대로 이어감)
  //   - 명시적 [🔄 새 케이스] 버튼으로만 리셋 가능 (헤더)
  const step = useCaseStore((s) => s.currentStep);
  const setStep = useCaseStore((s) => s.setStep);

  /** 명시적 새 케이스 시작 — 사용자가 헤더의 [🔄 새 케이스] 클릭 시. */
  const startNewCase = () => {
    if (caseId) {
      const ok = window.confirm(
        '진행 중인 케이스 진행 상황이 모두 초기화됩니다. 새 케이스로 시작할까요?',
      );
      if (!ok) return;
    }
    // Phase P.16 (2026-05-27 사용자 피드백: "콜드스타트 안 되고 쓰레기 데이터 남아있음")
    //   useClueTreeStore 의 sessionStorage 영속 응답이 잔존 → 새 케이스인데
    //   옛 evidence_tree path/posterior 가 그대로 표시되는 버그. reset 추가.
    resetCase();
    resetTriage();
    resetClueTree();
    // 영속화 키들 명시 제거 — sessionStorage/localStorage 잔존 차단
    try {
      window.sessionStorage.removeItem('aisherpa.reconClueCard.dismissed');
      window.sessionStorage.removeItem('aisherpa.entryGuideBanner.dismissed');
    } catch {
      /* ignore */
    }
    setStep(0);
    showToast('새 케이스 시작 — V-1 처음부터 (모든 store 초기화)', 2500);
  };

  const current = stepLabels[step];

  // M0-1 종료 → UNCLASSIFIED 빈 케이스 생성 → caseId 부여 → M0-2 진입
  const initCaseMutation = useMutation({
    mutationFn: createCase,
    onSuccess: (data) => {
      setCaseId(data.caseId);
      setStep(2);
      showToast(`케이스 생성: ${data.caseId.slice(0, 8)}… (시스템 구성 입력)`);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`케이스 생성 실패: ${msg} (백엔드 실행 확인)`);
    },
  });

  // M0-2 종료 → system_config·severity PATCH → M0-3 단서 루프 진입.
  // 단서 루프 진입 시 startTriage 가 이 system_config 의 environment_modifiers 를
  // 평가해 가설 점수를 시딩한다.
  const systemConfigMutation = useMutation({
    mutationFn: ({
      caseId: id,
      data,
    }: {
      caseId: string;
      data: Parameters<typeof updateCase>[1];
    }) => updateCase(id, data),
    onSuccess: () => {
      setStep(3);
      showToast('시스템 구성 저장 → 단서 루프 진입');
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`시스템 구성 저장 실패: ${msg}`);
    },
  });

  // M0-3 종료 → incident_type 확정 PATCH → M0-4 초동 수집 가이드 진입
  const finalizeCaseMutation = useMutation({
    mutationFn: ({
      caseId: id,
      data,
    }: {
      caseId: string;
      data: Parameters<typeof updateCase>[1];
    }) => updateCase(id, data),
    onSuccess: (data) => {
      if (data.incident_type) setIncidentType(data.incident_type);
      setStep(4);
      showToast(`사고유형 확정: ${data.incident_type}`);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`사고유형 확정 실패: ${msg}`);
    },
  });

  return (
    <div>
      <PageHeader
        eyebrow={`Layer 0 · ${current.code}`}
        title="사고 접수 워크플로우"
        description="분석 환경·케이스 메타·시스템 구성을 정의하고, 단서 루프(결정 트리)로 사고유형을 추정한 뒤 우선순위가 매겨진 초동 수집 가이드를 생성합니다."
        meta={
          <div className="flex items-center gap-3 flex-wrap">
            {/* Phase P.3 (2026-05-26) — 명시적 새 케이스 시작 버튼.
                다른 뷰 왔다가 돌아와도 진행 상황 유지 → 사용자가 명시적으로 누를 때만 reset. */}
            {(caseId || step > 0) && (
              <button
                type="button"
                onClick={startNewCase}
                className="text-[10.5px] text-ink-400 hover:text-amber-300 border border-ink-700 hover:border-amber-500/60 px-2 py-0.5 rounded transition-colors"
                title="모든 진행 상황 초기화 + V-1 처음부터"
              >
                🔄 새 케이스
              </button>
            )}
            {stepLabels.map((s, i) => {
              const state = i < step ? 'done' : i === step ? 'cur' : 'idle';
              return (
                <button
                  key={s.code}
                  onClick={() => i <= step && setStep(i)}
                  className={`flex items-center gap-2 transition-opacity ${
                    state === 'idle' ? 'opacity-50 cursor-default' : 'hover:opacity-100'
                  }`}
                >
                  <span
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-bold border ${
                      state === 'done'
                        ? 'bg-brand-teal text-ink-950 border-brand-teal'
                        : state === 'cur'
                        ? 'bg-cta-gradient text-white border-transparent shadow-glow'
                        : 'bg-ink-850 text-ink-400 border-ink-700'
                    }`}
                  >
                    {state === 'done' ? '' : i}
                  </span>
                  <span
                    className={`text-[12px] ${
                      state === 'cur'
                        ? 'text-ink-100 font-semibold'
                        : state === 'done'
                        ? 'text-ink-200'
                        : 'text-ink-400'
                    }`}
                  >
                    {s.title}
                  </span>
                  {i < stepLabels.length - 1 && (
                    <span
                      className={`mx-1 w-6 h-px ${
                        i < step ? 'bg-brand-teal' : 'bg-ink-700'
                      }`}
                    />
                  )}
                </button>
              );
            })}
          </div>
        }
      />

      <PageBody className="animate-fade-up">
        {step === 0 && (
          <Step0_CSPCards
            selected={csp}
            onSelect={(id) => {
              setCsp(id);
              showToast(`CSP 전환: ${id}`);
            }}
            onNext={() => setStep(1)}
          />
        )}
        {step === 1 && (
          <Step1_CaseMetadata
            onPrev={() => setStep(0)}
            onNext={(occurredAt) => {
              if (!csp) {
                showToast('CSP 누락. Step 0 으로 돌아가세요.');
                return;
              }
              // M0-1 종료 → UNCLASSIFIED 빈 케이스 즉시 생성 → caseId 확보
              const occurredIso = (() => {
                const d = new Date(occurredAt);
                return Number.isNaN(d.getTime())
                  ? new Date().toISOString()
                  : d.toISOString();
              })();
              initCaseMutation.mutate({
                incident_type: 'UNCLASSIFIED',
                csp: csp as CSP,
                severity: (severity as Severity) ?? 'high',
                occurred_at: occurredIso,
                title: title ?? undefined,
                tlp: tlp ?? 'AMBER',
                observables: [],
              });
            }}
          />
        )}
        {step === 2 && (
          <Step2_SystemConfig
            csp={csp}
            incidentType={incidentType}
            onPrev={() => setStep(1)}
            onSubmit={(config) => {
              if (!caseId) {
                showToast('caseId 누락. Step 1 으로 돌아가 케이스를 생성하세요.');
                return;
              }
              setSeverity(config.severity);
              // M0-2 → PATCH /api/cases/{caseId} — 시스템 구성 영속화
              systemConfigMutation.mutate({
                caseId,
                data: {
                  severity: config.severity,
                  system_config: {
                    vpc_id: config.vpc_id,
                    region: config.region,
                    services: config.services,
                    network: config.network,
                    publicIp: config.publicIp,
                    auditEnabled: config.auditEnabled,
                    scope: config.scope,
                    mfa_status: config.mfa_status,
                    iam_account_count: config.iam_account_count,
                    audit_log_retention_days: config.audit_log_retention_days,
                    data_sensitivity: config.data_sensitivity,
                    sso_enabled: config.sso_enabled,
                    multi_cloud: config.multi_cloud,
                  },
                },
              });
            }}
            isSubmitting={systemConfigMutation.isPending}
          />
        )}
        {step === 3 && (
          <Step3_Discovery
            onPrev={() => setStep(2)}
            onConfirm={(confirmedIncidentType) => {
              if (!caseId) {
                showToast('caseId 누락. Step 1 으로 돌아가 케이스를 생성하세요.');
                return;
              }
              // M0-3 → PATCH /api/cases/{caseId} — 단서 루프 확정 사고유형 영속화
              finalizeCaseMutation.mutate({
                caseId,
                data: { incident_type: confirmedIncidentType as IncidentType },
              });
            }}
            isSubmitting={finalizeCaseMutation.isPending}
          />
        )}
        {step === 4 && (
          <Step4_GuideChecklist_V2
            onPrev={() => setStep(3)}
            onComplete={() => {
              showToast('수집 가이드 완료 → 로그 수집');
              navigate('/logs');
            }}
          />
        )}
      </PageBody>
    </div>
  );
};

export default V1Setup;
