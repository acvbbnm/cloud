import Badge from '@/components/Badge';

import { useEvidenceLogStore } from '@/stores/useEvidenceLogStore';
import { useToastStore } from '@/stores/useToastStore';

import type { Observable } from '@/types';

export interface PreviewEvent {
  id: string;
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
  selected: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: (checked: boolean) => void;
}

const EventPreviewTable = ({ events, selected, onToggle, onToggleAll }: EventPreviewTableProps) => {
  // P.36 — V-1 적재함 push
  const loadEvidence = useEvidenceLogStore((s) => s.load);
  const evidenceHas = useEvidenceLogStore((s) => s.has);
  const showToast = useToastStore((s) => s.show);

  const buildRawLog = (evt: PreviewEvent) => {
    const obs: Observable[] = [];
    if (evt.user && evt.user !== '-') {
      obs.push({ type: 'ACCOUNT', value: evt.user, note: evt.ev });
    }
    if (evt.ip && evt.ip !== '-') {
      obs.push({ type: 'IP_ADDRESS', value: evt.ip, note: evt.ev });
    }
    return {
      loaded_id: `raw-${evt.id}`,
      source: 'raw' as const,
      source_id: evt.id,
      time: evt.ts,
      label: evt.ev || evt.id.slice(0, 12),
      observables: obs,
      fields: {
        event_name: evt.ev,
        source_ip: evt.ip,
        user: evt.user,
        csp: evt.csp,
        matched_rule: evt.matched ?? null,
        time: evt.ts,
      },
    };
  };
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
            {/* P.36 — V-1 적재함 push */}
            <th className="text-left px-3 py-3 border-b border-ink-700/60">적재</th>
          </tr>
        </thead>
        <tbody>
          {events.map((evt) => {
            const isSel = selected.has(evt.id);
            const log = buildRawLog(evt);
            const already = evidenceHas(log.loaded_id);
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
                <td className="px-3 py-2.5">
                  <button
                    type="button"
                    onClick={() => {
                      if (loadEvidence(log)) {
                        showToast(`➜ V-1 적재함: ${evt.ev}`);
                      } else {
                        showToast('이미 적재됨');
                      }
                    }}
                    disabled={already}
                    className="text-[10.5px] font-mono px-2 py-0.5 rounded border border-brand-teal/40 text-brand-teal hover:bg-brand-teal/15 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                    title={already ? '이미 적재됨' : 'V-1 Step3 적재함에 추가'}
                  >
                    {already ? '✓' : '➜ 적재함'}
                  </button>
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
