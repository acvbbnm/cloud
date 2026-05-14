import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import Card from '@/components/Card';
import KpiCard from '@/components/KpiCard';
import Badge from '@/components/Badge';
import { useToastStore } from '@/stores/useToastStore';
import { useCaseStore } from '@/stores/useCaseStore';
import { useBoardStore } from '@/stores/useBoardStore';
import { uploadLogs, getLogs } from '@/api/logs';

import DropZone from './DropZone';
import EventPreviewTable from './EventPreviewTable';
import type { PreviewEvent } from './EventPreviewTable';
import type { RawEventItem } from '@/types';

const PAGE_SIZE = 20;

const cspLabel = (csp: string) =>
  csp === 'naver' ? 'NCP' : csp === 'nhn' ? 'NHN' : csp.toUpperCase();

const toPreview = (item: RawEventItem): PreviewEvent => ({
  id: item.eventId,
  ts: item.ingestedAt,
  ev: item.matchedTargetId ?? '(unmatched)',
  ip: '—', // list 응답엔 IP 없음. 단건 조회 시 raw.content.sourceIp 에서 가져올 수 있음
  user: '—',
  csp: cspLabel(item.csp),
  matched: item.matchedTargetId,
  highlighted: !!item.matchedTargetId,
});

const V2Logs = () => {
  const navigate = useNavigate();
  const showToast = useToastStore((s) => s.show);
  const caseId = useCaseStore((s) => s.caseId);
  const addLogs = useBoardStore((s) => s.addLogs);
  const queryClient = useQueryClient();

  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const logsQuery = useQuery({
    queryKey: ['logs', caseId, page],
    queryFn: () => getLogs(caseId!, page, PAGE_SIZE),
    enabled: !!caseId,
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadLogs(caseId!, file),
    onSuccess: (stats) => {
      showToast(
        `업로드 완료: ${stats.totalEvents}건 (matched ${stats.matched} / unmatched ${stats.unmatched})`,
      );
      queryClient.invalidateQueries({ queryKey: ['logs', caseId] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`업로드 실패: ${msg}`);
    },
  });

  const handleUpload = (files: File[]) => {
    if (!caseId) {
      showToast('케이스가 없습니다. 먼저 V-1에서 사고 케이스를 생성하세요.');
      return;
    }
    if (files.length > 1) {
      showToast(`${files.length}개 파일 중 첫 번째만 업로드합니다`);
    }
    uploadMutation.mutate(files[0]);
  };

  const events: PreviewEvent[] = (logsQuery.data?.items ?? []).map(toPreview);
  const totalEvents = logsQuery.data?.total ?? 0;
  const lastStats = uploadMutation.data;

  const toggleOne = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const toggleAll = (checked: boolean) =>
    setSelected(checked ? new Set(events.map((e) => e.id)) : new Set());

  const handleAddToBoard = () => {
    if (!selected.size) {
      showToast('선택된 로그가 없습니다');
      return;
    }
    const picked = events.filter((e) => selected.has(e.id));
    addLogs(picked.map((p) => ({ ts: p.ts, ev: p.ev, ip: p.ip, user: p.user, csp: p.csp })));
    showToast(`${picked.length}개 로그 수사 보드에 추가됨`);
    setSelected(new Set());
    navigate('/board');
  };

  // caseId 없으면 V-1로 유도
  if (!caseId) {
    return (
      <div>
        <PageHeader
          eyebrow="Layer 1 · M1-1"
          title="로그 수집"
          description="진행 중인 사고 케이스가 없습니다."
        />
        <PageBody>
          <Card title={<>⚠️ 케이스 없음</>}>
            <p className="text-[13px] text-ink-300 mb-3">
              V-1 사고 접수 위저드를 먼저 완료해야 로그를 업로드할 수 있습니다.
            </p>
            <button onClick={() => navigate('/setup')} className="btn-primary">
              ← V-1 사고 접수로 돌아가기
            </button>
          </Card>
        </PageBody>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(totalEvents / PAGE_SIZE));

  return (
    <div>
      <PageHeader
        eyebrow="Layer 1 · M1-1"
        title="로그 수집"
        description="CSP 로그 파일을 업로드하면 무결성(SHA-256) 검증 후 시드 카탈로그와 자동 매칭됩니다."
        actions={
          <>
            <button onClick={handleAddToBoard} className="btn-ghost">
              📌 수사 보드에 추가
            </button>
            <button onClick={() => navigate('/ocsf')} className="btn-primary">
              OCSF 정규화 →
            </button>
          </>
        }
      />

      <PageBody className="flex flex-col gap-6 animate-fade-up">
        {/* 백엔드 통신 상태 패널 */}
        <div className="panel p-4 border-l-[3px] border-l-brand-teal text-[12px]">
          <div className="flex items-center justify-between gap-2 mb-2">
            <div className="flex items-center gap-2">
              <span className="eyebrow">백엔드 응답</span>
              {logsQuery.isLoading && <span className="tag-blue">로딩 중…</span>}
              {logsQuery.isError && <span className="tag-red">에러</span>}
              {logsQuery.isSuccess && <span className="tag-teal">연결됨 ✓</span>}
              {uploadMutation.isPending && <span className="tag-amber">업로드 중…</span>}
            </div>
            <code className="text-ink-400 font-mono text-[10.5px]">caseId: {caseId}</code>
          </div>
          {logsQuery.isError && (
            <div className="text-brand-red text-[11.5px]">
              {(logsQuery.error as Error)?.message ?? '백엔드 호출 실패'}
            </div>
          )}
          {logsQuery.isSuccess && (
            <div className="text-ink-300 leading-6">
              raw_events 총 <b className="text-ink-100">{totalEvents}건</b>
              {lastStats && (
                <>
                  <span className="mx-2 text-ink-500">·</span>
                  마지막 업로드 <code className="text-ink-200">{lastStats.sourceFile}</code>: total{' '}
                  <b className="text-ink-100">{lastStats.totalEvents}</b> / matched{' '}
                  <b className="text-brand-teal">{lastStats.matched}</b> / unmatched{' '}
                  <b className="text-brand-amber">{lastStats.unmatched}</b>
                  <span className="mx-2 text-ink-500">·</span>
                  sha256 <code className="text-ink-400">{lastStats.sha256.slice(0, 16)}…</code>
                </>
              )}
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <KpiCard
            label="총 수집 이벤트"
            value={totalEvents.toLocaleString()}
            color="blue"
            hint="raw_events 적재 건수"
          />
          <KpiCard
            label="매칭 (마지막 업로드)"
            value={lastStats?.matched ?? '—'}
            color="teal"
            hint="시드 카탈로그 매칭"
          />
          <KpiCard
            label="미매칭 (마지막 업로드)"
            value={lastStats?.unmatched ?? '—'}
            color="amber"
            hint="시드 카탈로그 외 이벤트"
          />
          <KpiCard
            label="파일"
            value={lastStats?.sourceFile ? '1+' : '0'}
            color="purple"
            hint={lastStats?.sourceFile ?? '업로드 대기'}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          <div className="lg:col-span-3">
            <DropZone onUpload={handleUpload} />
          </div>
          <Card title={<>✅ 매칭 분포 (마지막 업로드)</>} className="lg:col-span-2">
            {lastStats ? (
              Object.keys(lastStats.byTarget).length === 0 ? (
                <div className="text-[12px] text-ink-400 py-4">매칭된 항목 없음</div>
              ) : (
                Object.entries(lastStats.byTarget)
                  .sort(([, a], [, b]) => b - a)
                  .map(([targetId, count]) => (
                    <div
                      key={targetId}
                      className="flex justify-between items-center py-2.5 border-b border-ink-700/30 last:border-b-0 text-[12.5px]"
                    >
                      <span className="font-mono text-[11.5px]">{targetId}</span>
                      <Badge tone="teal">{count}건</Badge>
                    </div>
                  ))
              )
            ) : (
              <div className="text-[12px] text-ink-400 py-4">
                파일을 업로드하면 매칭 분포가 표시됩니다.
              </div>
            )}
          </Card>
        </div>

        <Card
          title={
            <>
              📋 적재된 raw_events (page {page} / {totalPages})
            </>
          }
          subtitle="체크 후 '수사 보드에 추가' 버튼으로 보드로 보낼 수 있습니다"
          action={
            <span className="chip text-[11px]">
              <span className="text-brand-teal">{selected.size}</span>
              <span className="text-ink-400">/ {events.length} 선택</span>
            </span>
          }
        >
          <EventPreviewTable
            events={events}
            selected={selected}
            onToggle={toggleOne}
            onToggleAll={toggleAll}
          />
          {totalEvents > PAGE_SIZE && (
            <div className="flex justify-end gap-2 mt-3">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="btn-ghost btn-sm disabled:opacity-40"
              >
                ← 이전
              </button>
              <span className="self-center text-[11.5px] text-ink-400">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= totalPages}
                className="btn-ghost btn-sm disabled:opacity-40"
              >
                다음 →
              </button>
            </div>
          )}
        </Card>
      </PageBody>
    </div>
  );
};

export default V2Logs;
