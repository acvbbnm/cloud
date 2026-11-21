/**
 * V-5 LogPanel — 우측 사이드 패널 (수집 로그 + 단서).
 *
 * Phase P.6 (2026-05-26 byungwoo 피드백):
 *   "수집 로그쪽에 단서들이 같이 추가되어서 드래그앤드롭해서 보드에 올려놓고
 *    노드 연결 기능으로 연결하는쪽이 맞지 않니"
 *
 *   - 탭 [수집 로그 / 단서] 로 분리
 *   - 단서 탭: useClueTreeStore.response.path 의 채택 단서 리스트
 *   - 각 단서 draggable → BoardCanvas / ChainGraphCanvas drop zone 으로 이관
 *
 * 드래그 페이로드
 * --------------
 *   - 로그:   MIME = text/plain (legacy), id 직렬화 → BoardCanvas
 *   - 단서:   MIME = application/x-aisherpa-clue, JSON {clue_key, label}
 *             → ChainGraphCanvas drop zone 이 처리 → POST /api/board/nodes
 */
import { useState } from 'react';

import { useBoardStore } from '@/stores/useBoardStore';
import { useClueTreeStore } from '@/stores/useClueTreeStore';

import type { BoardLog } from '@/stores/useBoardStore';
import type { BoardNode } from '@/types';

export const CLUE_DRAG_MIME = 'application/x-aisherpa-clue';

export interface CluePayload {
  clue_key: string;
  label: string;
}

interface LogPanelProps {
  onDragStart: (log: BoardLog) => void;
  /** 보드에 이미 올라간 단서 노드 — meta.clue_key 추출. 중복 차단 표시용. */
  boardNodes?: BoardNode[];
}

type Tab = 'logs' | 'clues';

const LogPanel = ({ onDragStart, boardNodes = [] }: LogPanelProps) => {
  const logs = useBoardStore((s) => s.logs);
  const removeLog = useBoardStore((s) => s.removeLog);
  const treeResponse = useClueTreeStore((s) => s.response);
  const [tab, setTab] = useState<Tab>('logs');

  // V-1 의 path 에서 root 제외 채택 단서 리스트
  const acceptedClues =
    treeResponse?.path?.filter((n) => n.clue_key && n.clue_key !== '__ROOT__') ?? [];

  // 보드에 이미 올라간 clue_key 집합
  const onBoardKeys = new Set<string>();
  for (const n of boardNodes) {
    const ck =
      n.meta && typeof n.meta === 'object' && 'clue_key' in (n.meta as Record<string, unknown>)
        ? ((n.meta as Record<string, unknown>).clue_key as string | undefined)
        : undefined;
    if (ck) onBoardKeys.add(ck);
  }

  return (
    <div className="panel min-h-[540px] max-h-[920px] flex flex-col">
      <div className="flex items-center justify-between p-4 pb-2.5">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setTab('logs')}
            className={
              'text-[11.5px] font-semibold px-2 py-0.5 rounded-sm transition-colors ' +
              (tab === 'logs'
                ? 'text-ink-100 bg-ink-800 border border-ink-700/60'
                : 'text-ink-400 hover:text-ink-200')
            }
          >
            수집 로그
          </button>
          <button
            type="button"
            onClick={() => setTab('clues')}
            className={
              'text-[11.5px] font-semibold px-2 py-0.5 rounded-sm transition-colors ' +
              (tab === 'clues'
                ? 'text-brand-teal bg-brand-teal/10 border border-brand-teal/30'
                : 'text-ink-400 hover:text-brand-teal/80')
            }
            title="V-1 Evidence Tree 에서 채택된 단서"
          >
            단서
          </button>
        </div>
        <span className="chip text-[10.5px]">
          {tab === 'logs' ? `${logs.length}건` : `${acceptedClues.length}건`}
        </span>
      </div>

      {/* ─── 수집 로그 탭 ─── */}
      {tab === 'logs' && (
        <div className="px-4 pb-4 overflow-y-auto flex-1 min-h-0">
          {logs.length === 0 ? (
            <div className="text-[11.5px] text-ink-400 leading-6">
              로그 수집 탭에서 행을 체크 후 “수사 보드에 추가”로 가져오세요.
            </div>
          ) : (
            logs.map((l) => (
              <div
                key={l.id}
                draggable
                onDragStart={(e) => {
                  // 로그도 단서와 동일 MIME 으로 → ChainGraphCanvas 가 보드 노드로 변환
                  const payload: CluePayload = {
                    clue_key: `log:${l.id}`,
                    label: `[${l.ts}] ${l.ev} · ${l.ip}`,
                  };
                  e.dataTransfer.effectAllowed = 'copy';
                  e.dataTransfer.setData(CLUE_DRAG_MIME, JSON.stringify(payload));
                  e.dataTransfer.setData('text/plain', String(l.id));
                  onDragStart(l);
                }}
                className="bg-ink-950 border border-ink-700/70 rounded-xl px-3 py-2 mb-1.5 text-[11.5px] cursor-grab hover:border-brand-blue active:cursor-grabbing transition-colors"
              >
                <div className="flex justify-between items-center mb-0.5">
                  <span className="font-mono text-ink-400 text-[10px]">{l.ts}</span>
                  <button
                    onClick={() => removeLog(l.id)}
                    className="text-ink-400 hover:text-brand-red text-[12px] leading-none"
                  >
                    ✕
                  </button>
                </div>
                <div className="font-semibold text-[12px] truncate">{l.ev}</div>
                <div className="text-brand-red text-[10px] mt-0.5 truncate">
                  {l.ip} · {l.user}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ─── 단서 탭 (Phase P.6) ─── */}
      {tab === 'clues' && (
        <div className="px-4 pb-4 overflow-y-auto flex-1 min-h-0">
          {acceptedClues.length === 0 ? (
            <div className="text-[11.5px] text-ink-400 leading-6">
              V-1 Evidence Tree 에서 단서를 채택하면 여기에 표시됩니다.
              <br />
              <span className="text-ink-500">우측 ChainGraph 로 드래그해 보드 노드로 추가하세요.</span>
            </div>
          ) : (
            <>
              <p className="text-[10.5px] text-brand-teal/80 mb-2 leading-4">
                단서를 우측 ChainGraph 로 끌어 놓으면 보드 노드로 추가됩니다.
                노드 연결은 [엣지 모드] 로.
              </p>
              {acceptedClues.map((c) => {
                const isOnBoard = onBoardKeys.has(c.clue_key);
                return (
                  <div
                    key={c.node_id}
                    draggable={!isOnBoard}
                    onDragStart={(e) => {
                      if (isOnBoard) {
                        e.preventDefault();
                        return;
                      }
                      const payload: CluePayload = {
                        clue_key: c.clue_key,
                        label: c.label || c.clue_key,
                      };
                      e.dataTransfer.effectAllowed = 'copy';
                      e.dataTransfer.setData(CLUE_DRAG_MIME, JSON.stringify(payload));
                      // 일부 브라우저는 text/plain 도 요구
                      e.dataTransfer.setData('text/plain', c.clue_key);
                    }}
                    className={
                      'border rounded-xl px-3 py-2 mb-1.5 text-[11.5px] transition-colors ' +
                      (isOnBoard
                        ? 'bg-ink-950/40 border-ink-700/40 opacity-50 cursor-not-allowed'
                        : 'bg-brand-teal/5 border-brand-teal/40 cursor-grab hover:border-brand-teal active:cursor-grabbing')
                    }
                    title={
                      isOnBoard
                        ? '이미 보드에 있습니다'
                        : `드래그해서 ChainGraph 에 추가\n${c.clue_key}`
                    }
                  >
                    <div className="flex justify-between items-center mb-0.5">
                      <span className="font-mono text-ink-500 text-[9.5px]">
                        {c.category || 'CLUE'} · depth {c.depth}
                      </span>
                      {isOnBoard && (
                        <span className="text-[9px] text-emerald-400/80">✓ 보드 있음</span>
                      )}
                    </div>
                    <div className="font-semibold text-[12px] truncate text-ink-100">
                      {c.label || c.clue_key}
                    </div>
                    <div className="text-brand-teal/70 text-[9.5px] mt-0.5 truncate font-mono">
                      {c.clue_key}
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default LogPanel;
