/**
 * Phase O.4 — Evidence Tree → V-5 보드 일괄 bridge 카드 (2026-05-26, byungwoo).
 *
 * paradigm doc §24 Phase O — Evidence Board 통합.
 *
 * 사용자 비전 (2026-05-26):
 *   "단서들이 수사보드에 연동되어서 수사보드에서 단서들을 조합해보면서
 *    타임라인을 직접 예측하며 어택 체인을 재구성"
 *
 * 동작:
 *   - V-1 Step 3 우측 sticky 영역에 노출 (path 채택 단서 ≥1 시)
 *   - 클릭 → POST /api/board/nodes/from-clue-tree
 *   - include_edges 토글 — 시간순 엣지 자동 생성 (기본 OFF)
 *   - 성공 시 결과 토스트 (생성 N · 이미 등록 M)
 *   - 자동 이동 X — 사용자가 V-5 로 직접 이동 (paradigm §16 정합)
 */
import { useState } from 'react';

import Card from '@/components/Card';

import { bridgeFromClueTree } from '@/api/board';

interface BridgeToBoardCardProps {
  caseId: string | null;
  /** 현재 path 의 채택 단서 수 (root 제외). 0 이면 카드 자체 미노출. */
  acceptedClueCount: number;
  /** 토스트 알림 핸들러 — Step3 부모가 useToastStore 와 연결. */
  onToast: (msg: string, ms?: number) => void;
}

const BridgeToBoardCard = ({
  caseId,
  acceptedClueCount,
  onToast,
}: BridgeToBoardCardProps) => {
  const [includeEdges, setIncludeEdges] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (acceptedClueCount === 0) return null;

  const handleBridge = async () => {
    if (!caseId || submitting) return;
    setSubmitting(true);
    try {
      const result = await bridgeFromClueTree({
        caseId,
        source: 'manual_bulk',
        include_edges: includeEdges,
      });
      const created = result.created_nodes.length;
      const skipped = result.skipped.length;
      const edges = result.created_edges.length;

      if (created === 0 && skipped > 0) {
        onToast(
          `이미 모든 단서가 보드에 있습니다 (skip ${skipped}건). V-5 보드로 이동해 조합해보세요.`,
          4500,
        );
      } else {
        const parts = [`보드에 단서 노드 ${created}개 생성`];
        if (edges > 0) parts.push(`시간순 엣지 ${edges}개`);
        if (skipped > 0) parts.push(`중복 skip ${skipped}건`);
        onToast(`${parts.join(' · ')}. V-5 보드로 이동해 조합해보세요.`, 4500);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      onToast(`보드 이관 실패: ${msg}`, 5000);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card
      title="단서들을 수사 보드로"
      subtitle={`현재 path 의 ${acceptedClueCount}개 단서를 V-5 보드 노드로 이관합니다`}
      borderColor="#2DD4BF"
    >
      <div className="space-y-2.5">
        <div className="text-[11px] text-ink-300 leading-relaxed">
          보드 위에서 단서들을 자유롭게 조합하며{' '}
          <span className="text-brand-teal font-semibold">타임라인·어택 체인</span> 을
          직접 예측하세요. 이미 보드에 있는 단서는 중복 추가되지 않습니다 (멱등).
        </div>

        <label className="flex items-center gap-2 text-[11px] text-ink-200 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={includeEdges}
            onChange={(e) => setIncludeEdges(e.target.checked)}
            className="accent-brand-teal"
          />
          <span>
            시간순 엣지도 자동 생성 (단서 채택 순서대로 →)
            <span className="text-ink-400">
              {' '}
              — 끄면 보드에서 직접 연결
            </span>
          </span>
        </label>

        <button
          type="button"
          onClick={handleBridge}
          disabled={submitting || !caseId}
          className="w-full text-[11.5px] font-semibold bg-brand-teal hover:bg-brand-tealDark text-ink-950 px-3 py-1.5 rounded transition-colors disabled:opacity-40"
          title="POST /api/board/nodes/from-clue-tree — paradigm §24 Phase O"
        >
          {submitting
            ? '이관 중…'
            : `${acceptedClueCount}개 단서 → 수사 보드로 보내기`}
        </button>
      </div>
    </Card>
  );
};

export default BridgeToBoardCard;
