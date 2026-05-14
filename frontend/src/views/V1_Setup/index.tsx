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
                },
              });
            }}
            isSubmitting={createCaseMutation.isPending}
          />
        )}
        {step === 3 && (
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
      </PageBody>
    </div>
  );
};

export default V1Setup;
