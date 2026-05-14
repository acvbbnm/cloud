import client from './client';
import type {
  AttackEventItem,
  GapResultResponse,
  MapStats,
  NormalizeStats,
  OCSFEventItem,
  PaginatedData,
} from '@/types';

/** POST /api/analysis/normalize — raw_events → ocsf_events 정규화. */
export const runNormalize = async (
  caseId: string,
  eventIds?: string[],
): Promise<NormalizeStats> => {
  const res = await client.post('/api/analysis/normalize', { caseId, eventIds });
  return res.data.data;
};

/** GET /api/analysis/ocsf — OCSF 결과 조회 (페이지네이션). */
export const getOcsf = async (
  caseId: string,
  page = 1,
  pageSize = 20,
  eventId?: string,
): Promise<PaginatedData<OCSFEventItem>> => {
  const res = await client.get('/api/analysis/ocsf', {
    params: { caseId, page, pageSize, ...(eventId ? { eventId } : {}) },
  });
  return res.data.data;
};

/** POST /api/analysis/map — OCSF → ATT&CK 매핑. */
export const runMap = async (caseId: string): Promise<MapStats> => {
  const res = await client.post('/api/analysis/map', { caseId });
  return res.data.data;
};

/** GET /api/analysis/attack — ATT&CK 결과 조회 (위험도 내림차순). */
export const getAttack = async (
  caseId: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedData<AttackEventItem>> => {
  const res = await client.get('/api/analysis/attack', {
    params: { caseId, page, pageSize },
  });
  return res.data.data;
};

/** POST /api/analysis/gap — 갭 감지 (gap_results INSERT). */
export const runGap = async (caseId: string): Promise<GapResultResponse> => {
  const res = await client.post('/api/analysis/gap', { caseId });
  return res.data.data;
};
