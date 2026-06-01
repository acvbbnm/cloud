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
import { getBoard, createNode, updateNode, createEdge, deleteEdge, autoLayout, isClueNode } from '@/api/board';
import { runMap } from '@/api/analysis';
import { getAttack } from '@/api/analysis';
import { postBrief } from '@/api/sherpa';
import { explainClue } from '@/api/clueTree';
import type {
  AttackEventItem,
  BoardNode,
  BriefingResponse,
  SherpaSource,
  IncidentType,
  ClueNodeMeta,
} from '@/types';

import LogPanel from './LogPanel';
// BoardCanvas — 가독성 정리 #1 로 제거 (메인 ChainGraphCanvas 와 중복)
// import BoardCanvas from './BoardCanvas';
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

  // pendingLog — BoardCanvas 제거로 더 이상 표시하지 않음.
  // LogPanel 의 onDragStart 콜백은 유지 (drag start 감지용 noop).
  const [, setPendingLog] = useState<BoardLog | null>(null);
  const [activeAttack, setActiveAttack] = useState<AttackEventItem | null>(null);
  const [activeBoardNode, setActiveBoardNode] = useState<BoardNode | null>(null);
  const [memo, setMemo] = useState('');

  // UF-04 — 엣지 생성 모드 (chain_nodes 간 화살표 연결)
  const [edgeMode, setEdgeMode] = useState(false);
  const [edgeStartId, setEdgeStartId] = useState<string | null>(null);
  // 가독성 정리 #2 — ATT&CK 후보 그리드 접기/펼치기 토글 (기본 접힘)
  const [attackOpen, setAttackOpen] = useState(false);
  // 가독성 정리 #3 — 셰르파 브리핑 카드 접기 (기본 접힘, 사이드바 길이 단축)
  const [sherpaOpen, setSherpaOpen] = useState(false);

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
  // P.31 — 단서 노드(attack_id=null) 선택 시는 호출 자체를 비활성화
  //   (사용자 피드백: "AI 브리핑 연결도 안 되어있는데 왜 남겨뒀어").
  //   단서일 땐 우측 상세 패널이 explainClue 풍부 메타로 대체.
  const activeIsClue = activeBoardNode ? isClueNode(activeBoardNode) : false;
  const briefAttackId =
    activeBoardNode?.attack_id ?? activeAttack?.attack_id ?? null;
  const briefEnabled = !!caseId && !activeIsClue;
  const briefQuery = useQuery({
    queryKey: ['sherpa', 'brief', caseId, briefAttackId],
    queryFn: () =>
      postBrief({
        caseId: caseId!,
        eventId: briefAttackId,
      }),
    enabled: briefEnabled,
    staleTime: 5 * 60 * 1000,
  });

  // P.31 — 단서 노드 선택 시 풍부 메타 (description / examples /
  //   discrimination_explanation / per-사고유형 likelihood / academic_source /
  //   how_to_find) 조회. 사용자 피드백: "상세 페이지엔 어떤 단서였는지
  //   시스템 구성에서 보였던것 처럼 좀더 자세하게".
  const activeClueKey: string | null =
    activeIsClue && activeBoardNode?.meta
      ? (activeBoardNode.meta as ClueNodeMeta).clue_key ?? null
      : null;
  const clueExplainQuery = useQuery({
    queryKey: ['clueExplain', activeClueKey],
    queryFn: () => explainClue(activeClueKey!),
    enabled: !!activeClueKey,
    staleTime: 10 * 60 * 1000,
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

  // UF-04-b — 엣지 삭제 (chain_edges) — hover ✕ 또는 라인 클릭
  const deleteEdgeMutation = useMutation({
    mutationFn: (edgeId: string) => deleteEdge(edgeId),
    onSuccess: () => {
      showToast('엣지 삭제 — 공격 체인 연결 해제');
      queryClient.invalidateQueries({ queryKey: ['board', caseId] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`엣지 삭제 실패: ${msg}`);
    },
  });

  // 자동 정렬 — networkx spring_layout 결과로 노드 좌표 일괄 재배치
  const autoLayoutMutation = useMutation({
    mutationFn: () => autoLayout(caseId!),
    onSuccess: (data) => {
      showToast(`✨ 자동 정렬 ${data.updated_nodes}개 노드 재배치`);
      queryClient.invalidateQueries({ queryKey: ['board', caseId] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`자동 정렬 실패: ${msg}`);
    },
  });

  // 가독성 정리 — V-5 에서 직접 ATT&CK 매핑 실행 (V-6 안 거치고)
  const mapAttackMutation = useMutation({
    mutationFn: () => runMap(caseId!),
    onSuccess: (stats) => {
      showToast(
        `↻ 매핑 ${stats.mapped}/${stats.total_ocsf}건 (매핑률 ${Math.round((stats.mappingRate ?? 0) * 100)}%)`,
      );
      queryClient.invalidateQueries({ queryKey: ['attack', caseId] });
      queryClient.invalidateQueries({ queryKey: ['board', caseId] });
      setAttackOpen(true); // 결과 자동 펼침
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`매핑 실패: ${msg}`);
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
        {/* P.29 (2026-05-31 사용자 피드백: "백엔드 응답 확인 칸 시연 시 제거") —
            board/attack/sherpa loading·error·caseId·카운트 디버그 패널 제거. */}

        {/* Phase 2.5 P6 — Dwell Time KPI 카드 (Mandiant 7d 벤치마크 비교) */}
        <DwellTimeKpi kpi={boardQuery.data?.kpi} />

        <div className="flex gap-4">
          <div className="flex-1 min-w-0 flex flex-col gap-3">
            {/* 가독성 정리 #1 — 옛 BoardCanvas 제거 (메인 ChainGraphCanvas 와 중복).
                pendingLog 토스트는 ChainGraphCanvas 의 onDropClue 가 처리. */}

            {/* 메인 보드 — ATT&CK + 단서 + 엣지 통합 그래프 (SVG, UF-04) */}
            <Card
              title={<>🗺 수사 보드 (단서 · ATT&CK · 엣지)</>}
              subtitle={
                <span className="text-[10.5px] text-ink-400">
                  좌측 LogPanel 의 🔍 단서를 드래그해서 떨어뜨리기 · 노드 클릭 = 상세 ·
                  엣지 모드에서 두 노드 연속 클릭 = 화살표
                </span>
              }
              action={
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => autoLayoutMutation.mutate()}
                    disabled={!caseId || boardNodes.length === 0 || autoLayoutMutation.isPending}
                    className="text-[11px] px-2.5 py-1 rounded-lg border border-brand-teal/50 bg-brand-teal/10 text-brand-teal hover:bg-brand-teal/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                    title="networkx spring_layout 으로 노드 좌표 일괄 재배치 (POST /api/board/auto-layout)"
                  >
                    {autoLayoutMutation.isPending ? '정렬 중…' : '✨ 자동 정렬'}
                  </button>
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
                // Phase P.15 — caseId 변경 시 viewport/tempPos 자동 reset
                // (zoom·pan 상태가 다른 case 로 이월되어 노드 안 보이는 버그 차단)
                key={caseId}
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
                onDeleteEdge={(edgeId) => deleteEdgeMutation.mutate(edgeId)}
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

            {/* ATT&CK 매핑 결과 후보 — 가독성 정리 #2: collapsible (기본 접힘) */}
            <Card
              title={
                <button
                  onClick={() => setAttackOpen((v) => !v)}
                  className="flex items-center gap-1.5 text-left hover:text-brand-purple/80 transition-colors"
                  title={attackOpen ? '접기' : '펼치기'}
                >
                  <span className="text-[11px] text-ink-400">{attackOpen ? '▼' : '▶'}</span>
                  <span>
                     ATT&CK 매핑 후보 ({attackItems.length}/{attackQuery.data?.total ?? 0})
                  </span>
                </button>
              }
              subtitle={
                attackOpen
                  ? '최신 매핑 순. 카드 클릭 시 우측 상세 표시 + "보드 추가"'
                  : undefined
              }
              action={
                <button
                  onClick={() => mapAttackMutation.mutate()}
                  disabled={!caseId || mapAttackMutation.isPending}
                  className="text-[11px] px-2.5 py-1 rounded-lg border border-brand-purple/50 bg-brand-purple/10 text-brand-purple hover:bg-brand-purple/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  title="OCSF → ATT&CK 매핑 (POST /api/analysis/map)"
                >
                  {mapAttackMutation.isPending ? '매핑 중…' : '↻ 매핑 실행'}
                </button>
              }
              className="flex-shrink-0"
            >
              {!attackOpen ? (
                <div className="text-[11.5px] text-ink-400 py-1">
                  카드를 펼쳐 ATT&CK 후보를 보드에 추가 (top {ATTACK_PAGE_SIZE})
                </div>
              ) : attackItems.length === 0 ? (
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
            {/* V1.fix.13 (2026-05-31) — 상세 패널 제목·서브타이틀 보강. 사용자 피드백: "상세쪽 설명 약간 수정 필요". */}
            <Card
              title={<>선택 노드 상세</>}
              subtitle="좌측 보드 노드 또는 아래 ATT&CK 후보를 클릭 → 사고유형 likelihood · KB 메타 · 수락/거부"
            >
              {activeBoardNode && activeIsClue ? (
                <ClueDetailPanel
                  node={activeBoardNode}
                  explain={clueExplainQuery.data}
                  isLoading={clueExplainQuery.isLoading}
                  isError={clueExplainQuery.isError}
                  onConfirm={() =>
                    updateStatusMutation.mutate({
                      nodeId: activeBoardNode.node_id,
                      status: 'CONFIRMED',
                    })
                  }
                  onReject={() =>
                    updateStatusMutation.mutate({
                      nodeId: activeBoardNode.node_id,
                      status: 'REJECTED',
                    })
                  }
                  busy={updateStatusMutation.isPending}
                />
              ) : activeBoardNode ? (
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
                <div className="text-[12px] text-ink-400 leading-5 space-y-2">
                  <div>
                    좌측 보드의 <span className="text-ink-200">공격 체인 노드</span> 또는 아래의{' '}
                    <span className="text-ink-200">ATT&CK 후보</span>를 클릭하면 상세가 표시됩니다.
                  </div>
                  <ul className="text-[11px] text-ink-500 leading-4 space-y-0.5 pl-3">
                    <li>· <span className="text-brand-teal/90">단서 노드</span> 클릭 → 사고유형 likelihood · KB 메타 · 학술 출처</li>
                    <li>· <span className="text-brand-purple/90">ATT&CK 노드</span> 클릭 → 기법·전술 + AI 셰르파 KB 브리핑</li>
                    <li>· <span className="text-amber-300/90">후보</span> 클릭 → [+ 보드 추가] 로 노드 생성</li>
                  </ul>
                </div>
              )}
            </Card>

            {/* P.31 — 단서 노드 선택 시는 브리핑 카드 자체 미렌더.
                사용자 피드백: "AI 브리핑 연결도 안되어있는데 왜 남겨뒀어".
                단서는 attack_id 가 null 이라 brief 호출 안 됨 — 상세 패널의
                clueExplainQuery (description / discrimination / likelihood top N
                / academic_source / how_to_find) 가 대신 KB 컨텍스트 역할.
                ATT&CK 노드·후보 선택 시 또는 미선택 시(케이스 최상위 자동)만 표시. */}
            {!activeIsClue && (
              <Card
                title={
                  <button
                    onClick={() => setSherpaOpen((v) => !v)}
                    className="flex items-center gap-1.5 text-left text-brand-purple hover:opacity-80 transition-colors"
                    title={sherpaOpen ? '접기' : '펼치기'}
                  >
                    <span className="text-[11px] text-ink-400">{sherpaOpen ? '▼' : '▶'}</span>
                    <span> AI 셰르파 브리핑</span>
                    {!sherpaOpen && briefQuery.isSuccess && (
                      <span className="ml-1 text-[10px] text-brand-teal/70">
                         응답 준비됨
                      </span>
                    )}
                    {!sherpaOpen && briefQuery.isLoading && (
                      <span className="ml-1 text-[10px] text-brand-blue/70 animate-pulse">
                        로딩…
                      </span>
                    )}
                  </button>
                }
                subtitle={
                  !sherpaOpen ? undefined : (
                    <a
                      href="/sherpa"
                      className="text-[10px] text-ink-400 hover:text-brand-purple"
                    >
                      더 깊은 질의는 V-8 셰르파 페이지에서 →
                    </a>
                  )
                }
              >
                {sherpaOpen ? (
                  <BriefingPanel
                    isLoading={briefQuery.isLoading}
                    isError={briefQuery.isError}
                    error={briefQuery.error}
                    data={briefQuery.data}
                    briefAttackId={briefAttackId}
                  />
                ) : (
                  <div className="text-[11.5px] text-ink-400 py-1">
                    카드 펼치면 선택 노드의 KB 컨텍스트 브리핑 표시
                  </div>
                )}
              </Card>
            )}

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

// P.31 — 단서 노드 풍부 메타 패널.
//   사용자 피드백: "상세 페이지엔 어떤 단서였는지 시스템 구성에서 보였던것처럼
//   좀더 자세하게 볼 수 있게, AI 브리핑 연결도 안되어있는데 왜 남겨뒀어.
//   그리고 왜 랜섬딱지만 붙어있어".
// 응답:
//   · 시스템 구성처럼 description / how_to_find (NCP·NHN) / examples / 학술 인용을
//     Row 형식으로 풍부 표시 → V-1 가이드 체크리스트와 동일한 디자인 언어.
//   · aggregated_likelihood top N 을 한국어 칩으로 다중 표시 →
//     "랜섬 0.84, 자격증명 0.62, 권한상승 0.41" 처럼 변별 사고유형 모두 노출.
//   · explainClue (GET /api/clue-tree/explain/{clue_key}) — Phase H.4 + L.2 응답
//     사용 (decision_tree.json + clue_descriptions.json 정적 소스).

const INCIDENT_KO_DETAIL: Record<IncidentType, string> = {
  CREDENTIAL_THEFT: '자격증명 탈취',
  PRIVILEGE_ESCALATION: '권한 상승',
  DATA_EXFILTRATION: '데이터 유출',
  AUDIT_LOG_TAMPERING: '로그 변조',
  RANSOMWARE: '랜섬웨어',
  MISCONFIG_EXPOSURE: '설정 노출',
  PHISH_INITIAL_ACCESS: '피싱 침투',
  INSIDER_THREAT: '내부자 위협',
  UNCLASSIFIED: '미분류',
};

interface ClueDetailPanelProps {
  node: BoardNode;
  explain:
    | {
        clue_key: string;
        description?: string;
        discrimination_explanation?: string;
        academic_source?: string;
        iso_framework?: string | null;
        examples?: string[];
        how_to_find?: { ncp?: string; nhn?: string; verify?: string };
        aggregated_likelihood?: Record<string, number>;
        techniques?: string[];
        confidence?: string;
      }
    | undefined;
  isLoading: boolean;
  isError: boolean;
  onConfirm: () => void;
  onReject: () => void;
  busy: boolean;
}

const ClueDetailPanel = ({
  node,
  explain,
  isLoading,
  isError,
  onConfirm,
  onReject,
  busy,
}: ClueDetailPanelProps) => {
  const meta = (node.meta ?? null) as ClueNodeMeta | null;
  const stage = meta?.stage ?? null;
  const source = meta?.source ?? null;
  // aggregated_likelihood top N (0.05 이상만, 최대 5개) — 사고유형 칩.
  const topIncidents = Object.entries(explain?.aggregated_likelihood ?? {})
    .filter(([, v]) => typeof v === 'number' && v >= 0.05)
    .sort((a, b) => (b[1] as number) - (a[1] as number))
    .slice(0, 5) as Array<[IncidentType, number]>;
  const sourceKo: Record<string, string> = {
    manual_drag: '수동 드래그',
    manual_bulk: '수동 일괄',
    auto_seed: '자동 시드',
    user_added: '수동 추가',
    direct_input: '직접 입력',
    log_analysis: '로그 분석',
    tree_candidate: '트리 후보',
  };

  return (
    <div className="text-[12.5px]">
      <div className="flex items-start gap-1.5 mb-2">
        <span className="text-[14px]">🔍</span>
        <div className="font-bold text-[14px] flex-1 leading-tight">{node.label}</div>
      </div>
      <div className="text-[10.5px] text-ink-400 font-mono mb-2 truncate">
        {meta?.clue_key ?? '—'}
      </div>

      <Row label="상태">
        <Badge tone={node.status === 'CONFIRMED' ? 'teal' : node.status === 'REJECTED' ? 'red' : 'gray'}>
          {node.status}
        </Badge>
      </Row>
      <Row label="유형"> 단서 (clue)</Row>
      {stage !== null && (
        <Row label="단계">
          <span className="font-mono text-[11.5px]">S{stage}</span>
        </Row>
      )}
      {source && (
        <Row label="입력 경로">
          <span className="text-[11.5px]">{sourceKo[source] ?? source}</span>
        </Row>
      )}
      {explain?.confidence && (
        <Row label="신뢰도">
          <span className="text-[11.5px]">{explain.confidence}</span>
        </Row>
      )}

      {/* 사고유형 적합도 — top N 다중 칩.
          사용자 피드백: "왜 랜섬딱지만 붙어있어" — 노드 위 단일 배지(=가장 강한 1개)
          외에 이 단서가 변별하는 모든 사고유형 likelihood 노출. */}
      <div className="mt-3 mb-1.5">
        <div className="text-ink-400 text-[10.5px] uppercase tracking-wider mb-1.5">
          사고유형 적합도 (top {topIncidents.length})
        </div>
        {topIncidents.length === 0 ? (
          <div className="text-[11.5px] text-ink-500">
            {isLoading ? '계산 중…' : '데이터 없음 (BN 미설정)'}
          </div>
        ) : (
          <div className="flex flex-wrap gap-1">
            {topIncidents.map(([type, score]) => (
              <span
                key={type}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-ink-900/60 border border-ink-700/60 text-[10.5px]"
                title={`${type} likelihood = ${score.toFixed(3)}`}
              >
                <span className="text-ink-200">{INCIDENT_KO_DETAIL[type] ?? type}</span>
                <span className="font-mono text-brand-teal">{(score * 100).toFixed(0)}%</span>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 단서 풀이 — V-1 가이드와 동일한 시스템 구성 언어 */}
      {isLoading && (
        <div className="mt-2 text-[11px] text-ink-400 animate-pulse">
          단서 메타 조회 중…
        </div>
      )}
      {isError && (
        <div className="mt-2 text-[11px] text-brand-red">
          단서 메타 조회 실패 — KB 응답 확인 필요
        </div>
      )}
      {explain?.description && (
        <div className="mt-3">
          <div className="text-ink-400 text-[10.5px] uppercase tracking-wider mb-1">정의</div>
          <div className="text-[11.5px] leading-5 text-ink-100">{explain.description}</div>
        </div>
      )}
      {explain?.discrimination_explanation && (
        <div className="mt-3">
          <div className="text-ink-400 text-[10.5px] uppercase tracking-wider mb-1">
            변별 풀이
          </div>
          <div className="text-[11.5px] leading-5 text-ink-200">
            {explain.discrimination_explanation}
          </div>
        </div>
      )}
      {explain?.how_to_find && (explain.how_to_find.ncp || explain.how_to_find.nhn || explain.how_to_find.verify) && (
        <div className="mt-3">
          <div className="text-ink-400 text-[10.5px] uppercase tracking-wider mb-1">
            CSP 콘솔에서 찾는 법
          </div>
          <div className="text-[11px] leading-5 space-y-0.5">
            {explain.how_to_find.ncp && (
              <div><span className="text-brand-blue font-semibold">NCP</span> · {explain.how_to_find.ncp}</div>
            )}
            {explain.how_to_find.nhn && (
              <div><span className="text-brand-teal font-semibold">NHN</span> · {explain.how_to_find.nhn}</div>
            )}
            {explain.how_to_find.verify && (
              <div><span className="text-ink-400">검증</span> · {explain.how_to_find.verify}</div>
            )}
          </div>
        </div>
      )}
      {explain?.examples && explain.examples.length > 0 && (
        <div className="mt-3">
          <div className="text-ink-400 text-[10.5px] uppercase tracking-wider mb-1">예시</div>
          <ul className="text-[11px] leading-5 list-disc list-inside text-ink-200 space-y-0.5">
            {explain.examples.slice(0, 4).map((ex, i) => (
              <li key={i} className="truncate">{ex}</li>
            ))}
          </ul>
        </div>
      )}
      {explain?.techniques && explain.techniques.length > 0 && (
        <div className="mt-3">
          <div className="text-ink-400 text-[10.5px] uppercase tracking-wider mb-1">
            연관 ATT&CK 기법
          </div>
          <div className="flex flex-wrap gap-1">
            {explain.techniques.slice(0, 6).map((t) => (
              <Badge key={t} tone="purple">{t}</Badge>
            ))}
          </div>
        </div>
      )}
      {(explain?.academic_source || explain?.iso_framework) && (
        <div className="mt-3 text-[10.5px] text-ink-500 leading-5 border-t border-ink-700/30 pt-2">
          {explain.academic_source && (
            <div><span className="text-ink-400">학술</span> · {explain.academic_source}</div>
          )}
          {explain.iso_framework && (
            <div><span className="text-ink-400">ISO</span> · {explain.iso_framework}</div>
          )}
        </div>
      )}

      <div className="flex gap-2 mt-4">
        <button
          onClick={onConfirm}
          disabled={busy || node.status === 'CONFIRMED'}
          className="btn-primary btn-sm flex-1 disabled:opacity-40"
        >
           수락
        </button>
        <button
          onClick={onReject}
          disabled={busy || node.status === 'REJECTED'}
          className="btn-danger btn-sm flex-1 disabled:opacity-40"
        >
           거부
        </button>
      </div>
    </div>
  );
};

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
