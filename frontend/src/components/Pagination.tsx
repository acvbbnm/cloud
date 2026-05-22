/**
 * 페이지 번호 선택형 페이지네이션 컴포넌트.
 *
 * 동작:
 *   - 총 페이지 ≤ siblings*2 + 5 면 모든 페이지 번호 노출
 *   - 그 이상이면 [1] [..] [current-siblings ~ current+siblings] [..] [last] 형태
 *   - 양 끝에 이전/다음 화살표 (disabled 처리)
 *
 * 사용처: V-2 raw_events, V-3 ocsf_events 등 페이지네이션 응답을 다루는 모든 화면.
 */

interface PaginationProps {
  /** 현재 페이지 (1-indexed) */
  page: number;
  /** 총 페이지 수 (≥ 1) */
  totalPages: number;
  /** 페이지 변경 핸들러 */
  onPageChange: (page: number) => void;
  /** 현재 페이지 좌우로 노출할 페이지 개수 (기본 1 → 양쪽 1개씩) */
  siblings?: number;
  /** 추가 className */
  className?: string;
}

const Pagination = ({
  page,
  totalPages,
  onPageChange,
  siblings = 1,
  className = '',
}: PaginationProps) => {
  if (totalPages <= 1) {
    return null;
  }

  const items = buildPageItems(page, totalPages, siblings);

  return (
    <div className={`flex items-center justify-end gap-1 mt-3 flex-wrap ${className}`}>
      <button
        onClick={() => onPageChange(Math.max(1, page - 1))}
        disabled={page <= 1}
        aria-label="이전 페이지"
        className="btn-ghost btn-sm disabled:opacity-40 px-2"
      >
        ←
      </button>

      {items.map((item, i) =>
        item === 'ellipsis' ? (
          <span
            key={`ellipsis-${i}`}
            className="px-1.5 text-ink-500 text-[11.5px] select-none"
          >
            …
          </span>
        ) : (
          <button
            key={item}
            onClick={() => onPageChange(item)}
            aria-label={`페이지 ${item}`}
            aria-current={item === page ? 'page' : undefined}
            className={
              item === page
                ? 'min-w-[28px] px-2 py-1 rounded-md text-[11.5px] font-bold bg-brand-blue/20 border border-brand-blue text-white'
                : 'min-w-[28px] px-2 py-1 rounded-md text-[11.5px] text-ink-300 border border-ink-700/60 hover:border-brand-blue/60 hover:text-white transition-colors'
            }
          >
            {item}
          </button>
        ),
      )}

      <button
        onClick={() => onPageChange(Math.min(totalPages, page + 1))}
        disabled={page >= totalPages}
        aria-label="다음 페이지"
        className="btn-ghost btn-sm disabled:opacity-40 px-2"
      >
        →
      </button>
    </div>
  );
};

/**
 * 페이지 번호 배열 생성. 'ellipsis' 마커로 …를 표시.
 *
 * 예시 (siblings=1):
 *   totalPages=5, page=3 → [1, 2, 3, 4, 5]
 *   totalPages=10, page=1 → [1, 2, ..., 10]
 *   totalPages=10, page=5 → [1, ..., 4, 5, 6, ..., 10]
 *   totalPages=10, page=10 → [1, ..., 9, 10]
 */
type PageItem = number | 'ellipsis';

function buildPageItems(page: number, totalPages: number, siblings: number): PageItem[] {
  // 임계값: 처음/끝 + 양옆 siblings + 현재 = 2*siblings + 3
  // 거기에 ellipsis 양쪽 가능성 고려 → 2*siblings + 5 이하면 전체 노출
  const fullThreshold = 2 * siblings + 5;

  if (totalPages <= fullThreshold) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const leftSibling = Math.max(page - siblings, 1);
  const rightSibling = Math.min(page + siblings, totalPages);

  const showLeftEllipsis = leftSibling > 2;
  const showRightEllipsis = rightSibling < totalPages - 1;

  const items: PageItem[] = [];

  // 첫 페이지 (항상)
  items.push(1);

  if (showLeftEllipsis) {
    items.push('ellipsis');
  } else if (leftSibling === 2) {
    // 인접 → ellipsis 대신 2 직접 추가 (위에서 1 추가했으니 중복 방지를 위해 leftSibling 시작점만 조정)
  }

  // 중앙 영역 — 1·last와 중복 안 되게 (1보다 크고 totalPages 보다 작은 페이지만)
  const startMid = showLeftEllipsis ? leftSibling : 2;
  const endMid = showRightEllipsis ? rightSibling : totalPages - 1;

  for (let i = startMid; i <= endMid; i++) {
    items.push(i);
  }

  if (showRightEllipsis) {
    items.push('ellipsis');
  }

  // 마지막 페이지 (totalPages > 1 이라 항상 별도)
  items.push(totalPages);

  return items;
}

export default Pagination;
