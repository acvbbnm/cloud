/**
 * 결정 트리 진행 — 사이드바 미니맵 (2026-05-22 v7).
 *
 * 사이드바에 작은 react-flow 트리 그래프 + 우측 상단 「⛶ 확대」 버튼.
 * 확대 클릭 시 부모(Step3_Discovery)가 TriageTreeGraph 오버레이를 열어 큰 트리 노출.
 *
 * - 완료 단계: Q + 확정 옵션만 (미선택은 사라짐)
 * - 현재 단계: Q + 모든 옵션
 * - 선택 옵션 위치에 따라 다음 Q 좌우로 드리프트 (클램프 ±50px)
 */
import { useMemo } from 'react';

import ReactFlow, {
  Background,
  type Edge,
  type Node,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';

export interface DecisionStep {
  node_id: string;
  question: string;
  options: Array<{ id: string; label: string }>;
  selectedIds: string[];
}

interface TriageTreeMinimapProps {
  trail: DecisionStep[];
  current: DecisionStep | null;
  isTerminal: boolean;
  onExpand?: () => void;
}

// 사이드바용 컴팩트 크기 — fitView 가 scale 조정
const LEVEL_H = 62;
const OPT_Y_OFFSET = 30;
const OPT_W = 58;
const Q_WIDTH = 140;
const OPT_WIDTH = 52;
const MAX_STEP_DRIFT = 50;

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
      data: { label: `Q${lvl + 1}. ${trunc(step.question, 18)}` },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      draggable: false,
      connectable: false,
      selectable: false,
      style: {
        background: isCurrent ? 'rgba(255, 149, 0, 0.16)' : 'rgba(38, 194, 129, 0.12)',
        border: isCurrent ? '1.5px solid #FF9500' : '1px solid rgba(38, 194, 129, 0.55)',
        color: isCurrent ? '#FF9500' : '#26C281',
        fontSize: '8px',
        fontWeight: 700,
        padding: '2px 4px',
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
          style: { stroke: '#26C281', strokeWidth: 1.5 },
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
        data: { label: trunc(opt.label, 10) },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        draggable: false,
        connectable: false,
        selectable: false,
        style: {
          background: isSelected
            ? 'rgba(38, 194, 129, 0.2)'
            : 'rgba(28, 32, 48, 0.6)',
          border: isSelected
            ? '1.5px solid #26C281'
            : '1px dashed rgba(122, 122, 134, 0.5)',
          color: isSelected ? '#26C281' : 'rgba(195, 195, 205, 0.85)',
          fontSize: '7.5px',
          fontWeight: isSelected ? 700 : 500,
          padding: '1px 3px',
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
          strokeWidth: isSelected ? 1.5 : 1,
          strokeDasharray: isSelected ? undefined : '3 3',
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
      data: { label: '◆ T 평가' },
      targetPosition: Position.Top,
      draggable: false,
      connectable: false,
      selectable: false,
      style: {
        background: 'rgba(255, 149, 0, 0.2)',
        border: '1.5px solid #FF9500',
        color: '#FF9500',
        fontSize: '8.5px',
        fontWeight: 700,
        padding: '2px 6px',
        borderRadius: '0',
        width: 110,
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
          style: { stroke: '#FF9500', strokeWidth: 1.5 },
          animated: true,
        });
      }
    }
  }

  return { nodes, edges };
};

const TriageTreeMinimap = ({
  trail,
  current,
  isTerminal,
  onExpand,
}: TriageTreeMinimapProps) => {
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

  return (
    <div className="border border-ink-700 bg-ink-950/40 flex flex-col">
      <div className="px-2.5 py-1.5 border-b border-ink-700 flex items-center justify-between shrink-0">
        <span className="text-[10px] text-ink-400 font-mono font-semibold uppercase tracking-[0.14em]">
          결정 트리 진행
        </span>
        {onExpand && (
          <button
            onClick={onExpand}
            title="전체 트리 그래프 보기"
            className="text-[10px] font-mono text-brand-teal hover:text-brand-tealDark border border-brand-teal/40 hover:border-brand-tealDark px-1.5 py-0.5 transition-colors"
          >
            ⛶ 확대
          </button>
        )}
      </div>
      <div style={{ height: 400 }}>
        {!hasContent ? (
          <div className="h-full flex items-center justify-center text-ink-500 text-[10.5px] italic font-mono">
            진행된 결정 트리 없음
          </div>
        ) : (
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
            zoomOnScroll={false}
            panOnDrag={true}
            zoomOnDoubleClick={false}
            minZoom={0.2}
            maxZoom={1.5}
          >
            <Background gap={14} color="rgba(120, 130, 150, 0.08)" />
          </ReactFlow>
        )}
      </div>
    </div>
  );
};

export default TriageTreeMinimap;
