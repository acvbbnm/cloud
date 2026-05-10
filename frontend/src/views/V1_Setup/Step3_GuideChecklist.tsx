import { useMemo, useState } from 'react';

import Card from '@/components/Card';
import Badge from '@/components/Badge';
import { useToastStore } from '@/stores/useToastStore';

import { CSP_META, TYPE_META, buildGuide } from './meta';
import type { CollectionItem } from './meta';

interface Step3Props {
  csp: string | null;
  incidentType: string | null;
  onPrev: () => void;
  onComplete: () => void;
}

const layerStyle: Record<CollectionItem['layer'], { icon: string; cls: string; label: string }> = {
  cloud: { icon: '☁', cls: 'bg-brand-blue/15 text-brand-blue ring-brand-blue/20', label: 'Cloud' },
  server: { icon: '🖥', cls: 'bg-brand-teal/15 text-brand-teal ring-brand-teal/20', label: 'Server' },
  network: { icon: '🔗', cls: 'bg-brand-purple/15 text-brand-purple ring-brand-purple/20', label: 'Network' },
  app: { icon: '📱', cls: 'bg-brand-amber/15 text-brand-amber ring-brand-amber/20', label: 'App' },
};

const priorityMeta: Record<number, { label: string; sub: string; color: string }> = {
  1: { label: 'P1 — 즉시 수집', sub: '휘발성, 시간 경과 시 소멸', color: '#FF4D6D' },
  2: { label: 'P2 — 긴급 수집', sub: '로그 로테이션 / 보존 기간 제한', color: '#FF8A4C' },
  3: { label: 'P3 — 일반 수집', sub: 'CSP 보존, 상대적으로 안전', color: '#3D7BFF' },
  4: { label: 'P4 — 환경 정보', sub: '변하지 않는 정적 정보', color: '#7C8497' },
};

const ItemRow = ({ item, checked, onToggle }: { item: CollectionItem; checked: boolean; onToggle: () => void }) => {
  const showToast = useToastStore((s) => s.show);
  const layer = layerStyle[item.layer];
  return (
    <div className="bg-ink-900/60 border border-ink-700/70 rounded-xl p-3.5 mb-2 hover:border-brand-blue/40 hover:bg-ink-900 transition-all">
      <div className="flex items-start gap-2.5">
        <button
          onClick={onToggle}
          className={`w-4 h-4 rounded border-2 shrink-0 mt-0.5 transition-colors ${
            checked ? 'bg-brand-teal border-brand-teal' : 'border-ink-500 hover:border-brand-blue'
          }`}
          title="수집 완료 표시"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="font-semibold text-[13px] truncate">{item.name}</div>
            <div className="flex gap-1 shrink-0">
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ring-1 ${layer.cls}`}>
                {layer.icon} {layer.label}
              </span>
              {item.auto ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-brand-teal/15 text-brand-teal ring-1 ring-brand-teal/25">
                  ⚡ AUTO
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-ink-800 text-ink-400 ring-1 ring-ink-700">
                  👤 수동
                </span>
              )}
            </div>
          </div>
          <div className="text-[11.5px] text-ink-400 leading-6">{item.hint}</div>
          <div className="text-[10.5px] mt-1 text-ink-400">⏱ {item.retention}</div>
          {item.cmd && (
            <button
              onClick={() => {
                navigator.clipboard?.writeText(item.cmd ?? '');
                showToast('커맨드 복사됨');
              }}
              className="w-full mt-2 bg-ink-950 border border-ink-700 rounded-lg px-2.5 py-1.5 font-mono text-[11px] text-blue-300 flex justify-between items-center hover:border-brand-blue text-left"
            >
              <code className="truncate flex-1">$ {item.cmd}</code>
              <span className="text-[10px] text-ink-400 ml-2">📋 복사</span>
            </button>
          )}
          {item.path && <div className="mt-1.5 text-[10.5px] text-blue-200 font-mono">📂 {item.path}</div>}
          {item.mitre.length > 0 && (
            <div className="mt-2 flex gap-1 flex-wrap">
              {item.mitre.map((m) => (
                <a
                  key={m}
                  href={`https://attack.mitre.org/techniques/${m.replace(/\./g, '/')}/`}
                  target="_blank"
                  rel="noreferrer"
                  className="bg-brand-purple/10 text-brand-purple px-2 py-0.5 rounded-full text-[10px] font-bold hover:bg-brand-purple/25"
                >
                  {m}
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const Step3_GuideChecklist = ({ csp, incidentType, onPrev, onComplete }: Step3Props) => {
  const cspKey = (csp ?? 'naver') as 'naver' | 'nhn' | 'all';
  const cspMeta = CSP_META[cspKey] ?? CSP_META.naver;
  const typeMeta = incidentType ? TYPE_META[incidentType] : null;
  const guide = useMemo(() => buildGuide(incidentType ?? 'iam-takeover', cspKey), [incidentType, cspKey]);
  const [checked, setChecked] = useState<Record<string, boolean>>({});

  const toggle = (id: string) => setChecked((prev) => ({ ...prev, [id]: !prev[id] }));

  const allItems = [...guide.required, ...guide.corroborating];
  const autoCount = allItems.filter((i) => i.auto).length;
  const p1Count = allItems.filter((i) => i.priority === 1).length;
  const totalCollected = Object.values(checked).filter(Boolean).length;
  const totalRate = Math.round((totalCollected / allItems.length) * 100);

  const groupBy = (items: CollectionItem[]) => {
    const map: Record<number, CollectionItem[]> = {};
    items.forEach((it) => {
      map[it.priority] = map[it.priority] ?? [];
      map[it.priority].push(it);
    });
    return map;
  };

  const renderColumn = (items: CollectionItem[], roleKey: string) => {
    const grouped = groupBy(items);
    return [1, 2, 3, 4].flatMap((p) => {
      const list = grouped[p];
      if (!list?.length) return [];
      const meta = priorityMeta[p];
      return [
        <div key={`pri-${roleKey}-${p}`} className="mb-4">
          <div
            className="flex items-center gap-2.5 pb-2 mb-2 border-b border-ink-700/40 text-[11px] font-bold uppercase tracking-[0.1em]"
            style={{ color: meta.color }}
          >
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold text-white shrink-0"
              style={{ background: meta.color }}
            >
              {p}
            </div>
            <div>
              <div>{meta.label}</div>
              <div className="text-[9.5px] font-normal normal-case text-ink-400 tracking-normal">
                {meta.sub}
              </div>
            </div>
          </div>
          {list.map((it, idx) => {
            const id = `${roleKey}-${p}-${idx}`;
            return <ItemRow key={id} item={it} checked={!!checked[id]} onToggle={() => toggle(id)} />;
          })}
        </div>,
      ];
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="h-section">초동 수집 가이드</h2>
        <p className="text-[13px] text-ink-400 mt-1.5 max-w-2xl">
          선택된 사고 유형 · CSP · 시스템 구성에 따라 자동 생성된{' '}
          <b className="text-brand-red">우선순위 기반</b> 수집 체크리스트입니다.
        </p>
      </div>

      <div className="panel p-5 border-l-[3px] border-l-brand-blue">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-brand-blue font-bold text-[14px]">
            {typeMeta?.label ?? '사고 유형'}
          </span>
          <span className="text-ink-400">—</span>
          <span className="font-bold text-[13px]" style={{ color: cspMeta.color }}>
            {cspMeta.label}
          </span>
        </div>
        <p className="text-[12.5px] text-ink-300 leading-7">{guide.ctx}</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatTile color="#FF4D6D" value={p1Count} label="즉시 수집 (휘발성)" />
        <StatTile color="#E6EAF2" value={allItems.length} label="총 수집 항목" />
        <StatTile color="#14D9B0" value={autoCount} label="⚡ 자동 분석" />
        <StatTile color="#7C8497" value={allItems.length - autoCount} label="👤 수동 분석" />
        <StatTile color="#3D7BFF" value={`${totalRate}%`} label="완료율" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title={<><Badge role="REQUIRED" size="sm" /> 필수 증거</>}>{renderColumn(guide.required, 'req')}</Card>
        <Card title={<><Badge role="CORROBORATING" size="sm" /> 보강 증거</>}>{renderColumn(guide.corroborating, 'cor')}</Card>
      </div>

      <div className="panel p-4 text-[11.5px] leading-7 text-ink-300">
        <b className="text-ink-100">범례</b> &nbsp;
        <span className="tag-blue mr-1">☁ Cloud</span>
        <span className="tag-teal mr-1">🖥 Server</span>
        <span className="tag-purple mr-1">🔗 Network</span>
        <span className="tag-amber mr-1">📱 App</span>
        <span className="mx-1.5 text-ink-400">|</span>
        <span className="tag-teal mr-1">⚡ AUTO</span>파이프라인 자동 분석{' '}
        <span className="tag-gray ml-1.5 mr-1">👤 수동</span>수사관 직접 분석
      </div>

      <div className="flex justify-between gap-2">
        <button onClick={onPrev} className="btn-ghost">
          ← 이전
        </button>
        <button onClick={onComplete} className="btn-success">
          수집 완료 → 로그 수집
        </button>
      </div>
    </div>
  );
};

const StatTile = ({ color, value, label }: { color: string; value: number | string; label: string }) => (
  <div className="panel p-4 relative overflow-hidden">
    <span className="absolute top-0 left-0 right-0 h-px opacity-60" style={{ background: color }} />
    <div className="text-[24px] font-extrabold" style={{ color }}>{value}</div>
    <div className="text-[11px] text-ink-400 mt-1">{label}</div>
  </div>
);

export default Step3_GuideChecklist;
