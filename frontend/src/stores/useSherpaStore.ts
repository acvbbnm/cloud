import { create } from 'zustand';

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

export const useSherpaStore = create<SherpaState>((set) => ({
  open: false,
  sessionId: null,
  messages: initialMessages,
  toggle: () => set((s) => ({ open: !s.open })),
  setOpen: (v) => set({ open: v }),
  setSessionId: (id) => set({ sessionId: id }),
  push: (msg) => set((s) => ({ messages: [...s.messages, { id: ++seq, ...msg }] })),
  reset: () => set({ sessionId: null, messages: initialMessages }),
}));
