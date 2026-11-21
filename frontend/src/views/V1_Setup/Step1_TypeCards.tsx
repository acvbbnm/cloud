import type { IncidentType } from '@/types';

import { TYPE_META, CSP_META } from './meta';

interface Step1Props {
  selected: IncidentType | null;
  csp: string | null;
  onSelect: (type: IncidentType) => void;
  onPrev: () => void;
  onNext: () => void;
}

// dev3 (2026-05-18): 이 화면은 폐기되고 Step1_CaseMetadata 로 교체됨. 파일 보존만.
// MULTI_CSP_LATERAL 도 2026-05-19 제거.
const orderedTypes: IncidentType[] = [
  'CREDENTIAL_THEFT',
  'PRIVILEGE_ESCALATION',
  'DATA_EXFILTRATION',
  'AUDIT_LOG_TAMPERING',
];

const sevTone = (sev: string) =>
  sev === 'CRITICAL'
    ? 'bg-brand-red/15 text-brand-red ring-brand-red/25'
    : sev === 'HIGH'
    ? 'bg-brand-amber/15 text-brand-amber ring-brand-amber/25'
    : 'bg-brand-purple/15 text-brand-purple ring-brand-purple/25';

const Step1_TypeCards = ({ selected, csp, onSelect, onPrev, onNext }: Step1Props) => {
  const cspKey = (csp ?? 'naver') as 'naver' | 'nhn' | 'all';
  const cspMeta = CSP_META[cspKey] ?? CSP_META.naver;
  const meta = selected ? TYPE_META[selected] : null;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="h-section">사고 유형 선택</h2>
        <p className="text-[13px] text-ink-400 mt-1.5 max-w-2xl">
          침해사고 시나리오를 선택하세요. 선택 즉시 핵심 확인 서비스와 MITRE 전술이 표시됩니다.
        </p>
      </div>

      <div className="flex items-center gap-2.5 flex-wrap">
        <span className="eyebrow">분석 환경</span>
        <span className="chip" style={{ color: cspMeta.color, borderColor: `${cspMeta.color}55` }}>
          {cspMeta.label}
        </span>
        <button onClick={onPrev} className="btn-ghost btn-sm">
          변경
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {orderedTypes.map((id) => {
          const t = TYPE_META[id];
          if (!t) return null;
          const sel = selected === id;
          return (
            <button
              key={id}
              onClick={() => onSelect(id)}
              className={`text-left panel p-5 card-hover transition-all ${
                sel ? 'ring-2 ring-brand-blue/60 shadow-glow' : ''
              }`}
            >
              <div className="flex items-center gap-2 mb-3">
                <span
                  className="w-10 h-10 rounded-xl flex items-center justify-center text-[20px]"
                  style={{ background: `${t.sevColor}22`, color: t.sevColor }}
                >
                  {t.icon}
                </span>
                <div>
                  <b className="text-[14px] block leading-tight" style={{ color: t.sevColor }}>
                    {t.label}
                  </b>
                  <span className="text-[10px] text-ink-400">{t.techniqueShort}</span>
                </div>
              </div>
              <div className="text-[12px] text-ink-300 leading-relaxed mb-3">{t.desc}</div>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ring-1 ${sevTone(t.severity)}`}>
                {t.severity}
              </span>
            </button>
          );
        })}
      </div>

      {meta && (
        <div className="panel p-6 border-l-[3px] animate-fade-up" style={{ borderLeftColor: meta.sevColor }}>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-brand-blue font-bold text-[14px]">{meta.label}</span>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ring-1 ${sevTone(meta.severity)}`}>
              {meta.severity}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <span className="eyebrow block mb-2">즉시 확인할 서비스</span>
              <div className="flex flex-wrap gap-1.5">
                {meta.services[cspKey].map((s) => (
                  <span key={s} className="tag-blue text-[11px]">{s}</span>
                ))}
              </div>
            </div>
            <div>
              <span className="eyebrow block mb-2">관련 MITRE ATT&CK 전술</span>
              <div className="flex flex-wrap gap-1.5">
                {meta.mitre.map((m) => (
                  <span key={m} className="tag-purple text-[11px]">{m}</span>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-ink-700/60">
            <span className="eyebrow block mb-1.5">초동 포인트</span>
            <p className="text-[12.5px] text-ink-200 leading-7">{meta.hint}</p>
          </div>
        </div>
      )}

      <div className="flex justify-between gap-2">
        <button onClick={onPrev} className="btn-ghost">
          ← 이전
        </button>
        <button onClick={onNext} disabled={!selected} className="btn-primary disabled:opacity-50">
          다음: 시스템 구성 →
        </button>
      </div>
    </div>
  );
};

export default Step1_TypeCards;
