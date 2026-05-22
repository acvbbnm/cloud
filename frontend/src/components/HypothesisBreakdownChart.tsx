/**
 * HypothesisBreakdownChart — V-1 Step 3 Discovery Loop 우측 패널 하단.
 *
 * E4 §4-8 (2026-05-21): 8 사고유형 비교 차트 + 기여 요소 breakdown.
 * 의료 감별진단의 "diagnostic breakdown" 비유.
 *
 * 표시:
 *   - 8 사고유형 leaderboard (점수 내림차순)
 *   - 각 사고유형 행 클릭 → 펼침 (소스별 점수 + 기여 항목 trace)
 *   - 학술 변호: 결정성 100% — "왜 이 가설인가" 추적 가능
 *
 * 데이터 소스 (5종, weights.json 단일 소스):
 *   - environment : system_config → environment_modifiers
 *   - tree        : 결정 트리 답변
 *   - combo       : 트리 답변 조합 부스트
 *   - clues       : 단서 (Observable)
 *   - techniques  : 부분 로그 매핑 ATT&CK 기법
 *
 * breakdown 데이터는 부모 (Step3_Discovery) 가 POST /api/triage/breakdown 호출 후 전달.
 * 데이터 없으면 trees/clues/techniques 카운트 요약만 표시.
 */
import { useState } from 'react';

import type { HypothesisScores, IncidentType } from '@/types';
import type { BreakdownResponse, BreakdownItem } from '@/api/triage';

interface HypothesisBreakdownChartProps {
  scores: HypothesisScores;
  /** 결정 트리 답변 수 (fallback 요약용) */
  treeAnswerCount: number;
  /** 단서 수 (fallback 요약용) */
  clueCount: number;
  /** 부분 분석 매핑된 기법 수 (fallback 요약용) */
  mappedTechniqueCount: number;
  /** auto_skip_tree threshold (default 130) */
  autoSkip?: number;
  /** 백엔드 /api/triage/breakdown 응답 — 있으면 expanded 영역에 출처 trace 표시 */
  breakdown?: BreakdownResponse | null;
  breakdownLoading?: boolean;
}

const INCIDENT_TYPE_KO: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '자격증명 탈취',
  PRIVILEGE_ESCALATION: '권한 상승',
  DATA_EXFILTRATION: '데이터 유출',
  AUDIT_LOG_TAMPERING: '감사 로그 변조',
  RANSOMWARE: '랜섬웨어',
  MISCONFIG_EXPOSURE: '설정 오류 노출',
  PHISH_INITIAL_ACCESS: '피싱 초기 침투',
  INSIDER_THREAT: '내부자 위협',
  UNCLASSIFIED: '미분류',
};

const TYPE_COLOR: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: 'bg-blue-500',
  PRIVILEGE_ESCALATION: 'bg-purple-500',
  DATA_EXFILTRATION: 'bg-orange-500',
  AUDIT_LOG_TAMPERING: 'bg-rose-500',
  RANSOMWARE: 'bg-red-500',
  MISCONFIG_EXPOSURE: 'bg-amber-500',
  PHISH_INITIAL_ACCESS: 'bg-fuchsia-500',
  INSIDER_THREAT: 'bg-teal-500',
  UNCLASSIFIED: 'bg-ink-700',
};

const SOURCE_LABEL: Record<string, string> = {
  environment: '환경 보정',
  tree: '결정 트리',
  combo: '조합 부스트',
  clues: '단서',
  techniques: '기법 매핑',
};

const SOURCE_BADGE: Record<string, string> = {
  environment: 'bg-emerald-500/20 text-emerald-300',
  tree: 'bg-blue-500/20 text-blue-300',
  combo: 'bg-purple-500/20 text-purple-300',
  clue: 'bg-amber-500/20 text-amber-300',
  technique: 'bg-rose-500/20 text-rose-300',
};

const HypothesisBreakdownChart = ({
  scores,
  treeAnswerCount,
  clueCount,
  mappedTechniqueCount,
  autoSkip = 130,
  breakdown = null,
  breakdownLoading = false,
}: HypothesisBreakdownChartProps) => {
  const [expanded, setExpanded] = useState<IncidentType | null>(null);

  const sorted = (Object.keys(scores) as IncidentType[])
    .filter((t) => t !== 'UNCLASSIFIED')
    .map((type) => ({ type, score: scores[type] }))
    .sort((a, b) => b.score - a.score);

  const totalNonZero = sorted.filter((r) => r.score > 0).length;
  const max = sorted[0]?.score ?? 0;

  return (
    <div className="border-t border-ink-700/40 pt-3">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider">
          📊 사고유형 비교 (8종)
        </div>
        <div className="text-[10px] text-ink-500">
          상위 {totalNonZero}/8 활성
          {breakdownLoading && <span className="ml-1 text-brand-blue">· 분해 중…</span>}
        </div>
      </div>

      {/* 기여 요소 요약 */}
      <div className="text-[10px] text-ink-500 leading-4 mb-2">
        기여 요소: 트리 답변 <b className="text-ink-300">{treeAnswerCount}</b> ·
        단서 <b className="text-ink-300">{clueCount}</b> ·
        부분 분석 <b className="text-ink-300">{mappedTechniqueCount}</b>
        {breakdown && (
          <>
            {' '}· 항목 <b className="text-ink-300">{breakdown.items.length}</b>건
          </>
        )}
      </div>

      {/* 8 사고유형 leaderboard */}
      <div className="space-y-0.5">
        {sorted.map((row, i) => {
          const pct = max > 0 ? (row.score / Math.max(autoSkip, max)) * 100 : 0;
          const isPrimary = i === 0 && row.score > 0;
          const isSecondary = i === 1 && row.score > 0;
          const isExpanded = expanded === row.type;

          return (
            <div key={row.type}>
              <button
                type="button"
                onClick={() =>
                  setExpanded((cur) => (cur === row.type ? null : row.type))
                }
                className={`w-full flex items-center gap-2 px-1.5 py-1 rounded text-left hover:bg-ink-800/60 transition-colors ${
                  isExpanded ? 'bg-ink-800/40' : ''
                }`}
              >
                <span
                  className={`w-4 shrink-0 text-[10px] font-mono ${
                    isPrimary
                      ? 'text-brand-teal font-bold'
                      : isSecondary
                      ? 'text-brand-amber'
                      : 'text-ink-500'
                  }`}
                >
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-0.5">
                    <span
                      className={`text-[10.5px] truncate ${
                        isPrimary
                          ? 'text-brand-teal font-semibold'
                          : isSecondary
                          ? 'text-brand-amber'
                          : 'text-ink-300'
                      }`}
                    >
                      {INCIDENT_TYPE_KO[row.type]}
                    </span>
                    <span className="text-[10px] font-mono text-ink-300 ml-2 shrink-0">
                      {row.score}
                    </span>
                  </div>
                  <div className="relative h-1.5 bg-ink-900 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-500 ${
                        TYPE_COLOR[row.type]
                      } ${row.score === 0 ? 'opacity-30' : ''}`}
                      style={{ width: `${Math.min(100, pct)}%` }}
                    />
                  </div>
                </div>
              </button>

              {isExpanded && (
                <div className="ml-6 mt-1 mb-1 text-[10px] text-ink-400 leading-4 bg-ink-900/40 rounded px-2 py-1.5 border border-ink-700/30">
                  <ExpandedDetail
                    type={row.type}
                    score={row.score}
                    breakdown={breakdown}
                    breakdownLoading={breakdownLoading}
                    fallbackCounts={{
                      tree: treeAnswerCount,
                      clue: clueCount,
                      technique: mappedTechniqueCount,
                    }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// expanded 영역 — 출처 trace
// ─────────────────────────────────────────────────────────────

interface ExpandedDetailProps {
  type: IncidentType;
  score: number;
  breakdown: BreakdownResponse | null;
  breakdownLoading: boolean;
  fallbackCounts: { tree: number; clue: number; technique: number };
}

const ExpandedDetail = ({
  type,
  score,
  breakdown,
  breakdownLoading,
  fallbackCounts,
}: ExpandedDetailProps) => {
  // breakdown 없으면 fallback 카운트만 표시 (백엔드 미응답 또는 초기 로딩)
  if (!breakdown) {
    return (
      <>
        <div className="text-ink-300 font-semibold mb-0.5">
          {INCIDENT_TYPE_KO[type]} {score}점 기여 출처
        </div>
        {breakdownLoading ? (
          <div className="text-ink-500 mt-1">출처 분해 로딩 중…</div>
        ) : (
          <>
            <ul className="space-y-0.5 list-disc pl-3">
              <li>결정 트리 답변 {fallbackCounts.tree}개 (Q1~Q6)</li>
              <li>단서(Observable) {fallbackCounts.clue}개</li>
              <li>부분 로그 분석 기법 {fallbackCounts.technique}개</li>
            </ul>
            <div className="text-[9.5px] text-ink-500 mt-1.5">
              ※ 정확한 점수 분해를 보려면 트리 답변·단서·부분 분석을 진행하세요.
            </div>
          </>
        )}
      </>
    );
  }

  // 이 사고유형에 기여한 항목만 필터 (weights[type] > 0)
  const contributingItems = breakdown.items.filter(
    (it) => (it.weights[type] ?? 0) > 0,
  );

  // 소스별 합산 (이 사고유형 기준)
  const bySource = breakdown.by_source;
  const sourceTotals: Array<{ src: string; value: number }> = [
    { src: 'environment', value: bySource.environment[type] ?? 0 },
    { src: 'tree', value: bySource.tree[type] ?? 0 },
    { src: 'combo', value: bySource.combo[type] ?? 0 },
    { src: 'clues', value: bySource.clues[type] ?? 0 },
    { src: 'techniques', value: bySource.techniques[type] ?? 0 },
  ].filter((s) => s.value !== 0);

  // 총합 검증 — by_source 합산 == totals[type]
  const sumCheck = sourceTotals.reduce((s, x) => s + x.value, 0);

  return (
    <>
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-ink-300 font-semibold">
          {INCIDENT_TYPE_KO[type]} {score}점 기여 분해
        </div>
        <div className="text-[9.5px] text-ink-500">
          소스 합산 <span className="text-ink-300">{sumCheck}</span>
        </div>
      </div>

      {/* 소스별 stacked bar */}
      {sourceTotals.length > 0 && (
        <div className="mb-2">
          <div className="relative h-2 bg-ink-900 rounded-full overflow-hidden flex">
            {sourceTotals.map((s) => {
              const pct = sumCheck > 0 ? (s.value / sumCheck) * 100 : 0;
              const color = {
                environment: 'bg-emerald-500',
                tree: 'bg-blue-500',
                combo: 'bg-purple-500',
                clues: 'bg-amber-500',
                techniques: 'bg-rose-500',
              }[s.src] ?? 'bg-ink-700';
              return (
                <div
                  key={s.src}
                  className={color}
                  style={{ width: `${pct}%` }}
                  title={`${SOURCE_LABEL[s.src]} ${s.value}점`}
                />
              );
            })}
          </div>
          <div className="flex flex-wrap gap-x-2 gap-y-0.5 mt-1 text-[9.5px]">
            {sourceTotals.map((s) => (
              <span key={s.src} className="inline-flex items-center gap-1 text-ink-400">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    {
                      environment: 'bg-emerald-500',
                      tree: 'bg-blue-500',
                      combo: 'bg-purple-500',
                      clues: 'bg-amber-500',
                      techniques: 'bg-rose-500',
                    }[s.src]
                  }`}
                />
                {SOURCE_LABEL[s.src]} <b className="text-ink-200">{s.value}</b>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 항목별 trace — 이 사고유형에 기여한 것만 */}
      {contributingItems.length > 0 ? (
        <ul className="space-y-1 max-h-[180px] overflow-y-auto pr-1">
          {contributingItems.map((it, idx) => (
            <ContribItemRow key={`${it.source}-${it.key}-${idx}`} item={it} typeKey={type} />
          ))}
        </ul>
      ) : (
        <div className="text-ink-500 italic">기여 항목 없음 — 점수 0</div>
      )}

      <div className="text-[9.5px] text-ink-500 mt-1.5 leading-4">
        ※ 결정성 100% — 같은 입력 시 같은 분해 (weights.json 단일 소스).
      </div>
    </>
  );
};

interface ContribItemRowProps {
  item: BreakdownItem;
  typeKey: IncidentType;
}

const ContribItemRow = ({ item, typeKey }: ContribItemRowProps) => {
  const pts = item.weights[typeKey] ?? 0;
  const badgeCls = SOURCE_BADGE[item.source] ?? 'bg-ink-700 text-ink-300';
  return (
    <li className="flex items-start gap-1.5 leading-4">
      <span
        className={`inline-block text-[9px] px-1.5 py-0.5 rounded font-semibold shrink-0 ${badgeCls}`}
      >
        {SOURCE_LABEL[item.source === 'clue' ? 'clues' : item.source === 'technique' ? 'techniques' : item.source]}
      </span>
      <div className="flex-1 min-w-0">
        <div className="text-ink-200 truncate" title={item.label}>
          {item.label}
        </div>
        {item.rationale && (
          <div className="text-[9px] text-ink-500 truncate" title={item.rationale}>
            {item.rationale}
          </div>
        )}
      </div>
      <span className="text-ink-200 font-mono text-[10px] shrink-0">+{pts}</span>
    </li>
  );
};

export default HypothesisBreakdownChart;
