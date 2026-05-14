import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import Card from '@/components/Card';
import Badge from '@/components/Badge';
import { useToastStore } from '@/stores/useToastStore';
import { useCaseStore } from '@/stores/useCaseStore';
import { useBoardStore } from '@/stores/useBoardStore';
import type { BoardLog } from '@/stores/useBoardStore';
import { getBoard, createNode, updateNode } from '@/api/board';
import { getAttack } from '@/api/analysis';
import type { AttackEventItem, BoardNode } from '@/types';

import LogPanel from './LogPanel';
import BoardCanvas from './BoardCanvas';

const ATTACK_PAGE_SIZE = 10;

const V5Board = () => {
  const navigate = useNavigate();
  const showToast = useToastStore((s) => s.show);
  const caseId = useCaseStore((s) => s.caseId);
  const cards = useBoardStore((s) => s.cards);
  const queryClient = useQueryClient();

  const [pendingLog, setPendingLog] = useState<BoardLog | null>(null);
  const [activeAttack, setActiveAttack] = useState<AttackEventItem | null>(null);
  const [activeBoardNode, setActiveBoardNode] = useState<BoardNode | null>(null);
  const [memo, setMemo] = useState('');

  const boardQuery = useQuery({
    queryKey: ['board', caseId],
    queryFn: () => getBoard(caseId!),
    enabled: !!caseId,
  });

  const attackQuery = useQuery({
    queryKey: ['attack', caseId, 1],
    queryFn: () => getAttack(caseId!, 1, ATTACK_PAGE_SIZE),
    enabled: !!caseId,
  });

  const addNodeMutation = useMutation({
    mutationFn: (att: AttackEventItem) =>
      createNode({
        caseId: caseId!,
        attack_id: att.attack_id,
        is_ai_suggested: false, // 수사관이 명시적으로 추가
      }),
    onSuccess: (node) => {
      showToast(`노드 추가: ${node.label}`);
      queryClient.invalidateQueries({ queryKey: ['board', caseId] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`노드 추가 실패: ${msg}`);
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ nodeId, status }: { nodeId: string; status: 'CONFIRMED' | 'REJECTED' }) =>
      updateNode(nodeId, { status }),
    onSuccess: (node) => {
      showToast(`${node.status === 'CONFIRMED' ? '수락' : '거부'}: ${node.label}`);
      queryClient.invalidateQueries({ queryKey: ['board', caseId] });
      setActiveBoardNode(node);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`상태 변경 실패: ${msg}`);
    },
  });

  if (!caseId) {
    return (
      <div>
        <PageHeader
          eyebrow="Layer 4 · M4-1"
          title="수사 보드"
          description="진행 중인 사고 케이스가 없습니다."
        />
        <PageBody>
          <Card title={<>⚠️ 케이스 없음</>}>
            <p className="text-[13px] text-ink-300 mb-3">
              V-1 사고 접수 위저드를 먼저 완료해야 수사 보드를 사용할 수 있습니다.
            </p>
            <button onClick={() => navigate('/setup')} className="btn-primary">
              ← V-1 사고 접수로 돌아가기
            </button>
          </Card>
        </PageBody>
      </div>
    );
  }

  const boardNodes = boardQuery.data?.nodes ?? [];
  const boardEdges = boardQuery.data?.edges ?? [];
  const attackItems = attackQuery.data?.items ?? [];
  // 이미 보드에 추가된 attack_id 집합 (중복 추가 방지 UI)
  const addedAttackIds = new Set(boardNodes.map((n) => n.attack_id).filter(Boolean));

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        eyebrow="Layer 4 · M4-1"
        title="수사 보드"
        description="ATT&CK 매핑 결과를 후보로 보고, 보드 노드로 추가하여 공격 체인을 재구성합니다."
        actions={
          <>
            <button onClick={() => navigate('/gap')} className="btn-ghost">
              ← 갭 감지
            </button>
            <button
              onClick={() => {
                showToast('→ ATT&CK 매핑 진행');
                navigate('/attack');
              }}
              className="btn-primary"
            >
              ATT&CK 매핑 →
            </button>
          </>
        }
      />

      <div className="max-w-[1280px] mx-auto w-full px-8 lg:px-12 py-6 flex gap-4 flex-1 overflow-hidden min-h-0 animate-fade-up flex-col">
        {/* 백엔드 통신 상태 패널 */}
        <div className="panel p-4 border-l-[3px] border-l-brand-teal text-[12px]">
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="eyebrow">백엔드 응답</span>
              {boardQuery.isLoading && <span className="tag-blue">board 로딩…</span>}
              {boardQuery.isError && <span className="tag-red">board 에러</span>}
              {boardQuery.isSuccess && <span className="tag-teal">board ✓</span>}
              {attackQuery.isLoading && <span className="tag-blue">attack 로딩…</span>}
              {attackQuery.isError && <span className="tag-red">attack 에러</span>}
              {attackQuery.isSuccess && <span className="tag-teal">attack ✓</span>}
              {addNodeMutation.isPending && <span className="tag-amber">노드 추가 중…</span>}
              {updateStatusMutation.isPending && (
                <span className="tag-amber">상태 변경 중…</span>
              )}
            </div>
            <code className="text-ink-400 font-mono text-[10.5px]">caseId: {caseId}</code>
          </div>
          <div className="text-ink-300 leading-6">
            chain_nodes <b className="text-ink-100">{boardNodes.length}</b>건 · edges{' '}
            <b className="text-ink-100">{boardEdges.length}</b>건 · ATT&CK 후보{' '}
            <b className="text-ink-100">{attackQuery.data?.total ?? 0}</b>건
          </div>
          {boardQuery.isError && (
            <div className="text-brand-red text-[11.5px] mt-1">
              {(boardQuery.error as Error)?.message ?? 'board 호출 실패'}
            </div>
          )}
        </div>

        <div className="flex gap-4 flex-1 overflow-hidden min-h-0">
          <div className="flex-1 min-w-0 flex flex-col gap-3">
            <BoardCanvas pendingLog={pendingLog} clearPendingLog={() => setPendingLog(null)} />

            {/* 보드 노드 (실 백엔드 데이터) */}
            <Card title={<>🎯 공격 체인 노드 (chain_nodes)</>} className="flex-shrink-0">
              {boardNodes.length === 0 ? (
                <div className="text-[12px] text-ink-400 py-2">
                  보드에 추가된 노드가 없습니다. 아래 ATT&CK 후보에서 "보드 추가" 를 눌러 노드를 생성하세요.
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {boardNodes.map((n) => {
                    const sel = activeBoardNode?.node_id === n.node_id;
                    const rejected = n.status === 'REJECTED';
                    return (
                      <button
                        key={n.node_id}
                        onClick={() => {
                          setActiveBoardNode(n);
                          setActiveAttack(null);
                        }}
                        className={`bg-ink-900/60 border rounded-xl px-3 py-2 text-[12px] flex flex-col gap-0.5 transition-all hover:border-brand-blue/50 ${
                          sel ? 'border-brand-blue/60 ring-1 ring-brand-blue/40 shadow-glow' : 'border-ink-700/70'
                        } ${rejected ? 'opacity-50 line-through' : ''}`}
                      >
                        <span className="font-semibold truncate max-w-[180px]">{n.label}</span>
                        <span className="text-ink-400 text-[10.5px]">
                          {n.is_ai_suggested ? '🧠 AI · ' : '👤 수동 · '}
                          <span
                            className={
                              n.status === 'CONFIRMED' ? 'text-brand-teal' : 'text-brand-red'
                            }
                          >
                            {n.status}
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
              {cards.length > 0 && (
                <p className="mt-3 text-[11.5px] text-ink-500">
                  캔버스에 클라이언트 로그 카드 {cards.length}개 (백엔드 미연동, 시각화용)
                </p>
              )}
            </Card>

            {/* ATT&CK 매핑 결과 후보 */}
            <Card
              title={<>🤖 ATT&CK 매핑 후보 (top {ATTACK_PAGE_SIZE})</>}
              subtitle="risk_score 내림차순. 카드 클릭 시 우측 상세 표시 + '보드 추가'"
              className="flex-shrink-0"
            >
              {attackItems.length === 0 ? (
                <div className="text-[12px] text-ink-400 py-2">
                  ATT&CK 매핑 결과가 없습니다. V-2 → V-3 정규화 → ATT&CK 매핑 (POST /api/analysis/map) 을
                  먼저 수행하세요.
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  {attackItems.map((att) => {
                    const sel = activeAttack?.attack_id === att.attack_id;
                    const added = addedAttackIds.has(att.attack_id);
                    return (
                      <button
                        key={att.attack_id}
                        onClick={() => {
                          setActiveAttack(att);
                          setActiveBoardNode(null);
                        }}
                        className={`text-left bg-ink-900/60 border rounded-xl px-3 py-2 text-[12px] flex flex-col gap-0.5 transition-all hover:border-brand-purple/50 ${
                          sel
                            ? 'border-brand-purple/60 ring-1 ring-brand-purple/40'
                            : 'border-ink-700/70'
                        } ${added ? 'opacity-60' : ''}`}
                      >
                        <span className="font-semibold truncate">{att.activity_name ?? '—'}</span>
                        <span className="text-ink-400 text-[10.5px]">
                          <span className="text-brand-purple">{att.technique_id}</span>
                          {att.tactic && <> · {att.tactic}</>}
                          {att.risk_score !== null && (
                            <> · risk <b className="text-brand-amber">{att.risk_score}</b></>
                          )}
                          {added && <> · <span className="text-brand-teal">보드에 있음</span></>}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </Card>
          </div>

          {/* 우측 컬럼 */}
          <div className="w-[300px] shrink-0 flex flex-col gap-3 overflow-y-auto pr-1">
            <Card title={<>ℹ️ 상세</>}>
              {activeBoardNode ? (
                <div className="text-[12.5px]">
                  <div className="font-bold text-[14px] mb-2 truncate">{activeBoardNode.label}</div>
                  <Row label="상태">
                    <Badge tone={activeBoardNode.status === 'CONFIRMED' ? 'teal' : 'red'}>
                      {activeBoardNode.status}
                    </Badge>
                  </Row>
                  <Row label="유형">
                    {activeBoardNode.is_ai_suggested ? '🧠 AI 제안' : '👤 수동 추가'}
                  </Row>
                  <Row label="attack_id">
                    <span className="font-mono text-[10.5px] text-ink-400">
                      {activeBoardNode.attack_id?.slice(0, 8) ?? '—'}
                    </span>
                  </Row>
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() =>
                        updateStatusMutation.mutate({
                          nodeId: activeBoardNode.node_id,
                          status: 'CONFIRMED',
                        })
                      }
                      disabled={
                        updateStatusMutation.isPending ||
                        activeBoardNode.status === 'CONFIRMED'
                      }
                      className="btn-primary btn-sm flex-1 disabled:opacity-40"
                    >
                      ✓ 수락
                    </button>
                    <button
                      onClick={() =>
                        updateStatusMutation.mutate({
                          nodeId: activeBoardNode.node_id,
                          status: 'REJECTED',
                        })
                      }
                      disabled={
                        updateStatusMutation.isPending ||
                        activeBoardNode.status === 'REJECTED'
                      }
                      className="btn-danger btn-sm flex-1 disabled:opacity-40"
                    >
                      ✗ 거부
                    </button>
                  </div>
                </div>
              ) : activeAttack ? (
                <div className="text-[12.5px]">
                  <div className="font-bold text-[14px] mb-2 truncate">
                    {activeAttack.activity_name ?? '—'}
                  </div>
                  <Row label="기법">
                    <Badge tone="purple">{activeAttack.technique_id}</Badge>
                  </Row>
                  <Row label="기법명">{activeAttack.technique_name ?? '—'}</Row>
                  <Row label="전술">{activeAttack.tactic}</Row>
                  <Row label="risk_score">
                    <b className="text-brand-amber">{activeAttack.risk_score ?? '—'}</b>
                  </Row>
                  <Row label="시각">
                    <span className="font-mono text-[10.5px]">
                      {activeAttack.event_time?.slice(0, 19) ?? '—'}
                    </span>
                  </Row>
                  <button
                    onClick={() => addNodeMutation.mutate(activeAttack)}
                    disabled={
                      addNodeMutation.isPending || addedAttackIds.has(activeAttack.attack_id)
                    }
                    className="btn-primary btn-sm w-full mt-3 disabled:opacity-40"
                  >
                    {addedAttackIds.has(activeAttack.attack_id)
                      ? '이미 보드에 있음'
                      : '+ 보드에 추가'}
                  </button>
                </div>
              ) : (
                <div className="text-[12px] text-ink-400">
                  공격 체인 노드 또는 ATT&CK 후보를 클릭하세요
                </div>
              )}
            </Card>

            <Card title={<span className="text-brand-purple">🧠 AI 셰르파 브리핑</span>}>
              <div className="bg-ink-950 border border-ink-700/70 rounded-xl p-3 text-[12px] leading-7 text-ink-200">
                <b className="text-ink-400">[Layer 3 미구현 — mock 표시 중]</b>
                <p className="mt-1">
                  AI 셰르파 백엔드(Ollama + RAG) 통합 시 attack_events 컨텍스트 기반 브리핑이
                  여기 표시됩니다.
                </p>
                <p className="mt-2 text-[10.5px] text-ink-500">
                  POST /api/sherpa/brief (예정)
                </p>
              </div>
            </Card>

            <Card title={<>📝 수사관 메모</>}>
              <textarea
                value={memo}
                onChange={(e) => setMemo(e.target.value)}
                placeholder="메모 입력... (현재는 클라이언트 상태)"
                rows={3}
                className="input resize-y min-h-[72px]"
              />
            </Card>

            <LogPanel onDragStart={setPendingLog} />
          </div>
        </div>
      </div>
    </div>
  );
};

const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div className="flex justify-between items-center py-1.5 border-b border-ink-700/30">
    <span className="text-ink-400">{label}</span>
    <span>{children}</span>
  </div>
);

export default V5Board;
