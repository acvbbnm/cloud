import { useState } from 'react';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import Badge from '@/components/Badge';

import { useCaseStore } from '@/stores/useCaseStore';
import { useToastStore } from '@/stores/useToastStore';
import { getIncidentTypeValidation } from '@/api/sherpa';
import { updateCase } from '@/api/intake';

import type { IncidentType } from '@/types';

const INCIDENT_TYPE_KO: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '자격증명 탈취',
  PRIVILEGE_ESCALATION: '권한 상승',
  DATA_EXFILTRATION: '데이터 유출',
  AUDIT_LOG_TAMPERING: '감사 로그 변조',
  //  dev3 C-1 신규 4종 (MULTI_CSP_LATERAL 2026-05-19 제거) 
  RANSOMWARE: '랜섬웨어',
  MISCONFIG_EXPOSURE: '설정 오류 노출',
  PHISH_INITIAL_ACCESS: '피싱 초기 침투',
  INSIDER_THREAT: '내부자 위협',
  UNCLASSIFIED: '미분류',
};

interface Props {
  caseId: string;
}

/**
 * V-8 사후 검증 카드 — dev3 청사진 §3 V-8 IncidentTypeReviewCard.
 *
 * V-1 Step 2 Discovery Loop 에서 확정한 사고유형이 Layer 2 전체 매핑 결과와
 * 정합하는지 백엔드(`/api/sherpa/validate-incident-type`)가 평가.
 *
 * 동작:
 *   - status === 'CONSISTENT' → 카드 숨김 (정합 시 노이즈 X)
 *   - status === 'REVIEW_NEEDED' → 카드 표시 + candidate_types 리스트
 *   - 후보 클릭 → secondary_incident_types 에 추가 (이미 있으면 토글)
 *   - 후보를 메인으로 격상 → incident_type 변경 + 기존 메인은 secondary 로
 *
 * 학술 근거:
 *   AWS GuardDuty AttackSequence finding + Microsoft Defender XDR attack story
 *   — 단일 매핑이 아닌 복합 사고유형 패턴 인식.
 */
const IncidentTypeReviewCard = ({ caseId }: Props) => {
  const showToast = useToastStore((s) => s.show);
  const queryClient = useQueryClient();
  const storeIncidentType = useCaseStore((s) => s.incidentType);
  const storeSecondary = useCaseStore((s) => s.secondaryIncidentTypes);
  const setIncidentType = useCaseStore((s) => s.setIncidentType);
  const setSecondaryIncidentTypes = useCaseStore((s) => s.setSecondaryIncidentTypes);
  const [dismissed, setDismissed] = useState(false);

  const validateQuery = useQuery({
    queryKey: ['incident-type-validation', caseId],
    queryFn: () => getIncidentTypeValidation(caseId),
    enabled: !!caseId && !dismissed,
    staleTime: 30_000, // 30초 캐시 — V-2 분석 직후 빈번한 재호출 방지
    retry: false,
  });

  const patchMutation = useMutation({
    mutationFn: (data: {
      incident_type?: IncidentType;
      secondary_incident_types?: IncidentType[];
    }) => updateCase(caseId, data),
    onSuccess: (data) => {
      if (data.incident_type) setIncidentType(data.incident_type);
      if (data.secondary_incident_types !== undefined) {
        setSecondaryIncidentTypes(data.secondary_incident_types ?? []);
      }
      // validation 재호출 → 새 메인·부 사고유형 기반 재평가
      queryClient.invalidateQueries({ queryKey: ['incident-type-validation', caseId] });
      showToast('사고유형 갱신 완료');
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`사고유형 갱신 실패: ${msg}`);
    },
  });

  // 로딩·CONSISTENT·dismiss 시 렌더 X
  if (!caseId || dismissed) return null;
  if (validateQuery.isLoading || validateQuery.isError) return null;
  const v = validateQuery.data;
  if (!v || v.status !== 'REVIEW_NEEDED') return null;

  const currentMain = (storeIncidentType ?? v.current_incident_type) as IncidentType;
  const currentSecondary = storeSecondary ?? v.current_secondary ?? [];

  // candidate_types 중 이미 메인이거나 부에 있는 것은 마킹용
  const candidates = (v.candidate_types ?? []).filter(
    (c) => c.incident_type !== currentMain,
  );

  const handleAddSecondary = (type: IncidentType) => {
    if (currentSecondary.includes(type)) {
      // 이미 있으면 제거 (토글)
      const next = currentSecondary.filter((t) => t !== type);
      patchMutation.mutate({ secondary_incident_types: next });
    } else {
      patchMutation.mutate({
        secondary_incident_types: [...currentSecondary, type],
      });
    }
  };

  const handlePromoteToMain = (type: IncidentType) => {
    // 후보를 메인으로 격상 → 기존 메인은 secondary 로 강등
    const nextSecondary = [
      currentMain,
      ...currentSecondary.filter((t) => t !== type && t !== currentMain),
    ];
    patchMutation.mutate({
      incident_type: type,
      secondary_incident_types: nextSecondary,
    });
  };

  return (
    <div className="max-w-[1280px] mx-auto w-full px-8 lg:px-12 pt-3">
      <div className="panel p-4 border-l-[3px] border-l-amber-500/80 bg-amber-500/5 animate-fade-up">
        {/* 헤더 */}
        <div className="flex items-start gap-3 mb-3">
          <span className="text-[18px] leading-none mt-0.5"></span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="eyebrow text-[10.5px] text-amber-300">
                V-8 사후 검증 — 추가 검토 권장
              </span>
              <Badge tone="amber" size="sm">
                REVIEW_NEEDED
              </Badge>
            </div>
            <p className="text-[12px] text-ink-200 mt-1 leading-5">{v.message}</p>
          </div>
          <button
            onClick={() => setDismissed(true)}
            className="text-ink-500 hover:text-ink-300 text-[11px] shrink-0"
            title="이 세션에서 숨기기"
          >
            
          </button>
        </div>

        {/* 현재 사고유형 상태 */}
        <div className="text-[11.5px] text-ink-300 mb-3 flex items-center gap-2 flex-wrap">
          <span className="text-ink-500">현재:</span>
          <Badge tone="teal" size="sm">
            메인 · {INCIDENT_TYPE_KO[currentMain]}
          </Badge>
          {currentSecondary.map((t) => (
            <Badge key={t} tone="blue" size="sm">
              부 · {INCIDENT_TYPE_KO[t]}
            </Badge>
          ))}
        </div>

        {/* 추가 발견된 시그널 (extra_techniques) */}
        {v.extra_techniques.length > 0 && (
          <div className="mb-3">
            <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-1">
              Layer 2 추가 매핑 기법
            </div>
            <div className="flex flex-wrap gap-1.5">
              {v.extra_techniques.slice(0, 8).map((t) => (
                <code
                  key={t}
                  className="text-[10.5px] font-mono bg-ink-900 text-ink-200 px-2 py-0.5 rounded border border-ink-700/60"
                >
                  {t}
                </code>
              ))}
              {v.extra_techniques.length > 8 && (
                <span className="text-[10.5px] text-ink-500 self-center">
                  +{v.extra_techniques.length - 8}개
                </span>
              )}
            </div>
          </div>
        )}

        {/* 후보 사고유형 */}
        {candidates.length > 0 && (
          <div>
            <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-2">
              후보 사고유형
            </div>
            <div className="space-y-2">
              {candidates.map((c) => {
                const isSecondary = currentSecondary.includes(c.incident_type);
                return (
                  <div
                    key={c.incident_type}
                    className="bg-ink-950/60 border border-ink-700/60 rounded-lg p-3 flex items-start gap-3"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <b className="text-[12.5px] text-ink-100">
                          {INCIDENT_TYPE_KO[c.incident_type]}
                        </b>
                        <code className="text-[10.5px] text-ink-500">
                          {Math.round(c.score)}점
                        </code>
                        {isSecondary && (
                          <Badge tone="blue" size="sm">
                            현재 부 사고유형
                          </Badge>
                        )}
                      </div>
                      <p className="text-[10.5px] text-ink-400 leading-5 mt-1">
                        {c.reason}
                      </p>
                    </div>
                    <div className="flex flex-col gap-1.5 shrink-0">
                      <button
                        onClick={() => handleAddSecondary(c.incident_type)}
                        disabled={patchMutation.isPending}
                        className="btn-ghost btn-sm whitespace-nowrap disabled:opacity-40"
                      >
                        {isSecondary ? '부 사고유형 해제' : '+ 부 사고유형'}
                      </button>
                      <button
                        onClick={() => handlePromoteToMain(c.incident_type)}
                        disabled={patchMutation.isPending}
                        className="btn-primary btn-sm whitespace-nowrap disabled:opacity-40"
                      >
                        메인으로 격상
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <p className="text-[10.5px] text-ink-500 mt-3 leading-5">
           AI 제안 — 결정은 수사관. 부 사고유형 등록 시 보고서·가이드가 자동 보강됩니다.
        </p>
      </div>
    </div>
  );
};

export default IncidentTypeReviewCard;
