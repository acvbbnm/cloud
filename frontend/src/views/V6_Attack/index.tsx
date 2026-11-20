import { useNavigate } from 'react-router-dom';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import Card from '@/components/Card';
import KpiCard from '@/components/KpiCard';
import Badge from '@/components/Badge';
import { useToastStore } from '@/stores/useToastStore';

interface MatrixCell {
  id: string;
  label: string;
  intensity: 'high' | 'med' | 'low';
}

interface MatrixCol {
  tactic: string;
  cells: MatrixCell[];
}

const matrix: MatrixCol[] = [
  {
    tactic: 'Initial Access',
    cells: [{ id: 'T1078', label: 'T1078 Valid Accounts', intensity: 'high' }],
  },
  {
    tactic: 'Persistence',
    cells: [
      { id: 'T1098', label: 'T1098 Account Manip', intensity: 'high' },
      { id: 'T1136', label: 'T1136 Create Account', intensity: 'med' },
    ],
  },
  {
    tactic: 'Priv Escalation',
    cells: [{ id: 'T1078.004', label: 'T1078.004 Cloud', intensity: 'high' }],
  },
  {
    tactic: 'Defense Evasion',
    cells: [{ id: 'T1562', label: 'T1562 Impair Def', intensity: 'med' }],
  },
  {
    tactic: 'Collection',
    cells: [{ id: 'T1530', label: 'T1530 Cloud Storage', intensity: 'high' }],
  },
  {
    tactic: 'Exfiltration',
    cells: [{ id: 'T1537', label: 'T1537 Transfer', intensity: 'high' }],
  },
];

const techniques = [
  { id: 'T1078', name: 'Valid Accounts', tactic: 'Initial Access', count: 23, severity: 'Critical' as const },
  { id: 'T1098', name: 'Account Manipulation', tactic: 'Persistence', count: 18, severity: 'Critical' as const },
  { id: 'T1078.004', name: 'Cloud Accounts', tactic: 'Priv Escalation', count: 45, severity: 'Critical' as const },
  { id: 'T1530', name: 'Data from Cloud Storage', tactic: 'Collection', count: 142, severity: 'Critical' as const },
  { id: 'T1537', name: 'Transfer to Cloud Acct', tactic: 'Exfiltration', count: 87, severity: 'Critical' as const },
  { id: 'T1136', name: 'Create Account', tactic: 'Persistence', count: 12, severity: 'High' as const },
  { id: 'T1562', name: 'Impair Defenses', tactic: 'Defense Evasion', count: 15, severity: 'High' as const },
];

const intensityClass: Record<MatrixCell['intensity'], string> = {
  high: 'bg-brand-red/22 text-brand-red ring-brand-red/30',
  med: 'bg-brand-amber/18 text-brand-amber ring-brand-amber/25',
  low: 'bg-brand-blue/15 text-brand-blue ring-brand-blue/20',
};

const sevTone = (s: 'Critical' | 'High') => (s === 'Critical' ? 'red' : 'amber');

const V6Attack = () => {
  const navigate = useNavigate();
  const showToast = useToastStore((s) => s.show);

  return (
    <div>
      <PageHeader
        eyebrow="Layer 3 · M3-2"
        title={
          <>
            MITRE ATT&CK <span className="grad-text">매핑</span>
          </>
        }
        description="샘플 사건의 ATT&CK 매핑을 전술과 기법별로 보여줍니다."
        actions={
          <button
            onClick={() => {
              showToast('→ 보고서 생성');
              navigate('/report');
            }}
            className="btn-primary"
          >
            보고서 →
          </button>
        }
      />

      <PageBody className="flex flex-col gap-6 animate-fade-up">
        <div className="grid grid-cols-3 gap-3">
          <KpiCard label="기법" value={techniques.length} color="purple" hint="샘플의 하위 기법 포함" />
          <KpiCard label="전술" value={matrix.length} color="red" hint="샘플에서 사용한 전술" />
          <KpiCard label="매핑 이벤트" value={342} color="blue" hint="샘플 이벤트 수" />
        </div>

        <Card title={<>ATT&CK 전술과 기법</>} subtitle="점은 샘플에서 관련도가 높게 표시된 기법입니다.">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
            {matrix.map((col) => (
              <div key={col.tactic}>
                <div className="text-center pb-2 border-b-2 border-ink-700/70 text-ink-300 text-[10.5px] font-bold uppercase tracking-[0.08em] mb-2">
                  {col.tactic}
                </div>
                <div className="flex flex-col gap-1.5">
                  {col.cells.map((cell) => (
                    <a
                      key={cell.id}
                      href={`https://attack.mitre.org/techniques/${cell.id.replace(/\./g, '/')}/`}
                      target="_blank"
                      rel="noreferrer"
                      className={`block px-2 py-2 rounded-lg text-[10.5px] font-medium ring-1 ring-inset ${intensityClass[cell.intensity]} hover:brightness-125 transition-all`}
                    >
                      {cell.label}
                      {cell.intensity === 'high' && <span className="ml-1">●</span>}
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card title={<>매핑된 기법</>}>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[12.5px]">
              <thead>
                <tr className="bg-ink-950/70 text-ink-400 text-[10.5px] uppercase tracking-[0.1em]">
                  <th className="text-left px-3 py-3 border-b border-ink-700/60">기법 ID</th>
                  <th className="text-left px-3 py-3 border-b border-ink-700/60">기법명</th>
                  <th className="text-left px-3 py-3 border-b border-ink-700/60">전술</th>
                  <th className="text-left px-3 py-3 border-b border-ink-700/60">이벤트 수</th>
                  <th className="text-left px-3 py-3 border-b border-ink-700/60">심각도</th>
                </tr>
              </thead>
              <tbody>
                {techniques.map((t) => (
                  <tr key={t.id} className="border-b border-ink-700/30 hover:bg-brand-blue/[0.04]">
                    <td className="px-3 py-2.5">
                      <Badge tone="purple">{t.id}</Badge>
                    </td>
                    <td className="px-3 py-2.5 font-medium">{t.name}</td>
                    <td className="px-3 py-2.5 text-ink-200">{t.tactic}</td>
                    <td className="px-3 py-2.5 font-mono text-ink-100">{t.count}</td>
                    <td className="px-3 py-2.5">
                      <Badge tone={sevTone(t.severity)}>{t.severity}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </PageBody>
    </div>
  );
};

export default V6Attack;
