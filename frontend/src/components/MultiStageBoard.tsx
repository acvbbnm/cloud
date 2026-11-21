/**
 * MultiStageBoard — MITRE Cloud Kill Chain 7단계 전체 시각화
 * (Phase N.4 + Phase P, 2026-05-27, KBW — 수사 보드 피드백 반영).
 *
 * 설계서: `docs/evidence_tree_paradigm.md` §23
 *
 * 변경 (2026-05-27, KBW):
 *   기존 — 확정된 사고유형들만 좌→우 시간순. confirmed 가 없으면 미노출.
 *   신규 — Initial Access → Impact 7단계를 항상 표시.
 *          확정(✓), 진행 중(▶), 미진입(·) 상태를 한눈에.
 *
 * 사용자 비전 (수사 보드 피드백):
 *   "마이터 클라우드 킬체인 전체 단계 표시"
 */
import type { IncidentType } from '@/types';

interface MultiStageBoardProps {
  confirmedHypotheses: IncidentType[];
  chainDescription: string;
  /** 현재 stage (1 = 첫 분석, 2+ = 후속 단계 추적 중). */
  stage: number;
  /** 사용자 [Zone 1 으로 회귀] 클릭 — 마지막 stage 취소. (선택) */
  onUndoLastStage?: () => void;
  /**
   * Phase P (KBW, 2026-05-27) — 현재 진행 중 가설(미확정, top-1).
   * Kill Chain 상 어느 단계가 "진행 중" 으로 보일지 결정.
   */
  currentPrimary?: IncidentType | null;
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

/** Kill Chain phase ID → 한국어/영어 라벨. */
interface KillChainPhase {
  phase: number;
  label: string;
  ko: string;
  /** 이 phase 에 속하는 사고유형들 (NCP/NHN 클라우드 컨텍스트). */
  incidents: IncidentType[];
}

/**
 * MITRE Cloud Kill Chain 7 phases — Initial Access ~ Impact.
 * 학술 정합: MITRE ATT&CK for Cloud (TA0001 → TA0040).
 */
const KILL_CHAIN: KillChainPhase[] = [
  { phase: 1, label: 'Initial Access',     ko: '초기 침투',    incidents: ['PHISH_INITIAL_ACCESS'] },
  { phase: 2, label: 'Credential Access',  ko: '자격증명 접근', incidents: ['CREDENTIAL_THEFT'] },
  { phase: 3, label: 'Privilege Esc.',     ko: '권한 상승',    incidents: ['PRIVILEGE_ESCALATION'] },
  { phase: 4, label: 'Discovery/Lateral',  ko: '내부 탐색',    incidents: ['INSIDER_THREAT', 'MISCONFIG_EXPOSURE'] },
  { phase: 5, label: 'Defense Evasion',    ko: '방어 회피',    incidents: ['AUDIT_LOG_TAMPERING'] },
  { phase: 6, label: 'Exfiltration',       ko: '데이터 유출',  incidents: ['DATA_EXFILTRATION'] },
  { phase: 7, label: 'Impact',             ko: '영향',         incidents: ['RANSOMWARE'] },
];

type PhaseStatus = 'confirmed' | 'current' | 'pending';

const MultiStageBoard = ({
  confirmedHypotheses,
  chainDescription,
  stage,
  onUndoLastStage,
  currentPrimary = null,
  disabled = false,
}: MultiStageBoardProps) => {
  const confirmedSet = new Set<IncidentType>(confirmedHypotheses);

  /** Kill Chain 단계별 상태 결정.
   *  - confirmed: 단계의 사고유형 중 하나가 confirmed 됨
   *  - current  : confirmed 가 아닌데 현재 top-1 가설이 이 단계에 속함
   *  - pending  : 그 외
   */
  const phaseStatus = (phase: KillChainPhase): PhaseStatus => {
    if (phase.incidents.some((h) => confirmedSet.has(h))) return 'confirmed';
    if (currentPrimary && phase.incidents.includes(currentPrimary)) return 'current';
    return 'pending';
  };

  /** 단계 안에서 표시 색 — confirmed 라면 해당 가설 색, current 면 currentPrimary 색, else 회색. */
  const phaseColor = (phase: KillChainPhase, status: PhaseStatus): string => {
    if (status === 'confirmed') {
      const h = phase.incidents.find((x) => confirmedSet.has(x));
      return h ? INCIDENT_COLORS[h] : '#7A8294';
    }
    if (status === 'current' && currentPrimary) {
      return INCIDENT_COLORS[currentPrimary];
    }
    return '#3A4250';
  };

  /** 단계 안에서 표시 라벨 — confirmed 면 그 가설 한국어, current 면 top-1 한국어, else 단계 한국어. */
  const phaseDisplayText = (phase: KillChainPhase, status: PhaseStatus): string => {
    if (status === 'confirmed') {
      const h = phase.incidents.find((x) => confirmedSet.has(x));
      return h ? INCIDENT_KO[h] : phase.ko;
    }
    if (status === 'current' && currentPrimary) {
      return INCIDENT_KO[currentPrimary];
    }
    return phase.ko;
  };

  const headerText =
    confirmedHypotheses.length > 0
      ? `다단계 공격 추적 — Stage ${stage}`
      : 'MITRE Cloud Kill Chain — 전체 단계';

  return (
    <div className="border border-emerald-700/40 bg-emerald-900/10 rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-emerald-700/30 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-emerald-300">
            {headerText}
          </span>
          <span className="text-[9px] text-emerald-400/70 font-mono">
            MITRE ATT&CK for Cloud · TA0001 → TA0040
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
        {/* Full Kill Chain — 7 phases (좌→우 시간순). 항상 표시. */}
        <div className="flex items-stretch gap-1 overflow-x-auto">
          {KILL_CHAIN.map((phase, i) => {
            const status = phaseStatus(phase);
            const color = phaseColor(phase, status);
            const isLastVisible = i === KILL_CHAIN.length - 1;

            const baseCls =
              status === 'confirmed'
                ? 'bg-emerald-900/30 border-emerald-500/70 shadow-[0_0_0_1px_rgba(38,194,129,0.25)]'
                : status === 'current'
                ? 'bg-amber-900/20 border-amber-500/60 ring-1 ring-amber-400/30'
                : 'bg-ink-900/30 border-ink-700/40';

            const statusIcon =
              status === 'confirmed' ? '✓' : status === 'current' ? '▶' : '·';
            const statusColor =
              status === 'confirmed'
                ? '#34D399'
                : status === 'current'
                ? '#FBBF24'
                : '#6B7280';

            return (
              <div key={phase.phase} className="flex items-stretch gap-1 min-w-0 flex-1">
                <div
                  className={`min-w-0 rounded border px-2 py-1.5 transition-all flex-1 ${baseCls}`}
                  style={
                    status !== 'pending' ? { borderColor: color } : undefined
                  }
                  title={`Phase ${phase.phase} · ${phase.label} (${phase.ko})`}
                >
                  <div className="flex items-center gap-1 mb-0.5">
                    <span
                      className="text-[9px] font-bold w-3 text-center"
                      style={{ color: statusColor }}
                    >
                      {statusIcon}
                    </span>
                    <span className="text-[8.5px] text-ink-500 font-mono uppercase tracking-wider">
                      P{phase.phase}
                    </span>
                  </div>
                  <div
                    className="text-[10.5px] font-semibold leading-3 truncate"
                    style={{
                      color:
                        status === 'pending'
                          ? 'rgba(180, 190, 200, 0.55)'
                          : color,
                    }}
                  >
                    {phaseDisplayText(phase, status)}
                  </div>
                  <div className="text-[8.5px] text-ink-500 font-mono mt-0.5 truncate">
                    {phase.label}
                  </div>
                </div>
                {!isLastVisible && (
                  <div
                    className="self-center text-[10px] leading-none select-none"
                    style={{
                      color:
                        status === 'confirmed'
                          ? 'rgba(38, 194, 129, 0.7)'
                          : 'rgba(120, 130, 150, 0.35)',
                    }}
                  >
                    →
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Chain 한국어 설명 — confirmed 가 있을 때만 */}
        {chainDescription && chainDescription !== '(미확정)' && (
          <div className="text-[10.5px] text-ink-300 leading-4 pt-1 border-t border-emerald-700/20">
            <span className="text-emerald-400 font-mono mr-1.5">CHAIN:</span>
            <span className="text-ink-100 font-semibold">{chainDescription}</span>
          </div>
        )}

        {/* multi-stage 안내 또는 첫 진입 안내 */}
        {confirmedHypotheses.length >= 2 ? (
          <div className="text-[9.5px] text-emerald-300/70 leading-4 font-mono">
            <span className="font-semibold">복합 공격 chain 확정</span> — Mandiant
            2024 평균 dwell time 16일 · 5-7단계 패턴 정합. V-7 보고서 자동 multi-stage.
          </div>
        ) : confirmedHypotheses.length === 0 ? (
          <div className="text-[9.5px] text-ink-400/80 leading-4 font-mono">
            ▶ 사고유형 확정 시 해당 단계가 ✓ 로 표시됩니다 · ▶ 는 현재 top-1 가설의
            예상 단계
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default MultiStageBoard;
