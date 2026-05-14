import { useState, useRef, useEffect } from 'react';

import { useSherpaStore } from '@/stores/useSherpaStore';

const quickReplies: { label: string; reply: string; source: string }[] = [
  {
    label: '수집 갭 설명',
    reply:
      'VPC Flow Log 미수집 — T1071 탐지에 REQUIRED 등급 증거입니다. NCP Console → VPC → Flow Log 추출을 권장합니다.',
    source: '갭 감지 모듈',
  },
  {
    label: 'T1078 사례',
    reply:
      'T1078 Valid Accounts: 해외 IP에서 consoleSignIn 후 권한 상승하는 패턴이 전형적입니다. NCP Activity Tracer에서 동일 시간대의 changeSubAccountLoginId 이벤트를 함께 확인하세요.',
    source: 'ATT&CK Cloud v14',
  },
  {
    label: '빠진 고리',
    reply:
      'T1078 → T1098 사이에 deleteAccessKey(T1070.008), createAccessKey(T1098.001) 이벤트가 누락되었을 가능성이 높습니다. 14:32~14:35 구간을 재검토해 주세요.',
    source: 'ATT&CK 교차 검색',
  },
];

const SherpaFab = () => {
  const open = useSherpaStore((s) => s.open);
  const toggle = useSherpaStore((s) => s.toggle);
  const messages = useSherpaStore((s) => s.messages);
  const push = useSherpaStore((s) => s.push);

  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, open]);

  const handleQuick = (i: number) => {
    const q = quickReplies[i];
    push({ role: 'user', text: q.label });
    window.setTimeout(() => push({ role: 'sherpa', text: q.reply, source: q.source }), 280);
  };

  const handleSend = () => {
    const q = input.trim();
    if (!q) return;
    push({ role: 'user', text: q });
    setInput('');
    window.setTimeout(
      () =>
        push({
          role: 'sherpa',
          text: `RAG 검색 결과: "${q}" 관련 ATT&CK 문서와 NCP/NHN 매핑 결과를 종합하면, 해당 이벤트는 권한 탈취 패턴과 연관됩니다. 90일 보존 윈도우를 우선 확보하세요.`,
          source: 'ChromaDB RAG / ATT&CK v14',
        }),
      350,
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
                {m.source && (
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
          <div className="flex flex-wrap gap-1.5 pt-1">
            {quickReplies.map((q, i) => (
              <button
                key={q.label}
                onClick={() => handleQuick(i)}
                className="text-[11px] text-brand-blue bg-brand-blue/10 border border-brand-blue/25 rounded-full px-3 py-1 hover:bg-brand-blue/20"
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
          />
          <button onClick={handleSend} className="btn-primary btn-sm">
            전송
          </button>
        </div>
      </div>
    </>
  );
};

export default SherpaFab;
