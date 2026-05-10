import { useEffect, useRef, useState } from 'react';

import { useBoardStore } from '@/stores/useBoardStore';
import type { BoardLog } from '@/stores/useBoardStore';

interface BoardCanvasProps {
  pendingLog: BoardLog | null;
  clearPendingLog: () => void;
}

interface DragState {
  cardId: number;
  offX: number;
  offY: number;
}

const BoardCanvas = ({ pendingLog, clearPendingLog }: BoardCanvasProps) => {
  const cards = useBoardStore((s) => s.cards);
  const addCard = useBoardStore((s) => s.addCard);
  const moveCard = useBoardStore((s) => s.moveCard);
  const removeCard = useBoardStore((s) => s.removeCard);

  const boardRef = useRef<HTMLDivElement | null>(null);
  const [hover, setHover] = useState(false);
  const [drag, setDrag] = useState<DragState | null>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    setHover(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    if (!boardRef.current?.contains(e.relatedTarget as Node)) {
      setHover(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setHover(false);
    if (!pendingLog || !boardRef.current) return;
    const rect = boardRef.current.getBoundingClientRect();
    const x = Math.max(0, e.clientX - rect.left - 80);
    const y = Math.max(0, e.clientY - rect.top - 20);
    addCard(pendingLog, x, y);
    clearPendingLog();
  };

  useEffect(() => {
    if (!drag) return;
    const onMove = (e: MouseEvent) => {
      if (!boardRef.current) return;
      const rect = boardRef.current.getBoundingClientRect();
      let nx = e.clientX - rect.left - drag.offX;
      let ny = e.clientY - rect.top - drag.offY;
      const maxX = rect.width - 168;
      const maxY = rect.height - 64;
      nx = Math.max(0, Math.min(nx, Math.max(0, maxX)));
      ny = Math.max(0, Math.min(ny, Math.max(0, maxY)));
      moveCard(drag.cardId, nx, ny);
    };
    const onUp = () => setDrag(null);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [drag, moveCard]);

  return (
    <div
      ref={boardRef}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`flex-1 relative bg-ink-950 border-2 border-dashed rounded-2xl overflow-hidden transition-all min-h-[300px] bg-dot-grid bg-dot-22 ${
        hover ? 'border-brand-blue shadow-glow' : 'border-ink-700'
      }`}
    >
      {cards.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-center pointer-events-none">
          <div>
            <div className="w-16 h-16 mx-auto rounded-2xl bg-ink-900 border border-ink-700 flex items-center justify-center text-[28px] mb-3">
              📋
            </div>
            <div className="text-[12px] text-ink-400">
              오른쪽 수집 로그를
              <br />
              여기로 드래그하세요
            </div>
          </div>
        </div>
      )}
      {cards.map((c) => (
        <div
          key={c.id}
          onMouseDown={(e) => {
            if ((e.target as HTMLElement).tagName === 'BUTTON') return;
            const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
            setDrag({
              cardId: c.id,
              offX: e.clientX - rect.left,
              offY: e.clientY - rect.top,
            });
          }}
          style={{ left: c.x, top: c.y }}
          className={`absolute w-44 bg-ink-850 border border-ink-700/80 rounded-xl p-2.5 text-[11px] shadow-soft select-none ${
            drag?.cardId === c.id ? 'cursor-grabbing z-20' : 'cursor-grab z-10'
          }`}
        >
          <div className="flex justify-between items-center mb-1">
            <span className="font-mono text-ink-400 text-[10px]">{c.log.ts}</span>
            <button
              onClick={() => removeCard(c.id)}
              className="text-ink-400 hover:text-brand-red text-[12px] leading-none"
            >
              ✕
            </button>
          </div>
          <div className="font-semibold truncate">{c.log.ev}</div>
          <div className="text-brand-red text-[10px] truncate mt-0.5">
            {c.log.ip} · {c.log.user}
          </div>
        </div>
      ))}
    </div>
  );
};

export default BoardCanvas;
