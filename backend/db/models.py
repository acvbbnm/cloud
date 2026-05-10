"""SQLAlchemy 모델 — 9개 테이블 정의.

⚠ 이 파일은 DB 담당자(이근형)만 수정한다.
  스키마 변경은 팀 합의 후 진행할 것.

설계서 참조: 5.1절 ERD + 5.2절 테이블 명세
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Boolean,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


# ── 테이블 1: 사고 케이스 ──
class IncidentCaseModel(Base):
    """사고 케이스 메타데이터."""

    __tablename__ = "incident_cases"

    case_id = Column(String(36), primary_key=True, default=_uuid)
    incident_type = Column(String(32), nullable=False)  # 5종 enum
    csp = Column(String(16), nullable=False)  # naver/nhn/all
    severity = Column(String(8), nullable=False)  # critical/high/medium/low
    occurred_at = Column(DateTime, nullable=False)
    system_config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)


# ── 테이블 2: 수집 대상 카탈로그 (지식베이스, 읽기 전용) ──
class CollectionTargetModel(Base):
    """수집 대상 카탈로그 — 시드 데이터로 초기화."""

    __tablename__ = "collection_targets"

    target_id = Column(String(36), primary_key=True)
    incident_type = Column(String(32), nullable=False)
    csp = Column(String(16), nullable=False)
    log_type = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    evidence_role = Column(String(16), nullable=False)  # REQUIRED/CORROBORATING
    priority = Column(Integer, nullable=False, default=5)  # 1~10


# ── 테이블 3: 원본 로그 이벤트 ──
class RawEventModel(Base):
    """원본 로그 이벤트 + SHA-256 해시."""

    __tablename__ = "raw_events"

    event_id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("incident_cases.case_id"), nullable=False)
    csp = Column(String(16), nullable=False)
    event_time = Column(DateTime, nullable=True)
    event_name = Column(String(128), nullable=True)
    source_file = Column(String(256), nullable=False)
    matched_target_id = Column(
        String(36), ForeignKey("collection_targets.target_id"), nullable=True
    )
    sha256_hash = Column(String(64), nullable=False)
    raw_json = Column(Text, nullable=False)  # 원본 전체 보존
    created_at = Column(DateTime, default=datetime.utcnow)


# ── 테이블 4: OCSF 정규화 이벤트 ──
class OCSFEventModel(Base):
    """OCSF 정규화 이벤트."""

    __tablename__ = "ocsf_events"

    ocsf_id = Column(String(36), primary_key=True, default=_uuid)
    event_id = Column(
        String(36), ForeignKey("raw_events.event_id"), nullable=False, unique=True
    )
    class_uid = Column(Integer, nullable=True)
    category_uid = Column(Integer, nullable=True)
    activity_id = Column(Integer, nullable=True)
    activity_name = Column(String(128), nullable=True)
    time = Column(Float, nullable=True)  # Unix timestamp
    actor = Column(JSON, nullable=True)
    src_endpoint = Column(JSON, nullable=True)
    status_code = Column(String(32), nullable=True)
    severity_id = Column(Integer, nullable=True)
    unmapped = Column(JSON, nullable=True)  # 매핑 안 된 원본 필드 보존
    created_at = Column(DateTime, default=datetime.utcnow)


# ── 테이블 5: ATT&CK 매핑 결과 ──
class AttackEventModel(Base):
    """ATT&CK 매핑 결과."""

    __tablename__ = "attack_events"

    attack_id = Column(String(36), primary_key=True, default=_uuid)
    ocsf_id = Column(
        String(36), ForeignKey("ocsf_events.ocsf_id"), nullable=False
    )
    technique_id = Column(String(16), nullable=False)  # T1078.004
    technique_name = Column(String(128), nullable=True)
    tactic = Column(String(64), nullable=True)
    rule_id = Column(String(16), nullable=True)
    risk_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── 테이블 6: 갭 판정 결과 ──
class GapResultModel(Base):
    """갭 감지 결과."""

    __tablename__ = "gap_results"

    gap_id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("incident_cases.case_id"), nullable=False)
    gap_type = Column(String(16), nullable=False)  # NONE/COLLECTION/EVIDENCE/INTERPRETATION
    missing = Column(JSON, nullable=True)  # 미수집 target 목록
    summary = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    completion_rate = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── 테이블 7: 공격 체인 노드 ──
class ChainNodeModel(Base):
    """수사 보드 — 공격 체인 노드."""

    __tablename__ = "chain_nodes"

    node_id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("incident_cases.case_id"), nullable=False)
    attack_id = Column(
        String(36), ForeignKey("attack_events.attack_id"), nullable=True
    )
    label = Column(String(256), nullable=True)
    status = Column(String(16), nullable=False, default="CONFIRMED")  # CONFIRMED/REJECTED
    is_ai_suggested = Column(Boolean, default=False)
    pos_x = Column(Float, default=0)
    pos_y = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── 테이블 8: 체인 엣지 ──
class ChainEdgeModel(Base):
    """수사 보드 — 방향성 엣지."""

    __tablename__ = "chain_edges"

    edge_id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("incident_cases.case_id"), nullable=False)
    from_node_id = Column(
        String(36), ForeignKey("chain_nodes.node_id"), nullable=False
    )
    to_node_id = Column(
        String(36), ForeignKey("chain_nodes.node_id"), nullable=False
    )
    label = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── 테이블 9: 수사관 조작 이력 ──
class ActionLogModel(Base):
    """감사 추적 — 수사관 모든 조작 기록."""

    __tablename__ = "action_logs"

    log_id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("incident_cases.case_id"), nullable=False)
    action = Column(String(32), nullable=False)  # ACCEPT/REJECT/EDIT_REPORT/...
    target_type = Column(String(32), nullable=True)  # chain_node, report, etc.
    target_id = Column(String(36), nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
