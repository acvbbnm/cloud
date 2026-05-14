import { useEffect, useRef, useState } from 'react';

import { useMutation, useQuery } from '@tanstack/react-query';

import PageHeader from '@/components/PageHeader';
import Card from '@/components/Card';
import Badge from '@/components/Badge';

import { useSherpaStore } from '@/stores/useSherpaStore';
import { useCaseStore } from '@/stores/useCaseStore';
import { getKbStats, postChat } from '@/api/sherpa';

import type { SherpaSource } from '@/types';

const KB_TONE: Record<string, 'red' | 'amber' | 'teal' | 'blue' | 'purple' | 'gray'> = {
  ATTACK: 'purple',
  PLAYBOOK: 'teal',
  CSP_DOC: 'blue',
  CASE_DB: 'amber',
};

const KB_LABEL: Record<string, string> = {
  ATTACK: 'MITRE ATT&CK for Cloud',
  PLAYBOOK: '대응 플레이북',
  CSP_DOC: 'CSP 공식 문서',
  CASE_DB: '침해사고 사례 DB',
};

const QUICK_QUERIES = [
  'T1078.004 IAM 권한 탈취 사례 알려줘',
  'NCP Activity Tracer 90일 보존 정책',
  '데이터 유출 대응 플레이북 우선순위',
];

const V8Sherpa = () => {
  const caseId = useCaseStore((s) => s.caseId);

  const messages = useSherpaStore((s) => s.messages);
  const push = useSherpaStore((s) => s.push);
  const sessionId = useSherpaStore((s) => s.sessionId);
  const setSessionId = useSherpaStore((s) => s.setSessionId);

  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // KB 인덱스 + 엔진 상태 — caseId 무관, 서버 KB 카탈로그.
  const kbQuery = useQuery({
    queryKey: ['sherpa', 'kb'],
    queryFn: getKbStats,
    staleTime: 60_000,
  });

  // 자연어 질의 — POST /api/sherpa/chat
  const chatMutation = useMutation({
    mutationFn: postChat,
    onSuccess: (data) => {
      if (!sessionId) setSessionId(data.sessionId);
      push({
        role: 'sherpa',
        text: data.response,
        sources: data.sources,
        source: formatSourceSummary(data.sources),
      });
    },
    onError: () => {
      push({
        role: 'sherpa',
        text: '⚠ 셰르파 응답 실패. 백엔드(서버 /api/sherpa/chat) 연결 또는 KB 인덱스를 확인해 주세요.',
      });
    },
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const handleSend = (q?: string) => {
    const text = (q ?? input).trim();
    if (!text || chatMutation.isPending) return;
    push({ role: 'user', text });
    setInput('');
    chatMutation.mutate({
      caseId: caseId ?? null,
      sessionId: sessionId ?? null,
      query: text,
    });
  };

  const engine = kbQuery.data?.engine;
  const engineConnected = engine && engine.engine !== 'stub';

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        eyebrow="Helper · sLLM"
        title={
          <>
            AI <span className="grad-text">셰르파</span>
          </>
        }
        description="오프라인 sLLM + KB RAG. AI는 판단·결정하지 않고 검색·요약·제안만 수행합니다."
        meta={
          <div className="flex items-center gap-2">
            <span className="chip">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  engineConnected ? 'bg-brand-teal' : 'bg-amber-400'
                }`}
              />
              {engine ? `${engine.engine}${engineConnected ? '' : ' (깡통 모드)'}` : '연결 확인 중…'}
            </span>
            <span className="chip">KB {kbQuery.data?.total ?? '…'}건</span>
            <span className="chip">{messages.length} 메시지</span>
            {sessionId && (
              <span className="chip text-[10px]">
                <code className="text-ink-400 font-mono">{sessionId.slice(0, 12)}…</code>
              </span>
            )}
          </div>
        }
      />

      {/* 백엔드 응답 패널 (V-2~6 동일 스타일) */}
      <div className="max-w-[1280px] mx-auto w-full px-8 lg:px-12 pt-2">
        <div className="bg-ink-950/60 border border-ink-700/60 rounded-xl px-4 py-3 text-[11.5px] text-ink-300 flex items-center gap-4 flex-wrap">
          <b className="text-brand-teal">백엔드 응답 ✓</b>
          <span>
            caseId: <code className="text-ink-400 font-mono">{caseId ?? '— (케이스 미선택)'}</code>
          </span>
          <span>
            engine:{' '}
            <code className="text-ink-400 font-mono">{engine?.engine ?? '?'}</code>
            {engine?.note && <span className="text-ink-500 ml-1">· {engine.note}</span>}
          </span>
          <span>
            KB:{' '}
            {kbQuery.data
              ? Object.entries(kbQuery.data.byKb)
                  .map(([k, v]) => `${KB_LABEL[k] ?? k} ${v}`)
                  .join(' · ')
              : '로딩…'}
          </span>
        </div>
      </div>

      <div className="max-w-[1280px] mx-auto w-full px-8 lg:px-12 py-6 grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0 animate-fade-up">
        {/* 좌측: 채팅 패널 */}
        <div className="lg:col-span-2 panel flex flex-col p-0 min-h-0">
          <div className="px-5 py-4 border-b border-ink-700/60 flex items-center gap-3">
            <span className="w-10 h-10 rounded-2xl bg-sherpa-gradient flex items-center justify-center text-[18px]">
              🤖
            </span>
            <div>
              <b className="text-[14px]">AI 셰르파</b>
              <div className="text-[11px] text-ink-400">
                {engine?.model ?? 'template-based'} · 오프라인
              </div>
            </div>
            <span
              className={`ml-auto inline-flex items-center gap-1 text-[11px] ${
                engineConnected ? 'text-brand-teal' : 'text-amber-400'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  engineConnected ? 'bg-brand-teal' : 'bg-amber-400'
                }`}
              />
              {engineConnected ? '연결됨' : 'stub'}
            </span>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-3">
            {messages.map((m) =>
              m.role === 'sherpa' ? (
                <div
                  key={m.id}
                  className="bg-ink-950 border border-ink-700/70 rounded-2xl p-4 text-[12.5px] leading-7 max-w-[85%] animate-fade-up"
                >
                  <b className="text-brand-purple text-[11px]">AI 셰르파</b>
                  <div className="mt-1 whitespace-pre-wrap text-ink-100">{m.text}</div>
                  {m.sources && m.sources.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {m.sources.map((s) => (
                        <span
                          key={s.source_id}
                          title={s.source_id}
                          className="inline-flex items-center gap-1 text-[10.5px] bg-ink-900 border border-ink-700/70 rounded-full px-2 py-0.5"
                        >
                          <Badge tone={KB_TONE[s.type] ?? 'gray'} size="sm">
                            {s.type}
                          </Badge>
                          <span className="text-ink-300">{s.title || s.source_id}</span>
                        </span>
                      ))}
                    </div>
                  )}
                  {!m.sources && m.source && (
                    <div className="mt-2 text-[10px] text-ink-400">출처: {m.source}</div>
                  )}
                </div>
              ) : (
                <div
                  key={m.id}
                  className="ml-auto bg-cta-gradient text-white rounded-2xl px-4 py-2.5 text-[12.5px] max-w-[75%] text-right animate-fade-up shadow-glow"
                >
                  {m.text}
                </div>
              ),
            )}
            {chatMutation.isPending && (
              <div className="bg-ink-950 border border-ink-700/70 rounded-2xl p-4 text-[12px] text-ink-400 max-w-[60%] animate-pulse">
                <b className="text-brand-purple text-[11px]">AI 셰르파</b>
                <div className="mt-1">KB 검색 중…</div>
              </div>
            )}
          </div>

          {/* 빠른 질의 칩 */}
          <div className="px-3 pb-2 flex flex-wrap gap-1.5">
            {QUICK_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => handleSend(q)}
                disabled={chatMutation.isPending}
                className="text-[10.5px] px-2.5 py-1 rounded-full bg-ink-900 border border-ink-700/70 text-ink-300 hover:border-brand-blue/40 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {q}
              </button>
            ))}
          </div>

          <div className="border-t border-ink-700/60 p-3 flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="질문 입력 (예: T1078.004 사례, NCP Activity Tracer 보존 기간 등)"
              className="input"
              disabled={chatMutation.isPending}
            />
            <button
              onClick={() => handleSend()}
              disabled={chatMutation.isPending || !input.trim()}
              className="btn-primary disabled:opacity-50"
            >
              {chatMutation.isPending ? '검색…' : '전송'}
            </button>
          </div>
        </div>

        {/* 우측: KB 인덱스 + 안내 */}
        <div className="flex flex-col gap-3 overflow-y-auto pr-1">
          <Card title={<>📚 KB 인덱스 (RAG 입력)</>}>
            {kbQuery.isLoading ? (
              <div className="text-[12px] text-ink-400 py-2">로딩 중…</div>
            ) : kbQuery.isError ? (
              <div className="text-[12px] text-red-400 py-2">KB 통계 조회 실패</div>
            ) : kbQuery.data ? (
              <div className="text-[12px] text-ink-300 leading-7 space-y-1">
                {Object.entries(kbQuery.data.byKb).map(([k, v]) => (
                  <KbRow
                    key={k}
                    label={KB_LABEL[k] ?? k}
                    count={v}
                    tone={KB_TONE[k] ?? 'gray'}
                  />
                ))}
                <div className="pt-2 mt-2 border-t border-ink-700/40 text-[11px] text-ink-400">
                  총 <b className="text-ink-200">{kbQuery.data.total}</b>건 청크. 엔진:{' '}
                  <code className="text-ink-300 font-mono">{kbQuery.data.engine.engine}</code>
                </div>
                {kbQuery.data.engine.engine === 'stub' && (
                  <div className="text-[10.5px] text-amber-400/80 leading-5">
                    ※ 현재 키워드 매칭 + 템플릿 응답으로 동작 중. Ollama Llama 3.1 8B + ChromaDB
                    교체는 후속 작업.
                  </div>
                )}
              </div>
            ) : null}
          </Card>

          <Card title={<>🎯 활용 안내</>}>
            <div className="text-[11.5px] text-ink-300 leading-6 space-y-2">
              <p>
                질문은 <b>ATT&CK 기법 ID</b>(예: <code>T1078.004</code>), <b>CSP 서비스명</b>(예:
                "Activity Tracer", "Cloud Trail"), <b>사고 유형</b>(예: "권한 탈취", "데이터 유출")
                키워드를 포함하면 KB 검색 정확도가 올라갑니다.
              </p>
              <p className="text-ink-400">
                케이스가 선택된 상태(<code>caseId</code> 존재)에서는 V-5 수사 보드에서 노드 클릭 시
                해당 기법의 컨텍스트 브리핑(<code>/api/sherpa/brief</code>)이 자동으로 호출됩니다.
              </p>
              <p className="text-amber-400/90 text-[11px]">
                AI는 판단하지 않습니다 — 모든 응답은 KB 출처가 첨부되며, 최종 결정은 수사관이
                수행합니다.
              </p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

const formatSourceSummary = (sources: SherpaSource[] | undefined): string => {
  if (!sources || sources.length === 0) return '출처 없음';
  const types = Array.from(new Set(sources.map((s) => s.type))).join(' · ');
  return `${types} (${sources.length}건)`;
};

const KbRow = ({
  label,
  count,
  tone,
}: {
  label: string;
  count: number;
  tone: 'red' | 'amber' | 'teal' | 'blue' | 'purple' | 'gray';
}) => (
  <div className="flex items-center justify-between py-1 border-b border-ink-700/30 last:border-b-0">
    <span>{label}</span>
    <Badge tone={tone} size="sm">
      {count.toLocaleString()}건
    </Badge>
  </div>
);

export default V8Sherpa;
