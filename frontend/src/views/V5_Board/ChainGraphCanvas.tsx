/**
 * 공격 체인 그래프 캔버스 — V-5 보드의 chain_nodes + chain_edges 시각화.
 *
 * SF-07 (Investigation Board) + UF-04 (수사관 주도 시나리오 구성) 의 일부.
 * 백엔드 응답 BoardResponse.nodes / .edges 를 받아 SVG 그래프로 렌더링.
 *
 * 자동 배치: NODES_PER_ROW 개씩 격자. chain_nodes.pos_x / pos_y 영속화는
 * 추후 작업 — 현재 모두 (0,0) 이라 자동 배치로 처리.
 *
 * 엣지 생성 모드:
 *   - edgeMode=true 일 때 노드 1번째 클릭 = 시작점 (초록), 2번째 클릭 = 끝점 → onCreateEdge
 *   - edgeMode=false 일 때 노드 클릭 = onSelectNode (기존 동작)
 */
import { useMemo } from 'react';

import type { BoardEdge, BoardNode } from '@/types';

interface ChainGraphCanvasProps {
  nodes: BoardNode[];
  edges: BoardEdge[];
  activeNodeId: string | null;
  edgeMode: boolean;
  edgeStartId: string | null;
  onSelectNode: (n: BoardNode) => void;
  onPickEdgeEnd: (fromId: string, toId: string) => void;
}

const NODE_W = 168;
const NODE_H = 64;
const GAP_X = 32;
const GAP_Y = 28;
const PAD = 18;
const NODES_PER_ROW = 4;

const ChainGraphCanvas = ({
  nodes,
  edges,
  activeNodeId,
  edgeMode,
  edgeStartId,
  onSelectNode,
  onPickEdgeEnd,
}: ChainGraphCanvasProps) => {
  // 자동 배치 — 격자 (row, col). 좌상단 (PAD, PAD) 부터.
  const layout = useMemo(() => {
    const m = new Map<string, { x: number; y: number }>();
    nodes.forEach((n, i) => {
      const row = Math.floor(i / NODES_PER_ROW);
      const col = i % NODES_PER_ROW;
      m.set(n.node_id, {
        x: PAD + col * (NODE_W + GAP_X),
        y: PAD + row * (NODE_H + GAP_Y),
      });
    });
    return m;
  }, [nodes]);

  if (nodes.length === 0) {
    return (
      <div className="text-[12px] text-ink-400 py-2">
        보드에 추가된 노드가 없습니다. 아래 ATT&CK 후보에서 "보드 추가" 를 눌러 노드를 생성하세요.
      </div>
    );
  }

  const rows = Math.ceil(nodes.length / NODES_PER_ROW);
  const cols = Math.min(nodes.length, NODES_PER_ROW);
  const width = PAD * 2 + cols * NODE_W + (cols - 1) * GAP_X;
  const height = PAD * 2 + rows * NODE_H + (rows - 1) * GAP_Y;

  const handleNodeClick = (n: BoardNode) => {
    if (edgeMode && edgeStartId && edgeStartId !== n.node_id) {
      onPickEdgeEnd(edgeStartId, n.node_id);
      return;
    }
    onSelectNode(n);
  };

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
      className="w-full bg-ink-950/40 border border-ink-700/40 rounded-xl"
      style={{ maxHeight: 380 }}
    >
      <defs>
        {/* 엣지 끝 화살표 — 파란 톤 */}
        <marker
          id="chain-arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerUnits="strokeWidth"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M0,0 L10,5 L0,10 z" fill="#3D7BFF" />
        </marker>
      </defs>

      {/* 엣지 — line + marker */}
      {edges.map((e) => {
        const a = layout.get(e.from_node_id);
        const b = layout.get(e.to_node_id);
        if (!a || !b) return null;
        const x1 = a.x + NODE_W / 2;
        const y1 = a.y + NODE_H / 2;
        const x2 = b.x + NODE_W / 2;
        const y2 = b.y + NODE_H / 2;
        return (
          <g key={e.edge_id}>
            <line
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke="#3D7BFF"
              strokeWidth={2}
              opacity={0.7}
              markerEnd="url(#chain-arrow)"
            />
            {e.label && (
              <text
                x={(x1 + x2) / 2}
                y={(y1 + y2) / 2 - 6}
                textAnchor="middle"
                fill="#9aa3b2"
                fontSize={10}
              >
                {e.label}
              </text>
            )}
          </g>
        );
      })}

      {/* 노드 — rect + label + status */}
      {nodes.map((n) => {
        const pos = layout.get(n.node_id);
        if (!pos) return null;
        const sel = activeNodeId === n.node_id;
        const isStart = edgeStartId === n.node_id;
        const isCandidate = edgeMode && edgeStartId !== null && edgeStartId !== n.node_id;
        const rejected = n.status === 'REJECTED';

        // stroke 색상 우선순위: start > candidate > selected > rejected > default
        let stroke = '#2A3441';
        if (rejected) stroke = '#EF4444';
        if (sel) stroke = '#3D7BFF';
        if (isCandidate) stroke = '#F59E0B';
        if (isStart) stroke = '#10B981';

        const fill = rejected ? '#1a1a1f' : '#161A21';
        const strokeWidth = isStart || isCandidate || sel ? 2.5 : 1;

        const labelText =
          n.label.length > 24 ? `${n.label.slice(0, 24)}…` : n.label;

        const statusColor =
          n.status === 'CONFIRMED'
            ? '#34D399'
            : n.status === 'REJECTED'
            ? '#F87171'
            : '#FBBF24';

        return (
          <g
            key={n.node_id}
            transform={`translate(${pos.x},${pos.y})`}
            onClick={() => handleNodeClick(n)}
            style={{ cursor: 'pointer' }}
          >
            <rect
              width={NODE_W}
              height={NODE_H}
              rx={10}
              ry={10}
              fill={fill}
              stroke={stroke}
              strokeWidth={strokeWidth}
              opacity={rejected ? 0.55 : 1}
            />
            <text
              x={NODE_W / 2}
              y={22}
              textAnchor="middle"
              fill="#E6E9F0"
              fontSize={11.5}
              fontWeight={600}
              textDecoration={rejected ? 'line-through' : 'none'}
            >
              {labelText}
            </text>
            <text
              x={NODE_W / 2}
              y={40}
              textAnchor="middle"
              fontSize={10}
            >
              <tspan fill="#9aa3b2">
                {n.is_ai_suggested ? '🧠 AI · ' : '👤 수동 · '}
              </tspan>
              <tspan fill={statusColor} fontWeight={600}>
                {n.status}
              </tspan>
            </text>
            {/* 엣지 모드 라벨 */}
            {isStart && (
              <text
                x={NODE_W / 2}
                y={56}
                textAnchor="middle"
                fill="#10B981"
                fontSize={9.5}
                fontWeight={700}
              >
                ↓ 엣지 시작점
              </text>
            )}
            {isCandidate && (
              <text
                x={NODE_W / 2}
                y={56}
                textAnchor="middle"
                fill="#F59E0B"
                fontSize={9.5}
                fontWeight={700}
              >
                + 연결 대상
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
};

export default ChainGraphCanvas;
