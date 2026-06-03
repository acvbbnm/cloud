/**
 * Phase 2.5 (P6, 2026-05-25) — Dwell Time KPI 카드.
 * 2026-05-29 — 타임라인 시각화 + 격차 강조 + 권고 안내 추가
 *
 * PDF 결론 (Mandiant M-Trends 2024 median dwell time 7일) 정합 비교.
 * V-5 Investigation Board 우측 패널에서 본 케이스의 dwell time 을 글로벌 평균과 비교.
 *
 * 산출 정의 (backend InvestigationBoard.compute_kpi):
 *   dwellTime = caseCreatedAt - earliestEventTime  (탐지 - 최초 침해)
 *   benchmark = 604800s (7일, Mandiant)
 */
import { useState } from 'react';

import SourceTag from '@/components/SourceTag';

import type { BoardKpi } from '@/types';

const SEC_PER_DAY = 86400;

// 등급 tone → Tailwind 클래스 (text / bg / border-l)
const TONE_CLASS: Record<string, { text: string; bg: string; borderL: string }> = {
  teal: { text: 'text-brand-teal', bg: 'bg-brand-teal', borderL: 'border-l-brand-teal' },
  amber: { text: 'text-amber-300', bg: 'bg-amber-400', borderL: 'border-l-amber-400' },
  red: { text: 'text-brand-red', bg: 'bg-brand-red', borderL: 'border-l-brand-red' },
  gray: { text: 'text-ink-400', bg: 'bg-ink-600', borderL: 'border-l-ink-600' },
};

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
  const [expanded, setExpanded] = useState(false);

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
  const containment = kpi.containmentSeconds;
  const benchmarkDays = Math.round(benchmark / SEC_PER_DAY);

  // 등급 — 백엔드 _dwell_grade (Mandiant median 10d + 분포 4등급). fallback 은 단순 비교.
  const grade = kpi.grade;
  const tone = grade?.tone ?? (dwell != null && dwell < benchmark ? 'teal' : 'red');
  const toneCls = TONE_CLASS[tone] ?? TONE_CLASS.gray;
  const barColor = toneCls.bg;
  const borderColor = toneCls.borderL;

  const ratio = dwell != null ? Math.min((dwell / benchmark) * 100, 200) : 0;

  // 평균 대비 초과 시간 (양수 = 늦음)
  const gapSeconds = dwell != null ? dwell - benchmark : null;
  const gapDays = gapSeconds != null ? Math.floor(gapSeconds / SEC_PER_DAY) : null;

  // Timeline 시각화 비율 — dwell + containment 합산 기준
  const totalSeconds = (dwell ?? 0) + (containment ?? 0);
  const dwellPct = totalSeconds > 0 ? ((dwell ?? 0) / totalSeconds) * 100 : 0;
  const benchmarkPct = totalSeconds > 0 ? Math.min((benchmark / totalSeconds) * 100, 100) : 0;

  return (
    <div className={`panel p-3 border-l-[3px] ${borderColor} text-[12px]`}>
      <div className="flex items-center justify-between mb-2 gap-2">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="eyebrow text-[10px] hover:text-brand-teal transition-colors flex items-center gap-1 min-w-0"
          title={expanded ? '접기' : '타임라인 펼치기'}
        >
          <span>{expanded ? '▼' : '▶'}</span>
          탐지 지연 시간 (Dwell Time)
        </button>
        {/* V1.fix.11 (2026-05-31) — "왜 수사보드에 있는지" 의문 → 클릭 popup 으로 의미·계산식·왜 보는지 설명 */}
        <SourceTag
          label="ⓘ"
          align="right"
          title="Dwell Time — 탐지 지연 시간 KPI"
          body={
            'Dwell Time 은 침해 발생 시점부터 탐지까지 걸린 시간을 측정하는\n' +
            '보안 사고 핵심 KPI 입니다. Mandiant M-Trends 2024 의 글로벌 중앙값\n' +
            '(10일) 을 기준으로 4 등급 (매우 빠름·평균 이내·평균 초과·장기 잠복)\n' +
            '으로 본 조직의 탐지 역량을 평가합니다.\n\n' +
            '계산:\n' +
            '  Dwell Time = 탐지 시각 − 최초 침해 이벤트시각\n\n' +
            '등급 기준 (Mandiant median 10d + 분포):\n' +
            '  · ≤ 1일   매우 빠름 (상위권)\n' +
            '  · ≤ 10일  평균 이내 (글로벌 median 이하)\n' +
            '  · ≤ 30일  평균 초과 (주의)\n' +
            '  · > 30일  장기 잠복 (체계 보강 권고)\n\n' +
            (grade?.source
              ? `근거: ${grade.source}`
              : '근거: Mandiant M-Trends 2024 (global median dwell 10d)')
          }
        />
      </div>

      <div className="flex items-baseline gap-2 mb-1">
        <span className="text-[20px] font-mono font-bold text-ink-100">
          {formatDuration(dwell)}
        </span>
        <span className="text-[10px] text-ink-400">/ 벤치마크 {benchmarkDays}d</span>
        {grade && (
          <span className={`text-[10.5px] font-bold ml-1 ${toneCls.text}`}>
            {grade.label}
          </span>
        )}
        {gapDays != null && gapDays > 0 && (
          <span className="text-[10px] text-ink-500 ml-1">
            (+{gapDays}d)
          </span>
        )}
      </div>

      {/* progress bar — 벤치마크(median) 대비 위치 */}
      <div className="h-1.5 bg-ink-800 mt-2 mb-1.5 relative overflow-hidden rounded-full">
        <div
          className={`h-full ${barColor} transition-all`}
          style={{ width: `${Math.min(ratio, 100)}%` }}
        />
        <div
          className="absolute top-0 right-0 h-full w-px bg-ink-400"
          title={`Mandiant median ${benchmarkDays}d`}
        />
      </div>

      <div className="text-[10.5px] text-ink-400 leading-5">
        {dwell != null && grade && (
          <>
            <b className={toneCls.text}>{grade.message}</b>
          </>
        )}
        {containment != null && (
          <>
            {' · '}격리 소요 <b className="text-ink-100">{formatDuration(containment)}</b>
          </>
        )}
      </div>

      {/* ── 확장 영역 — Timeline 시각화 + 권고 ── */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-ink-700/60 space-y-3">
          {/* Timeline 막대 — 최초 침해 → 탐지 → 격리 3 단계 */}
          <div>
            <div className="flex items-center justify-between text-[10px] text-ink-400 mb-1.5">
              <span>Timeline</span>
              <span className="font-mono text-ink-500">
                총 {formatDuration(totalSeconds)}
              </span>
            </div>
            <div className="h-6 bg-ink-800 rounded relative overflow-hidden flex">
              {/* Dwell 영역 (최초 침해 → 탐지) */}
              <div
                className={`${barColor} relative flex items-center justify-center transition-all`}
                style={{ width: `${dwellPct}%` }}
              >
                {dwellPct > 12 && (
                  <span className="text-[9px] text-white font-bold drop-shadow">
                    Dwell {formatDuration(dwell)}
                  </span>
                )}
              </div>
              {/* Containment 영역 (탐지 → 격리) */}
              {containment != null && (
                <div
                  className="bg-brand-blue relative flex items-center justify-center"
                  style={{ width: `${100 - dwellPct}%` }}
                >
                  {100 - dwellPct > 12 && (
                    <span className="text-[9px] text-white font-bold drop-shadow">
                      격리 {formatDuration(containment)}
                    </span>
                  )}
                </div>
              )}
              {/* Mandiant 7d 마크 */}
              {benchmarkPct > 0 && benchmarkPct < 100 && (
                <div
                  className="absolute top-0 h-full w-0.5 bg-amber-300/90"
                  style={{ left: `${benchmarkPct}%` }}
                  title="Mandiant 7d 벤치마크"
                />
              )}
            </div>
            {benchmarkPct > 0 && benchmarkPct < 100 && (
              <div
                className="text-[9px] text-amber-300/80 mt-0.5 -ml-1"
                style={{ marginLeft: `calc(${benchmarkPct}% - 14px)` }}
              >
                ↑ 7d
              </div>
            )}
            <div className="grid grid-cols-2 gap-1 mt-1.5 text-[9.5px]">
              <div className="text-ink-400">
                <span className={`inline-block w-2 h-2 rounded-sm mr-1 ${barColor}`} />
                탐지까지 (Dwell)
              </div>
              {containment != null && (
                <div className="text-ink-400">
                  <span className="inline-block w-2 h-2 rounded-sm mr-1 bg-brand-blue" />
                  격리까지 (Containment)
                </div>
              )}
            </div>
          </div>

          {/* 권고 메시지 — 등급 기반 (warning/critical = 경고, excellent/good = 칭찬) */}
          {(grade?.grade === 'warning' || grade?.grade === 'critical') &&
            gapDays != null && gapDays > 0 && (
              <div className="bg-brand-red/10 border border-brand-red/30 rounded px-2.5 py-1.5 text-[10.5px] leading-5">
                <b className={toneCls.text}>⚠ {grade.label} — 탐지 지연 {gapDays}일</b>
                <div className="text-ink-300 mt-0.5">
                  Mandiant median({benchmarkDays}d) 대비 {gapDays}일 초과. CSP Activity Tracer
                  보존 기간 90일 + 실시간 알람 임계값 점검 권고.
                </div>
              </div>
            )}
          {(grade?.grade === 'excellent' || grade?.grade === 'good') && dwell != null && (
            <div className="bg-brand-teal/10 border border-brand-teal/30 rounded px-2.5 py-1.5 text-[10.5px] leading-5">
              <b className="text-brand-teal">✓ {grade.label} — Mandiant 평균 이내</b>
              <div className="text-ink-300 mt-0.5">
                글로벌 median {benchmarkDays}d 대비{' '}
                {dwell < benchmark ? `${formatDuration(benchmark - dwell)} 빠름` : '동등 수준'}.
                초동 대응 양호.
              </div>
            </div>
          )}

          {/* 정의 + 출처 */}
          <div className="text-[9.5px] text-ink-500 leading-4 space-y-0.5">
            <div>
              <b className="text-ink-400">정의:</b> Dwell Time = 최초 침해 → 탐지 까지 경과 시간
            </div>
            <div>
              <b className="text-ink-400">출처:</b>{' '}
              {grade?.source ?? 'Mandiant M-Trends 2024 · global median 10d'}
            </div>
          </div>
        </div>
      )}

      <div className="mt-1 text-[9.5px] text-ink-500 font-mono leading-4">
        최초 침해: {kpi.earliestEventTime?.slice(0, 19) ?? '—'}
        <br />
        탐지/접수: {kpi.detectedAt?.slice(0, 19) ?? kpi.caseCreatedAt?.slice(0, 19) ?? '—'}
      </div>
    </div>
  );
};

export default DwellTimeKpi;
