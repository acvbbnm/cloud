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
  // terminal
  { id: 'T_evaluate', short: 'T 평가', parent: 'Q3_additional_context', col: 0, row: 3 },
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
  ['Q3_additional_context', 'T_evaluate'],
];

const X_STEP = 90;
const Y_STEP = 70;
const X_ORIGIN = 200;
const Y_ORIGIN = 20;

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

    const flowNodes: Node[] = TREE_NODES.map((meta) => {
      const isCurrent = meta.id === currentNodeId;
      const isCompleted = completedSet.has(meta.id);
      // Q2 다른 분기는 비활성 (회색 / 점선)
      const isQ2 = meta.id.startsWith('Q2');
      const isInactiveBranch = isQ2 && activeQ2 && meta.id !== activeQ2;

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
      if (isInactiveBranch) {
        bg = 'rgba(30, 35, 45, 0.4)';
        border = '1px dashed rgba(80, 85, 95, 0.4)';
        color = '#555c6e';
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
      return {
        id: `${from}-${to}`,
        source: from,
        target: to,
        animated: isActiveEdge,
        style: {
          stroke: isActiveEdge
            ? '#23c391'
            : isInactiveBranch
            ? 'rgba(80, 85, 95, 0.35)'
            : 'rgba(120, 130, 150, 0.5)',
          strokeWidth: isActiveEdge ? 2 : 1,
          strokeDasharray: isInactiveBranch ? '4 3' : undefined,
        },
      };
    });

    return { nodes: flowNodes, edges: flowEdges };
  }, [currentNodeId, completedNodeIds, isTerminal]);

  return (
    <div className="border border-ink-700/60 rounded-lg bg-ink-950/40" style={{ height: 280 }}>
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
        <span className="text-ink-600">--- 비활성 분기</span>
      </div>
    </div>
  );
};

export default TriageTreeMinimap;
