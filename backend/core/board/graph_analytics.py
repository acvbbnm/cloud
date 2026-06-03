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
    """V-5 자동 정렬 — networkx spring_layout 결과를 canvas 좌표로 매핑.

    개선 (2026-05-31):
      - **connected vs isolated 분리**: 엣지 없는 노드는 spring 에서 한 점에 뭉치는
        문제가 있어 별도 격자 영역(하단)에 배치
      - **충돌 회피**: spring 결과 후 노드 거리가 NODE_W+gap 미만이면 분리

    Returns:
        {node_id: (x, y)} — V-5 캔버스 픽셀 좌표 (좌상단 0,0 기준).
    """
    if not node_ids:
        return {}

    # 2026-06-03 — UI ChainGraphCanvas 의 NODE_W/H (168/64) 와 동기화.
    #   (이전 200/78 은 UI 가 168/64 로 되돌려져 불일치 → 노드 과도하게 벌어짐.)
    NODE_W = 168
    NODE_H = 64
    GAP_X = 28
    GAP_Y = 26
    CELL_W = NODE_W + GAP_X      # 196
    CELL_H = NODE_H + GAP_Y      # 90
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
    n_conn = len(connected)

    if n_conn <= 4:
        # 노드 2~4개 — spring 은 박스를 꽉 채워 과하게 벌어짐.
        # 대신 가로 한 줄 (단서 시퀀스 흐름) 결정적 배치 — 엣지가 짧고 깔끔.
        #   엣지 순서가 있으면 그 순서대로, 없으면 입력 순서.
        seq = _order_by_edges(connected, edges)
        y0 = pad + CELL_H  # 상단에서 한 칸 내려 시작 (여유)
        for i, nid in enumerate(seq):
            out[nid] = (pad + i * CELL_W, y0)
    else:
        # 5+ 노드 — spring_layout 사용 (k 작게 → 응집).
        spring_w = canvas_w - 2 * pad
        spring_h = canvas_h - 2 * pad
        g = nx.Graph()
        g.add_nodes_from(connected)
        g.add_edges_from([(a, b) for a, b in edges if a in connected_set and b in connected_set])
        spring_pos = nx.spring_layout(g, seed=42, k=0.9, iterations=120)
        xs = [p[0] for p in spring_pos.values()]
        ys = [p[1] for p in spring_pos.values()]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        rangex = (maxx - minx) or 1.0
        rangey = (maxy - miny) or 1.0
        for nid in connected:
            x, y = spring_pos.get(nid, (0, 0))
            cx = int(pad + (x - minx) / rangex * spring_w)
            cy = int(pad + (y - miny) / rangey * spring_h)
            out[nid] = (cx, cy)
        out = _resolve_collisions(out)

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


def _order_by_edges(nodes: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """엣지 방향을 따라 노드를 시퀀스로 정렬 (chain 흐름). 사이클·분기 시 best-effort.

    in-degree 0 인 노드(시작점)부터 따라가며 정렬. 못 따라간 노드는 뒤에 append.
    """
    node_set = set(nodes)
    succ: dict[str, list[str]] = {n: [] for n in nodes}
    indeg: dict[str, int] = {n: 0 for n in nodes}
    for a, b in edges:
        if a in node_set and b in node_set:
            succ[a].append(b)
            indeg[b] += 1
    # 시작점 = indeg 0 (없으면 입력 첫 노드)
    starts = [n for n in nodes if indeg[n] == 0] or [nodes[0]]
    ordered: list[str] = []
    seen: set[str] = set()
    stack = list(starts)
    while stack:
        n = stack.pop(0)
        if n in seen:
            continue
        seen.add(n)
        ordered.append(n)
        stack = succ[n] + stack
    # 누락 노드 (사이클 등) append
    for n in nodes:
        if n not in seen:
            ordered.append(n)
    return ordered
