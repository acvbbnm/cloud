import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import Card from '@/components/Card';
import Badge from '@/components/Badge';
import DwellTimeKpi from '@/components/DwellTimeKpi';
import { useToastStore } from '@/stores/useToastStore';
import { useCaseStore } from '@/stores/useCaseStore';
import { useBoardStore } from '@/stores/useBoardStore';
import type { BoardLog } from '@/stores/useBoardStore';
import { getBoard, createNode, updateNode, createEdge } from '@/api/board';
import { getAttack } from '@/api/analysis';
import { postBrief } from '@/api/sherpa';
import type { AttackEventItem, BoardNode, BriefingResponse, SherpaSource } from '@/types';

import LogPanel from './LogPanel';
import BoardCanvas from './BoardCanvas';
import ChainGraphCanvas from './ChainGraphCanvas';

const SOURCE_TONE: Record<string, 'red' | 'amber' | 'teal' | 'blue' | 'purple' | 'gray'> = {
  ATTACK: 'purple',
  PLAYBOOK: 'teal',
  CSP_DOC: 'blue',
  CASE_DB: 'amber',
};

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

  // UF-04 — 엣지 생성 모드 (chain_nodes 간 화살표 연결)
  const [edgeMode, setEdgeMode] = useState(false);
  const [edgeStartId, setEdgeStartId] = useState<string | null>(null);

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

  // AI 셰르파 brief — 선택된 board 노드(attack_id 가 있는 경우) 또는
  // 선택된 ATT&CK 후보 기준. 둘 다 없으면 케이스의 최상위 위험도 attack 자동 선택
  // (백엔드가 처리). KB 검색 결과는 5분 캐싱.
  const briefAttackId =
    activeBoardNode?.attack_id ?? activeAttack?.attack_id ?? null;
  const briefQuery = useQuery({
    queryKey: ['sherpa', 'brief', caseId, briefAttackId],
    queryFn: () =>
      postBrief({
        caseId: caseId!,
        eventId: briefAttackId,
      }),
    enabled: !!caseId,
    staleTime: 5 * 60 * 1000,
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

  // Phase P.6 (2026-05-26) — LogPanel 단서 탭에서 ChainGraph 로 드래그된 단서 처리.
  // POST /api/board/nodes {clue_key, pos_x, pos_y, source: 'manual_drag'}
  // 멱등: 보드에 같은 clue_key 노드가 이미 있으면 백엔드 호출 전 차단 (토스트 안내).
  const addClueNodeMutation = useMutation({
    mutationFn: (vars: {
      clue_key: string;
      label: string;
      pos_x: number;
      pos_y: number;
    }) =>
      createNode({
        caseId: caseId!,
        clue_key: vars.clue_key,
        label: vars.label,
        pos_x: vars.pos_x,
        pos_y: vars.pos_y,
        source: 'manual_drag',
        is_ai_suggested: false,
      }),
    onSuccess: (node) => {
      showToast(`🔍 단서 노드 추가 — ${node.label}`);
      queryClient.invalidateQueries({ queryKey: ['board', caseId] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`단서 노드 추가 실패: ${msg}`);
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

  // Phase 2.2 — 노드 드래그 위치 영속화
  const movePositionMutation = useMutation({
    mutationFn: ({ nodeId, x, y }: { nodeId: string; x: number; y: number }) =>
      updateNode(nodeId, { pos_x: x, pos_y: y }),
    onSuccess: () => {
      // 최신 위치를 받기 위해 보드 invalidate (조용히 — 토스트 안 띄움)
      queryClient.invalidateQueries({ queryKey: ['board', caseId] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`노드 위치 저장 실패: ${msg}`);
    },
  });

  // UF-04 — 엣지 생성 (chain_edges)
  const createEdgeMutation = useMutation({
    mutationFn: ({ fromId, toId }: { fromId: string; toId: string }) =>
      createEdge({
        caseId: caseId!,
        from_node_id: fromId,
        to_node_id: toId,
      }),
    onSuccess: () => {
      showToast('엣지 생성 — 공격 체인 연결');
      queryClient.invalidateQueries({ queryKey: ['board', caseId] });
      setEdgeStartId(null);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`엣지 생성 실패: ${msg}`);
      setEdgeStartId(null);
    },
  });

  const toggleEdgeMode = () => {
    setEdgeMode((m) => !m);
    setEdgeStartId(null);
  };

  const handleGraphNodeSelect = (n: BoardNode) => {
    // 엣지 모드 + 시작점 미선택 → 이번 클릭을 시작점으로
    if (edgeMode && edgeStartId === null) {
      setEdgeStartId(n.node_id);
      showToast(`엣지 시작점: ${n.label}. 두 번째 노드를 클릭하세요.`);
      return;
    }
    // 일반 모드 — 우측 상세 패널 갱신
    setActiveBoardNode(n);
    setActiveAttack(null);
  };

  if (!caseId) {
    return (
      <div>
        <PageHeader
          eyebrow="Layer 4 · M4-1"
          title="수사 보드"
          description="활성화된 사고 케이스가 없습니다."
        />
        <PageBody>
          <Card title={<>사고 케이스 없음</>}>
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
    <div className="flex flex-col h-full overflow-y-auto">
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

      <div className="max-w-[1280px] mx-auto w-full px-8 lg:px-12 py-6 flex gap-4 animate-fade-up flex-col">
        {/* 백엔드 통신 상태 패널 */}
        <div className="panel p-4 border-l-[3px] border-l-brand-teal text-[12px]">
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="eyebrow">백엔드 응답</span>
              {boardQuery.isLoading && <span className="tag-blue">board 로딩…</span>}
              {boardQuery.isError && <span className="tag-red">board 에러</span>}
              {boardQuery.isSuccess && <span className="tag-teal">board </span>}
              {attackQuery.isLoading && <span className="tag-blue">attack 로딩…</span>}
              {attackQuery.isError && <span className="tag-red">attack 에러</span>}
              {attackQuery.isSuccess && <span className="tag-teal">attack </span>}
              {addNodeMutation.isPending && <span className="tag-amber">노드 추가 중…</span>}
              {updateStatusMutation.isPending && (
                <span className="tag-amber">상태 변경 중…</span>
              )}
              {briefQuery.isLoading && <span className="tag-blue">sherpa 로딩…</span>}
              {briefQuery.isError && <span className="tag-red">sherpa 에러</span>}
              {briefQuery.isSuccess && <span className="tag-teal">sherpa </span>}
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

        {/* Phase 2.5 P6 — Dwell Time KPI 카드 (Mandiant 7d 벤치마크 비교) */}
        <DwellTimeKpi kpi={boardQuery.data?.kpi} />

        <div className="flex gap-4">
          <div className="flex-1 min-w-0 flex flex-col gap-3">
            <BoardCanvas pendingLog={pendingLog} clearPendingLog={() => setPendingLog(null)} />

            {/* 보드 노드 + 엣지 (SVG 그래프, UF-04) */}
            <Card
              title={<> 공격 체인 그래프 (chain_nodes + chain_edges)</>}
              subtitle={
                <span className="text-[10.5px] text-ink-400">
                  노드 클릭 = 상세 표시 · 엣지 모드에서 두 노드 연속 클릭 = 화살표 생성
                </span>
              }
              action={
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={toggleEdgeMode}
                    disabled={boardNodes.length < 2}
                    className={`text-[11px] px-2.5 py-1 rounded-lg border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                      edgeMode
                        ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                        : 'bg-ink-900 border-ink-700 text-ink-300 hover:border-brand-blue/40'
                    }`}
                    title={
                      boardNodes.length < 2
                        ? '노드 2개 이상 필요'
                        : edgeMode
                        ? '엣지 모드 켜짐 — 두 노드 연속 클릭으로 화살표 생성'
                        : '엣지 모드 켜기'
                    }
                  >
                     {edgeMode ? '엣지 모드 ON' : '엣지 모드'}
                  </button>
                  {edgeMode && edgeStartId && (
                    <button
                      onClick={() => setEdgeStartId(null)}
                      className="text-[11px] px-2 py-1 rounded-lg border border-ink-700 text-ink-400 hover:text-white"
                    >
                      취소
                    </button>
                  )}
                </div>
              }
              className="flex-shrink-0"
            >
              <ChainGraphCanvas
                nodes={boardNodes}
                edges={boardEdges}
                activeNodeId={activeBoardNode?.node_id ?? null}
                edgeMode={edgeMode}
                edgeStartId={edgeStartId}
                onSelectNode={handleGraphNodeSelect}
                onPickEdgeEnd={(fromId, toId) =>
                  createEdgeMutation.mutate({ fromId, toId })
                }
                onMoveNode={(nodeId, x, y) =>
                  movePositionMutation.mutate({ nodeId, x, y })
                }
                // Phase P.6 — LogPanel 단서 탭 drop 처리
                onDropClue={
                  caseId
                    ? (payload, x, y) => {
                        // 프론트 멱등 — 이미 있는 clue_key 차단
                        const exists = boardNodes.some((n) => {
                          const m = n.meta;
                          if (!m || typeof m !== 'object') return false;
                          return (
                            (m as Record<string, unknown>).clue_key === payload.clue_key
                          );
                        });
                        if (exists) {
                          showToast(
                            `📋 이미 보드에 있는 단서: ${payload.label}`,
                            3000,
                          );
                          return;
                        }
                        addClueNodeMutation.mutate({
                          clue_key: payload.clue_key,
                          label: payload.label,
                          pos_x: x,
                          pos_y: y,
                        });
                      }
                    : undefined
                }
              />
              {edgeMode && (
                <div className="mt-2 text-[10.5px] text-ink-400 leading-5">
                  {edgeStartId === null
                    ? '시작 노드를 클릭하세요.'
                    : '연결할 끝 노드를 클릭하세요. (취소: 우측 상단 [취소])'}
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
              title={<> ATT&CK 매핑 후보 (top {ATTACK_PAGE_SIZE})</>}
              subtitle="최신 매핑 순. 카드 클릭 시 우측 상세 표시 + '보드 추가'"
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
          <div className="w-[340px] shrink-0 flex flex-col gap-3">
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
                    {activeBoardNode.is_ai_suggested ? ' AI 제안' : ' 수동 추가'}
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
                       수락
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
                       거부
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

            <Card title={<span className="text-brand-purple"> AI 셰르파 브리핑</span>}>
              <BriefingPanel
                isLoading={briefQuery.isLoading}
                isError={briefQuery.isError}
                error={briefQuery.error}
                data={briefQuery.data}
                briefAttackId={briefAttackId}
              />
            </Card>

            <Card title={<> 수사관 메모</>}>
              <textarea
                value={memo}
                onChange={(e) => setMemo(e.target.value)}
                placeholder="메모 입력... (현재는 클라이언트 상태)"
                rows={3}
                className="input resize-y min-h-[72px]"
              />
            </Card>

            <LogPanel onDragStart={setPendingLog} boardNodes={boardNodes} />
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

interface BriefingPanelProps {
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  data: BriefingResponse | undefined;
  briefAttackId: string | null;
}

const BriefingPanel = ({
  isLoading,
  isError,
  error,
  data,
  briefAttackId,
}: BriefingPanelProps) => {
  if (isLoading) {
    return (
      <div className="bg-ink-950 border border-ink-700/70 rounded-xl p-3 text-[12px] text-ink-400 animate-pulse">
        KB 검색 중… (POST /api/sherpa/brief)
      </div>
    );
  }
  if (isError) {
    return (
      <div className="bg-ink-950 border border-ink-700/70 rounded-xl p-3 text-[12px] text-brand-red">
        <b>브리핑 호출 실패.</b>
        <div className="mt-1 text-[10.5px] text-ink-400">
          {(error as Error)?.message ?? '백엔드 /api/sherpa/brief 확인 필요'}
        </div>
      </div>
    );
  }
  if (!data) return null;

  // 케이스에 ATT&CK 매핑이 없는 경우 (백엔드가 technique_id: null 로 응답)
  if (!data.technique_id) {
    return (
      <div className="bg-ink-950 border border-ink-700/70 rounded-xl p-3 text-[12px] leading-6 text-ink-300">
        {data.briefing}
      </div>
    );
  }

  return (
    <div className="bg-ink-950 border border-ink-700/70 rounded-xl p-3 text-[12px] leading-6 text-ink-200">
      <div className="flex items-center gap-1.5 flex-wrap mb-2">
        <Badge tone="purple">{data.technique_id}</Badge>
        {data.tactic && <span className="text-[10.5px] text-ink-400">{data.tactic}</span>}
        <span
          className={`text-[10px] ml-auto ${
            data.confidence === 'high'
              ? 'text-brand-teal'
              : data.confidence === 'medium'
              ? 'text-brand-amber'
              : 'text-ink-400'
          }`}
        >
          신뢰도 {data.confidence}
        </span>
      </div>
      <div className="whitespace-pre-wrap text-ink-100 mb-2">{data.briefing}</div>

      {data.sources && data.sources.length > 0 && (
        <div className="mt-2 pt-2 border-t border-ink-700/50">
          <div className="text-[10px] text-ink-400 mb-1">출처 {data.sources.length}건</div>
          <div className="flex flex-wrap gap-1">
            {data.sources.map((s: SherpaSource) => (
              <span
                key={s.source_id}
                title={s.source_id}
                className="inline-flex items-center gap-1 text-[10px] bg-ink-900 border border-ink-700/70 rounded-full px-1.5 py-0.5"
              >
                <Badge tone={SOURCE_TONE[s.type] ?? 'gray'} size="sm">
                  {s.type}
                </Badge>
                <span className="text-ink-300 max-w-[120px] truncate">
                  {s.title || s.source_id}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {data.relatedTechniques && data.relatedTechniques.length > 0 && (
        <div className="mt-2 text-[10.5px] text-ink-400">
          관련 기법: {data.relatedTechniques.join(', ')}
        </div>
      )}

      <div className="mt-2 text-[10px] text-ink-500">
        {briefAttackId ? `attack_id: ${briefAttackId.slice(0, 8)}…` : '케이스 최상위 위험도 자동 선택'}
      </div>
    </div>
  );
};

export default V5Board;
