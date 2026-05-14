import type { ReactNode } from 'react';

type Tone = 'red' | 'amber' | 'teal' | 'blue' | 'purple' | 'gray';

interface BadgeProps {
  tone?: Tone;
  role?: 'REQUIRED' | 'CORROBORATING';
  size?: 'sm' | 'md';
  children?: ReactNode;
}

const toneClass: Record<Tone, string> = {
  red: 'bg-brand-red/15 text-brand-red ring-1 ring-inset ring-brand-red/20',
  amber: 'bg-brand-amber/15 text-brand-amber ring-1 ring-inset ring-brand-amber/20',
  teal: 'bg-brand-teal/15 text-brand-teal ring-1 ring-inset ring-brand-teal/20',
  blue: 'bg-brand-blue/15 text-brand-blue ring-1 ring-inset ring-brand-blue/20',
  purple: 'bg-brand-purple/15 text-brand-purple ring-1 ring-inset ring-brand-purple/20',
  gray: 'bg-ink-700/60 text-ink-200',
};

const sizeClass: Record<NonNullable<BadgeProps['size']>, string> = {
  sm: 'px-1.5 py-0.5 text-[10px]',
  md: 'px-2 py-0.5 text-[11px]',
};

const Badge = ({ tone, role, size = 'md', children }: BadgeProps) => {
  if (role) {
    const t: Tone = role === 'REQUIRED' ? 'red' : 'amber';
    return (
      <span className={`inline-flex items-center rounded-full font-bold ${sizeClass[size]} ${toneClass[t]}`}>
        {role}
      </span>
    );
  }
  const t: Tone = tone ?? 'blue';
  return (
    <span className={`inline-flex items-center rounded-full font-semibold ${sizeClass[size]} ${toneClass[t]}`}>
      {children}
    </span>
  );
};

export default Badge;
