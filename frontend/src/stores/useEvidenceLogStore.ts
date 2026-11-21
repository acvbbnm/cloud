/**
 * P.36 (2026-05-31) — V-1 Step3 적재함 zustand store.
 *
 * 사용자 비전:
 *   "적재함은 우리 토글에서 로그 업로드/분석한 거 그거를 저기에 추가하자는
 *    소리야" — V-2 logs / V-3 OCSF / V-6 ATT&CK 페이지의 row 를 push 받고,
 *   V-1 Step3 에서 단서로 채택하는 흐름.
 *
 * 흐름:
 *   V-2/V-3/V-6 row [➜ V-1 적재함] 버튼
 *      → useEvidenceLogStore.load(log)
 *      → V-1 Step3 EvidenceLogPanel (store 만 표시)
 *      → row 의 observable 칩 클릭 → 단서 채택
 *
 * 영속화:
 *   sessionStorage (탭 종료 시 초기화) — 케이스 전환 시 reset 권장.
 *   useCaseStore 의 caseId 와 분리 — 적재함은 사용자 화면 컨텍스트.
 */
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import type { Observable } from '@/types';

export type EvidenceSource = 'raw' | 'ocsf' | 'attack';

/** 적재된 로그 한 줄 — V-2/V-3/V-6 row 가 push. */
export interface LoadedLog {
  /** 클라이언트 고유 ID — list key + 매칭. */
  loaded_id: string;
  /** 어느 페이지에서 왔는지. */
  source: EvidenceSource;
  /** 원본 식별자 (event_id / ocsf_id / attack_id). */
  source_id: string;
  /** ISO datetime — 컴파스 점 detail 의 핵심 정보. */
  time: string | null;
  /** 한 줄 라벨 — V-2/V-3/V-6 가 친화적으로 생성. */
  label: string;
  /** 단서 채택용 observable 후보 (push 측에서 추출). */
  observables: Observable[];
  /** ATT&CK 기법 ID (attack source 만). */
  technique_id?: string;
  /** 전 필드 — V-1 detail 영역 노출. */
  fields: Record<string, string | number | null>;
}

interface EvidenceLogState {
  /** 적재된 로그 (push 순서 보존, 신규가 위). */
  logs: LoadedLog[];
  /** push (V-2/V-3/V-6 row 가 호출). 멱등 — loaded_id 중복 차단. */
  load: (log: LoadedLog) => boolean;
  /** 적재함에서 제거 (단서 채택은 별도 흐름이라 영향 없음). */
  unload: (loaded_id: string) => void;
  /** 케이스 전환 시 사용자 명시 초기화. */
  clear: () => void;
  /** loaded_id 가 이미 적재됐는지 검사 (V-2/V-3/V-6 버튼 상태용). */
  has: (loaded_id: string) => boolean;
}

export const useEvidenceLogStore = create<EvidenceLogState>()(
  persist(
    (set, get) => ({
      logs: [],
      load: (log) => {
        const existing = get().logs;
        if (existing.some((l) => l.loaded_id === log.loaded_id)) return false;
        set({ logs: [log, ...existing] });
        return true;
      },
      unload: (loaded_id) => {
        set({ logs: get().logs.filter((l) => l.loaded_id !== loaded_id) });
      },
      clear: () => set({ logs: [] }),
      has: (loaded_id) => get().logs.some((l) => l.loaded_id === loaded_id),
    }),
    {
      name: 'evidence-log-store',
      storage: createJSONStorage(() => sessionStorage),
      version: 1,
    },
  ),
);
