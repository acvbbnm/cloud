/**
 * V-1 Step 3 — Evidence Tree Discovery (Phase E, 2026-05-25, byungwoo).
 *
 * 설계서: `docs/evidence_tree_paradigm.md` §4 + §8
 *
 * TRIAGE_MODE=evidence_tree 일 때 Step3_Discovery 가 이 컴포넌트로 위임.
 *
 * 핵심 흐름:
 *   1. mount 시 hydrate(caseId) → 없으면 start(caseId) [백엔드 idempotent]
 *   2. 단서 채택 경로 3가지 — paradigm §4:
 *      A. ClueTreeView 의 후보 노드 클릭 → expand(source='tree_candidate')
 *      B. NextCluePanel IG 후보 클릭     → expand(source='tree_candidate')
 *      C. CluesInput 직접 입력           → expand(source='direct_input')
 *   3. confidence ≥0.65 + gap ≥0.20 도달 → notify 카드 노출
 *      (자동 종료 X — 사용자가 [확정하고 다음 단계] 클릭해야 진행)
 *
 * 레이아웃 (paradigm §8):
 *   ┌────────────────────────────────────────────────────────────┐
 *   │ [좌] ClueTreeView (메인, ~60%)                              │
 *   │       ROOT → 채택 단서 path → leaf children candidates      │
 *   │       후보 클릭 → 채택                                       │
 *   ├────────────────────────────────────────────────────────────┤
 *   │ [하] [CluesInput] [PartialLogAnalysis]                       │
 *   ├────────────────────────────────────────────────────────────┤
 *   │ [우 sticky]                                                  │
 *   │   ConfidenceGauge + HypothesisScoreBar + NextCluePanel IG    │
 *   │   confidence_reached 시 [확정하고 다음 단계로] 카드          │
 *   └────────────────────────────────────────────────────────────┘
 */
import { useEffect, useState } from 'react';

import Card from '@/components/Card';
import ClueTreeView from '@/components/ClueTreeView';
import CluesInput from '@/components/CluesInput';
import ConfidenceGauge from '@/components/ConfidenceGauge';
import DiscoveryIntroModal, {
  hasDismissedDiscoveryIntro,
} from '@/components/DiscoveryIntroModal';
import HypothesisScoreBar from '@/components/HypothesisScoreBar';
import IncidentTypeCompass from '@/components/IncidentTypeCompass';
import NextCluePanel from '@/components/NextCluePanel';
import PartialLogAnalysis from '@/components/PartialLogAnalysis';

import { useCaseStore } from '@/stores/useCaseStore';
import { useClueTreeStore } from '@/stores/useClueTreeStore';
import { useToastStore } from '@/stores/useToastStore';

import type { ClueCandidate, ClueTreeResponse } from '@/types/clueTree';
import type {
  ClueType,
  HypothesisScores,
  IncidentType,
  Observable,
} from '@/types';

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

interface Step3EvidenceTreeDiscoveryProps {
  onPrev: () => void;
  onConfirm: (confirmedIncidentType: IncidentType) => void;
  isSubmitting?: boolean;
}

const Step3_EvidenceTreeDiscovery = ({
  onPrev,
  onConfirm,
  isSubmitting,
}: Step3EvidenceTreeDiscoveryProps) => {
  const caseId = useCaseStore((s) => s.caseId);
  const observables = useCaseStore((s) => s.observables);
  const addObservable = useCaseStore((s) => s.addObservable);
  const removeObservable = useCaseStore((s) => s.removeObservable);
  const showToast = useToastStore((s) => s.show);

  const treeState = useClueTreeStore((s) => s.response);
  const loading = useClueTreeStore((s) => s.loading);
  const startTree = useClueTreeStore((s) => s.start);

  // Phase I — 메인 시각화 탭 (tree / compass). sessionStorage 영속화.
  const [mainView, setMainView] = useState<'tree' | 'compass'>(() => {
    if (typeof window === 'undefined') return 'tree';
    const stored = window.sessionStorage.getItem('aisherpa.evidenceTree.mainView');
    return stored === 'compass' ? 'compass' : 'tree';
  });
  const switchMainView = (v: 'tree' | 'compass') => {
    setMainView(v);
    try {
      window.sessionStorage.setItem('aisherpa.evidenceTree.mainView', v);
    } catch {
      /* ignore */
    }
  };
  const expandTree = useClueTreeStore((s) => s.expand);
  const refreshCandidates = useClueTreeStore((s) => s.refreshCandidates);
  const hydrate = useClueTreeStore((s) => s.hydrate);
  const resetServer = useClueTreeStore((s) => s.resetServer);

  // Phase G — 첫 진입 시 evidence_tree 패러다임 안내 모달
  const [introOpen, setIntroOpen] = useState(false);
  useEffect(() => {
    if (!hasDismissedDiscoveryIntro('evidence_tree')) {
      setIntroOpen(true);
    }
  }, []);

  // ClueCatalog 가 단서 키 ↔ outcome_flags 룩업이 필요할 때 — 일단은 응답 candidate 가 모두 가지고 옴

  // ── mount: hydrate 후 없으면 start ──
  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    (async () => {
      try {
        const hydrated = await hydrate(caseId);
        if (cancelled) return;
        if (!hydrated) {
          await startTree(caseId);
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        showToast(`단서 트리 시작 실패: ${msg}`, 5000);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  // ── 단서 채택 핸들러 (트리 후보 / IG 후보 클릭) ──
  // ⚠ closure stale 방지 — getState() 로 최신 current_leaf_id 직접 조회
  const handleAdoptCandidate = async (
    candidate: ClueCandidate,
    source: 'tree_candidate' | 'direct_input' | 'log_analysis' = 'tree_candidate',
  ) => {
    if (!caseId) return;
    const current = useClueTreeStore.getState().response;
    if (!current) return;
    try {
      const res = await expandTree({
        caseId,
        parent_node_id: current.current_leaf_id,
        clue_key: candidate.clue_key,
        source,
      });
      _maybeRecordObservable(res, candidate);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(`단서 채택 실패: ${msg}`, 4500);
    }
  };

  /** Observable 동기화 — case_store 의 observables 와 트리 단서 양립. */
  const _maybeRecordObservable = (
    _res: ClueTreeResponse,
    cand: ClueCandidate,
  ) => {
    // 후보 카테고리가 6종 ClueType 중 하나면 observables 에 자동 기록
    const allowed: ClueType[] = [
      'IP_ADDRESS',
      'ACCOUNT',
      'HASH',
      'DOMAIN',
      'TIME_WINDOW',
      'SERVICE',
    ];
    if (!allowed.includes(cand.category as ClueType)) return;
    addObservable({
      type: cand.category as ClueType,
      value: cand.value || cand.clue_key,
      weight_key: cand.clue_key,
      note: `Evidence Tree — ${cand.rationale}`,
    });
  };

  // ── CluesInput 직접 입력 핸들러 ──
  // ⚠ closure stale 방지 — getState() 로 최신 current_leaf_id 직접 조회.
  // 트리가 확장되어 leaf 가 바뀐 후 직접 입력 시 옛 leaf 에 expand 하지 않도록.
  const handleDirectClueAdd = async (obs: Observable) => {
    if (!caseId) return;
    const current = useClueTreeStore.getState().response;
    if (!current) return;

    const inferredKey = _inferClueKey(obs);
    if (!inferredKey) {
      // 카탈로그에 매칭 안 되면 observables 만 추가 (단서로 표시 X)
      addObservable(obs);
      showToast(
        `단서 카탈로그에 없는 항목 — 트리 외 단서로 기록됨 (${obs.type}:${obs.value})`,
        3500,
      );
      return;
    }

    try {
      const res = await expandTree({
        caseId,
        parent_node_id: current.current_leaf_id,
        clue_key: inferredKey,
        source: 'direct_input',
        // 사용자 입력값 (예: "203.0.113.5") 을 트리 노드 라벨로 표시
        label_override: `${obs.type}: ${obs.value}`,
      });
      addObservable(obs);
      // 채택된 단서를 보조 토스트로 안내
      const top = (() => {
        const sorted = (
          Object.entries(res.posterior_current) as [IncidentType, number][]
        ).filter(([k]) => k !== 'UNCLASSIFIED');
        sorted.sort((a, b) => b[1] - a[1]);
        return sorted[0];
      })();
      if (top) {
        showToast(
          `단서 채택 — 현재 1위 ${INCIDENT_TYPE_KO[top[0]]} ${(top[1] * 100).toFixed(1)}%`,
          2800,
        );
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(`단서 채택 실패 (${inferredKey}): ${msg}`, 4500);
    }
  };

  /** 단서 자유 입력 → clue_catalog 키 추론 (Phase E MVP — 정적 매핑).
   *  weight_key 가 있으면 그것을 우선, 없으면 TYPE:generic 으로 fallback. */
  const _inferClueKey = (obs: Observable): string | null => {
    if (obs.weight_key) return obs.weight_key;
    const generic: Record<ClueType, string> = {
      IP_ADDRESS: 'IP_ADDRESS:generic',
      ACCOUNT: 'ACCOUNT:generic',
      HASH: 'HASH:generic',
      DOMAIN: 'DOMAIN:generic',
      TIME_WINDOW: 'TIME_WINDOW:generic',
      SERVICE: 'SERVICE:generic',
    };
    return generic[obs.type] ?? null;
  };

  // ── 부분 로그 분석 → 단서 후보 자동 채택 ──
  const handlePartialAnalysisResult = (
    techniqueIds: string[],
    _filenames: string[],
    _scores: HypothesisScores,
  ): void => {
    if (!caseId || !treeState) return;
    // 비동기 적용 (각 기법을 순차 expand — 카탈로그에 없으면 skip)
    (async () => {
      for (const tid of techniqueIds) {
        const clueKey = `TECHNIQUE:${tid}`;
        try {
          await expandTree({
            caseId,
            parent_node_id:
              useClueTreeStore.getState().response?.current_leaf_id ??
              treeState.current_leaf_id,
            clue_key: clueKey,
            source: 'log_analysis',
          });
        } catch (_e) {
          // 카탈로그에 없는 기법은 무시 (정상 흐름)
        }
      }
    })();
  };

  // ── 확정 핸들러 ──
  const handleConfirm = () => {
    if (!treeState?.confidence.primary) return;
    onConfirm(treeState.confidence.primary);
  };

  // ── 렌더 ──
  if (!caseId) {
    return (
      <div className="p-6 text-ink-400 text-sm">케이스가 선택되지 않았습니다.</div>
    );
  }

  if (loading && !treeState) {
    return (
      <div className="p-6 text-ink-400 text-sm font-mono">
        단서 트리 시작 중…
      </div>
    );
  }

  if (!treeState) {
    return (
      <div className="p-6 text-ink-400 text-sm font-mono">
        단서 트리 초기화 대기 중…
      </div>
    );
  }

  // 사후확률 (HypothesisScores 형식 — UNCLASSIFIED 포함)
  const scoresForBar: HypothesisScores = treeState.posterior_current;

  return (
    <div className="grid grid-cols-12 gap-3">
      {/* Phase G — 첫 진입 사전 안내 (evidence_tree 패러다임) */}
      <DiscoveryIntroModal
        open={introOpen}
        onClose={() => setIntroOpen(false)}
        mode="evidence_tree"
      />

      {/* 좌측 메인 — Evidence Tree 시각화 + 입력 채널 */}
      <div className="col-span-12 lg:col-span-8 space-y-3">
        <Card
          title={mainView === 'tree' ? 'Evidence Tree — 단서로 맵 밝히기' : '사고유형 컴퍼스 — 360° 방향 수렴'}
          subtitle={
            mainView === 'tree'
              ? '현재 leaf 의 점선 후보 클릭 → 단서 채택 → 트리 자라기'
              : '단서마다 사후확률 무게중심이 한 사고유형 방향으로 이동 — 미로 헤쳐나가듯'
          }
          action={
            <div className="flex items-center gap-1">
              {/* Phase I — 탭 토글 (tree ↔ compass) */}
              <div className="flex border border-ink-700 rounded overflow-hidden">
                <button
                  type="button"
                  onClick={() => switchMainView('tree')}
                  className={`text-[10.5px] px-2 py-0.5 transition-colors ${
                    mainView === 'tree'
                      ? 'bg-brand-teal text-ink-950 font-semibold'
                      : 'text-ink-300 hover:text-ink-100 hover:bg-ink-800'
                  }`}
                  title="트리 시각화"
                >
                  🌳 트리
                </button>
                <button
                  type="button"
                  onClick={() => switchMainView('compass')}
                  className={`text-[10.5px] px-2 py-0.5 transition-colors border-l border-ink-700 ${
                    mainView === 'compass'
                      ? 'bg-brand-teal text-ink-950 font-semibold'
                      : 'text-ink-300 hover:text-ink-100 hover:bg-ink-800'
                  }`}
                  title="사고유형 360° 컴퍼스"
                >
                  🧭 컴퍼스
                </button>
              </div>
              <button
                type="button"
                onClick={async () => {
                  if (!caseId) return;
                  if (
                    !window.confirm(
                      '현재 트리를 초기화하고 cold-start 로 다시 시작합니다.\n계속하시겠습니까?',
                    )
                  )
                    return;
                  try {
                    await resetServer(caseId);
                    showToast('단서 트리 초기화 완료 — 첫 단서를 입력하세요', 3500);
                  } catch (e) {
                    const msg = e instanceof Error ? e.message : String(e);
                    showToast(`초기화 실패: ${msg}`, 4500);
                  }
                }}
                disabled={loading || isSubmitting}
                className="text-[10px] font-mono text-ink-400 hover:text-red-300 border border-ink-700 hover:border-red-500/60 px-2 py-0.5 rounded transition-colors disabled:opacity-40"
                title="기존 트리를 폐기하고 cold-start 로 재시작"
              >
                ⟲ 초기화
              </button>
            </div>
          }
        >
          {mainView === 'tree' ? (
            <ClueTreeView
              tree={treeState.tree}
              currentLeafId={treeState.current_leaf_id}
              entropyBits={treeState.confidence.entropy_bits}
              onAdoptCandidate={(c) => handleAdoptCandidate(c, 'tree_candidate')}
              onDirectInputClick={() => {
                // ✏ 트리 슬롯 클릭 — 하단 단서 직접 입력 카드로 스크롤 + 강조
                const el = document.getElementById('direct-input-card');
                if (el) {
                  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                  el.classList.add('ring-2', 'ring-amber-500/70');
                  window.setTimeout(() => {
                    el.classList.remove('ring-2', 'ring-amber-500/70');
                  }, 2000);
                }
              }}
              disabled={loading || isSubmitting}
              height={460}
            />
          ) : (
            <IncidentTypeCompass
              tree={treeState.tree}
              currentLeafId={treeState.current_leaf_id}
              primaryIncident={treeState.confidence.primary}
              confidenceReached={treeState.confidence.confidence_reached}
              disabled={loading || isSubmitting}
            />
          )}
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div id="direct-input-card" className="rounded transition-all">
          <Card title="단서 직접 입력" subtitle="✏ 트리 슬롯 클릭 → 자동 스크롤 + 강조">
            <CluesInput
              observables={observables}
              onAdd={handleDirectClueAdd}
              onRemove={removeObservable}
              preferredType={null}
              preferredVariant={null}
            />
          </Card>
          </div>
          <Card title="부분 로그 분석" subtitle="ATT&CK 기법 → 단서 후보 자동 추가">
            <PartialLogAnalysis
              caseId={caseId}
              currentScores={scoresForBar}
              mappedTechniques={[]}
              onAnalyzed={handlePartialAnalysisResult}
              disabled={loading}
            />
          </Card>
        </div>
      </div>

      {/* 우측 sticky — 신뢰도 + 가설 + IG 후보 */}
      <div className="col-span-12 lg:col-span-4 space-y-3">
        <Card title="현재 신뢰도" subtitle={`entropy ${treeState.confidence.entropy_bits.toFixed(2)} bits`}>
          <ConfidenceGauge scores={scoresForBar} scoringMode="bayesian" />
          <div className="mt-3">
            <HypothesisScoreBar
              scores={scoresForBar}
              scoringMode="bayesian"
              limit={2}
            />
          </div>
        </Card>

        <Card title="다음 단서 후보" subtitle="Information Gain 순">
          <NextCluePanel
            scores={scoresForBar}
            igCandidates={treeState.candidates}
            entropyBits={treeState.confidence.entropy_bits}
            onAdoptCandidate={(c) => handleAdoptCandidate(c, 'tree_candidate')}
            onRefreshCandidates={() => refreshCandidates(caseId)}
            disabled={loading || isSubmitting}
            scoringMode={treeState.scoring_mode}
          />
        </Card>

        {treeState.confidence.confidence_reached && treeState.confidence.primary && (
          <Card title="사고유형 확정 가능" subtitle="사용자 결정 — 자동 종료 X">
            <div className="space-y-2">
              <div className="text-[12.5px] text-ink-100">
                <span className="font-bold text-brand-teal">
                  {INCIDENT_TYPE_KO[treeState.confidence.primary]}
                </span>{' '}
                {(treeState.confidence.primary_prob * 100).toFixed(1)}%
              </div>
              {treeState.confidence.secondary && (
                <div className="text-[10.5px] text-ink-400">
                  2위 {INCIDENT_TYPE_KO[treeState.confidence.secondary]}{' '}
                  {(treeState.confidence.secondary_prob * 100).toFixed(1)}% · 격차{' '}
                  {(treeState.confidence.gap * 100).toFixed(1)}%p
                </div>
              )}
              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={handleConfirm}
                  disabled={isSubmitting}
                  className="flex-1 text-[11px] font-semibold bg-brand-teal hover:bg-brand-tealDark text-ink-950 px-3 py-1.5 rounded transition-colors disabled:opacity-40"
                >
                  확정하고 다음 단계로 →
                </button>
                <button
                  type="button"
                  onClick={() => {
                    // 그냥 계속 단서 채택 — confidence 카드는 알림으로 남음
                  }}
                  className="text-[11px] text-ink-300 hover:text-ink-100 border border-ink-700 hover:border-ink-500 px-3 py-1.5 rounded transition-colors"
                >
                  단서 더 채택
                </button>
              </div>
            </div>
          </Card>
        )}

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onPrev}
            className="text-[11px] text-ink-300 hover:text-ink-100 border border-ink-700 hover:border-ink-500 px-3 py-1.5 rounded transition-colors"
          >
            ← 이전 단계
          </button>
          {!treeState.confidence.confidence_reached && treeState.confidence.primary && (
            <button
              type="button"
              onClick={handleConfirm}
              disabled={isSubmitting}
              className="text-[11px] text-ink-400 hover:text-ink-100 border border-ink-700 hover:border-ink-500 px-3 py-1.5 rounded transition-colors disabled:opacity-40"
              title="confidence 미도달 — 현재 1위로 잠정 진행"
            >
              미확정 진행 →
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default Step3_EvidenceTreeDiscovery;
