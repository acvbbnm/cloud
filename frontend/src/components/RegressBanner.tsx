/**
 * RegressBanner — Zone 강등 + 회복 가이드 (V1.fix.9, 2026-05-31 byungwoo).
 *
 * 설계서: docs/evidence_tree_paradigm.md §21.8.1 회귀 권고
 *
 * 사용자 피드백 (2026-05-31)
 * --------------------------
 *   "모호해졌다고 떳는데 왜 다시 안돌아가는거같지"
 *
 * 진단
 * ----
 *   - 백엔드는 regress 시 zone=1 자동 강등 + regress_suggested=true 응답
 *   - 기존 UI 는 AttackChainCard (zone=2 일 때만 노출) 안에 회귀 메시지 가 들어
 *     있어 카드와 함께 unmount → 토스트 한 번 만 보고 끝, 다음 행동 모름.
 *
 * 해결
 * ----
 *   - Zone 무관 별도 배너로 분리
 *   - 현재 entropy bits + Top1·Top2 gap + 목표값 + 회복 가이드 표시
 *   - "단서를 더 채택해 변별력 회복" 명시
 *
 * 학술 정합
 * ---------
 *   - Shannon entropy H = -Σ P(h) log2 P(h)  — uniform 8 가설 시 max=3.0 bits
 *   - 회귀 트리거: H ≥ 2.0 bits OR gap < 0.10  (paradigm §21.8.1)
 *   - 회복 가이드: 강한 단서 (max P(c|h) ≥ 0.30) 1-2개 채택 시 H 자연 감소
 */

interface RegressBannerProps {
  /** 현재 entropy (bits). uniform 8 가설 max=3.0. */
  entropyBits: number;
  /** Top1 사후확률. */
  primaryProb: number;
  /** Top2 사후확률. */
  secondaryProb: number;
  /** 회귀 트리거 정상 여부. false 면 본 컴포넌트 noop. */
  regressSuggested: boolean;
}

// paradigm §21.8.1 의 트리거 임계값과 동일 (백엔드 zone_logic.py 와 동기 — V1.fix.9 보정).
const REGRESS_ENTROPY = 2.7;
const REGRESS_GAP = 0.10;

const RegressBanner = ({
  entropyBits,
  primaryProb,
  secondaryProb,
  regressSuggested,
}: RegressBannerProps) => {
  if (!regressSuggested) return null;

  const gap = primaryProb - secondaryProb;
  const triggers: string[] = [];
  if (entropyBits >= REGRESS_ENTROPY) {
    triggers.push(`entropy ${entropyBits.toFixed(2)} ≥ ${REGRESS_ENTROPY.toFixed(1)} bits`);
  }
  if (gap < REGRESS_GAP) {
    triggers.push(`Top1·Top2 격차 ${(gap * 100).toFixed(1)}% < ${(REGRESS_GAP * 100).toFixed(0)}%`);
  }

  // 회복 목표 — 둘 중 하나라도 충족하면 Zone 2 자동 복귀
  const entropyHealthy = entropyBits < REGRESS_ENTROPY;
  const gapHealthy = gap >= REGRESS_GAP;

  return (
    <div className="border border-amber-500/60 bg-amber-900/15 rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-amber-700/40 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-amber-300">
            회귀 권고 — Zone 1 (광범위 탐색) 으로 강등됨
          </span>
        </div>
        <span className="text-[9.5px] text-amber-300/70 font-mono">자동 강등 · 단서 추가로 회복</span>
      </div>

      <div className="px-3 py-2.5 space-y-2">
        <p className="text-[11px] text-amber-100/90 leading-5">
          가설이 다시 모호해졌습니다. 백엔드가 Zone 1 으로 자동 강등했고, 변별력 있는 단서를
          1-2개 더 채택하면 자동으로 Zone 2 복귀합니다.
        </p>

        {/* 트리거 사유 */}
        <div className="bg-ink-900/40 rounded px-2.5 py-1.5">
          <div className="text-[10px] text-amber-300/80 font-mono mb-1">트리거 사유</div>
          <ul className="space-y-0.5">
            {triggers.map((t) => (
              <li key={t} className="text-[10.5px] text-amber-100/85 leading-4 flex items-start gap-1.5">
                <span className="text-amber-400 mt-0.5">▸</span>
                <span className="font-mono">{t}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* 회복 진행 — 게이지 2개 (entropy + gap) */}
        <div className="grid grid-cols-2 gap-2">
          <Gauge
            label="entropy"
            value={entropyBits}
            max={3.0}
            threshold={REGRESS_ENTROPY}
            healthy={entropyHealthy}
            invertHealthy
            unit=" bits"
          />
          <Gauge
            label="Top1·Top2 격차"
            value={gap * 100}
            max={100}
            threshold={REGRESS_GAP * 100}
            healthy={gapHealthy}
            unit="%"
          />
        </div>

        <div className="text-[10.5px] text-amber-200/85 leading-5 pt-1 border-t border-amber-700/30">
          <span className="font-semibold">다음 행동 →</span> 우측 [다음 단서 후보] 패널에서 IG 순위 상위
          후보를 채택하세요. 강한 단서 (P(c|h) ≥ 0.30) 1-2개면 보통 회복됩니다.
        </div>
      </div>
    </div>
  );
};

interface GaugeProps {
  label: string;
  value: number;
  max: number;
  threshold: number;
  /** healthy === true 이면 회복 완료 상태. */
  healthy: boolean;
  /** true 면 "낮을수록 좋음" 게이지 (entropy 처럼). 기본은 "높을수록 좋음". */
  invertHealthy?: boolean;
  unit?: string;
}

const Gauge = ({ label, value, max, threshold, healthy, invertHealthy = false, unit = '' }: GaugeProps) => {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const tpct = Math.max(0, Math.min(100, (threshold / max) * 100));
  return (
    <div className="bg-ink-900/40 rounded px-2.5 py-1.5">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-ink-300 font-mono">{label}</span>
        <span
          className={
            'text-[10px] font-mono ' + (healthy ? 'text-emerald-300' : 'text-amber-300')
          }
        >
          {value.toFixed(2)}
          {unit} {healthy ? '✓' : ''}
        </span>
      </div>
      <div className="relative h-1.5 bg-ink-950 rounded overflow-hidden">
        <div
          className={
            'absolute inset-y-0 left-0 transition-all ' +
            (healthy ? 'bg-emerald-500/80' : 'bg-amber-500/80')
          }
          style={{ width: `${pct}%` }}
        />
        {/* threshold 표시 — 임계값 위치 점선 */}
        <div
          className="absolute inset-y-0 w-px bg-ink-300/60"
          style={{ left: `${tpct}%` }}
          title={`임계: ${threshold.toFixed(2)}${unit}${invertHealthy ? ' 이하' : ' 이상'} 회복`}
        />
      </div>
      <div className="text-[9px] text-ink-400 font-mono mt-0.5">
        목표: {invertHealthy ? '<' : '≥'} {threshold.toFixed(2)}
        {unit}
      </div>
    </div>
  );
};

export default RegressBanner;
