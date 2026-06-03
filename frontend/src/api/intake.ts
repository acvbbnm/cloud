import client from './client';

import type {
  CaseResponse,
  CreateCaseReq,
  GuideV2Response,
  IncidentType,
  Observable,
  TLP,
  TriageState,
} from '@/types';

export const createCase = async (data: CreateCaseReq): Promise<CaseResponse> => {
  const res = await client.post('/api/cases', data);
  return res.data.data;
};

export const getCase = async (caseId: string): Promise<CaseResponse> => {
  const res = await client.get(`/api/cases/${caseId}`);
  return res.data.data;
};

/** GET /api/guide/v2 — 외부 표준 6종 기반 Kill Chain 매트릭스 가이드 (dev2 채택).
 *  v1 getGuide() 는 2026-05-18 회의 결정에 따라 폐기됨. */
export const getGuideV2 = async (caseId: string): Promise<GuideV2Response> => {
  const res = await client.get('/api/guide/v2', { params: { caseId } });
  return res.data.data;
};

/** GET /api/guide/preview — Phase K (2026-05-26 byungwoo). V-1 Step3 트리아주
 *  진행 중 (UNCLASSIFIED) 상위 가설별 가이드 미리보기. case.system_config 환경
 *  보정 그대로 적용. 응답에 preview=true 마커. paradigm doc §19 참조. */
export const getGuidePreview = async (
  caseId: string,
  incidentType: IncidentType,
): Promise<GuideV2Response> => {
  const res = await client.get('/api/guide/preview', {
    params: { caseId, incidentType },
  });
  return res.data.data;
};

/** PATCH /api/cases/{caseId} — 케이스 부분 갱신 (dev3 B-3).
 *  V-8 IncidentTypeReviewCard 가 secondary_incident_types 등록 시 호출. */
export interface UpdateCaseReq {
  severity?: string;
  system_config?: Record<string, unknown>;
  incident_type?: IncidentType;
  title?: string;
  tlp?: TLP;
  observables?: Observable[];
  secondary_incident_types?: IncidentType[];
  triage_state?: TriageState | null;
  investigator_memo?: string;
}

export const updateCase = async (
  caseId: string,
  data: UpdateCaseReq,
): Promise<CaseResponse> => {
  const res = await client.patch(`/api/cases/${caseId}`, data);
  return res.data.data;
};
