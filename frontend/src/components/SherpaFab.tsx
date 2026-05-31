/**
 * AI 셰르파 플로팅 — 2026-05-22 블룸버그 스타일.
 * 로봇 이모지·그라데이션·글로우 제거. 텍스트 라벨 + 각진 사각 패널.
 */
import { useState, useRef, useEffect, useMemo } from 'react';

import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

import { useSherpaStore } from '@/stores/useSherpaStore';
import { useCaseStore } from '@/stores/useCaseStore';
import { streamChat, getKbStats, getMappingGapAnalysis } from '@/api/sherpa';
import type { SherpaSource, IncidentType } from '@/types';

type QuickQuery = { label: string; query: string; kind?: 'missing-link' };

// 사고유형 한글 라벨 (다른 컴포넌트와 동일 — 공유 export 없어 로컬 정의 패턴 따름)
const INCIDENT_TYPE_KO: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '자격증명 탈취',
  PRIVILEGE_ESCALATION: '권한 상승',
  DATA_EXFILTRATION: '데이터 유출',
  AUDIT_LOG_TAMPERING: '감사 로그 변조',
  RANSOMWARE: '랜섬웨어',
  MISCONFIG_EXPOSURE: '설정 오류 노출',
  PHISH_INITIAL_ACCESS: '피싱 초기 침투',
  INSIDER_THREAT: '내부자 위협',
  UNCLASSIFIED: '미분류',
};

// "빠진 고리" 는 케이스 인지형 특수 액션 (handleMissingLink) — 추천 세트에 항상 포함.
const MISSING_LINK_QUERY = '현재 ATT&CK 매핑 결과에서 빠졌을 가능성이 높은 기법을 추정해줘.';

// 케이스 미연결/미분류 시 기본 추천.
const DEFAULT_QUICK_QUERIES: QuickQuery[] = [
  { label: '수집 갭', query: '현재 케이스의 수집 갭을 설명해줘. REQUIRED 등급 우선.' },
  { label: 'T1078 사례', query: 'T1078 Valid Accounts 의 클라우드 침해 사례와 탐지 포인트를 알려줘.' },
  { label: '빠진 고리', query: MISSING_LINK_QUERY, kind: 'missing-link' },
];

const formatSourceSummary = (sources: SherpaSource[] | undefined): string => {
  if (!sources || sources.length === 0) return '출처 없음';
  const types = Array.from(new Set(sources.map((s) => s.type))).join(' · ');
  return `${types} (${sources.length}건)`;
};

const SherpaFab = () => {
  const caseId = useCaseStore((s) => s.caseId);
  const incidentType = useCaseStore((s) => s.incidentType);

  // 케이스 사고유형에 맞춘 추천 — 사고유형 확정 전이거나 미연결이면 기본 세트.
  const quickQueries = useMemo<QuickQuery[]>(() => {
    if (incidentType && incidentType !== 'UNCLASSIFIED') {
      const ko = INCIDENT_TYPE_KO[incidentType];
      return [
        {
          label: '대표 기법',
          query: `${ko}(${incidentType}) 사고의 대표 ATT&CK 기법과 클라우드 탐지 포인트를 알려줘.`,
        },
        {
          label: '대응 절차',
          query: `${ko} 사고의 초동 대응 절차와 권장 플레이북을 알려줘.`,
        },
        { label: '빠진 고리', query: MISSING_LINK_QUERY, kind: 'missing-link' },
      ];
    }
    return DEFAULT_QUICK_QUERIES;
  }, [incidentType]);

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

  // 엔진 상태 — 배지에 실제 연결/모델 반영 (V-8 과 동일 쿼리키로 캐시 공유)
  const kbQuery = useQuery({ queryKey: ['sherpa', 'kb'], queryFn: getKbStats, staleTime: 60_000 });
  const engine = kbQuery.data?.engine;
  const llmOnline = engine?.engine === 'ollama';
  const modelLabel = engine?.model ? engine.model.toUpperCase() : 'LLM';

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, open]);

  /**
   * 빈 sherpa 메시지가 이미 push 된 상태에서 query 를 스트리밍한다.
   * (handleSend·handleMissingLink 공용 — 호출 전 user·빈 sherpa push + setIsStreaming(true) 가정)
   */
  const runStream = async (query: string) => {
    await streamChat(
      {
        caseId: caseId ?? null,
        sessionId: sessionId ?? null,
        query,
      },
      {
        onStart: (newSessionId, sources) => {
          if (!sessionId) setSessionId(newSessionId);
          updateLast({ sources, source: formatSourceSummary(sources) });
        },
        onDelta: (delta) => appendDelta(delta),
        onDone: (sanitized) => {
          // Phase 2.5 — sanitized 가 있으면 KB 외 T-id 가 [KB외:T1234] 로 라벨링된
          // 버전. raw stream 텍스트를 sanitized 로 교체하여 환각 라벨 노출.
          if (sanitized) {
            updateLast({ text: sanitized });
          }
          setIsStreaming(false);
        },
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

  const handleSend = async (q?: string) => {
    const text = (q ?? input).trim();
    if (!text || isStreaming) return;
    push({ role: 'user', text });
    push({ role: 'sherpa', text: '' });
    setInput('');
    setIsStreaming(true);
    await runStream(text);
  };

  /**
   * "빠진 고리" — 케이스 인지형. 채팅(case 무관 RAG)으로 바로 보내지 않고,
   * 현재 케이스의 ATT&CK 매핑 결과를 먼저 조회해 실제 상황에 따라 분기한다:
   *   - 케이스 없음        → 케이스/매핑 먼저 안내 (LLM 호출 안 함)
   *   - 매핑 0건           → V-3/V-4 먼저 안내 (실제 매핑 유무를 판별)
   *   - 매핑 있음          → 관측·누락·추가 기법 요약을 컨텍스트로 주입해 LLM 추정
   */
  const handleMissingLink = async () => {
    if (isStreaming) return;
    const display = '현재 ATT&CK 매핑 결과에서 빠졌을 가능성이 높은 기법을 추정해줘.';
    push({ role: 'user', text: display });
    push({ role: 'sherpa', text: '' });

    if (!caseId) {
      updateLast({
        text:
          '아직 분석할 케이스가 연결되지 않았습니다.\n' +
          '- V-1에서 사고 케이스를 생성하고, V-3 정규화·V-4 ATT&CK 매핑을 수행한 뒤 다시 시도해 주세요.\n' +
          '- 매핑 결과가 있어야 빠졌을 가능성이 높은 기법을 추정할 수 있습니다.\n\n' +
          '※ 최종 판단은 수사관께서 직접 수행해 주세요.',
      });
      return;
    }

    setIsStreaming(true);
    try {
      const gap = await getMappingGapAnalysis(caseId);
      if (!gap.observed_count) {
        updateLast({
          text:
            `현재 케이스(${gap.current_incident_type})에 ATT&CK 매핑된 이벤트가 아직 없습니다.\n` +
            '- V-3 정규화 → V-4 ATT&CK 매핑을 먼저 실행해 주세요.\n' +
            '- 매핑 결과가 쌓이면 빠졌을 가능성이 높은 기법을 추정해 드립니다.\n\n' +
            '※ 최종 판단은 수사관께서 직접 수행해 주세요.',
        });
        setIsStreaming(false);
        return;
      }

      // 케이스 매핑 결과 기반 결정론적 분석 — LLM 미사용 (gpt-oss 비결정적
      // fallback 회피 + CLAUDE.md "AI 는 판단 안 함" 정합. brief/suggest 와 동일 계열).
      const lines: string[] = [
        `현재 케이스 ATT&CK 매핑 분석 — 사고유형 ${gap.current_incident_type}, 관측 기법 ${gap.observed_count}건`,
        '',
      ];

      if (gap.current_incident_type === 'UNCLASSIFIED') {
        // 사고유형 미확정 — 기대 기법 목록이 없어 "누락" 계산 자체가 불가.
        // "누락 없음" 으로 오인되지 않도록 별도 안내 (후보 사고유형으로 유도).
        lines.push('■ 사고유형이 아직 확정되지 않아 "기대 기법 대비 누락"을 계산할 수 없습니다.');
        lines.push('  → 아래 후보 사고유형을 참고해 V-1 단서루프에서 사고유형을 확정하면');
        lines.push('     빠졌을 가능성이 높은 기법을 추정해 드립니다.');
      } else if (gap.current_missing?.length) {
        lines.push('■ 빠졌을 가능성이 높은 기법 (이 사고유형의 기대 기법 중 미관측)');
        gap.current_missing.forEach((t) =>
          lines.push(`  · ${t} — V-2 로그·V-6 히트맵에서 해당 기법 흔적을 우선 확인하세요.`),
        );
      } else {
        lines.push('■ 이 사고유형의 기대 기법은 모두 관측되었습니다 (명시적 누락 없음).');
      }
      lines.push('');

      if (gap.extra_techniques?.length) {
        lines.push('■ 현재 사고유형으로 설명되지 않는 추가 관측 기법');
        lines.push(`  · ${gap.extra_techniques.join(', ')}`);
        lines.push('  → 다른 전술 단계 또는 복합 공격 신호일 수 있어 사고유형 재검토 후보입니다.');
        lines.push('');
      }

      const topCandidates = (gap.candidate_types ?? [])
        .filter((c) => c.score_ratio > 0 && c.type !== gap.current_incident_type)
        .slice(0, 3);
      if (topCandidates.length) {
        lines.push('■ 함께 검토할 후보 사고유형 (관측 기법 일치도)');
        topCandidates.forEach((c) =>
          lines.push(`  · ${c.type}: ${c.matched}/${c.expected} 기법 일치`),
        );
        lines.push('');
      }

      lines.push(
        '※ 케이스의 ATT&CK 매핑 결과 기반 결정론적 분석입니다. 최종 판단은 수사관께서 직접 수행해 주세요.',
      );
      updateLast({ text: lines.join('\n'), source: '케이스 매핑 분석' });
      setIsStreaming(false);
    } catch (e) {
      const status = axios.isAxiosError(e) ? e.response?.status : undefined;
      if (status === 404) {
        // 케이스가 localStorage 엔 있지만 서버 DB 엔 없음 (stale — DB 리셋·다른 환경·만료).
        // chat/stream 의 stale caseId fallback 과 동일 취지 — 404 를 사용자에게 노출하지 않는다.
        updateLast({
          text:
            '연결된 케이스를 서버에서 찾을 수 없습니다 (만료되었거나 다른 환경의 케이스).\n' +
            '- V-1에서 사고 케이스를 새로 생성한 뒤 V-3 정규화·V-4 ATT&CK 매핑을 수행해 주세요.\n\n' +
            '※ 최종 판단은 수사관께서 직접 수행해 주세요.',
        });
      } else {
        updateLast({
          text:
            '매핑 분석 조회에 실패했습니다. 백엔드(/api/sherpa/validate-incident-type) 확인이 필요합니다.\n' +
            `(상세: ${e instanceof Error ? e.message : String(e)})`,
        });
      }
      setIsStreaming(false);
    }
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
            <span className="text-[10px] text-ink-500">
              {modelLabel} ·{' '}
              <span className={llmOnline ? 'text-brand-teal' : 'text-amber-400'}>
                {kbQuery.isLoading ? '확인 중…' : llmOnline ? 'ONLINE' : 'OFFLINE'}
              </span>
            </span>
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
                onClick={() => (q.kind === 'missing-link' ? handleMissingLink() : handleSend(q.query))}
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
