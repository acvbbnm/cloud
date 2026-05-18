/**
 * 다음 단서 제안 패널 — V-1 Step 2 Discovery Loop 우측 (청사진 §2 F-3).
 *
 * 현재 가설 점수 분포를 기반으로 "어떤 단서를 추가하면 가설을 좁힐 수 있는지" 제안.
 * 백엔드 /api/triage/analyze 가 next_clues 응답을 주면 그것을 표시.
 * 미구현 상태에서는 클라이언트 휴리스틱 — 상위 2개 사고유형 별 권장 단서.
 *
 * 학술 근거: next_clue_graph.json (사고유형 → 결정 단서 매핑).
 */
import type { ClueType, HypothesisScores, IncidentType, NextClueSuggestion } from '@/types';

interface NextCluePanelProps {
  scores: HypothesisScores;
  /** 백엔드 응답이 있으면 그것을 우선 표시. 없으면 클라이언트 휴리스틱. */
  suggestions?: NextClueSuggestion[];
  onPickClueType?: (type: ClueType) => void;
}

const INCIDENT_TYPE_KO: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '자격증명 탈취',
  PRIVILEGE_ESCALATION: '권한 상승',
  DATA_EXFILTRATION: '데이터 유출',
  AUDIT_LOG_TAMPERING: '감사 로그 변조',
  MULTI_CSP_LATERAL: '멀티 CSP 횡이동',
  UNCLASSIFIED: '미분류',
};

// 사고유형별 다음 단서 휴리스틱 — backend/data/triage/next_clue_graph.json 의 발췌본
const NEXT_CLUE_HEURISTIC: Partial<
  Record<IncidentType, Array<{ question: string; hint_type: ClueType; rationale: string }>>
> = {
  CREDENTIAL_THEFT: [
    {
      question: '실패→성공 인증 패턴의 IP 가 더 있나요?',
      hint_type: 'IP_ADDRESS',
      rationale: 'brute-force 신호 — Q3:fail_then_success 가중치 +25',
    },
    {
      question: '동시 다지역 로그인이 발생한 계정명?',
      hint_type: 'ACCOUNT',
      rationale: '자격증명 공유 신호 — Q3:multi_region_concurrent +15',
    },
  ],
  PRIVILEGE_ESCALATION: [
    {
      question: '비정상 권한 변경이 일어난 서비스명?',
      hint_type: 'SERVICE',
      rationale: 'Q2C:permission_changes 보강 +25',
    },
    {
      question: '신규 IAM 계정 명 또는 ID?',
      hint_type: 'ACCOUNT',
      rationale: '백도어 계정 식별 — Q2C:iam_burst 보강 +25',
    },
  ],
  DATA_EXFILTRATION: [
    {
      question: 'Object Storage 정책 변경 시각?',
      hint_type: 'TIME_WINDOW',
      rationale: 'Q3:storage_policy_change 보강 +25',
    },
    {
      question: '대량 다운로드 외부 IP?',
      hint_type: 'IP_ADDRESS',
      rationale: 'T1567 Exfiltration Over Web Service 단서',
    },
  ],
  AUDIT_LOG_TAMPERING: [
    {
      question: '감사 로그 비활성 시점?',
      hint_type: 'TIME_WINDOW',
      rationale: 'Q2A:audit_log_disabled +35 보강',
    },
    {
      question: 'Tracer/CloudTrail 변경한 계정?',
      hint_type: 'ACCOUNT',
      rationale: 'T1562.008 흔적 — Q2C:log_gap +30 보강',
    },
  ],
  MULTI_CSP_LATERAL: [
    {
      question: '양쪽 CSP 모두에서 등장한 IP?',
      hint_type: 'IP_ADDRESS',
      rationale: 'Q3:multi_region_concurrent + Q2B:multi_csp_suspicious',
    },
    {
      question: '양쪽 CSP 공유 사용자명·이메일?',
      hint_type: 'ACCOUNT',
      rationale: 'SSO 토큰 침해 신호',
    },
  ],
};

const NextCluePanel = ({
  scores,
  suggestions,
  onPickClueType,
}: NextCluePanelProps) => {
  // 우선: 백엔드 응답 suggestions, 없으면 휴리스틱
  if (!suggestions || suggestions.length === 0) {
    // 상위 2개 사고유형
    const top = (Object.keys(scores) as IncidentType[])
      .filter((t) => t !== 'UNCLASSIFIED' && scores[t] > 0)
      .map((t) => ({ type: t, score: scores[t] }))
      .sort((a, b) => b.score - a.score)
      .slice(0, 2);

    if (top.length === 0) {
      return (
        <div className="border-t border-ink-700/40 pt-3">
          <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-1.5">
            🧭 다음 단서 제안
          </div>
          <p className="text-[10.5px] text-ink-500 leading-5">
            결정 트리에 답변하면 가설별 권장 단서가 표시됩니다.
          </p>
        </div>
      );
    }

    return (
      <div className="border-t border-ink-700/40 pt-3">
        <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-1.5">
          🧭 다음 단서 제안
        </div>
        <p className="text-[10px] text-ink-500 mb-2">
          현재 상위 가설을 좁히려면 다음 단서를 입력하세요:
        </p>
        <div className="space-y-1.5">
          {top.map(({ type }) => {
            const hints = NEXT_CLUE_HEURISTIC[type] ?? [];
            return (
              <div
                key={type}
                className="bg-ink-900/60 border border-ink-700/70 rounded-lg px-2.5 py-1.5"
              >
                <div className="text-[10.5px] text-brand-teal font-semibold mb-1">
                  {INCIDENT_TYPE_KO[type]}
                </div>
                <ul className="space-y-0.5">
                  {hints.map((h, i) => (
                    <li key={i} className="text-[10.5px] text-ink-200 leading-5">
                      <button
                        onClick={() => onPickClueType?.(h.hint_type)}
                        className="text-left hover:text-brand-blue transition-colors w-full"
                        title={h.rationale}
                      >
                        <span className="text-ink-500 mr-1">·</span>
                        {h.question}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // 백엔드 응답 형식
  return (
    <div className="border-t border-ink-700/40 pt-3">
      <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-1.5">
        🧭 다음 단서 제안 ({suggestions.length})
      </div>
      <ul className="space-y-1.5">
        {suggestions.slice(0, 5).map((s, i) => (
          <li
            key={i}
            className="bg-ink-900/60 border border-ink-700/70 rounded-lg px-2.5 py-1.5"
          >
            <div className="flex items-start gap-1.5">
              <span className="text-[10px] text-ink-500 mt-0.5">
                #{s.priority ?? i + 1}
              </span>
              <div className="flex-1 min-w-0">
                <button
                  onClick={() => s.hint_clue_type && onPickClueType?.(s.hint_clue_type)}
                  className="text-left text-[11px] text-ink-200 leading-5 hover:text-brand-blue transition-colors"
                  title={s.action}
                >
                  {s.question}
                </button>
                <div className="text-[9.5px] text-ink-500 mt-0.5">{s.source}</div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default NextCluePanel;
