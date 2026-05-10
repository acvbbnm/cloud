import { useBoardStore } from '@/stores/useBoardStore';
import type { BoardLog } from '@/stores/useBoardStore';

interface LogPanelProps {
  onDragStart: (log: BoardLog) => void;
}

const LogPanel = ({ onDragStart }: LogPanelProps) => {
  const logs = useBoardStore((s) => s.logs);
  const removeLog = useBoardStore((s) => s.removeLog);

  return (
    <div className="panel flex-1 min-h-0 flex flex-col">
      <div className="flex items-center justify-between p-4 pb-2.5">
        <h3 className="panel-title">📋 수집 로그</h3>
        <span className="chip text-[10.5px]">{logs.length}건</span>
      </div>
      <div className="px-4 pb-4 overflow-y-auto flex-1 min-h-0">
        {logs.length === 0 ? (
          <div className="text-[11.5px] text-ink-400 leading-6">
            로그 수집 탭에서 행을 체크 후 “수사 보드에 추가”로 가져오세요.
          </div>
        ) : (
          logs.map((l) => (
            <div
              key={l.id}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.effectAllowed = 'copy';
                e.dataTransfer.setData('text/plain', String(l.id));
                onDragStart(l);
              }}
              className="bg-ink-950 border border-ink-700/70 rounded-xl px-3 py-2 mb-1.5 text-[11.5px] cursor-grab hover:border-brand-blue active:cursor-grabbing transition-colors"
            >
              <div className="flex justify-between items-center mb-0.5">
                <span className="font-mono text-ink-400 text-[10px]">{l.ts}</span>
                <button
                  onClick={() => removeLog(l.id)}
                  className="text-ink-400 hover:text-brand-red text-[12px] leading-none"
                >
                  ✕
                </button>
              </div>
              <div className="font-semibold text-[12px] truncate">{l.ev}</div>
              <div className="text-brand-red text-[10px] mt-0.5 truncate">
                {l.ip} · {l.user}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default LogPanel;
