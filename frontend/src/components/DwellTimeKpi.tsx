/**
 * Phase 2.5 (P6, 2026-05-25) — Dwell Time KPI 카드.
 *
 * PDF 결론 (Mandiant M-Trends 2024 median dwell time 7일) 정합 비교.
 * V-5 Investigation Board 우측 패널에서 본 케이스의 dwell time 을 글로벌 평균과 비교.
 *
 * 산출 정의 (backend InvestigationBoard.compute_kpi):
 *   dwellTime = caseCreatedAt - earliestEventTime  (탐지 - 최초 침해)
 *   benchmark = 604800s (7일, Mandiant)
 */
import type { BoardKpi } from '@/types';

interface DwellTimeKpiProps {
  kpi?: BoardKpi;
}

/** seconds → "Nd Nh Nm" 또는 "Nh Nm" 형식. */
const formatDuration = (sec: number | null): string => {
  if (sec == null) return '—';
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ${m % 60}m`;
  const d = Math.floor(h / 24);
  return `${d}d ${h % 24}h`;
};

const DwellTimeKpi = ({ kpi }: DwellTimeKpiProps) => {
  if (!kpi) {
    return (
      <div className="panel p-3 text-[12px] text-ink-400">
        <div className="eyebrow text-[10px] mb-1">Dwell Time</div>
        <div>KPI 계산 불가 — 정규화된 OCSF 이벤트 필요</div>
      </div>
    );
  }

  const dwell = kpi.dwellTimeSeconds;
  const benchmark = kpi.benchmarkSeconds;
  // dwell 이 벤치마크보다 짧으면 우수 (teal), 길면 위험 (red)
  const isFaster = dwell != null && dwell < benchmark;
  const ratio = dwell != null ? Math.min((dwell / benchmark) * 100, 200) : 0;
  const barColor = isFaster ? 'bg-brand-teal' : 'bg-brand-red';

  return (
    <div className="panel p-3 border-l-[3px] border-l-brand-teal text-[12px]">
      <div className="flex items-center justify-between mb-2">
        <span className="eyebrow text-[10px]">Dwell Time (PDF 결론 §)</span>
        <span className="text-[9.5px] text-ink-500 font-mono">Mandiant M-Trends 2024</span>
      </div>

      <div className="flex items-baseline gap-2 mb-1">
        <span className="text-[20px] font-mono font-bold text-ink-100">
          {formatDuration(dwell)}
        </span>
        <span className="text-[10px] text-ink-400">/ 벤치마크 7d</span>
      </div>

      {/* progress bar — 벤치마크 7d 대비 위치 */}
      <div className="h-1 bg-ink-800 mt-2 mb-1.5 relative overflow-hidden">
        <div
          className={`h-full ${barColor} transition-all`}
          style={{ width: `${Math.min(ratio, 100)}%` }}
        />
        {/* 벤치마크 마크 (100%) */}
        <div className="absolute top-0 right-0 h-full w-px bg-ink-400" title="Mandiant 7d" />
      </div>

      <div className="text-[10.5px] text-ink-400 leading-5">
        {dwell != null && (
          <>
            본 케이스{' '}
            <b className={isFaster ? 'text-brand-teal' : 'text-brand-red'}>
              {isFaster ? '글로벌 평균보다 빠름' : '글로벌 평균보다 느림'}
            </b>
          </>
        )}
        {kpi.containmentSeconds != null && (
          <>
            {' · '}격리 소요 <b className="text-ink-100">{formatDuration(kpi.containmentSeconds)}</b>
          </>
        )}
      </div>

      <div className="mt-1 text-[9.5px] text-ink-500 font-mono leading-4">
        최초 침해: {kpi.earliestEventTime?.slice(0, 19) ?? '—'}
        <br />
        탐지/접수: {kpi.caseCreatedAt?.slice(0, 19) ?? '—'}
      </div>
    </div>
  );
};

export default DwellTimeKpi;
