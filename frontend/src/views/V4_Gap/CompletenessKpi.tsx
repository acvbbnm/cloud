interface CompletenessKpiProps {
  rate: number;
  label: string;
}

const CompletenessKpi = ({ rate, label }: CompletenessKpiProps) => {
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const filled = (rate / 100) * circumference;
  const offset = circumference - filled;
  const color = rate === 100 ? '#14D9B0' : rate >= 60 ? '#FBB13B' : '#FF4D6D';

  return (
    <div className="panel p-6 flex flex-col items-center gap-3 min-w-[220px]">
      <span className="eyebrow">증거 완결성</span>
      <svg width="160" height="160" viewBox="0 0 160 160">
        <circle cx="80" cy="80" r={radius} fill="none" stroke="#2A3045" strokeWidth="10" />
        <circle
          cx="80"
          cy="80"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 80 80)"
        />
        <text
          x="80"
          y="82"
          textAnchor="middle"
          dominantBaseline="central"
          fill={color}
          fontSize="34"
          fontWeight="800"
        >
          {rate}%
        </text>
      </svg>
      <div className="text-[13px] font-bold" style={{ color }}>
        {label}
      </div>
    </div>
  );
};

export default CompletenessKpi;
