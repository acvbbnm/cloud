import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import Card from '@/components/Card';
import KpiCard from '@/components/KpiCard';
import Pagination from '@/components/Pagination';
import { useToastStore } from '@/stores/useToastStore';
import { useCaseStore } from '@/stores/useCaseStore';
import { getOcsf, runNormalize } from '@/api/analysis';

import RawJsonPanel from './RawJsonPanel';
import FieldMappingTable from './FieldMappingTable';
import type { MappingRow } from './FieldMappingTable';

const PAGE_SIZE = 30;

// 시드 mapping_rules/{ncp_cloudtrail,nhn_cloud_trail}.json 의 핵심 매핑을 정리한 정적 참조
const mappings: MappingRow[] = [
  { source: 'eventTime / timestamp', target: 'time', rule: 'unix ms / ISO8601 / UTC 문자열 자동 감지' },
  { source: 'action (NCP) / eventId (NHN)', target: 'activity_name', rule: '직접 매핑' },
  { source: 'actionResultType / result', target: 'status_code', rule: 'SUCCESS=200, FAIL=500' },
  { source: 'content.actionUserName (NCP) / userName (NHN)', target: 'actor_user_name', rule: 'nested 또는 평탄' },
  { source: 'content.sourceIp (NCP) / userIp (NHN)', target: 'src_endpoint_ip', rule: 'IPv4/IPv6' },
  { source: '그 외 모든 원본 필드', target: 'unmapped_raw', rule: '원본 JSON 통째로 보존' },
];

const V3OCSF = () => {
  const navigate = useNavigate();
  const showToast = useToastStore((s) => s.show);
  const caseId = useCaseStore((s) => s.caseId);
  const queryClient = useQueryClient();

  const [page, setPage] = useState(1);
  const [selectedIdx, setSelectedIdx] = useState(0);

  const ocsfQuery = useQuery({
    queryKey: ['ocsf', caseId, page],
    queryFn: () => getOcsf(caseId!, page, PAGE_SIZE),
    enabled: !!caseId,
  });

  const normalizeMutation = useMutation({
    mutationFn: () => runNormalize(caseId!),
    onSuccess: (stats) => {
      showToast(
        `정규화 완료: ${stats.normalized}/${stats.total} (실패 ${stats.failed}, ${stats.normalizationRate}%)`,
      );
      queryClient.invalidateQueries({ queryKey: ['ocsf', caseId] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`정규화 실패: ${msg}`);
    },
  });

  if (!caseId) {
    return (
      <div>
        <PageHeader eyebrow="Layer 2 · M2-1" title="OCSF 정규화" description="활성화된 사고 케이스가 없습니다." />
        <PageBody>
          <Card title={<>사고 케이스 없음</>}>
            <p className="text-[13px] text-ink-300 mb-3">
              V-1 사고 접수 위저드를 먼저 완료하고 V-2 에서 로그를 업로드하세요.
            </p>
            <button onClick={() => navigate('/setup')} className="btn-primary">
              ← V-1 사고 접수로 돌아가기
            </button>
          </Card>
        </PageBody>
      </div>
    );
  }

  const total = ocsfQuery.data?.total ?? 0;
  const items = ocsfQuery.data?.items ?? [];
  const selected = items[selectedIdx];
  const stats = normalizeMutation.data;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const rawDisplay: Record<string, unknown> = selected?.unmapped_raw ?? {};
  const ocsfDisplay: Record<string, unknown> = selected
    ? {
        ocsf_id: selected.ocsf_id,
        event_id: selected.event_id,
        time: selected.time,
        activity_name: selected.activity_name,
        actor_user_name: selected.actor_user_name,
        src_endpoint_ip: selected.src_endpoint_ip,
        status_code: selected.status_code,
      }
    : {};

  return (
    <div>
      <PageHeader
        eyebrow="Layer 2 · M2-1"
        title="OCSF 정규화"
        description="원본 CSP 로그를 OCSF 1.3 평탄화 컬럼으로 변환합니다. 좌·우 패널에서 변환 전·후를 비교하세요."
        actions={
          <>
            <button
              onClick={() => normalizeMutation.mutate()}
              disabled={normalizeMutation.isPending}
              className="btn-ghost disabled:opacity-50"
            >
              {normalizeMutation.isPending ? '정규화 중…' : ' 정규화 실행'}
            </button>
            <button onClick={() => navigate('/gap')} className="btn-primary">
              갭 감지 →
            </button>
          </>
        }
      />

      <PageBody className="flex flex-col gap-6 animate-fade-up">
        {/* P.29 — 시연용 백엔드 응답 디버그 패널 제거 */}

        <div className="grid grid-cols-3 gap-3">
          <KpiCard
            label="정규화된 이벤트"
            value={total.toLocaleString()}
            color="teal"
            hint="ocsf_events 테이블"
          />
          <KpiCard
            label="실패 (마지막 실행)"
            value={stats?.failed ?? '—'}
            color="red"
            hint="failedEvents 확인"
          />
          <KpiCard label="스키마 버전" value="OCSF 1.3 (평탄화)" color="purple" hint="설계서 5.2절" />
        </div>

        {/* 샘플 selector */}
        {items.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="eyebrow">샘플 이벤트 (page {page})</span>
            {items.slice(0, 10).map((it, i) => (
              <button
                key={it.ocsf_id}
                onClick={() => setSelectedIdx(i)}
                className={`px-3 py-1.5 rounded-full text-[12px] font-semibold border transition-all max-w-[300px] truncate ${
                  selectedIdx === i
                    ? 'bg-brand-blue/15 border-brand-blue/50 text-brand-blue'
                    : 'bg-ink-900 border-ink-700 text-ink-300 hover:text-ink-100'
                }`}
                title={`${it.time} · ${it.activity_name}`}
              >
                {it.activity_name?.slice(0, 28) ?? '(no name)'}
              </button>
            ))}
            {totalPages > 1 && (
              <Pagination
                page={page}
                totalPages={totalPages}
                onPageChange={(p) => {
                  // 버그 #10 fix — 페이지 변경 시 selectedIdx 리셋 (범위 밖 접근 방어)
                  setPage(p);
                  setSelectedIdx(0);
                }}
                className="ml-auto"
              />
            )}
          </div>
        )}

        {/* 양면 비교 */}
        {selected ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <RawJsonPanel title="원본 CSP 로그 (unmapped_raw)" titleColor="#FF4D6D" badge="RAW" data={rawDisplay} />
            <RawJsonPanel
              title="OCSF 정규화 평탄화 컬럼"
              titleColor="#14D9B0"
              badge="OCSF 1.3"
              data={ocsfDisplay}
            />
          </div>
        ) : (
          <Card title={<>샘플 이벤트 없음</>}>
            <p className="text-[13px] text-ink-400">
              아직 정규화된 OCSF 이벤트가 없습니다. 「정규화 실행」 버튼을 눌러주세요.
            </p>
          </Card>
        )}

        <FieldMappingTable mappings={mappings} />
      </PageBody>
    </div>
  );
};

export default V3OCSF;
