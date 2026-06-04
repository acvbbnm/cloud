import client from './client';
import type { BoardEdge, BoardNode, BoardNodeMeta, BoardResponse, NodeStatus } from '@/types';

export interface CreateNodeReq {
  caseId: string;
  attack_id?: string | null;
  /** Phase O — 단서 1st-class 노드. attack_id 와 동시 지정 불가. */
  clue_key?: string | null;
  label?: string;
  is_ai_suggested?: boolean;
  pos_x?: number;
  pos_y?: number;
  /** Phase O — clue_key 동반 메타 옵션. */
  stage?: number;
  hypothesis?: string | null;
  source?: string;
  meta?: Record<string, unknown>;
}

export interface UpdateNodeReq {
  status?: NodeStatus;
  pos_x?: number;
  pos_y?: number;
  label?: string;
  meta?: Record<string, unknown>; // Phase O — shallow merge
}

export interface CreateEdgeReq {
  caseId: string;
  from_node_id: string;
  to_node_id: string;
  label?: string;
}

/** Phase O.3 — Evidence Tree → 보드 일괄 bridge 요청. */
export interface BridgeFromClueTreeReq {
  caseId: string;
  source?: string;
  include_root?: boolean;
  include_edges?: boolean;
  node_ids?: string[] | null;
}

export interface BridgeResult {
  created_nodes: BoardNode[];
  skipped: Array<{ clue_key: string; reason: string }>;
  created_edges: BoardEdge[];
}

/** GET /api/board?caseId= — case 의 보드 전체 상태. */
export const getBoard = async (caseId: string): Promise<BoardResponse> => {
  const res = await client.get('/api/board', { params: { caseId } });
  return res.data.data;
};

/** POST /api/board/nodes — 노드 추가. attack_id 주어지면 라벨 자동 생성. */
export const createNode = async (req: CreateNodeReq): Promise<BoardNode> => {
  const res = await client.post('/api/board/nodes', req);
  return res.data.data;
};

/** PATCH /api/board/nodes/{nodeId} — 노드 상태/좌표/라벨 부분 갱신.
 *  status 변경 시 백엔드가 action_logs 에 자동 기록. */
export const updateNode = async (nodeId: string, req: UpdateNodeReq): Promise<BoardNode> => {
  const res = await client.patch(`/api/board/nodes/${nodeId}`, req);
  return res.data.data;
};

/** DELETE /api/board/nodes/{nodeId} — 노드 1개 삭제 + 연결 엣지 자동 삭제. */
export const deleteNode = async (nodeId: string): Promise<{ node_id: string; deleted: boolean }> => {
  const res = await client.delete(`/api/board/nodes/${nodeId}`);
  return res.data.data;
};

/** POST /api/board/edges — 엣지 추가. self-loop / 다른 case 노드 연결은 400. */
export const createEdge = async (req: CreateEdgeReq) => {
  const res = await client.post('/api/board/edges', req);
  return res.data.data;
};

/** DELETE /api/board/edges/{edge_id} — 엣지 1개 삭제 (action_logs REJECT 기록). */
export const deleteEdge = async (edgeId: string): Promise<{ edge_id: string; deleted: boolean }> => {
  const res = await client.delete(`/api/board/edges/${edgeId}`);
  return res.data.data;
};

/** POST /api/board/auto-layout?caseId= — networkx spring_layout 자동 정렬. */
export const autoLayout = async (caseId: string): Promise<{
  updated_nodes: number;
  positions: Record<string, { x: number; y: number }>;
}> => {
  const res = await client.post('/api/board/auto-layout', null, { params: { caseId } });
  return res.data.data;
};

/** Phase O.3 — POST /api/board/nodes/from-clue-tree.
 *  Evidence Tree 의 채택 단서들을 보드 노드로 일괄 이관 (멱등 + 옵션 엣지). */
export const bridgeFromClueTree = async (
  req: BridgeFromClueTreeReq
): Promise<BridgeResult> => {
  const res = await client.post('/api/board/nodes/from-clue-tree', req);
  return res.data.data;
};

/** Phase O — BoardNode 가 단서 노드인지 type guard. */
export const isClueNode = (
  node: BoardNode
): node is BoardNode & { meta: NonNullable<BoardNodeMeta> & { type: 'clue' } } => {
  if (node.type === 'clue') return true;
  return !!node.meta && (node.meta as { type?: string }).type === 'clue';
};
