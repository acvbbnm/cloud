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

import AttackChainCard from '@/components/AttackChainCard';
import BridgeToBoardCard from '@/components/BridgeToBoardCard';
import Card from '@/components/Card';
import ClueTreeView from '@/components/ClueTreeView';
import ConfidenceGauge from '@/components/ConfidenceGauge';
import EntryGuideBanner, { hasDismissedEntryGuide } from '@/components/EntryGuideBanner';
import EvidenceLogPanel from '@/components/EvidenceLogPanel';
import GuidePreviewModal from '@/components/GuidePreviewModal';
import HypothesisScoreBar from '@/components/HypothesisScoreBar';
import IncidentTypeCompass from '@/components/IncidentTypeCompass';
import NextCluePanel from '@/components/NextCluePanel';
import ReconClueCard, { hasDismissedRecon } from '@/components/ReconClueCard';
import RegressBanner from '@/components/RegressBanner';

import { getGuidePreview } from '@/api/intake';

import { useCaseStore } from '@/stores/useCaseStore';
import { useClueTreeStore } from '@/stores/useClueTreeStore';
import { useEvidenceLogStore, type LoadedLog } from '@/stores/useEvidenceLogStore';
import { useToastStore } from '@/stores/useToastStore';

import type { ClueCandidate, ClueTreeResponse } from '@/types/clueTree';
import type {
  ClueType,
  GuideV2Response,
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
  const addObservable = useCaseStore((s) => s.addObservable);
  const showToast = useToastStore((s) => s.show);

  const treeState = useClueTreeStore((s) => s.response);
  const loading = useClueTreeStore((s) => s.loading);
  const startTree = useClueTreeStore((s) => s.start);

  // Phase I — 메인 시각화 탭 (tree / compass). sessionStorage 영속화.
  // 단서루프 입장 시 컴퍼스가 먼저 보이도록 기본값 = 'compass' (2026-06-03).
  const [mainView, setMainView] = useState<'tree' | 'compass'>(() => {
    if (typeof window === 'undefined') return 'compass';
    const stored = window.sessionStorage.getItem('aisherpa.evidenceTree.mainView');
    return stored === 'tree' ? 'tree' : 'compass';
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
  const advanceStage = useClueTreeStore((s) => s.advanceStage);
  const retract = useClueTreeStore((s) => s.retract);

  // ── Phase N.1 (2026-05-26) — 1차 정찰 단서 카드 dismiss 상태 ──
  // NIST SP 800-86 §4.1 Initial Triage. cold-start ~ depth 1 구간에 노출,
  // depth ≥ 2 면 자동 숨김. 사용자 X 클릭으로 영구 dismiss (sessionStorage).
  const [reconDismissed, setReconDismissed] = useState<boolean>(hasDismissedRecon);
  // Phase P.2 (2026-05-26) — 기본 수사 가이드 dismiss (UNCLASSIFIED 필수 로그 점검표)
  const [entryGuideDismissed, setEntryGuideDismissed] = useState<boolean>(
    hasDismissedEntryGuide,
  );

  // ── Phase M.3 (2026-05-26) — Zone 2 chain mode 상태 ──
  // chainFilterHypothesis: AttackChainCard 에서 선택된 가설 (null = 미선택, 통합 풀).
  // zone 1 으로 회귀 시 자동 해제.
  const [chainFilterHypothesis, setChainFilterHypothesis] = useState<IncidentType | null>(
    null,
  );
  // Zone 2 → Zone 1 자동 해제 (paradigm §21.8.1)
  useEffect(() => {
    if (treeState?.zone !== 2 && chainFilterHypothesis !== null) {
      setChainFilterHypothesis(null);
    }
  }, [treeState?.zone, chainFilterHypothesis]);
  // 회귀 권고 토스트 1회 알림 (state 진입 시점 감지)
  const [regressNotified, setRegressNotified] = useState(false);
  useEffect(() => {
    if (treeState?.regress_suggested && !regressNotified) {
      showToast(
        '회귀 권고 — 가설이 다시 모호해졌습니다. 광범위 탐색 (Zone 1) 으로 복귀 권장',
        4500,
      );
      setRegressNotified(true);
    }
    if (!treeState?.regress_suggested && regressNotified) {
      setRegressNotified(false);
    }
  }, [treeState?.regress_suggested, regressNotified, showToast]);

  // ── Phase K (2026-05-26 byungwoo) — 가설 가이드 미리보기 상태 ──
  // HypothesisScoreBar 의 행 클릭 → 가설 가이드 preview 로딩 → inline expand.
  // [전체 가이드 보기 →] 클릭 → 풀 가이드 모달 (GuidePreviewModal).
  const [expandedGuideType, setExpandedGuideType] = useState<IncidentType | null>(
    null,
  );
  const [guidePreviewCache, setGuidePreviewCache] = useState<
    Record<string, GuideV2Response>
  >({});
  const [guidePreviewLoading, setGuidePreviewLoading] = useState(false);
  const [fullGuideModalType, setFullGuideModalType] = useState<IncidentType | null>(
    null,
  );

  // ── P.36 (2026-05-31 정정) — 적재함은 useEvidenceLogStore 가 보관 ──
  //   V-2/V-3/V-6 의 row 가 store.load() 로 push, V-1 은 store.logs 만 표시.
  //   사용자: "적재함은 우리 토글에서 로그 업로드/분석한 거 그거를 추가".
  const loadedLogs = useEvidenceLogStore((s) => s.logs);
  // P.35.4 — 컴파스 점 클릭 → trail point detail (clue_key 매칭 로그 + 시각·posterior)
  const [selectedTrailPoint, setSelectedTrailPoint] = useState<{
    clue_key: string;
    label: string;
    stage: number;
    posterior: HypothesisScores;
  } | null>(null);
  const [highlightedClueKey, setHighlightedClueKey] = useState<string | null>(null);

  /** HypothesisScoreBar 행 클릭 → preview 로딩 + inline expand 토글. */
  const handleClickIncidentType = async (type: IncidentType) => {
    // 같은 행 다시 클릭 = 닫기
    if (expandedGuideType === type) {
      setExpandedGuideType(null);
      return;
    }
    setExpandedGuideType(type);
    if (guidePreviewCache[type] || !caseId) return;
    setGuidePreviewLoading(true);
    try {
      const res = await getGuidePreview(caseId, type);
      setGuidePreviewCache((prev) => ({ ...prev, [type]: res }));
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(`가이드 미리보기 실패: ${msg}`, 4500);
    } finally {
      setGuidePreviewLoading(false);
    }
  };

  /** 풀 가이드 모달 열기 — 이미 캐시된 preview 데이터 재사용. */
  const handleOpenFullGuide = (type: IncidentType) => {
    setFullGuideModalType(type);
    // 모달이 캐시 없이 열린 경우 백그라운드 로드
    if (!guidePreviewCache[type] && caseId) {
      setGuidePreviewLoading(true);
      getGuidePreview(caseId, type)
        .then((res) =>
          setGuidePreviewCache((prev) => ({ ...prev, [type]: res })),
        )
        .catch((e) => {
          const msg = e instanceof Error ? e.message : String(e);
          showToast(`가이드 로딩 실패: ${msg}`, 4500);
        })
        .finally(() => setGuidePreviewLoading(false));
    }
  };

  /** Phase K.4 — 가이드 기반 단서 후보 [+] 클릭 → expand_tree 호출. */
  const handleAdoptGuideClue = async (
    match: { clue_key: string; clue_type: string; matched_keyword: string },
    sourceContext: string,
  ) => {
    if (!caseId || !treeState) return;
    try {
      await expandTree({
        caseId,
        parent_node_id: treeState.current_leaf_id,
        clue_key: match.clue_key,
        source: 'direct_input', // 가이드 추천 = 사용자가 명시 채택, direct_input 분류
      });
      showToast(
        `가이드 추천 단서 채택 — ${match.clue_type}:${match.matched_keyword} (${sourceContext})`,
        2800,
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(`단서 채택 실패: ${msg}`, 4500);
    }
  };

  /** 트리에 이미 채택된 단서 키 set (가이드 매칭 시 중복 차단). */
  const acceptedClueKeys = (() => {
    const out = new Set<string>();
    if (!treeState) return out;
    for (const node of Object.values(treeState.tree.nodes)) {
      if (node.clue_key && node.clue_key !== '__ROOT__') out.add(node.clue_key);
    }
    return out;
  })();

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

  // ── P.36 — handleLoadLog / handleUnloadLog 제거 ──
  //   load/unload 는 useEvidenceLogStore action 으로 직접 호출.
  //   V-2/V-3/V-6 가 store.load(), V-1 적재함의 [×] 가 store.unload().

  // ── P.39 (2026-05-31 사용자: "로그 분석해온 거 단서로 채택하면 그 로그에
  //   대해서 분석 진행해서 단서 확률들이 올라가야") — 적재 로그 채택 시
  //   ATT&CK 기법 가중치 활용. ──
  //
  // 가중치 차이 (weights.json):
  //   · IP_ADDRESS:generic / ACCOUNT:generic = 5점 (3-4 사고유형 균등) → posterior 미동
  //   · TECHNIQUE:{technique_id} = 25-35점 (사고유형별 변별) → posterior 가시적 갱신
  //     (백엔드 expand_tree §P.21 가 source='log_analysis' + TECHNIQUE:* 키를
  //      합성 entry 로 처리 — bayes_net.technique_likelihood 정규화)
  //
  // 동작:
  //   · log.technique_id 가 있으면 (LogAnalysisFab 적재) → TECHNIQUE:{id} 채택
  //     트리 라벨에 raw observable 정보 부착 → 화면상 raw 신호 + 강한 가중치
  //   · log.technique_id 가 없으면 (V-2 raw / V-3 OCSF 등) → 기존 generic 흐름
  const handleAdoptFromLog = async (obs: Observable, log: LoadedLog) => {
    const originDesc = `로그 ${log.source}:${log.source_id.slice(0, 8)} · ${log.time?.slice(0, 16) ?? '시각 없음'}`;

    // technique_id 있으면 ATT&CK 기법 가중치 직접 활용
    if (log.technique_id && caseId) {
      const current = useClueTreeStore.getState().response;
      if (!current) return;
      const techniqueKey = `TECHNIQUE:${log.technique_id}`;
      // 트리 노드 라벨 — raw observable + 시각 + ATT&CK hint
      const overrideLabel = `${obs.type}: ${obs.value} (${log.technique_id}, ${log.time?.slice(11, 19) ?? '시각'})`;
      try {
        const res = await expandTree({
          caseId,
          parent_node_id: current.current_leaf_id,
          clue_key: techniqueKey,
          source: 'log_analysis',
          label_override: overrideLabel,
        });
        addObservable({
          ...obs,
          note: obs.note ? `${obs.note} — ${originDesc}` : originDesc,
        });
        // 갱신된 1위 가설 토스트
        const top = (() => {
          const sorted = (
            Object.entries(res.posterior_current) as [IncidentType, number][]
          ).filter(([k]) => k !== 'UNCLASSIFIED');
          sorted.sort((a, b) => b[1] - a[1]);
          return sorted[0];
        })();
        if (top) {
          showToast(
            `채택 — 1위 ${INCIDENT_TYPE_KO[top[0]]} ${(top[1] * 100).toFixed(1)}% (${log.technique_id} 가중치 반영)`,
            3200,
          );
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        // technique 채택 실패 시 — observable 단서로 fallback (legacy 흐름)
        showToast(
          `${log.technique_id} 채택 실패 — observable fallback: ${msg}`,
          3500,
        );
        const enriched: Observable = {
          ...obs,
          note: obs.note ? `${obs.note} (${originDesc})` : originDesc,
        };
        handleDirectClueAdd(enriched);
      }
      return;
    }

    // technique_id 없음 — observable generic 채택 (기존 흐름)
    const enriched: Observable = {
      ...obs,
      note: obs.note ? `${obs.note} (${originDesc})` : originDesc,
    };
    handleDirectClueAdd(enriched);
  };

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

  // V1.fix.20 — handlePartialAnalysisResult 제거 (부분 로그 분석 카드 폐기).
  //   해당 기능은 좌측 [로그] 토글로 대체. PartialLogAnalysis 컴포넌트 자체는
  //   파일 보존 (다른 위치 재사용 가능성).

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
      {/* Phase K.3 — 풀 가이드 모달 (HypothesisScoreBar 의 [전체 가이드 보기] 클릭) */}
      <GuidePreviewModal
        open={!!fullGuideModalType}
        onClose={() => setFullGuideModalType(null)}
        incidentType={fullGuideModalType}
        preview={
          fullGuideModalType ? guidePreviewCache[fullGuideModalType] ?? null : null
        }
        loading={guidePreviewLoading}
      />

      {/* 좌측 메인 — Evidence Tree 시각화 + 입력 채널 */}
      <div className="col-span-12 lg:col-span-8 space-y-3">
        {/* V1.fix.5 (2026-05-31) — MultiStageBoard "킬체인 7단계 전체" 제거.
            사유: 킬체인 전체단계 채우기 어렵고 UI 노이즈가 커서 사용자가 삭제 요청.
            기본 수사 가이드(EntryGuideBanner) 는 유지. */}

        {/* Phase P.2 (2026-05-26) — 기본 수사 가이드 (UNCLASSIFIED Initial Triage)
            사고유형 무관 필수 로그 점검표. 사후확률 영향 X — 단순 안내. */}
        {!entryGuideDismissed && (treeState.path.length - 1) < 4 && (
          <EntryGuideBanner
            caseId={caseId}
            onOpenFullGuide={(preview) => {
              setGuidePreviewCache((prev) => ({ ...prev, UNCLASSIFIED: preview }));
              setFullGuideModalType('UNCLASSIFIED');
            }}
            onDismiss={() => setEntryGuideDismissed(true)}
          />
        )}

        {/* Phase N.1 (2026-05-26) — 1차 정찰 가이드: cold-start ~ depth 1, 미dismiss 시 */}
        {!reconDismissed && (treeState.path.length - 1) < 2 && (
          <ReconClueCard
            acceptedClueKeys={acceptedClueKeys}
            disabled={loading || isSubmitting}
            onDismiss={() => setReconDismissed(true)}
            onAdopt={async (clueKey, label) => {
              if (!caseId) return;
              const current = useClueTreeStore.getState().response;
              if (!current) return;
              try {
                await expandTree({
                  caseId,
                  parent_node_id: current.current_leaf_id,
                  clue_key: clueKey,
                  source: 'direct_input',
                });
                showToast(`정찰 단서 채택 — ${label}`, 2500);
              } catch (e) {
                const msg = e instanceof Error ? e.message : String(e);
                showToast(`정찰 단서 채택 실패: ${msg}`, 4500);
              }
            }}
          />
        )}

        <Card
          title={mainView === 'tree' ? 'Evidence Tree' : '사고유형 컴퍼스'}
          subtitle={
            mainView === 'tree'
              ? '현재 leaf 의 점선 후보 클릭 → 단서 채택 → 트리 자라기'
              : '단서 채택 시 사고유형 방향으로 이동'
          }
          action={
            <div className="flex items-center gap-1">
              {/* Phase I — 탭 토글 (compass ↔ tree). 2026-06-03 컴퍼스를 앞으로 배치. */}
              <div className="flex border border-ink-700 rounded overflow-hidden">
                <button
                  type="button"
                  onClick={() => switchMainView('compass')}
                  className={`text-[10.5px] px-2 py-0.5 transition-colors ${
                    mainView === 'compass'
                      ? 'bg-brand-teal text-ink-950 font-semibold'
                      : 'text-ink-300 hover:text-ink-100 hover:bg-ink-800'
                  }`}
                  title="사고유형 360° 컴퍼스"
                >
                  컴퍼스
                </button>
                <button
                  type="button"
                  onClick={() => switchMainView('tree')}
                  className={`text-[10.5px] px-2 py-0.5 transition-colors border-l border-ink-700 ${
                    mainView === 'tree'
                      ? 'bg-brand-teal text-ink-950 font-semibold'
                      : 'text-ink-300 hover:text-ink-100 hover:bg-ink-800'
                  }`}
                  title="트리 시각화"
                >
                  🌳 트리
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
              zone={treeState.zone ?? 1}
              regressSuggested={treeState.regress_suggested ?? false}
              coreClueLikelihood={treeState.core_clue_likelihood ?? 0}
              // P.35.4 — 점 클릭 → trail point detail (적재 로그 매칭)
              onTrailPointClick={setSelectedTrailPoint}
              highlightedClueKey={highlightedClueKey}
            />
          )}
        </Card>

        {/* P.35.4 — 컴파스 점 클릭 시 trail point detail 카드 */}
        {selectedTrailPoint && mainView === 'compass' && (
          <Card
            title="🎯 단서 점 정보"
            subtitle="컴파스에서 클릭한 단서 — 적재 로그와 매칭"
            action={
              <button
                onClick={() => setSelectedTrailPoint(null)}
                className="text-[10.5px] text-ink-500 hover:text-ink-200 font-mono"
              >
                × 닫기
              </button>
            }
          >
            <TrailPointDetail
              point={selectedTrailPoint}
              loadedLogs={loadedLogs}
              onSelectLog={() => setHighlightedClueKey(null /* 로그 선택 후 강조 초기화 */)}
            />
          </Card>
        )}

        {/* P.35.2 — 분석 로그 적재 카드 (full width row) */}
        {caseId && (
          <Card title="분석 로그 적재함">
            <EvidenceLogPanel
              onAdoptFromLog={handleAdoptFromLog}
              onLogSelect={(l) => {
                // 적재 row 클릭 — 컴파스 detail 영역에 매칭 단서 표시
                setSelectedTrailPoint({
                  clue_key: `__loaded__:${l.loaded_id}`,
                  label: l.label,
                  stage: 1,
                  posterior: scoresForBar,
                });
              }}
              disabled={loading || isSubmitting}
            />
          </Card>
        )}

        {/* 단서 직접 입력 카드 제거 (2026-06-03 사용자 요청) — 단서는 1차 정찰 옵션·
            분석 로그 적재함·트리/IG 후보 채택으로만 추가. 단서는 수사 보드로 이관. */}
        <BridgeToBoardCard
          caseId={caseId}
          acceptedClueCount={Math.max(0, treeState.path.length - 1)}
          onToast={showToast}
        />
      </div>

      {/* 우측 sticky — 신뢰도 + 가설 + IG 후보 */}
      <div className="col-span-12 lg:col-span-4 space-y-3">
        <Card title="현재 신뢰도">
          <ConfidenceGauge scores={scoresForBar} scoringMode="bayesian" />
          <div className="mt-3">
            <HypothesisScoreBar
              scores={scoresForBar}
              scoringMode="bayesian"
              limit={2}
              onClickIncidentType={handleClickIncidentType}
              expandedType={expandedGuideType}
              guidePreview={
                expandedGuideType ? guidePreviewCache[expandedGuideType] ?? null : null
              }
              guideLoading={guidePreviewLoading}
              onOpenFullGuide={handleOpenFullGuide}
              onAdoptGuideClue={handleAdoptGuideClue}
              acceptedClueKeys={acceptedClueKeys}
            />
          </div>
        </Card>

        {/* V1.fix.9 (2026-05-31) — Zone 강등 시 회귀 권고 배너 (Zone 무관 노출).
            기존: AttackChainCard 안에 회귀 메시지 → zone=1 강등 시 카드와 함께 사라져
                  사용자가 다음 행동 모르는 문제. 별도 배너로 분리. */}
        {(treeState.regress_suggested || treeState.zone === 1) &&
          treeState.regress_suggested && (
            <RegressBanner
              entropyBits={treeState.confidence.entropy_bits ?? 0}
              primaryProb={treeState.confidence.primary_prob ?? 0}
              secondaryProb={treeState.confidence.secondary_prob ?? 0}
              regressSuggested={treeState.regress_suggested ?? false}
            />
          )}

        {/* Phase M.3 — Zone 2 진입 시 복합 가설 chain (paradigm §21.5) */}
        {treeState.zone === 2 && treeState.attack_chain && treeState.attack_chain.length > 0 && (
          <Card
            title="복합 가설 chain"
            subtitle="ATT&CK Kill Chain 시간순 · 카드 클릭 → 해당 가설 변별 단서 필터"
          >
            <AttackChainCard
              chain={treeState.attack_chain}
              selectedHypothesis={chainFilterHypothesis}
              onSelectHypothesis={setChainFilterHypothesis}
              regressSuggested={false /* V1.fix.9 — 외부 RegressBanner 가 노출 */}
              disabled={loading || isSubmitting}
              path={treeState.path}
            />
          </Card>
        )}

        <Card title="다음 단서 후보" subtitle="Information Gain 순">
          <NextCluePanel
            scores={scoresForBar}
            igCandidates={treeState.candidates}
            entropyBits={treeState.confidence.entropy_bits}
            onAdoptCandidate={(c) => handleAdoptCandidate(c, 'tree_candidate')}
            onRefreshCandidates={() => refreshCandidates(caseId)}
            disabled={loading || isSubmitting}
            scoringMode={treeState.scoring_mode}
            mode={treeState.zone === 2 ? 'chain' : 'standard'}
            chainFilterHypothesis={chainFilterHypothesis}
          />
        </Card>

        {/* 채택된 단서 — 정보 + 삭제 (삭제 시 트리·컴퍼스 replay 재계산) */}
        <Card title="채택된 단서" subtitle="삭제하면 트리·컴퍼스가 재계산됩니다">
          {(() => {
            const adopted = (treeState.path ?? []).filter(
              (n) => n.depth > 0 && n.clue_key !== '__ROOT__',
            );
            if (adopted.length === 0) {
              return (
                <p className="text-[11px] text-ink-500 italic py-3 text-center">
                  아직 채택된 단서가 없습니다 — 후보 클릭·직접 입력·로그 분석으로 추가
                </p>
              );
            }
            const SOURCE_KO: Record<string, string> = {
              system: '시스템',
              tree_candidate: '후보 선택',
              direct_input: '직접 입력',
              log_analysis: '로그 분석',
              heal: '자동 복구',
            };
            return (
              <ul className="space-y-1.5">
                {adopted.map((n) => (
                  <li
                    key={n.node_id}
                    className="flex items-start gap-2 bg-ink-900/50 border border-ink-700/60 rounded-lg px-2.5 py-2"
                  >
                    <span className="text-[10px] font-mono text-ink-500 shrink-0 mt-0.5">
                      {n.depth}.
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-[11.5px] text-ink-100 font-medium truncate">
                        {n.label}
                      </div>
                      <div className="text-[9.5px] text-ink-500 font-mono mt-0.5">
                        {n.category}
                        {n.value ? `:${n.value}` : ''}
                        {' · '}
                        {SOURCE_KO[n.source] ?? n.source}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={async () => {
                        if (!caseId) return;
                        if (
                          !window.confirm(
                            `단서 "${n.label}" 을(를) 삭제합니다.\n남은 단서로 트리·컴퍼스가 재계산됩니다.`,
                          )
                        )
                          return;
                        try {
                          await retract(caseId, n.node_id);
                          setChainFilterHypothesis(null);
                          showToast(`단서 삭제 — ${n.label}`, 2500);
                        } catch (e) {
                          const msg = e instanceof Error ? e.message : String(e);
                          showToast(`단서 삭제 실패: ${msg}`, 4500);
                        }
                      }}
                      disabled={loading || isSubmitting}
                      className="text-[10px] text-ink-500 hover:text-brand-red font-mono shrink-0 self-center disabled:opacity-40 disabled:cursor-not-allowed"
                      title="이 단서를 삭제하고 트리·컴퍼스 재계산"
                    >
                      × 삭제
                    </button>
                  </li>
                ))}
              </ul>
            );
          })()}
        </Card>

        {treeState.confidence.primary && (
          <Card
            title="사고유형 확정 가능"
            subtitle="사용자 결정 — 확률 무관 언제든 확정 가능 (자동 종료 X)"
          >
            <div className="space-y-2">
              <div className="text-[12.5px] text-ink-100">
                <span className="font-bold text-brand-teal">
                  {INCIDENT_TYPE_KO[treeState.confidence.primary]}
                </span>{' '}
                {(treeState.confidence.primary_prob * 100).toFixed(1)}%
                {!treeState.confidence.confidence_reached && (
                  <span className="ml-2 text-[10px] text-amber-400">
                    · 신뢰도 미도달 (잠정 확정)
                  </span>
                )}
              </div>
              {treeState.confidence.secondary && (
                <div className="text-[10.5px] text-ink-400">
                  2위 {INCIDENT_TYPE_KO[treeState.confidence.secondary]}{' '}
                  {(treeState.confidence.secondary_prob * 100).toFixed(1)}% · 격차{' '}
                  {(treeState.confidence.gap * 100).toFixed(1)}%p
                </div>
              )}
              {/* Phase N.4 — 자동/수동 진입 양립 (paradigm §23) */}
              <div className="flex flex-col gap-1.5 pt-1">
                <button
                  type="button"
                  onClick={async () => {
                    if (!caseId || !treeState.confidence.primary) return;
                    try {
                      await advanceStage(caseId, treeState.confidence.primary);
                      setChainFilterHypothesis(null);
                      showToast(
                        `🔗 ${INCIDENT_TYPE_KO[treeState.confidence.primary]} 확정 — 다음 단계 자동 추적 시작`,
                        3500,
                      );
                    } catch (e) {
                      const msg = e instanceof Error ? e.message : String(e);
                      showToast(`다음 단계 진입 실패: ${msg}`, 4500);
                    }
                  }}
                  disabled={isSubmitting || loading}
                  className="text-[11px] font-semibold bg-emerald-600 hover:bg-emerald-500 text-ink-950 px-3 py-1.5 rounded transition-colors disabled:opacity-40"
                  title="paradigm §23 Multi-Stage — 확정 가설 anchor + 연관 가설 새 baseline"
                >
                  🔗 다음 단계 추적 (multi-stage) →
                </button>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleConfirm}
                    disabled={isSubmitting}
                    className="flex-1 text-[11px] bg-brand-teal hover:bg-brand-tealDark text-ink-950 px-3 py-1.5 rounded transition-colors disabled:opacity-40"
                    title="단일 사고유형 확정 + V-2 로그 수집으로 진행"
                  >
                    확정하고 V-2 로 →
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      /* 단서 더 채택 — confidence 카드는 알림으로 남음 */
                    }}
                    className="text-[11px] text-ink-300 hover:text-ink-100 border border-ink-700 hover:border-ink-500 px-3 py-1.5 rounded transition-colors"
                  >
                    단서 더 채택
                  </button>
                </div>
              </div>
            </div>
          </Card>
        )}

        {/* V1.fix.20 — BridgeToBoardCard 를 좌측 메인 영역 (단서 직접 입력 옆) 으로 이동.
            우측 영역은 신뢰도·가설·IG 후보·확정으로 집중. */}

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onPrev}
            className="text-[11px] text-ink-300 hover:text-ink-100 border border-ink-700 hover:border-ink-500 px-3 py-1.5 rounded transition-colors"
          >
            ← 이전 단계
          </button>
          {/* 미확정 진행 버튼 제거 (2026-06-04) — 상단 '사고유형 확정 가능' 카드가
              확률 무관 항상 노출되어 잠정 확정을 커버. */}
        </div>
      </div>
    </div>
  );
};

// ── P.35.4 (2026-05-31) — 컴파스 trail point detail 패널 ──
//   사용자: "캠퍼스에서 점을 클릭하면 그 로그에 대한 정보가 자세히 보이게".
//   동작:
//     · 점 클릭 → onTrailPointClick 으로 부모 (Step3) 가 selectedTrailPoint 갱신
//     · 이 컴포넌트가 selectedTrailPoint.clue_key 와 매칭되는 적재 로그 검색
//     · 매칭 있으면 타임스탬프·기법·source 정보 노출 / 없으면 단서 메타만
interface TrailPointDetailProps {
  point: {
    clue_key: string;
    label: string;
    stage: number;
    posterior: HypothesisScores;
  };
  loadedLogs: LoadedLog[];
  onSelectLog?: (log: LoadedLog) => void;
}

const TrailPointDetail = ({ point, loadedLogs, onSelectLog }: TrailPointDetailProps) => {
  // 적재 로그 매칭 — 간단 휴리스틱: __loaded__ prefix 면 loaded_id 매칭,
  //   그 외엔 clue_key 의 value 가 로그 fields 에 포함되는지.
  const matchedLogs = (() => {
    if (point.clue_key.startsWith('__loaded__:')) {
      const lid = point.clue_key.slice('__loaded__:'.length);
      const m = loadedLogs.find((l) => l.loaded_id === lid);
      return m ? [m] : [];
    }
    // clue_key 형식: "TYPE:value" — value 가 fields 안에 있으면 매칭
    const parts = point.clue_key.split(':');
    const value = parts.length > 1 ? parts.slice(1).join(':') : point.clue_key;
    return loadedLogs.filter((l) =>
      Object.values(l.fields).some((v) =>
        v != null && String(v).toLowerCase().includes(value.toLowerCase()),
      ),
    );
  })();

  // top-3 사고유형
  const topIncidents = Object.entries(point.posterior)
    .filter(([k, v]) => k !== 'UNCLASSIFIED' && typeof v === 'number' && v >= 0.05)
    .sort((a, b) => (b[1] as number) - (a[1] as number))
    .slice(0, 3) as Array<[IncidentType, number]>;

  return (
    <div className="space-y-2.5 text-[11.5px]">
      <div>
        <div className="text-ink-400 text-[9.5px] uppercase tracking-wider mb-1">단서</div>
        <div className="font-semibold text-ink-100">{point.label}</div>
        <div className="font-mono text-[10px] text-ink-500 mt-0.5">
          {point.clue_key} · Stage {point.stage}
        </div>
      </div>

      <div>
        <div className="text-ink-400 text-[9.5px] uppercase tracking-wider mb-1">
          이 시점 사고유형 적합도 (top {topIncidents.length})
        </div>
        <div className="flex flex-wrap gap-1">
          {topIncidents.map(([type, p]) => (
            <span
              key={type}
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-ink-700/60 bg-ink-900/60 text-[10.5px]"
            >
              <span>{INCIDENT_TYPE_KO[type] ?? type}</span>
              <span className="font-mono text-brand-teal">{(p * 100).toFixed(1)}%</span>
            </span>
          ))}
        </div>
      </div>

      <div>
        <div className="text-ink-400 text-[9.5px] uppercase tracking-wider mb-1">
          연결된 분석 로그 ({matchedLogs.length})
        </div>
        {matchedLogs.length === 0 ? (
          <div className="text-[10.5px] text-ink-500 italic">
            매칭되는 적재 로그 없음 — 단서 카탈로그 키 또는 로그 fields 검토
          </div>
        ) : (
          <ul className="space-y-1">
            {matchedLogs.map((l) => (
              <li
                key={l.loaded_id}
                className="bg-ink-950/40 border border-ink-700/40 rounded px-2 py-1.5 cursor-pointer hover:border-brand-teal/40"
                onClick={() => onSelectLog?.(l)}
              >
                <div className="flex items-start gap-1.5">
                  <span
                    className={`text-[9px] font-mono px-1 py-px rounded shrink-0 ${
                      l.source === 'attack'
                        ? 'bg-purple-900/40 text-purple-200 border border-purple-700/40'
                        : 'bg-sky-900/40 text-sky-200 border border-sky-700/40'
                    }`}
                  >
                    {l.source === 'attack' ? 'ATT&CK' : 'OCSF'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] text-ink-100 truncate">{l.label}</div>
                    <div className="text-[10px] text-ink-500 font-mono">
                      🕒 {l.time?.slice(0, 19) ?? '시각 없음'}
                      {l.technique_id ? ` · ${l.technique_id}` : ''}
                    </div>
                  </div>
                </div>
                {/* fields detail */}
                <div className="mt-1 grid grid-cols-2 gap-x-2 gap-y-0.5 text-[10px] font-mono">
                  {Object.entries(l.fields).map(([k, v]) =>
                    v == null ? null : (
                      <div key={k} className="truncate">
                        <span className="text-ink-500">{k}:</span>{' '}
                        <span className="text-ink-200">{String(v).slice(0, 32)}</span>
                      </div>
                    ),
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default Step3_EvidenceTreeDiscovery;
