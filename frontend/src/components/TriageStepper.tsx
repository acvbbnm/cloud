/**
 * 결정 트리 답변 타임라인 스테퍼 — V-1 Step 2 Discovery Loop (§4-5).
 *
 * Q1✓ csp_alert → Q2A✓ 비정상로그인 → Q3✓ 실패→성공 → ▷ Q4 진행 중
 *
 * 각 단계 클릭 시 해당 노드로 되돌아가기 (답변 수정 → 점수 재계산).
 * 점수 90+ 시 조기 종료 인라인 카드 표시 (§4-6).
 *
 * 학술 근거: NIST SP 800-61r2 §3.2 Triage 6단계 + 의료 감별진단 진행 타임라인.
 */
import type { HypothesisScores, IncidentType } from '@/types';

interface CompletedPathEntry {
  node_id: string;
  selected_option_ids: string[];
}

interface TriageStepperProps {
  completedPath: CompletedPathEntry[];
  currentNodeId: string | null;
  hypothesisScores: HypothesisScores;
  isTerminal: boolean;
  onStepClick?: (nodeId: string, stepIndex: number) => void;
  onEarlyConfirm?: () => void;
  onContinue?: () => void;
}

const NODE_SHORT_LABELS: Record<string, string> = {
  Q1_inception: 'Q1 인지경로',
  Q2A_alert_type: 'Q2A 알람',
  Q2B_report_content: 'Q2B 신고',
  Q2C_audit_pattern: 'Q2C 감사',
  Q2D_anomaly_form: 'Q2D 이상',
  Q2E_minimal_checklist: 'Q2E 불명',
  Q3_additional_context: 'Q3 정황',
  Q4_CRED: 'Q4 MFA',
  Q4_RANSOM: 'Q4 백업',
  Q4_MISCFG: 'Q4 변경',
  Q4_INSIDER: 'Q4 직무',
  Q5_CRED: 'Q5 행위자',
  Q5_RANSOM: 'Q5 범위',
  Q5_MISCFG: 'Q5 주체',
  Q5_INSIDER: 'Q5 가시성',
  Q6_CRED: 'Q6 후속',
  Q6_RANSOM: 'Q6 랜섬',
  Q6_MISCFG: 'Q6 민감도',
  Q6_INSIDER: 'Q6 사후',
  T_evaluate: '평가',
};

const INCIDENT_TYPE_KO: Record<string, string> = {
  CREDENTIAL_THEFT: '자격증명 탈취',
  PRIVILEGE_ESCALATION: '권한 상승',
  DATA_EXFILTRATION: '데이터 유출',
  AUDIT_LOG_TAMPERING: '감사 로그 변조',
  RANSOMWARE: '랜섬웨어',
  MISCONFIG_EXPOSURE: '설정 오류 노출',
  PHISH_INITIAL_ACCESS: '피싱 초기 침투',
  INSIDER_THREAT: '내부자 위협',
};

const EARLY_TERMINATION_THRESHOLD = 90;

const getTopHypothesis = (
  scores: HypothesisScores,
): { type: IncidentType; score: number } | null => {
  let top: { type: IncidentType; score: number } | null = null;
  for (const [k, v] of Object.entries(scores)) {
    if (k === 'UNCLASSIFIED') continue;
    if (!top || v > top.score) {
      top = { type: k as IncidentType, score: v };
    }
  }
  return top;
};

const TriageStepper = ({
  completedPath,
  currentNodeId,
  hypothesisScores,
  isTerminal,
  onStepClick,
  onEarlyConfirm,
  onContinue,
}: TriageStepperProps) => {
  const top = getTopHypothesis(hypothesisScores);
  const showEarlyTermination =
    top &&
    top.score >= EARLY_TERMINATION_THRESHOLD &&
    !isTerminal &&
    currentNodeId !== null;

  if (completedPath.length === 0 && !currentNodeId) return null;

  return (
    <div className="space-y-2">
      {/* Stepper timeline */}
      <div className="flex items-center gap-1 flex-wrap text-[10.5px]">
        {completedPath.map((entry, i) => {
          const label = NODE_SHORT_LABELS[entry.node_id] ?? entry.node_id;
          const answerSummary =
            entry.selected_option_ids.length <= 2
              ? entry.selected_option_ids.join(', ')
              : `${entry.selected_option_ids.slice(0, 2).join(', ')}…`;
          return (
            <span key={entry.node_id} className="flex items-center gap-1">
              {i > 0 && <span className="text-ink-600">→</span>}
              <button
                onClick={() => onStepClick?.(entry.node_id, i)}
                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-brand-teal/10 border border-brand-teal/30 text-brand-teal hover:bg-brand-teal/20 transition-colors cursor-pointer"
                title={`${label}: ${entry.selected_option_ids.join(', ')} — 클릭하여 수정`}
              >
                <span className="text-[9px]">✓</span>
                <span className="font-medium">{label}</span>
                <span className="text-ink-400 text-[9px] max-w-[80px] truncate">
                  {answerSummary}
                </span>
              </button>
            </span>
          );
        })}

        {/* Current node indicator */}
        {currentNodeId && !isTerminal && (
          <span className="flex items-center gap-1">
            {completedPath.length > 0 && <span className="text-ink-600">→</span>}
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-brand-blue/10 border border-brand-blue/40 text-brand-blue animate-pulse">
              <span className="text-[9px]">▷</span>
              <span className="font-medium">
                {NODE_SHORT_LABELS[currentNodeId] ?? currentNodeId}
              </span>
              <span className="text-ink-400 text-[9px]">진행 중</span>
            </span>
          </span>
        )}

        {/* Terminal indicator */}
        {isTerminal && (
          <span className="flex items-center gap-1">
            {completedPath.length > 0 && <span className="text-ink-600">→</span>}
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/40 text-amber-400">
              <span className="text-[9px]">◆</span>
              <span className="font-medium">평가 완료</span>
            </span>
          </span>
        )}
      </div>

      {/* Early termination inline card (§4-6) */}
      {showEarlyTermination && top && (
        <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-amber-500/8 border border-amber-500/30 text-[11.5px]">
          <span className="text-amber-300 font-semibold whitespace-nowrap">
            🎯 {INCIDENT_TYPE_KO[top.type] ?? top.type} 신뢰도{' '}
            {Math.min(100, Math.round((top.score / 70) * 100))}%
          </span>
          <span className="text-ink-400 text-[10.5px]">
            더 질문하시겠습니까?
          </span>
          <div className="flex items-center gap-1.5 ml-auto flex-shrink-0">
            {onEarlyConfirm && (
              <button
                onClick={onEarlyConfirm}
                className="btn-primary btn-sm text-[10.5px] px-2.5 py-1"
              >
                지금 확정
              </button>
            )}
            {onContinue && (
              <button
                onClick={onContinue}
                className="btn-ghost btn-sm text-[10.5px] px-2.5 py-1"
              >
                계속 진행
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default TriageStepper;
