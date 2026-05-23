import { create } from 'zustand';

export interface ToastItem {
  id: number;
  message: string;
}

interface ToastState {
  items: ToastItem[];
  show: (msg: string, durationMs?: number) => void;
  dismiss: (id: number) => void;
  hide: () => void;
}

const MAX_VISIBLE = 3;
let seq = 0;

export const useToastStore = create<ToastState>((set, get) => ({
  items: [],
  show: (msg, durationMs = 2200) => {
    seq += 1;
    const id = seq;
    set((s) => {
      const next = [...s.items, { id, message: msg }];
      // 동시 표시 상한 — 가장 오래된 것부터 폐기
      return { items: next.slice(-MAX_VISIBLE) };
    });
    window.setTimeout(() => get().dismiss(id), durationMs);
  },
  dismiss: (id) => set((s) => ({ items: s.items.filter((t) => t.id !== id) })),
  hide: () => set({ items: [] }),
}));
