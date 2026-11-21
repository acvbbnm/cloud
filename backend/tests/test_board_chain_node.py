"""Phase O.2 — ChainNode 도메인 단위 테스트 (2026-05-26, byungwoo).

paradigm doc §24 Phase O — Evidence Board 통합.

검증:
    1. ATT&CK 노드 생성 — meta=None (legacy 호환)
    2. 단서 노드 생성 — build_clue_meta + meta 저장
    3. serialize — type 추론 (clue vs attack) + meta 동봉
    4. derive_label_from_clue — clue_catalog short_label 추출
    5. derive_label_from_clue — 카탈로그 없는 키는 fallback (clue_key 그대로)
    6. ChainNode.update — meta shallow merge
    7. build_clue_meta — 표준 필드 (type/clue_key/stage/source) 강제
    8. build_clue_meta — extra 병합 + hypothesis 옵션
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.board.chain import ChainNode
from db.models import Base, IncidentCaseModel


# ─────────────────────────────────────────────────────────────
# Fixtures — in-memory SQLite
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
    """샘플 케이스 1건 — O.2 노드 생성 테스트용."""
    c = IncidentCaseModel(
        case_id="case-o2-test-001",
        title="O.2 chain node test",
        csp="naver",
        incident_type="UNCLASSIFIED",
        severity="medium",
        occurred_at=datetime.utcnow(),
        triage_state=None,
    )
    db_session.add(c)
    db_session.commit()
    return c


# ─────────────────────────────────────────────────────────────
# 1. ATT&CK 노드 — legacy 호환
# ─────────────────────────────────────────────────────────────


def test_attack_node_create_meta_none(db_session, case) -> None:
    """기존 ATT&CK 노드 — meta=None 으로 생성 (legacy 호환)."""
    node = ChainNode.create(
        db_session,
        case_id=case.case_id,
        label="T1078 · Initial Access",
        attack_id=None,
    )
    assert node.meta is None
    ser = ChainNode.serialize(node)
    assert ser["type"] == "attack"
    assert "meta" not in ser  # meta None 시 응답에서 생략


# ─────────────────────────────────────────────────────────────
# 2. 단서 노드 — Phase O 통합
# ─────────────────────────────────────────────────────────────


def test_clue_node_create_with_build_clue_meta(db_session, case) -> None:
    """Phase O — 단서 노드 (type='clue') + meta 저장."""
    meta = ChainNode.build_clue_meta(
        clue_key="Q1_inception:csp_alert",
        stage=1,
        hypothesis="CREDENTIAL_THEFT",
        source="manual_drag",
    )
    node = ChainNode.create(
        db_session,
        case_id=case.case_id,
        label="CSP 자체 알람",
        attack_id=None,
        meta=meta,
    )
    assert node.meta == meta
    ser = ChainNode.serialize(node)
    assert ser["type"] == "clue"
    assert ser["meta"]["clue_key"] == "Q1_inception:csp_alert"
    assert ser["meta"]["stage"] == 1
    assert ser["meta"]["hypothesis"] == "CREDENTIAL_THEFT"
    assert ser["meta"]["source"] == "manual_drag"


# ─────────────────────────────────────────────────────────────
# 3. derive_label_from_clue — 카탈로그 우선
# ─────────────────────────────────────────────────────────────


def test_derive_label_from_clue_known_key() -> None:
    """clue_catalog 등록 키는 short_label 추출."""
    label = ChainNode.derive_label_from_clue("Q1_inception:csp_alert")
    assert label is not None
    assert "CSP" in label or "알람" in label  # short_label 정합


def test_derive_label_from_clue_unknown_key() -> None:
    """카탈로그 미등록 키는 clue_key 그대로 fallback (시연 안전)."""
    label = ChainNode.derive_label_from_clue("__nonexistent_clue__")
    assert label == "__nonexistent_clue__"


def test_derive_label_from_clue_none() -> None:
    """None 입력 → None 반환."""
    assert ChainNode.derive_label_from_clue(None) is None
    assert ChainNode.derive_label_from_clue("") is None


# ─────────────────────────────────────────────────────────────
# 4. update — meta shallow merge
# ─────────────────────────────────────────────────────────────


def test_update_node_meta_merges_shallow(db_session, case) -> None:
    """ChainNode.update(meta=...) 은 기존 meta 와 shallow merge.

    Phase O 보드 UX — 단서 노드 라벨 수정·anchor 가설 갱신 시 활용.
    """
    initial_meta = ChainNode.build_clue_meta(
        clue_key="Q1_inception:csp_alert", stage=1
    )
    node = ChainNode.create(
        db_session,
        case_id=case.case_id,
        label="CSP 알람",
        meta=initial_meta,
    )

    updated = ChainNode.update(
        db_session,
        node_id=node.node_id,
        meta={"hypothesis": "PHISH_INITIAL_ACCESS", "note": "user added later"},
    )
    assert updated is not None
    # 기존 키 유지 + 새 키 병합
    assert updated.meta["type"] == "clue"
    assert updated.meta["clue_key"] == "Q1_inception:csp_alert"
    assert updated.meta["stage"] == 1
    assert updated.meta["hypothesis"] == "PHISH_INITIAL_ACCESS"
    assert updated.meta["note"] == "user added later"


# ─────────────────────────────────────────────────────────────
# 5. build_clue_meta — 표준 필드 강제
# ─────────────────────────────────────────────────────────────


def test_build_clue_meta_required_fields() -> None:
    """build_clue_meta 결과는 type/clue_key/stage/source 항상 포함."""
    meta = ChainNode.build_clue_meta("Q1_inception:audit")
    assert meta["type"] == "clue"
    assert meta["clue_key"] == "Q1_inception:audit"
    assert meta["stage"] == 1  # default
    assert meta["source"] == "manual_drag"  # default
    assert "hypothesis" not in meta  # 옵션 미지정 시 키 없음


def test_build_clue_meta_extra_merge() -> None:
    """extra dict 은 표준 필드 위에 병합 — 단, type 등 핵심 키는 표준이 우선."""
    meta = ChainNode.build_clue_meta(
        clue_key="ACCOUNT:csp_admin",
        stage=2,
        hypothesis="PRIVILEGE_ESCALATION",
        source="auto_seed",
        extra={"confidence": 0.8, "tag": "anchor"},
    )
    assert meta["stage"] == 2
    assert meta["hypothesis"] == "PRIVILEGE_ESCALATION"
    assert meta["source"] == "auto_seed"
    assert meta["confidence"] == 0.8
    assert meta["tag"] == "anchor"
