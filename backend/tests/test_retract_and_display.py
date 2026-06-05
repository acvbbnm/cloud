"""단서 철회(retract_clue) + V-2 표시필드(extract_display_fields) 회귀 테스트.

2026-06-05 — dev3 머지로 들어온 신규 기능 2종이 테스트 0개로 합류되어 추가.

검증:
  retract_clue
    1. 선형 트리 중간 단서 철회 → 해당 단서만 제거, 나머지 순서 보존
    2. 마지막 단서 철회 → root 만 남음
    3. 결정성 — retract(c2) 후 posterior == [c1,c3] 순차 채택 posterior
    4. root / 미존재 노드 → ValueError
    5. 가드: 다단계(advance_stage 후) → ValueError (조용한 stage 소실 방지)
    6. 가드: 분기 트리 → ValueError (조용한 off-path 단서 유실 방지)
  extract_display_fields
    7. NHN 포맷 (eventId/userIp/userName, +0900 → UTC)
    8. NHN userId fallback
    9. NCP 포맷 (action/content.sourceIp/content.actionUserName)
   10. NCP 최상위 fallback (content 없음)
   11. None / 비-dict → 전부 None
   12. 파싱 불가 eventTime → 원본 문자열 fallback
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ingestion.log_ingestor import LogIngestor
from core.intake.clue_tree import path_from_root
from core.intake.clue_tree_service import (
    _load_tree_from_case,  # type: ignore
    advance_stage,
    expand_tree,
    retract_clue,
    start_tree,
)
from db.models import Base, IncidentCaseModel

KEYS = ["IP_ADDRESS:tor_vpn", "Q2A:privilege_change", "Q2A:object_storage_burst"]


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


def _new_case(db, case_id: str) -> IncidentCaseModel:
    c = IncidentCaseModel(
        case_id=case_id,
        title="retract/display test",
        csp="naver",
        incident_type="UNCLASSIFIED",
        severity="medium",
        occurred_at=datetime.utcnow(),
        triage_state=None,
    )
    db.add(c)
    db.commit()
    return c


@pytest.fixture
def case(db_session):
    return _new_case(db_session, "case-retract-001")


def _leaf(db, case_id: str) -> str:
    c = db.get(IncidentCaseModel, case_id)
    return c.triage_state["evidence_tree"]["current_leaf_id"]


def _adopt(db, case_id: str, key: str) -> dict:
    return expand_tree(db, case_id, _leaf(db, case_id), key)


def _node_id_for(db, case_id: str, clue_key: str) -> str:
    c = db.get(IncidentCaseModel, case_id)
    tree = _load_tree_from_case(c)
    return next(n.node_id for n in path_from_root(tree) if n.clue_key == clue_key)


# ─────────────────────────────────────────────────────────────
# retract_clue — 정상 동작
# ─────────────────────────────────────────────────────────────
def test_retract_middle_keeps_others_in_order(db_session, case):
    start_tree(db_session, case.case_id)
    for k in KEYS:
        _adopt(db_session, case.case_id, k)

    mid = _node_id_for(db_session, case.case_id, KEYS[1])
    data = retract_clue(db_session, case.case_id, mid)
    after = [p["clue_key"] for p in data["path"]]
    assert after == ["__ROOT__", KEYS[0], KEYS[2]]


def test_retract_last_clue_leaves_root(db_session, case):
    start_tree(db_session, case.case_id)
    _adopt(db_session, case.case_id, KEYS[0])
    only = _node_id_for(db_session, case.case_id, KEYS[0])
    data = retract_clue(db_session, case.case_id, only)
    assert [p["clue_key"] for p in data["path"]] == ["__ROOT__"]


def test_retract_is_deterministic(db_session, case):
    """retract(c2) 후 posterior == [c1,c3] 만 순차 채택한 posterior (결정성 §17)."""
    start_tree(db_session, case.case_id)
    for k in KEYS:
        _adopt(db_session, case.case_id, k)
    mid = _node_id_for(db_session, case.case_id, KEYS[1])
    a = retract_clue(db_session, case.case_id, mid)

    ref = _new_case(db_session, "case-retract-ref")
    start_tree(db_session, ref.case_id)
    _adopt(db_session, ref.case_id, KEYS[0])
    b = _adopt(db_session, ref.case_id, KEYS[2])

    assert a["posterior_current"] == b["posterior_current"]


def test_retract_root_rejected(db_session, case):
    d = start_tree(db_session, case.case_id)
    with pytest.raises(ValueError):
        retract_clue(db_session, case.case_id, d["current_leaf_id"])


def test_retract_unknown_node_rejected(db_session, case):
    start_tree(db_session, case.case_id)
    with pytest.raises(ValueError):
        retract_clue(db_session, case.case_id, "no-such-node")


# ─────────────────────────────────────────────────────────────
# retract_clue — 가드 (2026-06-05)
# ─────────────────────────────────────────────────────────────
def test_retract_blocked_in_multistage(db_session, case):
    """advance_stage 후엔 개별 철회 거부 — replay 가 stage 구조를 소실시키므로."""
    start_tree(db_session, case.case_id)
    _adopt(db_session, case.case_id, KEYS[0])
    target = _node_id_for(db_session, case.case_id, KEYS[0])
    advance_stage(db_session, case.case_id, "CREDENTIAL_THEFT")
    with pytest.raises(ValueError, match="다단계"):
        retract_clue(db_session, case.case_id, target)


def test_retract_blocked_in_branched_tree(db_session, case):
    """분기 트리(한 부모에 자식 2개)는 철회 거부 — path_from_root 누락 방지."""
    d = start_tree(db_session, case.case_id)
    root_id = d["current_leaf_id"]
    # 두 단서를 모두 root 의 자식으로 채택 → 분기 발생
    expand_tree(db_session, case.case_id, root_id, KEYS[0])
    expand_tree(db_session, case.case_id, root_id, KEYS[1])

    c = db_session.get(IncidentCaseModel, case.case_id)
    tree = _load_tree_from_case(c)
    assert len(tree.nodes) == 3  # root + 2 자식 (분기 확인)
    assert len(path_from_root(tree)) < len(tree.nodes)

    any_clue = next(
        n.node_id for n in tree.nodes.values() if n.clue_key != "__ROOT__"
    )
    with pytest.raises(ValueError, match="분기"):
        retract_clue(db_session, case.case_id, any_clue)


# ─────────────────────────────────────────────────────────────
# extract_display_fields
# ─────────────────────────────────────────────────────────────
def test_display_nhn():
    raw = {
        "eventTime": "2024-12-30T14:23:01.123+0900",
        "eventId": "event_id.iam.login",
        "userIp": "203.0.113.5",
        "userName": "alice",
        "userId": "alice@corp.com",
    }
    d = LogIngestor.extract_display_fields("nhn", raw)
    assert d["event_name"] == "event_id.iam.login"
    assert d["source_ip"] == "203.0.113.5"
    assert d["user"] == "alice"
    assert d["time"].startswith("2024-12-30T05:23:01")  # +0900 → UTC


def test_display_nhn_userid_fallback():
    raw = {"userId": "bob@corp.com", "userIp": "1.1.1.1", "eventId": "x"}
    d = LogIngestor.extract_display_fields("nhn", raw)
    assert d["user"] == "bob@corp.com"


def test_display_ncp_content():
    raw = {
        "eventTime": "2024-12-30 14:23:01 UTC",
        "action": "CreateAccessKey",
        "content": {"sourceIp": "9.9.9.9", "actionUserName": "carol"},
    }
    d = LogIngestor.extract_display_fields("naver", raw)
    assert d["event_name"] == "CreateAccessKey"
    assert d["source_ip"] == "9.9.9.9"
    assert d["user"] == "carol"
    assert d["time"].startswith("2024-12-30T14:23:01")


def test_display_ncp_toplevel_fallback():
    raw = {"action": "X", "sourceIp": "2.2.2.2", "actionUserName": "dave"}
    d = LogIngestor.extract_display_fields("naver", raw)
    assert d["source_ip"] == "2.2.2.2"
    assert d["user"] == "dave"


def test_display_none_and_nondict():
    empty = {"time": None, "event_name": None, "source_ip": None, "user": None}
    assert LogIngestor.extract_display_fields("nhn", None) == empty
    assert LogIngestor.extract_display_fields("naver", "not-a-dict") == empty


def test_display_unparseable_time_keeps_raw_string():
    raw = {"eventTime": "garbage", "action": "X"}
    d = LogIngestor.extract_display_fields("naver", raw)
    assert d["time"] == "garbage"
