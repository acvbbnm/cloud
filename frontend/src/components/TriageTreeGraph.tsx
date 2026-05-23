/**
 * 결정 트리 전체 그래프 — 오버레이 전용 (2026-05-22).
 *
 * Step3_Discovery 우측 사이드바의 TriageTreeMinimap(텍스트 요약)에서
 * 「⛶ 확대」 토글 시 슬라이드 오버레이로 노출되는 큰 react-flow 트리.
 *
 * 좌측 결정 트리 답변과 실시간 동기화 — 동일한 trail/current/isTerminal props 사용.
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

import type { DecisionStep } from '@/components/TriageTreeMinimap';

interface TriageTreeGraphProps {
  trail: DecisionStep[];
  current: DecisionStep | null;
  isTerminal: boolean;
}

// 큰 캔버스용 — 노드 크기·간격 넉넉히
const LEVEL_H = 110;
const OPT_Y_OFFSET = 56;
const OPT_W = 130;
const Q_WIDTH = 260;
const OPT_WIDTH = 110;
const MAX_STEP_DRIFT = 110;

const trunc = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}…` : s);

const buildLayout = (
  trail: DecisionStep[],
  current: DecisionStep | null,
  isTerminal: boolean,
): { nodes: Node[]; edges: Edge[] } => {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  let anchorX = 0;

  const steps: Array<{ step: DecisionStep; isCurrent: boolean }> = [
    ...trail.map((s) => ({ step: s, isCurrent: false })),
    ...(current ? [{ step: current, isCurrent: true }] : []),
  ];

  steps.forEach(({ step, isCurrent }, lvl) => {
    const isCompleted = !isCurrent;
    const qId = `q-${lvl}`;
    const qY = lvl * LEVEL_H;

    nodes.push({
      id: qId,
      position: { x: anchorX, y: qY },
      data: { label: `Q${lvl + 1}. ${trunc(step.question, 48)}` },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      draggable: false,
      connectable: false,
      selectable: false,
      style: {
        background: isCurrent ? 'rgba(255, 149, 0, 0.18)' : 'rgba(38, 194, 129, 0.14)',
        border: isCurrent ? '1.5px solid #FF9500' : '1px solid rgba(38, 194, 129, 0.6)',
        color: isCurrent ? '#FF9500' : '#26C281',
        fontSize: '12px',
        fontWeight: 700,
        padding: '6px 10px',
        borderRadius: '0',
        width: Q_WIDTH,
        textAlign: 'center' as const,
      },
    });

    if (lvl > 0) {
      const prev = steps[lvl - 1].step;
      const prevSel = prev.selectedIds[0];
      if (prevSel) {
        edges.push({
          id: `e-prev-${lvl}`,
          source: `opt-${lvl - 1}-${prevSel}`,
          target: qId,
          style: { stroke: '#26C281', strokeWidth: 2 },
          animated: true,
        });
      }
    }

    const total = step.options.length;
    const visible = isCompleted
      ? step.options.filter((o) => step.selectedIds.includes(o.id))
      : step.options;

    visible.forEach((opt) => {
      const origIdx = step.options.findIndex((o) => o.id === opt.id);
      const offset = (origIdx - (total - 1) / 2) * OPT_W;
      const x = anchorX + offset;
      const y = qY + OPT_Y_OFFSET;
      const isSelected = step.selectedIds.includes(opt.id);

      nodes.push({
        id: `opt-${lvl}-${opt.id}`,
        position: { x, y },
        data: { label: trunc(opt.label, 22) },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        draggable: false,
        connectable: false,
        selectable: false,
        style: {
          background: isSelected
            ? 'rgba(38, 194, 129, 0.22)'
            : 'rgba(28, 32, 48, 0.7)',
          border: isSelected
            ? '1.5px solid #26C281'
            : '1px dashed rgba(122, 122, 134, 0.5)',
          color: isSelected ? '#26C281' : 'rgba(195, 195, 205, 0.9)',
          fontSize: '11px',
          fontWeight: isSelected ? 700 : 500,
          padding: '4px 6px',
          borderRadius: '0',
          width: OPT_WIDTH,
          textAlign: 'center' as const,
        },
      });

      edges.push({
        id: `e-${qId}-${opt.id}`,
        source: qId,
        target: `opt-${lvl}-${opt.id}`,
        style: {
          stroke: isSelected ? '#26C281' : 'rgba(80, 85, 95, 0.6)',
          strokeWidth: isSelected ? 2 : 1,
          strokeDasharray: isSelected ? undefined : '4 4',
        },
      });
    });

    if (step.selectedIds.length > 0) {
      const firstSelId = step.selectedIds[0];
      const idx = step.options.findIndex((o) => o.id === firstSelId);
      if (idx >= 0) {
        const rawOffset = (idx - (total - 1) / 2) * OPT_W;
        const clamped = Math.max(-MAX_STEP_DRIFT, Math.min(MAX_STEP_DRIFT, rawOffset));
        anchorX += clamped;
      }
    }
  });

  if (isTerminal) {
    const tY = steps.length * LEVEL_H;
    nodes.push({
      id: 'terminal',
      position: { x: anchorX, y: tY },
      data: { label: '◆ T 종합평가' },
      targetPosition: Position.Top,
      draggable: false,
      connectable: false,
      selectable: false,
      style: {
        background: 'rgba(255, 149, 0, 0.22)',
        border: '1.5px solid #FF9500',
        color: '#FF9500',
        fontSize: '13px',
        fontWeight: 700,
        padding: '6px 12px',
        borderRadius: '0',
        width: 220,
        textAlign: 'center' as const,
      },
    });
    if (steps.length > 0) {
      const last = steps[steps.length - 1].step;
      const lastSel = last.selectedIds[0];
      if (lastSel) {
        edges.push({
          id: 'e-terminal',
          source: `opt-${steps.length - 1}-${lastSel}`,
          target: 'terminal',
          style: { stroke: '#FF9500', strokeWidth: 2 },
          animated: true,
        });
      }
    }
  }

  return { nodes, edges };
};

const TriageTreeGraph = ({ trail, current, isTerminal }: TriageTreeGraphProps) => {
  const { nodes, edges } = useMemo(
    () => buildLayout(trail, current, isTerminal),
    [trail, current, isTerminal],
  );
  const hasContent = nodes.length > 0;

  const stableKey = useMemo(
    () =>
      [
        ...trail.map((t) => `${t.node_id}:${t.selectedIds.join(',')}`),
        current?.node_id ?? '_',
        String(isTerminal),
      ].join('|'),
    [trail, current, isTerminal],
  );

  if (!hasContent) {
    return (
      <div className="h-full flex items-center justify-center text-ink-500 text-[12px] italic">
        진행된 결정 트리 없음
      </div>
    );
  }

  return (
    <ReactFlow
      key={stableKey}
      nodes={nodes}
      edges={edges}
      fitView
      fitViewOptions={{ padding: 0.18 }}
      proOptions={{ hideAttribution: true }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      zoomOnScroll={true}
      panOnDrag={true}
      zoomOnDoubleClick={true}
      minZoom={0.2}
      maxZoom={2.5}
    >
      <Background gap={20} color="rgba(120, 130, 150, 0.1)" />
      <Controls
        showInteractive={false}
        showZoom={true}
        showFitView={true}
        position="bottom-right"
        style={{ background: 'rgba(20, 25, 35, 0.7)', border: 'none' }}
      />
    </ReactFlow>
  );
};

export default TriageTreeGraph;
