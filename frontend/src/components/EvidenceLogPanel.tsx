/**
 * P.36 (2026-05-31) — V-1 Step3 적재함 표시 패널 (재작성).
 *
 * 사용자 정정:
 *   "적재함은 우리 토글에서 로그 업로드/분석한 거 그거를 저기에 추가하자는
 *    소리야" — 자체 검색 인터페이스 제거. V-2/V-3/V-6 페이지의 row 가
 *   useEvidenceLogStore.load() 로 push 한 결과만 표시.
 *
 * 동작:
 *   1. store.logs 를 위에서 아래로 시간순 (신규 위) 렌더
 *   2. row 클릭 → onLogSelect (컴파스 detail / highlight 트리거)
 *   3. row 의 observable 칩 → onAdoptFromLog (단서 채택 흐름)
 *   4. [×] 제거 → store.unload (단서 채택 후에도 누적 부담 줄이기)
 *
 * 안내:
 *   적재함이 비어있을 땐 V-2/V-3/V-6 로 이동 안내 (네비게이션 X — 사용자 판단).
 */
import { useEvidenceLogStore, type LoadedLog } from '@/stores/useEvidenceLogStore';

import type { Observable } from '@/types';

export type { LoadedLog } from '@/stores/useEvidenceLogStore';

interface EvidenceLogPanelProps {
  onAdoptFromLog: (obs: Observable, log: LoadedLog) => void;
  /** 적재 row 클릭 — 컴파스/디테일 영역 강조 콜백. */
  onLogSelect?: (log: LoadedLog) => void;
  disabled?: boolean;
}

const SOURCE_LABEL: Record<LoadedLog['source'], string> = {
  raw: 'RAW',
  ocsf: 'OCSF',
  attack: 'ATT&CK',
};

const SOURCE_CLASS: Record<LoadedLog['source'], string> = {
  raw: 'bg-amber-900/40 text-amber-200 border border-amber-700/40',
  ocsf: 'bg-sky-900/40 text-sky-200 border border-sky-700/40',
  attack: 'bg-purple-900/40 text-purple-200 border border-purple-700/40',
};

const EvidenceLogPanel = ({
  onAdoptFromLog,
  onLogSelect,
  disabled = false,
}: EvidenceLogPanelProps) => {
  const logs = useEvidenceLogStore((s) => s.logs);
  const unload = useEvidenceLogStore((s) => s.unload);
  const clear = useEvidenceLogStore((s) => s.clear);

  return (
    <div className="space-y-2.5">
      {/* 안내 + 적재 카운트 */}
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10.5px] text-ink-400 leading-4">
          V-2 (로그) · V-3 (OCSF) · V-6 (ATT&CK) 페이지의 row 에서 [➜ 적재함] 으로 추가.
          <br />
          <span className="text-ink-500">
            적재된 로그의 observable 칩을 클릭하면 단서 트리에 채택됩니다.
          </span>
        </p>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="text-[10px] font-mono text-ink-400">
            {logs.length}건
          </span>
          {logs.length > 0 && (
            <button
              type="button"
              onClick={() => {
                if (window.confirm('적재함을 비웁니다. 채택된 단서는 유지됩니다.')) {
                  clear();
                }
              }}
              className="text-[9.5px] text-ink-500 hover:text-brand-red font-mono"
              title="적재함 전체 비우기 (단서 채택은 유지)"
            >
              비우기
            </button>
          )}
        </div>
      </div>

      {/* 적재 목록 */}
      <ul className="space-y-1.5 max-h-[420px] overflow-y-auto pr-1">
        {logs.length === 0 && (
          <li className="text-center py-6 text-[11px] text-ink-500 italic border border-dashed border-ink-700/40 rounded-lg">
            적재된 로그 없음
            <div className="text-[10.5px] text-ink-600 mt-1 not-italic">
              상단 메뉴의{' '}
              <a href="/logs" className="text-brand-teal hover:underline">
                V-2 로그
              </a>
              {' · '}
              <a href="/ocsf" className="text-brand-teal hover:underline">
                V-3 OCSF
              </a>
              {' · '}
              <a href="/attack" className="text-brand-teal hover:underline">
                V-6 ATT&CK
              </a>{' '}
              에서 [➜ 적재함] 버튼으로 추가
            </div>
          </li>
        )}
        {logs.map((l) => {
          // observable 이 정확히 1개면 본문 클릭만으로 즉시 채택 (칩 클릭 불필요).
          const singleObs = l.observables.length === 1 ? l.observables[0] : null;
          return (
          <li
            key={l.loaded_id}
            className="bg-ink-900/60 border border-ink-700/60 rounded-lg px-2.5 py-2"
          >
            <button
              type="button"
              onClick={() =>
                singleObs ? onAdoptFromLog(singleObs, l) : onLogSelect?.(l)
              }
              disabled={singleObs ? disabled : false}
              className="w-full text-left disabled:opacity-40 disabled:cursor-not-allowed"
              title={
                singleObs
                  ? `클릭하면 ${singleObs.type}:${singleObs.value} 을 단서로 즉시 채택`
                  : '이 로그를 미리보기 (단서 채택 아님 — 채택은 아래 주황색 항목 클릭)'
              }
            >
              <div className="flex items-start gap-1.5">
                <span
                  className={`text-[9px] font-mono px-1 py-px rounded shrink-0 ${SOURCE_CLASS[l.source]}`}
                >
                  {SOURCE_LABEL[l.source]}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-[11.5px] text-ink-100 truncate font-medium">
                    {l.label}
                  </div>
                  <div className="text-[10px] text-ink-500 font-mono mt-0.5">
                    🕒 {l.time?.slice(0, 19) ?? '시각 없음'}
                    {l.technique_id ? ` · ${l.technique_id}` : ''}
                  </div>
                </div>
                {singleObs ? (
                  <span className="text-[9px] text-brand-amber shrink-0 self-center whitespace-nowrap">
                    ➜ 클릭하여 채택
                  </span>
                ) : (
                  <span className="text-[9px] text-ink-500 shrink-0 self-center whitespace-nowrap">
                    🔍 미리보기
                  </span>
                )}
              </div>
            </button>

            {/* observable → 단서 채택 버튼들 (단일 observable 은 본문 클릭으로 대체) */}
            {singleObs ? (
              <div className="mt-1 text-[9.5px] text-brand-amber/70 italic">
                ➜ 단서 1개 — 위 본문을 클릭하면 바로 채택됩니다
              </div>
            ) : l.observables.length > 0 ? (
              <div className="mt-1.5 pt-1.5 border-t border-ink-800/80">
                <div className="text-[9px] text-brand-amber/80 font-mono mb-1">
                  ➜ 단서 채택 — 아래 항목 클릭
                </div>
                <div className="flex flex-wrap gap-1">
                {l.observables.map((o, oi) => (
                  <button
                    key={`${l.loaded_id}-obs-${oi}`}
                    type="button"
                    onClick={() => onAdoptFromLog(o, l)}
                    disabled={disabled}
                    className="text-[9.5px] font-mono px-1.5 py-0.5 rounded border border-brand-amber/40 text-brand-amber hover:bg-brand-amber/15 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                    title={`${o.type}:${o.value} 을 단서로 채택`}
                  >
                    ➜ {o.type}:
                    {o.value.length > 18 ? `${o.value.slice(0, 17)}…` : o.value}
                  </button>
                ))}
                </div>
              </div>
            ) : (
              <div className="mt-1 text-[9.5px] text-ink-600 italic">
                추출 가능한 observable 없음 — 직접 입력 카드로 보강
              </div>
            )}

            {/* 제거 */}
            <div className="mt-1 flex justify-end">
              <button
                type="button"
                onClick={() => unload(l.loaded_id)}
                className="text-[9.5px] text-ink-500 hover:text-brand-red font-mono"
                title="적재함에서 제거 (채택된 단서는 유지)"
              >
                × 제거
              </button>
            </div>
          </li>
          );
        })}
      </ul>
    </div>
  );
};

export default EvidenceLogPanel;
