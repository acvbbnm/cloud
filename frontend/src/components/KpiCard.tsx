type KpiColor = 'blue' | 'teal' | 'amber' | 'red' | 'purple' | 'gray';

interface KpiCardProps {
  label: string;
  value: number | string;
  color?: KpiColor;
  hint?: string;
  trend?: string;
}

const valueClass: Record<KpiColor, string> = {
  blue: 'text-brand-blue',
  teal: 'text-brand-teal',
  amber: 'text-brand-amber',
  red: 'text-brand-red',
  purple: 'text-brand-purple',
  gray: 'text-ink-100',
};

const accentClass: Record<KpiColor, string> = {
  blue: 'bg-brand-blue',
  teal: 'bg-brand-teal',
  amber: 'bg-brand-amber',
  red: 'bg-brand-red',
  purple: 'bg-brand-purple',
  gray: 'bg-ink-500',
};

const KpiCard = ({ label, value, color = 'blue', hint, trend }: KpiCardProps) => {
  return (
    <div className="panel p-5 flex-1 min-w-[180px] relative overflow-hidden card-hover">
      <span
        className={`absolute top-0 left-0 right-0 h-px ${accentClass[color]} opacity-60`}
      />
      <div className="flex items-start justify-between gap-2">
        <span className="text-[11px] uppercase tracking-[0.12em] text-ink-300 font-semibold">
          {label}
        </span>
        {trend && <span className="text-[10px] text-ink-400">{trend}</span>}
      </div>
      <div className={`mt-2 text-[36px] font-extrabold leading-none ${valueClass[color]}`}>
        {value}
      </div>
      {hint && <p className="mt-2 text-[11px] text-ink-400">{hint}</p>}
    </div>
  );
};

export default KpiCard;
