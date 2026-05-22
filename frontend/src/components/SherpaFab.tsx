import { useState, useRef, useEffect } from 'react';

import { useSherpaStore } from '@/stores/useSherpaStore';
import { useCaseStore } from '@/stores/useCaseStore';
import { streamChat } from '@/api/sherpa';
import type { SherpaSource } from '@/types';

const quickQueries: { label: string; query: string }[] = [
  { label: '수집 갭 설명', query: '현재 케이스의 수집 갭을 설명해줘. REQUIRED 등급 우선.' },
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
              '⚠ 셰르파 응답 실패. 백엔드(/api/sherpa/chat/stream) 확인이 필요합니다.\n' +
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
        className="fixed bottom-7 right-7 w-[56px] h-[56px] rounded-full bg-sherpa-gradient shadow-glow z-[999] flex items-center justify-center text-[24px] text-white transition-all hover:scale-110 hover:rotate-3"
        title="AI 셰르파"
      >
        🤖
      </button>

      <div
        className={`fixed bottom-[96px] right-7 z-[998] w-[400px] h-[520px] panel border-ink-700 shadow-sherpa flex flex-col transition-all duration-200 origin-bottom-right ${
          open ? 'opacity-100 scale-100' : 'opacity-0 scale-90 translate-y-3 pointer-events-none'
        }`}
      >
        <div className="px-4 py-3 border-b border-ink-700/60 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="w-9 h-9 rounded-xl bg-sherpa-gradient flex items-center justify-center text-[15px]">
              🤖
            </span>
            <div>
              <b className="text-[13px]">AI 셰르파</b>
              <div className="text-[10px] text-ink-400">sLLM Llama 3.1 8B · 오프라인</div>
            </div>
          </div>
          <button onClick={toggle} className="text-ink-400 hover:text-ink-100 text-base">
            ✕
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto p-3.5 space-y-2.5">
          {messages.map((m) =>
            m.role === 'sherpa' ? (
              <div
                key={m.id}
                className="bg-ink-950 border border-ink-700/70 rounded-xl p-3 text-[12px] leading-6 max-w-[88%] animate-fade-up"
              >
                <b className="text-brand-purple text-[11px]">AI 셰르파</b>
                <div className="mt-1 whitespace-pre-wrap text-ink-100">{m.text}</div>
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {m.sources.map((s) => (
                      <span
                        key={s.source_id}
                        title={s.source_id}
                        className="text-[9.5px] text-ink-400 bg-ink-900 border border-ink-700/60 rounded-full px-1.5 py-0.5"
                      >
                        {s.type} · {s.title || s.source_id}
                      </span>
                    ))}
                  </div>
                )}
                {!m.sources && m.source && (
                  <span className="block mt-1.5 text-[9px] text-ink-400">출처: {m.source}</span>
                )}
              </div>
            ) : (
              <div
                key={m.id}
                className="ml-auto bg-cta-gradient/90 text-white rounded-xl px-3 py-2 text-[12px] max-w-[78%] text-right animate-fade-up"
              >
                {m.text}
              </div>
            ),
          )}
          {isStreaming &&
            messages.length > 0 &&
            messages[messages.length - 1].role === 'sherpa' &&
            messages[messages.length - 1].text === '' && (
              <div className="bg-ink-950 border border-ink-700/70 rounded-xl p-3 text-[11px] text-ink-400 max-w-[60%] animate-pulse">
                KB 검색 + 토큰 스트리밍 시작 중…
              </div>
            )}
          <div className="flex flex-wrap gap-1.5 pt-1">
            {quickQueries.map((q) => (
              <button
                key={q.label}
                onClick={() => handleSend(q.query)}
                disabled={isStreaming}
                className="text-[11px] text-brand-blue bg-brand-blue/10 border border-brand-blue/25 rounded-full px-3 py-1 hover:bg-brand-blue/20 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {q.label}
              </button>
            ))}
          </div>
        </div>

        <div className="p-2.5 border-t border-ink-700/60 flex gap-2">
          <input
            className="input"
            placeholder="질문 입력..."
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
