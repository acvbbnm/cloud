"""Layer 0 — IncidentCase 도메인.

설계서 5.4.2절 + 모듈별_구현_명세.md `IncidentCase` 항목.
DB 모델(IncidentCaseModel)을 래핑하여 CRUD를 캡슐화한다.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from db.models import IncidentCaseModel


class IncidentCase:
    """사고 케이스 도메인 — 케이스 CRUD를 캡슐화한다."""

    @classmethod
    def create(
        cls,
        db: Session,
        incident_type: str,
        csp: str,
        severity: str,
        occurred_at: datetime,
        system_config: Optional[dict] = None,
    ) -> IncidentCaseModel:
        """사고 케이스를 신규 생성하고 DB에 저장한다."""
        case = IncidentCaseModel(
            incident_type=incident_type,
            csp=csp,
            severity=severity,
            occurred_at=occurred_at,
            system_config=system_config,
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        return case

    @classmethod
    def get_by_id(cls, db: Session, case_id: str) -> Optional[IncidentCaseModel]:
        """case_id로 케이스를 조회한다. 없으면 None."""
        return db.get(IncidentCaseModel, case_id)

    @classmethod
    def update_config(
        cls,
        db: Session,
        case_id: str,
        severity: Optional[str] = None,
        system_config: Optional[dict] = None,
    ) -> Optional[IncidentCaseModel]:
        """케이스의 severity·system_config를 부분 갱신한다."""
        case = cls.get_by_id(db, case_id)
        if case is None:
            return None
        if severity is not None:
            case.severity = severity
        if system_config is not None:
            case.system_config = system_config
        db.commit()
        db.refresh(case)
        return case

    @classmethod
    def close(cls, db: Session, case_id: str) -> Optional[IncidentCaseModel]:
        """closed_at을 현재 시각으로 설정하여 케이스를 종료한다."""
        case = cls.get_by_id(db, case_id)
        if case is None:
            return None
        case.closed_at = datetime.utcnow()
        db.commit()
        db.refresh(case)
        return case
