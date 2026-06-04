/**
 * ClueTreeView — Evidence Tree 시각화 (Phase C, 2026-05-25, byungwoo).
 * Rev 2 (2026-05-25): TriageTreeMinimap 드리프트 anchor 패턴으로 재설계.
 *
 * 설계서: `docs/evidence_tree_paradigm.md` §4·§8
 *
 * 트리 구조 (legacy TriageTreeMinimap 정합):
 *   ROOT (◆ 수사 시작, anchor X=0)
 *    │
 *    ├─ cand1  cand2  cand3*  cand4  cand5    ← root 의 children_candidates fan-out
 *    │           ↓ (chosen* drifts anchor)
 *    │      cand3 (실선 — 채택된 단서)
 *    │       │
 *    │       ├─ cand6  cand7*  cand8          ← depth 1 fan-out
 *    │       │           ↓
 *    │       │      cand7 (실선)
 *    │       │       ├─ cand9*  cand10        ← depth 2 fan-out (CURRENT LEAF)
 *    │       │       ↑ 클릭 가능 (점선)
 *
 * - 채택 단서: 실선 brand-teal
 * - 선택된 후보 (= 다음 채택 단서): 후보 row 와 채택 노드 동시에 노출 + 실선 연결
 * - 미선택 후보 (siblings): 점선 회색, 클릭 불가 (과거 분기점이라 채택 불가)
 * - 현재 leaf 의 후보: 점선 회색 + 클릭 가능 (IG 게이지 표시)
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
  SerializedClueTree,
  SerializedClueTreeNode,
} from '@/types/clueTree';

interface ClueTreeViewProps {
  /** 전체 트리 (백엔드 ClueTreeResponse.tree). */
  tree: SerializedClueTree;
  /** 현재 leaf 노드 ID (트리 자라기 위치). */
  currentLeafId: string;
  /** confidence 정보 — entropy_bits 게이지 표시용. */
  entropyBits: number;
  /** 후보 클릭 → 단서 채택 핸들러. 현재 leaf 의 후보에서만 트리거. */
  onAdoptCandidate: (candidate: ClueCandidate) => void;
  /** 채택된 단서 노드 클릭 (optional, 상세 보기). */
  onClickNode?: (node: SerializedClueTreeNode) => void;
  /**
   * ✏ 직접 입력 슬롯 클릭 — 트리 안에서 자유 단서 입력.
   * 현재 leaf 의 후보 옆에 노드로 표시되어 트리가 끊기지 않게 함.
   */
  onDirectInputClick?: () => void;
  /** 비활성 (loading 중 클릭 방지). */
  disabled?: boolean;
  /** ⛶ 확대 — 부모가 큰 오버레이로 띄울 때. */
  onExpand?: () => void;
  /** ⟲ 초기화 — 기존 트리 폐기 + cold-start (2026-05-25 이전 트리 마이그레이션용). */
  onReset?: () => void;
  /** 헤더 텍스트 — 기본 "단서 트리". */
  title?: string;
  /** 그래프 영역 높이 (기본 460). */
  height?: number;
}

// 레이아웃 상수 — TriageTreeMinimap 스타일 정합 (단서가 길어서 약간 크게)
const LEVEL_H = 110;            // 채택 노드 간 세로 간격
const OPT_Y_OFFSET = 56;        // 채택 노드 → 후보 row 세로 간격
const OPT_W = 122;              // 후보 간 수평 간격
const NODE_WIDTH = 168;         // 채택 노드 폭
const CAND_WIDTH = 110;         // 후보 노드 폭
const MAX_STEP_DRIFT = 80;      // 선택된 후보의 X 드리프트 클램프 (anchor 이동 한계)

const trunc = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}…` : s);

/** root → currentLeaf 까지 채택 노드 시퀀스를 depth 순서로 추출. */
const collectPath = (
  nodes: Record<string, SerializedClueTreeNode>,
  rootId: string,
  leafId: string,
): SerializedClueTreeNode[] => {
  if (!nodes[leafId]) return nodes[rootId] ? [nodes[rootId]] : [];
  const chain: SerializedClueTreeNode[] = [];
  let cur: string | null = leafId;
  while (cur && nodes[cur]) {
    chain.push(nodes[cur]);
    cur = nodes[cur].parent_id;
  }
  return chain.reverse();
};

interface BuildResult {
  nodes: Node[];
  edges: Edge[];
}

const buildLayout = (
  tree: SerializedClueTree,
  currentLeafId: string,
  enableDirectInput: boolean,
): BuildResult => {
  const rfNodes: Node[] = [];
  const rfEdges: Edge[] = [];

  const path = collectPath(tree.nodes, tree.root_id, currentLeafId);
  if (path.length === 0) return { nodes: rfNodes, edges: rfEdges };

  let anchorX = 0;

  path.forEach((adopted, depth) => {
    const isRoot = adopted.clue_key === '__ROOT__';
    const isCurrentLeaf = adopted.node_id === currentLeafId;
    const adoptedNodeId = `adopted-${adopted.node_id}`;
    const adoptedY = depth * LEVEL_H;

    // ── 채택 노드 (실선 또는 root 점선 amber) ──
    rfNodes.push({
      id: adoptedNodeId,
      position: { x: anchorX, y: adoptedY },
      data: {
        label: isRoot
          ? '◆ 수사 시작 (Uniform 1/8)'
          : trunc(adopted.label, 22),
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
        width: NODE_WIDTH,
        textAlign: 'center' as const,
      },
    });

    // ── children_candidates fan-out (이 채택 노드 아래) ──
    // 결정 시점에 보였던 모든 후보를 dashed 로 표시. 그 중 실제 채택된 다음 노드는
    // "다음 채택 노드의 clue_key" 와 매칭하여 실선·brand-teal 로 강조.
    const candidates = adopted.children_candidates ?? [];
    const candCount = candidates.length;
    // 현재 leaf 면 직접 입력 슬롯도 children 의 일부로 fan-out 균등 배치
    const slotCount = isCurrentLeaf && enableDirectInput ? 1 : 0;
    const total = candCount + slotCount;
    if (total === 0) return;

    // 다음 채택 노드의 clue_key (있으면 → 선택된 후보 식별)
    const nextAdopted = path[depth + 1];
    const chosenClueKey = nextAdopted?.clue_key;
    const isLeafCandidates = isCurrentLeaf; // 현재 leaf 의 후보만 클릭 가능

    // 후보별 max IG (게이지 정규화)
    const maxIG = Math.max(...candidates.map((c) => c.expected_info_gain), 0.0001);

    let chosenAbsX = anchorX; // 선택된 후보의 절대 X (다음 anchor 계산용)
    candidates.forEach((cand, i) => {
      const offset = (i - (total - 1) / 2) * OPT_W;
      const x = anchorX + offset;
      const y = adoptedY + OPT_Y_OFFSET;
      const cid = `cand-${adopted.node_id}-${cand.candidate_id}`;
      const isChosen = chosenClueKey === cand.clue_key;
      if (isChosen) chosenAbsX = x;

      // 선택된 후보는 dashed 가 아니라 solid + brand-teal 로 표시
      const border = isChosen
        ? '1.5px solid rgba(38, 194, 129, 0.85)'
        : '1px dashed rgba(112, 158, 200, 0.5)';
      const background = isChosen
        ? 'rgba(38, 194, 129, 0.12)'
        : 'rgba(28, 32, 48, 0.45)';
      const color = isChosen ? '#26C281' : 'rgba(195, 205, 220, 0.75)';

      // 현재 leaf 후보만 클릭 가능
      const clickable = isLeafCandidates && !isChosen;

      const ig = cand.expected_info_gain;
      const igPct = Math.max(6, Math.min(100, (ig / maxIG) * 100));
      const igText = `IG ${ig.toFixed(3)}b`;
      const labelNode = (
        <div className="flex flex-col items-stretch gap-0.5 leading-tight">
          <div
            className="text-[9.5px] font-semibold text-center"
            style={{ color }}
          >
            {trunc(cand.label, 14)}
          </div>
          {isLeafCandidates && (
            <>
              <div className="relative h-1 rounded-full bg-ink-900/70 overflow-hidden">
                <div
                  className="absolute inset-y-0 left-0 bg-brand-teal/60"
                  style={{ width: `${igPct}%` }}
                />
              </div>
              <div className="text-[8px] text-ink-500 text-center font-mono">
                {igText}
              </div>
            </>
          )}
        </div>
      );

      rfNodes.push({
        id: cid,
        position: { x, y },
        data: { label: labelNode, candidate: cand },
        targetPosition: Position.Top,
        sourcePosition: Position.Bottom,
        draggable: false,
        connectable: false,
        selectable: clickable,
        style: {
          background,
          border,
          color,
          fontSize: '9.5px',
          fontWeight: isChosen ? 700 : 500,
          padding: '3px 5px',
          borderRadius: '0',
          width: CAND_WIDTH,
          textAlign: 'center' as const,
          cursor: clickable ? 'pointer' : 'default',
          opacity: clickable || isChosen ? 1 : 0.65,
        },
      });

      // 채택 노드 → 후보 edge
      rfEdges.push({
        id: `e-${adoptedNodeId}-${cid}`,
        source: adoptedNodeId,
        target: cid,
        style: {
          stroke: isChosen
            ? 'rgba(38, 194, 129, 0.85)'
            : 'rgba(80, 90, 105, 0.55)',
          strokeWidth: isChosen ? 1.5 : 1,
          strokeDasharray: isChosen ? undefined : '3 3',
        },
      });

      // 선택된 후보 → 다음 채택 노드 edge (실선)
      if (isChosen && nextAdopted) {
        rfEdges.push({
          id: `e-${cid}-adopted-${nextAdopted.node_id}`,
          source: cid,
          target: `adopted-${nextAdopted.node_id}`,
          style: { stroke: '#26C281', strokeWidth: 1.5 },
          animated: true,
        });
      }
    });

    // ── ✏ 직접 입력 슬롯 — 현재 leaf 에만 추가 (트리 끊김 방지) ──
    // 후보들과 같은 total 기준으로 fan-out — 마지막 위치 (candCount 인덱스)
    if (isCurrentLeaf && enableDirectInput) {
      const slotIdx = candCount;
      const offset = (slotIdx - (total - 1) / 2) * OPT_W;
      const x = anchorX + offset;
      const y = adoptedY + OPT_Y_OFFSET;
      const slotId = `direct-input-${adopted.node_id}`;

      const labelNode = (
        <div className="flex flex-col items-center gap-0.5 leading-tight">
          <div className="text-[14px] leading-none">+</div>
          <div className="text-[9px] font-semibold text-amber-300">
            직접 입력
          </div>
          <div className="text-[8px] text-ink-500 font-mono">
            카탈로그 외
          </div>
        </div>
      );

      rfNodes.push({
        id: slotId,
        position: { x, y },
        data: { label: labelNode, isDirectInputSlot: true },
        targetPosition: Position.Top,
        sourcePosition: Position.Bottom,
        draggable: false,
        connectable: false,
        selectable: true,
        style: {
          background: 'rgba(255, 149, 0, 0.08)',
          border: '1.5px dashed rgba(255, 149, 0, 0.55)',
          fontSize: '9px',
          padding: '4px 6px',
          borderRadius: '50% / 30%',  // 둥근 모서리 — 슬롯 강조
          width: CAND_WIDTH * 0.85,
          textAlign: 'center' as const,
          cursor: 'pointer',
        },
      });

      rfEdges.push({
        id: `e-${adoptedNodeId}-${slotId}`,
        source: adoptedNodeId,
        target: slotId,
        style: {
          stroke: 'rgba(255, 149, 0, 0.45)',
          strokeWidth: 1,
          strokeDasharray: '5 3',
        },
      });
    }

    // 다음 anchor 드리프트 — 선택된 후보의 X 로 이동 (클램프)
    if (chosenClueKey) {
      const rawShift = chosenAbsX - anchorX;
      const clamped = Math.max(-MAX_STEP_DRIFT, Math.min(MAX_STEP_DRIFT, rawShift));
      anchorX += clamped;
    }
  });

  return { nodes: rfNodes, edges: rfEdges };
};

const ClueTreeView = ({
  tree,
  currentLeafId,
  entropyBits,
  onAdoptCandidate,
  onClickNode,
  onDirectInputClick,
  disabled = false,
  onExpand,
  onReset,
  title = '단서 트리',
  height = 460,
}: ClueTreeViewProps) => {
  const enableDirectInput = Boolean(onDirectInputClick);
  const { nodes, edges } = useMemo(
    () => buildLayout(tree, currentLeafId, enableDirectInput),
    [tree, currentLeafId, enableDirectInput],
  );
  const hasContent = nodes.length > 0;

  const stableKey = useMemo(() => {
    const nodeIds = Object.keys(tree.nodes).sort();
    // 현재 leaf 의 candidates 목록도 키에 포함 — 갱신 시 react-flow 재마운트
    const leafCands = (tree.nodes[currentLeafId]?.children_candidates ?? [])
      .map((c) => c.candidate_id)
      .join(',');
    return `${currentLeafId}|${nodeIds.join(',')}|${leafCands}|${enableDirectInput ? 'di' : ''}`;
  }, [tree.nodes, currentLeafId, enableDirectInput]);

  const depth = (() => {
    let d = 0;
    let cur: string | null = currentLeafId;
    while (cur && tree.nodes[cur]) {
      const n: SerializedClueTreeNode = tree.nodes[cur];
      if (n.clue_key === '__ROOT__') break;
      d += 1;
      cur = n.parent_id;
    }
    return d;
  })();
  const leafCands = tree.nodes[currentLeafId]?.children_candidates?.length ?? 0;

  const handleNodeClick = (_evt: React.MouseEvent, node: Node) => {
    if (disabled) return;
    // ✏ 직접 입력 슬롯
    if (node.id.startsWith('direct-input-')) {
      onDirectInputClick?.();
      return;
    }
    if (node.id.startsWith('cand-')) {
      const cand = (node.data as { candidate?: ClueCandidate }).candidate;
      // 현재 leaf 의 후보만 채택 가능 — 과거 분기점 후보는 클릭 무시
      const leafCandIds = new Set(
        (tree.nodes[currentLeafId]?.children_candidates ?? []).map(
          (c) => c.candidate_id,
        ),
      );
      if (cand && leafCandIds.has(cand.candidate_id)) {
        onAdoptCandidate(cand);
      }
    } else if (node.id.startsWith('adopted-') && onClickNode) {
      const nodeIdRaw = node.id.replace('adopted-', '');
      const adopted = tree.nodes[nodeIdRaw];
      if (adopted) onClickNode(adopted);
    }
  };

  return (
    <div className="border border-ink-700 bg-ink-950/40 flex flex-col">
      <div className="px-2.5 py-1.5 border-b border-ink-700 flex items-center justify-between shrink-0">
        <span className="text-[10px] text-ink-400 font-mono font-semibold uppercase tracking-[0.14em]">
          {title}
          <span className="ml-2 text-[9.5px] text-ink-500 normal-case tracking-normal">
            depth {depth} · 후보 {leafCands}개 · entropy {entropyBits.toFixed(2)} bits
          </span>
        </span>
        <div className="flex items-center gap-1.5">
          {onReset && (
            <button
              type="button"
              onClick={onReset}
              disabled={disabled}
              title="기존 트리 폐기 + cold-start 재시작"
              className="text-[10px] font-mono text-ink-400 hover:text-red-300 border border-ink-700 hover:border-red-500/60 px-1.5 py-0.5 transition-colors disabled:opacity-40"
            >
              ⟲ 초기화
            </button>
          )}
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
      </div>
      <div style={{ height }}>
        {!hasContent ? (
          <div className="h-full flex items-center justify-center text-ink-500 text-[10.5px] italic font-mono">
            아직 채택된 단서 없음 — 1차 정찰 옵션 또는 분석 로그 적재로 시작하세요
          </div>
        ) : depth === 0 && leafCands === 0 ? (
          /* Cold-start — root 만 있고 후보 0개 */
          <div className="h-full flex flex-col items-center justify-center gap-3 px-6">
            <div className="text-[16px]"></div>
            <div className="text-[12px] text-brand-amber font-semibold text-center">
              어두운 맵 — 첫 단서를 입력하세요
            </div>
            <div className="text-[10.5px] text-ink-400 text-center leading-5 max-w-md">
              결정 트리는 단서로부터 자라납니다.
              <br />
              상단 <span className="text-brand-teal">1차 정찰 옵션</span> 또는{' '}
              <span className="text-brand-teal">분석 로그 적재함</span> 으로 첫 단서를 채택하면
              <br />
              그때부터 가능성의 트리와 다음 단서 후보가 등장합니다.
            </div>
            <div className="text-[9.5px] text-ink-500 italic mt-2">
              ※ Uniform prior (1/8) 상태에서는 모든 단서의 변별력이 균등 — 의미 있는 추천 불가
            </div>
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
            maxZoom={1.6}
          >
            <Background gap={14} color="rgba(120, 130, 150, 0.08)" />
          </ReactFlow>
        )}
      </div>
    </div>
  );
};

export default ClueTreeView;
