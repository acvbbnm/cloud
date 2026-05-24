import client from './client';
import type {
  BriefingResponse,
  ChatRequest,
  ChatResponse,
  IncidentTypeValidation,
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

/** POST /api/sherpa/chat/stream — 스트리밍 자연어 질의 (Phase 2.3).
 *
 *  ndjson 응답을 토큰 단위로 콜백에 전달:
 *    {type:"start", sessionId, sources[]}                  → onStart
 *    {type:"delta", content}                                → onDelta (반복)
 *    {type:"done", sanitized?}                              → onDone
 *
 *  Phase 2.5 (2026-05-24): done 에 sanitized 첨부 — KB 외 ATT&CK T-id 가 답변에
 *  섞였을 경우 "[KB외:T1234]" 형식으로 라벨링된 버전. 클라이언트는 raw 표시 직후
 *  sanitized 로 교체하여 환각 라벨을 사용자에게 노출한다.
 *
 *  UX: 100초 대기 → 첫 토큰 ~5초 + 점진 표시. fetch + ReadableStream 사용. */
export interface StreamChatHandlers {
  onStart?: (sessionId: string, sources: ChatResponse['sources']) => void;
  onDelta?: (delta: string) => void;
  onDone?: (sanitized?: string) => void;
  onError?: (err: Error) => void;
}

export async function streamChat(
  req: ChatRequest,
  handlers: StreamChatHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const baseURL = client.defaults.baseURL || '';
  try {
    const res = await fetch(`${baseURL}/api/sherpa/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify(req),
      signal,
    });
    if (!res.ok) {
      throw new Error(`stream HTTP ${res.status}`);
    }
    if (!res.body) {
      throw new Error('ReadableStream 미지원');
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let nl: number;
      while ((nl = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (!line) continue;
        try {
          const event = JSON.parse(line) as
            | { type: 'start'; sessionId: string; sources: ChatResponse['sources'] }
            | { type: 'delta'; content: string }
            | { type: 'done'; sanitized?: string };
          if (event.type === 'start') {
            handlers.onStart?.(event.sessionId, event.sources);
          } else if (event.type === 'delta') {
            handlers.onDelta?.(event.content);
          } else if (event.type === 'done') {
            handlers.onDone?.(event.sanitized);
          }
        } catch {
          // ndjson 파싱 실패 라인은 무시
        }
      }
    }
    // 마지막 잔여 버퍼 처리
    const tail = buffer.trim();
    if (tail) {
      try {
        const event = JSON.parse(tail);
        if (event.type === 'delta') handlers.onDelta?.(event.content);
        if (event.type === 'done') handlers.onDone?.(event.sanitized);
      } catch {
        // ignore
      }
    }
  } catch (e) {
    handlers.onError?.(e instanceof Error ? e : new Error(String(e)));
  }
}

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

/**
 * GET /api/sherpa/validate-incident-type — V-8 사후 검증.
 *
 * dev3 (2026-05-19): V-1 Step 2 에서 확정한 사고유형이 Layer 2 전체 매핑 결과와
 * 정합하는지 평가. REVIEW_NEEDED 응답 시 V-8 화면 상단에 카드 자동 노출.
 *
 * 응답 status:
 *   CONSISTENT      — 추가 검토 불필요 (카드 숨김)
 *   REVIEW_NEEDED   — 다른 사고유형 시그널 발견, candidate_types 제시
 */
export const getIncidentTypeValidation = async (
  caseId: string,
): Promise<IncidentTypeValidation> => {
  const res = await client.get('/api/sherpa/validate-incident-type', {
    params: { caseId },
  });
  return res.data.data;
};
