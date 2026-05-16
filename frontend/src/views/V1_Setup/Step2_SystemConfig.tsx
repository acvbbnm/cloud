import { useState } from 'react';

import { CSP_META, TYPE_META } from './meta';

interface SystemConfig {
  severity: string;
  occurred_at: string;
  vpc_id: string;
  region: string;
  services: string[];
  network: string;
  publicIp: string;
  auditEnabled: string;
  scope: string;
  // dev2 v2 가이드 보강 — environment_modifiers.json m-004~m-011 트리거 필드
  mfa_status: string;
  iam_account_count: number;
  audit_log_retention_days: number;
  data_sensitivity: string;
  sso_enabled: string;
  multi_cloud: string;
}

interface Step2Props {
  csp: string | null;
  incidentType: string | null;
  onPrev: () => void;
  onSubmit: (config: SystemConfig) => void;
  isSubmitting?: boolean;
}

type TabKey = 'basic' | 'system' | 'csp' | 'security' | 'scope';

const TABS: { id: TabKey; label: string }[] = [
  { id: 'basic', label: '🗂 사고 기본' },
  { id: 'system', label: '🖥 시스템 공통' },
  { id: 'csp', label: '☁ CSP 특화' },
  { id: 'security', label: '🛡 보안 정책' },
  { id: 'scope', label: '🎯 영향 범위' },
];

const sevOptions = [
  { id: 'critical', label: '🔴 Critical' },
  { id: 'high', label: '🟠 High' },
  { id: 'medium', label: '🟡 Medium' },
  { id: 'low', label: '🟢 Low' },
];

const Step2_SystemConfig = ({ csp, incidentType, onPrev, onSubmit, isSubmitting }: Step2Props) => {
  const cspKey = (csp ?? 'naver') as 'naver' | 'nhn' | 'all';
  const cspMeta = CSP_META[cspKey] ?? CSP_META.naver;
  const typeMeta = incidentType ? TYPE_META[incidentType] : null;
  const isNhn = cspKey === 'nhn';
  const isAll = cspKey === 'all';

  const [tab, setTab] = useState<TabKey>('basic');
  const [severity, setSeverity] = useState('critical');
  const [occurredAt, setOccurredAt] = useState('2026-03-25T14:32');
  const [investigator, setInvestigator] = useState('홍길동');
  const [memo, setMemo] = useState('');
  const [vpcId, setVpcId] = useState('vpc-prod-01');
  const [region, setRegion] = useState('KR (한국)');
  const [services, setServices] = useState<string[]>([]);
  const [network, setNetwork] = useState('VPC + Security Group 적용');
  const [publicIp, setPublicIp] = useState('있음 (LB 경유)');
  const [auditEnabled, setAuditEnabled] = useState('활성화 (정상 수집 중)');
  const [scope, setScope] = useState('admin-user, svc-backup');
  // dev2 v2 가이드 — environment_modifiers.json 트리거 필드
  const [mfaStatus, setMfaStatus] = useState('적용');
  const [iamAccountCount, setIamAccountCount] = useState<number>(12);
  const [auditLogRetentionDays, setAuditLogRetentionDays] = useState<number>(90);
  const [dataSensitivity, setDataSensitivity] = useState('없음');
  const [ssoEnabled, setSsoEnabled] = useState('없음');

  const toggleSvc = (s: string) => {
    setServices((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  };

  const handleSubmit = () => {
    onSubmit({
      severity,
      occurred_at: occurredAt,
      vpc_id: vpcId,
      region,
      services,
      network,
      publicIp,
      auditEnabled,
      scope,
      mfa_status: mfaStatus,
      iam_account_count: iamAccountCount,
      audit_log_retention_days: auditLogRetentionDays,
      data_sensitivity: dataSensitivity,
      sso_enabled: ssoEnabled,
      // csp='all' 선택 시 자동으로 멀티 클라우드 환경으로 인식 (m-010 트리거)
      multi_cloud: isAll ? '있음 (NCP + NHN 동시 사용)' : '없음',
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="h-section">시스템 구성 정보</h2>
        <p className="text-[13px] text-ink-400 mt-1.5 max-w-2xl">
          인프라 구성과 사고 범위를 입력하세요. 다음 단계의 수집 가이드 자동 생성에 활용됩니다.
        </p>
      </div>

      <div className="panel p-4 flex flex-wrap items-center gap-3 border-l-[3px] border-l-brand-blue">
        <div className="flex items-center gap-1.5">
          <span className="eyebrow">CSP</span>
          <span className="font-semibold text-[13px]" style={{ color: cspMeta.color }}>
            {cspMeta.label}
          </span>
        </div>
        <span className="divider w-px h-4 bg-ink-700" />
        <div className="flex items-center gap-1.5">
          <span className="eyebrow">사고유형</span>
          <span className="font-semibold text-[13px]" style={{ color: typeMeta?.sevColor ?? '#FBB13B' }}>
            {typeMeta?.label ?? '—'}
          </span>
        </div>
        <span className="divider w-px h-4 bg-ink-700" />
        <div className="flex items-center gap-1.5">
          <span className="eyebrow">핵심 서비스</span>
          <span className="text-brand-teal font-semibold text-[12px]">
            {typeMeta?.services[cspKey].slice(0, 2).join(' · ') ?? '—'}
          </span>
        </div>
      </div>

      <div className="flex gap-1 border-b border-ink-700/70">
        {TABS.map((t) => {
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`relative px-4 py-2.5 text-[13px] -mb-px transition-colors ${
                active ? 'text-ink-100 font-semibold' : 'text-ink-400 hover:text-ink-100'
              }`}
            >
              {t.label}
              {active && (
                <span className="absolute -bottom-px left-3 right-3 h-[2px] bg-cta-gradient rounded-full" />
              )}
            </button>
          );
        })}
      </div>

      <div className="panel p-6 animate-fade-up">
        {tab === 'basic' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="사고 인지 일시">
              <input
                type="datetime-local"
                value={occurredAt}
                onChange={(e) => setOccurredAt(e.target.value)}
                className="input"
              />
            </Field>
            <Field label="담당 수사관">
              <input value={investigator} onChange={(e) => setInvestigator(e.target.value)} className="input" />
            </Field>
            <Field label="사고 심각도">
              <div className="flex flex-wrap gap-1.5">
                {sevOptions.map((s) => {
                  const sel = severity === s.id;
                  return (
                    <button
                      key={s.id}
                      onClick={() => setSeverity(s.id)}
                      className={`px-3 py-1.5 rounded-full text-[12px] font-semibold border transition-all ${
                        sel
                          ? 'bg-brand-blue/15 border-brand-blue/50 text-brand-blue'
                          : 'bg-ink-900 border-ink-700 text-ink-300 hover:text-ink-100'
                      }`}
                    >
                      {s.label}
                    </button>
                  );
                })}
              </div>
            </Field>
            <Field label="탐지 / 신고 경로">
              <select className="input">
                <option>SIEM 알럿</option>
                <option>내부 직원 신고</option>
                <option>외부 제보</option>
                <option>자동 모니터링</option>
                <option>클라우드 보안 알림</option>
              </select>
            </Field>
            <Field label="사고 초기 메모" full>
              <textarea
                rows={2}
                value={memo}
                onChange={(e) => setMemo(e.target.value)}
                placeholder="사고 초기 상황, 특이사항 등..."
                className="input resize-y"
              />
            </Field>
          </div>
        )}

        {tab === 'system' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="OS 종류">
              <select className="input">
                <option>CentOS 7</option>
                <option>RHEL 8/9</option>
                <option>Ubuntu 22.04</option>
                <option>Debian</option>
                <option>Windows Server 2022</option>
              </select>
            </Field>
            <Field label="서버 역할">
              <select className="input">
                <option>웹서버 (Web)</option>
                <option>WAS (Application)</option>
                <option>DB 서버</option>
                <option>파일 서버</option>
                <option>배치/스케줄러</option>
              </select>
            </Field>
            <Field label="VPC ID">
              <input value={vpcId} onChange={(e) => setVpcId(e.target.value)} className="input" />
            </Field>
            <Field label="총 서버 / VM 수">
              <input type="number" defaultValue={12} className="input" />
            </Field>
          </div>
        )}

        {tab === 'csp' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2 pb-2 mb-1 border-b border-ink-700/60">
              <span className="eyebrow" style={{ color: cspMeta.color }}>
                ☁ {cspMeta.label} 특화 정보
              </span>
            </div>
            {!isAll ? (
              <>
                <Field label={isNhn ? 'VPC / Security Group' : 'VPC 구성 / ACG'}>
                  <select value={network} onChange={(e) => setNetwork(e.target.value)} className="input">
                    {(isNhn
                      ? ['VPC + Security Group 적용', 'Security Group만 적용', '기본 네트워크']
                      : ['VPC + ACG + NACL 모두 적용', 'VPC + ACG만 적용', 'Classic 환경']
                    ).map((o) => (
                      <option key={o}>{o}</option>
                    ))}
                  </select>
                </Field>
                <Field label="공인 IP 보유">
                  <select value={publicIp} onChange={(e) => setPublicIp(e.target.value)} className="input">
                    <option>있음 (서버 직접 할당)</option>
                    <option>있음 (LB 경유)</option>
                    <option>없음 (사설 IP만)</option>
                  </select>
                </Field>
                <Field label="영향 리전">
                  <select value={region} onChange={(e) => setRegion(e.target.value)} className="input">
                    <option>KR (한국)</option>
                    <option>JP (일본)</option>
                    {!isNhn && <option>SG (싱가포르)</option>}
                    <option>US (미국)</option>
                    <option>복수 리전</option>
                  </select>
                </Field>
                <Field
                  label={
                    <span className="flex items-center gap-1.5">
                      {isNhn ? 'CloudTrail' : 'Activity Tracer'} 활성화
                      <span className="tag-red text-[10px]">필수 확인</span>
                    </span>
                  }
                >
                  <select value={auditEnabled} onChange={(e) => setAuditEnabled(e.target.value)} className="input">
                    <option>활성화 (정상 수집 중)</option>
                    <option>활성화 (부분 수집)</option>
                    <option>비활성화</option>
                    <option>미확인</option>
                  </select>
                </Field>
              </>
            ) : (
              <>
                <Field label="CSP 간 연결 방식">
                  <select className="input">
                    <option>VPN Gateway</option>
                    <option>Direct Connect</option>
                    <option>퍼블릭 인터넷</option>
                  </select>
                </Field>
                <Field label="크로스 CSP 로그 통합">
                  <select className="input">
                    <option>있음 (SIEM 통합)</option>
                    <option>일부 통합</option>
                    <option>없음</option>
                  </select>
                </Field>
              </>
            )}

            <Field label="사용 중인 서비스" full>
              <div className="flex flex-wrap gap-1.5">
                {cspMeta.services.map((s) => {
                  const checked = services.includes(s);
                  return (
                    <label
                      key={s}
                      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11.5px] cursor-pointer border transition-all ${
                        checked
                          ? 'bg-brand-blue/15 border-brand-blue/50 text-brand-blue'
                          : 'bg-ink-900 border-ink-700 text-ink-300 hover:text-ink-100'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleSvc(s)}
                        className="accent-brand-blue"
                      />
                      {s}
                    </label>
                  );
                })}
              </div>
            </Field>
          </div>
        )}

        {tab === 'security' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2 pb-2 mb-1 border-b border-ink-700/60 flex items-center gap-2 flex-wrap">
              <span className="eyebrow text-brand-teal">🛡 보안 정책 (V2 가이드 환경 보정)</span>
              <span className="text-[10.5px] text-ink-400">
                입력값이 수집 가이드 V2 의 우선순위·추가 항목에 즉시 반영됩니다 (KISA §2.4 + NIST SP 800-86 §3 기반).
              </span>
            </div>

            <Field
              label={
                <span className="flex items-center gap-1.5">
                  MFA (다중 인증) 적용 현황
                  <span className="tag-red text-[10px]">필수 확인</span>
                </span>
              }
            >
              <select value={mfaStatus} onChange={(e) => setMfaStatus(e.target.value)} className="input">
                <option>적용</option>
                <option>부분 적용</option>
                <option>미적용</option>
                <option>미확인</option>
              </select>
              <p className="text-[10.5px] text-ink-400 mt-1">
                • 미적용 → 1.5.1 인증 + 1.5.4 실패 인증 priority +2 (CSA #2 IAM)
                <br />• 부분 적용 → 1.5.1 priority +1
              </p>
            </Field>

            <Field label="SSO (외부 IdP 연동)">
              <select value={ssoEnabled} onChange={(e) => setSsoEnabled(e.target.value)} className="input">
                <option>없음</option>
                <option>있음 (외부 IdP 연동)</option>
                <option>미확인</option>
              </select>
              <p className="text-[10.5px] text-ink-400 mt-1">
                • 있음 → 1.5.5 API 액세스 + 1.5.7 위험 기반 검색 priority +1
              </p>
            </Field>

            <Field label="IAM 사용자 계정 수 (대략)">
              <input
                type="number"
                min={0}
                value={iamAccountCount}
                onChange={(e) => setIamAccountCount(Number(e.target.value) || 0)}
                className="input"
              />
              <p className="text-[10.5px] text-ink-400 mt-1">
                • 50명 이상 → 1.5.2 권한 + 1.5.3 계정 생성 priority +1 (대규모 환경 노이즈)
              </p>
            </Field>

            <Field
              label={
                <span className="flex items-center gap-1.5">
                  감사 로그 보존 기간 (일)
                  <span className="tag-yellow text-[10px]">휘발성</span>
                </span>
              }
            >
              <input
                type="number"
                min={0}
                value={auditLogRetentionDays}
                onChange={(e) => setAuditLogRetentionDays(Number(e.target.value) || 0)}
                className="input"
              />
              <p className="text-[10.5px] text-ink-400 mt-1">
                • 90일 미만 → ⚠️ CT-RETENTION-WARNING 항목 추가 (NIST SP 800-86 §3.1 휘발성)
              </p>
            </Field>

            <Field label="민감 데이터 보유" full>
              <select
                value={dataSensitivity}
                onChange={(e) => setDataSensitivity(e.target.value)}
                className="input"
              >
                <option>없음</option>
                <option>있음 (개인정보·민감정보)</option>
                <option>미확인</option>
              </select>
              <p className="text-[10.5px] text-ink-400 mt-1">
                • 있음 → 1.4 파일 스토리지 priority +2, 1.7 로깅 메타 +1 (CSA #7 Accidental Disclosure)
              </p>
            </Field>

            {isAll && (
              <div className="md:col-span-2 panel p-3 border-l-[3px] border-l-brand-teal text-[11.5px]">
                <span className="eyebrow text-brand-teal">자동 인식</span>{' '}
                CSP 전체(naver + nhn) 선택 — <strong>멀티 클라우드 환경</strong>으로 분류되어 1.5.5 API 액세스 + Lateral Movement 단계 priority +2 가 적용됩니다 (m-010).
              </div>
            )}
          </div>
        )}

        {tab === 'scope' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="영향 계정">
              <input value={scope} onChange={(e) => setScope(e.target.value)} className="input" placeholder="쉼표로 구분" />
            </Field>
            <Field label="영향 VPC / 서브넷">
              <input defaultValue="vpc-prod-01 / 172.16.0.0/24" className="input" />
            </Field>
            <Field label="영향 서비스 및 리소스" full>
              <input
                defaultValue="Object Storage (bucket-finance-2026), Sub Account IAM"
                className="input"
              />
            </Field>
          </div>
        )}
      </div>

      <div className="flex justify-between gap-2">
        <button onClick={onPrev} className="btn-ghost">
          ← 이전
        </button>
        <button onClick={handleSubmit} className="btn-primary disabled:opacity-50" disabled={isSubmitting}>
          {isSubmitting ? '생성 중…' : '다음: 수집 가이드 →'}
        </button>
      </div>
    </div>
  );
};

const Field = ({
  label,
  children,
  full,
}: {
  label: React.ReactNode;
  children: React.ReactNode;
  full?: boolean;
}) => (
  <div className={full ? 'md:col-span-2' : ''}>
    <label className="block text-[11.5px] text-ink-300 mb-1.5 font-medium">{label}</label>
    {children}
  </div>
);

export default Step2_SystemConfig;
