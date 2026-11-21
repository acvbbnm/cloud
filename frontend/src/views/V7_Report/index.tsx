import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import Card from '@/components/Card';
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
  { key: 'overview', title: '사고 개요', emoji: '', rows: 4 },
  { key: 'timeline', title: '타임라인', emoji: '', rows: 8 },
  { key: 'impact', title: '영향 분석', emoji: '', rows: 4 },
  { key: 'attack_analysis', title: 'ATT&CK 결과', emoji: '', rows: 5 },
  { key: 'response', title: '대응 조치', emoji: '', rows: 4 },
  { key: 'recommendation', title: '권고사항', emoji: '', rows: 4 },
  { key: 'evidence', title: '주요 증거', emoji: '', rows: 6 },
  { key: 'comments', title: '수사관 코멘트', emoji: '', rows: 3 },
];

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

  // V1.fix.21 — "AI 초안 재생성" 버튼 제거. 초안 자동 생성 (mount 시 createReport)
  //   만으로 충분. 재생성 mutation 도 제거.

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

  // V1.fix.21 — "최종화" 버튼 제거. DOCX 다운로드로 외부 보고 흐름 종결.
  //   status='finalized' 전환은 V-8 사후 검증 등 별도 흐름에서 처리.

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
  // 시연 체크리스트  5 "V-7 dirty 추적 — 페이지 떠나기 전 미저장 변경 경고 없음" 대응
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
          title="사고 보고서"
          description="활성화된 사고 케이스가 없습니다."
        />
        <PageBody>
          <Card title={<>사고 케이스 없음</>}>
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
        title="사고 보고서"
        description="AI 보조 초안과 함께 KISA 양식 8섹션 보고서를 편집합니다. DOCX 내보내기 지원."
        meta={
          <div className="flex items-center gap-2 flex-wrap">
            {dirtyCount > 0 && (
              <span className="chip text-amber-400">미저장 {dirtyCount}건</span>
            )}
          </div>
        }
        actions={
          <>
            {/* V1.fix.21 — "AI 초안 재생성" 버튼 제거 (사용자 피드백). 초안은 1회
                자동 생성 후 사용자 편집·저장·DOCX 다운로드 흐름으로 충분. */}
            <button
              onClick={() => saveMutation.mutate()}
              disabled={
                isFinalized || dirtyCount === 0 || saveMutation.isPending
              }
              className="btn-ghost disabled:opacity-40"
            >
              {saveMutation.isPending ? '저장 중…' : ` 저장${dirtyCount > 0 ? ` (${dirtyCount})` : ''}`}
            </button>
            <button
              onClick={() => exportMutation.mutate()}
              disabled={!report || exportMutation.isPending}
              className="btn-primary disabled:opacity-40"
            >
              {exportMutation.isPending ? '다운로드 중…' : ' DOCX'}
            </button>
            {/* V1.fix.21 — "최종화" 버튼 제거 (사용자 피드백). DOCX 다운로드로 외부
                보고 흐름 종결. status='finalized' 상태 전환은 V-8 등 사후 검증
                과정에서 별도 처리. */}
          </>
        }
      />

      <PageBody className="animate-fade-up">
        {/* P.29 — 시연용 백엔드 응답 디버그 패널 제거.
            isFinalized 안내만 유지 (사용자 가이드 — 디버그 X 사용자 액션 컨텍스트). */}
        {isFinalized && (
          <div className="text-brand-teal text-[11.5px] mt-1 mb-4">
            최종화된 보고서입니다. 추가 편집 불가. DOCX 다운로드만 가능.
          </div>
        )}

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
                    isDirty ? (
                      <span className="text-[10px] text-amber-400"></span>
                    ) : undefined
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
