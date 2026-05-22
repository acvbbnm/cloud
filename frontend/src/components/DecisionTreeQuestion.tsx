/**
 * 결정 트리 단일 질문 컴포넌트 — V-1 Step 2 Discovery Loop 의  결정 트리.
 *
 * single_select / multi_select 자동 분기. 선택 후 [다음 →] 클릭으로 부모에게
 * 답변 ID 배열 전달. multi_select 의 경우 최소 1개 선택 강제.
 *
 * 학술 근거 표시: kisa_field 가 있으면 우측 상단 칩으로 출처 명시.
 */
import { useState } from 'react';

import Badge from '@/components/Badge';

import type { TriageTreeNode } from '@/types';

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
}

const DecisionTreeQuestion = ({
  node,
  step,
  totalEstimated,
  onSubmit,
  onReset,
  loading,
}: DecisionTreeQuestionProps) => {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const multi = !!node.multi_select;

  const toggle = (id: string) => {
    if (multi) {
      setSelectedIds((prev) =>
        prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
      );
    } else {
      setSelectedIds([id]);
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
        <div className="eyebrow mb-2"> 트리 종료</div>
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

  return (
    <div>
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
      <div className="text-[14px] text-ink-100 font-semibold mb-3 leading-7">
        Q. {node.question}
        {multi && (
          <span className="ml-2 text-[10.5px] text-amber-300 font-normal">
            (다중 선택 가능)
          </span>
        )}
      </div>

      {/* 옵션 */}
      <div className="space-y-1.5">
        {(node.options ?? []).map((opt) => {
          const selected = selectedIds.includes(opt.id);
          return (
            <button
              key={opt.id}
              onClick={() => toggle(opt.id)}
              disabled={loading}
              className={`w-full text-left rounded-xl px-3.5 py-2.5 border transition-all flex items-center gap-2.5 ${
                selected
                  ? 'border-brand-teal/70 bg-brand-teal/10 text-ink-100'
                  : 'border-ink-700/70 bg-ink-900/60 text-ink-200 hover:border-brand-blue/40 hover:bg-ink-900'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <span
                className={`flex-shrink-0 w-4 h-4 ${
                  multi ? 'rounded' : 'rounded-full'
                } border-2 flex items-center justify-center text-[10px] ${
                  selected
                    ? 'bg-brand-teal/80 border-brand-teal text-white'
                    : 'border-ink-600'
                }`}
              >
                {selected && (multi ? '' : '')}
              </span>
              <span className="text-[12.5px] leading-5 flex-1">{opt.label}</span>
            </button>
          );
        })}
      </div>

      {/* 다음 버튼 + 가중치 미리보기 (선택된 옵션 수) */}
      <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
        <span className="text-[10.5px] text-ink-500">
          {selectedIds.length > 0
            ? `${selectedIds.length}개 선택됨 — 점수 가중치는 우측에 즉시 반영됩니다`
            : multi
            ? '최소 1개 이상 선택해주세요'
            : '옵션을 선택해주세요'}
        </span>
        <button
          onClick={handleSubmit}
          disabled={selectedIds.length === 0 || loading}
          className="btn-primary btn-sm disabled:opacity-40"
        >
          {loading ? '진행 중…' : '다음 →'}
        </button>
      </div>
    </div>
  );
};

export default DecisionTreeQuestion;
