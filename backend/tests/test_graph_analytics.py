"""Phase J — Graph Data Science 단위 테스트 (2026-05-26, byungwoo).

검증:
    1. build_graph — 노드·엣지 직렬화 데이터 → DiGraph 변환
    2. page_rank — 합=1, 핵심 자산 강조
    3. page_rank_top_k — 상위 K개 정확도
    4. label_propagation_communities — 군집 식별
    5. analyze_board — 종합 분석 응답 무결성
"""
from __future__ import annotations

import math

import pytest

# networkx 미설치 환경 (CI 가벼운 deps) 에서는 graph_analytics 가 fallback(None) 으로
# 동작하므로 본 모듈 전체 skip. 로컬·실배포는 requirements.txt 의 networkx 설치됨.
pytest.importorskip("networkx")

from core.board.graph_analytics import (
    analyze_board,
    build_graph,
    label_propagation_communities,
    page_rank,
    page_rank_top_k,
)


# ─────────────────────────────────────────────────────────────
# 합성 그래프 — 공격 체인 예시
#
#   외부공격자 ──→ 계정A ──→ EC2 ──→ S3★ (← 핵심 표적)
#                  ↑
#                  └── 계정B (같은 IP 공유, 군집)
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def attack_chain_nodes() -> list[dict]:
    return [
        {"id": "attacker_ip", "label": "115.91.214.5", "type": "external_ip"},
        {"id": "account_a", "label": "user_A", "type": "account"},
        {"id": "account_b", "label": "user_B", "type": "account"},
        {"id": "ec2", "label": "EC2-instance", "type": "host"},
        {"id": "s3", "label": "secrets-bucket", "type": "storage"},
    ]


@pytest.fixture
def attack_chain_edges() -> list[dict]:
    return [
        {"src": "attacker_ip", "dst": "account_a", "kind": "compromise"},
        {"src": "attacker_ip", "dst": "account_b", "kind": "compromise"},
        {"src": "account_a", "dst": "ec2", "kind": "login"},
        {"src": "account_b", "dst": "ec2", "kind": "login"},
        {"src": "ec2", "dst": "s3", "kind": "access"},
        {"src": "account_a", "dst": "s3", "kind": "direct_access"},
    ]


# ─────────────────────────────────────────────────────────────
# 1. build_graph
# ─────────────────────────────────────────────────────────────


def test_build_graph_creates_directed(
    attack_chain_nodes, attack_chain_edges
) -> None:
    g = build_graph(attack_chain_nodes, attack_chain_edges)
    assert g is not None
    assert g.number_of_nodes() == 5
    assert g.number_of_edges() == 6
    assert g.is_directed()


def test_build_graph_preserves_node_metadata(
    attack_chain_nodes, attack_chain_edges
) -> None:
    g = build_graph(attack_chain_nodes, attack_chain_edges)
    assert g.nodes["s3"]["label"] == "secrets-bucket"
    assert g.nodes["s3"]["type"] == "storage"


def test_build_graph_skips_dangling_edges() -> None:
    nodes = [{"id": "a"}]
    edges = [{"src": "a", "dst": "z"}]  # z 존재 안함
    g = build_graph(nodes, edges)
    assert g.number_of_edges() == 0


def test_build_graph_empty_input() -> None:
    g = build_graph([], [])
    assert g is not None
    assert g.number_of_nodes() == 0


# ─────────────────────────────────────────────────────────────
# 2. PageRank
# ─────────────────────────────────────────────────────────────


def test_page_rank_sum_is_one(attack_chain_nodes, attack_chain_edges) -> None:
    g = build_graph(attack_chain_nodes, attack_chain_edges)
    ranks = page_rank(g)
    assert math.isclose(sum(ranks.values()), 1.0, abs_tol=1e-9)


def test_page_rank_central_target_wins(
    attack_chain_nodes, attack_chain_edges
) -> None:
    """수렴점 (S3) 이 가장 높은 PageRank — 핵심 표적 자동 식별."""
    g = build_graph(attack_chain_nodes, attack_chain_edges)
    ranks = page_rank(g)
    top = max(ranks.items(), key=lambda kv: kv[1])
    assert top[0] == "s3", f"S3 가 1위가 아님 (실제: {top})"


def test_page_rank_top_k_returns_sorted(
    attack_chain_nodes, attack_chain_edges
) -> None:
    g = build_graph(attack_chain_nodes, attack_chain_edges)
    top3 = page_rank_top_k(g, k=3)
    assert len(top3) == 3
    # 내림차순 정렬
    scores = [s for _, s in top3]
    assert scores == sorted(scores, reverse=True)


def test_page_rank_empty_graph_returns_empty() -> None:
    g = build_graph([], [])
    assert page_rank(g) == {}


# ─────────────────────────────────────────────────────────────
# 3. Label Propagation
# ─────────────────────────────────────────────────────────────


def test_label_propagation_finds_communities(
    attack_chain_nodes, attack_chain_edges
) -> None:
    """연결된 그래프 → 최소 1 군집."""
    g = build_graph(attack_chain_nodes, attack_chain_edges)
    communities = label_propagation_communities(g)
    assert len(communities) >= 1
    # 모든 노드가 어떤 군집에 속해야 함
    all_nodes = set()
    for c in communities:
        all_nodes.update(c)
    assert all_nodes == set(g.nodes())


def test_label_propagation_disconnected_two_components() -> None:
    """분리된 컴포넌트 2개 → 군집 2개 이상."""
    nodes = [
        {"id": "a"}, {"id": "b"},  # 컴포넌트 1
        {"id": "x"}, {"id": "y"},  # 컴포넌트 2 (분리)
    ]
    edges = [
        {"src": "a", "dst": "b"},
        {"src": "x", "dst": "y"},
    ]
    g = build_graph(nodes, edges)
    communities = label_propagation_communities(g)
    assert len(communities) >= 2


def test_label_propagation_empty_returns_empty() -> None:
    assert label_propagation_communities(build_graph([], [])) == []


# ─────────────────────────────────────────────────────────────
# 4. analyze_board — 종합 분석
# ─────────────────────────────────────────────────────────────


def test_analyze_board_returns_full_schema(
    attack_chain_nodes, attack_chain_edges
) -> None:
    result = analyze_board(attack_chain_nodes, attack_chain_edges)
    required = {"pagerank", "pagerank_top", "communities", "stats"}
    assert required.issubset(set(result.keys()))
    assert result["stats"]["nodes"] == 5
    assert result["stats"]["edges"] == 6
    assert result["stats"]["networkx_available"] is True


def test_analyze_board_pagerank_top_format(
    attack_chain_nodes, attack_chain_edges
) -> None:
    result = analyze_board(attack_chain_nodes, attack_chain_edges)
    top = result["pagerank_top"]
    assert len(top) == 3  # 기본 K=3
    for entry in top:
        assert "node_id" in entry
        assert "score" in entry
        assert 0 <= entry["score"] <= 1


def test_analyze_board_empty_graph() -> None:
    result = analyze_board([], [])
    assert result["stats"]["nodes"] == 0
    assert result["pagerank"] == {}
    assert result["communities"] == []


def test_analyze_board_deterministic(
    attack_chain_nodes, attack_chain_edges
) -> None:
    """같은 입력 → 같은 PageRank (결정성 100%)."""
    a = analyze_board(attack_chain_nodes, attack_chain_edges)
    b = analyze_board(attack_chain_nodes, attack_chain_edges)
    for nid in a["pagerank"]:
        assert math.isclose(a["pagerank"][nid], b["pagerank"][nid], abs_tol=1e-9)
