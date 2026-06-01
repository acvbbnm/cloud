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

import { INCIDENT_TYPES_KILL_CHAIN_ORDER } from '@/types';
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
  // ─── P.35.4 (2026-05-31) — trail point 클릭 핸들러 ──────────────
  /** trail point 클릭 — 부모가 단서 detail / 적재 로그 매칭 표시.
   *  사용자 비전: "컴파스 점 클릭하면 그 로그에 대한 정보가 자세히 보이게". */
  onTrailPointClick?: (point: {
    clue_key: string;
    label: string;
    stage: number;
    posterior: HypothesisScores;
  }) => void;
  /** 강조 표시할 단서 (외부 LogPanel 클릭 시 그 단서 점에 ring 추가). */
  highlightedClueKey?: string | null;
}

// R.2 (hard, 2026-05-28) — 단일 소스 import (types/index.ts).
// 사고유형 추가/순서 변경 시 types 한 곳만 수정하면 모든 컴포넌트 동기.
// 도메인 타입 narrowing: Exclude<IncidentType, 'UNCLASSIFIED'> 라 UI 분기 안전.
const INCIDENT_TYPES_ORDER: ReadonlyArray<Exclude<IncidentType, 'UNCLASSIFIED'>> =
  INCIDENT_TYPES_KILL_CHAIN_ORDER;

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
  /** 전역 누적 depth (라벨 표시용 — 1,2,3,4 연속). */
  depth: number;
  /** stage 내 순번 (좌표 반지름 계산용 — stage 전환 시 1 부터 재시작). */
  stageDepth: number;
  posterior: HypothesisScores;
  /** Phase P (KBW, 2026-05-27) — 노드 stage. */
  stage: number;
}

const trunc = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}…` : s);

/** root → currentLeaf path 수집.
 *
 * P.18 안전망: backend parent_id 체인이 중간에 끊겨 root 도달 못하는 케이스에서
 * trail[0] 이 root 가 아니고 isRoot 분기 + 중앙 ◆ 가 모두 실패하는 증상 방어.
 * root 노드가 tree.nodes 에 있으면 chain 의 첫 노드로 강제 prepend.
 */
const collectPath = (
  nodes: Record<string, SerializedClueTreeNode>,
  rootId: string,
  leafId: string,
): SerializedClueTreeNode[] => {
  const rootNode = nodes[rootId] ?? null;
  if (!nodes[leafId]) return rootNode ? [rootNode] : [];
  const chain: SerializedClueTreeNode[] = [];
  let cur: string | null = leafId;
  while (cur && nodes[cur]) {
    chain.push(nodes[cur]);
    cur = nodes[cur].parent_id;
  }
  chain.reverse();
  if (rootNode && chain[0]?.node_id !== rootNode.node_id) {
    chain.unshift(rootNode);
  }
  return chain;
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
  // V1.fix.17 — coreClueLikelihood 하단 부연 라벨 삭제로 미사용. 시그너처는 호환 유지.
  coreClueLikelihood: _coreClueLikelihood = 0,
  onTrailPointClick,
  highlightedClueKey,
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
  // P.26 (2026-05-31 사용자 피드백: "좌우 데이터유출/권한상승 글자 짤림") —
  //   기존 마진 70 → 100. P3 (3시) / P6 (9시) 라벨 폭 70px (textAnchor=start/end)
  //   가 화면 좌우 끝까지 안전하게 여유 확보.
  const R = effectiveSize / 2 - 100;  // anchor 반지름 (좌우 라벨 짤림 fix)
  const labelOffset = 28;             // 라벨 외곽 offset
  // depth 별 점진 확장 + 사후확률 temperature 평탄화 — 단서 누적이 적을 때
  // 모델이 너무 빨리 한 가설로 쏠리는 것을 시각만 부드럽게 표현.
  // ⚠ Bayes update 자체는 그대로 (e2e 회귀 0) — 시각화 calibration 만 적용.
  //
  // 사용자 비전:
  //   1. "단서 10개 정도는 찾아봐야 어느정도 갈피를 잡고 향하는 방향" (2026-05-26)
  //   2. "초기 이동 방향이 너무 큼 — 한 사고유형으로 치우치는 경향" (2026-05-26)
  //   3. V1.fix.22 (2026-06-01) — "노드를 많이 움직이게 + Zone 1 (외곽) 에 더 빨리 도달".
  //      SATURATION 15 → 8, MIN_RADIUS 8% → 22%, temperature 시작 4 → 2.5.
  //      효과: 단서 1개 채택 시 22% 반지름 (즉시 가시), 8개에서 최대 도달.
  //
  // 학술 정합: P^(1/T) softmax temperature (calibration) — Platt 1999, Guo 2017.
  const SATURATION_DEPTH = 8;        // V1.fix.22 — 15 → 8 (8 단서에서 외곽 도달)
  const MIN_RADIUS_FACTOR = 0.22;    // V1.fix.22 — 0.08 → 0.22 (초기부터 잘 보임)

  /** depth 별 무게중심 최대 반지름 — sqrt 곡선 (초반 점진 + 후반 saturation). */
  const radiusForDepth = (depth: number): number => {
    if (depth <= 0) return 0;
    const t = Math.min(1, depth / SATURATION_DEPTH);
    const factor = MIN_RADIUS_FACTOR + (0.90 - MIN_RADIUS_FACTOR) * Math.sqrt(t);
    return R * factor;
  };

  /** depth 별 temperature — V1.fix.22: 2.5 → 1 으로 빠르게 감소 (초기부터 우세 가설 반영).
   *  depth 1 → T≈2.3, depth 4 → T≈1.6, depth 8+ → T=1 (그대로). */
  const temperatureForDepth = (depth: number): number => {
    if (depth <= 0) return 3;
    if (depth >= SATURATION_DEPTH) return 1;
    // 2.5 → 1 으로 선형 감소
    const t = depth / SATURATION_DEPTH;
    return 2.5 - 1.5 * t;
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
  //
  // ⚠ 재설계 (2026-05-27, KBW — "노드 바깥 퍼지고 끊김" 버그 수정):
  //   좌표는 **posterior + stageDepth 만** 으로 결정론적 계산.
  //   zone/regress 전역 상태 의존 제거 (이전 zone 2 boost R*0.55 가 Zone 전환·
  //   회귀 on/off·stage 전환 시 점을 외곽으로 강제 이동 → 점프·뭉침의 원흉).
  //   Zone 2 강조는 외곽 원·배지 시각으로만 — 점 위치는 건드리지 않음.
  //
  //   stageDepth = 그 stage 내 단서 순번. stage 전환 시 1 부터 재시작 →
  //   "다시 중앙에서 시작" 자연 표현 (radiusForDepth 가 작은 반지름부터).
  const posteriorToXY = (
    posterior: HypothesisScores,
    stageDepth: number,
  ): { x: number; y: number } => {
    // stageDepth 별 T 적용 → 평탄화된 분포로 무게중심 계산
    const T = temperatureForDepth(stageDepth);
    const calibrated = tempered(posterior, T);

    // 사고유형 8 의 확률 정규화 (UNCLASSIFIED 제외 — calibrated 에서 이미 정규화됨)
    let weightSum = 0;
    for (const t of INCIDENT_TYPES_ORDER) weightSum += calibrated[t] ?? 0;
    if (weightSum <= 0) return { x: center, y: center };

    let dx = 0;
    let dy = 0;
    for (const t of INCIDENT_TYPES_ORDER) {
      const norm = (calibrated[t] ?? 0) / weightSum;
      const anchor = anchors.find((a) => a.type === t);
      if (!anchor) continue;
      dx += norm * (anchor.x - center);
      dy += norm * (anchor.y - center);
    }
    // stageDepth 별 최대 반지름 클램프 (단서 적을 땐 중심 근처, 누적되면 외곽).
    const maxR = radiusForDepth(stageDepth);
    const r = Math.sqrt(dx * dx + dy * dy);
    if (r > maxR && r > 0) {
      const scale = maxR / r;
      dx *= scale;
      dy *= scale;
    }
    return { x: center + dx, y: center + dy };
  };

  // 궤적 — root → 각 채택 단서 → current.
  //
  // ⚠ 재설계 (2026-05-27, KBW): RESET 마커 삽입 제거.
  //   이전엔 stage 전환 시 중앙(center) RESET 마커를 trail 에 끼워넣어
  //   polyline 이 외곽→중앙→외곽 으로 점프 + segment 끊김 발생.
  //   대신 stageDepth (stage 내 순번) 를 부여해 stage 전환 시 좌표가 자연히
  //   중앙 근처(작은 반지름)에서 다시 시작하도록 함. 마커 불필요.
  const trail: TrailPoint[] = useMemo(() => {
    const path = collectPath(tree.nodes, tree.root_id, currentLeafId);
    // stage 별 순번 카운터 — stage 전환 시 1 부터 재시작
    const stageCounter: Record<number, number> = {};
    return path.map((node) => {
      const nodeStage = node.stage ?? 1;
      const isRoot = node.clue_key === '__ROOT__';
      // root 는 stageDepth 0, 그 외는 stage 내 순번 증가
      let stageDepth = 0;
      if (!isRoot) {
        stageCounter[nodeStage] = (stageCounter[nodeStage] ?? 0) + 1;
        stageDepth = stageCounter[nodeStage];
      }
      const xy = posteriorToXY(node.posterior_after, stageDepth);
      return {
        x: xy.x,
        y: xy.y,
        clueKey: node.clue_key,
        label: isRoot ? '◆ 시작' : node.label,
        depth: node.depth,
        stageDepth,
        posterior: node.posterior_after,
        stage: nodeStage,
      };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree.nodes, tree.root_id, currentLeafId, anchors, center]);

  /** trail 을 stage 별 세그먼트로 분할 — stage 마다 독립 polyline (다른 색).
   *  재설계 (2026-05-27, KBW): 경계점 공유·RESET 마커 모두 제거. 순수 stage group.
   *  stage 전환 = 새 색 polyline 이 중앙 근처에서 시작 (stageDepth 1 부터).
   *  단일 점 stage 는 polyline 없이 점만 렌더 (아래 trail.map 이 처리). */
  const trailSegments = useMemo(() => {
    if (trail.length < 2) return [];
    const segs: TrailPoint[][] = [];
    let cur: TrailPoint[] = [trail[0]];
    let curStage = trail[0].stage;
    for (let i = 1; i < trail.length; i++) {
      const p = trail[i];
      if (p.stage !== curStage) {
        segs.push(cur);
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

  // P.32 (2026-05-31 사용자 피드백: "그림상으론 zone1 나가지도 못했는데
  //   zone2 활성화되어있는데") — 시각화-판정 불일치 fix.
  //
  // 원인:
  //   · 백엔드 zone 판정 = core_clue_likelihood ≥ 0.25 (TRIGGER_MIN_LIKELIHOOD,
  //     zone_logic.py §11). 단서 1개만 강해도 Zone 2 promote.
  //   · 시각화 점 위치 = posteriorToXY + radiusForDepth(stageDepth) 클램프.
  //     stageDepth 적으면 반지름이 R*0.08 ~ R*0.35 → 내부 보조원(R*0.5) 안쪽.
  //   · 두 신호가 같은 양(확신도)을 표현하지 않아 그림과 라벨이 모순.
  //
  // 해결: 시각화 zone (visualZone2) 을 점 반지름으로 재계산.
  //   현재 점이 내부원 R*0.5 이내면 visualZone2=false → 헤더 배지·외곽원·
  //   라벨 모두 Zone 1 톤으로 표시. 백엔드 zone 판정은 그대로 (회귀 등 다른
  //   로직 영향 X). 시각만 일관성 맞춤.
  //
  // 추가 표시:
  //   백엔드가 zone=2 인데 시각으로 아직 Zone 1 안쪽이면 "Zone 1+ · 코어 단서
  //   검출, 단서 누적 권장" 안내 — 수사관이 다음 행동(단서 추가) 유도.
  //
  // KBW 회귀 방지: 점 좌표 계산 (posteriorToXY) 은 zone 의존 제거된 상태 유지.
  //   visualZone2 는 *결과만* 읽음 — 좌표를 zone 으로 보정하지 않음.
  const currentRadius = currentPos
    ? Math.sqrt(
        Math.pow(currentPos.x - center, 2) + Math.pow(currentPos.y - center, 2),
      )
    : 0;
  const currentRadiusRatio = R > 0 ? currentRadius / R : 0;
  // 시각화 zone — 점이 내부원(R*0.5) 바깥일 때만 Zone 2 시각.
  const visualZone2 = zone === 2 && currentRadiusRatio >= 0.5;
  // 백엔드 zone=2 인데 시각상 안쪽 — 보스단서 검출은 됐지만 무게중심은 아직.
  const visualZoneHalf = zone === 2 && !visualZone2 && !regressSuggested;

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
          {/* V1.fix.17 (2026-06-01) — "depth N · 8 사고유형 360°" + "Zone 1+ (코어단서)
              · 1위 권한 상승(84.6%)" 부연 라벨 제거. 사용자: "다른 곳에서 확인 가능".
              Zone 배지만 간결하게 유지 (1·2 구분만). */}
          <span
            className={
              'ml-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[9px] font-semibold normal-case tracking-normal ' +
              (visualZone2
                ? 'bg-emerald-900/40 text-emerald-300 border border-emerald-600/40'
                : visualZoneHalf
                  ? 'bg-sky-900/30 text-sky-300/80 border border-sky-700/30'
                  : 'bg-amber-900/30 text-amber-300/80 border border-amber-700/30')
            }
          >
            {visualZone2
              ? 'Zone 2'
              : regressSuggested
                ? 'Zone 1'
                : 'Zone 1'}
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
          {/* 단위원 외곽 (Zone 2 영역 경계) — visualZone2 일 때만 강조.
              P.32 — zone === 2 가 아니라 visualZone2 사용 (점이 외곽일 때만). */}
          <circle
            cx={center}
            cy={center}
            r={R}
            fill="none"
            stroke={
              visualZone2
                ? 'rgba(38, 194, 129, 0.55)'
                : visualZoneHalf
                  ? 'rgba(56, 189, 248, 0.30)'  // sky — 코어단서는 검출, 무게중심은 아직
                  : 'rgba(120, 130, 150, 0.18)'
            }
            strokeWidth={visualZone2 ? 1.5 : 1}
            strokeDasharray={visualZone2 ? '6 4' : '3 4'}
            style={{ transition: 'stroke 320ms ease, stroke-width 320ms ease' }}
          />
          {/* Phase M.2 — 내부 보조원 = Zone 1 경계 (paradigm §21.6).
              P.32 — visualZone2 가 아닐 땐 (zone=1 또는 zone=2+안쪽) 강조 유지. */}
          <circle
            cx={center}
            cy={center}
            r={R * 0.5}
            fill="none"
            stroke={
              !visualZone2
                ? 'rgba(255, 149, 0, 0.32)'
                : 'rgba(120, 130, 150, 0.10)'
            }
            strokeWidth={1}
            strokeDasharray="4 4"
            style={{ transition: 'stroke 320ms ease' }}
          />
          {/* Zone 라벨 — visualZone2 면 외곽, 아니면 내부원 안내.
              P.32 — visualZoneHalf 시 "Zone 1+ (코어단서)" 중간 라벨. */}
          {!visualZone2 && (
            <text
              x={center}
              y={center - R * 0.5 - 6}
              fill={visualZoneHalf ? 'rgba(56, 189, 248, 0.85)' : 'rgba(255, 149, 0, 0.6)'}
              fontSize={visualZoneHalf ? 10 : 9}
              fontWeight={visualZoneHalf ? 700 : 600}
              textAnchor="middle"
              style={{ fontFamily: 'system-ui, sans-serif', letterSpacing: '0.05em' }}
            >
              {visualZoneHalf
                ? 'Zone 1+ · 코어 단서 검출 (단서 추가로 외곽 이동)'
                : 'Zone 1 · 광범위 탐색'}
            </text>
          )}
          {visualZone2 && (
            <text
              x={center}
              y={center - R - 10}
              fill="#26C281"
              fontSize={10.5}
              fontWeight={700}
              textAnchor="middle"
              style={{ fontFamily: 'system-ui, sans-serif', letterSpacing: '0.03em' }}
            >
              Zone 2 · 사고유형 chain 구체화
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
                strokeWidth={isLatest ? 3.2 : 2.8}
                strokeOpacity={isLatest ? 1.0 : 0.85}
                // Phase P.17 (사용자 피드백: "회귀권고에서도 오류가 있어 노드가 깨지는데")
                //   기존 dasharray "6 2" 가 점간 거리 짧을 때 (depth 1-3 근방) 끊겨 보임 →
                //   회귀권고/Zone1 케이스에서 polyline 이 안 보이는 버그.
                //   변경: 모든 segment 실선. stage 구분은 stroke 색 + opacity 로만.
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            );
          })}

          {/* 궤적 점 — 각 채택 단서. stage 별 색상.
              재설계 (2026-05-27, KBW): RESET 마커 분기 제거. stage 첫 단서
              (stageDepth===1 AND stage>1) 에 "Stage N" 배지만 표시. */}
          {trail.map((t, i) => {
            const isCurrent = i === trail.length - 1;
            const isRoot = i === 0;
            const isStageStart = t.stage > 1 && t.stageDepth === 1;
            const sc = stageColor(t.stage);
            // P.35.4 — 단서 점 클릭 detail + 외부 highlight ring
            const isClickable = !isRoot && onTrailPointClick && !disabled;
            const isHighlighted = highlightedClueKey && t.clueKey === highlightedClueKey;
            return (
              <g
                key={`trail-${i}`}
                style={isClickable ? { cursor: 'pointer' } : undefined}
                onClick={
                  isClickable
                    ? (e) => {
                        e.stopPropagation();
                        onTrailPointClick({
                          clue_key: t.clueKey,
                          label: t.label,
                          stage: t.stage,
                          posterior: t.posterior,
                        });
                      }
                    : undefined
                }
              >
                {isCurrent && (
                  <circle cx={t.x} cy={t.y} r={14} fill={sc.fill} opacity={0.18}>
                    <animate
                      attributeName="r"
                      values="10;16;10"
                      dur="1.8s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
                {/* 외부 LogPanel 클릭 시 매칭 단서에 ring 강조 */}
                {isHighlighted && (
                  <circle
                    cx={t.x}
                    cy={t.y}
                    r={11}
                    fill="none"
                    stroke="#FBBF24"
                    strokeWidth={2}
                    strokeDasharray="3 2"
                    opacity={0.95}
                  >
                    <animate
                      attributeName="r"
                      values="9;13;9"
                      dur="1.4s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
                <circle
                  cx={t.x}
                  cy={t.y}
                  r={isCurrent ? 6 : isRoot ? 4.5 : 4}
                  fill={isRoot ? '#FF9500' : sc.fill}
                  fillOpacity={isCurrent ? 1 : isRoot ? 1 : 0.55}
                  stroke={isCurrent ? sc.stroke : isRoot ? '#FFB04D' : sc.fill}
                  strokeWidth={isCurrent ? 1.5 : 1}
                  style={isCurrent ? { transition: 'cx 360ms ease, cy 360ms ease' } : undefined}
                />
                {/* stage 첫 단서 — "Stage N 시작" 배지 (중앙 마커 대신) */}
                {isStageStart && (
                  <text
                    x={t.x}
                    y={t.y - 14}
                    fill={sc.stroke}
                    fontSize={9.5}
                    fontWeight={700}
                    textAnchor="middle"
                    style={{ fontFamily: 'system-ui, sans-serif' }}
                  >
                    {sc.label} 시작
                  </text>
                )}
                {/* depth 번호 — 전역 단서 순서 (1,2,3,4 연속) */}
                {!isRoot && (
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
                {isCurrent && !isRoot && (
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

          {/* 중앙 ◆ 표식 (uniform 시작점) — 단서 0개 OR root 부재 fallback.
           *  P.18 안전망: backend parent_id 손상으로 trail[0].depth>0 인 경우에도 표시. */}
          {(trail.length <= 1 || (trail[0]?.depth ?? 0) > 0) && (
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
      {/* V1.fix.17 (2026-06-01) — 하단 zone 별 부연 안내 제거.
          사용자 피드백: "Zone 1+ 전환 중 ... 무게중심 외곽 등은 다른 곳에서 확인 가능".
          Zone 상태 + 회귀 권고는 RegressBanner + 상단 Zone 배지로 충분히 표시됨.
          여기는 confidence 도달 시 사고유형 방향 안내만 유지. */}
      <div className="px-2.5 py-1.5 border-t border-ink-700 text-[9.5px] text-ink-500 leading-4 font-mono">
        {confidenceReached && primaryIncident ? (
          <span className="text-brand-teal font-semibold">
            {INCIDENT_KO[primaryIncident]} 방향 도달 ✓
          </span>
        ) : (
          <span className="text-ink-500">단서를 누적하면 사고유형 방향으로 이동합니다</span>
        )}
      </div>
    </div>
  );
};

export default IncidentTypeCompass;
