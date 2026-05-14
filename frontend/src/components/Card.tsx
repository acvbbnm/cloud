import type { ReactNode } from 'react';

interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  className?: string;
  bodyClassName?: string;
  borderColor?: string;
  padding?: 'sm' | 'md' | 'lg';
  children: ReactNode;
}

const padMap: Record<NonNullable<CardProps['padding']>, string> = {
  sm: 'p-4',
  md: 'p-5',
  lg: 'p-6',
};

const Card = ({
  title,
  subtitle,
  action,
  className = '',
  bodyClassName = '',
  borderColor,
  padding = 'md',
  children,
}: CardProps) => {
  const borderStyle = borderColor ? { borderLeft: `3px solid ${borderColor}` } : undefined;
  return (
    <div className={`panel ${padMap[padding]} ${className}`} style={borderStyle}>
      {(title || action) && (
        <div className="flex items-start justify-between mb-3.5 gap-3">
          <div className="min-w-0">
            {title && <h3 className="panel-title">{title}</h3>}
            {subtitle && <p className="text-[12px] text-ink-400 mt-1">{subtitle}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      <div className={bodyClassName}>{children}</div>
    </div>
  );
};

export default Card;
