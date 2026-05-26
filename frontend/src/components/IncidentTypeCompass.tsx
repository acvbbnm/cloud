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
 * 8 사고유형 시계방향 배치 (12시 시작):
 *     12  CREDENTIAL_THEFT
 *   1:30  PRIVILEGE_ESCALATION
 *      3  DATA_EXFILTRATION
 *   4:30  AUDIT_LOG_TAMPERING
 *      6  RANSOMWARE
 *   7:30  MISCONFIG_EXPOSURE
 *      9  PHISH_INITIAL_ACCESS
 *  10:30  INSIDER_THREAT
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
}

const INCIDENT_TYPES_ORDER: IncidentType[] = [
  'CREDENTIAL_THEFT',      // 12시
  'PRIVILEGE_ESCALATION',  // 1:30
  'DATA_EXFILTRATION',     // 3시
  'AUDIT_LOG_TAMPERING',   // 4:30
  'RANSOMWARE',            // 6시
  'MISCONFIG_EXPOSURE',    // 7:30
  'PHISH_INITIAL_ACCESS',  // 9시
  'INSIDER_THREAT',        // 10:30
];

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
  const trailMaxRadius = R * 0.85;   // 무게중심이 닿을 수 있는 최대 반지름

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
  // UNCLASSIFIED 제외 후 정규화한 분포 사용.
  const posteriorToXY = (
    posterior: HypothesisScores,
  ): { x: number; y: number } => {
    // 사고유형 8 의 확률 정규화 (UNCLASSIFIED 제외)
    const incidents = INCIDENT_TYPES_ORDER.map((t) => ({
      type: t,
      p: posterior[t] ?? 0,
    }));
    const total = incidents.reduce((s, e) => s + e.p, 0);
    if (total <= 0) {
      return { x: center, y: center };
    }
    let dx = 0;
    let dy = 0;
    for (const { type, p } of incidents) {
      const norm = p / total;
      const anchor = anchors.find((a) => a.type === type)!;
      dx += norm * (anchor.x - center);
      dy += norm * (anchor.y - center);
    }
    // 최대 반지름 클램프 (시각 안정성)
    const r = Math.sqrt(dx * dx + dy * dy);
    if (r > trailMaxRadius) {
      const scale = trailMaxRadius / r;
      dx *= scale;
      dy *= scale;
    }
    return { x: center + dx, y: center + dy };
  };

  // 궤적 — root → 각 채택 단서 → current
  const trail: TrailPoint[] = useMemo(() => {
    const path = collectPath(tree.nodes, tree.root_id, currentLeafId);
    return path.map((node) => {
      const xy = posteriorToXY(node.posterior_after);
      return {
        x: xy.x,
        y: xy.y,
        clueKey: node.clue_key,
        label: node.clue_key === '__ROOT__' ? '◆ 시작' : node.label,
        depth: node.depth,
        posterior: node.posterior_after,
      };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree.nodes, tree.root_id, currentLeafId, anchors]);

  const currentPos = trail.length > 0 ? trail[trail.length - 1] : null;
  // 가장 가까운 anchor (현재 위치 기준)
  const nearestAnchor = useMemo(() => {
    if (!currentPos) return null;
    let best: Anchor | null = null;
    let bestDist = Infinity;
    for (const a of anchors) {
      const d = Math.hypot(a.x - currentPos.x, a.y - currentPos.y);
      if (d < bestDist) {
        bestDist = d;
        best = a;
      }
    }
    return best;
  }, [currentPos, anchors]);

  return (
    <div className="border border-ink-700 bg-ink-950/40 flex flex-col">
      <div className="px-2.5 py-1.5 border-b border-ink-700 flex items-center justify-between shrink-0">
        <span className="text-[10px] text-ink-400 font-mono font-semibold uppercase tracking-[0.14em]">
          {title}
          <span className="ml-2 text-[9.5px] text-ink-500 normal-case tracking-normal">
            depth {Math.max(0, trail.length - 1)} · 8 사고유형 360°
            {nearestAnchor && (
              <>
                {' '}· 방향
                <span
                  className="ml-1"
                  style={{ color: nearestAnchor.color }}
                >
                  {INCIDENT_KO[nearestAnchor.type]}
                </span>
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
          {/* 단위원 외곽 (점선) */}
          <circle
            cx={center}
            cy={center}
            r={R}
            fill="none"
            stroke="rgba(120, 130, 150, 0.18)"
            strokeWidth={1}
            strokeDasharray="3 4"
          />
          {/* 내부 보조원 — 50% 신뢰 영역 */}
          <circle
            cx={center}
            cy={center}
            r={R * 0.5}
            fill="none"
            stroke="rgba(120, 130, 150, 0.08)"
            strokeWidth={1}
          />

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

          {/* 8 anchor — 사고유형 점 + 라벨 */}
          {anchors.map((a) => {
            const isNearest = nearestAnchor?.type === a.type;
            const isPrimary =
              confidenceReached && primaryIncident === a.type;
            const dotR = isPrimary ? 9 : isNearest ? 7 : 5;
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
                {/* 라벨 — anchor 의 각도에 따라 anchor 외곽 위치에 텍스트 정렬 */}
                {(() => {
                  // text-anchor 결정 (각도 기반)
                  const cosA = Math.cos(a.angle);
                  let textAnchor: 'start' | 'middle' | 'end' = 'middle';
                  if (cosA > 0.3) textAnchor = 'start';
                  else if (cosA < -0.3) textAnchor = 'end';
                  return (
                    <text
                      x={a.labelX}
                      y={a.labelY}
                      fill={isPrimary ? a.color : 'rgba(220, 225, 235, 0.85)'}
                      fontSize={11}
                      fontWeight={isPrimary ? 700 : 600}
                      textAnchor={textAnchor}
                      dominantBaseline="middle"
                      style={{ fontFamily: 'system-ui, sans-serif' }}
                    >
                      {INCIDENT_KO[a.type]}
                    </text>
                  );
                })()}
              </g>
            );
          })}

          {/* 궤적 — 단서 시퀀스 연결 폴리라인 */}
          {trail.length >= 2 && (
            <polyline
              points={trail.map((t) => `${t.x.toFixed(1)},${t.y.toFixed(1)}`).join(' ')}
              fill="none"
              stroke="#26C281"
              strokeWidth={1.6}
              strokeOpacity={0.65}
              strokeDasharray="4 3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* 궤적 점 — 각 채택 단서 */}
          {trail.map((t, i) => {
            const isCurrent = i === trail.length - 1;
            const isRoot = i === 0;
            return (
              <g key={`trail-${i}`}>
                {isCurrent && (
                  <circle
                    cx={t.x}
                    cy={t.y}
                    r={14}
                    fill="#26C281"
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
                <circle
                  cx={t.x}
                  cy={t.y}
                  r={isCurrent ? 6 : isRoot ? 4.5 : 4}
                  fill={isCurrent ? '#26C281' : isRoot ? '#FF9500' : 'rgba(38, 194, 129, 0.55)'}
                  stroke={isCurrent ? '#34D399' : 'rgba(38, 194, 129, 0.8)'}
                  strokeWidth={isCurrent ? 1.5 : 1}
                />
                {/* depth 번호 */}
                {!isRoot && (
                  <text
                    x={t.x + 8}
                    y={t.y - 6}
                    fill="rgba(180, 200, 210, 0.65)"
                    fontSize={9}
                    fontWeight={600}
                    style={{ fontFamily: 'system-ui, sans-serif' }}
                  >
                    {i}
                  </text>
                )}
                {/* 현재 위치 단서 라벨 */}
                {isCurrent && !isRoot && (
                  <text
                    x={t.x}
                    y={t.y + 22}
                    fill="#26C281"
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
      {/* 하단 안내 */}
      <div className="px-2.5 py-1.5 border-t border-ink-700 text-[9.5px] text-ink-500 leading-4 font-mono">
        🧭 사후확률 가중 무게중심 — 단서가 누적될수록 한 사고유형 방향으로 수렴
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
