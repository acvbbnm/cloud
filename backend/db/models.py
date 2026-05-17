"""SQLAlchemy 모델 — 9개 테이블 정의.

⚠ 이 파일은 DB 담당자(이근형·최진규)만 수정한다.
  스키마 변경은 팀 합의 후 진행할 것.

설계서 참조: 5.1절 ERD + 5.2절 테이블 명세 (Table 43~51)
정렬 기준: 2026-05-11 — 설계서 5.2절 컬럼명/타입/제약 100% 일치
  · chain_nodes.label 은 보드 UI 표시용으로 팀 합의 추가 (설계서 8컬럼 + label)
  · 그 외 모든 컬럼은 설계서 명세를 따른다
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


# ── 테이블 1: 사고 케이스 (설계서 Table 43, 8컬럼) ──
class IncidentCaseModel(Base):
    """사고 케이스 메타데이터."""

    __tablename__ = "incident_cases"

    case_id = Column(String(36), primary_key=True, default=_uuid)
    incident_type = Column(String(32), nullable=False)  # 5종 enum (설계 비고 "6종" — 확정 필요)
    csp = Column(String(16), nullable=False)  # naver/nhn/all
    severity = Column(String(8), nullable=False)  # critical/high/medium/low
    occurred_at = Column(DateTime, nullable=False)
    system_config = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)


# ── 테이블 2: 수집 대상 카탈로그 (설계서 Table 44, 9컬럼) ──
class CollectionTargetModel(Base):
    """수집 대상 카탈로그 — 시드 데이터로 초기화."""

    __tablename__ = "collection_targets"

    target_id = Column(String(36), primary_key=True)
    incident_type = Column(String(32), nullable=False, index=True)
    csp = Column(String(16), nullable=False, index=True)
    log_type = Column(String(64), nullable=False)  # 예: Activity Tracer
    evidence_role = Column(String(16), nullable=False)  # REQUIRED/CORROBORATING
    storage_path = Column(String(255), nullable=True)
    retention_days = Column(Integer, nullable=True)
    priority = Column(Integer, nullable=False, default=5)  # 1~10
    description = Column(Text, nullable=True)


# ── 테이블 3: 원본 로그 이벤트 (설계서 Table 45, 8컬럼) ──
class RawEventModel(Base):
    """원본 로그 이벤트 + SHA-256 해시."""

    __tablename__ = "raw_events"

    event_id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("incident_cases.case_id"), nullable=False)
    csp = Column(String(16), nullable=False, index=True)
    raw_json = Column(Text, nullable=False)
    sha256 = Column(CHAR(64), nullable=False, index=True)  # 무결성 검증
    matched_target_id = Column(
        String(36), ForeignKey("collection_targets.target_id"), nullable=True
    )
    ingested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    source_file = Column(String(255), nullable=True)


# ── 테이블 4: OCSF 정규화 이벤트 (설계서 Table 46, 8컬럼) ──
class OCSFEventModel(Base):
    """OCSF 정규화 이벤트 — 평탄화된 검색 인덱스 컬럼.

    OCSF 전체 객체(nested actor, src_endpoint 등)는 unmapped_raw에 보관한다.
    """

    __tablename__ = "ocsf_events"

    ocsf_id = Column(String(36), primary_key=True, default=_uuid)
    event_id = Column(
        String(36), ForeignKey("raw_events.event_id"), nullable=False, unique=True
    )
    time = Column(DateTime, nullable=False, index=True)
    actor_user_name = Column(String(64), nullable=True, index=True)
    src_endpoint_ip = Column(String(45), nullable=True, index=True)  # IPv4/IPv6
    activity_name = Column(String(128), nullable=False, index=True)
    status_code = Column(Integer, nullable=True)
    unmapped_raw = Column(JSON, nullable=True)  # OCSF 풀 객체 + 매핑 안 된 원본


# ── 테이블 5: ATT&CK 매핑 결과 (설계서 Table 47, 7컬럼) ──
class AttackEventModel(Base):
    """ATT&CK 매핑 결과."""

    __tablename__ = "attack_events"

    attack_id = Column(String(36), primary_key=True, default=_uuid)
    ocsf_id = Column(
        String(36),
        ForeignKey("ocsf_events.ocsf_id"),
        nullable=False,
        unique=True,
    )
    technique_id = Column(String(16), nullable=False, index=True)  # T1078.004
    tactic = Column(String(32), nullable=False, index=True)
    rule_id = Column(String(36), nullable=False)  # 매핑 규칙 출처
    # risk_score 제거 (산출 근거 부재 / 학술 변호 불가). 우선순위 정렬은 mapped_at 또는
    # technique 빈도 기반으로 대체.
    mapped_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ── 테이블 6: 갭 판정 결과 (설계서 Table 48, 6컬럼) ──
class GapResultModel(Base):
    """갭 감지 결과.

    completion_rate 등 도출 가능한 값은 저장하지 않고 API 응답에서 계산해 내려준다.
    """

    __tablename__ = "gap_results"

    gap_id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("incident_cases.case_id"), nullable=False)
    gap_type = Column(String(16), nullable=False, index=True)  # NONE/COLLECTION/EVIDENCE/INTERPRETATION
    missing_required = Column(JSON, nullable=True)  # 누락 target_id 배열
    note = Column(Text, nullable=True)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ── 테이블 7: 공격 체인 노드 (설계서 Table 49, 8컬럼 + label 1컬럼 [팀 합의]) ──
class ChainNodeModel(Base):
    """수사 보드 — 공격 체인 노드.

    label은 설계서엔 없으나 보드 UI 노드 표시용으로 팀 합의하에 추가.
    """

    __tablename__ = "chain_nodes"

    node_id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("incident_cases.case_id"), nullable=False)
    attack_id = Column(
        String(36), ForeignKey("attack_events.attack_id"), nullable=True
    )  # NULL = AI 후보 노드
    status = Column(String(16), nullable=False, default="CONFIRMED")  # CONFIRMED/REJECTED
    is_ai_suggested = Column(Boolean, nullable=False, default=False)
    pos_x = Column(Integer, nullable=True)
    pos_y = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    label = Column(String(256), nullable=True)  # [팀 합의 추가 — 설계서 미정의]


# ── 테이블 8: 체인 엣지 (설계서 Table 50, 6컬럼) ──
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
    label = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ── 테이블 9: 수사관 조작 이력 (설계서 Table 51, 8컬럼) ──
class ActionLogModel(Base):
    """감사 추적 — 수사관 모든 조작 기록.

    MVP는 단일 수사관 가정 → actor 기본값 "investigator" (CLAUDE.md 정책).
    """

    __tablename__ = "action_logs"

    log_id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("incident_cases.case_id"), nullable=False)
    actor = Column(String(64), nullable=False, default="investigator")
    action = Column(String(32), nullable=False, index=True)  # ACCEPT/REJECT/EDIT_REPORT/FINALIZE_REPORT/EXPORT_REPORT
    target_type = Column(String(32), nullable=False)  # chain_node, report, etc.
    target_id = Column(String(36), nullable=True)
    detail = Column(JSON, nullable=True)
    logged_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
