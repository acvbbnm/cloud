import { useQuery } from '@tanstack/react-query';

import Card from '@/components/Card';
import Badge from '@/components/Badge';
import { useCaseStore } from '@/stores/useCaseStore';
import { getGuideV2 } from '@/api/intake';

import type {
  GuideV2AppliedModifier,
  GuideV2EnvWarning,
  GuideV2PhaseGroup,
  GuideV2SourceRef,
  GuideV2Target,
} from '@/types';

interface Step3V2Props {
  onPrev: () => void;
  onComplete: () => void;
}

// 외부 표준별 색상 톤 (출처 칩 시각화)
const STD_TONE: Record<string, 'red' | 'amber' | 'teal' | 'blue' | 'purple' | 'gray'> = {
  'Google Cloud Threat Intel': 'blue',
  'MITRE ATT&CK': 'purple',
  MITRE: 'purple',
  'KISA 침해사고 분석절차 안내서': 'red',
  KISA: 'red',
  'NIST SP 800-86': 'amber',
  NIST: 'amber',
  'ISO/IEC 27037': 'teal',
  ISO: 'teal',
  'CSA Top Threats to Cloud Computing': 'gray',
  CSA: 'gray',
};

const stdTone = (std: string | null | undefined): 'red' | 'amber' | 'teal' | 'blue' | 'purple' | 'gray' => {
  if (!std) return 'gray';
  for (const [key, tone] of Object.entries(STD_TONE)) {
    if (std.includes(key)) return tone;
  }
  return 'gray';
};

// 사고유형 → 한국어 라벨 (V-1 Step1 과 같은 표시)
const INCIDENT_TYPE_KO: Record<string, string> = {
  CREDENTIAL_THEFT: '자격증명 탈취',
  PRIVILEGE_ESCALATION: '권한 상승',
  DATA_EXFILTRATION: '데이터 유출',
  AUDIT_LOG_TAMPERING: '감사 로그 변조',
  MULTI_CSP_LATERAL: '멀티 CSP 횡이동',
};

// 우선순위 색상 분기
const priorityColor = (p: number): string => {
  if (p >= 11) return 'text-red-400 border-red-500/40 bg-red-500/10';
  if (p >= 8) return 'text-amber-400 border-amber-500/40 bg-amber-500/10';
  return 'text-brand-blue border-brand-blue/40 bg-brand-blue/10';
};

// ── 출처 칩 ──────────────────────────────────────────
const SourceChip = ({ s }: { s: GuideV2SourceRef }) => {
  const tone = stdTone(s.std);
  return (
    <span
      title={`${s.std ?? '표준'} ${s.ref ?? ''}${s.title ? ` — ${s.title}` : ''}`}
      className="inline-flex items-center gap-1 text-[10px] bg-ink-900 border border-ink-700/60 rounded-full px-2 py-0.5"
    >
      <Badge tone={tone} size="sm">
        {(s.std ?? '?').split(' ')[0]}
      </Badge>
      <span className="text-ink-300">{s.ref ?? '—'}</span>
    </span>
  );
};

// ── 단일 카테고리 항목 ────────────────────────────────
const TargetRow = ({ t }: { t: GuideV2Target }) => (
  <div className="bg-ink-900/60 border border-ink-700/70 rounded-xl p-3.5 mb-2 hover:border-brand-blue/40 transition-colors">
    <div className="flex items-start gap-2 mb-1.5">
      <span
        className={`inline-flex items-center justify-center min-w-[44px] h-6 rounded-md border text-[11px] font-bold ${priorityColor(
          t.priority,
        )}`}
        title={t.priority_basis}
      >
        P{t.priority}
      </span>
      <Badge tone={t.evidence_role === 'REQUIRED' ? 'red' : 'amber'} size="sm">
        {t.evidence_role}
      </Badge>
      <code className="text-[10.5px] text-ink-400 font-mono">{t.category_id}</code>
      <span className="font-semibold text-[13px] flex-1">{t.category_name}</span>
    </div>

    {/* csp_specific — NCP / NHN 별 매칭 패턴 */}
    {Object.keys(t.csp_specific || {}).length > 0 && (
      <div className="text-[11px] text-ink-300 leading-6 mb-1 ml-[52px] font-mono">
        {Object.entries(t.csp_specific).map(([csp, desc]) => (
          <div key={csp}>
            <span className="text-ink-500">{csp.toUpperCase()}</span> · {desc}
          </div>
        ))}
      </div>
    )}

    {/* 출처 칩 */}
    {t.sources && t.sources.length > 0 && (
      <div className="flex flex-wrap gap-1 mb-1 ml-[52px]">
        {t.sources.map((s, i) => (
          <SourceChip key={i} s={s} />
        ))}
      </div>
    )}

    {/* 휘발성 근거 + rationale */}
    <div className="ml-[52px]">
      <div className="text-[10.5px] text-ink-500 mb-0.5">📊 {t.priority_basis}</div>
      <div className="text-[11.5px] text-ink-300 leading-6">📚 {t.rationale}</div>
    </div>
  </div>
);

// ── Phase 카드 ────────────────────────────────────────
const PhaseCard = ({ phase, data }: { phase: string; data: GuideV2PhaseGroup }) => (
  <Card
    title={
      <div className="flex items-center gap-2">
        <span className="text-[11px] text-brand-purple font-mono">{data.phase_id ?? phase}</span>
        <span>{data.phase_name ?? phase}</span>
        <span className="text-[11px] text-ink-400">({phase})</span>
      </div>
    }
    subtitle={
      <div className="flex items-center gap-2 text-[10.5px] flex-wrap">
        {data.mitre_url && (
          <a
            href={data.mitre_url}
            target="_blank"
            rel="noreferrer"
            className="text-brand-purple hover:underline"
          >
            📖 MITRE
          </a>
        )}
        <span className="text-ink-400">·</span>
        <span className="text-ink-400">{data.kisa_reference}</span>
      </div>
    }
    className="mb-3"
  >
    {data.phase_description && (
      <p className="text-[11.5px] text-ink-300 leading-6 mb-2">{data.phase_description}</p>
    )}
    {data.targets.length === 0 ? (
      <div className="text-[11.5px] text-ink-500 py-2">(이 단계에 매칭되는 카테고리 없음)</div>
    ) : (
      <div>
        {data.targets.map((t) => (
          <TargetRow key={`${phase}-${t.category_id}`} t={t} />
        ))}
      </div>
    )}
  </Card>
);

// ── 환경 보정 적용 카드 ────────────────────────────────
const AppliedModifiersCard = ({ items }: { items: GuideV2AppliedModifier[] }) => {
  if (!items || items.length === 0) {
    return (
      <Card title={<>🛠 환경 보정 (applied_modifiers)</>} className="mb-3">
        <p className="text-[11.5px] text-ink-400">
          시스템 환경(<code>system_config</code>)에 따라 추가 적용된 보정이 없습니다.
        </p>
      </Card>
    );
  }
  return (
    <Card
      title={<>🛠 환경 보정 ({items.length}건 적용됨)</>}
      subtitle={
        <span className="text-[10.5px] text-ink-400">
          Step2 입력값이 카테고리·단계 우선순위에 반영된 결과
        </span>
      }
      className="mb-3"
    >
      <div className="space-y-1.5">
        {items.map((m) => (
          <div
            key={m.id}
            className="bg-ink-900/60 border border-ink-700/70 rounded-lg px-3 py-2 text-[11.5px] leading-6"
          >
            <div className="flex items-center gap-1.5 flex-wrap mb-0.5">
              <code className="text-[10px] text-ink-500 font-mono">{m.id}</code>
              <Badge tone="blue" size="sm">
                {m.effect}
              </Badge>
              {m.category_id && (
                <span className="text-[10.5px] text-ink-400">
                  → <code className="font-mono">{m.category_id}</code>
                  {m.boost !== null && m.boost !== undefined && m.boost !== 0 && (
                    <span className="text-amber-400"> +{m.boost}</span>
                  )}
                </span>
              )}
              {m.kill_chain_phase && (
                <span className="text-[10.5px] text-ink-400">
                  → phase <code className="text-brand-purple">{m.kill_chain_phase}</code>
                </span>
              )}
            </div>
            <div className="text-ink-300">{m.reason}</div>
            <div className="text-[10px] text-ink-500 mt-0.5">📚 {m.source}</div>
          </div>
        ))}
      </div>
    </Card>
  );
};

// ── 환경 경고 카드 ─────────────────────────────────────
const EnvWarningsCard = ({ items }: { items: GuideV2EnvWarning[] }) => {
  if (!items || items.length === 0) return null;
  return (
    <Card
      title={<span className="text-red-400">⚠ 환경 경고 ({items.length})</span>}
      subtitle={
        <span className="text-[10.5px] text-ink-400">
          입력된 환경 자체에 즉시 조치 권장 사항
        </span>
      }
      className="mb-3"
    >
      <div className="space-y-1.5">
        {items.map((w, i) => (
          <div
            key={i}
            className="bg-red-500/5 border border-red-500/30 rounded-lg px-3 py-2 text-[12px] leading-6"
          >
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="inline-flex items-center justify-center min-w-[36px] h-5 rounded-md border border-red-500/40 bg-red-500/10 text-red-400 text-[10px] font-bold">
                P{w.priority}
              </span>
              <Badge tone="red" size="sm">
                {w.evidence_role}
              </Badge>
              <span className="font-semibold">{w.category_name}</span>
            </div>
            <div className="text-ink-300 text-[11.5px]">{w.rationale}</div>
            {w.from_modifier && (
              <div className="text-[10px] text-ink-500 mt-0.5 font-mono">
                from: {w.from_modifier}
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
};

// ── 메인 컴포넌트 ──────────────────────────────────────
const Step3GuideChecklistV2 = ({ onPrev, onComplete }: Step3V2Props) => {
  const caseId = useCaseStore((s) => s.caseId);

  const guideQuery = useQuery({
    queryKey: ['guide-v2', caseId],
    queryFn: () => getGuideV2(caseId!),
    enabled: !!caseId,
    staleTime: 30_000,
  });

  if (!caseId) {
    return (
      <div className="panel p-6 text-[12.5px]">
        <p className="text-ink-300">
          ⚠ 케이스가 없습니다. 이전 단계에서 케이스를 먼저 생성해주세요.
        </p>
        <button onClick={onPrev} className="btn-ghost mt-3">
          ← Step2 시스템 구성
        </button>
      </div>
    );
  }

  if (guideQuery.isLoading) {
    return (
      <div className="panel p-6 text-center text-ink-400 text-[12.5px]">
        v2 수집 가이드 생성 중… (POST /api/guide/v2)
      </div>
    );
  }

  if (guideQuery.isError) {
    return (
      <div className="panel p-6 text-center">
        <p className="text-red-400 text-[12.5px] mb-2">
          v2 가이드 호출 실패. 백엔드(<code>/api/guide/v2</code>)를 확인해주세요.
        </p>
        <p className="text-[10.5px] text-ink-400">
          {(guideQuery.error as Error)?.message ?? 'unknown error'}
        </p>
        <button onClick={onPrev} className="btn-ghost mt-3">
          ← Step2
        </button>
      </div>
    );
  }

  const guide = guideQuery.data;
  if (!guide) return null;

  const phaseEntries = Object.entries(guide.phases);
  const totalTargets = phaseEntries.reduce((n, [, p]) => n + p.targets.length, 0);

  return (
    <div className="space-y-3 animate-fade-up">
      {/* 헤더 — 사고유형 + 메트릭 */}
      <div className="panel p-4 border-l-[3px] border-l-brand-teal">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className="eyebrow">v2 수집 가이드 (외부 표준 6종 기반)</span>
          <Badge tone="purple">{guide.incidentType}</Badge>
          <span className="text-[11px] text-ink-400">
            {INCIDENT_TYPE_KO[guide.incidentType] ?? ''}
          </span>
          <Badge tone="blue" size="sm">
            {guide.csp.toUpperCase()}
          </Badge>
          <span className="ml-auto text-[10.5px] text-ink-500 font-mono">
            caseId: {guide.caseId.slice(0, 8)}…
          </span>
        </div>
        <div className="text-[11.5px] text-ink-300 leading-6">
          Kill Chain <b className="text-ink-100">{phaseEntries.length}</b>단계 ·{' '}
          <b className="text-ink-100">{totalTargets}</b>개 카테고리 ·{' '}
          {guide.environment_warnings.length > 0 && (
            <span className="text-red-400">⚠ 환경 경고 {guide.environment_warnings.length}건</span>
          )}
          {guide.environment_warnings.length === 0 && '환경 경고 없음'}
        </div>
      </div>

      {/* 환경 경고 (있는 경우 최상단) */}
      <EnvWarningsCard items={guide.environment_warnings} />

      {/* Kill Chain Phase 카드들 */}
      {phaseEntries.length === 0 ? (
        <div className="panel p-6 text-center text-ink-400 text-[12px]">
          매칭되는 Kill Chain 단계가 없습니다. 사고유형 설정을 확인해주세요.
        </div>
      ) : (
        phaseEntries.map(([phase, data]) => (
          <PhaseCard key={phase} phase={phase} data={data} />
        ))
      )}

      {/* 적용된 환경 보정 */}
      <AppliedModifiersCard items={guide.applied_modifiers} />

      {/* 출처 푸터 */}
      <Card title={<>📚 본 가이드의 출처 (외부 표준 6종)</>} className="mb-3">
        <ul className="text-[11.5px] text-ink-300 leading-7 list-disc pl-5">
          {guide.source_standards.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
      </Card>

      {/* 액션 */}
      <div className="flex justify-between mt-4">
        <button onClick={onPrev} className="btn-ghost">
          ← Step2
        </button>
        <button onClick={onComplete} className="btn-primary">
          V-2 로그 수집 진행 →
        </button>
      </div>
    </div>
  );
};

export default Step3GuideChecklistV2;
