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
        title: Optional[str] = None,
        tlp: Optional[str] = "AMBER",
        observables: Optional[list] = None,
    ) -> IncidentCaseModel:
        """사고 케이스를 신규 생성하고 DB에 저장한다.

        dev3: title·tlp·observables 추가. 미지정 시 None / AMBER / [] 기본.
        """
        case = IncidentCaseModel(
            incident_type=incident_type,
            csp=csp,
            severity=severity,
            occurred_at=occurred_at,
            system_config=system_config,
            title=title,
            tlp=tlp or "AMBER",
            observables=observables if observables is not None else [],
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
        incident_type: Optional[str] = None,
        title: Optional[str] = None,
        tlp: Optional[str] = None,
        observables: Optional[list] = None,
        secondary_incident_types: Optional[list] = None,
        triage_state: Optional[dict] = None,
    ) -> Optional[IncidentCaseModel]:
        """케이스를 부분 갱신한다.

        dev3 (2026-05-19): Step 2 Discovery 종료 후 trigger 확정용 필드 추가.
        - `incident_type` — UNCLASSIFIED → 결정 트리 평가 결과로 갱신
        - `triage_state` — 트리 진행 상태 영속화
        - `secondary_incident_types` — V-8 사후 검증 부 사고유형
        """
        case = cls.get_by_id(db, case_id)
        if case is None:
            return None
        if severity is not None:
            case.severity = severity
        if system_config is not None:
            case.system_config = system_config
        # ── dev3 신규 ──
        if incident_type is not None:
            case.incident_type = incident_type
        if title is not None:
            case.title = title
        if tlp is not None:
            case.tlp = tlp
        if observables is not None:
            case.observables = observables
        if secondary_incident_types is not None:
            case.secondary_incident_types = secondary_incident_types
        if triage_state is not None:
            case.triage_state = triage_state
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
