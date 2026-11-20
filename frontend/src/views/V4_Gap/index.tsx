import { useNavigate } from 'react-router-dom';

import { useMutation } from '@tanstack/react-query';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import Card from '@/components/Card';
import Badge from '@/components/Badge';
import { useToastStore } from '@/stores/useToastStore';
import { useCaseStore } from '@/stores/useCaseStore';
import { runGap } from '@/api/analysis';

import CompletenessKpi from './CompletenessKpi';
import type { GapType } from '@/types';

// gap_type 메타
const GAP_META: Record<
  GapType,
  { label: string; color: string; bg: string; icon: string; cta: 'board' | 'setup' | 'sherpa' | null }
> = {
  NONE: {
    label: '갭 없음',
    color: 'text-brand-teal',
    bg: 'border-brand-teal/40 bg-brand-teal/[0.04]',
    icon: '✅',
    cta: 'board',
  },
  COLLECTION: {
    label: '수집 갭',
    color: 'text-brand-red',
    bg: 'border-brand-red/40 bg-brand-red/[0.04]',
    icon: '⛔',
    cta: 'setup',
  },
  EVIDENCE: {
    label: '증거 갭',
    color: 'text-brand-amber',
    bg: 'border-brand-amber/40 bg-brand-amber/[0.04]',
    icon: '⚠️',
    cta: null,
  },
  INTERPRETATION: {
    label: '해석 갭',
    color: 'text-brand-purple',
    bg: 'border-brand-purple/40 bg-brand-purple/[0.04]',
    icon: '🤖',
    cta: 'sherpa',
  },
};

const V4Gap = () => {
  const navigate = useNavigate();
  const showToast = useToastStore((s) => s.show);
  const caseId = useCaseStore((s) => s.caseId);

  const gapMutation = useMutation({
    mutationFn: () => runGap(caseId!),
    onSuccess: (data) => {
      showToast(`빠진 증거: ${data.gap_type} (완료율 ${data.completionRate}%)`);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`빠진 증거 실패: ${msg}`);
    },
  });

  if (!caseId) {
    return (
      <div>
        <PageHeader eyebrow="Layer 2 · M2-2" title="빠진 증거" description="진행 중인 사고 케이스가 없습니다." />
        <PageBody>
          <Card title={<>⚠️ 케이스 없음</>}>
            <p className="text-[13px] text-ink-300 mb-3">먼저 사고를 등록하세요.</p>
            <button onClick={() => navigate('/setup')} className="btn-primary">
              ← V-1 사고 접수
            </button>
          </Card>
        </PageBody>
      </div>
    );
  }

  const result = gapMutation.data;
  const meta = result ? GAP_META[result.gap_type] : null;

  return (
    <div>
      <PageHeader
        eyebrow="Layer 2 · M2-2"
        title="빠진 증거"
        description="수집 목록과 분석 결과를 대조해 빠진 증거를 찾습니다."
        actions={
          <>
            <button
              onClick={() => gapMutation.mutate()}
              disabled={gapMutation.isPending}
              className="btn-ghost disabled:opacity-50"
            >
              {gapMutation.isPending ? '판정 중…' : '🔁 빠진 증거 실행'}
            </button>
            {result?.gap_type === 'COLLECTION' && (
              <button
                onClick={() => {
                  showToast('Layer 0 복귀: 추가 로그 수집');
                  navigate('/setup');
                }}
                className="btn-danger"
              >
                ↩ Layer 0 복귀
              </button>
            )}
            {result?.gap_type === 'NONE' && (
              <button
                onClick={() => {
                  showToast('조사 보드 열기');
                  navigate('/board');
                }}
                className="btn-primary"
              >
                조사 보드 →
              </button>
            )}
            {result?.gap_type === 'INTERPRETATION' && (
              <button
                onClick={() => {
                  showToast('AI 셰르파 브리핑');
                  navigate('/sherpa');
                }}
                className="btn-primary"
              >
                AI 셰르파 →
              </button>
            )}
          </>
        }
      />

      <PageBody className="flex flex-col gap-6 animate-fade-up">
        {/* 백엔드 통신 상태 패널 */}
        <div className="panel p-4 border-l-[3px] border-l-brand-teal text-[12px]">
          <div className="flex items-center justify-between gap-2 mb-2">
            <div className="flex items-center gap-2">
              <span className="eyebrow">백엔드 응답</span>
              {!gapMutation.data && !gapMutation.isPending && (
                <span className="tag-gray">실행 대기</span>
              )}
              {gapMutation.isPending && <span className="tag-amber">판정 중…</span>}
              {gapMutation.isError && <span className="tag-red">에러</span>}
              {gapMutation.isSuccess && <span className="tag-teal">연결됨 ✓</span>}
            </div>
            <code className="text-ink-400 font-mono text-[10.5px]">caseId: {caseId}</code>
          </div>
          {gapMutation.isError && (
            <div className="text-brand-red text-[11.5px]">
              {(gapMutation.error as Error)?.message ?? '백엔드 호출 실패'}
            </div>
          )}
          {!gapMutation.data && !gapMutation.isPending && (
            <div className="text-ink-300 leading-6">
              우상단 「빠진 증거 실행」 버튼을 누르면 POST <code>/api/analysis/gap</code> 으로 판정합니다.
              실행 전에 V-3 에서 정규화 + ATT&CK 매핑이 끝나있어야 정확한 결과가 나옵니다.
            </div>
          )}
          {result && (
            <div className="text-ink-300 leading-6">
              gap_id <code className="text-ink-200">{result.gap_id.slice(0, 8)}…</code>{' '}
              · 판정 시각 {new Date(result.created_at).toLocaleString()}
            </div>
          )}
        </div>

        {/* 결과 없음 — 초기 상태 */}
        {!result && !gapMutation.isPending && (
          <Card title={<>증거 확인 전</>}>
            <p className="text-[13px] text-ink-400">
              상단의 「빠진 증거 실행」을 눌러 케이스의 증거 완결성을 분석해주세요.
            </p>
          </Card>
        )}

        {/* 결과 표시 */}
        {result && meta && (
          <>
            <div className={`panel p-6 border-l-[4px] ${meta.bg} ${meta.color.replace('text-', 'border-l-')}`}>
              <div className="flex items-center gap-3 mb-2">
                <span className="text-[28px]">{meta.icon}</span>
                <div>
                  <div className="eyebrow">판정 결과 — gap_type</div>
                  <div className={`text-[24px] font-extrabold ${meta.color}`}>
                    {result.gap_type} — {meta.label}
                  </div>
                </div>
              </div>
              <p className="text-[13px] text-ink-200 leading-7 mt-3">{result.summary}</p>
              <div className="mt-3 pt-3 border-t border-ink-700/40">
                <span className="eyebrow block mb-1">권장 행동</span>
                <p className="text-[12.5px] text-ink-100 font-medium">{result.recommendation}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <CompletenessKpi
                rate={result.completionRate}
                label={
                  result.completionRate === 100
                    ? '완전 수집'
                    : result.completionRate >= 60
                    ? '수집 빠진 증거'
                    : '필수 증거 부족'
                }
              />

              <div className="lg:col-span-2">
                <Card
                  title={
                    <>
                      ⛔ 미수집 필수 증거 — {result.missing.length}건
                    </>
                  }
                  borderColor="#FF4D6D"
                >
                  {result.missing.length === 0 ? (
                    <p className="text-[13px] text-ink-300">필수 증거가 모두 확보되었습니다.</p>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {result.missing.map((m) => (
                        <div
                          key={m.target_id}
                          className="flex items-center justify-between gap-3 py-2 border-b border-ink-700/30 last:border-b-0"
                        >
                          <div className="flex-1 min-w-0">
                            <div className="font-mono text-[11.5px] text-ink-200">{m.target_id}</div>
                            <div className="text-[12.5px] text-ink-100 mt-0.5">{m.log_type}</div>
                          </div>
                          <div className="flex gap-1.5 shrink-0">
                            <Badge role={m.evidence_role} size="sm" />
                            <Badge tone="amber">P{m.priority}</Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              </div>
            </div>
          </>
        )}
      </PageBody>
    </div>
  );
};

export default V4Gap;
