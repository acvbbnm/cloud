import client from './client';

import type {
  CreateCaseReq,
  CaseResponse,
  GuideV2Response,
} from '@/types';

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

// ── Mock 데이터 (API_계약서.md 참조) ──
const MOCK_CASE: CaseResponse = {
  caseId: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
  incident_type: 'CREDENTIAL_THEFT',
  csp: 'naver',
  severity: 'high',
  occurred_at: '2026-04-05T06:12:00Z',
  system_config: null,
  created_at: '2026-04-05T06:12:01Z',
  closed_at: null,
};

export const createCase = async (data: CreateCaseReq): Promise<CaseResponse> => {
  if (USE_MOCK) return MOCK_CASE;
  const res = await client.post('/api/cases', data);
  return res.data.data;
};

export const getCase = async (caseId: string): Promise<CaseResponse> => {
  if (USE_MOCK) return MOCK_CASE;
  const res = await client.get(`/api/cases/${caseId}`);
  return res.data.data;
};

/** PATCH /api/cases/{caseId} — 케이스 부분 갱신 (dev3 B-3).
 *  V-8 사후 검증에서 채택한 secondary_incident_types 영속화 등에 사용.
 *  허용 필드: severity, system_config, incident_type, title, tlp,
 *            observables, secondary_incident_types, triage_state */
export interface PatchCaseReq {
  severity?: string;
  system_config?: Record<string, unknown>;
  incident_type?: string;
  title?: string;
  tlp?: string;
  observables?: Array<Record<string, unknown>>;
  secondary_incident_types?: string[];
  triage_state?: Record<string, unknown>;
}

export const patchCase = async (
  caseId: string,
  patch: PatchCaseReq,
): Promise<CaseResponse> => {
  if (USE_MOCK) return MOCK_CASE;
  const res = await client.patch(`/api/cases/${caseId}`, patch);
  return res.data.data;
};

/** GET /api/guide/v2 — 외부 표준 6종 기반 Kill Chain 매트릭스 가이드 (dev2 채택).
 *  v1 getGuide() 는 2026-05-18 회의 결정에 따라 폐기됨. */
export const getGuideV2 = async (caseId: string): Promise<GuideV2Response> => {
  const res = await client.get('/api/guide/v2', { params: { caseId } });
  return res.data.data;
};
