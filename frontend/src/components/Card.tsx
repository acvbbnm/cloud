/**
 * 카드 — 2026-05-22 블룸버그 스타일.
 * 평탄한 패널·각진 모서리·상단 보더 헤더(터미널 위젯 헤더 느낌).
 */
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
  sm: 'p-3',
  md: 'p-3.5',
  lg: 'p-4',
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
  const borderStyle = borderColor ? { borderLeft: `2px solid ${borderColor}` } : undefined;
  return (
    <div className={`panel ${className}`} style={borderStyle}>
      {(title || action) && (
        <div className="flex items-start justify-between gap-3 px-3 py-1.5 bg-ink-850 border-b border-ink-700">
          <div className="min-w-0">
            {title && <h3 className="panel-title">{title}</h3>}
            {subtitle && <p className="text-[11px] text-ink-400 mt-0.5">{subtitle}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      <div className={`${padMap[padding]} ${bodyClassName}`}>{children}</div>
    </div>
  );
};

export default Card;
