import { create } from 'zustand';

interface ToastState {
  message: string | null;
  show: (msg: string, durationMs?: number) => void;
  hide: () => void;
}

let timer: number | null = null;

export const useToastStore = create<ToastState>((set) => ({
  message: null,
  show: (msg, durationMs = 2200) => {
    if (timer !== null) {
      window.clearTimeout(timer);
    }
    set({ message: msg });
    timer = window.setTimeout(() => set({ message: null }), durationMs);
  },
  hide: () => set({ message: null }),
}));
