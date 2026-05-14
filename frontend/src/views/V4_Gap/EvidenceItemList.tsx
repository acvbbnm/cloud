import Card from '@/components/Card';
import Badge from '@/components/Badge';

export interface EvidenceItem {
  name: string;
  role: 'REQUIRED' | 'CORROBORATING';
  collected: boolean;
  techniques: string[];
}

interface EvidenceItemListProps {
  items: EvidenceItem[];
}

const EvidenceItemList = ({ items }: EvidenceItemListProps) => {
  return (
    <Card title={<>증거 항목별 상태</>} subtitle="증거 역할(REQUIRED/CORROBORATING) 기준 수집 여부 점검">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[12.5px]">
          <thead>
            <tr className="bg-ink-950/70 text-ink-400 text-[10.5px] uppercase tracking-[0.1em]">
              <th className="text-left px-3 py-3 border-b border-ink-700/60">증거 항목</th>
              <th className="text-left px-3 py-3 border-b border-ink-700/60">역할</th>
              <th className="text-left px-3 py-3 border-b border-ink-700/60">상태</th>
              <th className="text-left px-3 py-3 border-b border-ink-700/60">관련 기법</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.name} className="border-b border-ink-700/30 hover:bg-brand-blue/[0.04]">
                <td className="px-3 py-2.5">{item.name}</td>
                <td className="px-3 py-2.5">
                  <Badge role={item.role} />
                </td>
                <td
                  className={`px-3 py-2.5 font-semibold ${
                    item.collected ? 'text-brand-teal' : 'text-brand-red'
                  }`}
                >
                  {item.collected ? '✓ 확보' : '✗ 미수집'}
                </td>
                <td className="px-3 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    {item.techniques.map((t) => (
                      <span key={t} className="tag-purple text-[10.5px]">{t}</span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};

export default EvidenceItemList;
