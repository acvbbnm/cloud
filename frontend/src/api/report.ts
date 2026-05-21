import client from './client';
import type { ReportResponse, ReportSections } from '@/types';

export type ReportStatus = 'draft' | 'edited' | 'finalized';

export interface CreateReportReq {
  caseId: string;
  /** true 면 기존 보고서 무시하고 새 초안 생성 (AI 초안 재생성). 기본 false (멱등). */
  regenerate?: boolean;
}

export interface UpdateReportReq {
  sections?: Partial<ReportSections>;
  status?: ReportStatus;
}

/** POST /api/report — 보고서 초안 생성 또는 조회 (멱등: regenerate=false 일 때). */
export const createReport = async (req: CreateReportReq): Promise<ReportResponse> => {
  const res = await client.post('/api/report', req);
  return res.data.data;
};

/** GET /api/report/{caseId} — 저장된 보고서 조회. 없으면 404. */
export const getReport = async (caseId: string): Promise<ReportResponse> => {
  const res = await client.get(`/api/report/${caseId}`);
  return res.data.data;
};

/** PATCH /api/report/{caseId} — 섹션 부분 갱신 + status 변경. EDIT_REPORT 자동 적재. */
export const patchReport = async (
  caseId: string,
  req: UpdateReportReq,
): Promise<ReportResponse> => {
  const res = await client.patch(`/api/report/${caseId}`, req);
  return res.data.data;
};

/** GET /api/report/{caseId}/export?format=docx — DOCX 직접 다운로드.
 *  Blob 으로 받아서 a[download] 트리거.
 *  PDF 는 UF-05 권장 우선순위(설계서 III장) — 백엔드 501, 프론트 버튼 자체 미노출
 *  (시연 차단 0). 추후 LibreOffice headless 또는 docx2pdf 통합 시 enablement. */
export const downloadReportDocx = async (caseId: string): Promise<void> => {
  const res = await client.get(`/api/report/${caseId}/export`, {
    params: { format: 'docx' },
    responseType: 'blob',
  });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement('a');
  a.href = url;
  a.download = `incident_report_${caseId}.docx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};
