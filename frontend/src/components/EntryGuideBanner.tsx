/**
 * EntryGuideBanner — Phase P.2 기본 수사 가이드 (2026-05-26 byungwoo).
 *
 * 사용자 비전 (2026-05-26):
 *   "기본 가이드 = 사고유형 unclassified 일 때 제공되는 가장 기초적인 가이드.
 *    엄청 필수 로그들 확인해보고 들어가자."
 *
 * 학술 정합
 * ---------
 *   - KISA 2.4 사고 탐지 단계 — 사고 유형 식별 전 공통 점검표
 *   - NIST SP 800-86 §4.1 Initial Triage — Initial Access · Credential Access · Discovery
 *
 * 동작
 * ----
 *   - mount 시 `getGuidePreview(caseId, 'UNCLASSIFIED')` 호출
 *   - 응답 phases (3개: IA / CA / Disc) 의 REQUIRED 타깃들을 컴팩트 카드로 노출
 *   - [전체 가이드 보기] → 기존 GuidePreviewModal 재활용
 *   - sessionStorage dismiss (사용자 명시 X 버튼)
 *
 * 디자인 — ReconClueCard 보다 한 단계 위 (cold-start 직후 가장 먼저 눈에 띄게).
 */
import { useEffect, useState } from 'react';

import SourceTag from '@/components/SourceTag';
import { getGuidePreview } from '@/api/intake';

import type { GuideV2Response, GuideV2Target } from '@/types';

interface EntryGuideBannerProps {
  caseId: string | null;
  /** [전체 가이드 보기] 클릭 콜백 — Step3 가 GuidePreviewModal 열 때 사용. */
  onOpenFullGuide?: (preview: GuideV2Response) => void;
  /** 영구 dismiss 콜백 (sessionStorage). */
  onDismiss?: () => void;
}

const DISMISS_KEY = 'aisherpa.entryGuideBanner.dismissed';

export const hasDismissedEntryGuide = (): boolean => {
  try {
    return window.sessionStorage.getItem(DISMISS_KEY) === '1';
  } catch {
    return false;
  }
};

const EntryGuideBanner = ({
  caseId,
  onOpenFullGuide,
  onDismiss,
}: EntryGuideBannerProps) => {
  const [guide, setGuide] = useState<GuideV2Response | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const res = await getGuidePreview(caseId, 'UNCLASSIFIED');
        if (cancelled) return;
        setGuide(res);
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
  }, [caseId]);

  const handleDismiss = () => {
    try {
      window.sessionStorage.setItem(DISMISS_KEY, '1');
    } catch {
      /* ignore */
    }
    onDismiss?.();
  };

  const handleOpenFull = () => {
    if (guide) onOpenFullGuide?.(guide);
  };

  // phase 별 REQUIRED 타깃만 최대 4개 추출 (컴팩트)
  const topByPhase: Array<{
    phaseName: string;
    kisaRef: string;
    targets: GuideV2Target[];
  }> = [];

  if (guide?.phases) {
    for (const [, group] of Object.entries(guide.phases)) {
      const requireds = group.targets
        .filter((t) => t.evidence_role === 'REQUIRED')
        .slice(0, 4);
      if (requireds.length === 0) continue;
      topByPhase.push({
        phaseName: group.phase_name ?? '?',
        kisaRef: group.kisa_reference ?? '',
        targets: requireds,
      });
    }
  }

  return (
    <div className="border border-brand-teal/40 bg-brand-teal/5 rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-brand-teal/30 flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-brand-teal">
            기본 수사 가이드 — 사고유형 무관
          </span>
          {/* V1.fix.6 — 인라인 라벨 → 클릭 popup 으로 (학술 근거는 숨김) */}
          <SourceTag
            label="ⓘ 근거"
            title="기본 수사 가이드 학술 근거"
            body={
              'KISA 침해사고 대응 안내서 §2.4 초기 대응 점검표\n' +
              'NIST SP 800-86 §4.1 Initial Triage (휘발성 증거 우선)\n\n' +
              '이 가이드는 사고유형 분류에 사용되지 않습니다. 단지 사고 인지 직후\n' +
              '먼저 살펴봐야 할 필수 로그 점검표입니다. 사후확률에 영향 없음.'
            }
          />
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handleOpenFull}
            disabled={!guide}
            className="text-[10px] text-brand-teal/90 hover:text-brand-teal border border-brand-teal/40 hover:border-brand-teal/80 px-2 py-0.5 rounded transition-colors disabled:opacity-40"
            title="UNCLASSIFIED 전체 가이드 모달"
          >
            전체 가이드 →
          </button>
          <button
            type="button"
            onClick={handleDismiss}
            className="text-[10px] text-brand-teal/60 hover:text-brand-teal/90 px-1.5 py-0.5 transition-colors"
            title="이 기본 가이드 닫기"
          >
            ✕
          </button>
        </div>
      </div>

      {loading && (
        <div className="px-3 py-3 text-[10.5px] text-ink-400 font-mono">
          기본 가이드 로딩 중…
        </div>
      )}
      {error && (
        <div className="px-3 py-3 text-[10.5px] text-red-300 font-mono">
          가이드 로드 실패: {error}
        </div>
      )}

      {!loading && !error && guide && (
        <div className="px-3 py-2 space-y-2.5">
          <p className="text-[10.5px] text-brand-teal/90 leading-5">
            사고유형 확정 전 <span className="font-semibold">먼저 봐야 할 필수 로그</span>{' '}
            점검표. 아래 항목들을 콘솔·CLI 로 한 번씩 훑은 뒤 본격 단서 채택을 시작하세요.
          </p>

          <div className="space-y-2">
            {topByPhase.map((p) => (
              <div key={p.phaseName} className="bg-ink-900/40 rounded px-2.5 py-1.5">
                <div className="text-[10.5px] text-ink-100 font-semibold mb-1 flex items-center gap-1.5">
                  <span>{p.phaseName}</span>
                  {p.kisaRef && (
                    <span className="text-[9px] text-ink-400 font-mono">
                      · {p.kisaRef}
                    </span>
                  )}
                </div>
                <ul className="space-y-0.5">
                  {p.targets.map((t) => (
                    <li
                      key={t.category_id}
                      className="text-[10px] text-ink-200 leading-4 flex items-start gap-1.5"
                      title={t.rationale}
                    >
                      <span className="text-brand-teal mt-0.5">▸</span>
                      <span className="flex-1 min-w-0">
                        <span className="font-medium">{t.category_name}</span>
                        {t.evidence_role === 'REQUIRED' && (
                          <span className="ml-1 text-[8.5px] text-red-400/80 font-mono">
                            REQUIRED
                          </span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* V1.fix.6 — 하단 메타 푸터 제거 (사용자 피드백: "영향 X 같은 메타 문구 없애기").
          학술 근거는 상단 ⓘ 근거 버튼에 통합. */}
    </div>
  );
};

export default EntryGuideBanner;
