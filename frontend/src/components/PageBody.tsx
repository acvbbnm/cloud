import type { ReactNode } from 'react';

interface PageBodyProps {
  children: ReactNode;
  className?: string;
}

const PageBody = ({ children, className = '' }: PageBodyProps) => {
  return (
    <div className={`max-w-[1280px] mx-auto px-8 lg:px-12 py-8 ${className}`}>{children}</div>
  );
};

export default PageBody;
