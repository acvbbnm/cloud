import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import Card from '@/components/Card';
import KpiCard from '@/components/KpiCard';
import Badge from '@/components/Badge';
import { useToastStore } from '@/stores/useToastStore';
import { useBoardStore } from '@/stores/useBoardStore';

import DropZone from './DropZone';
import EventPreviewTable from './EventPreviewTable';
import type { PreviewEvent } from './EventPreviewTable';

interface SourceStat {
  name: string;
  count: number;
  status: 'ok' | 'pending' | 'missing';
}

const initialEvents: PreviewEvent[] = [
  { id: 1, ts: '2026-03-25 02:34:18', ev: 'consoleSignIn', ip: '203.0.113.45', user: 'admin-user', csp: 'NCP', highlighted: true },
  { id: 2, ts: '2026-03-25 14:32:07', ev: 'changeSubAccountLoginId', ip: '203.0.113.45', user: 'admin-user', csp: 'NCP', highlighted: true },
  { id: 3, ts: '2026-03-25 14:33:15', ev: 'addSubAccountRole', ip: '203.0.113.45', user: 'admin-user', csp: 'NCP', highlighted: true },
  { id: 4, ts: '2026-03-25 14:35:42', ev: 'putBucketPolicy', ip: '203.0.113.45', user: 'svc-admin-prod', csp: 'NCP', highlighted: true },
  { id: 5, ts: '2026-03-25 14:38:55', ev: 'getObject (x142)', ip: '203.0.113.45', user: 'svc-admin-prod', csp: 'NCP', highlighted: true },
];

const initialSources: SourceStat[] = [
  { name: 'Activity Tracer', count: 8421, status: 'ok' },
  { name: 'Sub Account Log', count: 4102, status: 'ok' },
  { name: 'Object Storage Log', count: 2309, status: 'ok' },
  { name: 'VPC Flow Log', count: 0, status: 'missing' },
  { name: 'Cloud Advisor', count: 0, status: 'pending' },
];

const V2Logs = () => {
  const navigate = useNavigate();
  const showToast = useToastStore((s) => s.show);
  const addLogs = useBoardStore((s) => s.addLogs);

  const [events, setEvents] = useState<PreviewEvent[]>(initialEvents);
  const [sources, setSources] = useState<SourceStat[]>(initialSources);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const totalEvents = useMemo(
    () => sources.reduce((acc, s) => acc + s.count, 0) + 14832 - sources.reduce((a, s) => a + (s.count > 0 ? 0 : 0), 0),
    [sources],
  );
  const sourceCount = useMemo(() => sources.filter((s) => s.count > 0).length, [sources]);
  const gapCount = useMemo(() => sources.filter((s) => s.status !== 'ok').length, [sources]);

  const handleUpload = (files: File[]) => {
    let nextId = events.length + 100;
    const newSources: SourceStat[] = [...sources];
    const newEvents: PreviewEvent[] = [...events];

    files.forEach((file) => {
      const synthetic = Math.floor(Math.random() * 800) + 200;
      newSources.push({ name: file.name.slice(0, 26), count: synthetic, status: 'ok' });
      newEvents.push({
        id: ++nextId,
        ts: new Date().toISOString().replace('T', ' ').slice(0, 19),
        ev: 'uploadedEvent',
        ip: '203.0.113.45',
        user: 'uploaded-user',
        csp: 'UPLOAD',
      });
    });

    setSources(newSources);
    setEvents(newEvents);
    showToast(`${files.length}개 파일 로드 완료`);
  };

  const toggleOne = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = (checked: boolean) => {
    setSelected(checked ? new Set(events.map((e) => e.id)) : new Set());
  };

  const handleAddToBoard = () => {
    if (!selected.size) {
      showToast('선택된 로그가 없습니다');
      return;
    }
    const picked = events.filter((e) => selected.has(e.id));
    addLogs(picked.map((p) => ({ ts: p.ts, ev: p.ev, ip: p.ip, user: p.user, csp: p.csp })));
    showToast(`${picked.length}개 로그 수사 보드에 추가됨`);
    setSelected(new Set());
    navigate('/board');
  };

  return (
    <div>
      <PageHeader
        eyebrow="Layer 1 · M1-1"
        title="로그 수집"
        description="CSP 로그 파일을 업로드하면 이벤트 무결성(SHA-256)을 검증하고 OCSF 정규화 단계로 넘길 수 있습니다."
        actions={
          <>
            <button onClick={handleAddToBoard} className="btn-ghost">
              📌 수사 보드에 추가
            </button>
            <button onClick={() => navigate('/ocsf')} className="btn-primary">
              OCSF 정규화 →
            </button>
          </>
        }
      />

      <PageBody className="flex flex-col gap-6 animate-fade-up">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <KpiCard label="총 수집 이벤트" value={totalEvents.toLocaleString()} color="blue" hint="누적 정규화 대상" />
          <KpiCard label="수집 소스" value={sourceCount} color="teal" hint="활성 로그 소스" />
          <KpiCard label="분석 기간" value="5일" color="amber" hint="2026-03-20 ~ 03-25" />
          <KpiCard label="수집 갭" value={gapCount} color="red" hint="REQUIRED 미수집" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          <div className="lg:col-span-3">
            <DropZone onUpload={handleUpload} />
          </div>
          <Card title={<>✅ 수집 현황</>} className="lg:col-span-2">
            {sources.map((s) => (
              <div
                key={s.name}
                className={`flex justify-between items-center py-2.5 border-b border-ink-700/30 last:border-b-0 text-[12.5px] ${
                  s.status === 'ok' ? '' : 'opacity-65'
                }`}
              >
                <span>{s.name}</span>
                {s.status === 'ok' ? (
                  <Badge tone="teal">{s.count.toLocaleString()}건</Badge>
                ) : s.status === 'missing' ? (
                  <Badge tone="red">미수집</Badge>
                ) : (
                  <Badge tone="amber">대기 중</Badge>
                )}
              </div>
            ))}
          </Card>
        </div>

        <Card
          title={<>📋 수집 이벤트 미리보기</>}
          subtitle="체크 후 ‘수사 보드에 추가’ 버튼으로 보드로 보낼 수 있습니다"
          action={
            <span className="chip text-[11px]">
              <span className="text-brand-teal">{selected.size}</span>
              <span className="text-ink-400">/ {events.length} 선택</span>
            </span>
          }
        >
          <EventPreviewTable
            events={events}
            selected={selected}
            onToggle={toggleOne}
            onToggleAll={toggleAll}
          />
        </Card>
      </PageBody>
    </div>
  );
};

export default V2Logs;
