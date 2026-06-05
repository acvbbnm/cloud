/**
 * ReconClueCard — Phase N.1 1차 정찰 단서 가이드 (2026-05-26, byungwoo).
 *
 * 설계서: `docs/evidence_tree_paradigm.md` §4.4 (Phase N.1 신설)
 *
 * 학술 정합
 * ---------
 *   - NIST SP 800-86 §4.1 Initial Triage
 *   - NIST SP 800-61r2 §3.2 Sources of Precursors and Indicators (IDS·SIEM·외부 신고)
 *
 * 동기 (paradigm §21 비전 ② 의 사전 단계):
 *   "단서 1개로 한 사고유형 99% 쏠림" 방지. 사고유형 무관 약한 정찰 단서
 *   2-4개를 먼저 누적해 posterior 를 약 비균등으로 만들어두고, 그 후 사용자
 *   자체 단서가 들어와도 한 쪽으로 급격히 기울지 않도록 함.
 *
 * 동작
 * ----
 *   - mount 시 `getReconOptions()` 호출 → Q1·Q2A 그룹 표시
 *   - 옵션 클릭 → `onAdopt(clueKey)` 콜백 → Step3 가 expand_tree 호출
 *   - **선택된 옵션(✓) 재클릭 → `onRetract(clueKey)` 콜백 → Step3 가 retract 호출**
 *     (2026-06-05 사용자 요청 — 1차 정찰 선택 취소/되돌리기 지원)
 *   - **`treeDepth >= 2` 이면 자동 dismiss** (사용자가 2개 이상 누적 후 자체 단서로).
 *     단, Step3 가 "다시 열기" 로 재노출 가능 → 해제로 되돌릴 수 있음.
 *   - 사용자 명시 X 버튼으로 영구 dismiss (sessionStorage)
 *
 * 디자인
 * ------
 *   - cold-start 직후 가장 눈에 띄게 — V-1 Step3 상단
 *   - 단서 채택 후 트랜지션으로 자연 사라짐
 */
import { useEffect, useState } from 'react';

import SourceTag from '@/components/SourceTag';
import { getReconOptions } from '@/api/clueTree';

import type { ReconClueGroup, ReconClueOption } from '@/types/clueTree';
import type { IncidentType } from '@/types';

interface ReconClueCardProps {
  /** 옵션 클릭 → 단서 채택 콜백. Step3 가 expand_tree 호출. */
  onAdopt: (clueKey: string, label: string) => Promise<void> | void;
  /** 이미 선택된 옵션 재클릭 → 단서 철회(선택 해제) 콜백. Step3 가 retract 호출.
   *  미지정 시 선택 옵션은 비활성(기존 동작) 유지. */
  onRetract?: (clueKey: string, label: string) => Promise<void> | void;
  /** 트리에 이미 채택된 clue_key set — 선택 표시(✓) + 재클릭 시 해제. */
  acceptedClueKeys: Set<string>;
  /** loading 중. */
  disabled?: boolean;
  /** 영구 dismiss 콜백 (sessionStorage). */
  onDismiss?: () => void;
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

/** V1.fix.7 — 옵션별 popup body 텍스트 생성. */
const buildOptionBody = (opt: ReconClueOption, isMeta: boolean): string => {
  if (isMeta) {
    return (
      '이 옵션은 사고 발견 경로 메타 정보입니다.\n' +
      '사고 유형 분류에 영향을 주지 않습니다 (가중치 평탄화 V1.fix.4).\n\n' +
      `근거: ${opt.weight_source || '—'}`
    );
  }
  // 가중치 순으로 정렬 (큰 순)
  const sorted = Object.entries(opt.weights)
    .filter(([, w]) => w > 0)
    .sort(([, a], [, b]) => b - a);
  const table = sorted
    .map(([h, w]) => {
      const ko = INCIDENT_KO[h as IncidentType] ?? h;
      const bar = '█'.repeat(Math.min(8, Math.round(w / 5)));
      return `  ${ko.padEnd(10, ' ')} +${String(w).padStart(2, ' ')}  ${bar}`;
    })
    .join('\n');
  return (
    '이 단서를 채택하면 아래 사고유형 신뢰도가 ↑\n' +
    '(베이지안 likelihood × prior 정규화 — 가중치가 높을수록 변별력 ↑)\n\n' +
    table +
    '\n\n근거: ' +
    (opt.weight_source || '—')
  );
};

const DISMISS_KEY = 'aisherpa.reconClueCard.dismissed';

export const hasDismissedRecon = (): boolean => {
  try {
    return window.sessionStorage.getItem(DISMISS_KEY) === '1';
  } catch {
    return false;
  }
};

const ReconClueCard = ({
  onAdopt,
  onRetract,
  acceptedClueKeys,
  disabled = false,
  onDismiss,
}: ReconClueCardProps) => {
  const [groups, setGroups] = useState<ReconClueGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [adoptingKey, setAdoptingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await getReconOptions();
        if (cancelled) return;
        setGroups(res.groups);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleClick = async (opt: ReconClueOption) => {
    if (disabled || adoptingKey) return;
    const accepted = acceptedClueKeys.has(opt.clue_key);
    // 이미 선택된 옵션 재클릭 → 해제(철회). onRetract 미지정이면 무시(기존 동작).
    if (accepted && !onRetract) return;
    setAdoptingKey(opt.clue_key);
    try {
      if (accepted) {
        await onRetract?.(opt.clue_key, opt.short_label);
      } else {
        await onAdopt(opt.clue_key, opt.short_label);
      }
    } finally {
      setAdoptingKey(null);
    }
  };

  const handleDismiss = () => {
    try {
      window.sessionStorage.setItem(DISMISS_KEY, '1');
    } catch {
      /* ignore */
    }
    onDismiss?.();
  };

  return (
    <div className="border border-amber-600/40 bg-amber-900/10 rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-amber-700/30 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-amber-300">
            1차 정찰 (사고 인지 단계)
          </span>
          {/* V1.fix.6 — 인라인 라벨 → 클릭 popup */}
          <SourceTag
            label="ⓘ 근거"
            title="1차 정찰 가이드 학술 근거"
            body={
              'NIST SP 800-86 §4.1 Initial Triage\n' +
              'NIST SP 800-61r2 §3.2 Sources of Precursors and Indicators\n\n' +
              '"어떻게 사고를 알게 됐나요?" 는 사고 발견 경로 메타 정보로 사고\n' +
              '유형 변별력 없음 (V1.fix.4 평탄화). "어떤 이상이 있었나요?" 옵션은\n' +
              '각 사고유형 단서 가중치 5~35로 약한 1차 정찰 신호.'
            }
          />
        </div>
        <button
          type="button"
          onClick={handleDismiss}
          className="text-[10px] text-amber-300/60 hover:text-amber-100 px-1.5 py-0.5 transition-colors"
          title="이 정찰 가이드 닫기"
        >
          ✕
        </button>
      </div>

      {loading && (
        <div className="px-3 py-3 text-[10.5px] text-ink-400 font-mono">정찰 옵션 로딩 중…</div>
      )}
      {error && (
        <div className="px-3 py-3 text-[10.5px] text-red-300 font-mono">에러: {error}</div>
      )}

      {!loading && !error && (
        <div className="px-3 py-2 space-y-3">
          {groups.map((g) => {
            // V1.fix.8 (2026-05-31) — Q1_inception 그룹은 백엔드에서 배제 (recon-options).
            // 만약 어떤 이유로 도착해도 메타 라벨 표시 (defensive UI).
            const isMetaGroup = g.node_id === 'Q1_inception';
            return (
              <div key={g.node_id}>
                <div className="text-[10.5px] text-ink-200 font-semibold mb-1 flex items-center gap-1.5">
                  <span>{g.question}</span>
                  {isMetaGroup && (
                    <span className="text-[9px] text-ink-400 font-mono border border-ink-700 px-1 py-px rounded">
                      메타 · 사후확률 영향 없음
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                  {g.options.map((opt) => {
                    const accepted = acceptedClueKeys.has(opt.clue_key);
                    // 선택 항목은 onRetract 가 있을 때 재클릭으로 해제 가능.
                    const removable = accepted && !!onRetract;
                    return (
                      <div
                        key={opt.clue_key}
                        className={
                          'group rounded border transition-all flex items-stretch ' +
                          (accepted
                            ? removable
                              ? 'bg-emerald-900/15 border-emerald-700/40 hover:border-red-500/60 hover:bg-red-900/15'
                              : 'bg-emerald-900/15 border-emerald-700/30 opacity-60'
                            : adoptingKey === opt.clue_key
                              ? 'bg-amber-900/30 border-amber-500/60'
                              : 'bg-ink-900/40 border-ink-700/60 hover:border-amber-500/60 hover:bg-amber-900/15')
                        }
                      >
                        <button
                          type="button"
                          onClick={() => handleClick(opt)}
                          disabled={disabled || (accepted && !removable) || adoptingKey !== null}
                          className="text-left px-2.5 py-1.5 flex-1 min-w-0 cursor-pointer disabled:cursor-not-allowed"
                          title={
                            removable
                              ? `${opt.short_label} — 클릭하면 선택 해제`
                              : opt.short_label
                          }
                        >
                          <div className="flex items-start gap-1.5">
                            {/* V1.fix.18 — 라벨 두 줄 wrap (이전: 한 줄로 옆 카드 영역 침범).
                                line-clamp-2 + break-words + 충분한 leading 으로 2줄 표시.
                                2026-06-03 — 사고유형 색상 배지 제거 (사용자 요청). */}
                            <span
                              className="text-[10.5px] text-ink-100 font-medium flex-1 min-w-0 leading-[1.3]"
                              style={{
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                                wordBreak: 'break-word',
                              }}
                            >
                              {accepted ? '✓ ' : '◯ '}
                              {opt.short_label}
                              {removable && (
                                <span className="text-[9px] text-red-300/80 ml-1 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity">
                                  · 클릭 해제
                                </span>
                              )}
                            </span>
                          </div>
                        </button>
                        {/* V1.fix.7 — 옵션 출처·신뢰도 영향 popup (채택과 무관) */}
                        <div className="border-l border-ink-700/60 flex items-center px-1.5">
                          <SourceTag
                            label="ⓘ"
                            align="right"
                            title={`${opt.short_label} — 신뢰도 영향`}
                            body={buildOptionBody(opt, isMetaGroup)}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* V1.fix.6 — 하단 메타 푸터 제거 (학술 설명은 상단 ⓘ 근거 popup 으로 통합) */}
    </div>
  );
};

export default ReconClueCard;
