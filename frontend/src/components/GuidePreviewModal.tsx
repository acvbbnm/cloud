/**
 * Phase K.3 — 풀 가이드 미리보기 모달 (2026-05-26 byungwoo).
 *
 * 사용자 결정 (paradigm doc §19.6): "클릭하면 팝업창처럼".
 * V-1 Step 3 트리아주 진행 중 상위 가설 카드의 [전체 가이드] 버튼 클릭 →
 * 본 모달이 트리 위에 오버레이로 열림. 닫으면 트리 컨텍스트 그대로 유지.
 *
 * GuideV2Response 의 전체 phases · environment_warnings · applied_modifiers ·
 * source_standards · seed_targets 모두 노출. /api/guide/v2 화면과 동일한
 * 데이터 구조 (preview 응답도 동일 스키마).
 *
 * paradigm doc §19 참조.
 */
import type { GuideV2Response, IncidentType } from '@/types';

interface GuidePreviewModalProps {
  open: boolean;
  onClose: () => void;
  incidentType: IncidentType | null;
  preview: GuideV2Response | null;
  loading: boolean;
}

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

const GuidePreviewModal = ({
  open,
  onClose,
  incidentType,
  preview,
  loading,
}: GuidePreviewModalProps) => {
  if (!open || !incidentType) return null;

  const phases = preview?.phases ?? {};
  const phaseKeys = Object.keys(phases);
  const completionPct =
    preview && typeof preview.completionRate === 'number'
      ? Math.round(preview.completionRate * 100)
      : null;
  const envWarnings = preview?.environment_warnings ?? [];
  const appliedModifiers = preview?.applied_modifiers ?? [];
  const sourceStandards = preview?.source_standards ?? [];
  const seedTargets = preview?.seed_targets ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/80 backdrop-blur-sm p-4 animate-fade-up"
      onClick={onClose}
    >
      <div
        className="bg-ink-900 border border-ink-700/70 rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-start justify-between mb-3 pb-3 border-b border-ink-700/40">
          <div>
            <div className="text-[10.5px] text-brand-teal font-mono uppercase tracking-wider mb-1">
              가이드 미리보기 (사고유형 미확정)
            </div>
            <h2 className="text-[18px] font-bold text-ink-100">
              {INCIDENT_TYPE_KO[incidentType]}
              <span className="ml-2 text-[12px] font-normal text-ink-400">
                · {incidentType}
              </span>
            </h2>
            {completionPct !== null && (
              <div className="mt-1.5 text-[11px] text-ink-300">
                현재 수집 진행도{' '}
                <span className="font-mono text-brand-teal">{completionPct}%</span>
                {preview?.preview && (
                  <span className="ml-2 text-[10px] text-amber-400">
                    · preview (case.incident_type 미확정)
                  </span>
                )}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-ink-500 hover:text-ink-200 text-[24px] leading-none px-2"
            aria-label="닫기"
          >
            ×
          </button>
        </div>

        {loading ? (
          <div className="py-12 text-center text-ink-400 text-[12px] italic font-mono">
            가이드 로딩 중…
          </div>
        ) : !preview ? (
          <div className="py-12 text-center text-ink-500 text-[12px] italic">
            가이드 데이터 없음
          </div>
        ) : (
          <>
            {/* environment_warnings */}
            {envWarnings.length > 0 && (
              <div className="mb-4 px-3 py-2 bg-amber-900/15 border border-amber-700/40 rounded-lg">
                <div className="text-[11px] text-amber-200 font-semibold mb-1.5">
                  ⚠ 환경 경고 ({envWarnings.length}건) — system_config 기반 추가 수집 필요
                </div>
                <ul className="space-y-0.5 ml-3">
                  {envWarnings.map((w, i) => (
                    <li key={i} className="text-[10.5px] text-ink-300 leading-5">
                      <span className="text-amber-400 font-mono">•</span>{' '}
                      <span className="font-medium">{w.category_name}</span>{' '}
                      <span className="text-ink-500">— {w.rationale}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* applied_modifiers */}
            {appliedModifiers.length > 0 && (
              <div className="mb-4 px-3 py-2 bg-blue-900/15 border border-blue-700/40 rounded-lg">
                <div className="text-[11px] text-blue-200 font-semibold mb-1.5">
                  적용된 환경 보정 ({appliedModifiers.length}건)
                </div>
                <ul className="space-y-0.5 ml-3">
                  {appliedModifiers.slice(0, 6).map((m, i) => (
                    <li key={i} className="text-[10.5px] text-ink-400 leading-5">
                      <span className="font-mono text-blue-300/80">{m.id}</span>{' '}
                      — {m.effect}
                    </li>
                  ))}
                  {appliedModifiers.length > 6 && (
                    <li className="text-[10px] text-ink-500 italic">
                      … 외 {appliedModifiers.length - 6}건
                    </li>
                  )}
                </ul>
              </div>
            )}

            {/* Phase 별 수집 대상 */}
            {phaseKeys.length === 0 ? (
              <p className="text-[12px] text-ink-500 italic py-6 text-center">
                이 사고유형에 매칭되는 Kill Chain phase 없음
              </p>
            ) : (
              <div className="space-y-4 mb-4">
                {phaseKeys.map((phaseId) => {
                  const phase = phases[phaseId];
                  const targets = phase.targets ?? [];
                  return (
                    <div key={phaseId}>
                      <div className="flex items-baseline gap-2 mb-1.5 pb-1 border-b border-ink-700/30">
                        <h3 className="text-[13px] font-semibold text-ink-100">
                          {phase.phase_name ?? phaseId}
                        </h3>
                        <span className="text-[10px] text-ink-500 font-mono">
                          {targets.length}건
                        </span>
                        {phase.mitre_url && (
                          <a
                            href={phase.mitre_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] text-brand-teal hover:underline ml-auto"
                          >
                            MITRE →
                          </a>
                        )}
                      </div>
                      {phase.phase_description && (
                        <p className="text-[10.5px] text-ink-400 mb-2 leading-5">
                          {phase.phase_description}
                        </p>
                      )}
                      {targets.length === 0 ? (
                        <p className="text-[10.5px] text-ink-500 italic ml-2">
                          수집 대상 없음
                        </p>
                      ) : (
                        <ul className="space-y-1.5 ml-2">
                          {targets.map((t) => (
                            <li
                              key={t.category_id}
                              className="px-2.5 py-1.5 bg-ink-950/50 border border-ink-700/40 rounded text-[11px]"
                            >
                              <div className="flex items-center gap-1.5 mb-0.5">
                                <span
                                  className={`shrink-0 inline-block px-1.5 py-px text-[9px] font-mono rounded ${
                                    t.evidence_role === 'REQUIRED'
                                      ? 'bg-red-900/50 text-red-300 border border-red-700/50'
                                      : 'bg-amber-900/40 text-amber-300 border border-amber-700/50'
                                  }`}
                                >
                                  {t.evidence_role}
                                </span>
                                <span className="font-medium text-ink-200 truncate">
                                  {t.category_name}
                                </span>
                                {t.collected && (
                                  <span
                                    className="ml-auto text-emerald-400 text-[10px]"
                                    title="수집됨"
                                  >
                                    ✓ 수집
                                  </span>
                                )}
                              </div>
                              {t.rationale && (
                                <p className="text-[10px] text-ink-400 leading-4">
                                  {t.rationale}
                                </p>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* seed_targets (사이클 6 풍부 메타) */}
            {seedTargets.length > 0 && (
              <details className="mt-4 px-3 py-2 bg-ink-950/40 border border-ink-700/40 rounded-lg">
                <summary className="text-[11px] text-ink-300 font-semibold cursor-pointer">
                  V-1 Step 4 시드 단서 메타 ({seedTargets.length}건)
                </summary>
                <ul className="mt-1.5 space-y-0.5 ml-3 text-[10px] text-ink-400">
                  {seedTargets.slice(0, 5).map((s: Record<string, unknown>, i: number) => (
                    <li key={i} className="leading-4">
                      <span className="font-mono">
                        {(s.id as string) ?? '?'}
                      </span>
                      {' — '}
                      <span>
                        {(s.name as string) ?? (s.label as string) ?? '(이름 없음)'}
                      </span>
                    </li>
                  ))}
                  {seedTargets.length > 5 && (
                    <li className="italic">… 외 {seedTargets.length - 5}건</li>
                  )}
                </ul>
              </details>
            )}

            {/* 학술 인용 — 토글 (기본 접힘, 2026-06-03 사용자 요청) */}
            {sourceStandards.length > 0 && (
              <details className="mt-4 pt-3 border-t border-ink-700/40">
                <summary className="text-[9.5px] text-ink-500 font-semibold uppercase tracking-wider cursor-pointer select-none hover:text-ink-300 list-none flex items-center gap-1">
                  <span className="transition-transform">▸</span>
                  학술 인용 ({sourceStandards.length})
                </summary>
                <ul className="mt-1.5 space-y-0.5 text-[9.5px] text-ink-500 leading-4">
                  {sourceStandards.map((s, i) => (
                    <li key={i}>· {s}</li>
                  ))}
                </ul>
              </details>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default GuidePreviewModal;
