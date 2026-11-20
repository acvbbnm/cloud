"""Layer 2 — GapDetector.

설계서 5.4.4절 + UC-04 시퀀스 + 모듈별_구현_명세 GapDetector 항목.

분류 (가장 심각한 것 우선):
- COLLECTION    : 필수 증거 미수집 → Layer 0 복귀 권장
- INTERPRETATION: 매핑 안 된 이벤트 다수 → AI 셰르파 브리핑 권장
- EVIDENCE      : 매핑 결과가 있으나 부족 → 수사관 직접 판단
- NONE          : 갭 없음 → 수사 보드(Layer 4)로 진행
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from db.models import (
    AttackEventModel,
    CollectionTargetModel,
    GapResultModel,
    IncidentCaseModel,
    OCSFEventModel,
    RawEventModel,
)


_INTERPRETATION_THRESHOLD = 0.3  # 매핑률 30% 미만이면 INTERPRETATION 후보


class GapDetector:
    """갭 감지기 — 케이스 단위 분류 + gap_results INSERT."""

    @classmethod
    def detect(cls, db: Session, case_id: str) -> Optional[dict]:
        """케이스의 갭을 분석하고 gap_results 에 INSERT 후 응답 dict 반환."""
        case = db.get(IncidentCaseModel, case_id)
        if case is None:
            return None

        # 1) 필수 증거 집합
        required_targets = list(
            db.execute(
                select(CollectionTargetModel)
                .where(CollectionTargetModel.incident_type == case.incident_type)
                .where(CollectionTargetModel.csp.in_([case.csp, "all"]))
                .where(CollectionTargetModel.evidence_role == "REQUIRED")
            ).scalars()
        )
        required_ids = {t.target_id for t in required_targets}

        # 2) 수집된(matched) 집합
        collected_ids = set(
            db.execute(
                select(distinct(RawEventModel.matched_target_id))
                .where(RawEventModel.case_id == case_id)
                .where(RawEventModel.matched_target_id.is_not(None))
            ).scalars()
        )

        # 3) ocsf / attack 카운트
        total_ocsf = db.execute(
            select(OCSFEventModel)
            .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
            .where(RawEventModel.case_id == case_id)
        ).all()
        total_ocsf_n = len(total_ocsf)

        mapped_n = len(
            db.execute(
                select(AttackEventModel)
                .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
                .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
                .where(RawEventModel.case_id == case_id)
            ).all()
        )

        missing_ids = required_ids - collected_ids
        completion_rate = (
            round((len(required_ids) - len(missing_ids)) / len(required_ids) * 100, 2)
            if required_ids
            else 0.0
        )

        # 4) 분류
        missing_targets = [t for t in required_targets if t.target_id in missing_ids]
        missing_info = [
            {
                "target_id": t.target_id,
                "log_type": t.log_type,
                "evidence_role": t.evidence_role,
                "priority": t.priority,
            }
            for t in missing_targets
        ]

        if missing_ids:
            gap_type = "COLLECTION"
            summary = (
                f"필수 증거 {len(required_ids)}건 중 {len(missing_ids)}건 미수집. "
                f"우선 미수집 항목: {', '.join(sorted(missing_ids))[:200]}"
            )
            recommendation = "수집 가이드에서 빠진 로그를 확인한 뒤 추가하세요."
        elif total_ocsf_n == 0:
            gap_type = "EVIDENCE"
            summary = "정규화된 OCSF 이벤트가 없습니다."
            recommendation = "OCSF 정규화 화면에서 변환을 실행하세요."
        elif mapped_n == 0:
            gap_type = "INTERPRETATION"
            summary = (
                f"OCSF 이벤트 {total_ocsf_n}건 중 ATT&CK 규칙과 일치한 이벤트가 없습니다."
            )
            recommendation = "원본 로그와 선택한 사고 유형을 검토하세요."
        elif mapped_n / total_ocsf_n < _INTERPRETATION_THRESHOLD:
            gap_type = "INTERPRETATION"
            summary = (
                f"매핑률 {round(mapped_n / total_ocsf_n * 100, 2)}% — "
                f"OCSF {total_ocsf_n}건 중 {mapped_n}건만 매핑."
            )
            recommendation = "매핑되지 않은 이벤트는 원본 로그와 대조하세요."
        else:
            gap_type = "NONE"
            summary = (
                f"현재 수집 목록의 필수 증거 {len(required_ids)}건을 확보했습니다. "
                f"OCSF {total_ocsf_n}건 중 {mapped_n}건 매핑 (매핑률 {round(mapped_n / total_ocsf_n * 100, 2)}%)."
            )
            recommendation = "조사 보드에서 확보한 근거를 검토하세요."

        # 5) DB 적재
        gap = GapResultModel(
            case_id=case_id,
            gap_type=gap_type,
            missing_required=missing_info if missing_info else None,
            note=summary,
        )
        db.add(gap)
        db.commit()
        db.refresh(gap)

        return {
            "gap_id": gap.gap_id,
            "case_id": case_id,
            "gap_type": gap_type,
            "missing": missing_info,
            "summary": summary,
            "recommendation": recommendation,
            "completionRate": completion_rate,
            "created_at": (gap.detected_at or datetime.utcnow()).isoformat(),
        }
