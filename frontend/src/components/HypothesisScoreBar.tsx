/**
 * 가설 점수 막대그래프 — V-1 Step 2 Discovery Loop 우측 패널.
 *
 * 5개 사고유형(UNCLASSIFIED 제외)의 점수를 내림차순 막대로 표시.
 * 임계값 (high_confidence=70, auto_skip_tree=90) 표시선 + 1·2위 강조.
 *
 * Phase K (2026-05-26 byungwoo) — inline 가이드 미리보기:
 *   각 row 클릭 시 onClickIncidentType(type) 호출. 부모가 /api/guide/preview
 *   호출 후 guidePreview prop 채움. 클릭된 행 아래 inline expand 영역 노출.
 *   paradigm doc §19 (Phase K) 정합.
 *
 * 학술 근거: docs/dev3/가중치_설계_근거.md + weights.json
 */
import {
  extractGuideBasedClueCandidates,
  type GuideClueMatch,
} from '@/utils/guideToClueMatcher';

import type { GuideV2Response, HypothesisScores, IncidentType } from '@/types';

interface HypothesisScoreBarProps {
  scores: HypothesisScores;
  /** 임계값 표시 — 기본 90/130 (E4 6단계 누적 정합, 2026-05-21) */
  highConfidence?: number;
  autoSkip?: number;
  /** 최대 막대 너비 기준 점수 (기본 180 — terminal_score, E4 정합) */
  maxScale?: number;
  /** 추천 결과의 primary/secondary 강조 (있으면 표시) */
  highlightPrimary?: IncidentType;
  highlightSecondary?: IncidentType;
  /** 노출할 최대 가설 수 (기본 2 — 사용자 요청 2026-05-25, 0 = 전부) */
  limit?: number;
  /** 카드 헤더 클릭 시 호출 — 사고유형 비교 풀 오버레이 토글용 (2026-05-25) */
  onExpand?: () => void;
  /** Phase 2.5 (2026-05-25) — 백엔드 응답의 scoring_mode.
   *  'bayesian' 이면 점수를 확률 (0~1 또는 0~100%) 로 해석, 막대 100% 만점. */
  scoringMode?: 'additive' | 'bayesian';

  // ── Phase K (2026-05-26 byungwoo) — inline 가이드 미리보기 ──
  /** 각 행 클릭 시 호출 — 부모가 /api/guide/preview 호출 + guidePreview 채움. */
  onClickIncidentType?: (type: IncidentType) => void;
  /** 현재 펼쳐진 사고유형 (있으면 해당 행 아래에 가이드 inline 표시). */
  expandedType?: IncidentType | null;
  /** 가이드 미리보기 데이터 (preview 응답). expandedType 일 때만 사용. */
  guidePreview?: GuideV2Response | null;
  /** 가이드 로딩 중 — inline 영역에 스피너 표시. */
  guideLoading?: boolean;
  /** 풀 가이드 모달 열기 — K.3 에서 부모가 모달 노출. */
  onOpenFullGuide?: (type: IncidentType) => void;
  /** Phase K.4 — 가이드 기반 단서 후보 [+] 클릭 시 부모가 expand_tree 호출. */
  onAdoptGuideClue?: (match: GuideClueMatch, sourceContext: string) => void;
  /** 이미 채택된 단서 키 — 가이드 매칭 시 중복 차단. */
  acceptedClueKeys?: Set<string>;
}

// ── Phase K — 인라인 가이드 미리보기 (행 아래 expand 영역) ──
interface InlineGuidePreviewProps {
  incidentType: IncidentType;
  preview: GuideV2Response | null;
  loading: boolean;
  onOpenFull?: (type: IncidentType) => void;
  /** Phase K.4 — 가이드 기반 단서 후보 클릭 시 부모(Step3) 가 expand 호출. */
  onAdoptGuideClue?: (match: GuideClueMatch, source_target: string) => void;
  /** 이미 채택된 단서 키 (중복 차단). */
  acceptedClueKeys?: Set<string>;
}

const InlineGuidePreview = ({
  incidentType,
  preview,
  loading,
  onOpenFull,
  onAdoptGuideClue,
  acceptedClueKeys,
}: InlineGuidePreviewProps) => {
  if (loading) {
    return (
      <div className="mt-1.5 mb-1 px-2 py-2 bg-ink-950/60 border border-ink-700/50 rounded text-[10px] text-ink-400 italic">
        가이드 미리보기 로딩 중…
      </div>
    );
  }
  if (!preview) {
    return (
      <div className="mt-1.5 mb-1 px-2 py-2 bg-ink-950/60 border border-ink-700/50 rounded text-[10px] text-ink-500 italic">
        가이드 미리보기 없음 — 다시 클릭해서 로드
      </div>
    );
  }

  const phases = preview.phases ?? {};
  const phaseKeys = Object.keys(phases);
  const completionPct =
    typeof preview.completionRate === 'number'
      ? Math.round(preview.completionRate * 100)
      : null;
  const envWarnings = preview.environment_warnings ?? [];

  return (
    <div
      className="mt-1.5 mb-1 px-2 py-2 bg-ink-950/70 border border-ink-700/60 rounded text-[10.5px] max-h-80 overflow-y-auto"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[9.5px] text-brand-teal font-mono uppercase tracking-wider">
          가설 가이드 미리보기 · {phaseKeys.length} phase
        </span>
        {completionPct !== null && (
          <span className="text-[9.5px] text-ink-400 font-mono">
            수집 {completionPct}%
          </span>
        )}
      </div>

      {phaseKeys.length === 0 ? (
        <p className="text-[10px] text-ink-500 italic">
          이 사고유형에 매칭되는 phase 없음
        </p>
      ) : (
        <ul className="space-y-1.5">
          {phaseKeys.map((phaseId) => {
            const phase = phases[phaseId];
            const targets = (phase.targets ?? []).slice(0, 3);
            if (targets.length === 0) return null;
            return (
              <li key={phaseId}>
                <div className="text-[10px] text-ink-300 font-semibold mb-0.5">
                  {phase.phase_name ?? phaseId}
                </div>
                <ul className="ml-2 space-y-0.5">
                  {targets.map((t) => (
                    <li
                      key={t.category_id}
                      className="flex items-start gap-1 text-[10px] text-ink-400 leading-4"
                    >
                      <span
                        className={`shrink-0 inline-block w-1.5 h-1.5 mt-1 rounded-full ${
                          t.evidence_role === 'REQUIRED'
                            ? 'bg-red-500/80'
                            : 'bg-amber-500/70'
                        }`}
                        title={t.evidence_role}
                      />
                      <span className="flex-1 min-w-0 truncate">
                        {t.category_name}
                        {t.collected && (
                          <span className="ml-1 text-emerald-400">✓</span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </li>
            );
          })}
        </ul>
      )}

      {envWarnings.length > 0 && (
        <div className="mt-2 pt-1.5 border-t border-ink-700/50 text-[9.5px] text-amber-300/80 leading-4">
          ⚠ 환경 경고 {envWarnings.length}건 — 풀 가이드 참조
        </div>
      )}

      {/* Phase K.4 — 가이드 기반 단서 후보 2개 (휴리스틱 매핑) */}
      {onAdoptGuideClue && (() => {
        const matches = extractGuideBasedClueCandidates(
          phases,
          acceptedClueKeys ?? new Set(),
          2,
        );
        if (matches.length === 0) return null;
        return (
          <div className="mt-2 pt-1.5 border-t border-ink-700/50">
            <div className="text-[9.5px] text-brand-teal font-semibold mb-1 uppercase tracking-wider">
              가이드 기반 추가 단서 후보 ({matches.length})
            </div>
            <ul className="space-y-1">
              {matches.map((m, i) => (
                <li key={i}>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onAdoptGuideClue(m, `phase ${incidentType}`);
                    }}
                    className="w-full text-left px-2 py-1 bg-brand-teal/5 hover:bg-brand-teal/10 border border-brand-teal/30 hover:border-brand-teal/60 rounded text-[10px] text-ink-200 transition-colors"
                    title={`${m.matched_by}=${m.matched_keyword} → ${m.clue_key}`}
                  >
                    <span className="inline-block text-[9px] font-mono text-brand-teal mr-1.5">
                      [+]
                    </span>
                    <span className="font-mono text-brand-teal/90">{m.clue_type}</span>
                    <span className="text-ink-500 mx-1">·</span>
                    <span className="text-ink-300">{m.matched_keyword}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        );
      })()}

      {onOpenFull && (
        <button
          type="button"
          onClick={() => onOpenFull(incidentType)}
          className="mt-2 w-full text-[10px] text-brand-teal hover:text-brand-tealDark border border-brand-teal/40 hover:border-brand-tealDark py-1 rounded transition-colors"
        >
          전체 가이드 보기 →
        </button>
      )}
    </div>
  );
};


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

const HypothesisScoreBar = ({
  scores,
  highConfidence = 90,
  autoSkip = 130,
  maxScale = 180,
  highlightPrimary,
  highlightSecondary,
  limit = 2,
  onExpand,
  scoringMode = 'additive',
  onClickIncidentType,
  expandedType,
  guidePreview,
  guideLoading,
  onOpenFullGuide,
  onAdoptGuideClue,
  acceptedClueKeys,
}: HypothesisScoreBarProps) => {
  // Phase 2.5 (P4) — 베이지안 모드: 점수가 사후확률 (0~1 또는 0~100) — 백분율 표시
  const isBayesian = scoringMode === 'bayesian';
  // 베이지안 모드 임계값: high_conf 60%, auto 65%, max 100% (Phase 3.5 fitted)
  const effHighConf = isBayesian ? 60 : highConfidence;
  const effAutoSkip = isBayesian ? 65 : autoSkip;
  const effMaxScale = isBayesian ? 100 : maxScale;

  // UNCLASSIFIED 제외, 점수 내림차순
  // 베이지안 모드: 백엔드 hypothesis_scores 가 0~1 확률 → 0~100 으로 정규화
  const normalize = (s: number) => (isBayesian ? Math.round(s * 100) : s);
  const allRows = (Object.keys(scores) as IncidentType[])
    .filter((t) => t !== 'UNCLASSIFIED')
    .map((type) => ({ type, score: normalize(scores[type]) }))
    .sort((a, b) => b.score - a.score);
  const rows = limit > 0 ? allRows.slice(0, limit) : allRows;
  const hiddenCount = allRows.length - rows.length;

  const pct = (s: number) => Math.min(100, (s / effMaxScale) * 100);
  // 점수 표시 — bayesian 은 "84%" 형식, additive 는 정수
  const formatScore = (s: number) => (isBayesian ? `${s}%` : `${s}`);

  return (
    <div
      onClick={onExpand}
      className={onExpand ? 'cursor-pointer hover:bg-ink-800/30 rounded -mx-1 px-1 py-1 transition-colors' : ''}
      title={onExpand ? '클릭 시 8종 사고유형 비교·근거 보기' : undefined}
      role={onExpand ? 'button' : undefined}
      tabIndex={onExpand ? 0 : undefined}
      onKeyDown={(e) => {
        if (onExpand && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onExpand();
        }
      }}
    >
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider">
          {isBayesian ? '사고유형 신뢰도' : '가설 점수'}
          {limit > 0 && allRows.length > 0 && ` · 상위 ${rows.length}`}
        </span>
        {onExpand ? (
          <span className="text-[9.5px] text-brand-teal hover:underline">
            전체 8종 비교 ⛶
          </span>
        ) : (
          hiddenCount > 0 && (
            <span className="text-[9.5px] text-ink-500">+{hiddenCount}개</span>
          )
        )}
      </div>

      <div className="space-y-1.5">
        {rows.map(({ type, score }) => {
          const isPrimary = type === highlightPrimary;
          const isSecondary = type === highlightSecondary;
          const isHigh = score >= effAutoSkip;
          const isMedium = score >= effHighConf && !isHigh;
          const isExpanded = expandedType === type;
          const isClickable = !!onClickIncidentType;
          const color = isPrimary
            ? 'bg-brand-teal'
            : isSecondary
            ? 'bg-brand-amber'
            : isHigh
            ? 'bg-red-500'
            : isMedium
            ? 'bg-amber-500'
            : 'bg-brand-blue/60';
          return (
            <div key={type} className="text-[11px]">
              <div
                className={`${
                  isClickable
                    ? 'cursor-pointer hover:bg-ink-800/40 -mx-1 px-1 py-0.5 rounded transition-colors'
                    : ''
                } ${isExpanded ? 'bg-ink-800/40 -mx-1 px-1 py-0.5 rounded' : ''}`}
                onClick={(e) => {
                  if (!isClickable) return;
                  e.stopPropagation();
                  onClickIncidentType?.(type);
                }}
                role={isClickable ? 'button' : undefined}
                tabIndex={isClickable ? 0 : undefined}
                onKeyDown={(e) => {
                  if (!isClickable) return;
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    e.stopPropagation();
                    onClickIncidentType?.(type);
                  }
                }}
                title={
                  isClickable
                    ? `${INCIDENT_TYPE_KO[type]} 가이드 미리보기 (클릭)`
                    : undefined
                }
              >
                <div className="flex items-center justify-between mb-0.5">
                  <span
                    className={`${
                      isPrimary
                        ? 'text-brand-teal font-semibold'
                        : isSecondary
                        ? 'text-brand-amber font-semibold'
                        : 'text-ink-300'
                    }`}
                  >
                    {INCIDENT_TYPE_KO[type]}
                    {isPrimary && ' '}
                    {isSecondary && ' '}
                    {isExpanded && (
                      <span className="ml-1 text-[9px] text-brand-teal">▼</span>
                    )}
                  </span>
                  <span className="font-mono text-ink-200 text-[10.5px]">
                    {formatScore(score)}
                  </span>
                </div>
                <div className="relative h-2 rounded-full bg-ink-900 overflow-hidden">
                  <div
                    className={`h-full transition-all ${color}`}
                    style={{ width: `${pct(score)}%` }}
                  />
                  {/* 임계선 — high_confidence */}
                  <div
                    className="absolute top-0 bottom-0 w-px bg-amber-400/40"
                    style={{ left: `${pct(effHighConf)}%` }}
                    title={
                      isBayesian
                        ? `사고유형 제시 ${effHighConf}%`
                        : `high_confidence ${effHighConf}점`
                    }
                  />
                  {/* 임계선 — auto_skip */}
                  <div
                    className="absolute top-0 bottom-0 w-px bg-red-400/40"
                    style={{ left: `${pct(effAutoSkip)}%` }}
                    title={
                      isBayesian
                        ? `자동 확정 ${effAutoSkip}%`
                        : `auto_skip ${effAutoSkip}점`
                    }
                  />
                </div>
              </div>

              {/* Phase K — 클릭된 행 아래 inline 가이드 미리보기 */}
              {isExpanded && (
                <InlineGuidePreview
                  incidentType={type}
                  preview={guidePreview ?? null}
                  loading={!!guideLoading}
                  onOpenFull={onOpenFullGuide}
                  onAdoptGuideClue={onAdoptGuideClue}
                  acceptedClueKeys={acceptedClueKeys}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* 임계값 범례 — 모드별 라벨 */}
      <div className="mt-2.5 text-[9.5px] text-ink-500 leading-4">
        <div>
          <span className="inline-block w-2 h-2 rounded-full bg-amber-400/60 mr-1" />
          {isBayesian
            ? `사고유형 제시 ${effHighConf}% — 사후확률 도달`
            : `high_confidence ${effHighConf}점 — 사고유형 제시`}
        </div>
        <div>
          <span className="inline-block w-2 h-2 rounded-full bg-red-400/60 mr-1" />
          {isBayesian
            ? `자동 확정 ${effAutoSkip}% + gap 20%p`
            : `auto_skip ${effAutoSkip}점 + gap 30 — 자동 확정`}
        </div>
        {isBayesian && (
          <div className="text-[9px] text-ink-600 mt-1">
            베이즈 모드 — Verizon DBIR prior + Laplace smoothing likelihood
          </div>
        )}
      </div>
    </div>
  );
};

export default HypothesisScoreBar;
