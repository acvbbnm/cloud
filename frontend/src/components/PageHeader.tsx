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
    <div className="relative pt-10 pb-7 px-8 lg:px-12 bg-hero-gradient border-b border-ink-700/70">
      <div className="max-w-[1280px] mx-auto flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex flex-col gap-2.5 max-w-3xl">
          {eyebrow && <span className="eyebrow">{eyebrow}</span>}
          <h1 className="h-page">{title}</h1>
          {description && (
            <p className="text-[14px] text-ink-300 leading-relaxed">{description}</p>
          )}
          {meta && <div className="mt-1 flex flex-wrap gap-2">{meta}</div>}
        </div>
        {actions && <div className="flex flex-wrap gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  );
};

export default PageHeader;
