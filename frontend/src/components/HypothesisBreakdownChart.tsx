/**
 * HypothesisBreakdownChart — V-1 Step 2 Discovery Loop 우측 패널 하단.
 *
 * E4 §4-8 (2026-05-21): 8 사고유형 비교 차트 + 기여 요소 breakdown.
 * 의료 감별진단의 "diagnostic breakdown" 비유.
 *
 * 표시:
 *   - 8 사고유형 leaderboard (점수 내림차순)
 *   - 각 사고유형 행 클릭 → 펼침 (기여 요소 카운트)
 *   - 학술 변호: 결정성 100% — "왜 이 가설인가" 추적 가능
 *
 * 기여 요소 카운트:
 *   - 결정 트리 답변 N개 (completedPath)
 *   - 단서 N개 (observables — 부모 전달)
 *   - 부분 분석 기법 N개 (mappedTechniques)
 *
 * 백엔드 가중치 매트릭스를 클라이언트가 직접 읽지 않으므로, 출처별 정확한 점수
 * breakdown 은 추후 백엔드 /api/triage/breakdown API 도입 후 가능 (TODO).
 */
import { useState } from 'react';

import type { HypothesisScores, IncidentType } from '@/types';

interface HypothesisBreakdownChartProps {
  scores: HypothesisScores;
  /** 결정 트리 답변 수 */
  treeAnswerCount: number;
  /** 단서 수 */
  clueCount: number;
  /** 부분 분석 매핑된 기법 수 */
  mappedTechniqueCount: number;
  /** auto_skip_tree threshold (default 130) */
  autoSkip?: number;
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

const HypothesisBreakdownChart = ({
  scores,
  treeAnswerCount,
  clueCount,
  mappedTechniqueCount,
  autoSkip = 130,
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
        </div>
      </div>

      {/* 기여 요소 요약 */}
      <div className="text-[10px] text-ink-500 leading-4 mb-2">
        기여 요소: 트리 답변 <b className="text-ink-300">{treeAnswerCount}</b> ·
        단서 <b className="text-ink-300">{clueCount}</b> ·
        부분 분석 <b className="text-ink-300">{mappedTechniqueCount}</b>
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
                  <div className="text-ink-300 font-semibold mb-0.5">
                    {INCIDENT_TYPE_KO[row.type]} {row.score}점 기여 출처
                  </div>
                  <ul className="space-y-0.5 list-disc pl-3">
                    <li>결정 트리 답변 {treeAnswerCount}개 (Q1~Q6)</li>
                    <li>단서(Observable) {clueCount}개</li>
                    <li>부분 로그 분석 기법 {mappedTechniqueCount}개</li>
                  </ul>
                  <div className="text-[9.5px] text-ink-500 mt-1.5">
                    ※ 출처별 정확한 점수 분해는 추후 /api/triage/breakdown API 로 보강.
                    현재는 누적값만 권위 (weights.json 단일 소스).
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default HypothesisBreakdownChart;
