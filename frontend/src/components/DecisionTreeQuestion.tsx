/**
 * 결정 트리 단일 질문 컴포넌트 — V-1 Step 2 Discovery Loop 의 ③ 결정 트리.
 *
 * UX (2026-05-22 갱신):
 *   - 옵션 카드를 가능성(prospects)으로 노출. 각 옵션 아래에 "선택 시 다음 질문" 프리뷰.
 *   - 옵션을 선택하면 비채택 옵션이 페이드아웃 + 축소되고 선택 옵션이 강조됨.
 *   - "확정 →" 버튼으로 부모에게 답변 전달 → 부모는 next_node 로 이동.
 *   - multi_select 의 경우 다중 선택 가능 (페이드 동작은 미선택 옵션에만 적용).
 *
 * 학술 근거 표시: kisa_field 가 있으면 우측 상단 칩으로 출처 명시.
 */
import { useState } from 'react';

import Badge from '@/components/Badge';

import type { TriageTreeNode } from '@/types';
import type { TreeVisualizationNode } from '@/api/triage';

interface DecisionTreeQuestionProps {
  node: TriageTreeNode;
  /** 진행 단계 표시 (예: 2 / 3) — 옵션 */
  step?: number;
  totalEstimated?: number;
  /** 부모가 다음 노드로 진행. answer_ids 는 선택된 옵션 id 배열. */
  onSubmit: (answerIds: string[]) => void;
  /** 트리 시작점으로 되돌리기 (옵션) */
  onReset?: () => void;
  /** 로딩 표시 (백엔드 요청 중) */
  loading?: boolean;
  /**
   * 트리 전체 노드 라벨 맵 — `/api/triage/tree` 응답을 부모가 prefetch 해서 전달.
   * 옵션의 next 노드 id 로 다음 질문 라벨을 조회해 옵션 카드 하단에 프리뷰 표시.
   * 없으면 프리뷰 미표시 (안전한 fallback).
   */
  nodeLabelMap?: Record<string, TreeVisualizationNode>;
}

const DecisionTreeQuestion = ({
  node,
  step,
  totalEstimated,
  onSubmit,
  onReset,
  loading,
  nodeLabelMap,
}: DecisionTreeQuestionProps) => {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const multi = !!node.multi_select;

  const toggle = (id: string) => {
    if (multi) {
      setSelectedIds((prev) =>
        prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
      );
    } else {
      setSelectedIds((prev) => (prev[0] === id ? [] : [id]));
    }
  };

  const handleSubmit = () => {
    if (selectedIds.length === 0 || loading) return;
    onSubmit(selectedIds);
    setSelectedIds([]); // 다음 질문 위해 초기화
  };

  if (node.type === 'terminal') {
    return (
      <div className="panel p-4 border-l-[3px] border-l-brand-teal text-[12.5px]">
        <div className="eyebrow mb-2">🏁 트리 종료</div>
        <p className="text-ink-200 leading-6 whitespace-pre-line">
          {node.message ??
            '결정 트리가 종료되었습니다. 우측 가설 점수를 확인하세요.'}
        </p>
        {node.fallback_incident_type && (
          <p className="text-[11px] text-ink-400 mt-2">
            기본 사고유형: <code className="text-amber-300">{node.fallback_incident_type}</code>
          </p>
        )}
        {onReset && (
          <button onClick={onReset} className="btn-ghost btn-sm mt-3">
            ↻ 트리 처음부터
          </button>
        )}
      </div>
    );
  }

  const hasAnySelection = selectedIds.length > 0;

  return (
    <div>
      {/* 헤더 — 진행 단계 + KISA 출처 */}
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider">
          📋 결정 트리 질문
          {step && totalEstimated && (
            <span className="ml-2 text-ink-500">
              {step} / {totalEstimated}
            </span>
          )}
        </div>
        {node.kisa_field && (
          <Badge tone="red" size="sm">
            {node.kisa_field}
          </Badge>
        )}
      </div>

      {/* 질문 */}
      <div className="text-[14px] text-ink-100 font-semibold mb-3 leading-7">
        Q. {node.question}
        {multi && (
          <span className="ml-2 text-[10.5px] text-amber-300 font-normal">
            (다중 선택 가능)
          </span>
        )}
      </div>

      {/* 옵션 — 가능성 리스트 (비채택은 페이드, 선택은 강조 + next 프리뷰 확장) */}
      <div className="space-y-1.5">
        {(node.options ?? []).map((opt) => {
          const selected = selectedIds.includes(opt.id);
          const dimmed = hasAnySelection && !selected;
          const nextNode = opt.next && nodeLabelMap ? nodeLabelMap[opt.next] : undefined;
          const nextLabel = nextNode?.label;
          const nextIsTerminal = nextNode?.type === 'terminal';

          return (
            <button
              key={opt.id}
              onClick={() => toggle(opt.id)}
              disabled={loading}
              className={`w-full text-left rounded-xl px-3.5 py-2.5 border flex flex-col gap-1.5 transition-all duration-300 ${
                selected
                  ? 'border-brand-teal/80 bg-brand-teal/10 text-ink-100 shadow-[0_0_0_1px_rgba(45,212,191,0.5)]'
                  : dimmed
                  ? 'border-ink-800/60 bg-ink-900/30 text-ink-500 opacity-50 scale-[0.98]'
                  : 'border-ink-700/70 bg-ink-900/60 text-ink-200 hover:border-brand-blue/40 hover:bg-ink-900'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <div className="flex items-center gap-2.5">
                <span
                  className={`flex-shrink-0 w-4 h-4 ${
                    multi ? 'rounded' : 'rounded-full'
                  } border-2 flex items-center justify-center text-[10px] transition-colors ${
                    selected
                      ? 'bg-brand-teal/80 border-brand-teal text-white'
                      : 'border-ink-600'
                  }`}
                >
                  {selected && (multi ? '✓' : '●')}
                </span>
                <span className="text-[12.5px] leading-5 flex-1">{opt.label}</span>
              </div>

              {/* "선택 시 다음 질문" 프리뷰 — 선택 안 한 상태에서만 가능성으로 표시
                  선택된 옵션은 더 진한 색으로 "확정 시 진입" 안내 */}
              {nextLabel && (
                <div
                  className={`ml-6 flex items-start gap-1.5 text-[10.5px] leading-4 transition-opacity duration-300 ${
                    selected
                      ? 'text-brand-teal/90 font-medium'
                      : dimmed
                      ? 'text-ink-600 opacity-50'
                      : 'text-ink-500'
                  }`}
                >
                  <span aria-hidden className="select-none">↳</span>
                  <span className="flex-1">
                    {nextIsTerminal ? (
                      <>
                        <span className="text-amber-300/80">🏁 종료</span>
                        <span className="ml-1 opacity-70">— {nextLabel}</span>
                      </>
                    ) : (
                      <>
                        다음 질문: <span className="font-medium">{nextLabel}</span>
                      </>
                    )}
                  </span>
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* 안내 + 확정 버튼 */}
      <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
        <span className="text-[10.5px] text-ink-500">
          {hasAnySelection
            ? multi
              ? `${selectedIds.length}개 선택 — 다른 가능성은 회색 처리됨`
              : '선택됨 — 확정하면 다음 질문으로 이동합니다'
            : multi
            ? '가능성 항목 중 최소 1개 이상 선택'
            : '가능성 항목 중 하나를 선택하세요'}
        </span>
        <button
          onClick={handleSubmit}
          disabled={!hasAnySelection || loading}
          className="btn-primary btn-sm disabled:opacity-40"
        >
          {loading ? '진행 중…' : '확정 →'}
        </button>
      </div>
    </div>
  );
};

export default DecisionTreeQuestion;
