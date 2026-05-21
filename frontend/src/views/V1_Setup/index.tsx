import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useMutation } from '@tanstack/react-query';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import { useCaseStore } from '@/stores/useCaseStore';
import { useToastStore } from '@/stores/useToastStore';
import { createCase, updateCase } from '@/api/intake';
import type { CSP, IncidentType, Severity } from '@/types';

import Step0_CSPCards from './Step0_CSPCards';
import Step1_CaseMetadata from './Step1_CaseMetadata';
import Step2_Discovery from './Step2_Discovery';
import Step3_GuideChecklist_V2 from './Step3_GuideChecklist_V2';

// v1 수집 가이드는 2026-05-18 회의 결정에 따라 폐기 — V2 가 유일 화면.

const stepLabels = [
  { code: 'M0-0', title: '분석 환경 선택' },
  // dev3: 사고유형 5장 카드 폐기 — 케이스 메타 (Title/시각/Severity/TLP) 입력
  { code: 'M0-1', title: '케이스 메타' },
  { code: 'M0-2', title: '시스템 구성' },
  { code: 'M0-3', title: '초동 수집 가이드' },
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
  const [step, setStep] = useState(0);
  // dev3: occurred_at 은 Step 1 종료 시점에 createCase 로 곧장 전송 — 임시 보관 불필요.

  const current = stepLabels[step];

  // dev3 (2026-05-19): Step 1 종료 시점에 UNCLASSIFIED 빈 케이스 생성 → caseId 부여
  // → Step 2 Discovery Loop 가 caseId 기반으로 startTriage / 트리 진행 가능
  const initCaseMutation = useMutation({
    mutationFn: createCase,
    onSuccess: (data) => {
      setCaseId(data.caseId);
      setStep(2);
      showToast(`케이스 생성: ${data.caseId.slice(0, 8)}… (Discovery Loop 진입)`);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`케이스 생성 실패: ${msg} (백엔드 실행 확인)`);
    },
  });

  // dev3: Step 2 종료 시점 — system_config·incident_type 갱신 후 Step 3 진입
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
      setStep(3);
      showToast(`사고유형 확정: ${data.incident_type}`);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`사고유형 갱신 실패: ${msg}`);
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
          <Step1_CaseMetadata
            onPrev={() => setStep(0)}
            onNext={(occurredAt) => {
              if (!csp) {
                showToast('CSP 누락. Step 0 으로 돌아가세요.');
                return;
              }
              // dev3 (2026-05-19): Step 1 종료 → UNCLASSIFIED 빈 케이스 즉시 생성
              // → caseId 확보 → Step 2 Discovery Loop 의 startTriage 가 작동
              const occurredIso = (() => {
                const d = new Date(occurredAt);
                return Number.isNaN(d.getTime()) ? new Date().toISOString() : d.toISOString();
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
          <Step2_Discovery
            csp={csp}
            incidentType={incidentType}
            onPrev={() => setStep(1)}
            onSubmit={(config, confirmedIncidentType) => {
              if (!caseId) {
                showToast('caseId 누락. Step 1 으로 돌아가 케이스를 생성하세요.');
                return;
              }
              setSeverity(config.severity);
              // dev3: PATCH /api/cases/{caseId} — Discovery Loop 결과 통합 갱신
              // incident_type 은 Step 2 결정 트리에서 확정된 값 (UNCLASSIFIED 가능)
              finalizeCaseMutation.mutate({
                caseId,
                data: {
                  incident_type: confirmedIncidentType as IncidentType,
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
            isSubmitting={finalizeCaseMutation.isPending}
          />
        )}
        {step === 3 && (
          <Step3_GuideChecklist_V2
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
