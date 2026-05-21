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
import CluesInput from '@/components/CluesInput';
import DecisionTreeQuestion from '@/components/DecisionTreeQuestion';
import DiscoveryIntroModal, {
  hasDismissedDiscoveryIntro,
} from '@/components/DiscoveryIntroModal';
import HypothesisBreakdownChart from '@/components/HypothesisBreakdownChart';
import HypothesisScoreBar from '@/components/HypothesisScoreBar';
import NextCluePanel from '@/components/NextCluePanel';
import PartialLogAnalysis from '@/components/PartialLogAnalysis';
import TriageStepper from '@/components/TriageStepper';
import TriageTreeMinimap from '@/components/TriageTreeMinimap';

import type { ClueType } from '@/types';
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

// dev3 B-2 (2026-05-19): 클라이언트 측 TECH_WEIGHTS·applyTechniqueWeights 제거.
// 점수 산출은 백엔드 /api/triage/analyze-logs 응답으로만 — 결정성 100% 보장
// (청사진 §3 — 정적 weights.json 단일 소스). 학술 변호: 클라이언트 mock 가중치
// 잔존은 weights.json 과 어긋날 위험이 있어 일괄 제거.

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
  // ── dev3 C-1 신규 4종 (2026-05-19, MULTI_CSP_LATERAL 제거) ──
  RANSOMWARE: '랜섬웨어',
  MISCONFIG_EXPOSURE: '설정 오류 노출',
  PHISH_INITIAL_ACCESS: '피싱 초기 침투',
  INSIDER_THREAT: '내부자 위협',
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
  const observables = useCaseStore((s) => s.observables);
  const addObservable = useCaseStore((s) => s.addObservable);
  const removeObservable = useCaseStore((s) => s.removeObservable);
  const showToast = useToastStore((s) => s.show);

  const {
    currentNodeId,
    completedPath,
    hypothesisScores,
    mappedTechniques,
    recommendation,
    isTerminal,
    startTriage: storeStart,
    recordAnswer,
    addMappedTechniques,
    setCurrentNode,
    setHypothesisScores,
    setRecommendation,
    setTerminal,
    reset: resetTriage,
  } = useTriageStore();

  const [currentNode, setCurrentNodeData] = useState<TriageTreeNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [introOpen, setIntroOpen] = useState(false);
  /** NextCluePanel 권장 단서 클릭 시 CluesInput 의 selectedType 동기화 (mount 시점 키) */
  const [preferredClueType, setPreferredClueType] = useState<ClueType | null>(null);
  // Q4 (2026-05-21): 트리 답변에서 자동 추출된 variant — CluesInput 토글 자동 선택
  const [preferredVariant, setPreferredVariant] = useState<string | null>(null);

  // 진입 시 사전 안내 모달 표시 (영속화 체크)
  useEffect(() => {
    if (!hasDismissedDiscoveryIntro()) {
      setIntroOpen(true);
    }
  }, []);

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

  // Q4 (2026-05-21): 트리 답변 → 단서 힌트 매핑 — 답변 선택 시 CluesInput 의 type
  // + variant 자동 선택. 사용자가 단서를 직접 추가하면 가중치까지 함께 부여됨.
  // 학술 근거: 결정 트리·단서·가중치 3 자산의 단일 trace 형성 (재현성·일관성 보장).
  const ANSWER_TO_CLUE_HINT: Record<
    string,
    { clueType: ClueType; variant?: string; reason: string }
  > = {
    // Q2A 옵션
    non_korean_ip: { clueType: 'IP_ADDRESS', variant: 'non_korean', reason: 'CSP 알람의 비국내 IP — IP 단서 추가' },
    object_storage_burst: { clueType: 'SERVICE', variant: 'object_storage', reason: 'Object Storage 대량 활동 — 서비스 단서' },
    privilege_change: { clueType: 'ACCOUNT', variant: 'privilege_changed', reason: '권한 변경 알람 — 해당 계정 단서' },
    audit_log_disabled: { clueType: 'SERVICE', variant: 'cloud_trail', reason: '감사 로그 비활성 — Cloud Trail 단서' },
    off_hours: { clueType: 'TIME_WINDOW', variant: 'off_hours', reason: '비표준 시각 — 시각 윈도우 단서' },
    // Q2B 옵션
    identity_theft: { clueType: 'ACCOUNT', variant: 'inactive_to_active', reason: '신원 도용 — 해당 계정 단서' },
    multi_csp_suspicious: { clueType: 'IP_ADDRESS', variant: 'multi_csp_observed', reason: '멀티 CSP — IP 단서' },
    data_exposed: { clueType: 'SERVICE', variant: 'object_storage', reason: '데이터 노출 — 서비스 단서' },
    // Q2C 옵션
    iam_burst: { clueType: 'ACCOUNT', variant: 'newly_created', reason: '신규 IAM 다수 — 계정 단서' },
    permission_changes: { clueType: 'ACCOUNT', variant: 'privilege_changed', reason: '권한 변경 다수 — 계정 단서' },
    log_gap: { clueType: 'SERVICE', variant: 'cloud_trail', reason: '감사 로그 누락 — Cloud Trail 단서' },
    data_access: { clueType: 'SERVICE', variant: 'object_storage', reason: '비정상 데이터 액세스 — 서비스 단서' },
    // Q3 옵션
    fail_then_success: { clueType: 'ACCOUNT', variant: 'mfa_disabled', reason: '실패→성공 패턴 — MFA 미적용 계정 단서' },
    multi_region_concurrent: { clueType: 'IP_ADDRESS', variant: 'multi_account', reason: '동시 다지역 — IP 단서' },
    storage_policy_change: { clueType: 'SERVICE', variant: 'object_storage', reason: 'Object Storage 정책 변경 — 서비스 단서' },
    serverless_new: { clueType: 'SERVICE', variant: 'iam', reason: 'Serverless 신규 — IAM 단서' },
  };

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
      // Q4: 답변 중 단서 힌트가 있는 것 — 첫 번째만 적용 (CluesInput 자동 선택)
      let hintFired = false;
      for (const ansId of answerIds) {
        const hint = ANSWER_TO_CLUE_HINT[ansId];
        if (hint) {
          setPreferredClueType(hint.clueType);
          setPreferredVariant(hint.variant ?? null);
          showToast(`💡 ${hint.reason}`, 2800);
          hintFired = true;
          break;
        }
      }
      // §4-4: 격차 기반 진단 hint — 1위·2위 점수 격차로 토스트
      if (!hintFired) {
        const sorted = Object.entries(res.hypothesis_scores)
          .filter(([k]) => k !== 'UNCLASSIFIED')
          .sort(([, a], [, b]) => b - a);
        if (sorted.length >= 2) {
          const gap = sorted[0][1] - sorted[1][1];
          if (gap < 10) {
            showToast('⚠ 여전히 모호 — 추가 질문 권장', 2500);
          } else if (gap < 20) {
            showToast('가설 형성 중 — Q4·Q5·Q6 진행', 2500);
          } else if (gap < 30) {
            showToast('🎯 명확해지는 중', 2000);
          } else {
            showToast('🎯 명확 — 조기 확정 가능', 2500);
          }
        }
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
      {/* 진입 사전 안내 모달 — 첫 진입 시만 */}
      <DiscoveryIntroModal open={introOpen} onClose={() => setIntroOpen(false)} />

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
          <button
            onClick={() => setIntroOpen(true)}
            className="ml-auto text-[10.5px] text-brand-blue hover:underline"
          >
            ⓘ 사전 안내 다시 보기
          </button>
        </div>
        <div className="text-ink-500 text-[10.5px]">
          TheHive·DFIR-IRIS·NIST 800-61r2 표준 흐름. 결정성 100% — 같은 답변 시퀀스는 같은 결과.
        </div>
      </div>

      {/* 답변 타임라인 스테퍼 (§4-5) + 조기 종료 인라인 카드 (§4-6) */}
      {(completedPath.length > 0 || currentNodeId) && (
        <TriageStepper
          completedPath={completedPath}
          currentNodeId={currentNodeId}
          hypothesisScores={hypothesisScores}
          isTerminal={isTerminal}
          onStepClick={(nodeId, _stepIndex) => {
            showToast(`${nodeId} 로 되돌아갑니다 — 해당 노드부터 재진행`, 2500);
          }}
          onEarlyConfirm={() => {
            if (pendingConfig) {
              handleAccept(pendingConfig);
            } else {
              showToast('좌측 시스템 구성 폼을 먼저 제출해주세요', 2500);
            }
          }}
          onContinue={() => {
            showToast('Q4·Q5·Q6 추가 질문을 계속합니다', 2000);
          }}
        />
      )}

      {/* 3-panel 레이아웃 */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_minmax(360px,400px)] gap-4">
        {/* 좌측+중앙 묶음 (큰 영역) */}
        <div className="space-y-3 min-w-0">
          {/* ① 단서 입력 */}
          <Card
            title={<>📌 단서 입력 (Observable)</>}
            subtitle={
              preferredClueType
                ? `우측 권장 단서 — ${preferredClueType} 를 추가하세요`
                : 'DFIR-IRIS IOC + NIST 800-61r2 표 3-2 + Velociraptor artifact 기반 6종'
            }
          >
            <CluesInput
              key={`${preferredClueType ?? 'default'}-${preferredVariant ?? 'none'}`}
              observables={observables}
              preferredType={preferredClueType}
              preferredVariant={preferredVariant}
              onAdd={(o) => {
                addObservable(o);
                setPreferredClueType(null); // 권장 단서 추가 후 힌트 제거
                setPreferredVariant(null);
              }}
              onAfterAdd={async (o) => {
                // Q2 (2026-05-21): 단서 추가 시 즉시 백엔드 /api/triage/analyze 호출 →
                // weight_key 가 있으면 그 가중치, 없으면 generic fallback (Q1) 적용.
                if (!caseId) return;
                try {
                  const { analyzeClue } = await import('@/api/triage');
                  const res = await analyzeClue(caseId, hypothesisScores, {
                    type: o.type,
                    value: o.value,
                    weight_key: o.weight_key,
                    note: o.note,
                    added_at: o.added_at,
                  });
                  setHypothesisScores(res.hypothesis_scores);
                  // 토스트는 첫 단서만 (스팸 방지 — variant 명시는 더 강한 가중치라 알림 가치 큼)
                  if (o.weight_key) {
                    showToast(`단서 가중치 적용 (${o.weight_key})`);
                  }
                } catch (e) {
                  // 분석 실패해도 단서는 누적 — 백엔드 미응답 시 store 만 유지
                  console.warn('[triage/analyze] 단서 분석 실패:', e);
                }
              }}
              onRemove={removeObservable}
              disabled={loading}
            />
          </Card>

          {/* ② 부분 로그 분석 (선택) */}
          <Card
            title={<>📊 부분 로그 분석 (선택)</>}
            subtitle="AWS Detective scope time + Microsoft Sentinel entity 표준 흐름"
          >
            <PartialLogAnalysis
              caseId={caseId}
              currentScores={hypothesisScores}
              mappedTechniques={mappedTechniques}
              onAnalyzed={(techIds, _filenames, newScores) => {
                // dev3 B-2: 백엔드 /api/triage/analyze-logs 가 권위 있는 점수 산출
                // — 클라이언트 응답을 그대로 적용 (학술 변호: 결정성 100%).
                addMappedTechniques(techIds);
                setHypothesisScores(newScores);
                showToast(`${techIds.length}개 기법 매핑 → 가설 점수 갱신`);
              }}
              disabled={loading}
            />
          </Card>

          {/* ③ 결정 트리 질문 */}
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
                totalEstimated={6}
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

            {/* §4-3: 신뢰도 게이지 — 1위 사고유형의 score / 70 비율 */}
            {(() => {
              const sorted = Object.entries(hypothesisScores)
                .filter(([k]) => k !== 'UNCLASSIFIED')
                .sort(([, a], [, b]) => b - a);
              if (sorted.length < 1 || sorted[0][1] === 0) return null;
              const topScore = sorted[0][1];
              const confidence = Math.min(100, Math.round((topScore / 70) * 100));
              const gap = sorted.length >= 2 ? sorted[0][1] - sorted[1][1] : topScore;
              const stage =
                confidence < 40
                  ? { color: 'bg-ink-600', text: '단서 부족', textColor: 'text-ink-400' }
                  : confidence < 70
                  ? { color: 'bg-brand-blue', text: '가설 형성 중', textColor: 'text-brand-blue' }
                  : confidence < 90
                  ? { color: 'bg-green-500', text: '🎯 가설 형성', textColor: 'text-green-400' }
                  : { color: 'bg-amber-400', text: '✅ 자동 확정 가능', textColor: 'text-amber-300' };
              return (
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[10.5px]">
                    <span className={`font-semibold ${stage.textColor}`}>
                      {stage.text}
                    </span>
                    <span className="text-ink-400">{confidence}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-ink-800/60 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ease-out ${stage.color} ${
                        confidence >= 90 ? 'animate-pulse' : ''
                      }`}
                      style={{ width: `${confidence}%` }}
                    />
                  </div>
                  {gap < 20 && sorted[0][1] > 0 && (
                    <div className="text-[9.5px] text-amber-400">
                      ⚠ 1위·2위 격차 {gap}점 — 복합 사고 의심
                    </div>
                  )}
                </div>
              );
            })()}

            {/* 트리 미니맵 (react-flow) — 사용자 결정 #3 */}
            <div>
              <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-1.5">
                🌳 결정 트리 진행
              </div>
              <TriageTreeMinimap
                currentNodeId={currentNodeId}
                completedNodeIds={completedPath.map((p) => p.node_id)}
                isTerminal={isTerminal}
              />
            </div>

            {/* 사고유형 비교 차트 (§4-8) */}
            {Object.values(hypothesisScores).some((v) => v > 0) && (
              <HypothesisBreakdownChart
                scores={hypothesisScores}
                highlightType={recommendation?.primary?.incident_type}
              />
            )}

            {/* 다음 단서 제안 — 클릭 시 좌측 CluesInput 활성 */}
            <NextCluePanel
              scores={hypothesisScores}
              onPickClueType={(type) => {
                setPreferredClueType(type);
                showToast(`좌측 단서 입력에서 ${type} 를 추가해주세요`);
                // 좌측 단서 입력 영역으로 자동 스크롤 — 컨테이너 미정의 시 무시
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            />

            {/* 단서 누적 요약 */}
            {observables.length > 0 && (
              <div className="border-t border-ink-700/40 pt-3">
                <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider mb-1.5">
                  📌 단서 {observables.length}개
                </div>
                <ul className="space-y-0.5">
                  {observables.slice(0, 5).map((o, i) => (
                    <li key={i} className="text-[10.5px] text-ink-300 leading-5 truncate">
                      <span className="text-ink-500">{o.type}</span> · {o.value}
                    </li>
                  ))}
                  {observables.length > 5 && (
                    <li className="text-[10.5px] text-ink-500">… 외 {observables.length - 5}개</li>
                  )}
                </ul>
                <p className="text-[10px] text-ink-500 mt-1.5 leading-4">
                  ※ 단서별 가설 점수 기여는 백엔드 /api/triage/analyze 가 구현되면 활성화됩니다.
                </p>
              </div>
            )}

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
