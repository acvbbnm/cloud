"""Phase O.3 — Evidence Tree → 보드 bridge 통합 테스트 (2026-05-26, byungwoo).

paradigm doc §24 Phase O — Evidence Board 통합.

검증:
    1. 빈 tree → 빈 결과 (path 없음)
    2. 정상 path → type='clue' 노드 일괄 생성 + meta 4필드 정상
    3. 멱등성 — 두 번 호출 시 두 번째는 모두 skipped
    4. include_root=True 일 때 __ROOT__ 도 포함 (기본 False)
    5. include_edges=True → path 인접 엣지 자동 생성 (n-1 개)
    6. node_ids 부분 이관 — 지정된 tree node 만 생성
    7. anchor 가설 — confirmed_hypotheses[-1] 이 meta.hypothesis 로 반영
    8. 좌표 — 기존 보드 노드 max(pos_x) 우측에서 시작
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.board.chain import ChainNode
from core.board.clue_bridge import (
    BRIDGE_FALLBACK_X,
    BRIDGE_X_STEP,
    bridge_clue_tree_to_board,
)
from core.intake.clue_tree import ClueTree, ClueTreeNode
from db.models import Base, IncidentCaseModel


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


@pytest.fixture
def case(db_session):
    c = IncidentCaseModel(
        case_id="case-o3-bridge-001",
        title="O.3 bridge",
        csp="naver",
        incident_type="UNCLASSIFIED",
        severity="medium",
        occurred_at=datetime.utcnow(),
        triage_state=None,
    )
    db_session.add(c)
    db_session.commit()
    return c


def _make_tree_with_path(case_id: str, stage: int = 1) -> ClueTree:
    """3개 단서 path 가 있는 ClueTree 합성: __ROOT__ → A → B → C."""
    root = ClueTreeNode(
        node_id="root",
        parent_id=None,
        depth=0,
        clue_key="__ROOT__",
        category="",
        value="",
        label="root",
        source="cold_start",
    )
    n1 = ClueTreeNode(
        node_id="n1",
        parent_id="root",
        depth=1,
        clue_key="Q1_inception:csp_alert",
        category="Q1_inception",
        value="csp_alert",
        label="CSP 자체 알람",
        source="tree_candidate",
    )
    n2 = ClueTreeNode(
        node_id="n2",
        parent_id="n1",
        depth=2,
        clue_key="IP_ADDRESS:tor_vpn",
        category="IP_ADDRESS",
        value="tor_vpn",
        label="Tor/VPN 출처 IP",
        source="tree_candidate",
    )
    n3 = ClueTreeNode(
        node_id="n3",
        parent_id="n2",
        depth=3,
        clue_key="ACCOUNT:csp_admin",
        category="ACCOUNT",
        value="csp_admin",
        label="CSP Admin 계정",
        source="direct_input",
    )
    tree = ClueTree(
        case_id=case_id,
        root_id="root",
        nodes={"root": root, "n1": n1, "n2": n2, "n3": n3},
        current_leaf_id="n3",
        posterior_current={"CREDENTIAL_THEFT": 0.5, "PRIVILEGE_ESCALATION": 0.3},
        confidence_reached=False,
        stage=stage,
        confirmed_hypotheses=["CREDENTIAL_THEFT"] if stage >= 2 else [],
    )
    return tree


# ─────────────────────────────────────────────────────────────
# 1. 빈 tree
# ─────────────────────────────────────────────────────────────


def test_bridge_empty_tree(db_session, case) -> None:
    """채택 단서 없는 (root only) tree → 생성 0건, skip 0건."""
    root = ClueTreeNode(
        node_id="root",
        parent_id=None,
        depth=0,
        clue_key="__ROOT__",
        category="",
        value="",
        label="root",
        source="cold_start",
    )
    tree = ClueTree(
        case_id=case.case_id,
        root_id="root",
        nodes={"root": root},
        current_leaf_id="root",
    )
    result = bridge_clue_tree_to_board(db_session, case.case_id, tree)
    assert result["created_nodes"] == []
    assert result["skipped"] == []
    assert result["created_edges"] == []


# ─────────────────────────────────────────────────────────────
# 2. 정상 path → 3 단서 → 3 노드
# ─────────────────────────────────────────────────────────────


def test_bridge_creates_clue_nodes(db_session, case) -> None:
    tree = _make_tree_with_path(case.case_id, stage=2)
    result = bridge_clue_tree_to_board(db_session, case.case_id, tree)

    assert len(result["created_nodes"]) == 3
    assert result["skipped"] == []
    assert result["created_edges"] == []

    # 모두 type='clue' + meta 정상
    for serial in result["created_nodes"]:
        assert serial["type"] == "clue"
        assert serial["meta"]["type"] == "clue"
        assert serial["meta"]["stage"] == 2
        assert serial["meta"]["hypothesis"] == "CREDENTIAL_THEFT"  # anchor
        assert serial["meta"]["source"] == "manual_bulk"
        assert "tree_node_id" in serial["meta"]
        assert "tree_depth" in serial["meta"]

    # clue_key 순서 보존
    keys = [n["meta"]["clue_key"] for n in result["created_nodes"]]
    assert keys == [
        "Q1_inception:csp_alert",
        "IP_ADDRESS:tor_vpn",
        "ACCOUNT:csp_admin",
    ]


# ─────────────────────────────────────────────────────────────
# 3. 멱등성
# ─────────────────────────────────────────────────────────────


def test_bridge_is_idempotent(db_session, case) -> None:
    """같은 tree 두 번 bridge → 두 번째는 모두 skipped."""
    tree = _make_tree_with_path(case.case_id)
    first = bridge_clue_tree_to_board(db_session, case.case_id, tree)
    assert len(first["created_nodes"]) == 3

    second = bridge_clue_tree_to_board(db_session, case.case_id, tree)
    assert len(second["created_nodes"]) == 0
    assert len(second["skipped"]) == 3
    for skip in second["skipped"]:
        assert skip["reason"] == "already_on_board"


# ─────────────────────────────────────────────────────────────
# 4. include_root
# ─────────────────────────────────────────────────────────────


def test_bridge_excludes_root_by_default(db_session, case) -> None:
    tree = _make_tree_with_path(case.case_id)
    result = bridge_clue_tree_to_board(db_session, case.case_id, tree)
    keys = [n["meta"]["clue_key"] for n in result["created_nodes"]]
    assert "__ROOT__" not in keys


def test_bridge_includes_root_when_flag(db_session, case) -> None:
    tree = _make_tree_with_path(case.case_id)
    result = bridge_clue_tree_to_board(
        db_session, case.case_id, tree, include_root=True
    )
    keys = [n["meta"]["clue_key"] for n in result["created_nodes"]]
    assert "__ROOT__" in keys
    assert len(result["created_nodes"]) == 4


# ─────────────────────────────────────────────────────────────
# 5. include_edges
# ─────────────────────────────────────────────────────────────


def test_bridge_creates_sequence_edges(db_session, case) -> None:
    """3 노드 + include_edges → 2 엣지 (인접쌍)."""
    tree = _make_tree_with_path(case.case_id)
    result = bridge_clue_tree_to_board(
        db_session, case.case_id, tree, include_edges=True
    )
    assert len(result["created_nodes"]) == 3
    assert len(result["created_edges"]) == 2

    # 엣지 방향 검증 — node[0] → node[1] → node[2]
    node_ids = [n["node_id"] for n in result["created_nodes"]]
    edges = result["created_edges"]
    assert edges[0]["from_node_id"] == node_ids[0]
    assert edges[0]["to_node_id"] == node_ids[1]
    assert edges[1]["from_node_id"] == node_ids[1]
    assert edges[1]["to_node_id"] == node_ids[2]


# ─────────────────────────────────────────────────────────────
# 6. node_ids 부분 이관
# ─────────────────────────────────────────────────────────────


def test_bridge_partial_with_node_ids(db_session, case) -> None:
    tree = _make_tree_with_path(case.case_id)
    result = bridge_clue_tree_to_board(
        db_session, case.case_id, tree, node_ids=["n2"]
    )
    assert len(result["created_nodes"]) == 1
    assert result["created_nodes"][0]["meta"]["clue_key"] == "IP_ADDRESS:tor_vpn"


# ─────────────────────────────────────────────────────────────
# 7. anchor 가설 (확정 없을 시 None)
# ─────────────────────────────────────────────────────────────


def test_bridge_no_anchor_hypothesis_when_unconfirmed(db_session, case) -> None:
    tree = _make_tree_with_path(case.case_id, stage=1)  # confirmed = []
    result = bridge_clue_tree_to_board(db_session, case.case_id, tree)
    for serial in result["created_nodes"]:
        # hypothesis 키 자체가 없거나, None
        assert serial["meta"].get("hypothesis") is None


# ─────────────────────────────────────────────────────────────
# 8. 좌표 — 기존 노드 우측에서 시작
# ─────────────────────────────────────────────────────────────


def test_bridge_x_starts_right_of_existing(db_session, case) -> None:
    """기존 노드가 있을 때 신규 노드들이 그것과 겹치지 않음 (V-5 격자 회피).

    2026-05-31 — 옛 동작 (기존 노드 우측에서 시작) 에서 격자 + 충돌 회피로 변경.
    핵심 보장은 동일: 신규 노드가 기존 노드와 겹치지 않음.
    """
    # 기존 노드 1개 (pos_x=500, pos_y=100)
    ChainNode.create(
        db_session,
        case_id=case.case_id,
        label="Pre-existing",
        attack_id=None,
        pos_x=500,
        pos_y=100,
    )

    tree = _make_tree_with_path(case.case_id)
    result = bridge_clue_tree_to_board(db_session, case.case_id, tree)

    # 모든 신규 노드가 기존 노드 (500, 100) 와 겹치지 않아야 함 (200×95 셀 기준)
    for n in result["created_nodes"]:
        dx = abs(n["pos_x"] - 500)
        dy = abs(n["pos_y"] - 100)
        assert dx >= 200 or dy >= 95, (
            f"신규 노드 ({n['pos_x']},{n['pos_y']}) 가 기존 (500,100) 과 겹침"
        )

    # 신규 노드 끼리도 겹치지 않음
    coords = [(n["pos_x"], n["pos_y"]) for n in result["created_nodes"]]
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            dx = abs(coords[i][0] - coords[j][0])
            dy = abs(coords[i][1] - coords[j][1])
            assert dx >= 200 or dy >= 95, (
                f"신규 노드 끼리 겹침: {coords[i]} ↔ {coords[j]}"
            )


def test_bridge_x_fallback_when_no_existing(db_session, case) -> None:
    """기존 노드 0건이면 BRIDGE_FALLBACK_X 부터."""
    tree = _make_tree_with_path(case.case_id)
    result = bridge_clue_tree_to_board(db_session, case.case_id, tree)
    xs = [n["pos_x"] for n in result["created_nodes"]]
    assert xs[0] == BRIDGE_FALLBACK_X
