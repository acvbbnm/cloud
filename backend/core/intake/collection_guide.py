"""Layer 0 — CollectionGuide 도메인.

설계서 5.4.2절 + UC-01 시퀀스 + 모듈별_구현_명세.md `CollectionGuide` 항목.
사고유형 + CSP에 해당하는 수집 카탈로그를 조회하여 체크리스트를 생성한다.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import CollectionTargetModel, IncidentCaseModel, RawEventModel


class CollectionGuide:
    """수집 가이드 — 케이스 기준 체크리스트 생성/완료율 계산."""

    @classmethod
    def generate(cls, db: Session, case_id: str) -> Optional[dict]:
        """케이스의 사고유형·CSP에 매칭되는 수집 대상 체크리스트를 반환한다.

        반환 형식 (API 계약서 GET /api/guide 응답 data):
            { "caseId": str, "completionRate": float, "targets": [...] }
        없는 케이스면 None.
        """
        case = db.get(IncidentCaseModel, case_id)
        if case is None:
            return None

        targets = cls._lookup_targets(db, case.incident_type, case.csp)
        collected_ids = cls._collected_target_ids(db, case_id)
        completion_rate = cls._compute_completion_rate(targets, collected_ids)

        return {
            "caseId": case_id,
            "completionRate": completion_rate,
            "targets": [
                {
                    "target_id": t.target_id,
                    "log_type": t.log_type,
                    "evidence_role": t.evidence_role,
                    "priority": t.priority,
                    "description": t.description,
                    "collected": t.target_id in collected_ids,
                }
                for t in targets
            ],
        }

    @classmethod
    def _lookup_targets(
        cls, db: Session, incident_type: str, csp: str
    ) -> list[CollectionTargetModel]:
        """incident_type + csp(또는 'all')에 해당하는 collection_targets를 priority 내림차순으로 조회."""
        stmt = (
            select(CollectionTargetModel)
            .where(CollectionTargetModel.incident_type == incident_type)
            .where(CollectionTargetModel.csp.in_([csp, "all"]))
            .order_by(CollectionTargetModel.priority.desc())
        )
        return list(db.execute(stmt).scalars())

    @classmethod
    def _collected_target_ids(cls, db: Session, case_id: str) -> set[str]:
        """이미 raw_events에 적재되어 매칭된 target_id 집합."""
        stmt = (
            select(RawEventModel.matched_target_id)
            .where(RawEventModel.case_id == case_id)
            .where(RawEventModel.matched_target_id.is_not(None))
            .distinct()
        )
        return {row for row in db.execute(stmt).scalars() if row is not None}

    @classmethod
    def _compute_completion_rate(
        cls, targets: list[CollectionTargetModel], collected_ids: set[str]
    ) -> float:
        """필수(REQUIRED) 항목 기준 완료율(0.0~1.0). REQUIRED 0개면 0.0."""
        required = [t for t in targets if t.evidence_role == "REQUIRED"]
        if not required:
            return 0.0
        collected = sum(1 for t in required if t.target_id in collected_ids)
        return round(collected / len(required), 4)
