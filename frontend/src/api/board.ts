import client from './client';
import type { BoardNode, BoardResponse, NodeStatus } from '@/types';

export interface CreateNodeReq {
  caseId: string;
  attack_id?: string | null;
  label?: string;
  is_ai_suggested?: boolean;
  pos_x?: number;
  pos_y?: number;
}

export interface UpdateNodeReq {
  status?: NodeStatus;
  pos_x?: number;
  pos_y?: number;
  label?: string;
}

export interface CreateEdgeReq {
  caseId: string;
  from_node_id: string;
  to_node_id: string;
  label?: string;
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

/** POST /api/board/edges — 엣지 추가. self-loop / 다른 case 노드 연결은 400. */
export const createEdge = async (req: CreateEdgeReq) => {
  const res = await client.post('/api/board/edges', req);
  return res.data.data;
};
