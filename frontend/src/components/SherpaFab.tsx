/**
 * AI 셰르파 플로팅 — 2026-05-22 블룸버그 스타일.
 * 로봇 이모지·그라데이션·글로우 제거. 텍스트 라벨 + 각진 사각 패널.
 */
import { useState, useRef, useEffect } from 'react';

import { useSherpaStore } from '@/stores/useSherpaStore';
import { useCaseStore } from '@/stores/useCaseStore';
import { streamChat } from '@/api/sherpa';
import type { SherpaSource } from '@/types';

const quickQueries: { label: string; query: string }[] = [
  { label: '수집 갭', query: '현재 케이스의 수집 갭을 설명해줘. REQUIRED 등급 우선.' },
  { label: 'T1078 사례', query: 'T1078 Valid Accounts 의 클라우드 침해 사례와 탐지 포인트를 알려줘.' },
  { label: '빠진 고리', query: '현재 ATT&CK 매핑 결과에서 빠졌을 가능성이 높은 기법을 추정해줘.' },
];

const formatSourceSummary = (sources: SherpaSource[] | undefined): string => {
  if (!sources || sources.length === 0) return '출처 없음';
  const types = Array.from(new Set(sources.map((s) => s.type))).join(' · ');
  return `${types} (${sources.length}건)`;
};

const SherpaFab = () => {
  const caseId = useCaseStore((s) => s.caseId);

  const open = useSherpaStore((s) => s.open);
  const toggle = useSherpaStore((s) => s.toggle);
  const messages = useSherpaStore((s) => s.messages);
  const push = useSherpaStore((s) => s.push);
  const updateLast = useSherpaStore((s) => s.updateLast);
  const appendDelta = useSherpaStore((s) => s.appendDelta);
  const sessionId = useSherpaStore((s) => s.sessionId);
  const setSessionId = useSherpaStore((s) => s.setSessionId);

  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, open]);

  const handleSend = async (q?: string) => {
    const text = (q ?? input).trim();
    if (!text || isStreaming) return;
    push({ role: 'user', text });
    push({ role: 'sherpa', text: '' });
    setInput('');
    setIsStreaming(true);

    await streamChat(
      {
        caseId: caseId ?? null,
        sessionId: sessionId ?? null,
        query: text,
      },
      {
        onStart: (newSessionId, sources) => {
          if (!sessionId) setSessionId(newSessionId);
          updateLast({ sources, source: formatSourceSummary(sources) });
        },
        onDelta: (delta) => appendDelta(delta),
        onDone: () => setIsStreaming(false),
        onError: (err) => {
          updateLast({
            text:
              '셰르파 응답 실패. 백엔드(/api/sherpa/chat/stream) 확인이 필요합니다.\n' +
              `(상세: ${err.message})`,
          });
          setIsStreaming(false);
        },
      },
    );
  };

  return (
    <>
      <button
        onClick={toggle}
        className="fixed bottom-16 right-5 w-11 h-11 rounded-full bg-brand-teal text-ink-975 z-[999] font-mono text-[14px] font-bold flex items-center justify-center border border-brand-teal hover:bg-brand-tealDark hover:border-brand-tealDark transition-colors"
        title="AI 셰르파"
      >
        S
      </button>

      <div
        className={`fixed bottom-[124px] right-5 z-[998] w-[400px] h-[540px] bg-ink-900 border border-ink-700 flex flex-col transition-opacity duration-150 ${
          open ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      >
        <div className="px-3 py-2 bg-ink-850 border-b border-ink-700 flex items-center justify-between">
          <div className="flex items-center gap-2 font-mono">
            <span className="text-brand-amber font-bold tracking-[0.16em] text-[11px]">SHERPA</span>
            <span className="text-[10px] text-ink-500">LLAMA-3.1 · OFFLINE</span>
          </div>
          <button onClick={toggle} className="text-ink-400 hover:text-ink-100 text-[14px] leading-none">
            ×
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-2 text-[12px]">
          {messages.map((m) =>
            m.role === 'sherpa' ? (
              <div
                key={m.id}
                className="bg-ink-950 border border-ink-700 p-2.5 leading-5 max-w-[92%] animate-fade-up"
              >
                <b className="text-brand-amber text-[10px] font-mono uppercase tracking-[0.14em]">SHERPA</b>
                <div className="mt-1 whitespace-pre-wrap text-ink-100">{m.text}</div>
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {m.sources.map((s) => (
                      <span
                        key={s.source_id}
                        title={s.source_id}
                        className="text-[9px] font-mono text-ink-400 bg-ink-900 border border-ink-700 px-1.5 py-0.5"
                      >
                        {s.type} · {s.title || s.source_id}
                      </span>
                    ))}
                  </div>
                )}
                {!m.sources && m.source && (
                  <span className="block mt-1 text-[9px] text-ink-500 font-mono">출처: {m.source}</span>
                )}
              </div>
            ) : (
              <div
                key={m.id}
                className="ml-auto bg-ink-850 border border-ink-700 text-ink-100 px-2.5 py-1.5 max-w-[78%] text-right animate-fade-up"
              >
                {m.text}
              </div>
            ),
          )}
          {isStreaming &&
            messages.length > 0 &&
            messages[messages.length - 1].role === 'sherpa' &&
            messages[messages.length - 1].text === '' && (
              <div className="bg-ink-950 border border-ink-700 p-2 text-[11px] text-ink-400 max-w-[60%] font-mono animate-pulse">
                KB 검색 중…
              </div>
            )}
          <div className="flex flex-wrap gap-1 pt-1">
            {quickQueries.map((q) => (
              <button
                key={q.label}
                onClick={() => handleSend(q.query)}
                disabled={isStreaming}
                className="text-[10px] font-mono uppercase tracking-[0.06em] text-brand-amber bg-transparent border border-brand-amber/40 px-2 py-0.5 hover:bg-brand-amber/10 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {q.label}
              </button>
            ))}
          </div>
        </div>

        <div className="p-2 border-t border-ink-700 flex gap-1.5">
          <input
            className="input"
            placeholder="질문 입력…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            disabled={isStreaming}
          />
          <button
            onClick={() => handleSend()}
            disabled={isStreaming || !input.trim()}
            className="btn-primary btn-sm disabled:opacity-50"
          >
            {isStreaming ? '…' : '전송'}
          </button>
        </div>
      </div>
    </>
  );
};

export default SherpaFab;
