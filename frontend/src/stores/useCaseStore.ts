import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

interface CaseState {
  caseId: string | null;
  csp: string | null;
  incidentType: string | null;
  severity: string | null;
  currentStep: number;
  setCaseId: (id: string) => void;
  setCsp: (csp: string) => void;
  setIncidentType: (type: string) => void;
  setSeverity: (severity: string) => void;
  setStep: (step: number) => void;
  reset: () => void;
}

/**
 * 사고 케이스 진행 상태 — 새로고침/탭 이동 시에도 caseId 등이 유지되도록
 * localStorage 에 영속화. (시연 체크리스트 § 5 "V-1→V-2 caseId 전달" 이슈 대응)
 */
export const useCaseStore = create<CaseState>()(
  persist(
    (set) => ({
      caseId: null,
      csp: null,
      incidentType: null,
      severity: null,
      currentStep: 0,
      setCaseId: (id) => set({ caseId: id }),
      setCsp: (csp) => set({ csp }),
      setIncidentType: (type) => set({ incidentType: type }),
      setSeverity: (severity) => set({ severity }),
      setStep: (step) => set({ currentStep: step }),
      reset: () =>
        set({
          caseId: null,
          csp: null,
          incidentType: null,
          severity: null,
          currentStep: 0,
        }),
    }),
    {
      name: 'ai-sherpa-case',
      version: 1,
      storage: createJSONStorage(() => localStorage),
      // 액션 제외, 데이터만 영속화
      partialize: (s) => ({
        caseId: s.caseId,
        csp: s.csp,
        incidentType: s.incidentType,
        severity: s.severity,
        currentStep: s.currentStep,
      }),
    },
  ),
);
