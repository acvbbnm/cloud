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


def auto_layout_positions(
    node_ids: list[str],
    edges: list[tuple[str, str]],
    *,
    canvas_w: int = 900,
    canvas_h: int = 520,
    pad: int = 60,
) -> dict[str, tuple[int, int]]:
    """V-5 자동 정렬 — networkx spring_layout 결과를 canvas 좌표로 매핑.

    Returns:
        {node_id: (x, y)} — V-5 캔버스 픽셀 좌표 (좌상단 0,0 기준).

    동작:
        - networkx 미설치 → 격자 fallback (5열 그리드)
        - 노드 1개 → 캔버스 중앙
        - spring_layout 결정성 위해 seed=42 고정
    """
    if not node_ids:
        return {}

    if not _NETWORKX_AVAILABLE or len(node_ids) == 1:
        # fallback — 격자 배치 (cols=5)
        cols = 5
        cell_w = (canvas_w - 2 * pad) / max(cols, 1)
        cell_h = 110
        out: dict[str, tuple[int, int]] = {}
        for i, nid in enumerate(node_ids):
            r, c = divmod(i, cols)
            out[nid] = (int(pad + c * cell_w), int(pad + r * cell_h))
        return out

    g = nx.Graph()
    g.add_nodes_from(node_ids)
    g.add_edges_from(edges)

    # spring_layout — k 는 노드 간 최소 거리, iterations 는 수렴 횟수
    pos = nx.spring_layout(g, seed=42, k=0.6, iterations=80)

    # [-1, 1] → 캔버스 좌표
    out = {}
    for nid in node_ids:
        x, y = pos.get(nid, (0, 0))
        cx = int(pad + (x + 1) / 2 * (canvas_w - 2 * pad))
        cy = int(pad + (y + 1) / 2 * (canvas_h - 2 * pad))
        out[nid] = (cx, cy)
    return out
