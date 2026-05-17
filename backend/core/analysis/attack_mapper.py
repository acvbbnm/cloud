"""Layer 2 — AttackMapper.

설계서 5.4.4절 + 5.2.2절 + 모듈별_구현_명세 AttackMapper 항목.

ocsf_events → attack_events 변환:
  1. data/attack_rules/rules.json 로딩 (startup 1회 캐시)
  2. 각 ocsf_event 에 대해 csp 필터 + activity_name_pattern Regex 매칭
  3. condition 평가 (MVP 단계에선 비어있는 룰만 → 무시)
  4. 매칭 룰 1개 이상이면 첫 매칭 룰로 attack_events INSERT
  5. 룰 정보(technique_id/tactic/rule_id)를 그대로 사용

리스크 스코어링은 제거 (산출 근거 부재). 다중 매칭 시 룰 시드의 등록 순서
(구체성 높은 룰을 앞쪽에 배치) 에 의존.
"""
import json
import re
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from db.models import AttackEventModel, OCSFEventModel, RawEventModel


_RULES_CACHE: Optional[list[dict]] = None


def _load_rules() -> list[dict]:
    """attack_rules/rules.json 의 rules 배열을 로드/캐시. 각 룰에 컴파일된 Regex 첨부."""
    global _RULES_CACHE
    if _RULES_CACHE is not None:
        return _RULES_CACHE

    path: Path = settings.ATTACK_RULES_DIR / "rules.json"
    if not path.exists():
        _RULES_CACHE = []
        return _RULES_CACHE

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rules: list[dict] = []
    for rule in data.get("rules", []):
        pattern = rule.get("activity_name_pattern")
        if not pattern:
            continue
        try:
            compiled = re.compile(pattern)
        except re.error:
            continue
        rules.append({**rule, "_re": compiled})

    _RULES_CACHE = rules
    return _RULES_CACHE


# CSP 표기 정렬: 룰엔 'ncp', DB엔 'naver'
_DB_CSP_TO_RULE_CSP = {
    "naver": "ncp",
    "nhn": "nhn",
}


class AttackMapper:
    """ATT&CK 매핑기 — ocsf_events 한 건 또는 케이스 단위 매핑."""

    @classmethod
    def map_one(
        cls,
        db: Session,
        ocsf: OCSFEventModel,
        raw_csp: str,
    ) -> Optional[AttackEventModel]:
        """OCSF event 1건을 ATT&CK 룰과 매칭. 매칭 룰 있으면 attack_events INSERT 후 객체 반환."""
        # 이미 매핑돼 있으면 skip (ocsf_id UQ 제약)
        existing = db.execute(
            select(AttackEventModel).where(AttackEventModel.ocsf_id == ocsf.ocsf_id)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        rule_csp = _DB_CSP_TO_RULE_CSP.get(raw_csp)
        if rule_csp is None:
            return None

        candidates = []
        for rule in _load_rules():
            if rule.get("csp") != rule_csp:
                continue
            if rule["_re"].match(ocsf.activity_name or ""):
                candidates.append(rule)

        if not candidates:
            return None

        # 다중 매칭 시 룰 시드의 등록 순서대로 첫 번째 룰 선택 (구체성 높은 룰을 앞쪽에 배치).
        # risk_score 기반 정렬은 제거 (산출 근거 부재 — 학술 변호 불가).
        best = candidates[0]

        attack = AttackEventModel(
            ocsf_id=ocsf.ocsf_id,
            technique_id=best["technique_id"],
            tactic=best["tactic"],
            rule_id=best["rule_id"],
        )
        try:
            db.add(attack)
            db.flush()
        except IntegrityError:
            db.rollback()
            return None
        return attack

    @classmethod
    def map_case(cls, db: Session, case_id: str) -> dict:
        """케이스의 모든 ocsf_events 를 매핑. 통계 + 생성된 attack_events 목록 반환."""
        # ocsf_event + raw_event 조인하여 csp 함께 가져옴
        stmt = (
            select(OCSFEventModel, RawEventModel.csp)
            .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
            .where(RawEventModel.case_id == case_id)
        )
        rows = list(db.execute(stmt).all())

        mapped: list[AttackEventModel] = []
        for ocsf, csp in rows:
            attack = cls.map_one(db, ocsf, csp)
            if attack is not None:
                mapped.append(attack)

        db.commit()
        total = len(rows)
        unmapped = total - len(mapped)
        rate = round(len(mapped) / total * 100, 2) if total else 0.0
        return {
            "total_ocsf": total,
            "mapped": len(mapped),
            "unmapped": unmapped,
            "mappingRate": rate,
        }


def get_rule_technique_name(rule_id: str) -> Optional[str]:
    """rule_id 로 룰의 description (technique_name 대용) 조회. 응답 직렬화에서 사용."""
    for rule in _load_rules():
        if rule.get("rule_id") == rule_id:
            return rule.get("description")
    return None
