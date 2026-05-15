"""Layer 2 — GapDetector.

설계서 5.4.4절 + UC-04 시퀀스 + 모듈별_구현_명세 GapDetector 항목.

분류 (가장 심각한 것 우선):
- COLLECTION    : 필수 증거 미수집 → Layer 0 복귀 권장
- INTERPRETATION: 매핑 안 된 이벤트 다수 → AI 셰르파 브리핑 권장
- EVIDENCE      : 매핑 결과가 있으나 부족 → 수사관 직접 판단
- NONE          : 갭 없음 → 수사 보드(Layer 4)로 진행

v2 (2026-05-15) — 4개 참고자료 반영 확장:
  [R1] 한국정보보호학회 「클라우드 환경에서의 ATT&CK 매트릭스 기반 이벤트 로그 분석」
       (koreascience.kr/article/JAKO202413554384286)
       → kill-chain 9 tactic 커버리지 분석. 단계 누락은 INTERPRETATION 신호.
  [R2] Google Cloud Threat Intelligence 「Cloud Bad Log Configurations」
       (cloud.google.com/blog/ko/topics/threat-intelligence/cloud-bad-log-configurations)
       → REQUIRED 미수집 + CORROBORATING 수집된 비대칭 = bad config 신호.
  [R3] SentinelOne 「사이버보안 포렌식」 (anti-forensics 섹션)
       (sentinelone.com/ko/cybersecurity-101/cybersecurity/cybersecurity-forensics)
       → 시간 축 비정상 공백(>30분)은 로그 삭제·변조 후보.
  [R4] Naver Cloud 보안관제 실무 (brunch.co.kr/@topasvga/5026)
       → priority 가중 점수(P1=10, P2=5, P3=3, P4=1) — 단순 count 보다 실효.

추가 응답 필드 (backward-compat — 기존 필드 모두 유지):
  - priorityScore   : { collected, missing, total, percent }  [R4]
  - tacticCoverage  : { covered, total, byTactic, missingTactics }  [R1]
  - timeGaps        : [{ from, to, durationMinutes, suspicion }]  [R3]
  - badConfigSignals: string[]  [R2]
"""
from datetime import datetime, timedelta
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

# [R4] priority 가중치 — Naver Cloud 보안관제 실무 우선순위 체계 반영.
# priority 는 1(낮음)~10(높음). P1(>=10)=critical, P2(7~9)=high, P3(4~6)=mid, P4(<=3)=low.
_PRIORITY_WEIGHTS: dict[int, int] = {
    10: 10, 9: 7, 8: 7, 7: 7,  # critical/high
    6: 3, 5: 3, 4: 3,           # mid
    3: 1, 2: 1, 1: 1,           # low
}

# [R1] ATT&CK for Cloud kill-chain 주요 9 tactic — 논문 매트릭스 구조 반영.
# 본 시스템 rules.json 은 Credential Access ~ Impact 7종이지만, 갭 분석은
# 정찰·실행 등 미커버 단계까지 포함해 "이론적 단계 대비 실제 커버" 비율을 본다.
_KILL_CHAIN_TACTICS: list[str] = [
    "Initial Access",
    "Execution",
    "Persistence",
    "Privilege Escalation",
    "Defense Evasion",
    "Credential Access",
    "Discovery",
    "Lateral Movement",
    "Exfiltration",
    "Impact",
]

# [R3] anti-forensic 시간 갭 임계값 — 30분 이상 공백을 의심 구간으로 표시.
_TIME_GAP_THRESHOLD_MINUTES = 30


def _priority_weight(priority: int) -> int:
    """priority(1~10) → 가중치. 매핑되지 않은 값은 1로 폴백."""
    return _PRIORITY_WEIGHTS.get(int(priority or 0), 1)


def _compute_priority_score(
    required_targets: list[CollectionTargetModel],
    collected_ids: set[str],
) -> dict:
    """[R4] priority 가중 점수 — 단순 count 보다 P1 누락의 위험을 강하게 반영.

    예: P1(가중치 10) 1건 누락이 P4(가중치 1) 5건 누락보다 심각.
    """
    total_w = sum(_priority_weight(t.priority) for t in required_targets)
    collected_w = sum(
        _priority_weight(t.priority) for t in required_targets if t.target_id in collected_ids
    )
    missing_w = total_w - collected_w
    percent = round(collected_w / total_w * 100, 2) if total_w else 0.0
    return {
        "collected": collected_w,
        "missing": missing_w,
        "total": total_w,
        "percent": percent,
    }


def _compute_tactic_coverage(db: Session, case_id: str) -> dict:
    """[R1] ATT&CK kill-chain 단계별 커버리지 — 논문의 매트릭스 매핑 구조 반영.

    case 내 attack_events 의 tactic 분포를 집계하고, _KILL_CHAIN_TACTICS 와 비교해
    어떤 단계가 비어있는지 식별한다. 미커버 단계는 INTERPRETATION 갭의 부가 신호.
    """
    rows = list(
        db.execute(
            select(AttackEventModel.tactic)
            .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
            .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
            .where(RawEventModel.case_id == case_id)
        ).scalars()
    )
    by_tactic: dict[str, int] = {}
    for t in rows:
        by_tactic[t] = by_tactic.get(t, 0) + 1

    covered_tactics = set(by_tactic.keys())
    missing = [t for t in _KILL_CHAIN_TACTICS if t not in covered_tactics]
    # rules.json 외부의 tactic 도 있을 수 있으므로 union 으로 total 산정
    total = len(set(_KILL_CHAIN_TACTICS) | covered_tactics)
    return {
        "covered": len(covered_tactics),
        "total": total,
        "byTactic": by_tactic,
        "missingTactics": missing,
    }


def _detect_time_gaps(db: Session, case_id: str) -> list[dict]:
    """[R3] anti-forensic 후보 시간 공백 — SentinelOne "log deletion is forensic evidence".

    OCSF 이벤트의 time 을 정렬하고, 인접 이벤트 간격이 _TIME_GAP_THRESHOLD_MINUTES
    이상이면 의심 구간으로 기록한다. (단, 케이스 전체 기간이 너무 짧으면 skip.)
    """
    times = sorted(
        db.execute(
            select(OCSFEventModel.time)
            .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
            .where(RawEventModel.case_id == case_id)
            .where(OCSFEventModel.time.is_not(None))
        ).scalars()
    )
    if len(times) < 2:
        return []

    span = times[-1] - times[0]
    if span < timedelta(minutes=_TIME_GAP_THRESHOLD_MINUTES * 2):
        # 케이스 전체 기간이 1시간 미만이면 갭 정의 자체가 무의미.
        return []

    gaps: list[dict] = []
    for prev, curr in zip(times[:-1], times[1:]):
        diff = curr - prev
        mins = diff.total_seconds() / 60.0
        if mins >= _TIME_GAP_THRESHOLD_MINUTES:
            gaps.append(
                {
                    "from": prev.isoformat(),
                    "to": curr.isoformat(),
                    "durationMinutes": round(mins, 1),
                    "suspicion": "anti_forensic_candidate",
                }
            )
    return gaps


def _detect_bad_config(
    required_targets: list[CollectionTargetModel],
    corroborating_targets: list[CollectionTargetModel],
    collected_ids: set[str],
) -> list[str]:
    """[R2] Google Cloud bad log configuration heuristic.

    "REQUIRED 항목은 비어있는데 보조(CORROBORATING)만 수집된" 비대칭 패턴은
    수집 구성 오류의 강력한 신호 — 핵심 감사 로그 설정이 누락됐을 가능성.
    """
    signals: list[str] = []
    req_collected = sum(1 for t in required_targets if t.target_id in collected_ids)
    cor_collected = sum(1 for t in corroborating_targets if t.target_id in collected_ids)

    if required_targets and req_collected == 0 and cor_collected > 0:
        signals.append(
            f"필수 감사 로그 {len(required_targets)}건 전부 미수집인데 "
            f"보조 로그만 {cor_collected}건 수집됨 — CSP 감사 추적 비활성화 의심 "
            "(Google Cloud bad-log-config 패턴)."
        )
    elif required_targets and corroborating_targets:
        req_rate = req_collected / len(required_targets)
        cor_rate = cor_collected / len(corroborating_targets) if corroborating_targets else 0
        # REQUIRED 수집률이 CORROBORATING 보다 20%p 이상 낮으면 비대칭 경고
        if cor_rate - req_rate > 0.2:
            signals.append(
                f"REQUIRED 수집률 {round(req_rate * 100, 1)}% < "
                f"CORROBORATING 수집률 {round(cor_rate * 100, 1)}% — "
                "핵심 로그 우선순위 역전. 감사 정책 점검 필요."
            )
    return signals


class GapDetector:
    """갭 감지기 — 케이스 단위 분류 + gap_results INSERT.

    v2: priority 가중 / tactic 커버리지 / 시간 갭 / bad-config 신호 추가.
    분류 결정 자체는 기존 4분류(COLLECTION/EVIDENCE/INTERPRETATION/NONE) 를
    유지하되, priority 가중 점수가 보조 판단에 사용된다.
    """

    @classmethod
    def detect(cls, db: Session, case_id: str) -> Optional[dict]:
        """케이스의 갭을 분석하고 gap_results 에 INSERT 후 응답 dict 반환."""
        case = db.get(IncidentCaseModel, case_id)
        if case is None:
            return None

        # 1) 필수 / 보조 증거 집합
        targets_in_scope = list(
            db.execute(
                select(CollectionTargetModel)
                .where(CollectionTargetModel.incident_type == case.incident_type)
                .where(CollectionTargetModel.csp.in_([case.csp, "all"]))
            ).scalars()
        )
        required_targets = [t for t in targets_in_scope if t.evidence_role == "REQUIRED"]
        corroborating_targets = [
            t for t in targets_in_scope if t.evidence_role == "CORROBORATING"
        ]
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
        total_ocsf_n = len(
            db.execute(
                select(OCSFEventModel.ocsf_id)
                .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
                .where(RawEventModel.case_id == case_id)
            ).all()
        )
        mapped_n = len(
            db.execute(
                select(AttackEventModel.attack_id)
                .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
                .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
                .where(RawEventModel.case_id == case_id)
            ).all()
        )

        missing_ids = required_ids - collected_ids
        # 필수 증거가 정의된 경우만 비율 계산 — 미정의 (예: UNCLASSIFIED 케이스) 면 None.
        # 0.0 으로 채우면 "0% 완수" 와 "요구사항 미정의" 가 혼동되어 V-4 KPI 깨짐 (2026-05-24 walkthrough).
        completion_rate = (
            round((len(required_ids) - len(missing_ids)) / len(required_ids) * 100, 2)
            if required_ids
            else None
        )

        missing_targets = [t for t in required_targets if t.target_id in missing_ids]
        # priority 내림차순 정렬 — 가장 중요한 누락이 missing[0]
        missing_targets.sort(key=lambda t: -(t.priority or 0))
        missing_info = [
            {
                "target_id": t.target_id,
                "log_type": t.log_type,
                "evidence_role": t.evidence_role,
                "priority": t.priority,
            }
            for t in missing_targets
        ]

        # 4) 부가 진단 신호 (참고자료 R1~R4 반영)
        priority_score = _compute_priority_score(required_targets, collected_ids)
        tactic_coverage = _compute_tactic_coverage(db, case_id)
        time_gaps = _detect_time_gaps(db, case_id)
        bad_config_signals = _detect_bad_config(
            required_targets, corroborating_targets, collected_ids
        )

        # 5) 분류 — 기존 우선순위(COLLECTION > EVIDENCE > INTERPRETATION > NONE) 유지
        mapping_rate = (mapped_n / total_ocsf_n) if total_ocsf_n else 0.0

        if missing_ids:
            gap_type = "COLLECTION"
            top_missing = missing_targets[0] if missing_targets else None
            top_hint = (
                f" 최우선 누락: {top_missing.target_id} (P{top_missing.priority})"
                if top_missing
                else ""
            )
            summary = (
                f"필수 증거 {len(required_ids)}건 중 {len(missing_ids)}건 미수집 "
                f"(우선순위 가중 수집률 {priority_score['percent']}%).{top_hint}"
            )
            recommendation = (
                "Layer 0(사고 접수)으로 복귀하여 누락된 로그를 추가 수집하세요. "
                "우선순위가 높은 항목부터 처리하세요."
            )
        elif total_ocsf_n == 0:
            gap_type = "EVIDENCE"
            summary = "수집은 완료됐으나 정규화된 OCSF 이벤트가 없습니다."
            recommendation = "POST /api/analysis/normalize 를 호출하여 정규화를 먼저 수행하세요."
        elif mapped_n == 0:
            gap_type = "INTERPRETATION"
            summary = (
                f"OCSF 이벤트 {total_ocsf_n}건이 정규화됐으나 ATT&CK 매핑이 0건. "
                f"수집된 로그가 공격 시그니처와 일치하지 않습니다."
            )
            recommendation = "AI 셰르파에 브리핑을 요청하거나 사고유형 분류를 재검토하세요."
        elif mapping_rate < _INTERPRETATION_THRESHOLD:
            gap_type = "INTERPRETATION"
            summary = (
                f"매핑률 {round(mapping_rate * 100, 2)}% — "
                f"OCSF {total_ocsf_n}건 중 {mapped_n}건만 매핑. "
                f"커버된 ATT&CK 단계 {tactic_coverage['covered']}/{tactic_coverage['total']}."
            )
            recommendation = (
                "매핑 안 된 이벤트는 AI 셰르파 브리핑 또는 수사관 직접 판단이 필요합니다."
            )
        else:
            gap_type = "NONE"
            summary = (
                f"갭 없음. 필수 증거 {len(required_ids)}건 모두 수집, "
                f"OCSF {total_ocsf_n}건 중 {mapped_n}건 매핑 "
                f"(매핑률 {round(mapping_rate * 100, 2)}%). "
                f"ATT&CK 단계 커버리지 {tactic_coverage['covered']}/{tactic_coverage['total']}."
            )
            recommendation = "Layer 4 수사 보드로 진행하세요."

        # 6) 부가 신호를 recommendation 에 추가 (시연 가시성)
        addons: list[str] = []
        if bad_config_signals:
            addons.append("⚠ 수집 구성: " + " / ".join(bad_config_signals))
        if time_gaps:
            addons.append(
                f"⚠ 시간 공백 {len(time_gaps)}건 탐지 — 로그 삭제·변조 가능성 검토 필요"
            )
        if tactic_coverage["missingTactics"] and gap_type == "NONE":
            # NONE 이라도 단계 누락이 있으면 안내만
            addons.append(
                "ℹ 미커버 ATT&CK 단계: " + ", ".join(tactic_coverage["missingTactics"][:5])
            )
        if addons:
            recommendation = recommendation + "\n" + "\n".join(addons)

        # 7) DB 적재 — note 에는 summary 만 (스키마는 단순 유지, 부가 신호는 응답에만)
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
            # ── v2 부가 진단 필드 (frontend 점진적 적용) ───────────────────────
            "priorityScore": priority_score,           # [R4]
            "tacticCoverage": tactic_coverage,         # [R1]
            "timeGaps": time_gaps,                     # [R3]
            "badConfigSignals": bad_config_signals,    # [R2]
        }
