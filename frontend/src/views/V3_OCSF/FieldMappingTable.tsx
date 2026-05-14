import Card from '@/components/Card';

export interface MappingRow {
  source: string;
  target: string;
  rule: string;
}

interface FieldMappingTableProps {
  mappings: MappingRow[];
}

const FieldMappingTable = ({ mappings }: FieldMappingTableProps) => {
  return (
    <Card title={<>필드 매핑 상세</>} subtitle="CSP 원본 필드를 OCSF 1.3 스키마로 변환한 매핑 규칙">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[12.5px]">
          <thead>
            <tr className="bg-ink-950/70 text-ink-400 text-[10.5px] uppercase tracking-[0.1em]">
              <th className="text-left px-3 py-3 border-b border-ink-700/60">CSP 원본</th>
              <th className="text-center px-3 py-3 border-b border-ink-700/60 w-10"></th>
              <th className="text-left px-3 py-3 border-b border-ink-700/60">OCSF 필드</th>
              <th className="text-left px-3 py-3 border-b border-ink-700/60">규칙</th>
            </tr>
          </thead>
          <tbody>
            {mappings.map((row) => (
              <tr key={row.source} className="border-b border-ink-700/30 hover:bg-brand-blue/[0.04]">
                <td className="px-3 py-2.5 font-mono text-brand-red">{row.source}</td>
                <td className="px-3 py-2.5 text-center text-ink-400">→</td>
                <td className="px-3 py-2.5 font-mono text-brand-teal">{row.target}</td>
                <td className="px-3 py-2.5 text-ink-300">{row.rule}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};

export default FieldMappingTable;
