/**
 * Evidence Tree Zustand 스토어 — Phase C (2026-05-25, byungwoo).
 *
 * 설계서: `docs/evidence_tree_paradigm.md` §5~§6
 *
 * 정책:
 *   - 모든 베이즈 산술은 서버 — 클라이언트는 응답 그대로 보관.
 *   - 새로고침/탭 이동 대비 sessionStorage persist (DB 의 triage_state 와 이중 보호).
 *   - 같은 case_id 진입 시 hydrate 또는 startClueTree() 재호출 (백엔드 idempotent).
 */
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import {
  advanceClueTreeStage,
  expandClueTree,
  getClueTree,
  resetClueTree,
  startClueTree,
  suggestClueCandidates,
} from '@/api/clueTree';

import type {
  ClueExpandRequest,
  ClueTreeResponse,
} from '@/types/clueTree';

interface ClueTreeStoreState {
  // ── 현재 트리 상태 (서버 응답을 그대로 보관) ──
  caseId: string | null;
  response: ClueTreeResponse | null;
  loading: boolean;
  error: string | null;

  // ── 액션 ──
  /** 빈 트리 시작 (백엔드 idempotent — 기존 트리 있으면 그대로 반환). */
  start: (caseId: string) => Promise<ClueTreeResponse>;
  /** 단서 채택 — 후보 클릭 또는 직접 입력 또는 로그 분석 결과. */
  expand: (req: ClueExpandRequest) => Promise<ClueTreeResponse>;
  /** 현 leaf 의 후보 재계산 (트리 변하지 않음). */
  refreshCandidates: (caseId: string) => Promise<ClueTreeResponse>;
  /** DB 저장된 트리 로드 (새로고침·복귀). */
  hydrate: (caseId: string) => Promise<ClueTreeResponse | null>;
  /** 백엔드 트리 폐기 + cold-start 로 재시작 (Phase A→D 호환성 reset 용). */
  resetServer: (caseId: string) => Promise<ClueTreeResponse>;
  /**
   * Phase N.4 — 확정된 사고유형 anchor 다음 stage 진입.
   * STAGE_TRANSITION_MATRIX 의 연관 가중치로 새 baseline 시작.
   */
  advanceStage: (caseId: string, confirmedHypothesis: string) => Promise<ClueTreeResponse>;

  /** 응답으로 스토어 갱신 — 외부에서 직접 주입 시. */
  setResponse: (caseId: string, res: ClueTreeResponse) => void;
  /** 클라이언트 트리 상태 초기화 (서버 폐기 X). */
  reset: () => void;
}

const initialState = {
  caseId: null as string | null,
  response: null as ClueTreeResponse | null,
  loading: false,
  error: null as string | null,
};

export const useClueTreeStore = create<ClueTreeStoreState>()(
  persist(
    (set) => ({
      ...initialState,

      start: async (caseId: string) => {
        set({ loading: true, error: null });
        try {
          const res = await startClueTree(caseId);
          set({ caseId, response: res, loading: false });
          return res;
        } catch (e) {
          const message = e instanceof Error ? e.message : String(e);
          set({ loading: false, error: message });
          throw e;
        }
      },

      expand: async (req: ClueExpandRequest) => {
        set({ loading: true, error: null });
        try {
          const res = await expandClueTree(req);
          set({ caseId: req.caseId, response: res, loading: false });
          return res;
        } catch (e) {
          const message = e instanceof Error ? e.message : String(e);
          set({ loading: false, error: message });
          throw e;
        }
      },

      refreshCandidates: async (caseId: string) => {
        set({ loading: true, error: null });
        try {
          const res = await suggestClueCandidates(caseId);
          set({ caseId, response: res, loading: false });
          return res;
        } catch (e) {
          const message = e instanceof Error ? e.message : String(e);
          set({ loading: false, error: message });
          throw e;
        }
      },

      hydrate: async (caseId: string) => {
        set({ loading: true, error: null });
        try {
          const res = await getClueTree(caseId);
          set({ caseId, response: res, loading: false });
          return res;
        } catch (e) {
          // 404/409 = 트리 미시작 — 정상 흐름
          set({ loading: false, error: null });
          return null;
        }
      },

      resetServer: async (caseId: string) => {
        set({ loading: true, error: null });
        try {
          const res = await resetClueTree(caseId);
          set({ caseId, response: res, loading: false });
          return res;
        } catch (e) {
          const message = e instanceof Error ? e.message : String(e);
          set({ loading: false, error: message });
          throw e;
        }
      },

      advanceStage: async (caseId: string, confirmedHypothesis: string) => {
        set({ loading: true, error: null });
        try {
          const res = await advanceClueTreeStage(caseId, confirmedHypothesis);
          set({ caseId, response: res, loading: false });
          return res;
        } catch (e) {
          const message = e instanceof Error ? e.message : String(e);
          set({ loading: false, error: message });
          throw e;
        }
      },

      setResponse: (caseId: string, res: ClueTreeResponse) => {
        set({ caseId, response: res, loading: false, error: null });
      },

      reset: () => set({ ...initialState }),
    }),
    {
      name: 'aisherpa.clueTree',
      storage: createJSONStorage(() => sessionStorage),
      // caseId + response 만 영속화 (loading/error 제외)
      partialize: (state) => ({ caseId: state.caseId, response: state.response }),
    },
  ),
);
