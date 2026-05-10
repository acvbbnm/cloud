import { create } from 'zustand';

export interface BoardLog {
  id: number;
  ts: string;
  ev: string;
  ip: string;
  user: string;
  csp: string;
}

export interface BoardCard {
  id: number;
  log: BoardLog;
  x: number;
  y: number;
}

interface BoardState {
  logs: BoardLog[];
  cards: BoardCard[];
  addLogs: (logs: Omit<BoardLog, 'id'>[]) => number;
  removeLog: (id: number) => void;
  addCard: (log: BoardLog, x: number, y: number) => void;
  moveCard: (id: number, x: number, y: number) => void;
  removeCard: (id: number) => void;
}

let logSeq = 0;
let cardSeq = 0;

export const useBoardStore = create<BoardState>((set) => ({
  logs: [],
  cards: [],
  addLogs: (logs) => {
    const items: BoardLog[] = logs.map((l) => ({ ...l, id: ++logSeq }));
    set((s) => ({ logs: [...s.logs, ...items] }));
    return items.length;
  },
  removeLog: (id) => set((s) => ({ logs: s.logs.filter((l) => l.id !== id) })),
  addCard: (log, x, y) =>
    set((s) => ({ cards: [...s.cards, { id: ++cardSeq, log, x, y }] })),
  moveCard: (id, x, y) =>
    set((s) => ({
      cards: s.cards.map((c) => (c.id === id ? { ...c, x, y } : c)),
    })),
  removeCard: (id) => set((s) => ({ cards: s.cards.filter((c) => c.id !== id) })),
}));
