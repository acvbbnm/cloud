/**
 * 공격 체인 그래프 캔버스 — V-5 보드의 chain_nodes + chain_edges 시각화.
 *
 * SF-07 (Investigation Board) + UF-04 (수사관 주도 시나리오 구성) 의 일부.
 * 백엔드 응답 BoardResponse.nodes / .edges 를 받아 SVG 그래프로 렌더링.
 *
 * 배치:
 *   - node.pos_x / pos_y 가 양수면 그 위치 사용 (영속화된 위치, Phase 2.2)
 *   - 0/null 이면 자동 격자 배치 (좌상단 PAD 부터 NODES_PER_ROW 단위)
 *
 * 드래그 (Phase 2.2):
 *   - pointerdown on rect → 드래그 시작 + 캔버스 좌표계 기준 오프셋 저장
 *   - pointermove on svg → 임시 위치 갱신 (로컬 state, 백엔드 호출 X)
 *   - pointerup → onMoveNode(nodeId, x, y) 호출 → 부모가 PATCH /api/board/nodes/{id}
 *   - 드래그 거리 < 4px 이면 클릭으로 간주 (onSelectNode 호출)
 *
 * 엣지 생성 모드:
 *   - edgeMode=true 일 때 노드 1번째 클릭 = 시작점 (초록), 2번째 클릭 = 끝점 → onCreateEdge
 *   - edgeMode=false 일 때 노드 클릭 = onSelectNode (기존 동작)
 *   - edgeMode 일 때는 드래그 비활성
 */
import { useMemo, useRef, useState, useEffect } from 'react';

import { isClueNode } from '@/api/board';

import type { BoardEdge, BoardNode } from '@/types';

interface ChainGraphCanvasProps {
  nodes: BoardNode[];
  edges: BoardEdge[];
  activeNodeId: string | null;
  edgeMode: boolean;
  edgeStartId: string | null;
  onSelectNode: (n: BoardNode) => void;
  onPickEdgeEnd: (fromId: string, toId: string) => void;
  onMoveNode?: (nodeId: string, x: number, y: number) => void;
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
  onMoveNode,
}: ChainGraphCanvasProps) => {
  // 영속 위치 우선 + 미설정 시 격자 배치
  const baseLayout = useMemo(() => {
    const m = new Map<string, { x: number; y: number }>();
    nodes.forEach((n, i) => {
      const hasSaved = (n.pos_x ?? 0) > 0 || (n.pos_y ?? 0) > 0;
      if (hasSaved) {
        m.set(n.node_id, { x: n.pos_x ?? PAD, y: n.pos_y ?? PAD });
      } else {
        const row = Math.floor(i / NODES_PER_ROW);
        const col = i % NODES_PER_ROW;
        m.set(n.node_id, {
          x: PAD + col * (NODE_W + GAP_X),
          y: PAD + row * (NODE_H + GAP_Y),
        });
      }
    });
    return m;
  }, [nodes]);

  // 드래그 중 임시 위치 오버라이드 (백엔드 호출 전)
  const [tempPos, setTempPos] = useState<Map<string, { x: number; y: number }>>(new Map());
  const layout = useMemo(() => {
    if (tempPos.size === 0) return baseLayout;
    const m = new Map(baseLayout);
    tempPos.forEach((v, k) => m.set(k, v));
    return m;
  }, [baseLayout, tempPos]);

  // 드래그 상태
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{
    nodeId: string;
    offX: number;
    offY: number;
    startClientX: number;
    startClientY: number;
    moved: boolean;
  } | null>(null);

  // SVG 좌표계로 client 좌표 변환
  const toSvgCoords = (clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const p = pt.matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  };

  const handleNodePointerDown = (e: React.PointerEvent, n: BoardNode) => {
    if (edgeMode) return; // 엣지 모드일 때는 드래그 비활성
    if (!onMoveNode) return;
    e.stopPropagation();
    const pos = layout.get(n.node_id);
    if (!pos) return;
    const { x: svgX, y: svgY } = toSvgCoords(e.clientX, e.clientY);
    dragRef.current = {
      nodeId: n.node_id,
      offX: svgX - pos.x,
      offY: svgY - pos.y,
      startClientX: e.clientX,
      startClientY: e.clientY,
      moved: false,
    };
  };

  useEffect(() => {
    const handleMove = (e: PointerEvent) => {
      const d = dragRef.current;
      if (!d) return;
      const dist = Math.abs(e.clientX - d.startClientX) + Math.abs(e.clientY - d.startClientY);
      if (dist > 3) d.moved = true;
      const { x: svgX, y: svgY } = toSvgCoords(e.clientX, e.clientY);
      const nx = Math.max(0, Math.round(svgX - d.offX));
      const ny = Math.max(0, Math.round(svgY - d.offY));
      setTempPos((prev) => {
        const m = new Map(prev);
        m.set(d.nodeId, { x: nx, y: ny });
        return m;
      });
    };
    const handleUp = () => {
      const d = dragRef.current;
      if (!d) return;
      dragRef.current = null;
      if (d.moved) {
        // 드래그 종료 → 영속화
        const final = tempPos.get(d.nodeId);
        if (final && onMoveNode) {
          onMoveNode(d.nodeId, final.x, final.y);
        }
      } else {
        // 클릭으로 간주
        const n = nodes.find((x) => x.node_id === d.nodeId);
        if (n) {
          if (edgeMode && edgeStartId && edgeStartId !== n.node_id) {
            onPickEdgeEnd(edgeStartId, n.node_id);
          } else {
            onSelectNode(n);
          }
        }
        // 클릭은 임시 위치 폐기
        setTempPos((prev) => {
          if (!prev.has(d.nodeId)) return prev;
          const m = new Map(prev);
          m.delete(d.nodeId);
          return m;
        });
      }
    };
    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
    return () => {
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
    };
  }, [nodes, edgeMode, edgeStartId, onMoveNode, onPickEdgeEnd, onSelectNode, tempPos]);

  // 백엔드 응답이 갱신되면 임시 위치 초기화 (서버 값으로 통합)
  useEffect(() => {
    setTempPos(new Map());
  }, [nodes]);

  if (nodes.length === 0) {
    return (
      <div className="text-[12px] text-ink-400 py-2">
        보드에 추가된 노드가 없습니다. 아래 ATT&CK 후보에서 "보드 추가" 를 눌러 노드를 생성하세요.
      </div>
    );
  }

  // 캔버스 크기 — 격자 기본 + 드래그로 이동한 노드 범위 모두 포함
  const rows = Math.ceil(nodes.length / NODES_PER_ROW);
  const cols = Math.min(nodes.length, NODES_PER_ROW);
  const baseWidth = PAD * 2 + cols * NODE_W + (cols - 1) * GAP_X;
  const baseHeight = PAD * 2 + rows * NODE_H + (rows - 1) * GAP_Y;
  let maxRight = baseWidth;
  let maxBottom = baseHeight;
  layout.forEach((p) => {
    maxRight = Math.max(maxRight, p.x + NODE_W + PAD);
    maxBottom = Math.max(maxBottom, p.y + NODE_H + PAD);
  });
  const width = maxRight;
  const height = maxBottom;

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
      className="w-full bg-ink-950/40 border border-ink-700/40 rounded-xl"
      style={{ maxHeight: 380, touchAction: 'none' }}
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
        // Phase O — 단서 노드 시각 구분 (type='clue')
        const isClue = isClueNode(n);

        // stroke 색상 우선순위: start > candidate > selected > rejected > clue > default
        let stroke = '#2A3441';
        if (isClue) stroke = '#2DD4BF'; // teal — 단서 기본 stroke
        if (rejected) stroke = '#EF4444';
        if (sel) stroke = '#3D7BFF';
        if (isCandidate) stroke = '#F59E0B';
        if (isStart) stroke = '#10B981';

        // 단서 노드는 살짝 밝은 fill (teal 톤) — ATT&CK 노드와 한눈에 구분
        const fill = rejected ? '#1a1a1f' : isClue ? '#0F2F2C' : '#161A21';
        const strokeWidth = isStart || isCandidate || sel || isClue ? 2.5 : 1;

        // 단서 노드는 prefix 아이콘 + 짧은 라벨
        const rawLabel = isClue ? `🔍 ${n.label}` : n.label;
        const labelText =
          rawLabel.length > 24 ? `${rawLabel.slice(0, 24)}…` : rawLabel;

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
            onPointerDown={(e) => handleNodePointerDown(e, n)}
            style={{ cursor: edgeMode ? 'pointer' : 'grab', touchAction: 'none' }}
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
              <tspan fill={isClue ? '#5EEAD4' : '#9aa3b2'}>
                {isClue ? '단서 · ' : n.is_ai_suggested ? ' AI · ' : ' 수동 · '}
              </tspan>
              <tspan fill={statusColor} fontWeight={600}>
                {n.status}
              </tspan>
              {isClue &&
                n.meta &&
                'stage' in n.meta &&
                typeof (n.meta as { stage?: number }).stage === 'number' && (
                  <tspan fill="#5EEAD4">
                    {` · S${(n.meta as { stage: number }).stage}`}
                  </tspan>
                )}
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
