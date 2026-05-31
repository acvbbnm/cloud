import { useState } from 'react';

import { useCaseStore } from '@/stores/useCaseStore';

import type { Severity, TLP } from '@/types';

interface Step1Props {
  onPrev: () => void;
  onNext: (occurredAt: string) => void;
}

const severityOptions: { id: Severity; label: string; color: string; desc: string }[] = [
  { id: 'critical', label: 'Critical', color: '#ef4444', desc: '즉시 대응' },
  { id: 'high', label: 'High', color: '#f97316', desc: '주요 영향' },
  { id: 'medium', label: 'Medium', color: '#eab308', desc: '제한된 영향' },
  { id: 'low', label: 'Low', color: '#22c55e', desc: '경미' },
];

const tlpOptions: { id: TLP; label: string; color: string; desc: string }[] = [
  { id: 'RED', label: 'RED', color: '#ef4444', desc: '개인 한정' },
  { id: 'AMBER', label: 'AMBER', color: '#f59e0b', desc: '조직 내부' },
  { id: 'GREEN', label: 'GREEN', color: '#22c55e', desc: '커뮤니티 공유' },
  { id: 'WHITE', label: 'WHITE', color: '#e5e7eb', desc: '공개 가능' },
];

// datetime-local input 기본값 (현재 시각, 로컬 ISO 분 단위)
const nowLocalIso = (): string => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};

/**
 * V-1 Step 1 — 케이스 메타 (빈 케이스 시작).
 *
 * dev3 (2026-05-18): 사고유형 5장 카드 폐기 → 메타 입력 폼.
 *   incident_type 은 UNCLASSIFIED 로 시작, Step 2 Discovery Loop 에서 확정.
 *   학술 근거: TheHive 5 Create Case + DFIR-IRIS + NIST SP 800-61r2 §3.2 scope-first.
 */
const Step1_CaseMetadata = ({ onPrev, onNext }: Step1Props) => {
  const {
    title,
    severity,
    tlp,
    occurredAt: storedOccurredAt,
    setTitle,
    setSeverity,
    setTlp,
    setOccurredAt,
  } = useCaseStore();
  // V1.fix.1 (2026-05-31) — store 에 이미 저장돼 있으면 그 값 prefill (다른 뷰 다녀와도 유지)
  const [occurredAt, setOccurredAtLocal] = useState<string>(
    storedOccurredAt ?? nowLocalIso(),
  );

  // tlp 기본값: AMBER (조직 내부 공유 — TheHive 5 권장)
  const currentTlp: TLP = tlp ?? 'AMBER';
  const currentSeverity: Severity = (severity as Severity) ?? 'high';

  const canProceed = !!title?.trim() && !!occurredAt;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="h-section">사고 케이스 메타</h2>
        <p className="text-[13px] text-ink-400 mt-1.5 max-w-2xl">
          빈 케이스로 시작합니다. 사고유형은{' '}
          <span className="text-brand-teal font-semibold">Step 2 Discovery Loop</span> 에서
          단서·로그 분석·결정 트리로 확정됩니다.
        </p>
      </div>

      {/* 필수 입력 폼 */}
      <div className="panel p-5 flex flex-col gap-5">
        <span className="eyebrow text-[10.5px]">필수 입력</span>

        {/* 사건 제목 */}
        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] text-ink-300 font-medium">사건 제목</label>
          <input
            type="text"
            value={title ?? ''}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="예: 의심스러운 로그인 활동"
            className="bg-ink-900 border border-ink-700 rounded-md px-3 py-2 text-[13px] text-ink-100 focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
          />
        </div>

        {/* 발생 시각 */}
        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] text-ink-300 font-medium">발생 시각</label>
          <input
            type="datetime-local"
            value={occurredAt}
            onChange={(e) => {
              setOccurredAtLocal(e.target.value);
              setOccurredAt(e.target.value); // V1.fix.1 — store 동기화로 Step 2 prefill 가능
            }}
            className="bg-ink-900 border border-ink-700 rounded-md px-3 py-2 text-[13px] text-ink-100 focus:outline-none focus:ring-2 focus:ring-brand-blue/40 w-fit"
          />
        </div>

        {/* 심각도 */}
        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] text-ink-300 font-medium">심각도</label>
          <div className="flex gap-2 flex-wrap">
            {severityOptions.map((s) => {
              const sel = currentSeverity === s.id;
              return (
                <button
                  key={s.id}
                  onClick={() => setSeverity(s.id)}
                  className={`px-3 py-2 rounded-md border text-[12px] transition-all ${
                    sel
                      ? 'border-transparent shadow-glow text-white font-semibold'
                      : 'border-ink-700 text-ink-300 hover:border-ink-500'
                  }`}
                  style={sel ? { background: s.color } : undefined}
                >
                  {s.label}
                  <span className="ml-1.5 text-[10.5px] opacity-80">— {s.desc}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* TLP */}
        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] text-ink-300 font-medium">
            TLP <span className="text-ink-500 text-[10.5px]">(정보 공유 등급)</span>
          </label>
          <div className="flex gap-2 flex-wrap">
            {tlpOptions.map((t) => {
              const sel = currentTlp === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => setTlp(t.id)}
                  className={`px-3 py-2 rounded-md border text-[12px] transition-all ${
                    sel
                      ? 'border-transparent shadow-glow text-ink-950 font-semibold'
                      : 'border-ink-700 text-ink-300 hover:border-ink-500'
                  }`}
                  style={sel ? { background: t.color } : undefined}
                >
                  {t.label}
                  <span className="ml-1.5 text-[10.5px] opacity-80">— {t.desc}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 네비게이션 */}
      <div className="flex items-center justify-between">
        <button onClick={onPrev} className="btn-ghost">
          ← 이전
        </button>
        <button
          onClick={() => {
            if (!canProceed) return;
            setOccurredAt(occurredAt); // V1.fix.1 — 다음 진입 직전 store 확정
            onNext(occurredAt);
          }}
          disabled={!canProceed}
          className={`btn-primary ${!canProceed ? 'opacity-40 cursor-not-allowed' : ''}`}
        >
          다음 →
        </button>
      </div>
    </div>
  );
};

export default Step1_CaseMetadata;
