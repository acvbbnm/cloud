/**
 * AttackChainCard — Zone 2 복합 가설 chain (Phase M.3, 2026-05-26, byungwoo).
 *
 * 설계서: `docs/evidence_tree_paradigm.md` §21.5 + §22.4.M.3.1
 *
 * 비전 (paradigm §21.1 ②):
 *   "복합 공격 chain — 사실 하나의 공격유형만 일어난다는건 말이 안되잖아.
 *    복합적으로 공격이 일어났을텐데 사고유형 하나만 확정해 가는 방식은 틀린 거 같은데."
 *
 * → Top 3 가설을 ATT&CK Kill Chain 시간순으로 가로 배치 (좌 PHISH → 우 RANSOM).
 *
 * 학술 정합: MITRE ATT&CK Kill Chain (TA0001 → TA0040 Impact).
 *
 * 동작
 * ----
 *   - 클릭 → onSelectHypothesis 콜백 → 해당 가설별 변별 단서로 NextCluePanel 필터링
 *   - 같은 가설 다시 클릭 → 선택 해제 (통합 후보 풀로 복귀)
 *   - 선택된 가설은 강조 테두리 + 글로우
 */
import { Fragment } from 'react';

import type { AttackChainStep } from '@/types/clueTree';
import type { IncidentType } from '@/types';

interface AttackChainCardProps {
  chain: AttackChainStep[];
  selectedHypothesis: IncidentType | null;
  onSelectHypothesis: (h: IncidentType | null) => void;
  /** 회귀 권고 — 별도 안내 줄. */
  regressSuggested?: boolean;
  /** 회귀 버튼 클릭 — 사용자가 Zone 1 으로 자발 복귀 의사 표시 (선택 해제 + 토스트). */
  onRequestRegress?: () => void;
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

/** Kill Chain phase → 단계 표기 (간략). */
const phaseLabel = (phase: number): string => {
  switch (phase) {
    case 1:
      return 'Initial Access';
    case 2:
      return 'Credential Access';
    case 3:
      return 'Privilege Esc.';
    case 4:
      return 'Discovery/Lateral';
    case 5:
      return 'Defense Evasion';
    case 6:
      return 'Exfiltration';
    case 7:
      return 'Impact';
    default:
      return '—';
  }
};

const AttackChainCard = ({
  chain,
  selectedHypothesis,
  onSelectHypothesis,
  regressSuggested = false,
  onRequestRegress,
  disabled = false,
}: AttackChainCardProps) => {
  if (chain.length === 0) {
    return (
      <div className="text-[10.5px] text-ink-500 font-mono px-2 py-2">
        chain 데이터 없음 — Zone 2 진입 대기
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* 회귀 권고 알림 */}
      {regressSuggested && (
        <div className="bg-amber-900/20 border border-amber-700/50 rounded px-2.5 py-1.5 text-[10.5px] text-amber-200 leading-5 flex items-start gap-2">
          <span className="font-bold shrink-0">⤺ 회귀 권고</span>
          <span className="flex-1">
            entropy 상승 또는 가설 격차 축소로 다시 모호해졌습니다. 광범위 탐색
            (Zone 1) 으로 돌아가 단서를 더 모으는 것을 권장합니다.
          </span>
          {onRequestRegress && (
            <button
              type="button"
              onClick={onRequestRegress}
              disabled={disabled}
              className="text-[10px] font-mono text-amber-200 hover:text-amber-100 border border-amber-600/50 hover:border-amber-400 px-1.5 py-0.5 rounded transition-colors shrink-0 disabled:opacity-40"
            >
              Zone 1 로 복귀
            </button>
          )}
        </div>
      )}

      {/* Chain 시각 — 좌 PHISH → 우 RANSOM */}
      <div className="flex items-stretch gap-1.5">
        {chain.map((step, i) => {
          const isSelected = selectedHypothesis === step.hypothesis;
          const color = INCIDENT_COLORS[step.hypothesis];
          const prob = (step.probability * 100).toFixed(1);
          return (
            <Fragment key={`${step.hypothesis}-${i}`}>
              <button
                type="button"
                onClick={() => {
                  if (disabled) return;
                  onSelectHypothesis(isSelected ? null : step.hypothesis);
                }}
                disabled={disabled}
                className={
                  'flex-1 min-w-0 text-left rounded-md border transition-all px-2 py-1.5 ' +
                  (isSelected
                    ? 'bg-ink-900/90 shadow-[0_0_0_1px_rgba(38,194,129,0.35)]'
                    : 'bg-ink-900/40 hover:bg-ink-900/70 border-ink-700/70 hover:border-ink-600') +
                  (disabled ? ' opacity-50 cursor-not-allowed' : ' cursor-pointer')
                }
                style={isSelected ? { borderColor: color } : undefined}
                title={`Kill Chain 단계 ${step.kill_chain_phase} · ${phaseLabel(step.kill_chain_phase)}`}
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: color }}
                  />
                  <span className="text-[8.5px] text-ink-500 font-mono uppercase tracking-wider truncate">
                    phase {step.kill_chain_phase}
                  </span>
                </div>
                <div
                  className="text-[11px] font-semibold leading-4 truncate"
                  style={{ color: isSelected ? color : 'rgba(225, 232, 240, 0.9)' }}
                >
                  {INCIDENT_KO[step.hypothesis]}
                </div>
                <div className="text-[10px] text-ink-400 font-mono mt-0.5">
                  {prob}%
                </div>
              </button>
              {/* 화살표 (마지막 아닌 경우) */}
              {i < chain.length - 1 && (
                <div className="self-center text-ink-600 text-[14px] leading-none px-0.5 select-none">
                  →
                </div>
              )}
            </Fragment>
          );
        })}
      </div>

      {/* 안내 줄 */}
      <div className="text-[9.5px] text-ink-500 leading-4 font-mono pt-0.5">
        {selectedHypothesis ? (
          <>
            <span style={{ color: INCIDENT_COLORS[selectedHypothesis] }}>
              {INCIDENT_KO[selectedHypothesis]}
            </span>
            {' '}변별 단서로 필터링 중 · 다시 클릭 또는 다른 가설 클릭으로 변경
          </>
        ) : (
          <>
            🗺 Zone 2 — Top 3 가설을 Kill Chain 시간순으로. 카드 클릭 → 해당 가설
            변별 단서로 후보 필터링
          </>
        )}
      </div>
    </div>
  );
};

export default AttackChainCard;
