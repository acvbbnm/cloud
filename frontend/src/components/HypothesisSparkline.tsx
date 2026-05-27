/**
 * HypothesisSparkline — 가설별 신뢰도 시계열 미니 차트 (Phase N.3, 2026-05-26, byungwoo).
 *
 * 설계서: `docs/evidence_tree_paradigm.md` §21.1 ② 복합 공격 시간순 활성화
 *
 * 학술 정합
 * ---------
 *   - MITRE ATT&CK Kill Chain (TA0001 → TA0040) — 단계별 시간순 진행
 *   - Mandiant 2023 Dwell Time KPI — 평균 5-7단계 복합 공격
 *
 * 동작
 * ----
 *   path (root → leaf) 각 노드의 posterior_after[hypothesis] 시계열 → SVG polyline.
 *   "이 가설이 어느 단서 시점에 강했는가" 시각화. 단일 99% 쏠림이 아닌 가설별 활성
 *   곡선을 보여 복합 공격 직관 정합.
 *
 * 시각
 * ----
 *   ▁▁▂▄▆▇▇▆▅▄  ← polyline, 0~1 범위
 *   x: 단서 시점 (depth)
 *   y: 그 시점의 사후확률
 */
import type { ClueTreePathNode } from '@/types/clueTree';
import type { IncidentType } from '@/types';

interface HypothesisSparklineProps {
  /** root → leaf path (Step3 treeState.path 그대로). root 포함. */
  path: ClueTreePathNode[];
  /** 시계열을 그릴 가설. */
  hypothesis: IncidentType;
  /** 선 색상 (가설 색). */
  color: string;
  /** SVG width / height (기본 60 × 16). */
  width?: number;
  height?: number;
  /** 현재 사후확률 텍스트 동봉 여부 (기본 false). */
  showCurrent?: boolean;
}

const HypothesisSparkline = ({
  path,
  hypothesis,
  color,
  width = 60,
  height = 16,
  showCurrent = false,
}: HypothesisSparklineProps) => {
  // root 만 있거나 path 비어있으면 — 빈 placeholder
  if (path.length < 2) {
    return (
      <svg width={width} height={height} className="opacity-30">
        <line
          x1={0}
          y1={height - 1}
          x2={width}
          y2={height - 1}
          stroke={color}
          strokeWidth={0.5}
          strokeDasharray="1 2"
        />
      </svg>
    );
  }

  // posterior 시계열 추출 — 0~1 범위
  const series = path.map((node) => {
    const p = node.posterior_after?.[hypothesis] ?? 0;
    return Math.max(0, Math.min(1, p));
  });

  // 좌표 변환 — y 는 위→아래 flip
  const n = series.length;
  const xStep = n > 1 ? width / (n - 1) : 0;
  const points = series
    .map((v, i) => {
      const x = i * xStep;
      const y = height - v * (height - 1) - 0.5; // padding
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  // 현재 (마지막) 값
  const currentVal = series[series.length - 1];

  return (
    <span className="inline-flex items-center gap-1.5">
      <svg width={width} height={height} style={{ display: 'inline-block', verticalAlign: 'middle' }}>
        {/* 기준선 (50%) */}
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="rgba(120, 130, 150, 0.18)"
          strokeWidth={0.5}
          strokeDasharray="1 2"
        />
        {/* 시계열 polyline */}
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth={1.2}
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.85}
        />
        {/* 마지막 점 강조 */}
        <circle
          cx={(n - 1) * xStep}
          cy={height - currentVal * (height - 1) - 0.5}
          r={1.6}
          fill={color}
        />
      </svg>
      {showCurrent && (
        <span className="text-[9px] text-ink-500 font-mono">
          {(currentVal * 100).toFixed(0)}%
        </span>
      )}
    </span>
  );
};

export default HypothesisSparkline;
