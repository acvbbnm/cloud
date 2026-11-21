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
        # ── dev3 B-3 (2026-05-19) ──
        title: Optional[str] = None,
        tlp: str = "AMBER",
        observables: Optional[list] = None,
    ) -> IncidentCaseModel:
        """사고 케이스를 신규 생성하고 DB에 저장한다.

        dev3: title·tlp·observables 신규 칼럼 지원. UNCLASSIFIED 도 incident_type
        으로 허용 (Step 2 Discovery Loop 미통과 시 fallback).
        """
        case = IncidentCaseModel(
            incident_type=incident_type,
            csp=csp,
            severity=severity,
            occurred_at=occurred_at,
            system_config=system_config,
            title=title,
            tlp=tlp,
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
        # ── dev3 B-3 (2026-05-19) ──
        title: Optional[str] = None,
        tlp: Optional[str] = None,
        observables: Optional[list] = None,
        secondary_incident_types: Optional[list] = None,
        triage_state: Optional[dict] = None,
        incident_type: Optional[str] = None,
        investigator_memo: Optional[str] = None,
    ) -> Optional[IncidentCaseModel]:
        """케이스 필드를 부분 갱신한다.

        dev3: incident_type·title·tlp·observables·secondary_incident_types·
        triage_state 도 PATCH 대상. None 인 필드는 건드리지 않음.

        triage_state 는 dict 통째로 교체 (병합 X) — 클라이언트가 마지막 트리 상태를
        그대로 보내는 모델 (청사진 §3 stateless).
        """
        case = cls.get_by_id(db, case_id)
        if case is None:
            return None
        if severity is not None:
            case.severity = severity
        if system_config is not None:
            case.system_config = system_config
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
        if incident_type is not None:
            case.incident_type = incident_type
        if investigator_memo is not None:
            case.investigator_memo = investigator_memo
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
