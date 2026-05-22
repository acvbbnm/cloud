/**
 * ConfidenceGauge — V-1 Step 2 Discovery Loop 우측 패널.
 *
 * E4 (2026-05-21): 결정 트리 6단계 누적의 신뢰도를 시각화.
 * 의료 감별진단의 "diagnostic confidence" 비유.
 *
 * 신뢰도 = primary_score / auto_skip_tree (130) × 100
 * 색상 단계 (docs/dev3/결정트리_업그레이드.md §4-3):
 *   0-40%   회색  "단서 부족"
 *   40-70%  파랑  "가설 형성 중"
 *   70-90%  초록  "🎯 가설 형성"
 *   90%+    강조  "✅ 자동 확정 가능" + 펄스
 *
 * 격차(gap) < 30 시 amber "⚠ 복합 사고 의심" 추가 표시.
 */
import type { HypothesisScores, IncidentType } from '@/types';

interface ConfidenceGaugeProps {
  scores: HypothesisScores;
  /** auto_skip_tree threshold (default 130 — E4 6단계 누적 정합) */
  autoSkip?: number;
  /** gap_to_2nd threshold (default 30) */
  gapTo2nd?: number;
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

const ConfidenceGauge = ({
  scores,
  autoSkip = 130,
  gapTo2nd = 30,
}: ConfidenceGaugeProps) => {
  const sorted = (Object.keys(scores) as IncidentType[])
    .filter((t) => t !== 'UNCLASSIFIED')
    .map((type) => ({ type, score: scores[type] }))
    .sort((a, b) => b.score - a.score);

  const primary = sorted[0];
  const secondary = sorted[1];
  const gap = primary && secondary ? primary.score - secondary.score : 0;

  const ratio = primary ? Math.min(100, (primary.score / autoSkip) * 100) : 0;

  // 색상 단계
  let tone: 'gray' | 'blue' | 'green' | 'pulse';
  let label: string;
  if (ratio >= 100) {
    tone = 'pulse';
    label = '✅ 자동 확정 가능';
  } else if (ratio >= 70) {
    tone = 'green';
    label = '🎯 가설 형성';
  } else if (ratio >= 40) {
    tone = 'blue';
    label = '가설 형성 중';
  } else {
    tone = 'gray';
    label = '단서 부족';
  }

  const ratioColor = {
    gray: 'text-ink-400',
    blue: 'text-brand-blue',
    green: 'text-brand-teal',
    pulse: 'text-brand-teal',
  }[tone];

  const ringFill = {
    gray: '#475569',
    blue: '#3b82f6',
    green: '#14b8a6',
    pulse: '#14b8a6',
  }[tone];

  // gap hint
  const isComposite = primary && primary.score >= autoSkip * 0.7 && gap < gapTo2nd;

  return (
    <div>
      <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-2">
        🎚 신뢰도 게이지
      </div>

      {primary && (
        <>
          <div className="flex items-center gap-3 mb-2">
            {/* 원형 게이지 — CSS conic-gradient */}
            <div
              className={`relative w-16 h-16 rounded-full shrink-0 transition-all duration-500 ${
                tone === 'pulse' ? 'animate-pulse' : ''
              }`}
              style={{
                background: `conic-gradient(${ringFill} ${ratio}%, rgba(255,255,255,0.06) ${ratio}% 100%)`,
              }}
            >
              <div className="absolute inset-1.5 rounded-full bg-ink-900 flex items-center justify-center">
                <span className={`text-[14px] font-bold font-mono ${ratioColor}`}>
                  {Math.round(ratio)}%
                </span>
              </div>
            </div>

            <div className="min-w-0 flex-1">
              <div className="text-[11px] text-ink-300 truncate">
                <span className="text-ink-500">1위</span>{' '}
                <b className={ratioColor}>{INCIDENT_TYPE_KO[primary.type]}</b>
              </div>
              <div className="text-[10.5px] font-mono text-ink-400 mt-0.5">
                {primary.score} / {autoSkip}점
              </div>
              <div className={`text-[10.5px] mt-0.5 font-semibold ${ratioColor}`}>
                {label}
              </div>
            </div>
          </div>

          {/* gap hint */}
          {secondary && (
            <div
              className={`text-[10.5px] leading-4 rounded-md px-2 py-1.5 border ${
                isComposite
                  ? 'bg-amber-500/10 border-amber-500/30 text-amber-200'
                  : gap >= gapTo2nd
                  ? 'bg-brand-teal/10 border-brand-teal/30 text-ink-300'
                  : 'bg-ink-900/40 border-ink-700/40 text-ink-400'
              }`}
            >
              {isComposite ? (
                <>
                  ⚠ 1위 <b>{INCIDENT_TYPE_KO[primary.type]}</b> 과 2위{' '}
                  <b>{INCIDENT_TYPE_KO[secondary.type]}</b> 격차 <b>{gap}</b>점 —
                  복합 사고 의심
                </>
              ) : gap >= gapTo2nd ? (
                <>
                  🎯 1위와 2위 격차 <b>{gap}</b>점 — 명확
                </>
              ) : gap >= 10 ? (
                <>
                  가설 형성 중 — 1위·2위 격차 {gap}점 (Q5·Q6 진행 권장)
                </>
              ) : (
                <>여전히 모호 — 격차 {gap}점 (추가 단서 권장)</>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ConfidenceGauge;
