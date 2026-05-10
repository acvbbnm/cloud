import { create } from 'zustand';

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

export const useCaseStore = create<CaseState>((set) => ({
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
  reset: () => set({ caseId: null, csp: null, incidentType: null, severity: null, currentStep: 0 }),
}));
