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
import { CLUE_DRAG_MIME, type CluePayload } from './LogPanel';

import type { BoardEdge, BoardNode, IncidentType } from '@/types';

// Phase P.7 (2026-05-27, easy 32554e4 머지) — 단서 노드의 어떤 사고유형
// 단서였는지 라벨링. 수사 보드 피드백 by easycode42 (이지호):
// "단서에 어떤 사고유형의 단서였는지 라벨링이 필요".
const INCIDENT_KO: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '자격증명',
  PRIVILEGE_ESCALATION: '권한상승',
  DATA_EXFILTRATION: '데이터유출',
  AUDIT_LOG_TAMPERING: '로그변조',
  RANSOMWARE: '랜섬',
  MISCONFIG_EXPOSURE: '설정노출',
  PHISH_INITIAL_ACCESS: '피싱',
  INSIDER_THREAT: '내부자',
  UNCLASSIFIED: '미분류',
};

const INCIDENT_COLORS: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '#5BA3F0',
  PRIVILEGE_ESCALATION: '#A56BE6',
  DATA_EXFILTRATION: '#E66BC2',
  AUDIT_LOG_TAMPERING: '#E68A6B',
  RANSOMWARE: '#E63B3B',
  MISCONFIG_EXPOSURE: '#E6A03B',
  PHISH_INITIAL_ACCESS: '#6BE69E',
  INSIDER_THREAT: '#3BC2E6',
  UNCLASSIFIED: '#7A8294',
};

/** 단서 노드 meta 에서 사고유형 추출. clue_bridge 가 tree.confirmed_hypotheses[-1] 을
 *  meta.hypothesis 로 기록하므로 그 값을 사용. 없으면 null. */
const incidentFromNode = (n: BoardNode): IncidentType | null => {
  if (!n.meta || (n.meta as { type?: string }).type !== 'clue') return null;
  const h = (n.meta as { hypothesis?: string | null }).hypothesis;
  if (!h) return null;
  return h as IncidentType;
};

interface ChainGraphCanvasProps {
  nodes: BoardNode[];
  edges: BoardEdge[];
  activeNodeId: string | null;
  edgeMode: boolean;
  edgeStartId: string | null;
  onSelectNode: (n: BoardNode) => void;
  onPickEdgeEnd: (fromId: string, toId: string) => void;
  onMoveNode?: (nodeId: string, x: number, y: number) => void;
  /** Phase P.6 — LogPanel 단서 탭에서 드래그된 단서를 보드 노드로 변환.
   *  null 이면 drop 비활성 (caseId 없을 때 등). */
  onDropClue?: (payload: CluePayload, posX: number, posY: number) => void;
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
  onDropClue,
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

  // 드래그 중 임시 위치 오버라이드 (백엔드 호출 전).
  // Phase P.7 (2026-05-27, easy 머지) — closure-staleness 수정.
  //   기존 동작: useEffect deps 에 [nodes, edgeMode, edgeStartId, onMoveNode,
  //   onPickEdgeEnd, onSelectNode, tempPos] 포함 → pointermove 마다 setTempPos
  //   가 tempPos 갱신 → useEffect 재실행 → listener 재등록 폭주.
  //   변경: ref 미러링 + deps 비움 (한 번만 등록).
  const [tempPos, setTempPos] = useState<Map<string, { x: number; y: number }>>(new Map());
  const tempPosRef = useRef<Map<string, { x: number; y: number }>>(new Map());
  const updateTempPos = (
    fn: (prev: Map<string, { x: number; y: number }>) => Map<string, { x: number; y: number }>,
  ) => {
    const next = fn(tempPosRef.current);
    tempPosRef.current = next;
    setTempPos(next);
  };
  // Phase P.6 — 단서 drag-over 시각 강조
  const [clueDragOver, setClueDragOver] = useState(false);

  // Phase P.7 (사용자 피드백: "확대 기능이 없어서 식별 어렵다") — zoom + pan 추가.
  //   - viewport state: tx/ty (translate) + scale
  //   - wheel: 마우스 위치 기준 zoom in/out (0.4 ~ 3.0)
  //   - 빈 영역 pointerdown + drag: pan
  //   - 노드 pointerdown 은 stopPropagation 으로 pan 차단됨 (handleNodePointerDown)
  const [viewport, setViewport] = useState({ tx: 0, ty: 0, scale: 1 });
  const viewportRef = useRef(viewport);
  useEffect(() => {
    viewportRef.current = viewport;
  }, [viewport]);
  const panRef = useRef<{
    startClientX: number;
    startClientY: number;
    startTx: number;
    startTy: number;
  } | null>(null);
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

  // SVG viewBox 좌표계로 client 좌표 변환
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

  // Phase P.7 — world (zoom/pan 적용 전) 좌표 변환. 노드 드래그·단서 drop 용.
  const toWorldCoords = (clientX: number, clientY: number) => {
    const { x: svgX, y: svgY } = toSvgCoords(clientX, clientY);
    const { tx, ty, scale } = viewportRef.current;
    return { x: (svgX - tx) / scale, y: (svgY - ty) / scale };
  };

  const handleNodePointerDown = (e: React.PointerEvent, n: BoardNode) => {
    // Phase P.11 (2026-05-27 사용자 피드백: "엣지모드 작동 안 함") —
    //   기존 동작: edgeMode 면 즉시 return → dragRef 미설정 → handleUp click
    //             분기 도달 X → 엣지 생성 안 됨.
    //   변경: edgeMode 라도 dragRef set (드래그는 비활성, 클릭만 처리).
    //         handleUp 에서 edgeMode 면 onPickEdgeEnd / onSelectNode 호출.
    e.stopPropagation();
    const pos = layout.get(n.node_id);
    if (!pos) return;
    // Phase P.7 — world 좌표 사용 (zoom/pan 인지)
    const { x: worldX, y: worldY } = toWorldCoords(e.clientX, e.clientY);
    dragRef.current = {
      nodeId: n.node_id,
      offX: worldX - pos.x,
      offY: worldY - pos.y,
      startClientX: e.clientX,
      startClientY: e.clientY,
      moved: false,
    };
  };

  // Phase P.7 (2026-05-27, easy 머지) — 항상 최신 props 를 참조하기 위해 ref 미러링.
  // pointermove/up listener 는 한 번만 등록 (closure-staleness 방지).
  const nodesRef = useRef(nodes);
  const edgeModeRef = useRef(edgeMode);
  const edgeStartIdRef = useRef(edgeStartId);
  const onMoveNodeRef = useRef(onMoveNode);
  const onSelectNodeRef = useRef(onSelectNode);
  const onPickEdgeEndRef = useRef(onPickEdgeEnd);
  useEffect(() => {
    nodesRef.current = nodes;
    edgeModeRef.current = edgeMode;
    edgeStartIdRef.current = edgeStartId;
    onMoveNodeRef.current = onMoveNode;
    onSelectNodeRef.current = onSelectNode;
    onPickEdgeEndRef.current = onPickEdgeEnd;
  }, [nodes, edgeMode, edgeStartId, onMoveNode, onSelectNode, onPickEdgeEnd]);

  useEffect(() => {
    const handleMove = (e: PointerEvent) => {
      const d = dragRef.current;
      if (!d) return;
      const dist = Math.abs(e.clientX - d.startClientX) + Math.abs(e.clientY - d.startClientY);
      if (dist > 3) d.moved = true;
      // Phase P.7 — world 좌표로 노드 위치 갱신
      const { x: worldX, y: worldY } = toWorldCoords(e.clientX, e.clientY);
      const nx = Math.max(0, Math.round(worldX - d.offX));
      const ny = Math.max(0, Math.round(worldY - d.offY));
      updateTempPos((prev) => {
        const m = new Map(prev);
        m.set(d.nodeId, { x: nx, y: ny });
        return m;
      });
    };
    const handleUp = () => {
      const d = dragRef.current;
      if (!d) return;
      dragRef.current = null;
      // Phase P.11 — edgeMode 일 때는 드래그 이동 무시 (위치 영속화 X), 클릭만 처리
      if (d.moved && !edgeModeRef.current) {
        // 드래그 종료 → 영속화 (ref 의 최신 tempPos·onMoveNode 사용)
        const final = tempPosRef.current.get(d.nodeId);
        if (final && onMoveNodeRef.current) {
          onMoveNodeRef.current(d.nodeId, final.x, final.y);
        }
      } else {
        // 클릭으로 간주 (ref 의 최신 nodes·edgeMode·콜백 사용)
        const n = nodesRef.current.find((x) => x.node_id === d.nodeId);
        if (n) {
          if (
            edgeModeRef.current &&
            edgeStartIdRef.current &&
            edgeStartIdRef.current !== n.node_id
          ) {
            onPickEdgeEndRef.current(edgeStartIdRef.current, n.node_id);
          } else {
            onSelectNodeRef.current(n);
          }
        }
        // 클릭은 임시 위치 폐기
        updateTempPos((prev) => {
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
    // deps 비움 — listener 는 한 번만 등록. 최신 값은 ref 로 참조.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 백엔드 응답이 갱신되면 임시 위치 초기화 (서버 값으로 통합)
  useEffect(() => {
    tempPosRef.current = new Map();
    setTempPos(new Map());
  }, [nodes]);

  // Phase P.14 (2026-05-27 사용자 피드백: "보드 넘어가면 화면 망가짐") —
  //   기존: nodes.length===0 시 <div> 반환 → SVG 영역 사라짐 → Card 비율 깨짐 +
  //         단서 drop zone 사라져서 LogPanel 단서 드래그 무의미
  //   변경: 빈 보드도 SVG 렌더 + drop zone 유지. 안내 text 는 SVG 안에 overlay.
  const isEmpty = nodes.length === 0;

  // 캔버스 크기 — 빈 보드도 안전한 default. 격자 + 드래그 영역.
  const rows = Math.max(1, Math.ceil(nodes.length / NODES_PER_ROW));
  const cols = isEmpty ? NODES_PER_ROW : Math.min(nodes.length, NODES_PER_ROW);
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

  // Phase P.11 (사용자 피드백: "확대 작동 안 함") — React onWheel 은 passive listener
  // 라 preventDefault 무시됨. native addEventListener 로 {passive:false} 등록.
  // width/height 는 ref 로 전달 (deps 변경 시 listener 재등록 폭주 방지).
  const sizeRef = useRef({ width, height });
  useEffect(() => {
    sizeRef.current = { width, height };
  }, [width, height]);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheelNative = (e: WheelEvent) => {
      e.preventDefault();
      const { tx, ty, scale } = viewportRef.current;
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      const newScale = Math.min(3.0, Math.max(0.4, scale * delta));
      if (newScale === scale) return;
      const rect = svg.getBoundingClientRect();
      const { width: w, height: h } = sizeRef.current;
      const vbScaleX = w / rect.width;
      const vbScaleY = h / rect.height;
      const mouseSvgX = (e.clientX - rect.left) * vbScaleX;
      const mouseSvgY = (e.clientY - rect.top) * vbScaleY;
      const ratio = newScale / scale;
      const newTx = mouseSvgX - (mouseSvgX - tx) * ratio;
      const newTy = mouseSvgY - (mouseSvgY - ty) * ratio;
      setViewport({ tx: newTx, ty: newTy, scale: newScale });
    };
    svg.addEventListener('wheel', onWheelNative, { passive: false });
    return () => {
      svg.removeEventListener('wheel', onWheelNative);
    };
  }, []);

  const handleSvgPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    // 노드/엣지 가 아닌 빈 영역에서만 pan 시작
    // (노드 onPointerDown 은 stopPropagation 으로 여기 도달 X)
    if (edgeMode) return; // 엣지 모드면 pan 비활성 (클릭으로 엣지 생성)
    panRef.current = {
      startClientX: e.clientX,
      startClientY: e.clientY,
      startTx: viewportRef.current.tx,
      startTy: viewportRef.current.ty,
    };
  };

  useEffect(() => {
    const handlePanMove = (e: PointerEvent) => {
      const p = panRef.current;
      if (!p) return;
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const vbScaleX = width / rect.width;
      const vbScaleY = height / rect.height;
      const dx = (e.clientX - p.startClientX) * vbScaleX;
      const dy = (e.clientY - p.startClientY) * vbScaleY;
      setViewport({
        tx: p.startTx + dx,
        ty: p.startTy + dy,
        scale: viewportRef.current.scale,
      });
    };
    const handlePanUp = () => {
      panRef.current = null;
    };
    window.addEventListener('pointermove', handlePanMove);
    window.addEventListener('pointerup', handlePanUp);
    return () => {
      window.removeEventListener('pointermove', handlePanMove);
      window.removeEventListener('pointerup', handlePanUp);
    };
  }, [width, height]);

  const resetView = () => setViewport({ tx: 0, ty: 0, scale: 1 });
  // Phase P.11 — 휠 외 클릭으로도 zoom 가능 (사용자 피드백: "확대 기능 작동 안 함")
  const zoomBy = (factor: number) => {
    const { tx, ty, scale } = viewportRef.current;
    const newScale = Math.min(3.0, Math.max(0.4, scale * factor));
    if (newScale === scale) return;
    // 중앙 기준 zoom — 마우스 위치 정보 없으므로 SVG 중앙 기준
    const cx = sizeRef.current.width / 2;
    const cy = sizeRef.current.height / 2;
    const ratio = newScale / scale;
    setViewport({
      tx: cx - (cx - tx) * ratio,
      ty: cy - (cy - ty) * ratio,
      scale: newScale,
    });
  };

  // Phase P.6 — drop zone 핸들러 (LogPanel 단서 탭 → ChainGraph)
  const handleClueDragOver = (e: React.DragEvent<SVGSVGElement>) => {
    if (!onDropClue) return;
    // dataTransfer 타입 검사 — 단서 MIME 일 때만 drop 허용
    if (!e.dataTransfer.types.includes(CLUE_DRAG_MIME)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    if (!clueDragOver) setClueDragOver(true);
  };

  const handleClueDragLeave = (e: React.DragEvent<SVGSVGElement>) => {
    // SVG 내부 자식으로 이동하면 leave 가 발생하나 relatedTarget 이 SVG 내부.
    // currentTarget(SVG) 의 contains 검사로 진짜 outside 인지 확인.
    const related = e.relatedTarget as Node | null;
    if (related && e.currentTarget.contains(related)) return;
    setClueDragOver(false);
  };

  const handleClueDrop = (e: React.DragEvent<SVGSVGElement>) => {
    if (!onDropClue) return;
    e.preventDefault();
    setClueDragOver(false);
    const raw = e.dataTransfer.getData(CLUE_DRAG_MIME);
    if (!raw) return;
    let payload: CluePayload;
    try {
      payload = JSON.parse(raw) as CluePayload;
    } catch {
      return;
    }
    if (!payload.clue_key) return;
    // Phase P.7 — world 좌표 (zoom/pan 인지) 로 drop 위치 계산
    const { x, y } = toWorldCoords(e.clientX, e.clientY);
    // 노드 좌상단 기준 좌표 (NODE_W/H 의 중앙이 드롭 위치가 되도록 조정)
    const pos_x = Math.max(0, Math.round(x - NODE_W / 2));
    const pos_y = Math.max(0, Math.round(y - NODE_H / 2));
    onDropClue(payload, pos_x, pos_y);
  };

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
      className={
        'w-full border rounded-xl transition-colors ' +
        (clueDragOver
          ? 'bg-brand-teal/10 border-brand-teal/60 shadow-[0_0_0_2px_rgba(45,212,191,0.25)]'
          : 'bg-ink-950/40 border-ink-700/40')
      }
      // Phase P.7 (사용자 피드백: "공격체인그래프쪽이 너무 작다") — 영역 확장
      style={{ maxHeight: 680, minHeight: 480, touchAction: 'none' }}
      onDragOver={handleClueDragOver}
      onDragLeave={handleClueDragLeave}
      onDrop={handleClueDrop}
      // Phase P.11 — zoom 은 native addEventListener {passive:false} 로 등록
      // (React onWheel 은 passive 라 preventDefault 무시됨). pan 만 React 핸들러.
      onPointerDown={handleSvgPointerDown}
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

      {/* Phase P.7 — zoom/pan transform 적용 (모든 콘텐츠 감싸기) */}
      <g transform={`translate(${viewport.tx},${viewport.ty}) scale(${viewport.scale})`}>

      {/* Phase P.14 — 빈 보드 안내 overlay (SVG 안에 그려 drop zone 유지) */}
      {isEmpty && (
        <g pointerEvents="none">
          <text
            x={baseWidth / 2}
            y={baseHeight / 2 - 24}
            textAnchor="middle"
            fill="#5EEAD4"
            fontSize={14}
            fontWeight={600}
          >
            🔍 단서를 여기로 드래그하거나
          </text>
          <text
            x={baseWidth / 2}
            y={baseHeight / 2 + 2}
            textAnchor="middle"
            fill="#9aa3b2"
            fontSize={11.5}
          >
            아래 ATT&CK 후보의 [보드 추가] 로 노드를 생성하세요
          </text>
          <text
            x={baseWidth / 2}
            y={baseHeight / 2 + 22}
            textAnchor="middle"
            fill="#7A8294"
            fontSize={10}
            fontFamily="monospace"
          >
            우측 LogPanel 의 [🔍 단서] 탭 활용
          </text>
        </g>
      )}

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
        // Phase P.7 (easy 머지) — 단서 노드의 사고유형 추출
        const incident = isClue ? incidentFromNode(n) : null;
        const incidentColor = incident ? INCIDENT_COLORS[incident] : '#2DD4BF';

        // stroke 색상 우선순위: start > candidate > selected > rejected > clue(hypothesis) > default
        let stroke = '#2A3441';
        if (isClue) stroke = incidentColor; // 사고유형 색상 (없으면 teal)
        if (rejected) stroke = '#EF4444';
        if (sel) stroke = '#3D7BFF';
        if (isCandidate) stroke = '#F59E0B';
        if (isStart) stroke = '#10B981';

        // 단서 노드 fill — 사고유형 hue 의 어두운 톤 (배경 인식성)
        const fill = rejected ? '#1a1a1f' : isClue ? '#10181F' : '#161A21';
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
            {/* Phase P.7 (easy 머지) — 단서 노드 좌측 사고유형 색상 띠 (4px) */}
            {isClue && incident && (
              <rect
                x={0}
                y={0}
                width={4}
                height={NODE_H}
                rx={2}
                fill={incidentColor}
                opacity={0.95}
              />
            )}
            {/* Phase P.7 (easy 머지) — 단서 노드 우상단 사고유형 한국어 배지 */}
            {isClue && incident && (
              <>
                <rect
                  x={NODE_W - 56}
                  y={4}
                  width={52}
                  height={13}
                  rx={3}
                  fill={incidentColor}
                  fillOpacity={0.18}
                  stroke={incidentColor}
                  strokeWidth={0.8}
                />
                <text
                  x={NODE_W - 30}
                  y={13.5}
                  textAnchor="middle"
                  fill={incidentColor}
                  fontSize={9}
                  fontWeight={700}
                  style={{ fontFamily: 'system-ui, sans-serif' }}
                >
                  {INCIDENT_KO[incident]}
                </text>
              </>
            )}
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
      </g>
      {/* Phase P.11 — zoom 컨트롤 (SVG 우상단 고정 오버레이): [-] [percent] [+] [1:1] */}
      <g
        transform={`translate(${Math.max(8, width - 152)}, 8)`}
        style={{ cursor: 'pointer' }}
      >
        <rect x={0} y={0} width={144} height={22} rx={4}
              fill="#0f1117" stroke="#2a3441" strokeWidth={0.8} />
        {/* [-] 축소 */}
        <g onPointerDown={(e) => { e.stopPropagation(); zoomBy(0.85); }}>
          <rect x={3} y={3} width={20} height={16} rx={3}
                fill="#1a1f29" stroke="#2a3441" strokeWidth={0.6} />
          <text x={13} y={15} textAnchor="middle" fill="#9aa3b2"
                fontSize={13} fontWeight={700}>−</text>
        </g>
        {/* 현재 zoom % */}
        <text x={56} y={15} textAnchor="middle"
              fill={viewport.scale === 1 ? '#9aa3b2' : '#5EEAD4'}
              fontSize={10} fontFamily="monospace">
          {`${Math.round(viewport.scale * 100)}%`}
        </text>
        {/* [+] 확대 */}
        <g onPointerDown={(e) => { e.stopPropagation(); zoomBy(1.18); }}>
          <rect x={88} y={3} width={20} height={16} rx={3}
                fill="#1a1f29" stroke="#2a3441" strokeWidth={0.6} />
          <text x={98} y={15} textAnchor="middle" fill="#5EEAD4"
                fontSize={12} fontWeight={700}>+</text>
        </g>
        {/* [1:1] reset */}
        <g
          onPointerDown={(e) => {
            e.stopPropagation();
            resetView();
          }}
        >
          <rect x={113} y={3} width={28} height={16} rx={3}
                fill="#1a1f29" stroke="#2a3441" strokeWidth={0.6} />
          <text x={127} y={14} textAnchor="middle"
                fill="#5EEAD4" fontSize={9} fontWeight={700}>
            1:1
          </text>
        </g>
      </g>
    </svg>
  );
};

export default ChainGraphCanvas;
