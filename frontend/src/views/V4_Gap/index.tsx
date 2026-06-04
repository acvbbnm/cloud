import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useMutation } from '@tanstack/react-query';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import Card from '@/components/Card';
import Badge from '@/components/Badge';
import { useToastStore } from '@/stores/useToastStore';
import { useCaseStore } from '@/stores/useCaseStore';
import { runGap } from '@/api/analysis';

import CompletenessKpi from './CompletenessKpi';
import type { GapType } from '@/types';

const INCIDENT_TYPE_KO: Record<string, string> = {
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

// 갭 유형별 탭 상태 점 색상
const GAP_DOT: Record<GapType, string> = {
  NONE: 'bg-brand-teal',
  COLLECTION: 'bg-brand-red',
  EVIDENCE: 'bg-brand-amber',
  INTERPRETATION: 'bg-brand-purple',
};

// gap_type 메타
const GAP_META: Record<
  GapType,
  { label: string; color: string; bg: string; icon: string; cta: 'board' | 'setup' | 'sherpa' | null }
> = {
  NONE: {
    label: '갭 없음',
    color: 'text-brand-teal',
    bg: 'border-brand-teal/40 bg-brand-teal/[0.04]',
    icon: '',
    cta: 'board',
  },
  COLLECTION: {
    label: '수집 갭',
    color: 'text-brand-red',
    bg: 'border-brand-red/40 bg-brand-red/[0.04]',
    icon: '',
    cta: 'setup',
  },
  EVIDENCE: {
    label: '증거 갭',
    color: 'text-brand-amber',
    bg: 'border-brand-amber/40 bg-brand-amber/[0.04]',
    icon: '',
    cta: null,
  },
  INTERPRETATION: {
    label: '해석 갭',
    color: 'text-brand-purple',
    bg: 'border-brand-purple/40 bg-brand-purple/[0.04]',
    icon: '',
    cta: 'sherpa',
  },
};

const V4Gap = () => {
  const navigate = useNavigate();
  const showToast = useToastStore((s) => s.show);
  const caseId = useCaseStore((s) => s.caseId);

  const [selectedIdx, setSelectedIdx] = useState(0);

  const gapMutation = useMutation({
    mutationFn: () => runGap(caseId!),
    onSuccess: (data) => {
      setSelectedIdx(0);
      const n = data.perType?.length ?? 0;
      showToast(
        n >= 2
          ? `갭 감지: 사고유형 ${n}종 · 전체 판정 ${data.gap_type}`
          : `갭 감지: ${data.gap_type} (완료율 ${data.completionRate ?? 'N/A'}%)`,
      );
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`갭 감지 실패: ${msg}`);
    },
  });

  if (!caseId) {
    return (
      <div>
        <PageHeader eyebrow="Layer 2 · M2-2" title="갭 감지" description="활성화된 사고 케이스가 없습니다." />
        <PageBody>
          <Card title={<>사고 케이스 없음</>}>
            <p className="text-[13px] text-ink-300 mb-3">V-1 사고 접수 위저드를 먼저 완료하세요.</p>
            <button onClick={() => navigate('/setup')} className="btn-primary">
              ← V-1 사고 접수
            </button>
          </Card>
        </PageBody>
      </div>
    );
  }

  const result = gapMutation.data;
  const perType = result?.perType ?? [];
  const isMulti = perType.length >= 2;
  // 표시 대상 — multi 면 선택된 사고유형, 단일/구버전 응답이면 전체 결과.
  const activeDetail = perType.length > 0 ? perType[Math.min(selectedIdx, perType.length - 1)] : result;
  const activeTypeLabel =
    activeDetail && 'incident_type' in activeDetail
      ? INCIDENT_TYPE_KO[activeDetail.incident_type] ?? activeDetail.incident_type
      : null;
  const meta = activeDetail ? GAP_META[activeDetail.gap_type] : null;

  return (
    <div>
      <PageHeader
        eyebrow="Layer 2 · M2-2"
        title="갭 감지"
        description="필수 증거 수집 + OCSF 정규화 + ATT&CK 매핑 결과를 종합하여 갭 유형을 자동 판정합니다."
        actions={
          <>
            <button
              onClick={() => gapMutation.mutate()}
              disabled={gapMutation.isPending}
              className="btn-ghost disabled:opacity-50"
            >
              {gapMutation.isPending ? '판정 중…' : ' 갭 감지 실행'}
            </button>
            {result?.gap_type === 'COLLECTION' && (
              <button
                onClick={() => {
                  showToast('Layer 0 복귀: 추가 로그 수집');
                  navigate('/setup');
                }}
                className="btn-danger"
              >
                ↩ Layer 0 복귀
              </button>
            )}
            {result?.gap_type === 'NONE' && (
              <button
                onClick={() => {
                  showToast('수사 보드 진행');
                  navigate('/board');
                }}
                className="btn-primary"
              >
                수사 보드 →
              </button>
            )}
            {result?.gap_type === 'INTERPRETATION' && (
              <button
                onClick={() => {
                  showToast('AI 셰르파 브리핑');
                  navigate('/sherpa');
                }}
                className="btn-primary"
              >
                AI 셰르파 →
              </button>
            )}
          </>
        }
      />

      <PageBody className="flex flex-col gap-6 animate-fade-up">
        {/* P.29 — 시연용 백엔드 응답 디버그 패널 제거 */}

        {/* 결과 없음 — 초기 상태 */}
        {!result && !gapMutation.isPending && (
          <Card title={<>Gap Detection Not Run</>}>
            <p className="text-[13px] text-ink-400">
              상단의 「갭 감지 실행」을 눌러 케이스의 증거 완결성을 분석해주세요.
            </p>
          </Card>
        )}

        {/* 다중 사고유형 탭 — 단서 루프에서 2개 이상 확정 시 유형별 독립 갭 전환 */}
        {result && isMulti && (
          <div className="panel p-3">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className="eyebrow">확정 사고유형 {perType.length}종 · 유형별 갭</span>
              <span className="text-[10.5px] text-ink-400">
                번호를 눌러 각 사고유형의 증거 완결성을 독립 확인하세요 (전체 판정: {result.gap_type})
              </span>
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {perType.map((pt, i) => {
                const active = i === Math.min(selectedIdx, perType.length - 1);
                return (
                  <button
                    key={pt.incident_type}
                    type="button"
                    onClick={() => setSelectedIdx(i)}
                    className={
                      active
                        ? 'flex items-center gap-1.5 px-3 py-1.5 rounded text-[11.5px] font-semibold bg-brand-teal text-ink-950 transition-colors'
                        : 'flex items-center gap-1.5 px-3 py-1.5 rounded text-[11.5px] text-ink-300 border border-ink-700 hover:border-ink-500 hover:text-ink-100 transition-colors'
                    }
                    title={`${INCIDENT_TYPE_KO[pt.incident_type] ?? pt.incident_type} — ${pt.gap_type}`}
                  >
                    <span
                      className={
                        active
                          ? 'inline-flex items-center justify-center w-4 h-4 rounded-full bg-ink-950/30 text-[10px] font-bold'
                          : 'inline-flex items-center justify-center w-4 h-4 rounded-full bg-ink-800 text-[10px] font-bold'
                      }
                    >
                      {i + 1}
                    </span>
                    {INCIDENT_TYPE_KO[pt.incident_type] ?? pt.incident_type}
                    <span className={`w-2 h-2 rounded-full ${GAP_DOT[pt.gap_type]}`} />
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* 결과 표시 — activeDetail = (multi 면) 선택 유형, (단일이면) 전체 결과 */}
        {result && activeDetail && meta && (
          <>
            <div className={`panel p-6 border-l-[4px] ${meta.bg} ${meta.color.replace('text-', 'border-l-')}`}>
              <div className="flex items-center gap-3 mb-2">
                <span className="text-[28px]">{meta.icon}</span>
                <div>
                  <div className="eyebrow">
                    판정 결과 — gap_type
                    {isMulti && activeTypeLabel && (
                      <span className="text-ink-300 normal-case">{' '}· {activeTypeLabel}</span>
                    )}
                  </div>
                  <div className={`text-[24px] font-extrabold ${meta.color}`}>
                    {activeDetail.gap_type} — {meta.label}
                  </div>
                </div>
              </div>
              <p className="text-[13px] text-ink-200 leading-7 mt-3">{activeDetail.summary}</p>
              <div className="mt-3 pt-3 border-t border-ink-700/40">
                <span className="eyebrow block mb-1">권장 행동</span>
                <p className="text-[12.5px] text-ink-100 font-medium">{activeDetail.recommendation}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <CompletenessKpi
                rate={activeDetail.completionRate}
                label={
                  activeDetail.completionRate === null
                    ? '필수 증거 미정의'
                    : activeDetail.completionRate === 100
                    ? '완전 수집'
                    : activeDetail.completionRate >= 60
                    ? '수집 갭 감지'
                    : '필수 증거 부족'
                }
              />

              <div className="lg:col-span-2">
                <Card
                  title={
                    <>
                       미수집 필수 증거 — {activeDetail.missing.length}건
                    </>
                  }
                  borderColor="#FF4D6D"
                >
                  {activeDetail.missing.length === 0 ? (
                    <p className="text-[13px] text-ink-300">필수 증거가 모두 확보되었습니다.</p>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {activeDetail.missing.map((m) => (
                        <div
                          key={m.target_id}
                          className="flex items-center justify-between gap-3 py-2 border-b border-ink-700/30 last:border-b-0"
                        >
                          <div className="flex-1 min-w-0">
                            <div className="font-mono text-[11.5px] text-ink-200">{m.target_id}</div>
                            <div className="text-[12.5px] text-ink-100 mt-0.5">{m.log_type}</div>
                          </div>
                          <div className="flex gap-1.5 shrink-0">
                            <Badge role={m.evidence_role} size="sm" />
                            <Badge tone="amber">P{m.priority}</Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              </div>
            </div>

            {/* v2 부가 진단 패널 — 4개 참고자료 반영 (논문/Google/SentinelOne/Naver) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* [R4] Naver Cloud — priority 가중 점수 */}
              {result.priorityScore && (
                <Card title={<>우선순위 가중 수집률</>}>
                  <div className="flex items-baseline gap-2 mb-2">
                    <span className="text-[28px] font-extrabold text-ink-100">
                      {result.priorityScore.percent}%
                    </span>
                    <span className="text-[11.5px] text-ink-400">
                      ({result.priorityScore.collected} / {result.priorityScore.total} 가중점)
                    </span>
                  </div>
                  <div className="text-[11.5px] text-ink-300 leading-6">
                    P1=10, P2=7, P3=3, P4=1 가중치 적용. 단순 건수가 아닌 <b>중요도</b> 기준.
                    {result.priorityScore.missing > 0 && (
                      <>
                        {' '}누락 가중점 <b className="text-brand-amber">{result.priorityScore.missing}</b>점.
                      </>
                    )}
                  </div>
                  <div className="mt-2 text-[10.5px] text-ink-500">
                    출처: Naver Cloud 보안관제 실무 우선순위 체계
                  </div>
                </Card>
              )}

              {/* [R1] 논문 — ATT&CK kill-chain 커버리지 */}
              {result.tacticCoverage && (
                <Card title={<>ATT&CK 단계 커버리지</>}>
                  <div className="flex items-baseline gap-2 mb-2">
                    <span className="text-[28px] font-extrabold text-ink-100">
                      {result.tacticCoverage.covered}
                    </span>
                    <span className="text-[13px] text-ink-400">
                      / {result.tacticCoverage.total} 단계
                    </span>
                  </div>
                  {Object.keys(result.tacticCoverage.byTactic).length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-2">
                      {Object.entries(result.tacticCoverage.byTactic).map(([t, n]) => (
                        <span
                          key={t}
                          className="chip text-[10.5px]"
                          title={`${n}건 매핑`}
                        >
                          {t} · {n}
                        </span>
                      ))}
                    </div>
                  )}
                  {result.tacticCoverage.missingTactics.length > 0 && (
                    <div className="text-[11px] text-ink-400 leading-6">
                      미커버:{' '}
                      <span className="text-ink-300">
                        {result.tacticCoverage.missingTactics.slice(0, 6).join(', ')}
                        {result.tacticCoverage.missingTactics.length > 6 && ' …'}
                      </span>
                    </div>
                  )}
                  <div className="mt-2 text-[10.5px] text-ink-500">
                    출처: ATT&CK 매트릭스 기반 이벤트 로그 분석 (한국정보보호학회)
                  </div>
                </Card>
              )}

              {/* [R3] SentinelOne — anti-forensic 시간 갭 */}
              {result.timeGaps && result.timeGaps.length > 0 && (
                <Card title={<>시간 축 비정상 공백 — {result.timeGaps.length}건</>} borderColor="#FF4D6D">
                  <div className="flex flex-col gap-1.5">
                    {result.timeGaps.slice(0, 5).map((g, i) => (
                      <div
                        key={i}
                        className="text-[11.5px] text-ink-200 font-mono leading-5"
                      >
                        <span className="text-brand-red">●</span>{' '}
                        {g.from.slice(11, 19)} → {g.to.slice(11, 19)}{' '}
                        <span className="text-ink-400">({g.durationMinutes}분 공백)</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-2 text-[10.5px] text-ink-500">
                    30분 이상 이벤트 공백 = 로그 삭제·변조 후보. 출처: SentinelOne 사이버 포렌식 (anti-forensics)
                  </div>
                </Card>
              )}

              {/* [R2] Google Cloud — bad log config 신호 */}
              {result.badConfigSignals && result.badConfigSignals.length > 0 && (
                <Card title={<>수집 구성 경고 — {result.badConfigSignals.length}건</>} borderColor="#FFB020">
                  <ul className="flex flex-col gap-1.5 list-disc list-inside text-[12px] text-ink-200 leading-6">
                    {result.badConfigSignals.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                  <div className="mt-2 text-[10.5px] text-ink-500">
                    출처: Google Cloud Threat Intel — Cloud Bad Log Configurations
                  </div>
                </Card>
              )}
            </div>
          </>
        )}
      </PageBody>
    </div>
  );
};

export default V4Gap;
