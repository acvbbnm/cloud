import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import type {
  HypothesisScores,
  IncidentType,
  TriageRecommendation,
} from '@/types';

interface CompletedPathEntry {
  node_id: string;
  selected_option_ids: string[];
}

interface TriageStoreState {
  // ── 트리 진행 상태 ──
  currentNodeId: string | null;
  completedPath: CompletedPathEntry[];
  hypothesisScores: HypothesisScores;
  mappedTechniques: string[]; // 부분 분석에서 추출된 ATT&CK 기법 ID
  recommendation: TriageRecommendation | null;
  isTerminal: boolean;

  // ── 액션 ──
  startTriage: (rootNodeId: string) => void;
  recordAnswer: (nodeId: string, selectedOptionIds: string[]) => void;
  setCurrentNode: (nodeId: string | null) => void;
  setHypothesisScores: (scores: HypothesisScores) => void;
  addMappedTechniques: (techniqueIds: string[]) => void;
  setRecommendation: (rec: TriageRecommendation | null) => void;
  setTerminal: (terminal: boolean) => void;
  reset: () => void;
}

/**
 * 사고유형별 가설 점수 초기값 — IncidentType 6종 모두 0.
 * 백엔드 /api/triage/analyze /next 응답으로 갱신됨.
 */
const initialScores = (): HypothesisScores => ({
  CREDENTIAL_THEFT: 0,
  PRIVILEGE_ESCALATION: 0,
  DATA_EXFILTRATION: 0,
  AUDIT_LOG_TAMPERING: 0,
  MULTI_CSP_LATERAL: 0,
  UNCLASSIFIED: 0,
});

/**
 * Triage 결정 트리 진행 상태 — V-1 Step 2 Discovery Loop 의 ③ 결정 트리.
 *
 * dev3 (2026-05-18):
 *   - useCaseStore 와 분리 — 트리 진행은 케이스 메타와 다른 라이프사이클.
 *   - 새로고침/탭 이동 대비 localStorage persist (트리 깊이 6 까지 진행 보호).
 *   - 점수 계산은 백엔드 정적 JSON (weights.json) 으로만 — 클라이언트는 표시만.
 *
 * 학술 근거: weights.json + decision_tree.json (docs/dev3/가중치_설계_근거.md)
 */
export const useTriageStore = create<TriageStoreState>()(
  persist(
    (set) => ({
      currentNodeId: null,
      completedPath: [],
      hypothesisScores: initialScores(),
      mappedTechniques: [],
      recommendation: null,
      isTerminal: false,

      startTriage: (rootNodeId) =>
        set({
          currentNodeId: rootNodeId,
          completedPath: [],
          hypothesisScores: initialScores(),
          mappedTechniques: [],
          recommendation: null,
          isTerminal: false,
        }),

      recordAnswer: (nodeId, selectedOptionIds) =>
        set((s) => ({
          completedPath: [
            ...s.completedPath.filter((p) => p.node_id !== nodeId),
            { node_id: nodeId, selected_option_ids: selectedOptionIds },
          ],
        })),

      setCurrentNode: (nodeId) => set({ currentNodeId: nodeId }),

      setHypothesisScores: (scores) => set({ hypothesisScores: scores }),

      addMappedTechniques: (techniqueIds) =>
        set((s) => {
          // 중복 제거 (Set 사용)
          const merged = new Set<string>([...s.mappedTechniques, ...techniqueIds]);
          return { mappedTechniques: Array.from(merged) };
        }),

      setRecommendation: (rec) => set({ recommendation: rec }),

      setTerminal: (terminal) => set({ isTerminal: terminal }),

      reset: () =>
        set({
          currentNodeId: null,
          completedPath: [],
          hypothesisScores: initialScores(),
          mappedTechniques: [],
          recommendation: null,
          isTerminal: false,
        }),
    }),
    {
      name: 'ai-sherpa-triage',
      version: 1,
      storage: createJSONStorage(() => localStorage),
      // 액션 제외, 데이터만 영속화
      partialize: (s) => ({
        currentNodeId: s.currentNodeId,
        completedPath: s.completedPath,
        hypothesisScores: s.hypothesisScores,
        mappedTechniques: s.mappedTechniques,
        recommendation: s.recommendation,
        isTerminal: s.isTerminal,
      }),
    },
  ),
);

/**
 * 사고유형별 점수 내림차순 정렬 헬퍼.
 * UNCLASSIFIED 는 항상 0 이므로 제외.
 *
 * @example
 *   const top = sortedHypotheses(scores);
 *   top[0] // { type: 'CREDENTIAL_THEFT', score: 105 }
 */
export const sortedHypotheses = (
  scores: HypothesisScores,
): Array<{ type: IncidentType; score: number }> => {
  return (Object.keys(scores) as IncidentType[])
    .filter((t) => t !== 'UNCLASSIFIED')
    .map((type) => ({ type, score: scores[type] }))
    .sort((a, b) => b.score - a.score);
};
