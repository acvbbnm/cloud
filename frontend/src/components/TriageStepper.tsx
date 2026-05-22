/**
 * TriageStepper — V-1 Step 2 Discovery Loop 상단 timeline.
 *
 * E4 (2026-05-21): 결정 트리 6단계 (Q1~Q6) 진행 상태를 시각화.
 * 의료 감별진단의 "diagnostic timeline" 비유 + 답변 수정 진입점.
 *
 * 동작:
 *   - 완료된 노드는 ✓ + 선택한 옵션 요약 표시
 *   - 현재 노드는 ▷ + 강조
 *   - 미진행 노드는 회색 dot
 *   - 완료된 노드 클릭 시 onRevisit 콜백 호출 (해당 노드 재방문 — 점수 재계산)
 *
 * 학술 근거: docs/dev3/결정트리_업그레이드.md §4-5 (답변 timeline Stepper).
 */
import type { TriagePathEntry } from '@/types';

interface TriageStepperProps {
  completedPath: TriagePathEntry[];
  currentNodeId: string | null;
  isTerminal: boolean;
  onRevisit?: (nodeId: string) => void;
}

// 노드 ID → 표시 라벨 (간결한 단어)
const NODE_LABEL: Record<string, string> = {
  Q1_inception: '인지경로',
  Q2A_alert_type: 'CSP알람',
  Q2B_report_content: '외부신고',
  Q2C_audit_pattern: '감사패턴',
  Q2D_anomaly_form: '서비스이상',
  Q2E_minimal_checklist: '최소점검',
  Q3_CRED: '자격증명',
  Q3_DATA: '데이터노출',
  Q3_INSIDER: '내부자',
  Q3_IMPACT: '영향패턴',
  Q3_additional_context: '추가정황',
  Q4_CRED: '증거무결성',
  Q4_RANSOM: '백업무결성',
  Q4_MISCFG: '공개시점',
  Q4_INSIDER: '직무범위',
  Q5_CRED: '행위자',
  Q5_RANSOM: '영향범위',
  Q5_MISCFG: '변경주체',
  Q5_INSIDER: '가시성',
  Q6_CRED: '후속시그널',
  Q6_RANSOM: '랜섬노트',
  Q6_MISCFG: '민감도',
  Q6_INSIDER: '사후행동',
};

// 노드 ID → "Q번호" 표시 (1, 2, 3, 4, 5, 6)
const stageOf = (nid: string): number => {
  if (nid.startsWith('Q1')) return 1;
  if (nid.startsWith('Q2')) return 2;
  if (nid.startsWith('Q3')) return 3;
  if (nid.startsWith('Q4')) return 4;
  if (nid.startsWith('Q5')) return 5;
  if (nid.startsWith('Q6')) return 6;
  return 0;
};

const TriageStepper = ({
  completedPath,
  currentNodeId,
  isTerminal,
  onRevisit,
}: TriageStepperProps) => {
  // 6 stages — 각 stage 가 어느 노드인지 추적
  const completedByStage: Record<number, TriagePathEntry> = {};
  for (const p of completedPath) {
    const stg = stageOf(p.node_id);
    if (stg > 0) completedByStage[stg] = p;
  }

  const currentStage = currentNodeId ? stageOf(currentNodeId) : 0;
  const maxStage = isTerminal ? 6 : Math.max(currentStage, ...Object.keys(completedByStage).map(Number));

  const stages = [1, 2, 3, 4, 5, 6];

  return (
    <div className="panel p-3 border-l-[3px] border-l-brand-blue/60">
      <div className="flex items-center gap-2 mb-2">
        <span className="eyebrow text-brand-blue">진단 타임라인</span>
        <span className="text-[10px] text-ink-500">
          Q1 → Q6 (6단계 동적 분기 — NIST 800-61r2 + 의료 감별진단)
        </span>
      </div>

      <div className="flex items-center gap-1 flex-wrap">
        {stages.map((stg, i) => {
          const done = stg in completedByStage;
          const cur = stg === currentStage && !isTerminal;
          const inactive = stg > maxStage && !cur;
          const entry = completedByStage[stg];
          const label = entry ? NODE_LABEL[entry.node_id] ?? `Q${stg}` : `Q${stg}`;

          return (
            <div key={stg} className="flex items-center">
              <button
                type="button"
                onClick={() => {
                  if (done && entry && onRevisit) onRevisit(entry.node_id);
                }}
                disabled={!done}
                title={
                  done
                    ? `Q${stg} ${label} — 답변 수정 (점수 재계산)`
                    : cur
                    ? `Q${stg} ${label} — 진행 중`
                    : `Q${stg} 미진행`
                }
                className={`flex items-center gap-1.5 px-2 py-1 rounded-md border transition-all ${
                  done
                    ? 'bg-brand-teal/10 border-brand-teal/30 text-brand-teal hover:bg-brand-teal/20 cursor-pointer'
                    : cur
                    ? 'bg-brand-blue/15 border-brand-blue text-brand-blue shadow-glow'
                    : inactive
                    ? 'bg-ink-900/40 border-ink-800/40 text-ink-600 cursor-default'
                    : 'bg-ink-900/40 border-ink-700/40 text-ink-400 cursor-default'
                }`}
              >
                <span
                  className={`w-4 h-4 rounded-full flex items-center justify-center text-[9.5px] font-bold ${
                    done
                      ? 'bg-brand-teal text-ink-950'
                      : cur
                      ? 'bg-brand-blue text-white animate-pulse'
                      : 'bg-ink-800 text-ink-500'
                  }`}
                >
                  {done ? '✓' : cur ? '▷' : stg}
                </span>
                <span className="text-[10.5px] font-semibold">Q{stg}</span>
                <span className="text-[10px] opacity-70 truncate max-w-[7.5em]">
                  {label}
                </span>
              </button>

              {i < stages.length - 1 && (
                <span
                  className={`mx-0.5 w-2.5 h-px ${
                    stg < currentStage || stg in completedByStage
                      ? 'bg-brand-teal'
                      : 'bg-ink-700'
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {isTerminal && (
        <div className="text-[10.5px] text-brand-teal mt-2 font-semibold">
          ✓ 6단계 완료 — 우측 추천 결과 확인
        </div>
      )}
    </div>
  );
};

export default TriageStepper;
