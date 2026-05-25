/**
 * 다음 단서 제안 패널 — V-1 Step 2 Discovery Loop 우측 (청사진 §2 F-3).
 *
 * 현재 가설 점수 분포를 기반으로 "어떤 단서를 추가하면 가설을 좁힐 수 있는지" 제안.
 *
 * 3 모드 — 우선순위:
 *   1. **IG 모드 (Phase D, 2026-05-25)**: `igCandidates` prop 제공 시 —
 *      백엔드 Information Gain 정렬 후보 + 게이지 + rationale + outcome_flags badge.
 *      paradigm doc §7 + §16 정합. Phase E 에서 Step3_Discovery 가 ClueTree
 *      응답을 전달함.
 *   2. **legacy 백엔드 응답 모드**: `suggestions` (NextClueSuggestion[]) — additive·bayesian.
 *   3. **클라이언트 휴리스틱 fallback**: 상위 2개 사고유형 별 권장 단서.
 *
 * 학술 근거: Shannon 1948 IG · BAN(IEEE 2023) marginalization · Google Chronicle
 *   Rule-to-Outcome (PDF §17.A) outcome_flags 정형화.
 */
import type { ClueType, HypothesisScores, IncidentType, NextClueSuggestion } from '@/types';
import type { ClueCandidate } from '@/types/clueTree';

interface NextCluePanelProps {
  scores: HypothesisScores;
  /** 백엔드 응답이 있으면 그것을 우선 표시. 없으면 클라이언트 휴리스틱. */
  suggestions?: NextClueSuggestion[];
  onPickClueType?: (type: ClueType) => void;

  // ── Phase D — IG 모드 props ──
  /**
   * Evidence Tree IG 후보 (Phase B `/api/clue-tree/*` 응답).
   * 제공 시 legacy heuristic / suggestions 모두 무시하고 IG UI 단독 노출.
   */
  igCandidates?: ClueCandidate[];
  /**
   * IG 후보 클릭 핸들러 — 단서 채택 (Step3_Discovery 가 expand 호출).
   */
  onAdoptCandidate?: (candidate: ClueCandidate) => void;
  /**
   * 현재 사후확률 entropy (bits). 헤더에 표시.
   * paradigm §16 — 5/3/2 동적 후보 K 기준.
   */
  entropyBits?: number;
  /**
   * 클릭 비활성 (loading 중).
   */
  disabled?: boolean;
  /**
   * 후보 재계산 트리거 — 새로고침 버튼 클릭 핸들러.
   */
  onRefreshCandidates?: () => void;
  /**
   * Phase H.4 — 백엔드 scoring_mode ('bayes_net' 시 BN 활성 hint 표시).
   */
  scoringMode?: 'additive' | 'bayesian' | 'evidence_tree' | 'bayes_net';
}

const INCIDENT_TYPE_KO: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '자격증명 탈취',
  PRIVILEGE_ESCALATION: '권한 상승',
  DATA_EXFILTRATION: '데이터 유출',
  AUDIT_LOG_TAMPERING: '감사 로그 변조',
  // dev3 C-1 신규 4종 (MULTI_CSP_LATERAL 2026-05-19 제거)
  RANSOMWARE: '랜섬웨어',
  MISCONFIG_EXPOSURE: '설정 오류 노출',
  PHISH_INITIAL_ACCESS: '피싱 초기 침투',
  INSIDER_THREAT: '내부자 위협',
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
  // MULTI_CSP_LATERAL 휴리스틱은 2026-05-19 제거. 환경 변수 multi_cloud 만 보존.
  //  dev3 C-1 신규 4종 
  RANSOMWARE: [
    {
      question: '랜섬 노트 또는 비표준 확장자(.locked/.encrypted) 발견된 객체?',
      hint_type: 'HASH',
      rationale: 'MITRE T1486 Data Encrypted for Impact 직접 증거',
    },
    {
      question: '대량 PutObject 발생 시각?',
      hint_type: 'TIME_WINDOW',
      rationale: 'T1486 + T1490 (Inhibit System Recovery) 결합 시그널',
    },
  ],
  MISCONFIG_EXPOSURE: [
    {
      question: '외부 공개로 설정된 Object Storage 컨테이너?',
      hint_type: 'SERVICE',
      rationale: 'CSA #3 Misconfiguration — public bucket 탐지',
    },
    {
      question: '외부 노출 자원의 공인 IP?',
      hint_type: 'IP_ADDRESS',
      rationale: 'T1190 Exploit Public-Facing Application 단서',
    },
  ],
  PHISH_INITIAL_ACCESS: [
    {
      question: '피싱 메일 URL 또는 첨부 해시?',
      hint_type: 'HASH',
      rationale: 'T1566 Phishing 직접 증거 — phishing kit 매칭',
    },
    {
      question: '의심 도메인 또는 신규 등록 도메인?',
      hint_type: 'DOMAIN',
      rationale: 'typo-squatting · DGA 패턴 — T1566.001 보강',
    },
  ],
  INSIDER_THREAT: [
    {
      question: '권한 변경 또는 휴면 계정 활성화한 내부 사용자?',
      hint_type: 'ACCOUNT',
      rationale: 'KISA §3.3 불법적 자원 사용 + MITRE T1078 직접 증거',
    },
    {
      question: '비정상 시각 또는 정상 업무 시간 내부 IP 접근?',
      hint_type: 'IP_ADDRESS',
      rationale: '내부자 위협의 가장 강한 시그널 — 정상 시간대 활동',
    },
  ],
};

// ── Phase D — outcome_flags badge 표기 헬퍼 ──

const outcomeFlagBadgeColor = (flag: string): string => {
  // 위험/공격 시그널 → red, 인증/계정 → amber, 출처/익명 → blue, 기본 → teal
  if (/Anonymized|Foreign|Phishing|Ransomware|Tampered|Exfiltration/i.test(flag)) {
    return 'bg-red-900/40 text-red-300 border-red-700/50';
  }
  if (/Mfa|Auth|Account|Privileged|Privilege|Creation|Dormant/i.test(flag)) {
    return 'bg-amber-900/40 text-amber-300 border-amber-700/50';
  }
  if (/Source|Off|Hours|Burst|Service/i.test(flag)) {
    return 'bg-blue-900/40 text-blue-300 border-blue-700/50';
  }
  return 'bg-emerald-900/30 text-emerald-300 border-emerald-700/50';
};

const formatFlagLabel = (key: string, value: unknown): string => {
  // "outcomeIsAnonymizedSource" → "AnonymizedSource"
  const stripped = key.replace(/^outcome/, '');
  if (typeof value === 'boolean') return stripped;
  return `${stripped}: ${String(value)}`;
};

const NextCluePanel = ({
  scores,
  suggestions,
  onPickClueType,
  igCandidates,
  onAdoptCandidate,
  entropyBits,
  disabled,
  onRefreshCandidates,
  scoringMode,
}: NextCluePanelProps) => {
  // ── Phase D — IG 모드 (최우선) ──
  if (igCandidates) {
    return (
      <div className="border-t border-ink-700/40 pt-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider">
            다음 단서 후보 · IG 정렬
            {scoringMode === 'bayes_net' && (
              <span className="ml-1.5 text-[8.5px] font-mono text-purple-300 normal-case tracking-normal border border-purple-700/50 bg-purple-900/30 rounded px-1 py-px">
                BN
              </span>
            )}
            {entropyBits !== undefined && (
              <span className="ml-2 text-[9.5px] normal-case tracking-normal text-ink-500">
                entropy {entropyBits.toFixed(2)} bits · {igCandidates.length}개
              </span>
            )}
          </span>
          {onRefreshCandidates && (
            <button
              type="button"
              onClick={onRefreshCandidates}
              disabled={disabled}
              title="후보 재계산"
              className="text-[9.5px] font-mono text-brand-teal hover:text-brand-tealDark border border-brand-teal/40 hover:border-brand-tealDark px-1.5 py-0.5 transition-colors disabled:opacity-40"
            >
              ↻ 재계산
            </button>
          )}
        </div>

        {igCandidates.length === 0 ? (
          <div className="bg-amber-900/15 border border-amber-700/40 rounded px-2.5 py-2 text-[10.5px] text-amber-200 leading-5">
            🔦 <span className="font-semibold">첫 단서 입력 대기 중</span>
            <div className="text-[9.5px] text-ink-400 mt-1 leading-4">
              Uniform prior 상태 — 좌측 <span className="text-brand-teal">단서 직접 입력</span>{' '}
              또는 <span className="text-brand-teal">부분 로그 분석</span> 으로
              시작하면 변별력 있는 IG 후보가 등장합니다.
            </div>
          </div>
        ) : (
          <p className="text-[9.5px] text-ink-500 leading-4 mb-2">
            Information Gain (Shannon 1948 + Pearl marginalization) 큰 순.
            각 막대는 정규화된 변별력 — 클릭 시 단서 채택.
          </p>
        )}

        <ul className="space-y-1.5">
          {igCandidates.map((c, i) => {
            // 정규화 게이지 (max 기준)
            const maxIg = Math.max(...igCandidates.map((x) => x.expected_info_gain), 0.0001);
            const pct = Math.max(8, Math.min(100, (c.expected_info_gain / maxIg) * 100));
            const flagEntries = c.outcome_flags
              ? Object.entries(c.outcome_flags).slice(0, 4)
              : [];

            return (
              <li
                key={c.candidate_id}
                className={`bg-ink-900/60 border border-ink-700/70 rounded-lg px-2.5 py-2 transition-colors ${
                  disabled
                    ? 'opacity-50'
                    : 'hover:border-brand-teal/60 hover:bg-ink-900/80 cursor-pointer'
                }`}
                onClick={() => {
                  if (!disabled && onAdoptCandidate) onAdoptCandidate(c);
                }}
                role="button"
                tabIndex={disabled ? -1 : 0}
                onKeyDown={(e) => {
                  if (disabled) return;
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onAdoptCandidate?.(c);
                  }
                }}
              >
                <div className="flex items-start gap-1.5 mb-1">
                  <span className="text-[10px] text-ink-500 mt-0.5 font-mono">
                    #{i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] text-ink-100 font-semibold leading-4">
                      {c.label}
                    </div>
                    <div className="text-[9.5px] text-ink-500 font-mono mt-0.5">
                      {c.category} · {c.clue_key}
                    </div>
                  </div>
                  <span className="text-[9.5px] text-brand-teal font-mono shrink-0">
                    IG {c.expected_info_gain.toFixed(3)}b
                  </span>
                </div>

                {/* IG 정규화 게이지 */}
                <div className="relative h-1.5 rounded-full bg-ink-950/80 overflow-hidden mb-1.5">
                  <div
                    className="absolute inset-y-0 left-0 bg-brand-teal/70 transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>

                {c.rationale && (
                  <div className="text-[9.5px] text-ink-400 leading-4 mb-1">
                    {c.rationale}
                  </div>
                )}

                {/* Phase H.4 — ATT&CK 기법 badge (clue_to_attack 매핑) */}
                {c.techniques && c.techniques.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-1">
                    {c.techniques.slice(0, 4).map((t) => (
                      <span
                        key={t}
                        className="text-[8.5px] font-mono border border-purple-700/55 bg-purple-900/30 text-purple-200 px-1 py-px rounded"
                        title={`ATT&CK 기법 ${t}`}
                      >
                        {t}
                      </span>
                    ))}
                    {c.techniques.length > 4 && (
                      <span className="text-[8.5px] font-mono text-ink-500">
                        +{c.techniques.length - 4}
                      </span>
                    )}
                  </div>
                )}

                {/* outcome_flags badge (PDF §17.A Google Chronicle) */}
                {flagEntries.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {flagEntries.map(([k, v]) => (
                      <span
                        key={k}
                        className={`text-[8.5px] font-mono border px-1 py-px rounded ${outcomeFlagBadgeColor(k)}`}
                        title={`${k} = ${JSON.stringify(v)}`}
                      >
                        {formatFlagLabel(k, v)}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    );
  }

  // ── legacy: 백엔드 응답 suggestions, 없으면 휴리스틱 ──
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
             다음 단서 제안
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
           다음 단서 제안
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
         다음 단서 제안 ({suggestions.length})
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
