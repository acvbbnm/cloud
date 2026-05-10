import { useEffect, useRef, useState } from 'react';

import PageHeader from '@/components/PageHeader';
import Card from '@/components/Card';
import Badge from '@/components/Badge';
import { useSherpaStore } from '@/stores/useSherpaStore';

const playbooks = [
  {
    title: 'IAM 권한 탈취 대응',
    techniques: ['T1078', 'T1098'],
    summary: '해외 IP 로그인 직후 권한 상승 패턴 — 즉시 계정 잠금 및 Access Key 회전을 권고합니다.',
  },
  {
    title: '데이터 유출 대응',
    techniques: ['T1530', 'T1537'],
    summary:
      'Object Storage 대용량 GET 이벤트가 단시간에 발생하면 Pre-signed URL 발급 이력과 외부 IP 트래픽을 함께 확인하세요.',
  },
  {
    title: '수집 갭 보강',
    techniques: ['T1071'],
    summary:
      'VPC Flow Log 미수집 시 네트워크 공격 경로 추적이 어렵습니다. NCP 콘솔에서 Flow Log를 활성화하고 30일 보존 윈도우 내 추출하세요.',
  },
];

const V8Sherpa = () => {
  const messages = useSherpaStore((s) => s.messages);
  const push = useSherpaStore((s) => s.push);
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    const q = input.trim();
    if (!q) return;
    push({ role: 'user', text: q });
    setInput('');
    window.setTimeout(
      () =>
        push({
          role: 'sherpa',
          text: `RAG 검색 결과: "${q}" 관련 ATT&CK 문서·NCP/NHN 매핑·과거 사고 사례를 종합하면, 해당 질의는 클라우드 권한 탈취 패턴과 연관됩니다. 90일 보존 윈도우 내 Activity Tracer / CloudTrail 이벤트를 우선 추출하시기 바랍니다.`,
          source: 'ChromaDB RAG · ATT&CK v14',
        }),
      400,
    );
  };

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        eyebrow="Helper · sLLM"
        title={
          <>
            AI <span className="grad-text">셰르파</span>
          </>
        }
        description="오프라인 sLLM(Llama 3.1 8B) + ChromaDB RAG. AI는 판단·결정하지 않고 검색·요약·제안만 수행합니다."
        meta={
          <div className="flex items-center gap-2">
            <span className="chip">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-teal" />
              모델 연결됨
            </span>
            <span className="chip">v14 ATT&CK</span>
            <span className="chip">{messages.length} 메시지</span>
          </div>
        }
      />

      <div className="max-w-[1280px] mx-auto w-full px-8 lg:px-12 py-8 grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0 animate-fade-up">
        <div className="lg:col-span-2 panel flex flex-col p-0 min-h-0">
          <div className="px-5 py-4 border-b border-ink-700/60 flex items-center gap-3">
            <span className="w-10 h-10 rounded-2xl bg-sherpa-gradient flex items-center justify-center text-[18px]">
              🤖
            </span>
            <div>
              <b className="text-[14px]">AI 셰르파</b>
              <div className="text-[11px] text-ink-400">sLLM Llama 3.1 8B · 오프라인</div>
            </div>
            <span className="ml-auto inline-flex items-center gap-1 text-[11px] text-brand-teal">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-teal" />
              연결됨
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
                  {m.source && (
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
          </div>

          <div className="border-t border-ink-700/60 p-3 flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="질문 입력 (예: T1078 사례, VPC Flow Log 수집 방법 등)"
              className="input"
            />
            <button onClick={handleSend} className="btn-primary">
              전송
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-3 overflow-y-auto pr-1">
          <Card title={<>🎯 추천 플레이북</>}>
            <div className="space-y-2.5">
              {playbooks.map((p) => (
                <div key={p.title} className="bg-ink-950 border border-ink-700/70 rounded-xl p-3.5 hover:border-brand-blue/40 transition-colors">
                  <div className="font-bold text-[13px] mb-1.5">{p.title}</div>
                  <div className="flex flex-wrap gap-1 mb-1.5">
                    {p.techniques.map((t) => (
                      <Badge key={t} tone="purple" size="sm">
                        {t}
                      </Badge>
                    ))}
                  </div>
                  <div className="text-[11.5px] text-ink-300 leading-6">{p.summary}</div>
                </div>
              ))}
            </div>
          </Card>

          <Card title={<>📚 KB 인덱스</>}>
            <div className="text-[12px] text-ink-300 leading-7 space-y-1">
              <KbRow label="ATT&CK Cloud v14" count={623} tone="purple" />
              <KbRow label="NCP Activity Tracer 매핑" count={412} tone="blue" />
              <KbRow label="NHN CloudTrail 매핑" count={398} tone="teal" />
              <KbRow label="KISA 침해사고 보고서 양식" count={1} tone="amber" />
              <KbRow label="OCSF 1.3 스키마 정의" count={1} tone="gray" />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
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
