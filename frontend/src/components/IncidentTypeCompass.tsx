/**
 * IncidentTypeCompass — 사고유형 8 방향 컴퍼스 시각화 (Phase I, 2026-05-26, byungwoo).
 *
 * 사용자 비전 — "단서를 통해 미로를 헤쳐나가듯이 한 사고유형 방향으로 수렴":
 *   - 8 사고유형을 단위원 위 45° 간격 anchor 로 배치
 *   - 단서 채택 시 사후확률 가중 무게중심으로 위치 이동
 *     position = Σ (P(h_k) × anchor_k for k in hypotheses)
 *   - 단서 누적 = 궤적 (시작점 → 각 단서 → 현재)
 *   - confidence 도달 시 가장 가까운 anchor 강조 (글로우)
 *
 * 학술 정합:
 *   - Pearl 1988 Belief Simplex Projection
 *   - 사후확률 분포의 2D barycentric 투영
 *   - "어두운 맵 밝히기" (paradigm §1) 메타포의 직접 구현
 *
 * 8 사고유형 시계방향 배치 (12시 시작, Phase P 재배치 — KBW 2026-05-27).
 * MITRE Cloud Kill Chain 시간순 (Initial Access → Impact) 으로 인접 사고유형이
 * 의미상 연결되도록 재정렬. 수사 보드 피드백 "맵 인접 배치 확인" 응답.
 *
 *     12  PHISH_INITIAL_ACCESS    (Phase 1, Initial Access)
 *   1:30  CREDENTIAL_THEFT        (Phase 2, Credential Access)
 *      3  PRIVILEGE_ESCALATION    (Phase 3, Privilege Esc.)
 *   4:30  INSIDER_THREAT          (Phase 4, Discovery/Lateral)
 *      6  MISCONFIG_EXPOSURE      (Phase 4, Discovery/Lateral)
 *   7:30  AUDIT_LOG_TAMPERING     (Phase 5, Defense Evasion)
 *      9  DATA_EXFILTRATION       (Phase 6, Exfiltration)
 *  10:30  RANSOMWARE              (Phase 7, Impact)
 *
 * 인접성:
 *   PHISH ↔ CRED ↔ PRIV ↔ INSIDER ↔ MISCFG ↔ AUDIT ↔ DATA ↔ RANSOM
 *   모두 Kill Chain 순서로 ±1 단계 차이 (시계방향 자연 흐름).
 */
import { useEffect, useMemo, useRef, useState } from 'react';

import type { HypothesisScores, IncidentType } from '@/types';
import type { SerializedClueTree, SerializedClueTreeNode } from '@/types/clueTree';

interface IncidentTypeCompassProps {
  /** 전체 트리 (백엔드 ClueTreeResponse.tree). */
  tree: SerializedClueTree;
  /** 현재 leaf 노드 ID. */
  currentLeafId: string;
  /** confidence 도달 시 강조 사고유형. */
  primaryIncident?: IncidentType | null;
  confidenceReached?: boolean;
  /**
   * SVG 한 변 길이 (기본 자동 반응형 — 부모 width).
   * 명시 시 고정 크기. min 460, max 780.
   */
  size?: number;
  /** 자동 반응형 사용 (기본 true). false 시 size 고정 사용. */
  responsive?: boolean;
  /** 헤더 텍스트. */
  title?: string;
  /** 카드 헤더 오른쪽 — ⛶ 확대 / 모드 토글 등. */
  headerRight?: React.ReactNode;
  /** 비활성 (loading). */
  disabled?: boolean;
  // ─── Phase M.2 (2026-05-26) — 2-zone 컴퍼스 (paradigm §21·§22.3) ───
  /** 1 = 광범위 탐색 (내부 원 안), 2 = 사고유형 chain 구체화 (외부 원 부근). */
  zone?: 1 | 2;
  /** Zone 2 → 1 회귀 권고 — 헤더 알림. */
  regressSuggested?: boolean;
  /** 보스 단서 likelihood (시각화 보조 — 0 ~ 1). */
  coreClueLikelihood?: number;
}

// Phase P (KBW, 2026-05-27) — Kill Chain 시간순 시계방향 재배치.
const INCIDENT_TYPES_ORDER: IncidentType[] = [
  'PHISH_INITIAL_ACCESS',  // 12시   · Phase 1 · Initial Access
  'CREDENTIAL_THEFT',      // 1:30   · Phase 2 · Credential Access
  'PRIVILEGE_ESCALATION',  // 3시    · Phase 3 · Privilege Esc.
  'INSIDER_THREAT',        // 4:30   · Phase 4 · Discovery/Lateral
  'MISCONFIG_EXPOSURE',    // 6시    · Phase 4 · Discovery/Lateral
  'AUDIT_LOG_TAMPERING',   // 7:30   · Phase 5 · Defense Evasion
  'DATA_EXFILTRATION',     // 9시    · Phase 6 · Exfiltration
  'RANSOMWARE',            // 10:30  · Phase 7 · Impact
];

/** 사고유형별 Kill Chain phase (1~7). 컴퍼스 라벨 + 인접 검증용. */
const KILL_CHAIN_PHASE: Record<IncidentType, number> = {
  PHISH_INITIAL_ACCESS: 1,
  CREDENTIAL_THEFT: 2,
  PRIVILEGE_ESCALATION: 3,
  INSIDER_THREAT: 4,
  MISCONFIG_EXPOSURE: 4,
  AUDIT_LOG_TAMPERING: 5,
  DATA_EXFILTRATION: 6,
  RANSOMWARE: 7,
  UNCLASSIFIED: 99,
};

/** Stage 별 trail 색 — Phase P (KBW, 2026-05-27) 사용자 피드백
 *  "다시 중앙에서 시작 다른색 사용해서 다음 트리라는 인상" */
const STAGE_COLORS: Record<number, { fill: string; stroke: string; label: string }> = {
  1: { fill: '#26C281', stroke: '#34D399', label: 'Stage 1' },
  2: { fill: '#5BA3F0', stroke: '#7BBAFA', label: 'Stage 2' },
  3: { fill: '#A56BE6', stroke: '#BB87F0', label: 'Stage 3' },
  4: { fill: '#E66BC2', stroke: '#F087D0', label: 'Stage 4' },
};
const stageColor = (stage: number) =>
  STAGE_COLORS[stage] ?? STAGE_COLORS[4];

// 사고유형별 한국어 라벨 + 색상
const INCIDENT_KO: Record<IncidentType, string> = {
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

// 사고유형별 색상 (HSL hue) — 시계방향 spectrum
const INCIDENT_COLORS: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '#5BA3F0',      // blue
  PRIVILEGE_ESCALATION: '#A56BE6',  // purple
  DATA_EXFILTRATION: '#E66BC2',     // pink
  AUDIT_LOG_TAMPERING: '#E68A6B',   // coral
  RANSOMWARE: '#E63B3B',            // red
  MISCONFIG_EXPOSURE: '#E6A03B',    // amber
  PHISH_INITIAL_ACCESS: '#6BE69E',  // mint
  INSIDER_THREAT: '#3BC2E6',        // cyan
  UNCLASSIFIED: '#7A8294',          // gray
};

interface Anchor {
  type: IncidentType;
  angle: number;       // radians
  x: number;           // SVG coord
  y: number;
  labelX: number;      // 라벨 위치 (anchor 보다 약간 바깥)
  labelY: number;
  color: string;
}

interface TrailPoint {
  x: number;
  y: number;
  clueKey: string;
  label: string;
  depth: number;
  posterior: HypothesisScores;
  /** Phase P (KBW, 2026-05-27) — 노드 stage. */
  stage: number;
}

const trunc = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}…` : s);

/** root → currentLeaf path 수집. */
const collectPath = (
  nodes: Record<string, SerializedClueTreeNode>,
  rootId: string,
  leafId: string,
): SerializedClueTreeNode[] => {
  if (!nodes[leafId]) return nodes[rootId] ? [nodes[rootId]] : [];
  const chain: SerializedClueTreeNode[] = [];
  let cur: string | null = leafId;
  while (cur && nodes[cur]) {
    chain.push(nodes[cur]);
    cur = nodes[cur].parent_id;
  }
  return chain.reverse();
};

const IncidentTypeCompass = ({
  tree,
  currentLeafId,
  primaryIncident,
  confidenceReached = false,
  size,
  responsive = true,
  title = '사고유형 컴퍼스',
  headerRight,
  disabled = false,
  zone = 1,
  regressSuggested = false,
  coreClueLikelihood = 0,
}: IncidentTypeCompassProps) => {
  // ── 반응형: 부모 컨테이너 width 추적 ──
  const containerRef = useRef<HTMLDivElement>(null);
  const [measured, setMeasured] = useState<number>(size ?? 600);

  useEffect(() => {
    if (!responsive || size !== undefined) return;
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 600;
      // anchor 라벨 폭 여유 — 70px 빼고 min/max 클램프
      const s = Math.max(460, Math.min(780, Math.floor(w - 8)));
      setMeasured(s);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [responsive, size]);

  const effectiveSize = size ?? measured;

  // ── 레이아웃 계산 ──
  const center = effectiveSize / 2;
  const R = effectiveSize / 2 - 70;  // anchor 반지름 (라벨 여유 확보)
  const labelOffset = 28;            // 라벨 외곽 offset
  // depth 별 점진 확장 + 사후확률 temperature 평탄화 — 단서 누적이 적을 때
  // 모델이 너무 빨리 한 가설로 쏠리는 것을 시각만 부드럽게 표현.
  // ⚠ Bayes update 자체는 그대로 (e2e 회귀 0) — 시각화 calibration 만 적용.
  //
  // 사용자 비전 (2026-05-26):
  //   1. "단서 10개 정도는 찾아봐야 어느정도 갈피를 잡고 향하는 방향"
  //   2. "초기 이동 방향이 너무 큼 — 한 사고유형으로 치우치는 경향"
  //   → SATURATION_DEPTH 15 (이전 10), temperature scaling 추가.
  //
  // 학술 정합: P^(1/T) softmax temperature (calibration) — Platt 1999, Guo 2017.
  const SATURATION_DEPTH = 15;
  const MIN_RADIUS_FACTOR = 0.08;  // depth 1 → 8% 반지름 (이전 12% → 더 안쪽)

  /** depth 별 무게중심 최대 반지름 — sqrt 곡선 (초반 점진 + 후반 saturation). */
  const radiusForDepth = (depth: number): number => {
    if (depth <= 0) return 0;
    const t = Math.min(1, depth / SATURATION_DEPTH);
    const factor = MIN_RADIUS_FACTOR + (0.85 - MIN_RADIUS_FACTOR) * Math.sqrt(t);
    return R * factor;
  };

  /** depth 별 temperature — 깊을수록 T↓ (실제 분포에 가깝게).
   *  depth 1 → T=4 (매우 평탄), depth 5 → T=2.5, depth 10 → T=1.5, depth 15+ → T=1 (그대로). */
  const temperatureForDepth = (depth: number): number => {
    if (depth <= 0) return 5;
    if (depth >= SATURATION_DEPTH) return 1;
    // 4 → 1 으로 선형 감소
    const t = depth / SATURATION_DEPTH;
    return 4 - 3 * t;
  };

  /** P^(1/T) 으로 분포 평탄화. T>1 = 평탄, T=1 = 그대로. */
  const tempered = (
    posterior: HypothesisScores,
    T: number,
  ): Record<string, number> => {
    if (T <= 1) return posterior;
    const out: Record<string, number> = {};
    let total = 0;
    for (const t of INCIDENT_TYPES_ORDER) {
      const p = posterior[t] ?? 0;
      const v = Math.pow(Math.max(0, p), 1 / T);
      out[t] = v;
      total += v;
    }
    if (total <= 0) return posterior;
    for (const t of INCIDENT_TYPES_ORDER) {
      out[t] = out[t] / total;
    }
    return out;
  };

  // 8 anchor — 12시 시작, 시계방향 45° 간격
  const anchors: Anchor[] = useMemo(() => {
    return INCIDENT_TYPES_ORDER.map((type, i) => {
      const angle = -Math.PI / 2 + (i * 2 * Math.PI) / 8;
      return {
        type,
        angle,
        x: center + R * Math.cos(angle),
        y: center + R * Math.sin(angle),
        labelX: center + (R + labelOffset) * Math.cos(angle),
        labelY: center + (R + labelOffset) * Math.sin(angle),
        color: INCIDENT_COLORS[type],
      };
    });
  }, [center, R]);

  // 사후확률 → 무게중심 (anchor 들의 가중평균).
  // depth 별 temperature 평탄화 + 최대 반지름 클램프 — 초반 부드러운 진입.
  const posteriorToXY = (
    posterior: HypothesisScores,
    depth: number,
  ): { x: number; y: number } => {
    // depth 별 T 적용 → 평탄화된 분포로 무게중심 계산
    const T = temperatureForDepth(depth);
    const calibrated = tempered(posterior, T);

    // 사고유형 8 의 확률 정규화 (UNCLASSIFIED 제외 — calibrated 에서 이미 정규화됨)
    let weightSum = 0;
    for (const t of INCIDENT_TYPES_ORDER) weightSum += calibrated[t] ?? 0;
    if (weightSum <= 0) return { x: center, y: center };

    let dx = 0;
    let dy = 0;
    for (const t of INCIDENT_TYPES_ORDER) {
      const norm = (calibrated[t] ?? 0) / weightSum;
      const anchor = anchors.find((a) => a.type === t)!;
      dx += norm * (anchor.x - center);
      dy += norm * (anchor.y - center);
    }
    // depth 별 최대 반지름 클램프 (단서 적을 땐 중심 근처)
    const maxR = radiusForDepth(depth);
    const r = Math.sqrt(dx * dx + dy * dy);
    if (r > maxR && r > 0) {
      const scale = maxR / r;
      dx *= scale;
      dy *= scale;
    }
    // Phase M.2 — Zone 2 진입 시 점을 외부 원 부근으로 끌어올림 (paradigm §21.6).
    // 회귀 권고 중에는 boost 해제 (자연 위치로 복귀 — 사용자에게 모호함 시각화).
    // 방향은 보존하고 반지름만 최소 R*0.55 보장 (내부 원 밖, 외부 원 근처).
    if (zone === 2 && !regressSuggested && r > 0) {
      const minR = R * 0.55;
      const curR = Math.sqrt(dx * dx + dy * dy);
      if (curR < minR) {
        const scale = minR / curR;
        dx *= scale;
        dy *= scale;
      }
    }
    return { x: center + dx, y: center + dy };
  };

  // 궤적 — root → 각 채택 단서 → current.
  // Phase P (KBW, 2026-05-27) — stage 경계에서 중앙(center)으로 reset point 삽입.
  // 사용자 피드백: "다음 사고유형 단서 찾는거의 경우 다시 중앙에서 시작 다른색"
  const trail: TrailPoint[] = useMemo(() => {
    const path = collectPath(tree.nodes, tree.root_id, currentLeafId);
    const points: TrailPoint[] = [];
    let prevStage = 1;
    path.forEach((node, idx) => {
      const nodeStage = node.stage ?? 1;
      // stage 전환 시점 — 새 stage 시작 직전 "중앙 reset 마커" 삽입.
      // 이로써 trail polyline 이 외곽 → 중앙 → 새 방향 으로 꺾임.
      if (idx > 0 && nodeStage > prevStage) {
        points.push({
          x: center,
          y: center,
          clueKey: `__STAGE_RESET_${nodeStage}__`,
          label: `◆ Stage ${nodeStage} 시작`,
          depth: 0,
          posterior: { ...node.posterior_after, UNCLASSIFIED: 0 } as HypothesisScores,
          stage: nodeStage,
        });
      }
      const xy = posteriorToXY(node.posterior_after, node.depth);
      points.push({
        x: xy.x,
        y: xy.y,
        clueKey: node.clue_key,
        label: node.clue_key === '__ROOT__' ? '◆ 시작' : node.label,
        depth: node.depth,
        posterior: node.posterior_after,
        stage: nodeStage,
      });
      prevStage = nodeStage;
    });
    return points;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree.nodes, tree.root_id, currentLeafId, anchors, center]);

  /** trail 을 stage 별 세그먼트로 분할 — polyline 색 다르게 그릴 수 있도록.
   *  Phase P.12 (2026-05-27 사용자 피드백: "또 노드 끊어짐 현상 페이즈2 바뀔때"):
   *    Stage 경계점을 양쪽 segment 에 *공유* 시켜 시각적 연속성 보장.
   *    또한 단일 점 segment 도 그려지도록 인접 점 추가 (이전 끊김의 진짜 원인). */
  const trailSegments = useMemo(() => {
    if (trail.length < 2) return [];
    const segs: TrailPoint[][] = [];
    let cur: TrailPoint[] = [trail[0]];
    let curStage = trail[0].stage;
    for (let i = 1; i < trail.length; i++) {
      const p = trail[i];
      if (p.stage !== curStage) {
        // Stage 경계 — 새 점도 *이전 segment 의 마지막 점* 으로 추가 (연결성 ↑)
        cur.push(p);
        segs.push(cur);
        // 새 segment 는 경계점부터 시작
        cur = [p];
        curStage = p.stage;
      } else {
        cur.push(p);
      }
    }
    if (cur.length > 0) segs.push(cur);
    return segs;
  }, [trail]);

  const currentPos = trail.length > 0 ? trail[trail.length - 1] : null;
  // 사후확률 1위 anchor — 우측 신뢰도 패널과 일관성 보장.
  // (이전엔 무게중심에서 가장 가까운 anchor 였으나 다른 가설들의 분포 효과로
  //  1위 사고유형과 다를 수 있어 사용자 혼란 → 1위 가설 직접 사용으로 fix)
  const topAnchor = useMemo(() => {
    if (!currentPos) return null;
    const posterior = currentPos.posterior;
    let bestType: IncidentType | null = null;
    let bestProb = -1;
    for (const a of anchors) {
      const p = posterior[a.type] ?? 0;
      if (p > bestProb) {
        bestProb = p;
        bestType = a.type;
      }
    }
    return bestType ? anchors.find((a) => a.type === bestType) ?? null : null;
  }, [currentPos, anchors]);

  // 이전: 무게중심에서 가장 가까운 anchor (nearestAnchor) — 1위 가설과
  // 다를 수 있어 사용자 혼란 → topAnchor (사후확률 1위) 로 통일.

  return (
    <div className="border border-ink-700 bg-ink-950/40 flex flex-col">
      <div className="px-2.5 py-1.5 border-b border-ink-700 flex items-center justify-between shrink-0">
        <span className="text-[10px] text-ink-400 font-mono font-semibold uppercase tracking-[0.14em]">
          {title}
          <span className="ml-2 text-[9.5px] text-ink-500 normal-case tracking-normal">
            depth {Math.max(0, trail.length - 1)} · 8 사고유형 360°
            {/* Phase M.2 — Zone 배지 */}
            <span
              className={
                'ml-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[9px] font-semibold ' +
                (zone === 2 && !regressSuggested
                  ? 'bg-emerald-900/40 text-emerald-300 border border-emerald-600/40'
                  : 'bg-amber-900/30 text-amber-300/80 border border-amber-700/30')
              }
              title={
                zone === 2 && !regressSuggested
                  ? '코어 단서 발견 — 사고유형 chain 구체화 단계'
                  : '광범위 탐색 — 단서 누적 중'
              }
            >
              {zone === 2 && !regressSuggested ? '🗺 Zone 2' : 'Zone 1'}
            </span>
            {regressSuggested && (
              <span
                className="ml-1 inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[9px] font-semibold bg-amber-900/40 text-amber-300 border border-amber-600/40"
                title="entropy 상승 또는 가설 격차 축소 — 광범위 탐색 복귀 권고"
              >
                ⤺ 회귀 권고
              </span>
            )}
            {topAnchor && (
              <>
                {' '}· 1위
                <span
                  className="ml-1"
                  style={{ color: topAnchor.color }}
                >
                  {INCIDENT_KO[topAnchor.type]}
                </span>
                {currentPos && (
                  <span className="ml-1 text-ink-500">
                    ({((currentPos.posterior[topAnchor.type] ?? 0) * 100).toFixed(1)}%)
                  </span>
                )}
              </>
            )}
          </span>
        </span>
        {headerRight}
      </div>
      <div
        ref={containerRef}
        className="relative flex items-center justify-center"
        style={{ minHeight: effectiveSize }}
      >
        <svg
          width={effectiveSize}
          height={effectiveSize}
          viewBox={`0 0 ${effectiveSize} ${effectiveSize}`}
          style={{ display: 'block' }}
        >
          {/* 단위원 외곽 (Zone 2 영역 경계) — zone===2 일 때 강조 */}
          <circle
            cx={center}
            cy={center}
            r={R}
            fill="none"
            stroke={
              zone === 2 && !regressSuggested
                ? 'rgba(38, 194, 129, 0.55)'
                : 'rgba(120, 130, 150, 0.18)'
            }
            strokeWidth={zone === 2 && !regressSuggested ? 1.5 : 1}
            strokeDasharray={zone === 2 && !regressSuggested ? '6 4' : '3 4'}
            style={{ transition: 'stroke 320ms ease, stroke-width 320ms ease' }}
          />
          {/* Phase M.2 — 내부 보조원 = Zone 1 경계 (paradigm §21.6) */}
          <circle
            cx={center}
            cy={center}
            r={R * 0.5}
            fill="none"
            stroke={
              zone === 1
                ? 'rgba(255, 149, 0, 0.32)'
                : 'rgba(120, 130, 150, 0.10)'
            }
            strokeWidth={1}
            strokeDasharray="4 4"
            style={{ transition: 'stroke 320ms ease' }}
          />
          {/* Zone 라벨 — 내부 원 위쪽 (Zone 1) 또는 외부 원 위쪽 (Zone 2) */}
          {zone === 1 && (
            <text
              x={center}
              y={center - R * 0.5 - 6}
              fill="rgba(255, 149, 0, 0.6)"
              fontSize={9}
              fontWeight={600}
              textAnchor="middle"
              style={{ fontFamily: 'system-ui, sans-serif', letterSpacing: '0.05em' }}
            >
              Zone 1 · 광범위 탐색
            </text>
          )}
          {zone === 2 && !regressSuggested && (
            <text
              x={center}
              y={center - R - 10}
              fill="#26C281"
              fontSize={10.5}
              fontWeight={700}
              textAnchor="middle"
              style={{ fontFamily: 'system-ui, sans-serif', letterSpacing: '0.03em' }}
            >
              🗺 Zone 2 · 사고유형 chain 구체화
            </text>
          )}

          {/* 8 방향 분할선 */}
          {anchors.map((a) => (
            <line
              key={`spoke-${a.type}`}
              x1={center}
              y1={center}
              x2={a.x}
              y2={a.y}
              stroke="rgba(120, 130, 150, 0.10)"
              strokeWidth={0.8}
              strokeDasharray="2 4"
            />
          ))}

          {/* 8 anchor — 사고유형 점 + 라벨. 1위 anchor 강조 (우측 신뢰도 패널 정합). */}
          {anchors.map((a) => {
            const isTop = topAnchor?.type === a.type;
            const isPrimary =
              confidenceReached && primaryIncident === a.type;
            const dotR = isPrimary ? 9 : isTop ? 7 : 5;
            // 표시 변수 통일 (legacy isNearest 명 → isTop 의미)
            const isNearest = isTop;
            return (
              <g key={`anchor-${a.type}`}>
                {/* glow (confidence 도달 시) */}
                {isPrimary && (
                  <circle
                    cx={a.x}
                    cy={a.y}
                    r={18}
                    fill={a.color}
                    opacity={0.15}
                  >
                    <animate
                      attributeName="r"
                      values="14;22;14"
                      dur="2.4s"
                      repeatCount="indefinite"
                    />
                    <animate
                      attributeName="opacity"
                      values="0.10;0.28;0.10"
                      dur="2.4s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
                <circle
                  cx={a.x}
                  cy={a.y}
                  r={dotR}
                  fill={a.color}
                  fillOpacity={isPrimary ? 1 : isNearest ? 0.85 : 0.55}
                  stroke={a.color}
                  strokeWidth={isPrimary ? 2 : 1}
                />
                {/* 라벨 — anchor 의 각도에 따라 anchor 외곽 위치에 텍스트 정렬.
                    Phase P (KBW) — Kill Chain phase 번호 prefix 로 인접 의미 시각화. */}
                {(() => {
                  // text-anchor 결정 (각도 기반)
                  const cosA = Math.cos(a.angle);
                  let textAnchor: 'start' | 'middle' | 'end' = 'middle';
                  if (cosA > 0.3) textAnchor = 'start';
                  else if (cosA < -0.3) textAnchor = 'end';
                  const phase = KILL_CHAIN_PHASE[a.type];
                  return (
                    <>
                      <text
                        x={a.labelX}
                        y={a.labelY - 6}
                        fill={isPrimary ? a.color : 'rgba(160, 170, 185, 0.7)'}
                        fontSize={8.5}
                        fontWeight={700}
                        textAnchor={textAnchor}
                        dominantBaseline="middle"
                        style={{
                          fontFamily: 'system-ui, sans-serif',
                          letterSpacing: '0.05em',
                        }}
                      >
                        P{phase}
                      </text>
                      <text
                        x={a.labelX}
                        y={a.labelY + 6}
                        fill={isPrimary ? a.color : 'rgba(220, 225, 235, 0.85)'}
                        fontSize={11}
                        fontWeight={isPrimary ? 700 : 600}
                        textAnchor={textAnchor}
                        dominantBaseline="middle"
                        style={{ fontFamily: 'system-ui, sans-serif' }}
                      >
                        {INCIDENT_KO[a.type]}
                      </text>
                    </>
                  );
                })()}
              </g>
            );
          })}

          {/* 궤적 — stage 별 세그먼트로 폴리라인 분할 (Phase P, KBW).
              각 stage 가 자체 색상으로 그려져 "다음 트리" 인상 강화.
              Phase P.10 (2026-05-27 사용자 피드백: "이전 사고유형 선이 안 보임") —
              과거 segment 의 가시성 강화: opacity 0.42→0.72, dasharray 제거 (실선),
              strokeWidth 1.8→2.2 로 두께 증가. */}
          {trailSegments.map((seg, si) => {
            if (seg.length < 2) return null;
            const sc = stageColor(seg[0].stage);
            const isLatest = si === trailSegments.length - 1;
            return (
              <polyline
                key={`trail-seg-${si}`}
                points={seg.map((t) => `${t.x.toFixed(1)},${t.y.toFixed(1)}`).join(' ')}
                fill="none"
                stroke={sc.fill}
                strokeWidth={isLatest ? 2.8 : 2.4}
                strokeOpacity={isLatest ? 0.92 : 0.78}
                // Phase P.17 (사용자 피드백: "회귀권고에서도 오류가 있어 노드가 깨지는데")
                //   기존 dasharray "6 2" 가 점간 거리 짧을 때 (depth 1-3 근방) 끊겨 보임 →
                //   회귀권고/Zone1 케이스에서 polyline 이 안 보이는 버그.
                //   변경: 모든 segment 실선. stage 구분은 stroke 색 + opacity 로만.
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            );
          })}

          {/* 궤적 점 — 각 채택 단서. stage 별 색상. */}
          {trail.map((t, i) => {
            const isCurrent = i === trail.length - 1;
            const isRoot = i === 0;
            const isResetMarker = t.clueKey.startsWith('__STAGE_RESET_');
            const sc = stageColor(t.stage);
            return (
              <g key={`trail-${i}`}>
                {isCurrent && (
                  <circle
                    cx={t.x}
                    cy={t.y}
                    r={14}
                    fill={sc.fill}
                    opacity={0.18}
                  >
                    <animate
                      attributeName="r"
                      values="10;16;10"
                      dur="1.8s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
                {/* stage reset 마커 — 중앙에 큰 ◆ + stage 라벨 */}
                {isResetMarker ? (
                  <>
                    <circle
                      cx={t.x}
                      cy={t.y}
                      r={10}
                      fill={sc.fill}
                      fillOpacity={0.18}
                      stroke={sc.stroke}
                      strokeWidth={1.5}
                      strokeDasharray="3 2"
                    />
                    <text
                      x={t.x}
                      y={t.y + 4}
                      fill={sc.stroke}
                      fontSize={13}
                      fontWeight={800}
                      textAnchor="middle"
                      style={{ fontFamily: 'system-ui, sans-serif' }}
                    >
                      ◆
                    </text>
                    <text
                      x={t.x}
                      y={t.y - 16}
                      fill={sc.stroke}
                      fontSize={10}
                      fontWeight={700}
                      textAnchor="middle"
                      style={{ fontFamily: 'system-ui, sans-serif' }}
                    >
                      {sc.label} 시작
                    </text>
                  </>
                ) : (
                  <circle
                    cx={t.x}
                    cy={t.y}
                    r={isCurrent ? 6 : isRoot ? 4.5 : 4}
                    fill={isCurrent ? sc.fill : isRoot ? '#FF9500' : sc.fill}
                    fillOpacity={isCurrent ? 1 : isRoot ? 1 : 0.55}
                    stroke={isCurrent ? sc.stroke : isRoot ? '#FFB04D' : sc.fill}
                    strokeWidth={isCurrent ? 1.5 : 1}
                    style={isCurrent ? { transition: 'cx 360ms ease, cy 360ms ease' } : undefined}
                  />
                )}
                {/* depth 번호 (reset 마커 제외)
                 *  Phase P.17 — trail index `i` 대신 t.depth 사용.
                 *  RESET 마커가 삽입되면 i 가 점프 (1,2,4) → 사용자 혼란.
                 *  depth 는 실제 단서 순서라 RESET 무관하게 1,2,3,4 연속. */}
                {!isRoot && !isResetMarker && (
                  <text
                    x={t.x + 8}
                    y={t.y - 6}
                    fill="rgba(180, 200, 210, 0.65)"
                    fontSize={9}
                    fontWeight={600}
                    style={{ fontFamily: 'system-ui, sans-serif' }}
                  >
                    {t.depth}
                  </text>
                )}
                {/* 현재 위치 단서 라벨 */}
                {isCurrent && !isRoot && !isResetMarker && (
                  <text
                    x={t.x}
                    y={t.y + 22}
                    fill={sc.stroke}
                    fontSize={10.5}
                    fontWeight={700}
                    textAnchor="middle"
                    style={{ fontFamily: 'system-ui, sans-serif' }}
                  >
                    {trunc(t.label, 18)}
                  </text>
                )}
              </g>
            );
          })}

          {/* 중앙 ◆ 표식 (uniform 시작점) — 단서 0개일 때만 */}
          {trail.length <= 1 && (
            <g>
              <text
                x={center}
                y={center + 5}
                fill="#FF9500"
                fontSize={28}
                textAnchor="middle"
                style={{ fontFamily: 'system-ui, sans-serif' }}
              >
                ◆
              </text>
              <text
                x={center}
                y={center + 30}
                fill="rgba(180, 200, 210, 0.55)"
                fontSize={10}
                textAnchor="middle"
                style={{ fontFamily: 'system-ui, sans-serif' }}
              >
                수사 시작 (Uniform 1/8)
              </text>
            </g>
          )}
        </svg>

        {/* 비활성 오버레이 */}
        {disabled && (
          <div className="absolute inset-0 bg-ink-950/40 flex items-center justify-center">
            <span className="text-[11px] text-ink-400 font-mono">처리 중…</span>
          </div>
        )}
      </div>
      {/* 하단 안내 — zone 별 메시지 (paradigm §21.4) */}
      <div className="px-2.5 py-1.5 border-t border-ink-700 text-[9.5px] text-ink-500 leading-4 font-mono">
        {zone === 2 && !regressSuggested ? (
          <>
            🗺 <span className="text-emerald-300 font-semibold">Zone 2</span> — 코어 단서 발견 (P(c|h)={(coreClueLikelihood * 100).toFixed(0)}%).
            Top 가설 chain 으로 다음 단서를 좁혀가세요
          </>
        ) : regressSuggested ? (
          <>
            ⤺ <span className="text-amber-300 font-semibold">회귀 권고</span> — entropy 상승/가설 격차 축소로 다시 모호.
            Zone 1 으로 돌아가 광범위 탐색 권장
          </>
        ) : (
          <>
            🧭 <span className="text-amber-300 font-semibold">Zone 1</span> — 사후확률 가중 무게중심.
            맵 탐색 (depth ≥ 3) + 코어 단서 (P(c|h) ≥ 45%) 모두 충족 시 Zone 2 진입
          </>
        )}
        {confidenceReached && primaryIncident && (
          <span className="ml-2 text-brand-teal font-semibold">
            · {INCIDENT_KO[primaryIncident]} 방향 도달 ✓
          </span>
        )}
      </div>
    </div>
  );
};

export default IncidentTypeCompass;
