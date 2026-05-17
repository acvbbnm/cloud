import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import type { SherpaSource } from '@/types';

export interface SherpaMessage {
  id: number;
  role: 'sherpa' | 'user';
  text: string;
  /** sherpa 메시지에 첨부된 KB 출처 목록 (있는 경우). */
  sources?: SherpaSource[];
  /** 표시용 출처 요약 텍스트 (UI fallback). */
  source?: string;
}

interface SherpaState {
  open: boolean;
  /** 백엔드 서버 메모리 세션 ID. 첫 응답 후 세팅되어 후속 chat 호출 시 재사용. */
  sessionId: string | null;
  messages: SherpaMessage[];
  toggle: () => void;
  setOpen: (v: boolean) => void;
  setSessionId: (id: string | null) => void;
  push: (msg: Omit<SherpaMessage, 'id'>) => void;
  reset: () => void;
}

let seq = 0;

const initialMessages: SherpaMessage[] = [
  {
    id: ++seq,
    role: 'sherpa',
    text: '수사관님, 케이스 분석 중입니다. 무엇을 도와드릴까요?',
  },
];

/**
 * AI 셰르파 채팅 상태 — sessionId + messages 를 localStorage 영속화.
 * (시연 체크리스트  5 "V-8 sessionId 새로고침 시 사라짐" 이슈 대응)
 *
 * open 토글 자체는 휘발 (UI 상태라 새로고침 시 닫혀있는 게 자연스러움).
 *
 * 주의: 백엔드는 sessionId 를 인메모리 세션으로 보관하므로 서버 재시작 시
 * 클라이언트 sessionId 가 유효하지 않을 수 있음. 이 경우 백엔드가 새 세션을
 * 생성해 응답하고, 클라이언트는 새 sessionId 로 자동 갱신됨.
 */
export const useSherpaStore = create<SherpaState>()(
  persist(
    (set) => ({
      open: false,
      sessionId: null,
      messages: initialMessages,
      toggle: () => set((s) => ({ open: !s.open })),
      setOpen: (v) => set({ open: v }),
      setSessionId: (id) => set({ sessionId: id }),
      push: (msg) =>
        set((s) => ({ messages: [...s.messages, { id: ++seq, ...msg }] })),
      reset: () => set({ sessionId: null, messages: initialMessages }),
    }),
    {
      name: 'ai-sherpa-sherpa',
      version: 1,
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({
        sessionId: s.sessionId,
        messages: s.messages,
      }),
      // hydrate 시 message id seq 를 가장 큰 값 + 1 로 재설정 (충돌 방지)
      onRehydrateStorage: () => (state) => {
        if (state?.messages?.length) {
          seq = Math.max(...state.messages.map((m) => m.id));
        }
      },
    },
  ),
);
