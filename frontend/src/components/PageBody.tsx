import type { ReactNode } from 'react';

interface PageBodyProps {
  children: ReactNode;
  className?: string;
}

// 블룸버그 스타일 — 가로 폭 제한 제거, 좁은 좌우 여백, 위 패딩 축소
const PageBody = ({ children, className = '' }: PageBodyProps) => {
  return <div className={`px-4 py-4 ${className}`}>{children}</div>;
};

export default PageBody;
