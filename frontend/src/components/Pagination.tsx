/**
 * 페이지 점프 페이지네이션 — 2026-05-22.
 * prev/next + 페이지 번호 직접 선택. 끝·중간 생략 패턴(1 … 5 [6] 7 … 12).
 */
interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  /** 좌우 인접 표시 개수 (기본 1 → [현재±1]) */
  siblings?: number;
  className?: string;
}

const ellipsis = '…';

/** 표시할 페이지 토큰 배열 생성 — 숫자 또는 ellipsis. */
const buildPages = (
  page: number,
  total: number,
  siblings: number,
): (number | typeof ellipsis)[] => {
  if (total <= 7 + siblings * 2) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const left = Math.max(2, page - siblings);
  const right = Math.min(total - 1, page + siblings);
  const tokens: (number | typeof ellipsis)[] = [1];
  if (left > 2) tokens.push(ellipsis);
  for (let i = left; i <= right; i++) tokens.push(i);
  if (right < total - 1) tokens.push(ellipsis);
  tokens.push(total);
  return tokens;
};

const Pagination = ({
  page,
  totalPages,
  onPageChange,
  siblings = 1,
  className = '',
}: PaginationProps) => {
  if (totalPages <= 1) return null;
  const tokens = buildPages(page, totalPages, siblings);

  const goto = (p: number) => {
    if (p < 1 || p > totalPages || p === page) return;
    onPageChange(p);
  };

  return (
    <div className={`flex items-center justify-end gap-1 font-mono ${className}`}>
      <button
        onClick={() => goto(1)}
        disabled={page <= 1}
        className="px-2 py-1 text-[11px] uppercase border border-ink-700 bg-ink-900 text-ink-300 hover:text-ink-100 hover:border-brand-amber disabled:opacity-30 disabled:cursor-default transition-colors"
        title="처음"
      >
        «
      </button>
      <button
        onClick={() => goto(page - 1)}
        disabled={page <= 1}
        className="px-2 py-1 text-[11px] uppercase border border-ink-700 bg-ink-900 text-ink-300 hover:text-ink-100 hover:border-brand-amber disabled:opacity-30 disabled:cursor-default transition-colors"
        title="이전"
      >
        ‹
      </button>
      {tokens.map((tok, i) =>
        tok === ellipsis ? (
          <span
            key={`e-${i}`}
            className="px-1.5 py-1 text-[11px] text-ink-500 select-none"
          >
            {ellipsis}
          </span>
        ) : (
          <button
            key={tok}
            onClick={() => goto(tok)}
            className={`min-w-[28px] px-2 py-1 text-[11px] border transition-colors ${
              tok === page
                ? 'bg-brand-amber border-brand-amber text-ink-975 font-bold'
                : 'bg-ink-900 border-ink-700 text-ink-300 hover:text-ink-100 hover:border-brand-amber'
            }`}
          >
            {tok}
          </button>
        ),
      )}
      <button
        onClick={() => goto(page + 1)}
        disabled={page >= totalPages}
        className="px-2 py-1 text-[11px] uppercase border border-ink-700 bg-ink-900 text-ink-300 hover:text-ink-100 hover:border-brand-amber disabled:opacity-30 disabled:cursor-default transition-colors"
        title="다음"
      >
        ›
      </button>
      <button
        onClick={() => goto(totalPages)}
        disabled={page >= totalPages}
        className="px-2 py-1 text-[11px] uppercase border border-ink-700 bg-ink-900 text-ink-300 hover:text-ink-100 hover:border-brand-amber disabled:opacity-30 disabled:cursor-default transition-colors"
        title="마지막"
      >
        »
      </button>
    </div>
  );
};

export default Pagination;
