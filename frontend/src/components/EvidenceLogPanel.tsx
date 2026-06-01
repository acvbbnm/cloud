/**
 * P.35.2 (2026-05-31) — V-1 Step3 분석 로그 적재 + 로그 → 단서 변환 패널.
 *
 * 사용자 비전:
 *   "다음 단서 후보는 제안만 — 실제 로그를 찾아와서 분석 후 추가가 정합.
 *    분석한 로그들을 적재할 수 있는 칸 + 그 로그를 단서로 올릴 수 있도록.
 *    타임스탬프도 중요하니 컴파스 점 클릭 시 그 로그에 대한 정보가
 *    자세히 보이도록."
 *
 * 동작:
 *   1. 상단 검색 — V-2 에서 매핑된 ATT&CK / OCSF 결과 받아 클라이언트 필터링
 *   2. 결과 row → [➜ 적재] 버튼 → loadedLogs 메모리 상태 추가 (멱등)
 *   3. 적재 목록 row → [➜ 단서로 채택] 버튼 → Observable 추출 → 부모 콜백
 *      → handleDirectClueAdd (Step3) 경유 → expandTree (label_override 포함)
 *   4. 적재 row 클릭 → 부모 onLogSelect 로 컴파스/디테일 영역 강조
 *
 * 상태:
 *   - 검색 query / source filter — 컴포넌트 로컬 useState
 *   - 적재 로그 목록 (LoadedLog[]) — 부모(Step3) 가 useState 로 보관 + props 전달
 *     (컴파스 점 클릭 시 매칭 detail 노출에 필요)
 *
 * 학술 정합:
 *   AI 비판단 (CLAUDE.md §5) — 추천·검색·요약만, 채택 결정은 수사관.
 *   ISO/IEC 27035 Detection & Analysis — 증거 기반 결정.
 */
import { useMemo, useState } from 'react';

import { useQuery } from '@tanstack/react-query';

import { getAttack, getOcsf } from '@/api/analysis';

import type {
  AttackEventItem,
  OCSFEventItem,
  Observable,
} from '@/types';

const FETCH_PAGE_SIZE = 100;

export type EvidenceSource = 'attack' | 'ocsf';

/** 적재된 분석 로그 한 줄. Step3 useState 로 보관. */
export interface LoadedLog {
  /** 클라이언트 채번 ID — list key + onLogSelect 식별자. */
  loaded_id: string;
  source: EvidenceSource;
  /** 원본 식별자 — attack_id 또는 ocsf_id. */
  source_id: string;
  /** ISO datetime — event_time 또는 time. */
  time: string | null;
  /** 한 줄 라벨 — `${activity_name} · ${technique_id?}`. */
  label: string;
  /** observable 후보 — actor_user_name / src_endpoint_ip / technique_id. */
  observables: Observable[];
  /** technique_id (attack source 만). 컴파스 점 매칭에 활용. */
  technique_id?: string;
  /** 보조 fields — detail 카드에 표시. */
  fields: Record<string, string | number | null>;
}

interface EvidenceLogPanelProps {
  caseId: string;
  loadedLogs: LoadedLog[];
  onLoad: (log: LoadedLog) => void;
  onUnload: (loaded_id: string) => void;
  onAdoptFromLog: (obs: Observable, log: LoadedLog) => void;
  /** 적재 row 클릭 — 컴파스/디테일 영역 강조. */
  onLogSelect?: (log: LoadedLog) => void;
  disabled?: boolean;
}

/** AttackEventItem → LoadedLog 변환.
 *
 * NOTE: 프론트 ClueType union 은 6종 (IP_ADDRESS·ACCOUNT·HASH·DOMAIN·
 *   TIME_WINDOW·SERVICE) — ATT&CK technique_id 자체는 직접 매핑되지 않는다.
 *   따라서 ATT&CK row 는 observable 추출 없이 메타만 노출 (사용자에게
 *   "추출 가능한 observable 없음 — OCSF 결과를 적재해 단서 채택" 안내).
 *   technique_id 는 컴파스 점 detail 영역에서 활용.
 */
const fromAttack = (e: AttackEventItem): LoadedLog => ({
  loaded_id: `att-${e.attack_id}`,
  source: 'attack',
  source_id: e.attack_id,
  time: e.event_time,
  label: `${e.activity_name ?? e.technique_id} · ${e.tactic}`,
  observables: [], // 6종 ClueType 미매칭 — OCSF row 로 hop 권장
  technique_id: e.technique_id,
  fields: {
    technique_id: e.technique_id,
    technique_name: e.technique_name,
    tactic: e.tactic,
    activity_name: e.activity_name,
    rule_id: e.rule_id,
    event_time: e.event_time,
  },
});

/** OCSFEventItem → LoadedLog 변환 — actor_user_name → ACCOUNT,
 *   src_endpoint_ip → IP_ADDRESS observable 추출.
 *   _inferClueKey (Step3) 가 카탈로그에서 weight_key 매핑. */
const fromOcsf = (e: OCSFEventItem): LoadedLog => {
  const obs: Observable[] = [];
  if (e.actor_user_name) {
    obs.push({
      type: 'ACCOUNT',
      value: e.actor_user_name,
      note: e.activity_name,
    });
  }
  if (e.src_endpoint_ip) {
    obs.push({
      type: 'IP_ADDRESS',
      value: e.src_endpoint_ip,
      note: e.activity_name,
    });
  }
  return {
    loaded_id: `ocsf-${e.ocsf_id}`,
    source: 'ocsf',
    source_id: e.ocsf_id,
    time: e.time,
    label: e.activity_name || e.ocsf_id.slice(0, 12),
    observables: obs,
    fields: {
      activity_name: e.activity_name,
      actor_user: e.actor_user_name,
      src_ip: e.src_endpoint_ip,
      status_code: e.status_code,
      time: e.time,
    },
  };
};

const EvidenceLogPanel = ({
  caseId,
  loadedLogs,
  onLoad,
  onUnload,
  onAdoptFromLog,
  onLogSelect,
  disabled = false,
}: EvidenceLogPanelProps) => {
  const [query, setQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState<EvidenceSource>('attack');

  const attackQuery = useQuery({
    queryKey: ['analysis', 'attack', caseId, 1, FETCH_PAGE_SIZE],
    queryFn: () => getAttack(caseId, 1, FETCH_PAGE_SIZE),
    enabled: !!caseId && sourceFilter === 'attack',
    staleTime: 60_000,
  });
  const ocsfQuery = useQuery({
    queryKey: ['analysis', 'ocsf', caseId, 1, FETCH_PAGE_SIZE],
    queryFn: () => getOcsf(caseId, 1, FETCH_PAGE_SIZE),
    enabled: !!caseId && sourceFilter === 'ocsf',
    staleTime: 60_000,
  });

  // 검색 결과 — 클라이언트 필터링 (caseId 당 ~100건 이내)
  const matches = useMemo<LoadedLog[]>(() => {
    const q = query.trim().toLowerCase();
    let pool: LoadedLog[] = [];
    if (sourceFilter === 'attack') {
      pool = (attackQuery.data?.items ?? []).map(fromAttack);
    } else {
      pool = (ocsfQuery.data?.items ?? []).map(fromOcsf);
    }
    if (!q) return pool.slice(0, 30);
    return pool
      .filter((l) =>
        [l.label, l.technique_id ?? '', ...Object.values(l.fields).map(String)]
          .join(' ')
          .toLowerCase()
          .includes(q),
      )
      .slice(0, 30);
  }, [sourceFilter, query, attackQuery.data, ocsfQuery.data]);

  const loadedSet = useMemo(
    () => new Set(loadedLogs.map((l) => l.loaded_id)),
    [loadedLogs],
  );

  const isLoading =
    (sourceFilter === 'attack' && attackQuery.isLoading) ||
    (sourceFilter === 'ocsf' && ocsfQuery.isLoading);

  return (
    <div className="space-y-2.5">
      {/* 안내 + source toggle */}
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10.5px] text-ink-400 leading-4">
          V-2 분석 결과 검색 후 적재 → 적재된 로그를 단서로 채택.
          <br />
          <span className="text-ink-500">
            (다음 단서 후보의 의심·검증을 실제 로그로 뒷받침)
          </span>
        </p>
        <div className="flex rounded border border-ink-700/60 overflow-hidden text-[10px] font-mono shrink-0">
          {(['attack', 'ocsf'] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSourceFilter(s)}
              className={`px-2 py-1 transition-colors ${
                sourceFilter === s
                  ? 'bg-brand-teal/20 text-brand-teal'
                  : 'bg-ink-900/60 text-ink-400 hover:text-ink-200'
              }`}
            >
              {s === 'attack' ? 'ATT&CK' : 'OCSF'}
            </button>
          ))}
        </div>
      </div>

      {/* 검색 인풋 */}
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={
          sourceFilter === 'attack'
            ? '기법 ID·활동·전술 검색 (예: T1078, ConsoleLogin)'
            : '활동·사용자·IP 검색'
        }
        disabled={disabled}
        className="w-full text-[11.5px] bg-ink-900/60 border border-ink-700/60 rounded px-2 py-1.5 placeholder:text-ink-500 focus:outline-none focus:border-brand-teal/60"
      />

      {/* 검색 결과 */}
      <div>
        <div className="text-[9.5px] text-ink-500 uppercase tracking-wider mb-1 flex justify-between">
          <span>검색 결과 ({matches.length})</span>
          <span className="font-mono">
            {isLoading
              ? '로딩…'
              : `${sourceFilter === 'attack' ? attackQuery.data?.total ?? 0 : ocsfQuery.data?.total ?? 0}건 매핑됨`}
          </span>
        </div>
        <ul className="max-h-[180px] overflow-y-auto space-y-1 pr-1">
          {matches.length === 0 && !isLoading && (
            <li className="text-[10.5px] text-ink-500 italic py-1">
              매칭 로그 없음 — V-2 에서 매핑 실행 또는 검색어 조정
            </li>
          )}
          {matches.map((m) => {
            const already = loadedSet.has(m.loaded_id);
            return (
              <li
                key={m.loaded_id}
                className="bg-ink-950/40 border border-ink-700/40 rounded px-2 py-1.5 flex items-start gap-2"
              >
                <div className="flex-1 min-w-0">
                  <div className="text-[11px] text-ink-100 truncate">{m.label}</div>
                  <div className="text-[9.5px] text-ink-500 font-mono">
                    {m.time?.slice(0, 19) ?? '시각 없음'}
                    {m.technique_id ? ` · ${m.technique_id}` : ''}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => !already && onLoad(m)}
                  disabled={already || disabled}
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-brand-teal/40 text-brand-teal hover:bg-brand-teal/15 transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
                  title={already ? '이미 적재됨' : '적재함에 추가'}
                >
                  {already ? '✓ 적재됨' : '➜ 적재'}
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {/* 적재 목록 */}
      <div>
        <div className="text-[9.5px] text-ink-500 uppercase tracking-wider mb-1 flex justify-between">
          <span>적재함 ({loadedLogs.length})</span>
          <span className="font-mono text-ink-600">→ 단서로 채택</span>
        </div>
        <ul className="space-y-1 max-h-[200px] overflow-y-auto pr-1">
          {loadedLogs.length === 0 && (
            <li className="text-[10.5px] text-ink-500 italic py-1">
              아직 적재된 로그 없음
            </li>
          )}
          {loadedLogs.map((l) => (
            <li
              key={l.loaded_id}
              className="bg-ink-900/60 border border-ink-700/60 rounded-lg px-2 py-1.5"
            >
              <button
                type="button"
                onClick={() => onLogSelect?.(l)}
                className="w-full text-left"
                title="컴파스/디테일 영역 강조"
              >
                <div className="flex items-start gap-1.5">
                  <span
                    className={`text-[9px] font-mono px-1 py-px rounded shrink-0 ${
                      l.source === 'attack'
                        ? 'bg-purple-900/40 text-purple-200 border border-purple-700/40'
                        : 'bg-sky-900/40 text-sky-200 border border-sky-700/40'
                    }`}
                  >
                    {l.source === 'attack' ? 'ATT&CK' : 'OCSF'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] text-ink-100 truncate">{l.label}</div>
                    <div className="text-[9.5px] text-ink-500 font-mono">
                      {l.time?.slice(0, 19) ?? '시각 없음'}
                    </div>
                  </div>
                </div>
              </button>
              {/* observable → 단서 채택 버튼들 */}
              {l.observables.length > 0 ? (
                <div className="mt-1.5 pt-1.5 border-t border-ink-800/80 flex flex-wrap gap-1">
                  {l.observables.map((o, oi) => (
                    <button
                      key={`${l.loaded_id}-obs-${oi}`}
                      type="button"
                      onClick={() => onAdoptFromLog(o, l)}
                      disabled={disabled}
                      className="text-[9.5px] font-mono px-1.5 py-0.5 rounded border border-brand-amber/40 text-brand-amber hover:bg-brand-amber/15 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                      title={`${o.type}:${o.value} 을 단서로 트리에 채택`}
                    >
                      ➜ {o.type}:{o.value.length > 18 ? `${o.value.slice(0, 17)}…` : o.value}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="mt-1 text-[9.5px] text-ink-600 italic">
                  추출 가능한 observable 없음 — 직접 입력으로 보강 가능
                </div>
              )}
              {/* 제거 */}
              <div className="mt-1 flex justify-end">
                <button
                  type="button"
                  onClick={() => onUnload(l.loaded_id)}
                  className="text-[9.5px] text-ink-500 hover:text-brand-red font-mono"
                  title="적재함에서 제거 (단서 채택은 유지)"
                >
                  × 제거
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default EvidenceLogPanel;
