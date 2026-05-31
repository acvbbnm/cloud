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
 * 사용 예
 * -------
 *   <SourceTag
 *     label="출처"
 *     title="1차 정찰 가이드 학술 근거"
 *     body="NIST SP 800-86 §4.1 Initial Triage — 사고 인지 직후 휘발성 증거 우선."
 *   />
 */
import { useEffect, useRef, useState } from 'react';

interface SourceTagProps {
  /** 버튼 라벨 (기본: 'ⓘ 출처'). */
  label?: string;
  /** popup 제목. */
  title: string;
  /** popup 본문 (마크다운 X, 텍스트). 줄바꿈은 \n. */
  body: string;
  /** 추가 클래스. */
  className?: string;
  /** popup 정렬 방향 (기본 'left'). */
  align?: 'left' | 'right';
}

const SourceTag = ({
  label = 'ⓘ 출처',
  title,
  body,
  className = '',
  align = 'left',
}: SourceTagProps) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className={`relative inline-block ${className}`}>
      <button
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
      {open && (
        <div
          className={
            'absolute z-50 mt-1 w-80 bg-ink-900 border border-ink-700 rounded-md shadow-xl p-3 ' +
            (align === 'right' ? 'right-0' : 'left-0')
          }
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
        </div>
      )}
    </div>
  );
};

export default SourceTag;
