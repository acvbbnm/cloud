/**
 * 결정 트리 단일 질문 — 세로 트리형 가능성 리스트 + 확정 시 잔여 옵션 소거.
 *
 * 동작:
 *   1. 모든 옵션을 트리 가지(├─ └─)로 노출 — "가능성 항목"
 *   2. 사용자가 옵션 클릭 → 미선택 옵션 흐려짐 (preview)
 *   3. "확정 → 다음" 클릭 → 미선택 옵션 fade-out → parent.onSubmit
 *
 * single_select / multi_select 자동 분기. 학술 근거 표시: kisa_field 칩.
 */
import { useState } from 'react';

import Badge from '@/components/Badge';

import type { TriageTreeNode } from '@/types';

interface DecisionTreeQuestionProps {
  node: TriageTreeNode;
  step?: number;
  totalEstimated?: number;
  onSubmit: (answerIds: string[]) => void;
  onReset?: () => void;
  loading?: boolean;
}

const FADE_MS = 280;

const DecisionTreeQuestion = ({
  node,
  step,
  totalEstimated,
  onSubmit,
  onReset,
  loading,
}: DecisionTreeQuestionProps) => {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [confirming, setConfirming] = useState(false);
  const multi = !!node.multi_select;

  const toggle = (id: string) => {
    if (confirming || loading) return;
    if (multi) {
      setSelectedIds((prev) =>
        prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
      );
    } else {
      setSelectedIds([id]);
    }
  };

  const handleConfirm = () => {
    if (selectedIds.length === 0 || loading || confirming) return;
    setConfirming(true);
    window.setTimeout(() => {
      onSubmit(selectedIds);
      setSelectedIds([]);
      setConfirming(false);
    }, FADE_MS);
  };

  if (node.type === 'terminal') {
    return (
      <div className="panel p-4 border-l-[3px] border-l-brand-teal text-[12.5px]">
        <div className="eyebrow mb-2">트리 종료</div>
        <p className="text-ink-200 leading-6 whitespace-pre-line">
          {node.message ?? '결정 트리가 종료되었습니다. 우측 가설 점수를 확인하세요.'}
        </p>
        {node.fallback_incident_type && (
          <p className="text-[11px] text-ink-400 mt-2">
            기본 사고유형:{' '}
            <code className="text-brand-amber font-mono">{node.fallback_incident_type}</code>
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

  const options = node.options ?? [];
  const lastIdx = options.length - 1;

  return (
    <div className="font-mono">
      {/* 헤더 — 진행 단계 + KISA 출처 */}
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider">
          결정 트리 질문
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
      <div className="text-[13.5px] text-ink-100 font-semibold mb-2 leading-6">
        Q. {node.question}
        {multi && (
          <span className="ml-2 text-[10.5px] text-brand-amber font-normal">
            (다중 선택 가능)
          </span>
        )}
      </div>

      {/* 옵션 — 세로 트리 가지 (├─ └─)
          다중 선택(multi) 시 미선택 옵션을 흐리지 않음 → 추가 선택 가능 시각화.
          단일 선택일 때만 흐림 처리 (다른 옵션 클릭 = 교체 신호). */}
      <div className="text-[12.5px] leading-5">
        {options.map((opt, i) => {
          const selected = selectedIds.includes(opt.id);
          const dimmed =
            !multi && selectedIds.length > 0 && !selected && !confirming;
          const hidden = confirming && !selected;
          const isLast = i === lastIdx;
          return (
            <div
              key={opt.id}
              style={{ transitionDuration: `${FADE_MS}ms` }}
              className={`flex items-start transition-all ease-out ${
                hidden
                  ? 'opacity-0 max-h-0 my-0 overflow-hidden'
                  : dimmed
                  ? 'opacity-40'
                  : 'opacity-100'
              }`}
            >
              <span className="select-none shrink-0 w-7 text-ink-500 text-[12px] leading-8 text-center">
                {isLast ? '└─' : '├─'}
              </span>
              <button
                onClick={() => toggle(opt.id)}
                disabled={loading || confirming}
                className={`flex-1 text-left px-2.5 py-1.5 border my-0.5 transition-colors flex items-start gap-2 ${
                  selected
                    ? 'border-brand-amber bg-brand-amber/10 text-ink-50'
                    : 'border-ink-700 bg-ink-900 text-ink-200 hover:border-brand-amber/50 hover:text-ink-100'
                } disabled:cursor-not-allowed`}
              >
                {/* 다중=네모 체크박스 / 단일=원형 라디오 — 클릭 가능 신호 명확히 */}
                <span
                  className={`shrink-0 mt-0.5 w-3.5 h-3.5 border flex items-center justify-center text-[9px] ${
                    multi ? '' : 'rounded-full'
                  } ${
                    selected
                      ? 'bg-brand-amber border-brand-amber text-ink-975'
                      : 'border-ink-600'
                  }`}
                >
                  {selected ? '✓' : ''}
                </span>
                <span className="flex-1 leading-5 whitespace-normal break-words">{opt.label}</span>
              </button>
            </div>
          );
        })}
      </div>

      {/* 확정 액션 */}
      <div className="flex items-center justify-between mt-2.5 flex-wrap gap-2">
        <span className="text-[10.5px] text-ink-500">
          {selectedIds.length > 0
            ? multi
              ? `${selectedIds.length}개 선택 — 다른 항목을 더 클릭해 추가하거나 확정`
              : `${selectedIds.length}개 선택 — 확정 시 다른 가능성 항목 제거`
            : multi
            ? '여러 항목을 클릭해 모두 선택 가능'
            : '가능성 항목 중 하나를 선택해주세요'}
        </span>
        <button
          onClick={handleConfirm}
          disabled={selectedIds.length === 0 || loading || confirming}
          className="btn-primary btn-sm disabled:opacity-40"
        >
          {loading ? '진행 중…' : confirming ? '확정 중…' : '확정 → 다음'}
        </button>
      </div>
    </div>
  );
};

export default DecisionTreeQuestion;
