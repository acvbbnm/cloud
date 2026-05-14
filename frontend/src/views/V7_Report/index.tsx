import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import Card from '@/components/Card';
import Badge from '@/components/Badge';
import { useToastStore } from '@/stores/useToastStore';
import { useCaseStore } from '@/stores/useCaseStore';
import {
  createReport,
  patchReport,
  downloadReportDocx,
} from '@/api/report';
import type { ReportResponse, ReportSections } from '@/types';

interface SectionMeta {
  key: keyof ReportSections;
  title: string;
  emoji: string;
  rows: number;
}

const SECTIONS: SectionMeta[] = [
  { key: 'overview', title: '사고 개요', emoji: '📌', rows: 4 },
  { key: 'timeline', title: '타임라인', emoji: '⏱', rows: 8 },
  { key: 'impact', title: '영향 분석', emoji: '💥', rows: 4 },
  { key: 'attack_analysis', title: 'ATT&CK 결과', emoji: '🎯', rows: 5 },
  { key: 'response', title: '대응 조치', emoji: '🛡', rows: 4 },
  { key: 'recommendation', title: '권고사항', emoji: '💡', rows: 4 },
  { key: 'evidence', title: '주요 증거', emoji: '📁', rows: 6 },
  { key: 'comments', title: '수사관 코멘트', emoji: '🗒', rows: 3 },
];

const STATUS_TONE: Record<string, 'red' | 'amber' | 'teal' | 'blue' | 'purple' | 'gray'> = {
  draft: 'blue',
  edited: 'amber',
  finalized: 'teal',
};

const V7Report = () => {
  const navigate = useNavigate();
  const showToast = useToastStore((s) => s.show);
  const caseId = useCaseStore((s) => s.caseId);
  const queryClient = useQueryClient();

  // 로컬 편집 상태 (서버 응답으로 초기화, 저장 시 PATCH 일괄 반영)
  const [draftSections, setDraftSections] = useState<Partial<ReportSections>>({});
  const [dirty, setDirty] = useState<Set<keyof ReportSections>>(new Set());

  // 보고서 조회/초기 생성 — createReport(regenerate=false) 는 멱등이라 useQuery 로 사용
  const reportQuery = useQuery({
    queryKey: ['report', caseId],
    queryFn: () => createReport({ caseId: caseId!, regenerate: false }),
    enabled: !!caseId,
    staleTime: 30_000,
  });

  // 서버 응답이 바뀌면 로컬 편집 상태를 동기화 (단 dirty 한 필드는 보존)
  useEffect(() => {
    if (reportQuery.data) {
      setDraftSections((prev) => {
        const next: Partial<ReportSections> = {};
        for (const s of SECTIONS) {
          next[s.key] = dirty.has(s.key)
            ? (prev[s.key] ?? reportQuery.data!.sections[s.key])
            : reportQuery.data!.sections[s.key];
        }
        return next;
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportQuery.data]);

  const regenerateMutation = useMutation({
    mutationFn: () => createReport({ caseId: caseId!, regenerate: true }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['report', caseId], updated);
      setDirty(new Set());
      showToast('AI 초안 재생성 완료');
    },
    onError: (err: unknown) => {
      showToast(
        `재생성 실패: ${err instanceof Error ? err.message : String(err)}`,
      );
    },
  });

  const saveMutation = useMutation({
    mutationFn: () => {
      const sections: Partial<ReportSections> = {};
      for (const k of dirty) {
        sections[k] = draftSections[k] ?? '';
      }
      return patchReport(caseId!, { sections });
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(['report', caseId], updated);
      setDirty(new Set());
      showToast(`저장 완료 (status: ${updated.status})`);
    },
    onError: (err: unknown) => {
      showToast(`저장 실패: ${err instanceof Error ? err.message : String(err)}`);
    },
  });

  const finalizeMutation = useMutation({
    mutationFn: () => patchReport(caseId!, { status: 'finalized' }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['report', caseId], updated);
      showToast('보고서 최종화 완료 (FINALIZE_REPORT 적재)');
    },
    onError: (err: unknown) => {
      showToast(
        `최종화 실패: ${err instanceof Error ? err.message : String(err)}`,
      );
    },
  });

  const exportMutation = useMutation({
    mutationFn: () => downloadReportDocx(caseId!),
    onSuccess: () => showToast('DOCX 다운로드 완료 (EXPORT_REPORT 적재)'),
    onError: (err: unknown) => {
      showToast(
        `다운로드 실패: ${err instanceof Error ? err.message : String(err)}`,
      );
    },
  });

  // 미저장 변경이 있을 때 페이지 떠나기 경고 (탭 닫기·새로고침·뒤로가기)
  // 시연 체크리스트 § 5 "V-7 dirty 추적 — 페이지 떠나기 전 미저장 변경 경고 없음" 대응
  useEffect(() => {
    if (dirty.size === 0) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // Chrome 등 일부 브라우저는 returnValue 가 비어있지 않아야 confirm 다이얼로그 표시
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty.size]);

  if (!caseId) {
    return (
      <div>
        <PageHeader
          eyebrow="Layer 4 · M4-2"
          title="보고서 생성"
          description="진행 중인 사고 케이스가 없습니다."
        />
        <PageBody>
          <Card title={<>⚠️ 케이스 없음</>}>
            <p className="text-[13px] text-ink-300 mb-3">
              V-1 사고 접수 위저드를 먼저 완료해야 보고서를 생성할 수 있습니다.
            </p>
            <button onClick={() => navigate('/setup')} className="btn-primary">
              ← V-1 사고 접수로 돌아가기
            </button>
          </Card>
        </PageBody>
      </div>
    );
  }

  const report: ReportResponse | undefined = reportQuery.data;
  const status = report?.status ?? 'draft';
  const isFinalized = status === 'finalized';
  const dirtyCount = dirty.size;
  const totalChars = SECTIONS.reduce(
    (n, s) => n + (draftSections[s.key]?.length ?? 0),
    0,
  );

  const handleChange = (k: keyof ReportSections, v: string) => {
    setDraftSections((p) => ({ ...p, [k]: v }));
    setDirty((p) => {
      const ns = new Set(p);
      ns.add(k);
      return ns;
    });
  };

  return (
    <div>
      <PageHeader
        eyebrow="Layer 4 · M4-2"
        title={
          <>
            보고서 <span className="grad-text">생성</span>
          </>
        }
        description="KISA 양식 8 섹션을 편집하고 AI 초안을 활용해 사고 보고서를 완성합니다. DOCX 내보내기 지원."
        meta={
          <div className="flex items-center gap-2 flex-wrap">
            <Badge tone={STATUS_TONE[status] ?? 'gray'}>{status}</Badge>
            <span className="chip">{totalChars.toLocaleString()} chars</span>
            {dirtyCount > 0 && (
              <span className="chip text-amber-400">미저장 {dirtyCount}건</span>
            )}
            <code className="text-ink-400 font-mono text-[10.5px]">
              caseId: {caseId}
            </code>
          </div>
        }
        actions={
          <>
            <button
              onClick={() => regenerateMutation.mutate()}
              disabled={
                isFinalized ||
                regenerateMutation.isPending ||
                reportQuery.isLoading
              }
              className="btn-ghost disabled:opacity-40"
              title="ATT&CK 매핑·갭·로그 데이터로 8섹션을 다시 생성"
            >
              {regenerateMutation.isPending ? '생성 중…' : '🧠 AI 초안 재생성'}
            </button>
            <button
              onClick={() => saveMutation.mutate()}
              disabled={
                isFinalized || dirtyCount === 0 || saveMutation.isPending
              }
              className="btn-ghost disabled:opacity-40"
            >
              {saveMutation.isPending ? '저장 중…' : `💾 저장${dirtyCount > 0 ? ` (${dirtyCount})` : ''}`}
            </button>
            <button
              onClick={() => exportMutation.mutate()}
              disabled={!report || exportMutation.isPending}
              className="btn-ghost disabled:opacity-40"
            >
              {exportMutation.isPending ? '다운로드 중…' : '📝 DOCX'}
            </button>
            <button
              onClick={() => finalizeMutation.mutate()}
              disabled={
                !report || isFinalized || finalizeMutation.isPending || dirtyCount > 0
              }
              className="btn-primary disabled:opacity-40"
              title={dirtyCount > 0 ? '미저장 변경이 있습니다. 저장 후 최종화하세요.' : ''}
            >
              {finalizeMutation.isPending ? '최종화 중…' : '✅ 최종화'}
            </button>
          </>
        }
      />

      <PageBody className="animate-fade-up">
        {/* 백엔드 응답 패널 */}
        <div className="panel p-4 border-l-[3px] border-l-brand-teal text-[12px] mb-4">
          <div className="flex items-center justify-between gap-2 mb-1 flex-wrap">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="eyebrow">백엔드 응답</span>
              {reportQuery.isLoading && (
                <span className="tag-blue">report 로딩…</span>
              )}
              {reportQuery.isError && (
                <span className="tag-red">report 에러</span>
              )}
              {reportQuery.isSuccess && <span className="tag-teal">report ✓</span>}
              {regenerateMutation.isPending && (
                <span className="tag-amber">AI 초안 생성 중…</span>
              )}
              {saveMutation.isPending && (
                <span className="tag-amber">PATCH 중…</span>
              )}
              {finalizeMutation.isPending && (
                <span className="tag-amber">FINALIZE 중…</span>
              )}
              {exportMutation.isPending && (
                <span className="tag-amber">DOCX 다운로드 중…</span>
              )}
            </div>
          </div>
          <div className="text-ink-300 leading-6">
            보고서 상태{' '}
            <b className="text-ink-100">{status}</b>
            {report?.created_at && (
              <>
                {' '}· 생성{' '}
                <code className="text-ink-400 font-mono text-[10.5px]">
                  {report.created_at.slice(0, 19).replace('T', ' ')}
                </code>
              </>
            )}
            {' '}· 8섹션{' '}
            <b className="text-ink-100">{totalChars.toLocaleString()}</b>
            {' '}chars
            {dirtyCount > 0 && (
              <>
                {' '}·{' '}
                <span className="text-amber-400">
                  미저장 {Array.from(dirty).join(', ')}
                </span>
              </>
            )}
          </div>
          {reportQuery.isError && (
            <div className="text-brand-red text-[11.5px] mt-1">
              {(reportQuery.error as Error)?.message ?? 'report 호출 실패'}
            </div>
          )}
          {isFinalized && (
            <div className="text-brand-teal text-[11.5px] mt-1">
              ✓ 최종화된 보고서입니다. 추가 편집 불가. DOCX 다운로드만 가능.
            </div>
          )}
        </div>

        {reportQuery.isLoading && !report ? (
          <div className="panel p-8 text-center text-ink-400 text-[13px]">
            보고서 초기 생성 중… (POST /api/report)
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {SECTIONS.map((s, i) => {
              const value = draftSections[s.key] ?? '';
              const isDirty = dirty.has(s.key);
              return (
                <Card
                  key={s.key}
                  title={
                    <>
                      <span className="w-6 h-6 rounded-lg bg-cta-gradient text-white text-[11px] font-bold flex items-center justify-center">
                        {i + 1}
                      </span>
                      <span>
                        {s.emoji} {s.title}
                      </span>
                    </>
                  }
                  action={
                    <div className="flex items-center gap-1.5">
                      {isDirty && (
                        <span className="text-[10px] text-amber-400">●</span>
                      )}
                      <span className="chip text-[10px]">
                        {value.length.toLocaleString()} chars
                      </span>
                    </div>
                  }
                >
                  <textarea
                    value={value}
                    onChange={(e) => handleChange(s.key, e.target.value)}
                    rows={s.rows}
                    readOnly={isFinalized}
                    className={`input resize-y font-mono leading-7 ${
                      isFinalized ? 'opacity-70 cursor-not-allowed' : ''
                    }`}
                    placeholder={isFinalized ? '' : `${s.title} 내용 입력…`}
                  />
                </Card>
              );
            })}
          </div>
        )}
      </PageBody>
    </div>
  );
};

export default V7Report;
