/**
 * SourceTag — 학술/표준 출처 라벨 (클릭 popup, 2026-05-31 byungwoo · V1.fix.6).
 *
 * 사용자 피드백 (2026-05-31):
 *   "KISA 2.4 · NIST SP 800-86 §4.1 같은 것들은 처음부터 UI 에 보이는 건 안좋다.
 *    클릭하면 근거를 띄워야지"
 *
 * 동작
 * ----
 *   - 기본 표시: 작은 아이콘 (ⓘ) 또는 텍스트 "출처"
 *   - 클릭 → popover 표시 (제목 + 본문) + outside click 으로 닫힘
 *   - ESC 로 닫기
 *
 * V1.fix.15 (2026-06-01) — Portal 기반으로 변경.
 *   사용자 피드백: "1차 정찰 ⓘ 클릭 시 내용 짤림 발생".
 *   원인: ReconClueCard 의 `overflow-hidden` 컨테이너에 popup 이 갇힘.
 *   조치: popup 만 `createPortal` 로 document.body 에 렌더 + fixed 위치 계산.
 *         부모 컨테이너의 overflow/stacking context 무관하게 항상 위에 표시.
 *
 * 사용 예
 * -------
 *   <SourceTag
 *     label="출처"
 *     title="1차 정찰 가이드 학술 근거"
 *     body="NIST SP 800-86 §4.1 Initial Triage — 사고 인지 직후 휘발성 증거 우선."
 *   />
 */
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

interface SourceTagProps {
  /** 버튼 라벨 (기본: 'ⓘ 출처'). */
  label?: string;
  /** popup 제목. */
  title: string;
  /** popup 본문 (마크다운 X, 텍스트). 줄바꿈은 \n. */
  body: string;
  /** 추가 클래스. */
  className?: string;
  /** popup 정렬 방향 (기본 'left'). 버튼 좌측 정렬 = 'left', 우측 정렬 = 'right'. */
  align?: 'left' | 'right';
}

const POPUP_W = 320; // w-80
const POPUP_MARGIN = 4;

const SourceTag = ({
  label = 'ⓘ 출처',
  title,
  body,
  className = '',
  align = 'left',
}: SourceTagProps) => {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const popRef = useRef<HTMLDivElement | null>(null);

  // 버튼 위치 기준 popup 좌표 계산 (viewport 경계 fit)
  const computePos = () => {
    const btn = btnRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    let left = align === 'right' ? rect.right - POPUP_W : rect.left;
    let top = rect.bottom + POPUP_MARGIN;
    // viewport 우측 경계 fit
    const vw = window.innerWidth;
    if (left + POPUP_W > vw - 8) left = vw - POPUP_W - 8;
    if (left < 8) left = 8;
    // viewport 하단 경계 — 넘치면 버튼 위로 띄움
    const vh = window.innerHeight;
    // popup 높이는 모르니 휴리스틱 (대략 240px)
    if (top + 240 > vh - 8 && rect.top - 240 > 8) {
      top = rect.top - 240 - POPUP_MARGIN;
    }
    setPos({ top, left });
  };

  useEffect(() => {
    if (!open) return;
    computePos();
    const onScroll = () => computePos();
    const onResize = () => computePos();
    const onDoc = (e: MouseEvent) => {
      const tgt = e.target as Node;
      if (btnRef.current?.contains(tgt)) return;
      if (popRef.current?.contains(tgt)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    window.addEventListener('scroll', onScroll, true); // capture — 모든 scroll
    window.addEventListener('resize', onResize);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onResize);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <span className={`inline-block ${className}`}>
      <button
        ref={btnRef}
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className={
          'text-[9.5px] font-mono px-1.5 py-0.5 rounded border transition-colors ' +
          (open
            ? 'border-brand-blue/60 text-brand-blue bg-brand-blue/10'
            : 'border-ink-700/60 text-ink-400 hover:text-brand-blue hover:border-brand-blue/40')
        }
        title="클릭하여 학술 근거 확인"
      >
        {label}
      </button>
      {open &&
        createPortal(
          <div
            ref={popRef}
            style={{
              position: 'fixed',
              top: pos.top,
              left: pos.left,
              width: POPUP_W,
              zIndex: 9999,
            }}
            className="bg-ink-900 border border-ink-700 rounded-md shadow-xl p-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-1.5 gap-2">
              <div className="text-[11px] text-ink-100 font-semibold leading-4">{title}</div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="text-[10px] text-ink-400 hover:text-ink-100 shrink-0"
                title="닫기 (Esc)"
              >
                ✕
              </button>
            </div>
            <div className="text-[10.5px] text-ink-300 leading-5 whitespace-pre-line">
              {body}
            </div>
          </div>,
          document.body,
        )}
    </span>
  );
};

export default SourceTag;
