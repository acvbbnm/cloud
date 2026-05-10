interface RawJsonPanelProps {
  title: string;
  titleColor?: string;
  badge?: string;
  data: Record<string, unknown>;
}

const colorFor = (value: unknown): string => {
  if (typeof value === 'number' || typeof value === 'boolean') return 'text-brand-amber';
  return 'text-blue-200';
};

const renderJson = (data: Record<string, unknown>, depth = 1): JSX.Element[] => {
  return Object.entries(data).flatMap(([key, value], idx, arr) => {
    const isLast = idx === arr.length - 1;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return [
        <div key={`${depth}-${key}`} style={{ paddingLeft: depth * 14 }}>
          <span className="text-blue-300">"{key}"</span>
          <span className="text-ink-200">: {'{'}</span>
        </div>,
        ...renderJson(value as Record<string, unknown>, depth + 1),
        <div key={`${depth}-${key}-close`} style={{ paddingLeft: depth * 14 }}>
          <span className="text-ink-200">{isLast ? '}' : '},'}</span>
        </div>,
      ];
    }
    const renderedValue =
      typeof value === 'string' ? `"${value}"` : value === null ? 'null' : String(value);
    return [
      <div key={`${depth}-${key}-leaf`} style={{ paddingLeft: depth * 14 }}>
        <span className="text-blue-300">"{key}"</span>
        <span className="text-ink-200">: </span>
        <span className={colorFor(value)}>{renderedValue}</span>
        {!isLast && <span className="text-ink-200">,</span>}
      </div>,
    ];
  });
};

const RawJsonPanel = ({ title, titleColor, badge, data }: RawJsonPanelProps) => {
  return (
    <div className="panel p-5 flex-1 min-w-0">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-h3" style={{ color: titleColor }}>
          {title}
        </h3>
        {badge && (
          <span
            className="text-[10px] px-2 py-0.5 rounded-full font-bold"
            style={{ background: `${titleColor}22`, color: titleColor }}
          >
            {badge}
          </span>
        )}
      </div>
      <div className="bg-ink-950 border border-ink-700 rounded-xl p-4 font-mono text-[11.5px] overflow-auto max-h-[460px] leading-7">
        <div>{'{'}</div>
        {renderJson(data)}
        <div>{'}'}</div>
      </div>
    </div>
  );
};

export default RawJsonPanel;
