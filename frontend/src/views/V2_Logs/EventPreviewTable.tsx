import Badge from '@/components/Badge';

export interface PreviewEvent {
  id: number;
  ts: string;
  ev: string;
  ip: string;
  user: string;
  csp: string;
  matched?: string | null;
  highlighted?: boolean;
}

interface EventPreviewTableProps {
  events: PreviewEvent[];
  selected: Set<number>;
  onToggle: (id: number) => void;
  onToggleAll: (checked: boolean) => void;
}

const EventPreviewTable = ({ events, selected, onToggle, onToggleAll }: EventPreviewTableProps) => {
  if (events.length === 0) {
    return (
      <div className="text-center py-10 text-ink-400 text-[12px]">
        업로드된 이벤트가 없습니다.
      </div>
    );
  }

  const allChecked = events.length > 0 && selected.size === events.length;

  return (
    <div className="w-full overflow-x-auto -mx-1">
      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr className="bg-ink-950/70 text-ink-400 text-[10.5px] uppercase tracking-[0.1em]">
            <th className="text-left px-3 py-3 border-b border-ink-700/60 w-8">
              <input
                type="checkbox"
                checked={allChecked}
                onChange={(e) => onToggleAll(e.target.checked)}
                className="accent-brand-blue cursor-pointer"
              />
            </th>
            <th className="text-left px-3 py-3 border-b border-ink-700/60">Timestamp</th>
            <th className="text-left px-3 py-3 border-b border-ink-700/60">Event Name</th>
            <th className="text-left px-3 py-3 border-b border-ink-700/60">Source IP</th>
            <th className="text-left px-3 py-3 border-b border-ink-700/60">User</th>
            <th className="text-left px-3 py-3 border-b border-ink-700/60">CSP</th>
          </tr>
        </thead>
        <tbody>
          {events.map((evt) => {
            const isSel = selected.has(evt.id);
            return (
              <tr
                key={evt.id}
                className={`border-b border-ink-700/30 hover:bg-brand-blue/[0.04] transition-colors ${
                  evt.highlighted ? 'bg-brand-red/[0.04]' : ''
                }`}
              >
                <td className="px-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={isSel}
                    onChange={() => onToggle(evt.id)}
                    className="accent-brand-blue cursor-pointer"
                  />
                </td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-ink-200">{evt.ts}</td>
                <td className="px-3 py-2.5 font-medium">{evt.ev}</td>
                <td className="px-3 py-2.5 text-brand-red font-mono">{evt.ip}</td>
                <td className="px-3 py-2.5 text-ink-200">{evt.user}</td>
                <td className="px-3 py-2.5">
                  <Badge tone="blue" size="sm">
                    {evt.csp}
                  </Badge>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default EventPreviewTable;
