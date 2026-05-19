"""Layer 3 — V-8 사후 검증 추론 엔진 (dev3 청사진 §원칙 5).

확정된 사고유형(`incident_cases.incident_type`)과 Layer 2 ATT&CK 매핑 결과를 비교하여
**증거가 발견되었으나 V-1 Step 2 Discovery 에서 미확정된 추가 사고유형**을 제안한다.

핵심 원칙:
  · AI 판단·결정 X — tactic → incident_type 정적 매핑 사용 (결정성 100%)
  · "이게 맞다" 가 아니라 "이 증거도 발견됨, 수사관이 판단" 안내
  · 채택 여부는 수사관이 PATCH /api/cases (secondary_incident_types) 로 확정

설계서 정합:
  · 청사진 §원칙 5 "V-8 사후 검증 — Layer 2 전체 매핑 결과로 V-1 결정 보완"
  · 사용자 결정사항 6번 "V-8 사후 검증 유지"
  · CLAUDE.md "AI 는 판단/결정하지 않는다"
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    AttackEventModel,
    IncidentCaseModel,
    OCSFEventModel,
    RawEventModel,
)


# ─────────────────────────────────────────────────────────────
# Tactic → Incident Type 정적 매핑 (학술 변호 가능 기준)
# ─────────────────────────────────────────────────────────────
# 참조: MITRE ATT&CK Cloud Matrix v14 + 청사진 §3 사고유형 enum
# 한 tactic 이 여러 incident_type 에 매핑 가능 (multi-mapping) — 가중치로 표현.
TACTIC_TO_INCIDENT_TYPES: dict[str, list[tuple[str, float]]] = {
    "Initial Access": [("CREDENTIAL_THEFT", 1.0)],
    "Credential Access": [("CREDENTIAL_THEFT", 1.0)],
    "Privilege Escalation": [("PRIVILEGE_ESCALATION", 1.0)],
    "Persistence": [
        ("PRIVILEGE_ESCALATION", 0.7),  # 신규 계정·정책 부여로 권한 유지
        ("CREDENTIAL_THEFT", 0.3),  # 자격증명 백도어 유지
    ],
    "Defense Evasion": [("AUDIT_LOG_TAMPERING", 0.8)],
    "Discovery": [("DATA_EXFILTRATION", 0.5)],  # 정찰 → 유출 전조
    "Lateral Movement": [("MULTI_CSP_LATERAL", 1.0)],
    "Collection": [("DATA_EXFILTRATION", 0.8)],
    "Exfiltration": [("DATA_EXFILTRATION", 1.0)],
    "Impact": [
        ("AUDIT_LOG_TAMPERING", 0.6),  # 로그·계정 삭제 (T1485, T1531)
        ("DATA_EXFILTRATION", 0.2),  # 데이터 파괴 = 유출 후 은폐 가능성
    ],
}


# ─────────────────────────────────────────────────────────────
# 기법별 override (tactic 으로 안 잡히는 명시적 케이스)
# ─────────────────────────────────────────────────────────────
TECHNIQUE_OVERRIDES: dict[str, list[tuple[str, float]]] = {
    # T1531 Account Access Removal — Impact 이지만 권한 박탈 = 권한 변동
    "T1531": [("AUDIT_LOG_TAMPERING", 0.7), ("PRIVILEGE_ESCALATION", 0.3)],
    # T1485 Data Destruction — 데이터 파괴는 로그 변조보다 유출·은폐 의도가 큼
    "T1485": [("AUDIT_LOG_TAMPERING", 0.5), ("DATA_EXFILTRATION", 0.5)],
    # T1098 Account Manipulation — 권한 부여는 권한 상승의 핵심 패턴
    "T1098": [("PRIVILEGE_ESCALATION", 1.0)],
    "T1098.001": [("PRIVILEGE_ESCALATION", 1.0)],
    # T1136 Create Account — 신규 계정은 권한 상승 + persistence
    "T1136.003": [("PRIVILEGE_ESCALATION", 1.0)],
    # T1552 Unsecured Credentials — 자격증명 노출
    "T1552": [("CREDENTIAL_THEFT", 1.0)],
}


# ─────────────────────────────────────────────────────────────
# 점수 임계값
# ─────────────────────────────────────────────────────────────
# 사후 검증에서 secondary 로 제안할 최소 누적 점수.
# attack_event 1개당 1.0 ~ 가중치 점수 누적 → 1.5 이상이면 "발견됨" 으로 간주.
SUGGEST_THRESHOLD = 1.5


def _score_event(technique_id: str, tactic: str) -> list[tuple[str, float]]:
    """단일 attack_event 에서 (incident_type, score) 리스트 산출.

    technique override 가 있으면 우선, 없으면 tactic 매핑 사용.
    """
    if technique_id in TECHNIQUE_OVERRIDES:
        return TECHNIQUE_OVERRIDES[technique_id]
    return TACTIC_TO_INCIDENT_TYPES.get(tactic, [])


def infer_from_attacks(
    db: Session, case_id: str
) -> dict:
    """케이스의 attack_events 를 분석하여 사고유형 추론.

    Returns:
        {
          "confirmed":         str | None,      # 현재 incident_cases.incident_type
          "scores":            {type: float},   # 사고유형별 누적 점수
          "evidence_count":    {type: int},     # 사고유형별 기여 attack_event 수
          "suggested_secondary": [type, ...],   # 임계값 통과 + confirmed 와 다른 것
          "samples":           [{...}, ...],    # 대표 증거 (최대 5건)
          "total_attacks":     int,
        }
    """
    case = db.get(IncidentCaseModel, case_id)
    if case is None:
        return {
            "error": "CASE_NOT_FOUND",
            "confirmed": None,
            "scores": {},
            "evidence_count": {},
            "suggested_secondary": [],
            "samples": [],
            "total_attacks": 0,
        }

    # case 의 모든 attack_events 조회 (raw_events.case_id 조인)
    rows = list(
        db.execute(
            select(AttackEventModel)
            .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
            .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
            .where(RawEventModel.case_id == case_id)
        ).scalars()
    )

    scores: dict[str, float] = {}
    evidence_count: dict[str, int] = {}
    samples_by_type: dict[str, list[dict]] = {}

    for atk in rows:
        contributions = _score_event(atk.technique_id, atk.tactic)
        for itype, weight in contributions:
            scores[itype] = scores.get(itype, 0.0) + weight
            evidence_count[itype] = evidence_count.get(itype, 0) + 1
            # 대표 증거 (사고유형당 최대 3건)
            if len(samples_by_type.setdefault(itype, [])) < 3:
                samples_by_type[itype].append(
                    {
                        "attack_id": atk.attack_id,
                        "technique_id": atk.technique_id,
                        "tactic": atk.tactic,
                        "rule_id": atk.rule_id,
                        "weight": weight,
                    }
                )

    confirmed = case.incident_type
    # confirmed 와 다른 사고유형 중 임계값 통과
    suggested: list[str] = sorted(
        [
            t
            for t, s in scores.items()
            if s >= SUGGEST_THRESHOLD and t != confirmed and t != "UNCLASSIFIED"
        ],
        key=lambda t: -scores[t],
    )

    # flatten samples — suggested 사고유형의 증거만 모음
    flat_samples: list[dict] = []
    for itype in suggested:
        for s in samples_by_type.get(itype, []):
            flat_samples.append({**s, "incident_type": itype})
    flat_samples = flat_samples[:5]  # 최대 5건

    return {
        "confirmed": confirmed,
        "scores": {k: round(v, 2) for k, v in scores.items()},
        "evidence_count": evidence_count,
        "suggested_secondary": suggested,
        "samples": flat_samples,
        "total_attacks": len(rows),
        "threshold": SUGGEST_THRESHOLD,
    }
