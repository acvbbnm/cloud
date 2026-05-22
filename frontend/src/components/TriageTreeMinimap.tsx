/**
 * 결정 트리 미니맵 — V-1 Step 2 Discovery Loop 우측 패널 (사용자 결정 #3).
 *
 * react-flow 11 로 E4 6단계 동적 분기 트리를 시각화한다.
 * (decision_tree.json v3-e4-6stage 정합 — Q1→Q2→Q3→Q4→Q5→Q6→T)
 *
 * 노드 상태:
 *   ● 현재 위치 (currentNodeId)
 *   ✓ 답변 완료 (completedNodeIds)
 *   (밝은 테두리) 활성 분기의 도달 가능 경로
 *   (회색 점선) 다른 옵션 선택 시 갈 수 있었던 비활성 분기
 *
 * 사고유형별 분기 색상 (doc §4-7):
 *   자격증명=파랑 · 랜섬웨어=빨강 · 설정오류=주황 · 내부자=청록 · 데이터=자홍
 *
 * 학술 변호 (doc §4-7): "다른 선택이 가능했음" 을 회색 점선으로 시각 입증 →
 * 결정 트리의 분기 결정성과 대안 경로 존재를 동시에 보인다.
 */
import { useMemo } from 'react';

import ReactFlow, {
  Background,
  Controls,
  type Edge,
  type Node,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';

interface TriageTreeMinimapProps {
  currentNodeId: string | null;
  completedNodeIds: string[];
  isTerminal: boolean;
}

type Family = 'common' | 'cred' | 'ransom' | 'miscfg' | 'insider' | 'data';

/** 사고유형 분기 계열별 색상·라벨. */
const FAMILY: Record<Family, { color: string; label: string }> = {
  common: { color: '#9aa3b2', label: '공통' },
  cred: { color: '#3D7BFF', label: '자격증명' },
  ransom: { color: '#EF4444', label: '랜섬웨어' },
  miscfg: { color: '#F59E0B', label: '설정오류' },
  insider: { color: '#2DD4BF', label: '내부자' },
  data: { color: '#C026D3', label: '데이터' },
};

/** #RRGGBB → rgba(r,g,b,a). */
const tint = (hex: string, alpha: number): string => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

interface TreeNodeMeta {
  id: string;
  short: string;
  family: Family;
  col: number;
  row: number;
}

/**
 * 트리 노드 메타 — decision_tree.json v3-e4-6stage 의 24 노드 구조 정합.
 * 시각화용 정적 격자 좌표 (col, row). 백엔드 /api/triage/tree 와 동일 골격.
 */
const TREE_NODES: TreeNodeMeta[] = [
  // ── row 0 — Q1 인지 경로 ──
  { id: 'Q1_inception', short: 'Q1 인지경로', family: 'common', col: 0, row: 0 },
  // ── row 1 — Q2 직접 정황 (5 분기) ──
  { id: 'Q2A_alert_type', short: 'Q2A CSP알람', family: 'common', col: -3, row: 1 },
  { id: 'Q2B_report_content', short: 'Q2B 외부신고', family: 'common', col: -1, row: 1 },
  { id: 'Q2C_audit_pattern', short: 'Q2C 정기감사', family: 'common', col: 1, row: 1 },
  { id: 'Q2D_anomaly_form', short: 'Q2D 서비스이상', family: 'common', col: 3, row: 1 },
  { id: 'Q2E_minimal_checklist', short: 'Q2E 출처불명', family: 'common', col: 5, row: 1 },
  // ── row 2 — Q3 추가 패턴 (4 variant) ──
  { id: 'Q3_CRED', short: 'Q3 자격증명', family: 'cred', col: -3, row: 2 },
  { id: 'Q3_DATA', short: 'Q3 데이터', family: 'data', col: -1, row: 2 },
  { id: 'Q3_INSIDER', short: 'Q3 내부자', family: 'insider', col: 1, row: 2 },
  { id: 'Q3_IMPACT', short: 'Q3 영향', family: 'ransom', col: 3, row: 2 },
  // ── row 3 — Q4 증거 무결성 (4 lane) ──
  { id: 'Q4_CRED', short: 'Q4 MFA우회', family: 'cred', col: -3, row: 3 },
  { id: 'Q4_MISCFG', short: 'Q4 노출시점', family: 'miscfg', col: -1, row: 3 },
  { id: 'Q4_INSIDER', short: 'Q4 직무범위', family: 'insider', col: 1, row: 3 },
  { id: 'Q4_RANSOM', short: 'Q4 백업무결성', family: 'ransom', col: 3, row: 3 },
  // ── row 4 — Q5 영향 범위·행위자 ──
  { id: 'Q5_CRED', short: 'Q5 행위자', family: 'cred', col: -3, row: 4 },
  { id: 'Q5_MISCFG', short: 'Q5 변경주체', family: 'miscfg', col: -1, row: 4 },
  { id: 'Q5_INSIDER', short: 'Q5 접속환경', family: 'insider', col: 1, row: 4 },
  { id: 'Q5_RANSOM', short: 'Q5 피해규모', family: 'ransom', col: 3, row: 4 },
  // ── row 5 — Q6 후속 시그널·의도 ──
  { id: 'Q6_CRED', short: 'Q6 후속행동', family: 'cred', col: -3, row: 5 },
  { id: 'Q6_MISCFG', short: 'Q6 민감도', family: 'miscfg', col: -1, row: 5 },
  { id: 'Q6_INSIDER', short: 'Q6 사후행동', family: 'insider', col: 1, row: 5 },
  { id: 'Q6_RANSOM', short: 'Q6 랜섬노트', family: 'ransom', col: 3, row: 5 },
  // ── row 6 — 종합 평가 ──
  { id: 'T_evaluate', short: 'T 종합평가', family: 'common', col: 0, row: 6 },
];

/** 트리 엣지 — decision_tree.json 의 6단계 분기 골격. */
const TREE_EDGES: Array<[string, string]> = [
  ['Q1_inception', 'Q2A_alert_type'],
  ['Q1_inception', 'Q2B_report_content'],
  ['Q1_inception', 'Q2C_audit_pattern'],
  ['Q1_inception', 'Q2D_anomaly_form'],
  ['Q1_inception', 'Q2E_minimal_checklist'],
  // Q2 → Q3 (Q2B 는 4 variant 로 fan-out)
  ['Q2A_alert_type', 'Q3_CRED'],
  ['Q2B_report_content', 'Q3_DATA'],
  ['Q2B_report_content', 'Q3_CRED'],
  ['Q2B_report_content', 'Q3_INSIDER'],
  ['Q2B_report_content', 'Q3_IMPACT'],
  ['Q2C_audit_pattern', 'Q3_INSIDER'],
  ['Q2D_anomaly_form', 'Q3_IMPACT'],
  // Q3 → Q4 (Q3_DATA 는 라우터 — 3 lane 으로 분기)
  ['Q3_CRED', 'Q4_CRED'],
  ['Q3_DATA', 'Q4_MISCFG'],
  ['Q3_DATA', 'Q4_INSIDER'],
  ['Q3_DATA', 'Q4_RANSOM'],
  ['Q3_INSIDER', 'Q4_INSIDER'],
  ['Q3_IMPACT', 'Q4_RANSOM'],
  // Q4 → Q5 → Q6 → T (lane 별 직선)
  ['Q4_CRED', 'Q5_CRED'],
  ['Q5_CRED', 'Q6_CRED'],
  ['Q6_CRED', 'T_evaluate'],
  ['Q4_MISCFG', 'Q5_MISCFG'],
  ['Q5_MISCFG', 'Q6_MISCFG'],
  ['Q6_MISCFG', 'T_evaluate'],
  ['Q4_INSIDER', 'Q5_INSIDER'],
  ['Q5_INSIDER', 'Q6_INSIDER'],
  ['Q6_INSIDER', 'T_evaluate'],
  ['Q4_RANSOM', 'Q5_RANSOM'],
  ['Q5_RANSOM', 'Q6_RANSOM'],
  ['Q6_RANSOM', 'T_evaluate'],
];

const META_BY_ID = new Map(TREE_NODES.map((n) => [n.id, n]));

const X_STEP = 92;
const Y_STEP = 62;
const X_ORIGIN = 320;
const Y_ORIGIN = 16;

/** id 가 Q3~Q6 분기 노드면 단계 숫자(3~6), 아니면 0. */
const stageRank = (id: string): number => {
  const m = id.match(/^Q([3-6])_/);
  return m ? Number(m[1]) : 0;
};

/** activeLane 기준으로 비활성 처리할 family 집합. */
const inactiveFamilies = (lane: Family | null): Set<Family> => {
  if (lane === null) return new Set();
  // Q3_DATA(데이터 라우터) 단계에서는 아직 Q4 lane 미확정 → 자격증명만 배제
  if (lane === 'data') return new Set<Family>(['cred']);
  const all: Family[] = ['cred', 'ransom', 'miscfg', 'insider', 'data'];
  return new Set(all.filter((f) => f !== lane));
};

type NodeState = 'current' | 'completed' | 'inactive' | 'reachable' | 'terminal';

const TriageTreeMinimap = ({
  currentNodeId,
  completedNodeIds,
  isTerminal,
}: TriageTreeMinimapProps) => {
  const { nodes, edges } = useMemo(() => {
    const completedSet = new Set(completedNodeIds);
    const pathSet = new Set(completedNodeIds);
    if (currentNodeId) pathSet.add(currentNodeId);

    // 활성 Q2 분기 — 다른 Q2 형제는 비활성
    const currentIsQ2 = currentNodeId?.startsWith('Q2') ?? false;
    const activeQ2 = currentIsQ2
      ? currentNodeId
      : completedNodeIds.find((id) => id.startsWith('Q2')) ?? null;

    // 활성 lane — 경로 상 가장 깊은 Q3~Q6 노드의 family
    let activeLane: Family | null = null;
    let deepestRank = 0;
    for (const id of pathSet) {
      const rank = stageRank(id);
      if (rank > deepestRank) {
        deepestRank = rank;
        activeLane = META_BY_ID.get(id)?.family ?? null;
      }
    }
    const blockedFamilies = inactiveFamilies(activeLane);

    /** 노드 상태 판정 — completed 가 inactive 보다 우선. */
    const stateOf = (meta: TreeNodeMeta): NodeState => {
      if (meta.id === currentNodeId) return 'current';
      if (completedSet.has(meta.id)) return 'completed';
      if (meta.id === 'T_evaluate') return isTerminal ? 'terminal' : 'reachable';
      // Q2 형제 분기 비활성
      if (meta.id.startsWith('Q2') && activeQ2 && meta.id !== activeQ2) {
        return 'inactive';
      }
      // 다른 사고유형 lane 비활성
      if (meta.family !== 'common' && blockedFamilies.has(meta.family)) {
        return 'inactive';
      }
      return 'reachable';
    };

    const flowNodes: Node[] = TREE_NODES.map((meta) => {
      const state = stateOf(meta);
      const fam = FAMILY[meta.family];

      let bg = tint(fam.color, 0.06);
      let border = `1px dashed ${tint(fam.color, 0.28)}`;
      let color = tint(fam.color, 0.55);
      let prefix = '';

      if (state === 'reachable') {
        bg = tint(fam.color, 0.08);
        border = `1px solid ${tint(fam.color, 0.4)}`;
        color = tint(fam.color, 0.7);
      }
      if (state === 'completed') {
        bg = tint(fam.color, 0.2);
        border = `1.5px solid ${tint(fam.color, 0.8)}`;
        color = fam.color;
        prefix = '✓ ';
      }
      if (state === 'current') {
        bg = tint(fam.color, 0.28);
        border = `2px solid ${fam.color}`;
        color = fam.color;
        prefix = '● ';
      }
      if (state === 'inactive') {
        bg = 'rgba(30, 35, 45, 0.45)';
        border = '1px dashed rgba(80, 85, 95, 0.4)';
        color = '#555c6e';
      }
      if (state === 'terminal') {
        bg = 'rgba(245, 158, 11, 0.2)';
        border = '1.5px solid #F59E0B';
        color = '#F59E0B';
        prefix = '◆ ';
      }

      return {
        id: meta.id,
        position: {
          x: X_ORIGIN + meta.col * X_STEP,
          y: Y_ORIGIN + meta.row * Y_STEP,
        },
        data: { label: `${prefix}${meta.short}` },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        draggable: false,
        connectable: false,
        selectable: false,
        style: {
          background: bg,
          border,
          color,
          fontSize: '9px',
          fontWeight: 600,
          padding: '3px 6px',
          borderRadius: '6px',
          width: 'auto',
          minWidth: 74,
          textAlign: 'center' as const,
        },
      };
    });

    const flowEdges: Edge[] = TREE_EDGES.map(([from, to]) => {
      const toMeta = META_BY_ID.get(to);
      const fromCompleted = completedSet.has(from);
      const toOnPath = to === currentNodeId || completedSet.has(to);
      const isTakenPath = fromCompleted && toOnPath;
      const isNextStep = from === currentNodeId;

      // 비활성 판정 — 끝점 중 하나라도 비활성 분기면 회색 점선
      const toInactive =
        (to.startsWith('Q2') && activeQ2 && to !== activeQ2) ||
        (toMeta !== undefined &&
          toMeta.family !== 'common' &&
          blockedFamilies.has(toMeta.family));
      const fromInactive =
        (from.startsWith('Q2') && activeQ2 && from !== activeQ2) ||
        (META_BY_ID.get(from)?.family !== 'common' &&
          blockedFamilies.has(META_BY_ID.get(from)?.family as Family));
      const isInactive = (toInactive || fromInactive) && !isTakenPath;

      const laneColor = FAMILY[toMeta?.family ?? 'common'].color;

      let stroke = tint(laneColor, 0.32);
      let strokeWidth = 1;
      let dash: string | undefined = undefined;
      if (isInactive) {
        stroke = 'rgba(80, 85, 95, 0.32)';
        dash = '4 3';
      } else if (isTakenPath) {
        stroke = laneColor;
        strokeWidth = 2;
      } else if (isNextStep) {
        stroke = tint(laneColor, 0.75);
        strokeWidth = 1.5;
      }

      return {
        id: `${from}-${to}`,
        source: from,
        target: to,
        animated: isTakenPath || isNextStep,
        style: { stroke, strokeWidth, strokeDasharray: dash },
      };
    });

    return { nodes: flowNodes, edges: flowEdges };
  }, [currentNodeId, completedNodeIds, isTerminal]);

  return (
    <div className="border border-ink-700/60 rounded-lg bg-ink-950/40" style={{ height: 320 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        panOnScroll={false}
        zoomOnDoubleClick={false}
        minZoom={0.2}
      >
        <Background gap={16} color="rgba(120, 130, 150, 0.1)" />
        <Controls
          showInteractive={false}
          showZoom={true}
          showFitView={true}
          position="bottom-right"
          style={{ background: 'rgba(20, 25, 35, 0.7)', border: 'none' }}
        />
      </ReactFlow>
      <div className="px-2 py-1 text-[9px] text-ink-500 flex items-center gap-2.5 flex-wrap border-t border-ink-700/40">
        <span><span className="text-brand-blue">●</span> 현재</span>
        <span><span className="text-brand-teal">✓</span> 완료</span>
        <span><span style={{ color: '#F59E0B' }}>◆</span> 평가</span>
        <span className="text-ink-600">--- 비활성 분기</span>
        <span className="w-px h-2.5 bg-ink-700" />
        {(['cred', 'ransom', 'miscfg', 'insider', 'data'] as Family[]).map((f) => (
          <span key={f} className="flex items-center gap-1">
            <span
              className="inline-block w-2 h-2 rounded-sm"
              style={{ background: FAMILY[f].color }}
            />
            {FAMILY[f].label}
          </span>
        ))}
      </div>
    </div>
  );
};

export default TriageTreeMinimap;
