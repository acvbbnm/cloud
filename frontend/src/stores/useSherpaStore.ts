import { create } from 'zustand';

export interface SherpaMessage {
  id: number;
  role: 'sherpa' | 'user';
  text: string;
  source?: string;
}

interface SherpaState {
  open: boolean;
  messages: SherpaMessage[];
  toggle: () => void;
  setOpen: (v: boolean) => void;
  push: (msg: Omit<SherpaMessage, 'id'>) => void;
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
  messages: initialMessages,
  toggle: () => set((s) => ({ open: !s.open })),
  setOpen: (v) => set({ open: v }),
  push: (msg) => set((s) => ({ messages: [...s.messages, { id: ++seq, ...msg }] })),
}));
