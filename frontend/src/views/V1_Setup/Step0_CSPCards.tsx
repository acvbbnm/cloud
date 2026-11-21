import { CSP_META } from './meta';

interface Step0Props {
  selected: string | null;
  onSelect: (csp: string) => void;
  onNext: () => void;
}

// dev3 (2026-05-19): 멀티 CSP('all') 옵션 제거 — MULTI_CSP_LATERAL 사고유형 삭제와 함께
const cspOrder = ['naver', 'nhn'];

const Step0_CSPCards = ({ selected, onSelect, onNext }: Step0Props) => {
  const meta = CSP_META[selected ?? 'naver'] ?? CSP_META.naver;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="h-section">분석 환경 선택</h2>
        <p className="text-[13px] text-ink-400 mt-1.5 max-w-2xl">
          침해 사고가 발생한 클라우드 서비스 제공자(CSP)를 선택하세요. 선택한 CSP에 맞춰
          서비스 이름·로그 경로·수집 체크리스트가 자동 전환됩니다.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {cspOrder.map((id) => {
          const c = CSP_META[id];
          const sel = selected === id;
          return (
            <button
              key={id}
              onClick={() => onSelect(id)}
              className={`text-left panel p-5 transition-colors card-hover relative overflow-hidden ${
                sel ? 'border-brand-amber' : ''
              }`}
            >
              {id === 'naver' && (
                <span className="absolute top-3 right-3 chip text-[10px]">기본값</span>
              )}
              <div className="flex items-baseline gap-2 mb-3 font-mono">
                <b className="text-[14px] tracking-[0.04em] text-ink-100">{c.label}</b>
                <span className="text-[10px] text-ink-500 uppercase tracking-[0.12em]">
                  {c.short}
                </span>
              </div>
              {/* desc 라인 제거 (2026-05-25) — 아래 services 칩과 중복. */}
              <div className="flex flex-wrap gap-1">
                {c.services.slice(0, 4).map((s) => (
                  <span key={s} className="text-[10px] text-ink-400 bg-ink-900/60 border border-ink-700 px-2 py-0.5">
                    {s}
                  </span>
                ))}
              </div>
            </button>
          );
        })}
      </div>

      {selected && (
        <div className="panel p-5 animate-fade-up">
          <div className="flex items-center gap-2 mb-2">
            <span className="font-bold text-[14px] text-ink-100">{meta.label}</span>
            <span className="chip text-[10px]">선택됨</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[12px] leading-7 text-ink-300">
            <div>
              <span className="eyebrow text-[10px] block mb-1.5">핵심 서비스</span>
              <span>{meta.services.slice(0, 5).join(' · ')}</span>
            </div>
            <div>
              <span className="eyebrow text-[10px] block mb-1.5">보안 서비스</span>
              <span>{meta.security.join(' · ')}</span>
            </div>
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <button onClick={onNext} disabled={!selected} className="btn-primary disabled:opacity-50">
          다음: 케이스 메타 →
        </button>
      </div>
    </div>
  );
};

export default Step0_CSPCards;
