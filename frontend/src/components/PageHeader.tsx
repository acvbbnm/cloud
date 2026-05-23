/**
 * 페이지 헤더 — 2026-05-22 블룸버그 스타일.
 * hero-gradient 제거, 좌측 앰버 띠 + 고밀도 한 줄 메타.
 */
import type { ReactNode } from 'react';

interface PageHeaderProps {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
}

const PageHeader = ({ eyebrow, title, description, actions, meta }: PageHeaderProps) => {
  return (
    <div className="relative pt-4 pb-3 px-5 bg-ink-950 border-b border-ink-700">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex flex-col gap-1 min-w-0">
          {eyebrow && (
            <span className="text-[10px] font-mono uppercase tracking-[0.16em] text-brand-amber">
              {eyebrow}
            </span>
          )}
          <h1 className="h-page">{title}</h1>
          {description && (
            <p className="text-[12px] text-ink-400 leading-relaxed max-w-3xl">{description}</p>
          )}
          {meta && <div className="mt-1.5 flex flex-wrap gap-2 items-center">{meta}</div>}
        </div>
        {actions && <div className="flex flex-wrap gap-1.5 shrink-0">{actions}</div>}
      </div>
    </div>
  );
};

export default PageHeader;
