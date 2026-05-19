/**
 * V-8 사후 검증 카드 (dev3 청사진 §원칙 5)
 *
 * Layer 2 ATT&CK 매핑 결과를 분석해 "V-1 Step 2 에서 확정한 사고유형 외에
 * 추가로 발견된 사고유형" 을 제안한다. 수사관이 채택하면 PATCH /api/cases 로
 * secondary_incident_types 영속화.
 *
 * 결정성 100% — LLM 사용 안 함, 정적 (tactic → incident_type) 매핑.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import Card from '@/components/Card';
import Badge from '@/components/Badge';

import { postVerifyIncidentTypes } from '@/api/sherpa';
import { patchCase, getCase } from '@/api/intake';
import { useToastStore } from '@/stores/useToastStore';

const INCIDENT_TYPE_LABEL: Record<string, string> = {
  CREDENTIAL_THEFT: '🔑 자격증명 탈취',
  PRIVILEGE_ESCALATION: '⬆ 권한 상승',
  DATA_EXFILTRATION: '📤 데이터 유출',
  AUDIT_LOG_TAMPERING: '🗑 감사로그 변조',
  MULTI_CSP_LATERAL: '🔀 멀티 CSP 횡적이동',
  UNCLASSIFIED: '❓ 미분류',
};

interface Props {
  caseId: string;
}

const PostHocVerificationCard = ({ caseId }: Props) => {
  const showToast = useToastStore((s) => s.show);
  const queryClient = useQueryClient();

  // 현재 케이스 (confirmed + secondary 표시용)
  const caseQuery = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => getCase(caseId),
    enabled: !!caseId,
    staleTime: 10_000,
  });

  // 사후 검증 — 사용자가 버튼 누르면 수행 (또는 자동 1회)
  const verifyMutation = useMutation({
    mutationFn: () => postVerifyIncidentTypes(caseId),
    onError: (err) => {
      showToast(`사후 검증 실패: ${(err as Error).message}`);
    },
  });

  // secondary 채택 PATCH
  const acceptMutation = useMutation({
    mutationFn: (secondary: string[]) =>
      patchCase(caseId, { secondary_incident_types: secondary }),
    onSuccess: () => {
      showToast('✓ 부가 사고유형 영속화 완료');
      queryClient.invalidateQueries({ queryKey: ['case', caseId] });
    },
    onError: (err) => showToast(`PATCH 실패: ${(err as Error).message}`),
  });

  const result = verifyMutation.data;
  const caseData = caseQuery.data;
  const existingSecondary = caseData?.secondary_incident_types || [];

  // 자동 1회 실행 (caseId 있고 attack_events 존재할 경우)
  // 의도적으로 useEffect 안 씀 — 사용자가 명시적으로 누르도록 유도

  return (
    <Card
      title={
        <>
          🔍 V-8 사후 검증
          <span className="ml-1 chip text-[10px]">dev3 §원칙 5</span>
        </>
      }
    >
      <div className="text-[12px] text-ink-300 leading-6 space-y-3">
        <p className="text-ink-400 text-[11.5px]">
          V-1 에서 확정한 사고유형 외에 Layer 2 매핑에서 발견된 추가 사고유형을 제안합니다.
          정적 (tactic → incident_type) 매핑 — LLM 미사용, 결정성 100%.
        </p>

        {!verifyMutation.data && (
          <button
            onClick={() => verifyMutation.mutate()}
            disabled={verifyMutation.isPending}
            className="btn-primary text-[11.5px] w-full disabled:opacity-50"
          >
            {verifyMutation.isPending ? '분석 중…' : '🔬 사후 검증 실행'}
          </button>
        )}

        {result && (
          <>
            <div className="bg-ink-950 border border-ink-700/70 rounded-lg px-3 py-2 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-ink-400 text-[10.5px]">V-1 확정</span>
                <Badge tone="teal" size="sm">
                  {INCIDENT_TYPE_LABEL[result.confirmed] || result.confirmed}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-400 text-[10.5px]">분석 attack_events</span>
                <span className="font-mono text-ink-200">{result.total_attacks}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-400 text-[10.5px]">제안 임계값</span>
                <span className="font-mono text-ink-400">≥ {result.threshold}</span>
              </div>
            </div>

            <div>
              <div className="text-[11px] text-ink-300 mb-1.5 font-semibold">📊 사고유형별 점수</div>
              <div className="space-y-1">
                {Object.entries(result.scores)
                  .sort(([, a], [, b]) => b - a)
                  .map(([type, score]) => {
                    const isConfirmed = type === result.confirmed;
                    const isSuggested = result.suggested_secondary.includes(type);
                    const cnt = result.evidence_count[type] || 0;
                    return (
                      <div
                        key={type}
                        className={`flex items-center justify-between px-2 py-1 rounded text-[11px] ${
                          isSuggested
                            ? 'bg-amber-500/10 border border-amber-500/40'
                            : isConfirmed
                            ? 'bg-brand-teal/10 border border-brand-teal/40'
                            : 'bg-ink-950'
                        }`}
                      >
                        <span className="text-ink-200">
                          {isSuggested && '★ '}
                          {isConfirmed && '✓ '}
                          {INCIDENT_TYPE_LABEL[type] || type}
                        </span>
                        <span className="font-mono text-ink-300">
                          {score.toFixed(1)} <span className="text-ink-500">({cnt})</span>
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>

            {result.suggested_secondary.length > 0 ? (
              <div className="border-t border-ink-700/40 pt-3 space-y-2">
                <div className="text-[11.5px] text-amber-400 leading-5">
                  ★ Layer 2 매핑에서 추가 사고유형 증거 <b>{result.suggested_secondary.length}</b>건
                  발견됨. 채택 시 케이스의 <code className="text-[10px]">secondary_incident_types</code>{' '}
                  에 영속화됩니다.
                </div>
                <div className="flex flex-wrap gap-1">
                  {result.suggested_secondary.map((t) => (
                    <Badge key={t} tone="amber" size="sm">
                      {INCIDENT_TYPE_LABEL[t] || t}
                    </Badge>
                  ))}
                </div>
                <button
                  onClick={() => acceptMutation.mutate(result.suggested_secondary)}
                  disabled={
                    acceptMutation.isPending ||
                    JSON.stringify(existingSecondary.sort()) ===
                      JSON.stringify([...result.suggested_secondary].sort())
                  }
                  className="btn-primary text-[11px] w-full disabled:opacity-50"
                >
                  {acceptMutation.isPending
                    ? '저장 중…'
                    : JSON.stringify(existingSecondary.sort()) ===
                      JSON.stringify([...result.suggested_secondary].sort())
                    ? '✓ 이미 채택됨'
                    : '+ 부가 사고유형으로 채택'}
                </button>
                {existingSecondary.length > 0 && (
                  <div className="text-[10.5px] text-ink-400">
                    현재 케이스 secondary: {existingSecondary.join(', ')}
                  </div>
                )}
                {result.samples.length > 0 && (
                  <details className="text-[10.5px] text-ink-400">
                    <summary className="cursor-pointer hover:text-ink-200">
                      대표 증거 {result.samples.length}건 보기
                    </summary>
                    <div className="mt-2 space-y-1 font-mono text-[10px]">
                      {result.samples.map((s, i) => (
                        <div key={i} className="border-l-2 border-amber-500/40 pl-2">
                          <span className="text-amber-400">{s.incident_type}</span> |{' '}
                          {s.technique_id} ({s.tactic}) · {s.rule_id}
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            ) : (
              <div className="text-[11px] text-brand-teal/90 border-t border-ink-700/40 pt-2">
                ✓ V-1 확정 사고유형과 정합. 추가 사고유형 제안 없음.
              </div>
            )}

            <button
              onClick={() => verifyMutation.mutate()}
              disabled={verifyMutation.isPending}
              className="text-[10.5px] text-ink-400 hover:text-ink-200 underline w-full text-center"
            >
              ↻ 재분석
            </button>
          </>
        )}
      </div>
    </Card>
  );
};

export default PostHocVerificationCard;
