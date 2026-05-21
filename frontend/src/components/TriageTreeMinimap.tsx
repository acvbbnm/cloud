/**
 * 결정 트리 미니맵 — V-1 Step 2 Discovery Loop 우측 패널 (사용자 결정 #3).
 *
 * react-flow 11 로 정적 트리 시각화. 청사진 §2 의 트리 시각화 모형 그대로.
 *
 * 노드 상태:
 *   ✅ 답변 완료 (completedPath 의 node_id)
 *   🔵 현재 위치 (currentNodeId)
 *   ⚪ 가능 경로 (트리 정의 상 도달 가능)
 *   🔴 차단 (현재 분기에서 도달 불가 — 다른 옵션 선택했으므로)
 *
 * 학술 근거: 사용자 결정 #3 트리 시각화 + DFIR-IRIS·TheHive 의 case timeline.
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

/**
 * 트리 노드 메타 — backend/data/triage/decision_tree.json 의 구조 정합.
 * (실제로는 백엔드에서 트리 메타를 받아오는 게 정석이나, 시각화용 정적 매핑이라 임베드)
 */
interface TreeNodeMeta {
  id: string;
  short: string;
  parent?: string;
  // x, y 격자 좌표 (col, row)
  col: number;
  row: number;
}

// E4 사고유형별 분기 색상
const BRANCH_COLORS: Record<string, string> = {
  CRED: '#3B82F6',    // blue
  RANSOM: '#EF4444',  // red
  MISCFG: '#F97316',  // orange
  INSIDER: '#14B8A6', // teal
};

const TREE_NODES: TreeNodeMeta[] = [
  // root
  { id: 'Q1_inception', short: 'Q1 인지 경로', col: 0, row: 0 },
  // depth 1
  { id: 'Q2A_alert_type', short: 'Q2A CSP 알람', parent: 'Q1_inception', col: -2, row: 1 },
  { id: 'Q2B_report_content', short: 'Q2B 외부 신고', parent: 'Q1_inception', col: -1, row: 1 },
  { id: 'Q2C_audit_pattern', short: 'Q2C 정기 감사', parent: 'Q1_inception', col: 0, row: 1 },
  { id: 'Q2D_anomaly_form', short: 'Q2D 서비스 이상', parent: 'Q1_inception', col: 1, row: 1 },
  { id: 'Q2E_minimal_checklist', short: 'Q2E 출처 불명', parent: 'Q1_inception', col: 2, row: 1 },
  // depth 2
  { id: 'Q3_additional_context', short: 'Q3 추가 정황', col: 0, row: 2 },
  // E4 depth 3 — Q4 분기 (사고유형별)
  { id: 'Q4_CRED', short: 'Q4 증거·MFA', parent: 'Q3_additional_context', col: -1.5, row: 3 },
  { id: 'Q4_RANSOM', short: 'Q4 백업', parent: 'Q3_additional_context', col: -0.5, row: 3 },
  { id: 'Q4_MISCFG', short: 'Q4 변경시점', parent: 'Q3_additional_context', col: 0.5, row: 3 },
  { id: 'Q4_INSIDER', short: 'Q4 직무범위', parent: 'Q3_additional_context', col: 1.5, row: 3 },
  // E4 depth 4 — Q5 분기
  { id: 'Q5_CRED', short: 'Q5 행위자', parent: 'Q4_CRED', col: -1.5, row: 4 },
  { id: 'Q5_RANSOM', short: 'Q5 영향범위', parent: 'Q4_RANSOM', col: -0.5, row: 4 },
  { id: 'Q5_MISCFG', short: 'Q5 변경주체', parent: 'Q4_MISCFG', col: 0.5, row: 4 },
  { id: 'Q5_INSIDER', short: 'Q5 가시성', parent: 'Q4_INSIDER', col: 1.5, row: 4 },
  // E4 depth 5 — Q6 분기
  { id: 'Q6_CRED', short: 'Q6 후속시그널', parent: 'Q5_CRED', col: -1.5, row: 5 },
  { id: 'Q6_RANSOM', short: 'Q6 랜섬노트', parent: 'Q5_RANSOM', col: -0.5, row: 5 },
  { id: 'Q6_MISCFG', short: 'Q6 민감도', parent: 'Q5_MISCFG', col: 0.5, row: 5 },
  { id: 'Q6_INSIDER', short: 'Q6 사후행동', parent: 'Q5_INSIDER', col: 1.5, row: 5 },
  // terminal
  { id: 'T_evaluate', short: 'T 평가', col: 0, row: 6 },
];

const TREE_EDGES: Array<[string, string]> = [
  ['Q1_inception', 'Q2A_alert_type'],
  ['Q1_inception', 'Q2B_report_content'],
  ['Q1_inception', 'Q2C_audit_pattern'],
  ['Q1_inception', 'Q2D_anomaly_form'],
  ['Q1_inception', 'Q2E_minimal_checklist'],
  ['Q2A_alert_type', 'Q3_additional_context'],
  ['Q2B_report_content', 'Q3_additional_context'],
  ['Q2C_audit_pattern', 'Q3_additional_context'],
  ['Q2D_anomaly_form', 'Q3_additional_context'],
  // E4 Q3 → Q4 분기
  ['Q3_additional_context', 'Q4_CRED'],
  ['Q3_additional_context', 'Q4_RANSOM'],
  ['Q3_additional_context', 'Q4_MISCFG'],
  ['Q3_additional_context', 'Q4_INSIDER'],
  // Q4 → Q5
  ['Q4_CRED', 'Q5_CRED'],
  ['Q4_RANSOM', 'Q5_RANSOM'],
  ['Q4_MISCFG', 'Q5_MISCFG'],
  ['Q4_INSIDER', 'Q5_INSIDER'],
  // Q5 → Q6
  ['Q5_CRED', 'Q6_CRED'],
  ['Q5_RANSOM', 'Q6_RANSOM'],
  ['Q5_MISCFG', 'Q6_MISCFG'],
  ['Q5_INSIDER', 'Q6_INSIDER'],
  // Q6 → T
  ['Q6_CRED', 'T_evaluate'],
  ['Q6_RANSOM', 'T_evaluate'],
  ['Q6_MISCFG', 'T_evaluate'],
  ['Q6_INSIDER', 'T_evaluate'],
];

const X_STEP = 80;
const Y_STEP = 55;
const X_ORIGIN = 200;
const Y_ORIGIN = 15;

const TriageTreeMinimap = ({
  currentNodeId,
  completedNodeIds,
  isTerminal,
}: TriageTreeMinimapProps) => {
  const { nodes, edges } = useMemo(() => {
    const completedSet = new Set(completedNodeIds);

    // 현재 노드가 Q2 분기 중 하나라면 그 분기만 활성. 그렇지 않으면 completed 에서 Q2 검색.
    const currentIsQ2 = currentNodeId?.startsWith('Q2');
    const activeQ2 = currentIsQ2
      ? currentNodeId
      : completedNodeIds.find((id) => id.startsWith('Q2')) ?? null;

    // E4: 활성 Q4 분기 감지 (CRED/RANSOM/MISCFG/INSIDER)
    const activeBranch = (() => {
      const q4 = completedNodeIds.find((id) => id.startsWith('Q4_')) ?? (currentNodeId?.startsWith('Q4_') ? currentNodeId : null);
      if (q4) return q4.replace('Q4_', '');
      const q5 = completedNodeIds.find((id) => id.startsWith('Q5_')) ?? (currentNodeId?.startsWith('Q5_') ? currentNodeId : null);
      if (q5) return q5.replace('Q5_', '');
      const q6 = completedNodeIds.find((id) => id.startsWith('Q6_')) ?? (currentNodeId?.startsWith('Q6_') ? currentNodeId : null);
      if (q6) return q6.replace('Q6_', '');
      return null;
    })();

    const flowNodes: Node[] = TREE_NODES.map((meta) => {
      const isCurrent = meta.id === currentNodeId;
      const isCompleted = completedSet.has(meta.id);
      // Q2 다른 분기는 비활성 (회색 / 점선)
      const isQ2 = meta.id.startsWith('Q2');
      const isInactiveBranch = isQ2 && activeQ2 && meta.id !== activeQ2;
      // E4: Q4~Q6 비활성 분기 (다른 사고유형 경로)
      const branchSuffix = meta.id.match(/^Q[456]_(\w+)$/)?.[1];
      const isInactiveE4 = branchSuffix && activeBranch && branchSuffix !== activeBranch;
      const branchColor = branchSuffix ? BRANCH_COLORS[branchSuffix] : null;

      let bg = 'rgba(60, 70, 90, 0.4)';
      let border = '1px solid rgba(120, 130, 150, 0.4)';
      let color = '#9aa3b2';

      if (isCompleted) {
        bg = 'rgba(35, 195, 145, 0.18)';
        border = '1.5px solid rgba(35, 195, 145, 0.7)';
        color = '#23c391';
      }
      if (isCurrent) {
        bg = 'rgba(61, 123, 255, 0.22)';
        border = '2px solid #3D7BFF';
        color = '#3D7BFF';
      }
      if (isInactiveBranch || isInactiveE4) {
        bg = 'rgba(30, 35, 45, 0.4)';
        border = '1px dashed rgba(80, 85, 95, 0.4)';
        color = '#555c6e';
      }
      if (branchColor && !isInactiveE4 && (isCompleted || isCurrent)) {
        bg = `${branchColor}22`;
        border = `1.5px solid ${branchColor}`;
        color = branchColor;
      }
      if (meta.id === 'T_evaluate' && isTerminal) {
        bg = 'rgba(245, 158, 11, 0.18)';
        border = '1.5px solid #F59E0B';
        color = '#F59E0B';
      }

      const label = `${isCompleted ? '✓ ' : isCurrent ? '● ' : ''}${meta.short}`;

      return {
        id: meta.id,
        position: {
          x: X_ORIGIN + meta.col * X_STEP,
          y: Y_ORIGIN + meta.row * Y_STEP,
        },
        data: { label },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        draggable: false,
        connectable: false,
        selectable: false,
        style: {
          background: bg,
          border,
          color,
          fontSize: '10px',
          fontWeight: 600,
          padding: '4px 8px',
          borderRadius: '6px',
          width: 'auto',
          minWidth: 90,
          textAlign: 'center' as const,
        },
      };
    });

    const flowEdges: Edge[] = TREE_EDGES.map(([from, to]) => {
      const fromCompleted = completedSet.has(from);
      const toActive = to === currentNodeId || completedSet.has(to);
      const isActiveEdge = fromCompleted && toActive;
      // Q2 비활성 분기 엣지는 점선
      const toMeta = TREE_NODES.find((n) => n.id === to);
      const isInactiveBranch =
        toMeta?.id.startsWith('Q2') && activeQ2 && toMeta.id !== activeQ2;
      // E4: Q4~Q6 비활성 분기 엣지
      const toBranchSuffix = to.match(/^Q[456]_(\w+)$/)?.[1];
      const isInactiveE4Edge = toBranchSuffix && activeBranch && toBranchSuffix !== activeBranch;
      const edgeBranchColor = toBranchSuffix ? BRANCH_COLORS[toBranchSuffix] : null;
      return {
        id: `${from}-${to}`,
        source: from,
        target: to,
        animated: isActiveEdge,
        style: {
          stroke: isActiveEdge
            ? (edgeBranchColor ?? '#23c391')
            : (isInactiveBranch || isInactiveE4Edge)
            ? 'rgba(80, 85, 95, 0.35)'
            : 'rgba(120, 130, 150, 0.5)',
          strokeWidth: isActiveEdge ? 2 : 1,
          strokeDasharray: (isInactiveBranch || isInactiveE4Edge) ? '4 3' : undefined,
        },
      };
    });

    return { nodes: flowNodes, edges: flowEdges };
  }, [currentNodeId, completedNodeIds, isTerminal]);

  return (
    <div className="border border-ink-700/60 rounded-lg bg-ink-950/40" style={{ height: 380 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        panOnScroll={false}
        zoomOnDoubleClick={false}
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
      <div className="px-2 py-1 text-[9.5px] text-ink-500 flex items-center gap-3 flex-wrap border-t border-ink-700/40">
        <span><span className="text-brand-blue">●</span> 현재</span>
        <span><span className="text-brand-teal">✓</span> 완료</span>
        <span><span style={{ color: '#F59E0B' }}>◆</span> 평가</span>
        <span><span style={{ color: BRANCH_COLORS.CRED }}>■</span> CRED</span>
        <span><span style={{ color: BRANCH_COLORS.RANSOM }}>■</span> RANSOM</span>
        <span><span style={{ color: BRANCH_COLORS.MISCFG }}>■</span> MISCFG</span>
        <span><span style={{ color: BRANCH_COLORS.INSIDER }}>■</span> INSIDER</span>
        <span className="text-ink-600">--- 비활성</span>
      </div>
    </div>
  );
};

export default TriageTreeMinimap;
