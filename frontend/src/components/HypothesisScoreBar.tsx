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
  /** 임계값 표시 — 기본 70/90 */
  highConfidence?: number;
  autoSkip?: number;
  /** 최대 막대 너비 기준 점수 (기본 120 — terminal_score) */
  maxScale?: number;
  /** 추천 결과의 primary/secondary 강조 (있으면 표시) */
  highlightPrimary?: IncidentType;
  highlightSecondary?: IncidentType;
}

const INCIDENT_TYPE_KO: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '자격증명 탈취',
  PRIVILEGE_ESCALATION: '권한 상승',
  DATA_EXFILTRATION: '데이터 유출',
  AUDIT_LOG_TAMPERING: '감사 로그 변조',
  MULTI_CSP_LATERAL: '멀티 CSP 횡이동',
  // dev3 C-1 신규 4종
  RANSOMWARE: '랜섬웨어',
  MISCONFIG_EXPOSURE: '설정 오류 노출',
  PHISH_INITIAL_ACCESS: '피싱 초기 침투',
  INSIDER_THREAT: '내부자 위협',
  UNCLASSIFIED: '미분류',
};

const HypothesisScoreBar = ({
  scores,
  highConfidence = 70,
  autoSkip = 90,
  maxScale = 120,
  highlightPrimary,
  highlightSecondary,
}: HypothesisScoreBarProps) => {
  // UNCLASSIFIED 제외, 점수 내림차순
  const rows = (Object.keys(scores) as IncidentType[])
    .filter((t) => t !== 'UNCLASSIFIED')
    .map((type) => ({ type, score: scores[type] }))
    .sort((a, b) => b.score - a.score);

  const pct = (s: number) => Math.min(100, (s / maxScale) * 100);

  return (
    <div>
      <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-2">
        📊 가설 점수
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
                  {isPrimary && ' ●'}
                  {isSecondary && ' ○'}
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
          auto_skip {autoSkip}점 + gap 20 — 자동 확정
        </div>
      </div>
    </div>
  );
};

export default HypothesisScoreBar;
