import client from './client';
import type {
  BriefingResponse,
  ChatRequest,
  ChatResponse,
  KbStatsResponse,
  PlaybookRequest,
  PlaybookResponse,
  SuggestRequest,
  SuggestResponse,
} from '@/types';

export interface BriefRequest {
  caseId: string;
  eventId?: string | null; // attack_id (선택)
}

/** POST /api/sherpa/brief — ATT&CK 컨텍스트 브리핑.
 *  eventId 가 없으면 케이스 내 최상위 위험도 attack 자동 선택. */
export const postBrief = async (req: BriefRequest): Promise<BriefingResponse> => {
  const res = await client.post('/api/sherpa/brief', req);
  return res.data.data;
};

/** POST /api/sherpa/chat — 자연어 질의. sessionId 가 있으면 서버 메모리에 누적. */
export const postChat = async (req: ChatRequest): Promise<ChatResponse> => {
  const res = await client.post('/api/sherpa/chat', req);
  return res.data.data;
};

/** POST /api/sherpa/suggest — 두 노드 사이 빠진 고리 후보 추천 (후순위 깡통). */
export const postSuggest = async (req: SuggestRequest): Promise<SuggestResponse> => {
  const res = await client.post('/api/sherpa/suggest', req);
  return res.data.data;
};

/** POST /api/sherpa/playbook — 기법 chain 에 대한 플레이북 추천 (후순위 깡통). */
export const postPlaybook = async (req: PlaybookRequest): Promise<PlaybookResponse> => {
  const res = await client.post('/api/sherpa/playbook', req);
  return res.data.data;
};

/** GET /api/sherpa/kb — KB 인덱스 통계 + LLM 엔진 상태 (V8 우측 패널). */
export const getKbStats = async (): Promise<KbStatsResponse> => {
  const res = await client.get('/api/sherpa/kb');
  return res.data.data;
};
