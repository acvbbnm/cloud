"""Phase J — Graph Data Science (GDS) 알고리즘 (2026-05-26, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §17.C (PDF §17.C 채택 — networkx 이식)

V-7 InvestigationBoard 의 chain_nodes + chain_edges 그래프에 GDS 알고리즘 적용:
    1. PageRank      — 공격자가 노린 중심 자산 자동 강조 (어떤 노드가 여러 경로의
                       수렴점인가 — 가장 중요한 표적)
    2. Label Propagation — 의심 계정 군집 (blast radius — 1건 침해 확정 시
                          유사 패턴 계정 자동 군집화)

학술 근거:
    - Brin & Page 1998 (Stanford) PageRank
    - Carnegie Mellon Attack Graph (Sheyner et al. 2002)
    - Zhu & Ghahramani 2002 Label Propagation
    - PDF §17.C — Cyberattack Graph Modeling (IEEE Xplore 2023)

CLAUDE.md 정합:
    - networkx 3.x 사용 (in-memory) — Neo4j 미도입 (오프라인·SQLite 단일 파일 정책)
    - AI 비판단 — 알고리즘 결과는 강조 시각화만, 자동 판단 X
    - 결정성 100% — 같은 입력 그래프 → 같은 결과
"""
from __future__ import annotations

from typing import Any, Optional

try:
    import networkx as nx
    _NETWORKX_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NETWORKX_AVAILABLE = False


# ─────────────────────────────────────────────────────────────
# 그래프 빌더
# ─────────────────────────────────────────────────────────────


def build_graph(nodes: list[dict], edges: list[dict]) -> Optional["nx.DiGraph"]:
    """chain_nodes + chain_edges 직렬화 데이터 → networkx DiGraph.

    chain_nodes 예시:
        {"id": "n1", "label": "EC2 인스턴스 A", "type": "host", ...}
    chain_edges 예시:
        {"src": "n1", "dst": "n2", "kind": "accessed", ...}

    networkx 미설치 시 None 반환 — caller 가 fallback 처리.
    """
    if not _NETWORKX_AVAILABLE:
        return None
    g: "nx.DiGraph" = nx.DiGraph()
    for n in nodes:
        nid = n.get("id") or n.get("node_id")
        if not nid:
            continue
        # 노드 메타데이터 그대로 보존 (label / type / created_at 등)
        g.add_node(nid, **{k: v for k, v in n.items() if k != "id"})
    for e in edges:
        src = e.get("src") or e.get("from") or e.get("source")
        dst = e.get("dst") or e.get("to") or e.get("target")
        if not src or not dst:
            continue
        if src not in g or dst not in g:
            continue
        g.add_edge(src, dst, **{k: v for k, v in e.items() if k not in ("src", "dst")})
    return g


# ─────────────────────────────────────────────────────────────
# PageRank — 중심 자산 식별
# ─────────────────────────────────────────────────────────────


def page_rank(
    graph: Optional["nx.DiGraph"],
    *,
    alpha: float = 0.85,
    max_iter: int = 100,
) -> dict[str, float]:
    """PageRank — 노드 중심성 점수 (0~1, 합=1).

    Brin & Page 1998 표준 알고리즘. networkx 의존.

    파라미터:
        alpha    : damping factor (기본 0.85, 표준값)
        max_iter : 수렴 최대 반복 (기본 100)

    반환: {node_id: score} — 모두 합 = 1.
    networkx 미설치·빈 그래프 시 {} 반환.
    """
    if not graph or graph.number_of_nodes() == 0:
        return {}
    try:
        ranks = nx.pagerank(graph, alpha=alpha, max_iter=max_iter)
    except Exception:  # 수렴 실패 등
        # uniform fallback
        n = graph.number_of_nodes()
        return {nid: 1.0 / n for nid in graph.nodes()}
    return dict(ranks)


def page_rank_top_k(
    graph: Optional["nx.DiGraph"],
    k: int = 3,
    *,
    alpha: float = 0.85,
) -> list[tuple[str, float]]:
    """PageRank 상위 k 노드 — UI 강조 후보."""
    ranks = page_rank(graph, alpha=alpha)
    if not ranks:
        return []
    sorted_ranks = sorted(ranks.items(), key=lambda x: -x[1])
    return sorted_ranks[:k]


# ─────────────────────────────────────────────────────────────
# Label Propagation — 의심 군집 식별
# ─────────────────────────────────────────────────────────────


def label_propagation_communities(
    graph: Optional["nx.DiGraph"],
) -> list[set[str]]:
    """Label Propagation 으로 그래프 군집 분리.

    Zhu & Ghahramani 2002 — semi-supervised learning 의 그래프 적용.
    유사한 패턴(엣지 밀도) 노드들이 같은 라벨로 수렴.

    networkx 의 asyn_lpa_communities 사용 (방향성 보존).
    반환: 각 군집의 노드 ID set 리스트.
    """
    if not graph or graph.number_of_nodes() == 0:
        return []
    try:
        # 방향성 그래프 → 무방향으로 변환 후 LPA (LPA 는 무방향 그래프 표준)
        undirected = graph.to_undirected()
        # 결정성 보장 위해 seed 고정
        communities = nx.community.label_propagation_communities(undirected)
        return [set(c) for c in communities]
    except Exception:  # pragma: no cover
        return [set(graph.nodes())]


# ─────────────────────────────────────────────────────────────
# 종합 분석 — V-7 보드 UI 입력
# ─────────────────────────────────────────────────────────────


def analyze_board(
    nodes: list[dict],
    edges: list[dict],
    *,
    pagerank_top_k: int = 3,
) -> dict[str, Any]:
    """V-7 보드 그래프 종합 분석 — UI 표시용 결과 구조화.

    반환:
        {
          "pagerank": {node_id: score, ...},
          "pagerank_top": [(node_id, score), ...],  # 상위 K개
          "communities": [[node_id, ...], ...],     # Label Propagation 군집
          "stats": {nodes, edges, communities_count}
        }
    networkx 미설치 시 빈 결과 (자연 degrade).
    """
    graph = build_graph(nodes, edges)
    if graph is None:
        return {
            "pagerank": {},
            "pagerank_top": [],
            "communities": [],
            "stats": {
                "nodes": len(nodes),
                "edges": len(edges),
                "communities_count": 0,
                "networkx_available": False,
            },
        }

    pr = page_rank(graph)
    pr_top = page_rank_top_k(graph, k=pagerank_top_k)
    communities = label_propagation_communities(graph)

    return {
        "pagerank": pr,
        "pagerank_top": [
            {"node_id": nid, "score": score} for nid, score in pr_top
        ],
        "communities": [sorted(c) for c in communities],
        "stats": {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "communities_count": len(communities),
            "networkx_available": True,
        },
    }


def _grid_pack(
    node_ids: list[str],
    *,
    x0: int,
    y0: int,
    cols: int,
    cell_w: int,
    cell_h: int,
) -> dict[str, tuple[int, int]]:
    """격자 배치 헬퍼 — row-major 순서로 (x0,y0) 부터 cell_w×cell_h 셀에 배치."""
    out: dict[str, tuple[int, int]] = {}
    for i, nid in enumerate(node_ids):
        r, c = divmod(i, cols)
        out[nid] = (x0 + c * cell_w, y0 + r * cell_h)
    return out


def _resolve_collisions(
    positions: dict[str, tuple[int, int]],
    *,
    min_gap_x: int = 200,
    min_gap_y: int = 90,
    max_iter: int = 30,
) -> dict[str, tuple[int, int]]:
    """충돌 회피 — 두 노드가 min_gap 이내면 서로 떨어뜨림 (단순 반발 시뮬).

    NODE_W=168 + 여유 32 = 200, NODE_H=64 + 여유 26 = 90 가 기본값.
    """
    ids = list(positions.keys())
    pos = {nid: list(p) for nid, p in positions.items()}
    for _ in range(max_iter):
        moved = False
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                dx = pos[b][0] - pos[a][0]
                dy = pos[b][1] - pos[a][1]
                overlap_x = min_gap_x - abs(dx)
                overlap_y = min_gap_y - abs(dy)
                if overlap_x > 0 and overlap_y > 0:
                    # 둘 다 겹침 — 더 작은 축으로 분리
                    if overlap_x < overlap_y:
                        shift = (overlap_x + 1) / 2
                        sign = 1 if dx >= 0 else -1
                        pos[a][0] -= int(sign * shift)
                        pos[b][0] += int(sign * shift)
                    else:
                        shift = (overlap_y + 1) / 2
                        sign = 1 if dy >= 0 else -1
                        pos[a][1] -= int(sign * shift)
                        pos[b][1] += int(sign * shift)
                    moved = True
        if not moved:
            break
    return {nid: (p[0], p[1]) for nid, p in pos.items()}


def auto_layout_positions(
    node_ids: list[str],
    edges: list[tuple[str, str]],
    *,
    canvas_w: int = 1100,
    canvas_h: int = 620,
    pad: int = 60,
) -> dict[str, tuple[int, int]]:
    """V-5 자동 정렬 — 계층형(layered) 배치로 엣지 교차 최소화.

    정책 (2026-06-03 — spring_layout → 계층형 전환):
      · connected: depth(열) × row 계층 배치 (_layered_layout).
        부모→자식 엣지가 좌→우로만 흘러 노드를 가로지르지 않음.
        단일 chain → 한 줄 / 분기 → 자식 세로 분산.
      · isolated: connected 아래 격자 (엣지 0 이면 전체 상단 격자).

    Returns:
        {node_id: (x, y)} — V-5 캔버스 픽셀 좌표 (좌상단 0,0 기준).
    """
    if not node_ids:
        return {}

    # 2026-06-03 — UI ChainGraphCanvas 의 NODE_W/H (168/64) 와 동기화.
    #   (이전 200/78 은 UI 가 168/64 로 되돌려져 불일치 → 노드 과도하게 벌어짐.)
    # 2026-06-03 — UI ChainGraphCanvas 의 NODE_W/H (168/64) 와 동기화.
    # 2026-06-05 — 연결 구조(엣지)가 잘 보이도록 간격만 소폭 확대 (28/26 → 60/40).
    #   중앙정렬·직각라우팅은 도입하지 않음(이전 피드백) — 상단정렬·베지어 유지.
    NODE_W = 168
    NODE_H = 64
    GAP_X = 60
    GAP_Y = 40
    CELL_W = NODE_W + GAP_X      # 228
    CELL_H = NODE_H + GAP_Y      # 104
    cols_all = max(1, (canvas_w - 2 * pad) // CELL_W)

    # networkx 없거나 1 노드 → 전체 격자 (상단부터)
    if not _NETWORKX_AVAILABLE or len(node_ids) == 1:
        return _grid_pack(node_ids, x0=pad, y0=pad, cols=cols_all, cell_w=CELL_W, cell_h=CELL_H)

    # 엣지에 등장하는 노드 = connected, 그 외 = isolated
    connected_set = set()
    for a, b in edges:
        connected_set.add(a)
        connected_set.add(b)
    connected = [n for n in node_ids if n in connected_set]
    isolated = [n for n in node_ids if n not in connected_set]

    # 엣지가 전혀 없으면 (전부 isolated) → 그냥 상단부터 격자 (하단 쏠림 방지)
    if not connected:
        return _grid_pack(node_ids, x0=pad, y0=pad, cols=cols_all, cell_w=CELL_W, cell_h=CELL_H)

    out: dict[str, tuple[int, int]] = {}

    # connected — 계층형(layered) 배치: depth 를 열(column), 같은 depth 노드를
    # 행(row)으로 펼침. 부모→자식 엣지가 항상 좌→우로 흘러 노드를 가로지르지
    # 않음 (분기는 세로로 분산). chain·tree·DAG 모두 깔끔.
    layer_pos = _layered_layout(
        connected, edges, x0=pad, y0=pad, cell_w=CELL_W, cell_h=CELL_H,
    )
    out.update(layer_pos)

    # isolated: connected 영역 아래쪽에 격자 (있을 때만)
    if isolated:
        max_y = max((p[1] for p in out.values()), default=pad)
        iso_y0 = max_y + CELL_H
        iso_pos = _grid_pack(
            isolated, x0=pad, y0=iso_y0, cols=cols_all,
            cell_w=CELL_W, cell_h=CELL_H,
        )
        out.update(iso_pos)

    return out


def _layered_layout(
    nodes: list[str],
    edges: list[tuple[str, str]],
    *,
    x0: int,
    y0: int,
    cell_w: int,
    cell_h: int,
) -> dict[str, tuple[int, int]]:
    """계층형 배치 — depth(BFS 레벨)를 열, 같은 depth 를 행으로 배치.

    엣지 교차 최소화 정책:
      · depth = 루트(in-degree 0)로부터의 최장 경로 거리 (longest-path layering)
      · 같은 depth 노드는 부모의 평균 행 위치 근처로 정렬 (barycenter) 후 행 부여
      · 단일 chain (분기 없음) → 한 줄 (모두 row 0)
      · 분기 → 자식들이 세로로 펼쳐짐

    좌표: x = x0 + depth*cell_w, y = y0 + row*cell_h
    """
    if not nodes:
        return {}
    node_set = set(nodes)
    succ: dict[str, list[str]] = {n: [] for n in nodes}
    pred: dict[str, list[str]] = {n: [] for n in nodes}
    indeg: dict[str, int] = {n: 0 for n in nodes}
    for a, b in edges:
        if a in node_set and b in node_set and b not in succ[a]:
            succ[a].append(b)
            pred[b].append(a)
            indeg[b] += 1

    # ── depth 계산 (longest path; 사이클이면 방문 제한으로 안전) ──
    depth: dict[str, int] = {n: 0 for n in nodes}
    roots = [n for n in nodes if indeg[n] == 0] or [nodes[0]]
    # Kahn 위상정렬 기반 longest-path. 사이클 노드는 위상순서에서 빠지므로
    # 마지막에 depth 0 (또는 최대) 로 fallback.
    from collections import deque
    indeg_work = dict(indeg)
    queue = deque(roots)
    visited_order: list[str] = []
    while queue:
        n = queue.popleft()
        visited_order.append(n)
        for c in succ[n]:
            if depth[c] < depth[n] + 1:
                depth[c] = depth[n] + 1
            indeg_work[c] -= 1
            if indeg_work[c] == 0:
                queue.append(c)
    # 위상정렬 미방문(사이클) 노드 — 직전 노드 depth+1 best-effort
    for n in nodes:
        if n not in visited_order:
            ds = [depth[p] + 1 for p in pred[n] if p in depth]
            depth[n] = max(ds) if ds else 0

    # ── 같은 depth 내 행(row) 부여 — barycenter (부모 평균 행) 순 정렬 ──
    from collections import defaultdict
    by_depth: dict[int, list[str]] = defaultdict(list)
    for n in nodes:
        by_depth[depth[n]].append(n)

    row_of: dict[str, int] = {}
    out: dict[str, tuple[int, int]] = {}
    for d in sorted(by_depth):
        layer = by_depth[d]
        if d == 0:
            # 루트 레이어 — 입력 순서 유지
            ordered = layer
        else:
            # 부모들의 평균 row 로 정렬 (교차 최소화)
            def bary(n: str) -> float:
                ps = [row_of[p] for p in pred[n] if p in row_of]
                return sum(ps) / len(ps) if ps else 0.0
            ordered = sorted(layer, key=bary)
        for r, n in enumerate(ordered):
            row_of[n] = r
            out[n] = (x0 + d * cell_w, y0 + r * cell_h)

    # 단일 chain (각 depth 노드 1개) 이면 자연히 한 줄 (row 0) 이 됨.
    return out
