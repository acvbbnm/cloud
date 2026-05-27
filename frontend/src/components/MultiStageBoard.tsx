/**
 * MultiStageBoard — 다단계 공격 chain 시각화 (Phase N.4, 2026-05-26, byungwoo).
 *
 * 설계서: `docs/evidence_tree_paradigm.md` §23
 *
 * 사용자 비전 (2026-05-26):
 *   "특정 단계 도달 후 그 사고유형에서 시작해서 연관된 다른 공격도 찾아가기"
 *
 * 동작
 * ----
 *   confirmed_hypotheses 가 1개 이상이면 노출. 확정된 사고유형들을 ATT&CK Kill Chain
 *   시간순으로 가로 시각화 + 현재 진행 중 stage 표시 + Mandiant Dwell Time 라벨.
 *
 * 학술 정합
 * ---------
 *   - MITRE ATT&CK Flow (2023) — 단계 시퀀스
 *   - Mandiant M-Trends 2024 — 평균 16일 dwell, 5-7단계 chain
 */
import type { IncidentType } from '@/types';

interface MultiStageBoardProps {
  confirmedHypotheses: IncidentType[];
  chainDescription: string;
  /** 현재 stage (1 = 첫 분석, 2+ = 후속 단계 추적 중). */
  stage: number;
  /** 사용자 [Zone 1 으로 회귀] 클릭 — 마지막 stage 취소. (선택) */
  onUndoLastStage?: () => void;
  disabled?: boolean;
}

const INCIDENT_KO: Record<IncidentType, string> = {
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

const INCIDENT_COLORS: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '#5BA3F0',
  PRIVILEGE_ESCALATION: '#A56BE6',
  DATA_EXFILTRATION: '#E66BC2',
  AUDIT_LOG_TAMPERING: '#E68A6B',
  RANSOMWARE: '#E63B3B',
  MISCONFIG_EXPOSURE: '#E6A03B',
  PHISH_INITIAL_ACCESS: '#6BE69E',
  INSIDER_THREAT: '#3BC2E6',
  UNCLASSIFIED: '#7A8294',
};

const KILL_CHAIN_PHASE: Record<IncidentType, number> = {
  PHISH_INITIAL_ACCESS: 1,
  CREDENTIAL_THEFT: 2,
  PRIVILEGE_ESCALATION: 3,
  INSIDER_THREAT: 4,
  MISCONFIG_EXPOSURE: 4,
  AUDIT_LOG_TAMPERING: 5,
  DATA_EXFILTRATION: 6,
  RANSOMWARE: 7,
  UNCLASSIFIED: 99,
};

const PHASE_LABEL: Record<number, string> = {
  1: 'Initial Access',
  2: 'Credential Access',
  3: 'Privilege Escalation',
  4: 'Discovery/Lateral',
  5: 'Defense Evasion',
  6: 'Exfiltration',
  7: 'Impact',
};

const MultiStageBoard = ({
  confirmedHypotheses,
  chainDescription,
  stage,
  onUndoLastStage,
  disabled = false,
}: MultiStageBoardProps) => {
  if (confirmedHypotheses.length === 0) {
    return null;
  }

  return (
    <div className="border border-emerald-700/40 bg-emerald-900/10 rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-emerald-700/30 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-emerald-300">
            🔗 다단계 공격 추적 — Stage {stage}
          </span>
          <span className="text-[9px] text-emerald-400/70 font-mono">
            MITRE ATT&CK Flow · Mandiant M-Trends 2024
          </span>
        </div>
        {confirmedHypotheses.length > 0 && onUndoLastStage && (
          <button
            type="button"
            onClick={onUndoLastStage}
            disabled={disabled}
            className="text-[10px] text-emerald-300/60 hover:text-emerald-100 border border-emerald-700/40 hover:border-emerald-500/60 px-1.5 py-0.5 rounded transition-colors disabled:opacity-40"
            title="마지막 확정 가설 취소 — 클라이언트 표시만 (서버 상태 유지)"
          >
            ↶ 최근 단계 취소
          </button>
        )}
      </div>

      <div className="px-3 py-2.5 space-y-2">
        {/* Chain 시각화 — 좌→우 시간순 */}
        <div className="flex items-stretch gap-1.5 flex-wrap">
          {confirmedHypotheses.map((h, i) => {
            const color = INCIDENT_COLORS[h];
            const phase = KILL_CHAIN_PHASE[h];
            const isLast = i === confirmedHypotheses.length - 1;
            return (
              <div key={`${h}-${i}`} className="flex items-stretch gap-1.5">
                <div
                  className={
                    'min-w-0 rounded border px-2 py-1.5 transition-all ' +
                    (isLast
                      ? 'border-emerald-500/70 bg-emerald-900/30 shadow-[0_0_0_1px_rgba(38,194,129,0.25)]'
                      : 'border-ink-700/60 bg-ink-900/40')
                  }
                  style={isLast ? { borderColor: color } : undefined}
                >
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
                    <span className="text-[8.5px] text-ink-500 font-mono uppercase tracking-wider">
                      Phase {phase}
                    </span>
                    <span className="text-[8.5px] text-ink-600 font-mono">
                      ({PHASE_LABEL[phase] ?? '—'})
                    </span>
                  </div>
                  <div
                    className="text-[11.5px] font-semibold leading-4"
                    style={{ color }}
                  >
                    ✓ {INCIDENT_KO[h]}
                  </div>
                  <div className="text-[9px] text-ink-500 font-mono mt-0.5">
                    Stage {i + 1}
                  </div>
                </div>
                {!isLast && (
                  <div className="self-center text-emerald-500/70 text-[14px] leading-none select-none">
                    →
                  </div>
                )}
              </div>
            );
          })}
          {/* 다음 단계 안내 */}
          {confirmedHypotheses.length > 0 && (
            <div className="self-center text-ink-500 text-[10.5px] font-mono px-2">
              <span className="text-emerald-400 text-[14px] mr-1">→</span>
              Stage {stage} 추적 중…
            </div>
          )}
        </div>

        {/* Chain 한국어 설명 */}
        {chainDescription && chainDescription !== '(미확정)' && (
          <div className="text-[10.5px] text-ink-300 leading-4 pt-1 border-t border-emerald-700/20">
            <span className="text-emerald-400 font-mono mr-1.5">CHAIN:</span>
            <span className="text-ink-100 font-semibold">{chainDescription}</span>
          </div>
        )}

        {/* multi-stage 안내 */}
        {confirmedHypotheses.length >= 2 && (
          <div className="text-[9.5px] text-emerald-300/70 leading-4 font-mono">
            🔗 <span className="font-semibold">복합 공격 chain 확정</span> — Mandiant 2024
            평균 dwell time 16일 · 5-7단계 패턴 정합. V-7 보고서가 자동으로 multi-stage
            chain 으로 구성됩니다.
          </div>
        )}
      </div>
    </div>
  );
};

export default MultiStageBoard;
