import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import KpiCard from '@/components/KpiCard';
import { useToastStore } from '@/stores/useToastStore';

import RawJsonPanel from './RawJsonPanel';
import FieldMappingTable from './FieldMappingTable';
import type { MappingRow } from './FieldMappingTable';

interface SampleEvent {
  id: string;
  label: string;
  raw: Record<string, unknown>;
  ocsf: Record<string, unknown>;
}

const samples: SampleEvent[] = [
  {
    id: 'NCL-8821',
    label: 'changeSubAccountLoginId — 14:32:07',
    raw: {
      eventId: 'NCL-8821',
      eventName: 'changeSubAccountLoginId',
      eventTime: '2026-03-25T14:32:07+09:00',
      userIp: '203.0.113.45',
      userName: 'admin-user',
      subAccountId: 'svc-backup',
      actionResult: 'success',
      regionCode: 'KR',
    },
    ocsf: {
      class_uid: 3001,
      class_name: 'Account Change',
      activity_id: 3,
      time: 1711342327000,
      severity_id: 4,
      status: 'Success',
      actor: { user: { name: 'admin-user' }, session: { ip: '203.0.113.45' } },
      cloud: { provider: 'Naver Cloud', region: 'KR' },
    },
  },
  {
    id: 'NCL-8830',
    label: 'addSubAccountRole — 14:33:15',
    raw: {
      eventId: 'NCL-8830',
      eventName: 'addSubAccountRole',
      eventTime: '2026-03-25T14:33:15+09:00',
      userIp: '203.0.113.45',
      userName: 'admin-user',
      role: 'NCP_ADMIN',
      actionResult: 'success',
    },
    ocsf: {
      class_uid: 3001,
      class_name: 'Account Change',
      activity_id: 5,
      time: 1711342395000,
      severity_id: 5,
      status: 'Success',
      actor: { user: { name: 'admin-user' }, session: { ip: '203.0.113.45' } },
      assigned_role: 'NCP_ADMIN',
    },
  },
  {
    id: 'NCL-9020',
    label: 'consoleSignIn — 02:34:18',
    raw: {
      eventId: 'NCL-9020',
      eventName: 'consoleSignIn',
      eventTime: '2026-03-25T02:34:18+09:00',
      userIp: '203.0.113.45',
      userName: 'admin-user',
      mfa: false,
      actionResult: 'success',
    },
    ocsf: {
      class_uid: 3002,
      class_name: 'Authentication',
      activity_id: 1,
      time: 1711301658000,
      severity_id: 3,
      status: 'Success',
      actor: { user: { name: 'admin-user' }, session: { ip: '203.0.113.45' } },
      mfa: false,
    },
  },
];

const mappings: MappingRow[] = [
  { source: 'eventName', target: 'activity_name', rule: '매핑 테이블' },
  { source: 'eventTime', target: 'time', rule: 'ISO → epoch ms' },
  { source: 'userIp', target: 'actor.session.ip', rule: '직접 매핑' },
  { source: 'userName', target: 'actor.user.name', rule: '직접 매핑' },
  { source: 'actionResult', target: 'status', rule: '값 변환' },
  { source: 'regionCode', target: 'cloud.region', rule: '직접 매핑' },
];

const V3OCSF = () => {
  const navigate = useNavigate();
  const showToast = useToastStore((s) => s.show);
  const [selected, setSelected] = useState(0);
  const sample = samples[selected];

  return (
    <div>
      <PageHeader
        eyebrow="Layer 2 · M2-1"
        title={
          <>
            OCSF <span className="grad-text">정규화</span>
          </>
        }
        description="원본 CSP 로그를 OCSF 1.3 표준 스키마로 변환합니다. 좌·우 패널에서 변환 전후를 비교하고 매핑 규칙을 점검하세요."
        actions={
          <button
            onClick={() => {
              showToast('→ 갭 감지 진행');
              navigate('/gap');
            }}
            className="btn-primary"
          >
            갭 감지 →
          </button>
        }
      />

      <PageBody className="flex flex-col gap-6 animate-fade-up">
        <div className="grid grid-cols-3 gap-3">
          <KpiCard label="정규화율" value="100%" color="teal" hint="전체 이벤트 매핑 성공" />
          <KpiCard label="정규화 완료" value="14,832" color="blue" hint="OCSF 1.3 변환" />
          <KpiCard label="스키마 버전" value="OCSF 1.3" color="purple" hint="2024-04 릴리스" />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="eyebrow">샘플 이벤트</span>
          {samples.map((s, i) => (
            <button
              key={s.id}
              onClick={() => setSelected(i)}
              className={`px-3 py-1.5 rounded-full text-[12px] font-semibold border transition-all ${
                selected === i
                  ? 'bg-brand-blue/15 border-brand-blue/50 text-brand-blue'
                  : 'bg-ink-900 border-ink-700 text-ink-300 hover:text-ink-100'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <RawJsonPanel title="원본 CSP 로그" titleColor="#FF4D6D" badge="RAW" data={sample.raw} />
          <RawJsonPanel title="OCSF 정규화 결과" titleColor="#14D9B0" badge="OCSF 1.3" data={sample.ocsf} />
        </div>

        <FieldMappingTable mappings={mappings} />
      </PageBody>
    </div>
  );
};

export default V3OCSF;
