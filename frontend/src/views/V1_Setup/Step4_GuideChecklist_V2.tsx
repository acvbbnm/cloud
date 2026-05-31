import { useEffect, useState } from 'react';

import { useQuery } from '@tanstack/react-query';

import Card from '@/components/Card';
import Badge from '@/components/Badge';
import { useCaseStore } from '@/stores/useCaseStore';
import { getGuideV2, getGuidePreview } from '@/api/intake';

import type {
  GuideV2AppliedModifier,
  GuideV2ClueSignals,
  GuideV2CollectionMethod,
  GuideV2EnvWarning,
  GuideV2PhaseGroup,
  GuideV2SourceRef,
  GuideV2Target,
  IncidentType,
} from '@/types';

interface Step4V2Props {
  onPrev: () => void;
  onComplete: () => void;
}

//  상수 

const STD_META: Record<
  string,
  { tone: 'red' | 'amber' | 'teal' | 'blue' | 'purple' | 'gray'; short: string; full: string }
> = {
  'Google Cloud Threat Intel': { tone: 'blue', short: 'Google', full: 'Google Cloud Threat Intel' },
  'MITRE ATT&CK': { tone: 'purple', short: 'MITRE', full: 'MITRE ATT&CK Cloud Matrix v14' },
  MITRE: { tone: 'purple', short: 'MITRE', full: 'MITRE ATT&CK' },
  'KISA 침해사고 분석절차 안내서': {
    tone: 'red',
    short: 'KISA',
    full: 'KISA 침해사고 분석절차 안내서 (제2010-8호)',
  },
  KISA: { tone: 'red', short: 'KISA', full: 'KISA 침해사고 분석절차 안내서' },
  'NIST SP 800-86': { tone: 'amber', short: 'NIST', full: 'NIST SP 800-86 Forensic Techniques' },
  NIST: { tone: 'amber', short: 'NIST', full: 'NIST SP 800-86' },
  'ISO/IEC 27037': { tone: 'teal', short: 'ISO', full: 'ISO/IEC 27037:2012' },
  ISO: { tone: 'teal', short: 'ISO', full: 'ISO/IEC 27037' },
  'CSA Top Threats to Cloud Computing': {
    tone: 'gray',
    short: 'CSA',
    full: 'CSA Top Threats to Cloud Computing 2024',
  },
  CSA: { tone: 'gray', short: 'CSA', full: 'CSA Top Threats 2024' },
};

const stdMeta = (std: string | null | undefined) => {
  if (!std) return { tone: 'gray' as const, short: '?', full: '알 수 없는 표준' };
  for (const [key, meta] of Object.entries(STD_META)) {
    if (std.includes(key)) return meta;
  }
  return { tone: 'gray' as const, short: std.split(' ')[0], full: std };
};

const INCIDENT_TYPE_KO: Record<string, string> = {
  CREDENTIAL_THEFT: '자격증명 탈취',
  PRIVILEGE_ESCALATION: '권한 상승',
  DATA_EXFILTRATION: '데이터 유출',
  AUDIT_LOG_TAMPERING: '감사 로그 변조',
  RANSOMWARE: '랜섬웨어',
  MISCONFIG_EXPOSURE: '설정 오류 노출',
  PHISH_INITIAL_ACCESS: '피싱 초기 침투',
  INSIDER_THREAT: '내부자 위협',
  UNCLASSIFIED: '미분류',
};

const CSP_KO: Record<string, string> = {
  naver: 'NCP',
  nhn: 'NHN',
};

// MITRE Kill Chain 12 전술 한국어명 + 한 줄 정의 (PhaseInfoBanner 용)
const KILL_CHAIN_TACTICS: { id: string; en: string; ko: string; def: string }[] = [
  { id: 'TA0001', en: 'Initial Access', ko: '초기 침투', def: '공격자가 클라우드 환경에 처음 들어오는 단계 (자격증명 남용·피싱·공인 IP 노출)' },
  { id: 'TA0002', en: 'Execution', ko: '실행', def: '악성 코드·명령이 클라우드 자원에서 실행되는 단계' },
  { id: 'TA0003', en: 'Persistence', ko: '영속성 확보', def: '재로그인 없이 접근을 유지하는 백도어 (AccessKey 추가·Sub Account 등) 확보' },
  { id: 'TA0004', en: 'Privilege Escalation', ko: '권한 확대', def: '일반 사용자 → 관리자 등 더 높은 권한 획득' },
  { id: 'TA0005', en: 'Stealth', ko: '은닉', def: '탐지를 회피하기 위해 흔적 제거·로그 변조 수행 (감사 로그 자체에 손대는 단계)' },
  { id: 'TA0112', en: 'Defense Impairment', ko: '방어 무력화', def: '보안 도구·감사 로그 비활성화 (Tracer 삭제 등)' },
  { id: 'TA0006', en: 'Credential Access', ko: '자격증명 접근', def: '비밀번호·AccessKey·root 비밀번호 등 자격증명 탈취' },
  { id: 'TA0007', en: 'Discovery', ko: '환경 탐색', def: '리소스·계정·정책을 열거 (정찰)' },
  { id: 'TA0008', en: 'Lateral Movement', ko: '횡이동', def: '한 시스템 → 다른 시스템 / 한 CSP → 다른 CSP 로 이동' },
  { id: 'TA0009', en: 'Collection', ko: '데이터 수집', def: '탈취·유출 대상 데이터를 식별·수집' },
  { id: 'TA0010', en: 'Exfiltration', ko: '데이터 유출', def: '수집한 데이터를 외부로 반출 (Pre-signed URL·외부 S3 export 등)' },
  { id: 'TA0040', en: 'Impact', ko: '영향·파괴', def: '서비스 중단·자원 삭제·데이터 파괴' },
];

//  헬퍼 

const priorityColor = (p: number): string => {
  if (p >= 11) return 'text-red-300 border-red-500/50 bg-red-500/15';
  if (p >= 8) return 'text-amber-300 border-amber-500/50 bg-amber-500/15';
  return 'text-brand-blue border-brand-blue/50 bg-brand-blue/10';
};
const priorityLabel = (p: number): string => {
  if (p >= 11) return '즉시 수집';
  if (p >= 8) return '우선 수집';
  return '일반 수집';
};

// priority_basis 에 "+ 환경 보정 +N" 이 포함되어 있으면 N 추출
const extractBoost = (basis: string | null | undefined): number => {
  if (!basis) return 0;
  const m = basis.match(/환경 보정 \+(\d+)/);
  return m ? parseInt(m[1], 10) : 0;
};

const summarizeForList = (t: GuideV2Target, primaryCsp: string): string => {
  const cs = t.csp_specific || {};
  const keys = Object.keys(cs);
  if (keys.length === 0) return '';
  const preferred = primaryCsp === 'all' ? 'naver' : primaryCsp;
  const csp = cs[preferred] ? preferred : keys[0];
  const label = CSP_KO[csp] ?? csp.toUpperCase();
  return `${label} · ${cs[csp]}`;
};

//  외부 표준 카드 (KB 패널용) 
const SourceCardLarge = ({ s }: { s: GuideV2SourceRef }) => {
  const meta = stdMeta(s.std);
  const Inner = (
    <div className="bg-ink-900/70 border border-ink-700/60 rounded-lg px-3 py-2 hover:border-brand-blue/40 transition-colors">
      <div className="flex items-center gap-1.5 mb-1 flex-wrap">
        <Badge tone={meta.tone} size="sm">
          {meta.short}
        </Badge>
        <span className="text-[11px] text-ink-200 font-semibold truncate">{meta.full}</span>
        {s.url && <span className="ml-auto text-[10px] text-brand-blue">외부 ↗</span>}
      </div>
      {s.ref && <div className="text-[11px] text-ink-300 font-mono">{s.ref}</div>}
      {s.title && <div className="text-[11px] text-ink-400 leading-5 mt-0.5">{s.title}</div>}
    </div>
  );
  return s.url ? (
    <a href={s.url} target="_blank" rel="noreferrer" className="block">
      {Inner}
    </a>
  ) : (
    Inner
  );
};

//  수집 방법 카드 (KB 패널용) 
const CollectionMethodCard = ({ csp, method }: { csp: string; method: GuideV2CollectionMethod }) => {
  if (!method) return null;
  const label = CSP_KO[csp] ?? csp.toUpperCase();
  const patternKind = method.pattern_kind || (csp === 'naver' ? 'action' : 'eventId');
  return (
    <div className="bg-ink-900/70 border border-ink-700/60 rounded-lg p-3 mb-2">
      <div className="flex items-center gap-1.5 mb-2 flex-wrap">
        <Badge tone={csp === 'naver' ? 'teal' : 'blue'} size="sm">
          {label}
        </Badge>
        <span className="text-[11.5px] text-ink-200 font-semibold">{method.log_source}</span>
        {method.patterns && method.patterns.length > 0 && (
          <code
            className="text-[10.5px] text-ink-400 font-mono ml-auto truncate max-w-[60%]"
            title={method.patterns.join(' / ')}
          >
            {patternKind}: {method.patterns.slice(0, 2).join(' · ')}
            {method.patterns.length > 2 && ` (+${method.patterns.length - 2})`}
          </code>
        )}
      </div>
      {method.collection_steps && method.collection_steps.length > 0 && (
        <ol className="text-[11.5px] text-ink-200 leading-6 list-decimal pl-5 space-y-0.5">
          {method.collection_steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
      )}
      {method.cli_hint && (
        <div className="mt-2 pt-2 border-t border-ink-700/40">
          <div className="text-[9.5px] text-ink-500 uppercase tracking-wider mb-0.5">CLI / 자동화</div>
          <code className="text-[10.5px] text-ink-300 font-mono break-all leading-5">
            {method.cli_hint}
          </code>
        </div>
      )}
    </div>
  );
};

//  KB 패널 
const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div className="mb-3.5">
    <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-1.5">
      {title}
    </div>
    {children}
  </div>
);

const KbPanel = ({
  target,
  primaryCsp,
  onClose,
}: {
  target: GuideV2Target | null;
  primaryCsp: string;
  onClose: () => void;
}) => {
  if (!target) {
    return (
      <div className="panel p-5 lg:sticky lg:top-4 h-fit">
        <div className="eyebrow mb-2"> 지식 베이스 (KB)</div>
        <div className="text-[12px] text-ink-300 leading-6">
          좌측 가이드 / 매트릭스 셀을 클릭하면 여기에 <b>왜 필요한가</b>, <b>어떻게 수집하나</b>, <b>활용 사례</b>, <b>외부 표준 인용</b> 등 자세한 내용이 펼쳐집니다.
        </div>
        <div className="mt-3 text-[10.5px] text-ink-500 leading-5">
          KB 인덱스는 외부 표준 6종 (Google Cloud Threat Intel · MITRE ATT&CK · KISA · NIST · ISO · CSA) 의 분류 번호를 그대로 따릅니다.
        </div>
      </div>
    );
  }

  const methods = target.collection_methods || {};
  const cspOrder =
    primaryCsp === 'all'
      ? Object.keys(methods)
      : methods[primaryCsp]
      ? [primaryCsp, ...Object.keys(methods).filter((c) => c !== primaryCsp)]
      : Object.keys(methods);

  return (
    <div className="panel p-5 lg:sticky lg:top-4 max-h-[calc(100vh-2rem)] overflow-y-auto">
      <div className="flex items-start gap-2 mb-3 pb-3 border-b border-ink-700/60">
        <div className="flex-1 min-w-0">
          <div className="eyebrow mb-1"> KB · {target.category_id}</div>
          <div className="text-[15px] font-bold text-ink-100 leading-snug">{target.category_name}</div>
          <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
            <span
              className={`inline-flex items-center justify-center min-w-[42px] h-5 rounded-md border text-[10px] font-bold ${priorityColor(
                target.priority,
              )}`}
            >
              P{target.priority}
            </span>
            <Badge tone={target.evidence_role === 'REQUIRED' ? 'red' : 'amber'} size="sm">
              {target.evidence_role === 'REQUIRED' ? '필수' : '보강'}
            </Badge>
            <span className="text-[10.5px] text-ink-400">{priorityLabel(target.priority)}</span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-ink-500 hover:text-ink-200 text-[18px] leading-none px-1"
          title="패널 닫기"
        >
          ×
        </button>
      </div>

      <Section title=" 왜 필요한가">
        <p className="text-[12px] text-ink-200 leading-6 whitespace-pre-line">{target.rationale}</p>
      </Section>

      {cspOrder.length > 0 && (
        <Section title=" 어떻게 수집하나 (CSP 별 단계)">
          {cspOrder.map((csp) => (
            <CollectionMethodCard key={csp} csp={csp} method={methods[csp]} />
          ))}
        </Section>
      )}

      {target.use_cases && target.use_cases.length > 0 && (
        <Section title={` 활용 사례 (${target.use_cases.length}건)`}>
          <ul className="text-[11.5px] text-ink-200 leading-6 list-disc pl-5 space-y-0.5">
            {target.use_cases.map((u, i) => (
              <li key={i}>{u}</li>
            ))}
          </ul>
        </Section>
      )}

      {target.priority_basis && (
        <Section title=" 우선순위 산출 근거">
          <p className="text-[11px] text-ink-300 leading-6">{target.priority_basis}</p>
        </Section>
      )}

      {(target.sources ?? []).length > 0 && (
        <Section title={` 외부 표준 인용 (${target.sources?.length ?? 0}건)`}>
          <div className="space-y-1.5">
            {target.sources?.map((s, i) => (
              <SourceCardLarge key={i} s={s} />
            ))}
          </div>
        </Section>
      )}
    </div>
  );
};

//  Phase 안내 카드 (접이식) 
const PhaseInfoBanner = ({ activePhases }: { activePhases: Set<string> }) => {
  const [expanded, setExpanded] = useState(false);
  const activeCount = KILL_CHAIN_TACTICS.filter((t) => activePhases.has(t.en)).length;

  return (
    <div className="panel mb-3">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-ink-900/50 transition-colors"
      >
        <span className="text-[14px]"></span>
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-semibold text-ink-100">
            MITRE Kill Chain 12 전술이란?
          </div>
          <div className="text-[10.5px] text-ink-400 mt-0.5">
            공격이 시간 순으로 거치는 12단계. 현재 사고유형은 이 중{' '}
            <span className="text-brand-teal font-semibold">{activeCount}단계</span>를 다룹니다.
          </div>
        </div>
        <span
          className={`text-[14px] text-ink-500 transition-transform ${expanded ? 'rotate-90' : ''}`}
        >
          ›
        </span>
      </button>
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-ink-700/40">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
            {KILL_CHAIN_TACTICS.map((t) => {
              const active = activePhases.has(t.en);
              return (
                <div
                  key={t.id}
                  className={`rounded-lg px-3 py-2 border transition-all ${
                    active
                      ? 'bg-brand-teal/10 border-brand-teal/50'
                      : 'bg-ink-900/40 border-ink-700/60 opacity-60'
                  }`}
                >
                  <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
                    <span className="text-[9.5px] font-mono text-brand-purple">{t.id}</span>
                    <span
                      className={`text-[11.5px] font-semibold ${
                        active ? 'text-ink-100' : 'text-ink-400'
                      }`}
                    >
                      {t.ko}
                    </span>
                    <span className="text-[10px] text-ink-500">({t.en})</span>
                    {active && <Badge tone="teal" size="sm">현재 가이드</Badge>}
                  </div>
                  <div className="text-[10.5px] text-ink-300 leading-5">{t.def}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

//  리스트 뷰: 단일 행 
interface TargetRowProps {
  t: GuideV2Target;
  primaryCsp: string;
  selected: boolean;
  checked: boolean;
  onClick: () => void;
  onToggleCheck: () => void;
}

const TargetRow = ({
  t,
  primaryCsp,
  selected,
  checked,
  onClick,
  onToggleCheck,
}: TargetRowProps) => {
  const summary = summarizeForList(t, primaryCsp);
  return (
    <div
      className={`bg-ink-900/60 border rounded-xl p-3 mb-1.5 transition-all ${
        selected
          ? 'border-brand-teal/70 bg-brand-teal/10 shadow-lg shadow-brand-teal/10'
          : checked
          ? 'border-green-500/40 bg-green-500/5'
          : 'border-ink-700/70 hover:border-brand-blue/40 hover:bg-ink-900'
      }`}
    >
      <div className="flex items-center gap-2.5">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleCheck();
          }}
          className={`flex-shrink-0 w-5 h-5 rounded border-2 transition-all flex items-center justify-center ${
            checked
              ? 'bg-green-500/80 border-green-500 text-white'
              : 'border-ink-600 hover:border-brand-teal/70'
          }`}
          title={checked ? '수집 완료 표시 해제' : '수집 완료로 표시'}
        >
          {checked && <span className="text-[12px] leading-none"></span>}
        </button>
        <span
          className={`flex-shrink-0 inline-flex flex-col items-center justify-center min-w-[58px] h-10 rounded-md border ${priorityColor(
            t.priority,
          )}`}
          title={t.priority_basis}
        >
          <span className="text-[10px] opacity-90 leading-none">P{t.priority}</span>
          <span className="text-[9.5px] mt-0.5 leading-none">{priorityLabel(t.priority)}</span>
        </span>
        <button onClick={onClick} className="flex-1 text-left min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
            <Badge tone={t.evidence_role === 'REQUIRED' ? 'red' : 'amber'} size="sm">
              {t.evidence_role === 'REQUIRED' ? '필수' : '보강'}
            </Badge>
            {t.clue_relevant && (
              <Badge tone="teal" size="sm">단서 연관</Badge>
            )}
            <span
              className={`font-semibold text-[13.5px] ${
                checked ? 'text-ink-400 line-through' : 'text-ink-100'
              }`}
            >
              {t.category_name}
            </span>
            <code className="text-[10px] text-ink-500 font-mono">{t.category_id}</code>
          </div>
          {summary && (
            <div className="text-[11px] text-ink-400 leading-5 truncate">
              <span className="text-brand-teal"></span> {summary}
            </div>
          )}
        </button>
        <span
          onClick={onClick}
          className={`flex-shrink-0 text-[18px] cursor-pointer transition-transform ${
            selected ? 'text-brand-teal rotate-90' : 'text-ink-500 hover:text-ink-300'
          }`}
        >
          ›
        </span>
      </div>
    </div>
  );
};

//  리스트 뷰: Phase 카드 
const PhaseCard = ({
  phase,
  data,
  primaryCsp,
  selectedKey,
  checkedKeys,
  onSelect,
  onToggleCheck,
}: {
  phase: string;
  data: GuideV2PhaseGroup;
  primaryCsp: string;
  selectedKey: string | null;
  checkedKeys: Set<string>;
  onSelect: (key: string, t: GuideV2Target) => void;
  onToggleCheck: (key: string) => void;
}) => {
  const targetsCount = data.targets.length;
  const checkedCount = data.targets.filter((t) =>
    checkedKeys.has(`${phase}::${t.category_id}`),
  ).length;
  return (
    <Card
      title={
        <div className="flex items-center gap-2 flex-wrap">
          <span>{data.phase_name ?? phase}</span>
          <span className="text-[10.5px] text-ink-500 font-mono">{data.phase_id}</span>
          {targetsCount > 0 && (
            <span
              className={`text-[10.5px] font-semibold ${
                checkedCount === targetsCount ? 'text-green-400' : 'text-ink-400'
              }`}
            >
              {checkedCount}/{targetsCount}
            </span>
          )}
        </div>
      }
      subtitle={
        <div className="flex items-center gap-2 text-[10px] flex-wrap">
          {data.mitre_url && (
            <a href={data.mitre_url} target="_blank" rel="noreferrer" className="text-brand-purple hover:underline">
               MITRE 공식
            </a>
          )}
          {data.kisa_reference && (
            <>
              <span className="text-ink-500">·</span>
              <span className="text-ink-400">{data.kisa_reference}</span>
            </>
          )}
        </div>
      }
      className="mb-3"
    >
      {data.phase_description && (
        <p className="text-[11px] text-ink-400 leading-5 mb-2">{data.phase_description}</p>
      )}
      {data.targets.length === 0 ? (
        <div className="text-[11.5px] text-ink-500 py-2">(이 단계에 매칭되는 카테고리 없음)</div>
      ) : (
        <div>
          {data.targets.map((t) => {
            const key = `${phase}::${t.category_id}`;
            return (
              <TargetRow
                key={key}
                t={t}
                primaryCsp={primaryCsp}
                selected={selectedKey === key}
                checked={checkedKeys.has(key)}
                onClick={() => onSelect(key, t)}
                onToggleCheck={() => onToggleCheck(key)}
              />
            );
          })}
        </div>
      )}
    </Card>
  );
};

//  매트릭스 뷰 
interface MatrixViewProps {
  phases: [string, GuideV2PhaseGroup][];
  selectedKey: string | null;
  checkedKeys: Set<string>;
  onSelect: (key: string, t: GuideV2Target) => void;
  onToggleCheck: (key: string) => void;
}

const MatrixView = ({
  phases,
  selectedKey,
  checkedKeys,
  onSelect,
  onToggleCheck,
}: MatrixViewProps) => {
  // 세로축: 고유 카테고리 ID (한 카테고리 = 한 행)
  const categoryMap = new Map<string, { name: string; priority: number; role: string }>();
  const cellMap = new Map<string, GuideV2Target>(); // key = `${phase}::${catId}`

  for (const [phase, group] of phases) {
    for (const t of group.targets) {
      if (!categoryMap.has(t.category_id)) {
        categoryMap.set(t.category_id, {
          name: t.category_name,
          priority: t.priority,
          role: t.evidence_role,
        });
      } else {
        const ex = categoryMap.get(t.category_id)!;
        if (t.priority > ex.priority) ex.priority = t.priority;
      }
      cellMap.set(`${phase}::${t.category_id}`, t);
    }
  }
  // P 내림차순 정렬
  const categoryIds = [...categoryMap.keys()].sort((a, b) => {
    const pa = categoryMap.get(a)!.priority;
    const pb = categoryMap.get(b)!.priority;
    return pb - pa;
  });

  return (
    <Card
      title={<> MITRE ATT&CK 매트릭스</>}
      subtitle={
        <span className="text-[10.5px] text-ink-400">
          가로: Kill Chain 단계 · 세로: 수집 카테고리 · 빈 칸은 매칭 없음 · 셀 클릭 시 KB 펼침
        </span>
      }
      className="mb-3"
    >
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px]">
          <thead>
            <tr>
              <th className="sticky left-0 bg-ink-900 z-10 text-left px-3 py-2 border-b border-ink-700/60 min-w-[180px]">
                <div className="text-[10.5px] text-ink-400 font-semibold">카테고리 (KB)</div>
              </th>
              {phases.map(([phase, data]) => (
                <th
                  key={phase}
                  className="text-center px-2 py-2 border-b border-l border-ink-700/60 min-w-[120px]"
                  title={data.phase_description}
                >
                  <div className="flex flex-col items-center gap-0.5">
                    <span className="text-[9.5px] font-mono text-brand-purple">{data.phase_id}</span>
                    <span className="text-[11.5px] font-semibold text-ink-100">
                      {data.phase_name ?? phase}
                    </span>
                    <span className="text-[9.5px] text-ink-500">{phase}</span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {categoryIds.map((catId) => {
              const meta = categoryMap.get(catId)!;
              return (
                <tr key={catId} className="hover:bg-ink-900/30">
                  <th className="sticky left-0 bg-ink-950 z-10 text-left px-3 py-2 border-b border-ink-700/40 align-top">
                    <div className="flex items-start gap-1.5 flex-wrap">
                      <div className="flex-1 min-w-0">
                        <div className="text-[11.5px] font-semibold text-ink-100 leading-tight">
                          {meta.name}
                        </div>
                        <div className="flex items-center gap-1 mt-0.5">
                          <code className="text-[9.5px] text-ink-500 font-mono">{catId}</code>
                          <Badge tone={meta.role === 'REQUIRED' ? 'red' : 'amber'} size="sm">
                            {meta.role === 'REQUIRED' ? '필수' : '보강'}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  </th>
                  {phases.map(([phase]) => {
                    const key = `${phase}::${catId}`;
                    const t = cellMap.get(key);
                    if (!t) {
                      return (
                        <td
                          key={phase}
                          className="text-center px-2 py-2 border-b border-l border-ink-700/30 text-ink-700"
                        >
                          <span className="text-[14px]">·</span>
                        </td>
                      );
                    }
                    const isSelected = selectedKey === key;
                    const isChecked = checkedKeys.has(key);
                    const boost = extractBoost(t.priority_basis);
                    return (
                      <td
                        key={phase}
                        className={`text-center px-1 py-1.5 border-b border-l transition-all ${
                          isSelected
                            ? 'border-brand-teal/70 bg-brand-teal/15'
                            : 'border-ink-700/30 hover:bg-ink-900/60'
                        }`}
                      >
                        <button
                          onClick={() => onSelect(key, t)}
                          className={`w-full rounded-md border px-2 py-1.5 transition-all ${
                            isChecked
                              ? 'opacity-60 border-green-500/40 bg-green-500/5'
                              : priorityColor(t.priority)
                          }`}
                          title={`${t.category_name} — ${t.priority_basis}`}
                        >
                          <div className="flex items-center justify-center gap-1">
                            <span className="font-bold text-[11.5px]">P{t.priority}</span>
                            {boost > 0 && (
                              <span className="text-[9.5px] text-amber-300 font-semibold">↑+{boost}</span>
                            )}
                            {t.clue_relevant && (
                              <span
                                className="text-[9.5px] text-brand-teal font-semibold"
                                title="단서 루프 신호와 연관된 단계"
                              >
                                ●단서
                              </span>
                            )}
                            {isChecked && <span className="text-[10px] text-green-400"></span>}
                          </div>
                          <div className="text-[9.5px] opacity-80 mt-0.5">
                            {priorityLabel(t.priority)}
                          </div>
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onToggleCheck(key);
                          }}
                          className={`mt-1 text-[9.5px] transition-colors ${
                            isChecked
                              ? 'text-green-400'
                              : 'text-ink-500 hover:text-brand-teal'
                          }`}
                          title={isChecked ? '수집 완료 표시 해제' : '수집 완료로 표시'}
                        >
                          {isChecked ? ' 수집됨' : ' 수집 표시'}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-3 pt-2 border-t border-ink-700/40 text-[10.5px] text-ink-400 leading-5">
        <span className="inline-block w-3 h-3 rounded mr-1 bg-red-500/30 border border-red-500/50 align-middle" />{' '}
        P11+ 즉시 수집 ·
        <span className="inline-block w-3 h-3 rounded mr-1 ml-2 bg-amber-500/30 border border-amber-500/50 align-middle" />{' '}
        P8~10 우선 수집 ·
        <span className="inline-block w-3 h-3 rounded mr-1 ml-2 bg-brand-blue/20 border border-brand-blue/50 align-middle" />{' '}
        P7 이하 일반 수집 ·{' '}
        <span className="text-amber-300 font-semibold">↑+N</span> = Step2 환경 보정으로 우선순위 가산
      </div>
    </Card>
  );
};

//  환경 보정 카드 
const AppliedModifiersCard = ({ items }: { items: GuideV2AppliedModifier[] }) => {
  if (!items || items.length === 0) {
    return (
      <Card title={<> 환경 보정</>} className="mb-3">
        <p className="text-[11.5px] text-ink-400">
          Step2 시스템 환경 입력에 따라 추가 적용된 보정이 없습니다.
        </p>
      </Card>
    );
  }
  return (
    <Card
      title={<> 환경 보정 ({items.length}건 적용)</>}
      subtitle={
        <span className="text-[10.5px] text-ink-400">
          Step2 입력값이 가이드 우선순위에 어떻게 반영됐는지
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
              <Badge tone="blue" size="sm">{m.effect}</Badge>
              {m.category_id && (
                <span className="text-[11px] text-ink-300">
                  → <b>{m.category_id}</b>
                  {m.boost !== null && m.boost !== undefined && m.boost !== 0 && (
                    <span className="text-amber-400"> +{m.boost}</span>
                  )}
                </span>
              )}
              {m.kill_chain_phase && (
                <span className="text-[11px] text-ink-300">
                  → <b className="text-brand-purple">{m.kill_chain_phase}</b> 단계
                </span>
              )}
              <code className="text-[9.5px] text-ink-500 font-mono ml-auto">{m.id}</code>
            </div>
            <div className="text-ink-200">{m.reason}</div>
            {m.source && <div className="text-[10px] text-ink-500 mt-0.5"> {m.source}</div>}
          </div>
        ))}
      </div>
    </Card>
  );
};

//  환경 경고 카드 
const EnvWarningsCard = ({ items }: { items: GuideV2EnvWarning[] }) => {
  if (!items || items.length === 0) return null;
  return (
    <Card
      title={<span className="text-red-400"> 환경 경고 ({items.length})</span>}
      subtitle={
        <span className="text-[10.5px] text-ink-400">
          현재 환경에서 즉시 조치가 권장되는 항목 — 분석 신뢰성에 직접 영향
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
            <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
              <span className="inline-flex items-center justify-center min-w-[36px] h-5 rounded-md border border-red-500/40 bg-red-500/10 text-red-300 text-[10px] font-bold">
                P{w.priority}
              </span>
              <Badge tone="red" size="sm">필수</Badge>
              <span className="font-semibold text-ink-100">{w.category_name}</span>
            </div>
            <div className="text-ink-300 text-[11.5px]">{w.rationale}</div>
          </div>
        ))}
      </div>
    </Card>
  );
};

//  단서 루프 신호 카드 (Phase L)
const OBSERVABLE_TYPE_KO: Record<string, string> = {
  ip: 'IP',
  domain: '도메인',
  url: 'URL',
  hash: '해시',
  email: '이메일',
  username: '계정',
  cve: 'CVE',
  other: '기타',
};

// ATT&CK 기법 ID → MITRE 공식 기법 페이지 URL
// 기반기법 T1078 → /techniques/T1078/ , 서브기법 T1078.004 → /techniques/T1078/004/
const mitreTechniqueUrl = (tech: string): string | null => {
  const m = tech.match(/^T(\d{4})(?:\.(\d{3}))?$/);
  if (!m) return null;
  const base = `T${m[1]}`;
  return m[2]
    ? `https://attack.mitre.org/techniques/${base}/${m[2]}/`
    : `https://attack.mitre.org/techniques/${base}/`;
};

const ClueSignalsCard = ({ signals }: { signals: GuideV2ClueSignals | undefined }) => {
  if (!signals || !signals.has_signal) return null;
  const {
    signal_techniques,
    clue_techniques,
    evidenced_techniques,
    signal_tactics,
    boosted_category_ids,
    observable_summary,
  } = signals;
  const clueSet = new Set(clue_techniques);
  const logSet = new Set(evidenced_techniques);

  return (
    <Card
      title={<span className="text-brand-teal">단서 루프 신호 반영</span>}
      subtitle={
        <span className="text-[10.5px] text-ink-400">
          단서 루프가 확보한 ATT&CK 기법·Observable 로 아래 단계 카테고리 우선순위를 가산했습니다
          (수집 항목 자체는 표준 카탈로그 그대로)
        </span>
      }
      className="mb-3"
    >
      <div className="space-y-2.5">
        {observable_summary.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[10.5px] text-ink-400 font-semibold">확보 Observable</span>
            {observable_summary.map((o) => (
              <Badge key={o.type} tone="blue" size="sm">
                {OBSERVABLE_TYPE_KO[o.type] ?? o.type} {o.count}
              </Badge>
            ))}
          </div>
        )}

        {signal_tactics.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[10.5px] text-ink-400 font-semibold">우선순위 가산 단계</span>
            {signal_tactics.map((t) => (
              <Badge key={t} tone="teal" size="sm">{t}</Badge>
            ))}
            {boosted_category_ids.length > 0 && (
              <span className="text-[10px] text-ink-500">
                · 카테고리 {boosted_category_ids.length}종 부스트
              </span>
            )}
          </div>
        )}

        {signal_techniques.length > 0 && (
          <div>
            <span className="text-[10.5px] text-ink-400 font-semibold">확보 ATT&CK 기법</span>
            <div className="flex items-center gap-1 flex-wrap mt-1">
              {signal_techniques.map((tech) => {
                const fromClue = clueSet.has(tech);
                const fromLog = logSet.has(tech);
                const src = fromClue && fromLog ? '단서+로그' : fromClue ? '단서' : '로그';
                const url = mitreTechniqueUrl(tech);
                const chipClass =
                  'inline-flex items-center gap-0.5 text-[10px] font-mono px-1.5 py-0.5 rounded border border-brand-purple/40 bg-brand-purple/10 text-brand-purple';
                if (!url) {
                  return (
                    <code key={tech} className={chipClass} title={`출처: ${src}`}>
                      {tech}
                    </code>
                  );
                }
                return (
                  <a
                    key={tech}
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    className={`${chipClass} hover:bg-brand-purple/25 hover:border-brand-purple/70 transition-colors`}
                    title={`출처: ${src} · MITRE ATT&CK ${tech} 페이지 열기 ↗`}
                  >
                    {tech}
                    <span className="text-[8px] opacity-70">↗</span>
                  </a>
                );
              })}
            </div>
            <div className="text-[9.5px] text-ink-500 mt-1">
              출처 — <span className="text-brand-teal">단서</span>: 단서 루프 채택 ·{' '}
              <span className="text-ink-300">로그</span>: 업로드 로그 ATT&CK 매핑 · 기법 클릭 시 MITRE
              ATT&CK 페이지 ↗
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};

//  메인
const CHECKED_KEY_PREFIX = 'ai-sherpa-v2-collected:';
const VIEW_MODE_KEY = 'ai-sherpa-v2-view-mode';

// multi-type: 사고유형별 수집 진행을 분리 추적 (caseId:incidentType 네임스페이스).
const checkedStorageKey = (caseId: string, incidentType: string): string =>
  `${CHECKED_KEY_PREFIX}${caseId}:${incidentType}`;

const loadCheckedKeys = (caseId: string, incidentType: string): Set<string> => {
  try {
    const raw = localStorage.getItem(checkedStorageKey(caseId, incidentType));
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
};

const saveCheckedKeys = (
  caseId: string,
  incidentType: string,
  keys: Set<string>,
): void => {
  try {
    localStorage.setItem(
      checkedStorageKey(caseId, incidentType),
      JSON.stringify([...keys]),
    );
  } catch {
    // ignore
  }
};

type ViewMode = 'list' | 'matrix';

const loadViewMode = (): ViewMode => {
  try {
    return localStorage.getItem(VIEW_MODE_KEY) === 'matrix' ? 'matrix' : 'list';
  } catch {
    return 'list';
  }
};

const Step4GuideChecklistV2 = ({ onPrev, onComplete }: Step4V2Props) => {
  const caseId = useCaseStore((s) => s.caseId);
  const primaryType = useCaseStore((s) => s.incidentType);
  const secondaryTypes = useCaseStore((s) => s.secondaryIncidentTypes);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<GuideV2Target | null>(null);
  const [checkedKeys, setCheckedKeys] = useState<Set<string>>(new Set());
  const [viewMode, setViewMode] = useState<ViewMode>(loadViewMode);

  // 단서 루프에서 확정된 사고유형 목록 — primary(케이스 확정값) + secondary(부 가설).
  // 2개 이상이면 탭으로 각 사고유형별 독립 수집 가이드를 전환 제공.
  const typeList = (
    [primaryType, ...secondaryTypes].filter(Boolean) as IncidentType[]
  ).filter((t, i, arr) => arr.indexOf(t) === i);
  const isMulti = typeList.length >= 2;
  const [selectedType, setSelectedType] = useState<IncidentType | null>(
    typeList[0] ?? null,
  );
  // primary 가 비동기로 채워지거나 목록이 바뀌면 선택 보정.
  useEffect(() => {
    if (typeList.length === 0) return;
    if (!selectedType || !typeList.includes(selectedType)) {
      setSelectedType(typeList[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typeList.join('|')]);

  // primary 는 케이스에 확정 저장된 유형 → getGuideV2.
  // secondary 는 환경 보정 미리보기 → getGuidePreview(동일 GuideV2Response 형태).
  const activeType = selectedType ?? typeList[0] ?? null;
  const isPrimaryActive = !!activeType && activeType === primaryType;
  const guideQuery = useQuery({
    queryKey: ['guide-v2', caseId, activeType],
    queryFn: () =>
      isPrimaryActive
        ? getGuideV2(caseId!)
        : getGuidePreview(caseId!, activeType as IncidentType),
    enabled: !!caseId && !!activeType,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (caseId && activeType) setCheckedKeys(loadCheckedKeys(caseId, activeType));
  }, [caseId, activeType]);

  const switchView = (m: ViewMode) => {
    setViewMode(m);
    try {
      localStorage.setItem(VIEW_MODE_KEY, m);
    } catch {
      // ignore
    }
  };

  const handleSelectType = (t: IncidentType) => {
    if (t === activeType) return;
    setSelectedType(t);
    // 가이드가 바뀌므로 우측 KB 패널/선택 초기화.
    setSelectedKey(null);
    setSelectedTarget(null);
  };

  const handleSelect = (key: string, t: GuideV2Target) => {
    if (selectedKey === key) {
      setSelectedKey(null);
      setSelectedTarget(null);
    } else {
      setSelectedKey(key);
      setSelectedTarget(t);
    }
  };

  const handleToggleCheck = (key: string) => {
    setCheckedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      if (caseId && activeType) saveCheckedKeys(caseId, activeType, next);
      return next;
    });
  };

  if (!caseId) {
    return (
      <div className="panel p-6 text-[12.5px]">
        <p className="text-ink-300"> 케이스가 없습니다. 이전 단계에서 케이스를 먼저 생성해주세요.</p>
        <button onClick={onPrev} className="btn-ghost mt-3">← Step2 시스템 구성</button>
      </div>
    );
  }
  if (guideQuery.isLoading) {
    return (
      <div className="panel p-6 text-center text-ink-400 text-[12.5px]">
        v2 수집 가이드 생성 중… (GET /api/guide/v2)
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
        <button onClick={onPrev} className="btn-ghost mt-3">← Step2</button>
      </div>
    );
  }

  const guide = guideQuery.data;
  if (!guide) return null;

  const phaseEntries = Object.entries(guide.phases);
  const activePhases = new Set(phaseEntries.map(([p]) => p));
  const uniqueCategoryIds = new Set<string>();
  for (const [, p] of phaseEntries) for (const t of p.targets) uniqueCategoryIds.add(t.category_id);
  const totalTargets = uniqueCategoryIds.size;
  const checkedTotal = checkedKeys.size;
  const totalTargetSlots = phaseEntries.reduce((n, [, p]) => n + p.targets.length, 0);

  return (
    <div className="animate-fade-up">
      {/* 다중 사고유형 탭 — 단서 루프에서 2개 이상 확정 시 각 유형별 독립 가이드 전환 */}
      {isMulti && (
        <div className="panel p-3 mb-3">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="eyebrow">단서 루프 확정 사고유형 {typeList.length}종</span>
            <span className="text-[10.5px] text-ink-400">
              번호를 눌러 사고유형별 수집 가이드를 전환하세요 (각각 독립 진행)
            </span>
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {typeList.map((t, i) => {
              const active = t === activeType;
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() => handleSelectType(t)}
                  className={
                    active
                      ? 'flex items-center gap-1.5 px-3 py-1.5 rounded text-[11.5px] font-semibold bg-brand-teal text-ink-950 transition-colors'
                      : 'flex items-center gap-1.5 px-3 py-1.5 rounded text-[11.5px] text-ink-300 border border-ink-700 hover:border-ink-500 hover:text-ink-100 transition-colors'
                  }
                  title={`${INCIDENT_TYPE_KO[t] ?? t} 수집 가이드 보기`}
                >
                  <span
                    className={
                      active
                        ? 'inline-flex items-center justify-center w-4 h-4 rounded-full bg-ink-950/30 text-[10px] font-bold'
                        : 'inline-flex items-center justify-center w-4 h-4 rounded-full bg-ink-800 text-[10px] font-bold'
                    }
                  >
                    {i + 1}
                  </span>
                  {INCIDENT_TYPE_KO[t] ?? t}
                  {t === primaryType && (
                    <span
                      className={
                        active ? 'text-[9px] opacity-80' : 'text-[9px] text-brand-teal'
                      }
                    >
                      주
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 헤더 */}
      <div className="panel p-4 border-l-[3px] border-l-brand-teal mb-3">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className="eyebrow">v2 수집 가이드 (외부 표준 6종 기반)</span>
          <Badge tone="purple">{guide.incidentType}</Badge>
          <span className="text-[11px] text-ink-400">
            {INCIDENT_TYPE_KO[guide.incidentType] ?? ''}
          </span>
          <Badge tone="blue" size="sm">{guide.csp.toUpperCase()}</Badge>
          <span className="ml-auto text-[10.5px] text-ink-500 font-mono">
            caseId: {guide.caseId.slice(0, 8)}…
          </span>
        </div>
        <div className="text-[11.5px] text-ink-300 leading-6">
          Kill Chain <b className="text-ink-100">{phaseEntries.length}</b>단계 ·{' '}
          <b className="text-ink-100">{totalTargets}</b>개 고유 카테고리 ·{' '}
          <b className={checkedTotal === totalTargetSlots ? 'text-green-400' : 'text-amber-300'}>
            {checkedTotal}/{totalTargetSlots}
          </b>{' '}
          수집 완료
          {guide.environment_warnings.length > 0 && (
            <>
              {' '}· <span className="text-red-400"> 환경 경고 {guide.environment_warnings.length}건</span>
            </>
          )}
        </div>

        {/* 뷰 토글 */}
        <div className="flex items-center gap-1.5 mt-2.5 pt-2.5 border-t border-ink-700/40">
          <span className="text-[10.5px] text-ink-400">표시 방식</span>
          <button
            onClick={() => switchView('list')}
            className={viewMode === 'list' ? 'btn-primary btn-sm' : 'btn-ghost btn-sm'}
          >
             리스트
          </button>
          <button
            onClick={() => switchView('matrix')}
            className={viewMode === 'matrix' ? 'btn-primary btn-sm' : 'btn-ghost btn-sm'}
            title="MITRE ATT&CK 매트릭스 형태로 한눈에 시각화"
          >
             매트릭스
          </button>
          <span className="ml-auto text-[10px] text-ink-500">
            {viewMode === 'matrix'
              ? '셀 = 카테고리 × Kill Chain 단계 매칭. 빈 칸은 적용 안 됨'
              : 'Phase 별 카드. 항목 클릭 시 우측 KB 펼침'}
          </span>
        </div>
      </div>

      {/* 단서 루프 신호 반영 (Phase L) — 신호가 있을 때만 노출 */}
      <ClueSignalsCard signals={guide.clue_signals} />

      {/* Kill Chain 안내 (접이식) */}
      <PhaseInfoBanner activePhases={activePhases} />

      {/* 환경 경고 */}
      <EnvWarningsCard items={guide.environment_warnings} />

      {/* 좌우 분할 */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_minmax(380px,440px)] gap-4">
        <div className="min-w-0">
          {phaseEntries.length === 0 ? (
            <div className="panel p-6 text-center text-ink-400 text-[12px]">
              매칭되는 Kill Chain 단계가 없습니다. 사고유형 설정을 확인해주세요.
            </div>
          ) : viewMode === 'matrix' ? (
            <MatrixView
              phases={phaseEntries}
              selectedKey={selectedKey}
              checkedKeys={checkedKeys}
              onSelect={handleSelect}
              onToggleCheck={handleToggleCheck}
            />
          ) : (
            phaseEntries.map(([phase, data]) => (
              <PhaseCard
                key={phase}
                phase={phase}
                data={data}
                primaryCsp={guide.csp}
                selectedKey={selectedKey}
                checkedKeys={checkedKeys}
                onSelect={handleSelect}
                onToggleCheck={handleToggleCheck}
              />
            ))
          )}

          <AppliedModifiersCard items={guide.applied_modifiers} />
        </div>

        <div className="min-w-0">
          <KbPanel
            target={selectedTarget}
            primaryCsp={guide.csp}
            onClose={() => {
              setSelectedKey(null);
              setSelectedTarget(null);
            }}
          />
        </div>
      </div>

      <div className="flex justify-between mt-4">
        <button onClick={onPrev} className="btn-ghost">← Step2</button>
        <button onClick={onComplete} className="btn-primary">V-2 로그 수집 진행 →</button>
      </div>
    </div>
  );
};

export default Step4GuideChecklistV2;
