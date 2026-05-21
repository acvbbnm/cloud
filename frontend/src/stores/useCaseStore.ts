import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import type { IncidentType, TLP, Observable } from '@/types';

interface CaseState {
  caseId: string | null;
  csp: string | null;
  incidentType: IncidentType | null;
  severity: string | null;
  currentStep: number;
  // ── dev3 신규 (Step 1 케이스 메타) ──
  title: string | null;
  tlp: TLP | null;
  observables: Observable[];
  secondaryIncidentTypes: IncidentType[]; // V-8 사후 검증 결과로 추가된 부 사고유형

  setCaseId: (id: string) => void;
  setCsp: (csp: string) => void;
  setIncidentType: (type: IncidentType | null) => void;
  setSeverity: (severity: string) => void;
  setStep: (step: number) => void;
  // ── dev3 신규 액션 ──
  setTitle: (title: string) => void;
  setTlp: (tlp: TLP) => void;
  setObservables: (observables: Observable[]) => void;
  addObservable: (observable: Observable) => void;
  removeObservable: (index: number) => void;
  setSecondaryIncidentTypes: (types: IncidentType[]) => void;
  reset: () => void;
}

/**
 * 사고 케이스 진행 상태 — 새로고침/탭 이동 시에도 caseId 등이 유지되도록
 * localStorage 에 영속화. (시연 체크리스트 5 "V-1→V-2 caseId 전달" 이슈 대응)
 *
 * dev3 (2026-05-18): title, tlp, observables, secondaryIncidentTypes 추가.
 *   incidentType 기본값은 UNCLASSIFIED 가 아닌 null — Step 2 Discovery Loop 통과 후 설정.
 *   persist version 1 → 2 마이그레이션 추가.
 */
export const useCaseStore = create<CaseState>()(
  persist(
    (set) => ({
      caseId: null,
      csp: null,
      incidentType: null,
      severity: null,
      currentStep: 0,
      title: null,
      tlp: null,
      observables: [],
      secondaryIncidentTypes: [],

      setCaseId: (id) => set({ caseId: id }),
      setCsp: (csp) => set({ csp }),
      setIncidentType: (type) => set({ incidentType: type }),
      setSeverity: (severity) => set({ severity }),
      setStep: (step) => set({ currentStep: step }),
      setTitle: (title) => set({ title }),
      setTlp: (tlp) => set({ tlp }),
      setObservables: (observables) => set({ observables }),
      addObservable: (observable) =>
        set((s) => ({ observables: [...s.observables, observable] })),
      removeObservable: (index) =>
        set((s) => ({ observables: s.observables.filter((_, i) => i !== index) })),
      setSecondaryIncidentTypes: (types) => set({ secondaryIncidentTypes: types }),

      reset: () =>
        set({
          caseId: null,
          csp: null,
          incidentType: null,
          severity: null,
          currentStep: 0,
          title: null,
          tlp: null,
          observables: [],
          secondaryIncidentTypes: [],
        }),
    }),
    {
      name: 'ai-sherpa-case',
      version: 2,
      storage: createJSONStorage(() => localStorage),
      // dev2 (v1) → dev3 (v2) 마이그레이션: 신규 필드 기본값 채움
      migrate: (persisted, version) => {
        const state = (persisted ?? {}) as Partial<CaseState>;
        if (version < 2) {
          return {
            ...state,
            title: state.title ?? null,
            tlp: state.tlp ?? null,
            observables: state.observables ?? [],
            secondaryIncidentTypes: state.secondaryIncidentTypes ?? [],
          };
        }
        return state;
      },
      // 액션 제외, 데이터만 영속화
      partialize: (s) => ({
        caseId: s.caseId,
        csp: s.csp,
        incidentType: s.incidentType,
        severity: s.severity,
        currentStep: s.currentStep,
        title: s.title,
        tlp: s.tlp,
        observables: s.observables,
        secondaryIncidentTypes: s.secondaryIncidentTypes,
      }),
    },
  ),
);
