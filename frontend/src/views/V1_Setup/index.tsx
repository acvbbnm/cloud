import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useMutation } from '@tanstack/react-query';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import { useCaseStore } from '@/stores/useCaseStore';
import { useToastStore } from '@/stores/useToastStore';
import { createCase } from '@/api/intake';
import type { IncidentType, CSP, Severity } from '@/types';

import Step0_CSPCards from './Step0_CSPCards';
import Step1_TypeCards from './Step1_TypeCards';
import Step2_SystemConfig from './Step2_SystemConfig';
import Step3_GuideChecklist from './Step3_GuideChecklist';
import Step3_GuideChecklist_V2 from './Step3_GuideChecklist_V2';

// localStorage 키 — 사용자 선호하는 가이드 버전 영속화
const GUIDE_VERSION_KEY = 'ai-sherpa-guide-version';
type GuideVersion = 'v1' | 'v2';
const loadGuideVersion = (): GuideVersion => {
  try {
    const v = localStorage.getItem(GUIDE_VERSION_KEY);
    return v === 'v2' ? 'v2' : 'v1';
  } catch {
    return 'v1';
  }
};

const stepLabels = [
  { code: 'M0-0', title: '분석 환경 선택' },
  { code: 'M0-1', title: '사고 유형' },
  { code: 'M0-2', title: '시스템 구성' },
  { code: 'M0-3', title: '초동 수집 가이드' },
];

const V1Setup = () => {
  const navigate = useNavigate();
  const { csp, incidentType, setCsp, setIncidentType, setSeverity, setCaseId } = useCaseStore();
  const showToast = useToastStore((s) => s.show);
  const [step, setStep] = useState(0);
  const [guideVersion, setGuideVersion] = useState<GuideVersion>(loadGuideVersion);

  const switchGuideVersion = (v: GuideVersion) => {
    setGuideVersion(v);
    try {
      localStorage.setItem(GUIDE_VERSION_KEY, v);
    } catch {
      // localStorage 비활성 환경 — 메모리 상태만 유지
    }
  };

  const current = stepLabels[step];

  const createCaseMutation = useMutation({
    mutationFn: createCase,
    onSuccess: (data) => {
      setCaseId(data.caseId);
      setStep(3);
      showToast(`사고 케이스 생성: ${data.caseId.slice(0, 8)}…`);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`케이스 생성 실패: ${msg}`);
    },
  });

  return (
    <div>
      <PageHeader
        eyebrow={`Layer 0 · ${current.code}`}
        title={
          <>
            사고 접수 <span className="grad-text">워크플로</span>
          </>
        }
        description="CSP·사고 유형·시스템 구성을 입력하면 우선순위 기반 초동 수집 가이드를 자동 생성합니다."
        meta={
          <div className="flex items-center gap-3 flex-wrap">
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
                    {state === 'done' ? '✓' : i}
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
          <Step1_TypeCards
            selected={incidentType}
            csp={csp}
            onSelect={setIncidentType}
            onPrev={() => setStep(0)}
            onNext={() => setStep(2)}
          />
        )}
        {step === 2 && (
          <Step2_SystemConfig
            csp={csp}
            incidentType={incidentType}
            onPrev={() => setStep(1)}
            onSubmit={(config) => {
              if (!csp || !incidentType) {
                showToast('CSP·사고유형 누락. 이전 단계로 돌아가세요.');
                return;
              }
              setSeverity(config.severity);
              const occurredIso = (() => {
                const d = new Date(config.occurred_at);
                return Number.isNaN(d.getTime()) ? new Date().toISOString() : d.toISOString();
              })();
              createCaseMutation.mutate({
                incident_type: incidentType as IncidentType,
                csp: csp as CSP,
                severity: config.severity as Severity,
                occurred_at: occurredIso,
                system_config: {
                  vpc_id: config.vpc_id,
                  region: config.region,
                  services: config.services,
                  network: config.network,
                  publicIp: config.publicIp,
                  auditEnabled: config.auditEnabled,
                  scope: config.scope,
                  // dev2 v2 가이드 — environment_modifiers.json 트리거 필드
                  mfa_status: config.mfa_status,
                  iam_account_count: config.iam_account_count,
                  audit_log_retention_days: config.audit_log_retention_days,
                  data_sensitivity: config.data_sensitivity,
                  sso_enabled: config.sso_enabled,
                  multi_cloud: config.multi_cloud,
                },
              });
            }}
            isSubmitting={createCaseMutation.isPending}
          />
        )}
        {step === 3 && (
          <>
            {/* v1/v2 토글 — dev2 청사진 § 6.2 */}
            <div className="panel p-3 mb-3 flex items-center gap-2 flex-wrap">
              <span className="eyebrow text-[10.5px]">수집 가이드 버전</span>
              <button
                onClick={() => switchGuideVersion('v1')}
                className={
                  guideVersion === 'v1'
                    ? 'btn-primary btn-sm'
                    : 'btn-ghost btn-sm'
                }
              >
                기존 가이드 (v1)
              </button>
              <button
                onClick={() => switchGuideVersion('v2')}
                className={
                  guideVersion === 'v2'
                    ? 'btn-primary btn-sm'
                    : 'btn-ghost btn-sm'
                }
                title="외부 표준 6종(KISA·MITRE·NIST·ISO·Google·CSA) 기반 Kill Chain 매트릭스"
              >
                🆕 표준 기반 (v2)
              </button>
              <span className="ml-auto text-[10.5px] text-ink-400">
                {guideVersion === 'v2'
                  ? '/api/guide/v2 — 외부 표준 6종 + system_config 동적 보정'
                  : '/api/guide — 기존 시드 5건 단순 체크리스트'}
              </span>
            </div>

            {guideVersion === 'v2' ? (
              <Step3_GuideChecklist_V2
                onPrev={() => setStep(2)}
                onComplete={() => {
                  showToast('수집 가이드 (v2) 완료 → 로그 수집');
                  navigate('/logs');
                }}
              />
            ) : (
              <Step3_GuideChecklist
                csp={csp}
                incidentType={incidentType}
                onPrev={() => setStep(2)}
                onComplete={() => {
                  showToast('수집 가이드 완료 → 로그 수집');
                  navigate('/logs');
                }}
              />
            )}
          </>
        )}
      </PageBody>
    </div>
  );
};

export default V1Setup;
