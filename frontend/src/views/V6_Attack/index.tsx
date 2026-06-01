import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import Card from '@/components/Card';
import KpiCard from '@/components/KpiCard';
import Badge from '@/components/Badge';
import { useToastStore } from '@/stores/useToastStore';
import { useCaseStore } from '@/stores/useCaseStore';
import { useEvidenceLogStore } from '@/stores/useEvidenceLogStore';
import { getAttack, runMap } from '@/api/analysis';
import type { AttackEventItem } from '@/types';

const FETCH_PAGE_SIZE = 100; // 한 페이지로 모두 받아 집계 (228건이면 두 페이지로 충분)

interface TechniqueAgg {
  technique_id: string;
  technique_name: string | null;
  tactic: string;
  count: number;
}

type Intensity = 'high' | 'med' | 'low';

// risk_score 제거 — 색상·심각도는 탐지 횟수(count) 기반으로 대체.
// 학술 변호: 한 기법이 여러 번 탐지되면 그만큼 활동이 빈번하다는 객관 지표.
const intensityFor = (count: number): Intensity => {
  if (count >= 4) return 'high';
  if (count >= 2) return 'med';
  return 'low';
};

const intensityClass: Record<Intensity, string> = {
  high: 'bg-brand-red/22 text-brand-red ring-brand-red/30',
  med: 'bg-brand-amber/18 text-brand-amber ring-brand-amber/25',
  low: 'bg-brand-blue/15 text-brand-blue ring-brand-blue/20',
};

const sevTone = (count: number): 'red' | 'amber' | 'blue' =>
  count >= 4 ? 'red' : count >= 2 ? 'amber' : 'blue';

const countLabel = (count: number): string =>
  count >= 4 ? '다수 탐지' : count >= 2 ? '복수 탐지' : '단일 탐지';

/**
 * AttackEventItem[] → tactic 별 컬럼 + technique 집계.
 * (tactic, technique_id) 그룹별 count.
 */
const aggregate = (items: AttackEventItem[]): TechniqueAgg[] => {
  const map = new Map<string, TechniqueAgg>();
  for (const ev of items) {
    const key = `${ev.tactic}::${ev.technique_id}`;
    const prev = map.get(key);
    if (prev) {
      prev.count += 1;
    } else {
      map.set(key, {
        technique_id: ev.technique_id,
        technique_name: ev.technique_name,
        tactic: ev.tactic,
        count: 1,
      });
    }
  }
  return Array.from(map.values());
};

const V6Attack = () => {
  const navigate = useNavigate();
  const showToast = useToastStore((s) => s.show);
  const caseId = useCaseStore((s) => s.caseId);
  const queryClient = useQueryClient();

  const [page, setPage] = useState(1);

  const attackQuery = useQuery({
    queryKey: ['attack', caseId, page, FETCH_PAGE_SIZE],
    queryFn: () => getAttack(caseId!, page, FETCH_PAGE_SIZE),
    enabled: !!caseId,
  });

  // P.36 — V-1 적재함 push
  const loadEvidence = useEvidenceLogStore((s) => s.load);
  const evidenceHas = useEvidenceLogStore((s) => s.has);

  /** AttackEventItem 1건 → 적재함 LoadedLog. 기법 ID 는 6종 ClueType 미매칭
   *  이라 observable 추출 없음. timestamp + 기법 메타만 적재. */
  const buildAttackLog = (e: AttackEventItem) => ({
    loaded_id: `att-${e.attack_id}`,
    source: 'attack' as const,
    source_id: e.attack_id,
    time: e.event_time,
    label: `${e.activity_name ?? e.technique_id} · ${e.tactic}`,
    observables: [],
    technique_id: e.technique_id,
    fields: {
      technique_id: e.technique_id,
      technique_name: e.technique_name,
      tactic: e.tactic,
      activity_name: e.activity_name,
      rule_id: e.rule_id,
      event_time: e.event_time,
    },
  });

  // techTable 의 row 가 *집계* 라 첫 발생 attack_event 를 representative 로 적재
  const firstAttackForTech = (tactic: string, technique_id: string): AttackEventItem | undefined =>
    (attackQuery.data?.items ?? []).find(
      (e) => e.tactic === tactic && e.technique_id === technique_id,
    );

  const mapMutation = useMutation({
    mutationFn: () => runMap(caseId!),
    onSuccess: (stats) => {
      showToast(
        `매핑 완료: OCSF ${stats.total_ocsf}건 중 mapped ${stats.mapped} / unmapped ${stats.unmapped} (rate ${stats.mappingRate}%)`,
      );
      queryClient.invalidateQueries({ queryKey: ['attack', caseId] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`매핑 실패: ${msg}`);
    },
  });

  if (!caseId) {
    return (
      <div>
        <PageHeader
          eyebrow="Layer 2 · M2-3"
          title="ATT&CK 매핑"
          description="활성화된 사고 케이스가 없습니다."
        />
        <PageBody>
          <Card title={<>사고 케이스 없음</>}>
            <p className="text-[13px] text-ink-300 mb-3">
              V-1 사고 접수 위저드를 먼저 완료해야 매핑 결과를 볼 수 있습니다.
            </p>
            <button onClick={() => navigate('/setup')} className="btn-primary">
              ← V-1 사고 접수로 돌아가기
            </button>
          </Card>
        </PageBody>
      </div>
    );
  }

  const items = attackQuery.data?.items ?? [];
  const total = attackQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / FETCH_PAGE_SIZE));

  // 집계 (현재 페이지의 items 기준 — 페이지당 100건이면 일반적으로 한 페이지로 충분)
  const aggregations = useMemo(() => aggregate(items), [items]);

  // tactic 별로 그룹핑 (히트맵 컬럼)
  const matrixByTactic = useMemo(() => {
    const groups = new Map<string, TechniqueAgg[]>();
    for (const agg of aggregations) {
      const arr = groups.get(agg.tactic) ?? [];
      arr.push(agg);
      groups.set(agg.tactic, arr);
    }
    // 전술 정렬: tactic 내 총 탐지 count 합산 내림차순 (탐지 많은 전술 왼쪽)
    return Array.from(groups.entries())
      .map(([tactic, techs]) => ({
        tactic,
        techniques: techs.sort((a, b) => b.count - a.count),
        total_count: techs.reduce((s, t) => s + t.count, 0),
      }))
      .sort((a, b) => b.total_count - a.total_count);
  }, [aggregations]);

  // 기법 상세 표: count 내림차순
  const techTable = useMemo(
    () => [...aggregations].sort((a, b) => b.count - a.count),
    [aggregations],
  );

  return (
    <div>
      <PageHeader
        eyebrow="Layer 2 · M2-3"
        title="MITRE ATT&CK 매핑"
        description="attack_events 를 ATT&CK Cloud Matrix 의 전술 × 기법 히트맵으로 집계합니다. 결정론적 JSON 룰 기반 — 환각 없음."
        actions={
          <>
            <button
              onClick={() => mapMutation.mutate()}
              disabled={mapMutation.isPending}
              className="btn-ghost"
            >
              {mapMutation.isPending ? '매핑 중…' : '↻ ATT&CK 매핑 실행'}
            </button>
            <button
              onClick={() => {
                showToast('→ 보고서 생성');
                navigate('/report');
              }}
              className="btn-primary"
            >
              보고서 →
            </button>
          </>
        }
      />

      <PageBody className="flex flex-col gap-6 animate-fade-up">
        {/* P.29 — 시연용 백엔드 응답 디버그 패널 제거 */}

        <div className="grid grid-cols-3 gap-3">
          <KpiCard
            label="탐지된 기법"
            value={aggregations.length}
            color="purple"
            hint={total > 0 ? `${total}건의 ATT&CK 매핑 결과` : '매핑 대기'}
          />
          <KpiCard
            label="전술 커버리지"
            value={`${matrixByTactic.length}`}
            color="red"
            hint="MITRE ATT&CK Cloud Matrix"
          />
          <KpiCard
            label="매핑 이벤트"
            value={total.toLocaleString()}
            color="blue"
            hint="attack_events 총 건수"
          />
        </div>

        {items.length === 0 && !attackQuery.isLoading && (
          <Card title={<>No ATT&CK Mapping</>}>
            <p className="text-[12.5px] text-ink-300 leading-6">
              아직 ATT&CK 매핑 결과가 없습니다. 상단의 <code className="text-brand-teal">↻ ATT&CK 매핑 실행</code> 버튼으로
              <code className="text-brand-teal mx-1">POST /api/analysis/map</code> 을 호출하세요.
              V-3 정규화 + V-2 raw 적재가 선행되어 있어야 합니다.
            </p>
          </Card>
        )}

        {matrixByTactic.length > 0 && (
          <Card
            title={<>ATT&CK Cloud Matrix 히트맵</>}
            subtitle=" = 탐지 · 색상 = 탐지 횟수 (≥4 red / ≥2 amber / 1 blue) · 정렬 = 전술 내 총 탐지 합산 내림차순"
          >
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
              {matrixByTactic.map((col) => (
                <div key={col.tactic}>
                  <div className="text-center pb-2 border-b-2 border-ink-700/70 text-ink-300 text-[10.5px] font-bold uppercase tracking-[0.08em] mb-2">
                    {col.tactic}
                    <span className="ml-1 text-[9.5px] text-ink-500">({col.total_count})</span>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    {col.techniques.map((t) => {
                      const intensity = intensityFor(t.count);
                      return (
                        <a
                          key={t.technique_id}
                          href={`https://attack.mitre.org/techniques/${t.technique_id.replace(/\./g, '/')}/`}
                          target="_blank"
                          rel="noreferrer"
                          className={`block px-2 py-2 rounded-lg text-[10.5px] font-medium ring-1 ring-inset ${intensityClass[intensity]} hover:brightness-125 transition-all`}
                          title={`${t.technique_name ?? ''} (탐지 ${t.count}건)`}
                        >
                          <div className="font-bold">{t.technique_id}</div>
                          <div className="truncate">{t.technique_name ?? '—'}</div>
                          <div className="text-[9.5px] opacity-75 mt-0.5">
                            탐지 {t.count}건
                            {intensity === 'high' && <span className="ml-1"></span>}
                          </div>
                        </a>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {techTable.length > 0 && (
          <Card title={<>탐지 기법 상세 (count 내림차순)</>}>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-[12.5px]">
                <thead>
                  <tr className="bg-ink-950/70 text-ink-400 text-[10.5px] uppercase tracking-[0.1em]">
                    <th className="text-left px-3 py-3 border-b border-ink-700/60">기법 ID</th>
                    <th className="text-left px-3 py-3 border-b border-ink-700/60">기법명</th>
                    <th className="text-left px-3 py-3 border-b border-ink-700/60">전술</th>
                    <th className="text-left px-3 py-3 border-b border-ink-700/60">이벤트 수</th>
                    <th className="text-left px-3 py-3 border-b border-ink-700/60">탐지 빈도</th>
                    {/* P.36 — V-1 적재함 push */}
                    <th className="text-left px-3 py-3 border-b border-ink-700/60">적재</th>
                  </tr>
                </thead>
                <tbody>
                  {techTable.map((t) => {
                    const ev = firstAttackForTech(t.tactic, t.technique_id);
                    const log = ev ? buildAttackLog(ev) : null;
                    const already = log ? evidenceHas(log.loaded_id) : false;
                    return (
                      <tr
                        key={`${t.tactic}-${t.technique_id}`}
                        className="border-b border-ink-700/30 hover:bg-brand-blue/[0.04]"
                      >
                        <td className="px-3 py-2.5">
                          <Badge tone="purple">{t.technique_id}</Badge>
                        </td>
                        <td className="px-3 py-2.5 font-medium">{t.technique_name ?? '—'}</td>
                        <td className="px-3 py-2.5 text-ink-200">{t.tactic}</td>
                        <td className="px-3 py-2.5 font-mono text-ink-100">{t.count}</td>
                        <td className="px-3 py-2.5">
                          <Badge tone={sevTone(t.count)}>{countLabel(t.count)}</Badge>
                        </td>
                        <td className="px-3 py-2.5">
                          {log ? (
                            <button
                              type="button"
                              onClick={() => {
                                if (loadEvidence(log)) {
                                  showToast(`➜ V-1 적재함: ${t.technique_id}`);
                                } else {
                                  showToast('이미 적재됨');
                                }
                              }}
                              disabled={already}
                              className="text-[10.5px] font-mono px-2 py-0.5 rounded border border-brand-teal/40 text-brand-teal hover:bg-brand-teal/15 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                              title={
                                already
                                  ? '이미 적재됨'
                                  : '첫 발생 attack_event 를 V-1 Step3 적재함에 추가'
                              }
                            >
                              {already ? '✓' : '➜ 적재함'}
                            </button>
                          ) : (
                            <span className="text-[10px] text-ink-600">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {total > FETCH_PAGE_SIZE && (
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
        )}
      </PageBody>
    </div>
  );
};

export default V6Attack;
