import client from './client';
import type { IngestionStats, LogsListData, RawEventItem } from '@/types';

/** POST /api/logs/upload — multipart (caseId + file). 응답: IngestionStats. */
export const uploadLogs = async (caseId: string, file: File): Promise<IngestionStats> => {
  const formData = new FormData();
  formData.append('caseId', caseId);
  formData.append('file', file);
  const res = await client.post('/api/logs/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data.data;
};

/** GET /api/logs?caseId=&page=&pageSize= — 이벤트 목록 (페이지네이션). */
export const getLogs = async (
  caseId: string,
  page = 1,
  pageSize = 20,
): Promise<LogsListData> => {
  const res = await client.get('/api/logs', { params: { caseId, page, pageSize } });
  return res.data.data;
};

/** GET /api/logs/{eventId} — 단건 원본 이벤트 (raw JSON 포함). */
export const getEvent = async (eventId: string): Promise<RawEventItem> => {
  const res = await client.get(`/api/logs/${eventId}`);
  return res.data.data;
};
