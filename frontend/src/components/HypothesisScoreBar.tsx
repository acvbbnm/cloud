/**
 * 가설 점수 막대그래프 — V-1 Step 2 Discovery Loop 우측 패널.
 *
 * 5개 사고유형(UNCLASSIFIED 제외)의 점수를 내림차순 막대로 표시.
 * 임계값 (high_confidence=70, auto_skip_tree=90) 표시선 + 1·2위 강조.
 *
 * 학술 근거: docs/dev3/가중치_설계_근거.md + weights.json
 */
import type { HypothesisScores, IncidentType } from '@/types';

interface HypothesisScoreBarProps {
  scores: HypothesisScores;
  /** 임계값 표시 — 기본 90/130 (E4 6단계 누적 정합, 2026-05-21) */
  highConfidence?: number;
  autoSkip?: number;
  /** 최대 막대 너비 기준 점수 (기본 180 — terminal_score, E4 정합) */
  maxScale?: number;
  /** 추천 결과의 primary/secondary 강조 (있으면 표시) */
  highlightPrimary?: IncidentType;
  highlightSecondary?: IncidentType;
  /** 노출할 최대 가설 수 (기본 2 — 사용자 요청 2026-05-25, 0 = 전부) */
  limit?: number;
  /** 카드 클릭 시 호출 — 사고유형 비교 풀 오버레이 토글용 (2026-05-25) */
  onExpand?: () => void;
}

const INCIDENT_TYPE_KO: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '자격증명 탈취',
  PRIVILEGE_ESCALATION: '권한 상승',
  DATA_EXFILTRATION: '데이터 유출',
  AUDIT_LOG_TAMPERING: '감사 로그 변조',
  // dev3 C-1 신규 4종 (MULTI_CSP_LATERAL 2026-05-19 제거)
  RANSOMWARE: '랜섬웨어',
  MISCONFIG_EXPOSURE: '설정 오류 노출',
  PHISH_INITIAL_ACCESS: '피싱 초기 침투',
  INSIDER_THREAT: '내부자 위협',
  UNCLASSIFIED: '미분류',
};

const HypothesisScoreBar = ({
  scores,
  highConfidence = 90,
  autoSkip = 130,
  maxScale = 180,
  highlightPrimary,
  highlightSecondary,
  limit = 2,
  onExpand,
}: HypothesisScoreBarProps) => {
  // UNCLASSIFIED 제외, 점수 내림차순 — 사용자 요청 2026-05-25: 상위 N개만 (기본 2)
  const allRows = (Object.keys(scores) as IncidentType[])
    .filter((t) => t !== 'UNCLASSIFIED')
    .map((type) => ({ type, score: scores[type] }))
    .sort((a, b) => b.score - a.score);
  const rows = limit > 0 ? allRows.slice(0, limit) : allRows;
  const hiddenCount = allRows.length - rows.length;

  const pct = (s: number) => Math.min(100, (s / maxScale) * 100);

  return (
    <div
      onClick={onExpand}
      className={onExpand ? 'cursor-pointer hover:bg-ink-800/30 rounded -mx-1 px-1 py-1 transition-colors' : ''}
      title={onExpand ? '클릭 시 8종 사고유형 비교·근거 보기' : undefined}
      role={onExpand ? 'button' : undefined}
      tabIndex={onExpand ? 0 : undefined}
      onKeyDown={(e) => {
        if (onExpand && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onExpand();
        }
      }}
    >
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider">
           가설 점수 {limit > 0 && allRows.length > 0 && ` · 상위 ${rows.length}`}
        </span>
        {onExpand ? (
          <span className="text-[9.5px] text-brand-teal hover:underline">
            전체 8종 비교 ⛶
          </span>
        ) : (
          hiddenCount > 0 && (
            <span className="text-[9.5px] text-ink-500">+{hiddenCount}개</span>
          )
        )}
      </div>

      <div className="space-y-1.5">
        {rows.map(({ type, score }) => {
          const isPrimary = type === highlightPrimary;
          const isSecondary = type === highlightSecondary;
          const isHigh = score >= autoSkip;
          const isMedium = score >= highConfidence && !isHigh;
          const color = isPrimary
            ? 'bg-brand-teal'
            : isSecondary
            ? 'bg-brand-amber'
            : isHigh
            ? 'bg-red-500'
            : isMedium
            ? 'bg-amber-500'
            : 'bg-brand-blue/60';
          return (
            <div key={type} className="text-[11px]">
              <div className="flex items-center justify-between mb-0.5">
                <span
                  className={`${
                    isPrimary
                      ? 'text-brand-teal font-semibold'
                      : isSecondary
                      ? 'text-brand-amber font-semibold'
                      : 'text-ink-300'
                  }`}
                >
                  {INCIDENT_TYPE_KO[type]}
                  {isPrimary && ' '}
                  {isSecondary && ' '}
                </span>
                <span className="font-mono text-ink-200 text-[10.5px]">
                  {score}
                </span>
              </div>
              <div className="relative h-2 rounded-full bg-ink-900 overflow-hidden">
                <div
                  className={`h-full transition-all ${color}`}
                  style={{ width: `${pct(score)}%` }}
                />
                {/* 임계선 — high_confidence */}
                <div
                  className="absolute top-0 bottom-0 w-px bg-amber-400/40"
                  style={{ left: `${pct(highConfidence)}%` }}
                  title={`high_confidence ${highConfidence}점`}
                />
                {/* 임계선 — auto_skip */}
                <div
                  className="absolute top-0 bottom-0 w-px bg-red-400/40"
                  style={{ left: `${pct(autoSkip)}%` }}
                  title={`auto_skip ${autoSkip}점`}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* 임계값 범례 */}
      <div className="mt-2.5 text-[9.5px] text-ink-500 leading-4">
        <div>
          <span className="inline-block w-2 h-2 rounded-full bg-amber-400/60 mr-1" />
          high_confidence {highConfidence}점 — 사고유형 제시
        </div>
        <div>
          <span className="inline-block w-2 h-2 rounded-full bg-red-400/60 mr-1" />
          auto_skip {autoSkip}점 + gap 30 — 자동 확정
        </div>
      </div>
    </div>
  );
};

export default HypothesisScoreBar;
