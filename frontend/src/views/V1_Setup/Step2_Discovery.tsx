/**
 * V-1 Step 2 — Discovery Loop (dev3 신규).
 *
 * 3-panel:
 *   좌측: 시스템 구성 (기존 Step2_SystemConfig 의 보안 정책·CSP 특화 폼)
 *   중앙: 결정 트리 질문 (DecisionTreeQuestion) — 향후 단서 입력·부분 로그 분석 추가
 *   우측: 가설 점수 (HypothesisScoreBar) + 추천 결과
 *
 * 차후 확장 (다음 사이클):
 *   - 단서 입력 (CluesInput) — IP·계정·해시·도메인·시각·서비스명
 *   - 부분 로그 분석 (DropZone 재사용)
 *   - 다음 단서 제안 (next_clue_graph.json 시각화)
 *   - 결정 트리 시각화 (react-flow 미니 그래프)
 *
 * 학술 근거: docs/dev3/V1_재설계_청사진.md §2 Step 2
 */
import { useEffect, useState } from 'react';

import Card from '@/components/Card';
import Badge from '@/components/Badge';
import DecisionTreeQuestion from '@/components/DecisionTreeQuestion';
import HypothesisScoreBar from '@/components/HypothesisScoreBar';
import { useCaseStore } from '@/stores/useCaseStore';
import { useToastStore } from '@/stores/useToastStore';
import { useTriageStore } from '@/stores/useTriageStore';
import { nextTriage, startTriage } from '@/api/triage';

import Step2_SystemConfig from './Step2_SystemConfig';

import type {
  IncidentType,
  TriageRecommendation,
  TriageTreeNode,
} from '@/types';

interface Step2DiscoveryProps {
  csp: string | null;
  incidentType: string | null;
  onPrev: () => void;
  onSubmit: (
    config: Parameters<
      React.ComponentProps<typeof Step2_SystemConfig>['onSubmit']
    >[0],
    confirmedIncidentType: IncidentType,
  ) => void;
  isSubmitting?: boolean;
}

const INCIDENT_TYPE_KO: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '자격증명 탈취',
  PRIVILEGE_ESCALATION: '권한 상승',
  DATA_EXFILTRATION: '데이터 유출',
  AUDIT_LOG_TAMPERING: '감사 로그 변조',
  MULTI_CSP_LATERAL: '멀티 CSP 횡이동',
  UNCLASSIFIED: '미분류',
};

const OUTCOME_LABEL: Record<TriageRecommendation['outcome'], string> = {
  auto_confirm: '✅ 자동 확정',
  propose_single: '🎯 단일 가설 제시',
  propose_composite: '🔀 복합 가설 (주 + 부)',
  continue_or_skip: '➡ 추가 단서 또는 UNCLASSIFIED 진행',
};

const Step2_Discovery = ({
  csp,
  incidentType,
  onPrev,
  onSubmit,
  isSubmitting,
}: Step2DiscoveryProps) => {
  const caseId = useCaseStore((s) => s.caseId);
  const showToast = useToastStore((s) => s.show);

  const {
    currentNodeId,
    completedPath,
    hypothesisScores,
    recommendation,
    isTerminal,
    startTriage: storeStart,
    recordAnswer,
    setCurrentNode,
    setHypothesisScores,
    setRecommendation,
    setTerminal,
    reset: resetTriage,
  } = useTriageStore();

  const [currentNode, setCurrentNodeData] = useState<TriageTreeNode | null>(null);
  const [loading, setLoading] = useState(false);

  // 트리 시작 — 케이스가 있고 currentNodeId 가 없을 때
  useEffect(() => {
    let cancelled = false;
    const initTree = async () => {
      if (!caseId || currentNodeId) return;
      setLoading(true);
      try {
        const res = await startTriage(caseId);
        if (cancelled) return;
        if (res.next_node) {
          storeStart(res.next_node.id);
          setCurrentNodeData(res.next_node);
          setHypothesisScores(res.hypothesis_scores);
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        showToast(`트리아주 시작 실패: ${msg}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    initTree();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  // currentNodeId 변경 시 currentNode 데이터 동기화 (mock 응답에서 채워짐)
  // — 실제로는 startTriage / nextTriage 응답에서 next_node 를 직접 받음

  const handleSubmitAnswer = async (answerIds: string[]) => {
    if (!caseId || !currentNodeId) return;
    setLoading(true);
    try {
      const res = await nextTriage(
        {
          caseId,
          current_node_id: currentNodeId,
          answer_ids: answerIds,
        },
        hypothesisScores,
        completedPath,
      );
      recordAnswer(currentNodeId, answerIds);
      setHypothesisScores(res.hypothesis_scores);
      setRecommendation(res.recommendation ?? null);
      setTerminal(res.is_terminal);
      if (res.next_node) {
        setCurrentNode(res.next_node.id);
        setCurrentNodeData(res.next_node);
      } else {
        setCurrentNode(null);
        setCurrentNodeData(null);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(`트리아주 진행 실패: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  const handleResetTree = async () => {
    if (!caseId) return;
    resetTriage();
    setCurrentNodeData(null);
    setLoading(true);
    try {
      const res = await startTriage(caseId);
      if (res.next_node) {
        storeStart(res.next_node.id);
        setCurrentNodeData(res.next_node);
        setHypothesisScores(res.hypothesis_scores);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(`트리 리셋 실패: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  // 추천 결과에 따른 사고유형 확정 → 다음 단계로
  const handleAccept = (sysConfig: Parameters<typeof onSubmit>[0]) => {
    const chosen: IncidentType =
      recommendation?.primary?.incident_type ?? 'UNCLASSIFIED';
    onSubmit(sysConfig, chosen);
  };

  const handleSkip = (sysConfig: Parameters<typeof onSubmit>[0]) => {
    onSubmit(sysConfig, 'UNCLASSIFIED');
  };

  // 시스템 구성 폼은 submit 시 좌측에서 호출. 우리는 Discovery 결과와 묶어서 처리.
  // Step2_SystemConfig 는 form 의 onSubmit prop 으로 sysConfig 전달.
  // 우리는 그 sysConfig 를 받아 사고유형과 함께 onSubmit 호출.
  const [pendingConfig, setPendingConfig] = useState<
    Parameters<typeof onSubmit>[0] | null
  >(null);

  // 시스템 구성 제출 → 추천 결과에 따라 자동 또는 사용자 선택
  const handleSystemConfigSubmit = (
    config: Parameters<typeof onSubmit>[0],
  ) => {
    setPendingConfig(config);
    // 자동 확정이면 바로 진행
    if (recommendation?.outcome === 'auto_confirm') {
      handleAccept(config);
    }
    // 그 외에는 사용자 명시 클릭 대기 (handleAccept / handleSkip)
  };

  return (
    <div className="space-y-4 animate-fade-up">
      {/* 헤더 — 가벼운 안내 */}
      <div className="panel p-3 border-l-[3px] border-l-brand-teal text-[11.5px]">
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <span className="eyebrow">Layer 0 · M0-2 · Discovery Loop</span>
          <Badge tone="purple" size="sm">
            UNCLASSIFIED
          </Badge>
          <span className="text-ink-400">
            단서·트리아주 누적으로 사고유형을 추정합니다
          </span>
        </div>
        <div className="text-ink-500 text-[10.5px]">
          TheHive·DFIR-IRIS·NIST 800-61r2 표준 흐름. 결정성 100% — 같은 답변 시퀀스는 같은 결과.
        </div>
      </div>

      {/* 3-panel 레이아웃 */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_minmax(360px,400px)] gap-4">
        {/* 좌측+중앙 묶음 (큰 영역) */}
        <div className="space-y-3 min-w-0">
          {/* 중앙 — 결정 트리 질문 */}
          <Card
            title={<>📋 결정 트리 (KISA §2.4 + NIST 800-61r2 §3.2)</>}
            subtitle="질문 답변이 우측 가설 점수에 즉시 반영됩니다"
          >
            {!caseId ? (
              <p className="text-[12px] text-ink-400">
                케이스 ID 가 없습니다. 이전 단계에서 케이스를 생성해주세요.
              </p>
            ) : !currentNode ? (
              loading ? (
                <p className="text-[12px] text-ink-400">트리아주 로딩 중…</p>
              ) : (
                <div>
                  <p className="text-[12px] text-ink-300 mb-2">
                    트리가 종료되었습니다. 우측 추천을 확인하세요.
                  </p>
                  <button onClick={handleResetTree} className="btn-ghost btn-sm">
                    ↻ 처음부터
                  </button>
                </div>
              )
            ) : (
              <DecisionTreeQuestion
                node={currentNode}
                step={completedPath.length + 1}
                totalEstimated={3}
                loading={loading}
                onSubmit={handleSubmitAnswer}
                onReset={handleResetTree}
              />
            )}
          </Card>

          {/* 좌측 — 시스템 구성 (기존 폼 그대로) */}
          <Card
            title={<>⚙ 시스템 구성 (environment_modifiers)</>}
            subtitle="입력한 구성·보안 정책이 Step 3 가이드 우선순위에 반영됩니다"
          >
            <Step2_SystemConfig
              csp={csp}
              incidentType={incidentType}
              onPrev={onPrev}
              onSubmit={handleSystemConfigSubmit}
              isSubmitting={isSubmitting}
            />
          </Card>
        </div>

        {/* 우측 — 가설 점수 + 추천 + 액션 (sticky) */}
        <div className="min-w-0">
          <div className="panel p-4 lg:sticky lg:top-4 space-y-4">
            <HypothesisScoreBar
              scores={hypothesisScores}
              highlightPrimary={recommendation?.primary?.incident_type}
              highlightSecondary={recommendation?.secondary?.incident_type}
            />

            {/* 트리 경로 요약 (간단) */}
            {completedPath.length > 0 && (
              <div>
                <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-1.5">
                  🧭 트리 경로
                </div>
                <ul className="space-y-0.5">
                  {completedPath.map((p) => (
                    <li
                      key={p.node_id}
                      className="text-[10.5px] text-ink-300 leading-5"
                    >
                      <code className="text-ink-500">{p.node_id}</code>
                      <span className="text-ink-400 ml-1">
                        → {p.selected_option_ids.length}개 선택
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 추천 결과 */}
            {recommendation && (
              <div className="border-t border-ink-700/40 pt-3">
                <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-1.5">
                  🎯 추천
                </div>
                <div className="text-[12px] mb-2">
                  <Badge
                    tone={
                      recommendation.outcome === 'auto_confirm'
                        ? 'teal'
                        : recommendation.outcome === 'propose_composite'
                        ? 'amber'
                        : recommendation.outcome === 'propose_single'
                        ? 'blue'
                        : 'gray'
                    }
                    size="sm"
                  >
                    {OUTCOME_LABEL[recommendation.outcome]}
                  </Badge>
                </div>

                {recommendation.primary && (
                  <div className="text-[11.5px] text-ink-200 mb-1">
                    주: <b>{INCIDENT_TYPE_KO[recommendation.primary.incident_type]}</b>{' '}
                    <code className="text-ink-500">
                      ({recommendation.primary.score}점)
                    </code>
                  </div>
                )}
                {recommendation.secondary && (
                  <div className="text-[11.5px] text-ink-300 mb-1">
                    부: {INCIDENT_TYPE_KO[recommendation.secondary.incident_type]}{' '}
                    <code className="text-ink-500">
                      ({recommendation.secondary.score}점)
                    </code>
                  </div>
                )}

                {recommendation.rationale.length > 0 && (
                  <ul className="text-[10.5px] text-ink-400 leading-5 mt-1.5 list-disc pl-4 space-y-0.5">
                    {recommendation.rationale.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                )}

                <p className="text-[10.5px] text-ink-300 mt-2 leading-5">
                  {recommendation.message}
                </p>
              </div>
            )}

            {/* 액션 버튼 — 시스템 구성이 제출되고 추천이 있을 때만 활성 */}
            {pendingConfig && recommendation && (
              <div className="border-t border-ink-700/40 pt-3 space-y-1.5">
                {recommendation.primary &&
                  recommendation.outcome !== 'continue_or_skip' && (
                    <button
                      onClick={() => handleAccept(pendingConfig)}
                      disabled={isSubmitting}
                      className="btn-primary btn-sm w-full disabled:opacity-50"
                    >
                      {isSubmitting
                        ? '진행 중…'
                        : `✓ ${INCIDENT_TYPE_KO[recommendation.primary.incident_type]} 로 확정`}
                    </button>
                  )}
                <button
                  onClick={() => handleSkip(pendingConfig)}
                  disabled={isSubmitting}
                  className="btn-ghost btn-sm w-full disabled:opacity-50"
                >
                  건너뛰기 — UNCLASSIFIED 진행
                </button>
              </div>
            )}

            {!pendingConfig && isTerminal && (
              <p className="text-[10.5px] text-ink-500 leading-5 border-t border-ink-700/40 pt-2">
                ⓘ 좌측 시스템 구성 폼을 제출하면 추천 사고유형으로 다음 단계 진행 가능.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Step2_Discovery;
