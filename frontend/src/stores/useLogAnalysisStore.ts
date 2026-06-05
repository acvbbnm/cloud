/**
 * useLogAnalysisStore — 실시간 로그 분석 결과 + drawer 상태 (2026-05-26, byungwoo).
 *
 * 사용자 비전 — "셰르파처럼 별도 칸으로, 국내 CSP 로그가 실시간 단서로 추가되면서
 *   힘이 생기는 흐름".
 *
 * 영속화: sessionStorage — 탭 닫기 전까지 분석 결과 + 채택 단서 history 유지.
 * 분석 결과는 case 단위 1개 (multi-file 분석은 분석 시 덮어쓰기).
 */
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

interface MappedEvent {
  attack_id: string;
  ocsf_id: string;
  technique_id: string;
  technique_name: string | null;
  tactic: string;
  rule_id: string;
  time: string | null;
  actor_user_name: string | null;
  src_endpoint_ip: string | null;
  activity_name: string | null;
}

export interface LogAnalysisResult {
  caseId: string;
  mapped_events: MappedEvent[];
  analyzed_at: string;  // ISO-8601
  file_name: string;
  /** funnel — 수집 전체 이벤트 수(ingestion.totalEvents). 노이즈 = total - mapped. */
  total_events?: number;
}

interface LogAnalysisStoreState {
  /** drawer 열림 상태. */
  open: boolean;
  /** 현재 분석 결과 (가장 최근 1건). */
  result: LogAnalysisResult | null;
  /** 단서로 이미 채택된 clue_key set (중복 채택 방지). */
  adoptedKeys: Set<string>;

  toggle: () => void;
  setOpen: (open: boolean) => void;
  setResult: (result: LogAnalysisResult | null) => void;
  markAdopted: (clueKey: string) => void;
  clearAdopted: () => void;
  reset: () => void;
}

export const useLogAnalysisStore = create<LogAnalysisStoreState>()(
  persist(
    (set) => ({
      open: false,
      result: null,
      adoptedKeys: new Set<string>(),

      toggle: () => set((s) => ({ open: !s.open })),
      setOpen: (open) => set({ open }),
      setResult: (result) => set({ result, adoptedKeys: new Set() }),  // 새 결과 시 채택 history 초기화
      markAdopted: (clueKey) =>
        set((s) => {
          const next = new Set(s.adoptedKeys);
          next.add(clueKey);
          return { adoptedKeys: next };
        }),
      clearAdopted: () => set({ adoptedKeys: new Set() }),
      reset: () => set({ open: false, result: null, adoptedKeys: new Set() }),
    }),
    {
      name: 'aisherpa.logAnalysis',
      storage: createJSONStorage(() => sessionStorage, {
        // Set 직렬화 — JSON 은 Set 미지원이라 array 로 변환
        reviver: (key, value) => {
          if (key === 'adoptedKeys' && Array.isArray(value)) {
            return new Set(value as string[]);
          }
          return value;
        },
        replacer: (key, value) => {
          if (key === 'adoptedKeys' && value instanceof Set) {
            return Array.from(value);
          }
          return value;
        },
      }),
      // 열림 상태는 영속화 X (탭 진입 시 항상 닫힌 상태)
      partialize: (state) => ({
        result: state.result,
        adoptedKeys: state.adoptedKeys,
      }),
    },
  ),
);
