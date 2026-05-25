/**
 * ClueTreeView — Evidence Tree 시각화 (Phase C, 2026-05-25, byungwoo).
 *
 * 설계서: `docs/evidence_tree_paradigm.md` §4·§8
 *
 * 구조:
 *   root (uniform prior, 시스템 노드)
 *     ↓ 채택된 단서 1
 *     ↓ 채택된 단서 2
 *     ↓ ...
 *     ↓ current leaf
 *     ├─ 후보 1 (점선, IG=…)
 *     ├─ 후보 2 (점선, IG=…)
 *     └─ ... K 개 (entropy 기반 동적, 사용자 결정 §16)
 *
 * 클릭 동작:
 *   - 후보 클릭 → onAdoptCandidate(candidate) — Step3_Discovery 가 expand 호출
 *   - 채택 노드 클릭 → onClickNode(node) — 상세 패널 토글 (optional)
 *
 * 비주얼:
 *   - 채택 단서: 실선 brand-teal (TriageTreeMinimap 의 selected 옵션 스타일)
 *   - 후보:     점선 회색 + IG 게이지 (paradigm §8)
 *   - 루트:     얇은 점선 amber (uniform prior 표시)
 */
import { useMemo } from 'react';

import ReactFlow, {
  Background,
  type Edge,
  type Node,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';

import type {
  ClueCandidate,
  ClueTreePathNode,
} from '@/types/clueTree';

interface ClueTreeViewProps {
  /** root → current leaf 까지 채택 단서 경로. */
  path: ClueTreePathNode[];
  /** 현 leaf 의 다음 후보 (Information Gain 정렬). */
  candidates: ClueCandidate[];
  /** confidence 정보 — entropy_bits 게이지 표시용. */
  entropyBits: number;
  /** 후보 클릭 → 단서 채택 핸들러. */
  onAdoptCandidate: (candidate: ClueCandidate) => void;
  /** 채택된 단서 노드 클릭 (optional, 상세 보기). */
  onClickNode?: (node: ClueTreePathNode) => void;
  /** 후보 IG 표시 단위 — bits (기본) | percent (entropy 비). */
  igDisplay?: 'bits' | 'percent';
  /** 비활성 (loading 중 클릭 방지). */
  disabled?: boolean;
  /** ⛶ 확대 — 부모가 큰 오버레이로 띄울 때. */
  onExpand?: () => void;
  /** 헤더 텍스트 — 기본 "단서 트리". */
  title?: string;
  /** 그래프 영역 높이 (기본 460). */
  height?: number;
}

// 레이아웃 상수 — TriageTreeMinimap 스타일 정합
const LEVEL_H = 70;
const NODE_W = 168;
const CAND_W = 152;
const CAND_X_SPACING = 168;

const trunc = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}…` : s);

const buildLayout = (
  path: ClueTreePathNode[],
  candidates: ClueCandidate[],
  entropyBits: number,
  igDisplay: 'bits' | 'percent',
): { nodes: Node[]; edges: Edge[] } => {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  let centerX = 0;
  let leafId: string | null = null;

  // 1. 채택된 단서 경로 (root → leaf)
  path.forEach((p, lvl) => {
    const isRoot = p.clue_key === '__ROOT__';
    const id = `node-${p.node_id}`;
    leafId = id;

    nodes.push({
      id,
      position: { x: centerX, y: lvl * LEVEL_H },
      data: {
        label: isRoot
          ? '◆ 수사 시작 (Uniform 1/8)'
          : `${trunc(p.label, 22)}`,
      },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      draggable: false,
      connectable: false,
      selectable: !isRoot,
      style: {
        background: isRoot
          ? 'rgba(255, 149, 0, 0.10)'
          : 'rgba(38, 194, 129, 0.16)',
        border: isRoot
          ? '1px dashed rgba(255, 149, 0, 0.6)'
          : '1.5px solid #26C281',
        color: isRoot ? '#FF9500' : '#26C281',
        fontSize: '10px',
        fontWeight: 700,
        padding: '4px 6px',
        borderRadius: '0',
        width: NODE_W,
        textAlign: 'center' as const,
      },
    });

    if (lvl > 0) {
      const prev = path[lvl - 1];
      edges.push({
        id: `e-${prev.node_id}-${p.node_id}`,
        source: `node-${prev.node_id}`,
        target: id,
        style: { stroke: '#26C281', strokeWidth: 1.6 },
        animated: true,
      });
    }
  });

  // 2. 현 leaf 의 children candidates (점선)
  if (leafId && candidates.length > 0) {
    const baseY = path.length * LEVEL_H;
    const total = candidates.length;
    // entropy ≥ 2.5 → 5 / 1.5–2.5 → 3 / <1.5 → 2 (paradigm §16)
    // 최대 IG 값으로 게이지 정규화
    const maxIG = Math.max(...candidates.map((c) => c.expected_info_gain), 0.0001);

    candidates.forEach((cand, i) => {
      const offset = (i - (total - 1) / 2) * CAND_X_SPACING;
      const x = centerX + offset;
      const y = baseY;
      const cid = `cand-${cand.candidate_id}`;

      const ig = cand.expected_info_gain;
      // bits 또는 percent (entropy 대비) 표시
      const igLabel =
        igDisplay === 'percent'
          ? `${((ig / Math.max(entropyBits, 0.01)) * 100).toFixed(0)}% IG`
          : `IG ${ig.toFixed(3)}b`;
      // 막대 길이 (0~100%, IG / maxIG 정규화)
      const barPct = Math.max(6, Math.min(100, (ig / maxIG) * 100));

      // ReactFlow 의 data.label 은 string | ReactNode — 막대까지 그릴 수 있도록 ReactNode 로
      const labelNode = (
        <div className="flex flex-col items-stretch gap-0.5 leading-tight">
          <div className="text-[10px] text-ink-200 font-semibold text-center">
            {trunc(cand.label, 22)}
          </div>
          <div className="relative h-1.5 rounded-full bg-ink-900/70 overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 bg-brand-teal/60"
              style={{ width: `${barPct}%` }}
            />
          </div>
          <div className="text-[8.5px] text-ink-400 text-center font-mono">
            {igLabel}
          </div>
        </div>
      );

      nodes.push({
        id: cid,
        position: { x, y },
        data: { label: labelNode, candidate: cand },
        targetPosition: Position.Top,
        draggable: false,
        connectable: false,
        selectable: true,
        style: {
          background: 'rgba(28, 32, 48, 0.55)',
          border: '1px dashed rgba(112, 158, 200, 0.7)',
          color: '#C8D1E0',
          fontSize: '10px',
          fontWeight: 500,
          padding: '4px 6px',
          borderRadius: '0',
          width: CAND_W,
          textAlign: 'center' as const,
          cursor: 'pointer',
        },
      });

      edges.push({
        id: `e-${leafId}-${cid}`,
        source: leafId as string,
        target: cid,
        style: {
          stroke: 'rgba(112, 158, 200, 0.55)',
          strokeWidth: 1,
          strokeDasharray: '4 3',
        },
      });
    });
  }

  return { nodes, edges };
};

const ClueTreeView = ({
  path,
  candidates,
  entropyBits,
  onAdoptCandidate,
  onClickNode,
  igDisplay = 'bits',
  disabled = false,
  onExpand,
  title = '단서 트리',
  height = 460,
}: ClueTreeViewProps) => {
  const { nodes, edges } = useMemo(
    () => buildLayout(path, candidates, entropyBits, igDisplay),
    [path, candidates, entropyBits, igDisplay],
  );
  const hasContent = nodes.length > 0;
  const stableKey = useMemo(
    () =>
      [
        ...path.map((p) => p.node_id),
        ...candidates.map((c) => c.candidate_id),
      ].join('|'),
    [path, candidates],
  );

  const handleNodeClick = (_evt: React.MouseEvent, node: Node) => {
    if (disabled) return;
    if (node.id.startsWith('cand-')) {
      const cand = (node.data as { candidate?: ClueCandidate }).candidate;
      if (cand) onAdoptCandidate(cand);
    } else if (node.id.startsWith('node-') && onClickNode) {
      // path node 클릭
      const nodeIdRaw = node.id.replace('node-', '');
      const pathNode = path.find((p) => p.node_id === nodeIdRaw);
      if (pathNode) onClickNode(pathNode);
    }
  };

  return (
    <div className="border border-ink-700 bg-ink-950/40 flex flex-col">
      <div className="px-2.5 py-1.5 border-b border-ink-700 flex items-center justify-between shrink-0">
        <span className="text-[10px] text-ink-400 font-mono font-semibold uppercase tracking-[0.14em]">
          {title}
          <span className="ml-2 text-[9.5px] text-ink-500 normal-case tracking-normal">
            depth {Math.max(0, path.length - 1)} · 후보 {candidates.length}개 · entropy {entropyBits.toFixed(2)} bits
          </span>
        </span>
        {onExpand && (
          <button
            type="button"
            onClick={onExpand}
            title="전체 트리 보기"
            className="text-[10px] font-mono text-brand-teal hover:text-brand-tealDark border border-brand-teal/40 hover:border-brand-tealDark px-1.5 py-0.5 transition-colors"
          >
            ⛶ 확대
          </button>
        )}
      </div>
      <div style={{ height }}>
        {!hasContent ? (
          <div className="h-full flex items-center justify-center text-ink-500 text-[10.5px] italic font-mono">
            아직 채택된 단서 없음 — 후보를 클릭하거나 직접 입력하세요
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
            elementsSelectable={true}
            onNodeClick={handleNodeClick}
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

export default ClueTreeView;
