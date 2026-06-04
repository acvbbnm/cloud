/**
 * LogAnalysisFab — 실시간 로그 분석 플로팅 패널 (2026-05-26, byungwoo).
 *
 * 사용자 비전 — "셰르파처럼 별도 칸으로, 국내 CSP 로그 분석이 실시간 단서로 추가
 *   되면서 힘이 생기는 흐름".
 *
 * 위치: 우측 하단 (셰르파 FAB 위), 전 화면 공용.
 * 클릭 시 우측 slide-in drawer — DropZone + 분석 진행 + ATT&CK 기법 리스트.
 * 각 기법 옆 [+ 단서 추가] 버튼 — V-1 Step 3 진행 중일 때만 활성.
 *
 * 백엔드 활용:
 *   POST /api/triage/analyze-logs — 기존 작동 (NCP/NHN 파서 + OCSF + ATT&CK)
 *
 * 학술 정합:
 *   - "Live Investigation" 패턴 (Palo Alto Cortex / Splunk SOAR)
 *   - paradigm doc §4.3 — 로그 파일 등록 → 자동 단서 추출 채널
 */
import { useEffect, useRef, useState } from 'react';

import { useCaseStore } from '@/stores/useCaseStore';
import { useClueTreeStore } from '@/stores/useClueTreeStore';
import { useEvidenceLogStore } from '@/stores/useEvidenceLogStore';
import { useLogAnalysisStore } from '@/stores/useLogAnalysisStore';
import { useToastStore } from '@/stores/useToastStore';

import { analyzeLogs } from '@/api/triage';

import type { HypothesisScores, Observable } from '@/types';

// 8 사고유형 + UNCLASSIFIED 모두 0 으로 시작 (analyzeLogs 의 baseline)
const EMPTY_SCORES: HypothesisScores = {
  CREDENTIAL_THEFT: 0,
  PRIVILEGE_ESCALATION: 0,
  DATA_EXFILTRATION: 0,
  AUDIT_LOG_TAMPERING: 0,
  RANSOMWARE: 0,
  MISCONFIG_EXPOSURE: 0,
  PHISH_INITIAL_ACCESS: 0,
  INSIDER_THREAT: 0,
  UNCLASSIFIED: 0,
};

interface MappedEvent {
  attack_id: string;
  ocsf_id: string;
  technique_id: string;
  technique_name: string | null;
  tactic: string;
  rule_id: string;
  time: string | null;
  actor_user_name: string | null;
  src_endpoint_ip: string | null;
  activity_name: string | null;
}

interface TechniqueGroup {
  technique_id: string;
  technique_name: string | null;
  tactic: string;
  count: number;
  events: MappedEvent[];
}

/** mapped_events 를 technique_id 별로 그룹화. */
const groupByTechnique = (events: MappedEvent[]): TechniqueGroup[] => {
  const map = new Map<string, TechniqueGroup>();
  for (const ev of events) {
    const tid = ev.technique_id;
    if (!tid) continue;
    if (!map.has(tid)) {
      map.set(tid, {
        technique_id: tid,
        technique_name: ev.technique_name,
        tactic: ev.tactic,
        count: 0,
        events: [],
      });
    }
    const g = map.get(tid)!;
    g.count += 1;
    g.events.push(ev);
  }
  return Array.from(map.values()).sort((a, b) => b.count - a.count);
};

const LogAnalysisFab = () => {
  const caseId = useCaseStore((s) => s.caseId);
  const showToast = useToastStore((s) => s.show);
  const open = useLogAnalysisStore((s) => s.open);
  const toggle = useLogAnalysisStore((s) => s.toggle);
  const result = useLogAnalysisStore((s) => s.result);
  const setResult = useLogAnalysisStore((s) => s.setResult);
  // P.37 — adoptedKeys/markAdopted (legacy 단서 직접 채택) 는 미사용.
  //   loadedSet 으로 적재함 store 기반 멱등 검사로 대체.
  const clueTree = useClueTreeStore((s) => s.response);

  // P.37 (2026-05-31 사용자: "내가 말한건 저 토글 열어서 분석된 로그를 분석
  //   로그 적재함에 추가하는 형태") — expandTree 즉시 호출 X. useEvidenceLogStore
  //   에 push, V-1 Step3 적재함에서 단서 채택은 별도 단계.
  const loadEvidence = useEvidenceLogStore((s) => s.load);
  const evidenceHas = useEvidenceLogStore((s) => s.has);

  const [analyzing, setAnalyzing] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // 적재 가능 — 케이스만 있으면 가능 (V-1 Step3 진행 무관).
  // 적재함은 어디서나 push 가능, 단서 채택은 V-1 Step3 에서.
  const canLoad = Boolean(caseId);

  // P.38 — 기법 그룹화 제거. raw event 그대로 시각 오름차순 정렬 (사고 진행 흐름).
  //   groupByTechnique 는 보조 통계용으로 보존 (헤더 "N 기법 식별").
  const mappedEvents: MappedEvent[] = result
    ? [...(result.mapped_events as MappedEvent[])].sort((a, b) => {
        const ta = a.time ?? '';
        const tb = b.time ?? '';
        return ta.localeCompare(tb);
      })
    : [];
  const techniqueGroups = result ? groupByTechnique(result.mapped_events) : [];

  const handleFile = async (file: File) => {
    if (!caseId) {
      showToast('케이스가 선택되지 않았습니다 — V-1 에서 케이스 진입 후 다시 시도', 4500);
      return;
    }
    setAnalyzing(true);
    try {
      const res = await analyzeLogs(
        caseId,
        file,
        clueTree?.posterior_current ?? EMPTY_SCORES,
      );
      setResult({
        caseId: res.caseId,
        mapped_events: res.mapped_events as MappedEvent[],
        analyzed_at: new Date().toISOString(),
        file_name: file.name,
      });
      showToast(`✓ ${file.name} 분석 완료 — ${res.mapped_events.length}건 매핑`, 3500);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(`로그 분석 실패: ${msg}`, 5000);
    } finally {
      setAnalyzing(false);
    }
  };

  /** P.38 (2026-05-31 사용자: "단서가 단서다워야지 — 미리 다 ATT&CK 매핑
   *   끝나 있으면 사고유형 찾기 의미 없음") — MappedEvent → raw event 단위
   *   LoadedLog. 표시·적재 모두 raw OCSF 관점 (시각·user·ip·activity 가 주),
   *   ATT&CK 기법은 보조 hint.
   *
   *   빈값 가드 — backend OCSF 정규화에서 actor·ip 가 "-"/"" 같은 플레이스홀더로
   *   채워지면 칩이 의미 없으므로 push 차단 (P.37 의 `ACCOUNT: -` 버그 fix).
   */
  const isMeaningful = (v: string | null | undefined): v is string =>
    !!v && v !== '-' && v.trim() !== '' && v.toLowerCase() !== 'null';

  const buildEventLog = (ev: MappedEvent) => {
    const obs: Observable[] = [];
    if (isMeaningful(ev.actor_user_name)) {
      obs.push({ type: 'ACCOUNT', value: ev.actor_user_name!, note: ev.activity_name ?? undefined });
    }
    if (isMeaningful(ev.src_endpoint_ip)) {
      obs.push({ type: 'IP_ADDRESS', value: ev.src_endpoint_ip!, note: ev.activity_name ?? undefined });
    }
    return {
      loaded_id: `ev-${ev.attack_id}`,
      source: 'ocsf' as const,  // raw OCSF event 관점 (ATT&CK 는 보조 hint)
      source_id: ev.attack_id,
      time: ev.time,
      // 라벨 = raw 활동명 (수사관이 *해석할* 신호) — ATT&CK 기법명은 hint 로 fields 에
      label: ev.activity_name || ev.rule_id || ev.attack_id.slice(0, 12),
      observables: obs,
      technique_id: ev.technique_id,  // 적재함 row 의 hint 배지로 활용
      fields: {
        time: ev.time,
        actor_user: ev.actor_user_name,
        src_ip: ev.src_endpoint_ip,
        activity_name: ev.activity_name,
        // ATT&CK 보조 hint (적재함 detail 에서 마지막에 노출, 적재함 list 라벨엔 X)
        attack_hint_technique: ev.technique_id,
        attack_hint_name: ev.technique_name,
        attack_hint_tactic: ev.tactic,
        attack_rule_id: ev.rule_id,
      },
    };
  };

  /** P.38 — [➜ 적재함] 클릭 — 개별 raw event 적재. */
  const handleLoadEvent = (ev: MappedEvent) => {
    if (!canLoad) return;
    const log = buildEventLog(ev);
    if (loadEvidence(log)) {
      showToast(
        `➜ V-1 적재함: ${ev.activity_name ?? ev.attack_id.slice(0, 8)}`,
        2500,
      );
    } else {
      showToast('이미 적재됨', 1800);
    }
  };

  const handleLoadAll = () => {
    if (!canLoad || !result) return;
    let added = 0;
    for (const ev of result.mapped_events as MappedEvent[]) {
      if (loadEvidence(buildEventLog(ev))) added += 1;
    }
    const total = result.mapped_events.length;
    showToast(
      added > 0
        ? `➜ V-1 적재함에 ${added}건 추가 (${total - added}건 이미 적재됨)`
        : `모든 이벤트 이미 적재됨 (${total}건)`,
      3000,
    );
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void handleFile(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // 드로어 외부 클릭 시 닫기 (ESC 도)
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') toggle();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, toggle]);

  return (
    <>
      {/* FAB 버튼 (셰르파 위 ~64px) */}
      <button
        onClick={toggle}
        title="실시간 로그 분석 — 국내 CSP 로그 → ATT&CK 단서"
        className="fixed bottom-32 right-5 w-11 h-11 rounded-full bg-brand-amber text-ink-975 z-[999] font-mono text-[14px] font-bold flex items-center justify-center border border-brand-amber hover:bg-amber-400 transition-colors shadow-lg"
      >
              </button>

      {/* Drawer (우측 slide-in) */}
      {open && (
        <>
          {/* backdrop — 클릭 시 닫기 */}
          <div
            className="fixed inset-0 z-[996] bg-black/30 transition-opacity"
            onClick={toggle}
          />
          <div
            className="fixed top-0 right-0 bottom-0 z-[997] w-[440px] max-w-[90vw] bg-ink-900 border-l border-ink-700 flex flex-col shadow-2xl animate-slide-in-right"
            role="dialog"
            aria-modal="true"
          >
            {/* 헤더 */}
            <div className="px-4 py-3 border-b border-ink-700 bg-ink-850 flex items-center justify-between">
              <div>
                <div className="text-[13px] font-semibold text-ink-100">
                  실시간 로그 분석
                </div>
                <div className="text-[10.5px] text-ink-400 mt-0.5">
                  NCP/NHN 로그 → OCSF → ATT&CK 매핑 → 단서 채택
                </div>
              </div>
              <button
                onClick={toggle}
                className="text-ink-400 hover:text-ink-100 text-[18px] leading-none px-2"
                title="닫기 (ESC)"
              >
                ✕
              </button>
            </div>

            {/* 본문 */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {/* 케이스 상태 안내 */}
              {!caseId && (
                <div className="bg-amber-900/20 border border-amber-700/50 rounded px-3 py-2 text-[11px] text-amber-200 leading-5">
                  ⚠ 케이스 미선택 — V-1 에서 케이스 진입 후 사용
                </div>
              )}
              {caseId && !clueTree && (
                <div className="bg-blue-900/20 border border-blue-700/50 rounded px-3 py-2 text-[11px] text-blue-200 leading-5">
                  ℹ 적재함 push 만 가능 — V-1 Step3 에서 적재된 로그의 observable
                  칩을 클릭해 단서 채택.
                </div>
              )}

              {/* DropZone */}
              <div
                onDrop={handleDrop}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                className={`border-2 border-dashed rounded-lg px-4 py-6 text-center transition-colors ${
                  dragging
                    ? 'border-brand-teal bg-brand-teal/10'
                    : 'border-ink-600 bg-ink-950/40 hover:border-ink-500'
                }`}
              >
                <div className="text-[11.5px] text-ink-200 font-semibold">
                  NCP·NHN 로그 파일 드래그
                </div>
                <div className="text-[10px] text-ink-500 mt-0.5">또는</div>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={analyzing || !caseId}
                  className="mt-1.5 text-[10.5px] font-mono text-brand-teal hover:text-brand-tealDark border border-brand-teal/50 hover:border-brand-tealDark px-3 py-1 rounded transition-colors disabled:opacity-40"
                >
                  파일 선택
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".json,.log,.txt,.csv"
                  className="hidden"
                  onChange={handleFileChange}
                />
                <div className="text-[9px] text-ink-500 mt-2">
                  지원: .json / .log / .txt / .csv
                </div>
              </div>

              {/* 진행 표시 */}
              {analyzing && (
                <div className="bg-ink-950/60 border border-ink-700 rounded px-3 py-2.5 text-[11px] text-ink-200">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-brand-teal rounded-full animate-pulse" />
                    <span>분석 진행 중 — parsing · OCSF · ATT&CK 매핑…</span>
                  </div>
                </div>
              )}

              {/* 결과 */}
              {result && !analyzing && (
                <>
                  <div className="border-t border-ink-700 pt-3">
                    <div className="text-[10.5px] text-ink-400 font-mono uppercase tracking-wider mb-1">
                      분석 결과 — {result.file_name}
                    </div>
                    <div className="text-[10px] text-ink-500 leading-4">
                      {result.mapped_events.length}건 매핑 · {techniqueGroups.length}{' '}
                      기법 식별 · {new Date(result.analyzed_at).toLocaleTimeString('ko-KR')}
                    </div>
                  </div>

                  {mappedEvents.length === 0 ? (
                    <div className="text-[11px] text-ink-500 italic text-center py-4">
                      매핑된 이벤트 없음 — 로그 형식 또는 룰 갭 확인 필요
                    </div>
                  ) : (
                    <>
                      {/* P.38 — raw event row (시각·user·ip·activity 주, ATT&CK hint 부) */}
                      <div className="space-y-1.5 max-h-[420px] overflow-y-auto pr-1">
                        {mappedEvents.map((ev) => {
                          const loadedId = `ev-${ev.attack_id}`;
                          const loaded = evidenceHas(loadedId);
                          const hasActor = isMeaningful(ev.actor_user_name);
                          const hasIp = isMeaningful(ev.src_endpoint_ip);
                          return (
                            <div
                              key={ev.attack_id}
                              className={`bg-ink-900/60 border rounded-lg px-2.5 py-2 ${
                                loaded ? 'border-emerald-700/60' : 'border-ink-700/70'
                              }`}
                            >
                              <div className="flex items-start justify-between gap-2 mb-1">
                                <div className="flex-1 min-w-0">
                                  {/* 1행: 시각 + 활동명 (사용자가 *해석할* raw 신호) */}
                                  <div className="text-[10.5px] text-ink-100 leading-4">
                                    <span className="font-mono text-ink-400">
                                      {ev.time?.slice(0, 19) ?? '시각 없음'}
                                    </span>
                                    <span className="mx-1 text-ink-600">·</span>
                                    <span className="font-medium">
                                      {ev.activity_name ?? ev.rule_id}
                                    </span>
                                  </div>
                                  {/* 2행: actor / ip (관찰가능값) */}
                                  <div className="text-[10px] text-ink-300 font-mono mt-0.5 leading-4 truncate">
                                    {hasActor && (
                                      <span>
                                        <span className="text-ink-500">user</span> {ev.actor_user_name}
                                      </span>
                                    )}
                                    {hasActor && hasIp && (
                                      <span className="text-ink-600 mx-1.5">·</span>
                                    )}
                                    {hasIp && (
                                      <span>
                                        <span className="text-ink-500">ip</span> {ev.src_endpoint_ip}
                                      </span>
                                    )}
                                    {!hasActor && !hasIp && (
                                      <span className="text-ink-600 italic">
                                        관찰 가능값 없음
                                      </span>
                                    )}
                                  </div>
                                  {/* 3행: ATT&CK 보조 hint (작게, 흐리게 — 수사관 해석 검증용) */}
                                  <div className="text-[9px] text-ink-500 font-mono mt-1">
                                    <span className="text-ink-600">hint:</span>{' '}
                                    <span className="text-purple-400/80">
                                      {ev.technique_id}
                                    </span>
                                    {ev.tactic && (
                                      <span className="text-ink-600"> · {ev.tactic}</span>
                                    )}
                                  </div>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => handleLoadEvent(ev)}
                                  disabled={!canLoad || loaded}
                                  className={`text-[9.5px] font-mono whitespace-nowrap px-2 py-0.5 rounded border transition-colors ${
                                    loaded
                                      ? 'border-emerald-600/70 text-emerald-300 bg-emerald-900/30 cursor-default'
                                      : canLoad
                                      ? 'border-brand-teal/50 text-brand-teal hover:bg-brand-teal/10'
                                      : 'border-ink-700 text-ink-500 cursor-not-allowed opacity-50'
                                  }`}
                                  title={
                                    !canLoad
                                      ? '활성 케이스 없음 (V-1 사고 접수 후 가능)'
                                      : loaded
                                      ? '이미 V-1 적재함에 있음'
                                      : 'raw event 를 V-1 Step3 적재함에 추가 — 거기서 observable 칩으로 단서 채택'
                                  }
                                >
                                  {loaded ? '✓ 적재됨' : '➜ 적재함'}
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {canLoad &&
                        mappedEvents.some(
                          (ev) => !evidenceHas(`ev-${ev.attack_id}`),
                        ) && (
                          <button
                            type="button"
                            onClick={handleLoadAll}
                            className="w-full text-[11px] font-semibold bg-brand-teal hover:bg-brand-tealDark text-ink-950 px-3 py-1.5 rounded transition-colors"
                          >
                            미적재 이벤트 모두 V-1 적재함에 추가 →
                          </button>
                        )}
                    </>
                  )}
                </>
              )}
            </div>

            {/* 하단 안내 */}
            <div className="px-4 py-2 border-t border-ink-700 text-[9.5px] text-ink-500 leading-4 font-mono">
              paradigm §4.3 · NCP/NHN 파서 · OCSF 정규화 · ATT&CK Cloud Matrix v14
            </div>
          </div>
        </>
      )}
    </>
  );
};

export default LogAnalysisFab;
