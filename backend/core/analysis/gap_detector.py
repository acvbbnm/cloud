"""Layer 2 — GapDetector.

설계서 5.4.4절 + UC-04 시퀀스 + 모듈별_구현_명세 GapDetector 항목.

분류 (가장 심각한 것 우선):
- COLLECTION    : 필수 증거 미수집 → Layer 0 복귀 권장
- INTERPRETATION: 매핑 안 된 이벤트 다수 → AI 셰르파 브리핑 권장
- EVIDENCE      : 매핑 결과가 있으나 부족 → 수사관 직접 판단
- NONE          : 갭 없음 → 수사 보드(Layer 4)로 진행

multi-type (2026-05-31): 단서 루프에서 2개 이상의 사고유형이 확정되면
(case.incident_type + case.secondary_incident_types) 각 유형의 REQUIRED 증거
집합이 서로 다르므로 COLLECTION 갭을 유형별로 독립 판정한다. OCSF 정규화·ATT&CK
매핑 카운트는 케이스 전역이므로 EVIDENCE/INTERPRETATION/NONE 은 유형 간 공통.
응답 `perType` 배열로 유형별 결과를 내려주고, gap_results 에는 기존과 동일하게
전체(worst) 1행만 적재해 report_generator 등 기존 소비자 호환을 유지한다.
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

# 갭 심각도 순위 (작을수록 심각) — 전체(worst) 판정에 사용.
_SEVERITY_RANK = {"COLLECTION": 0, "INTERPRETATION": 1, "EVIDENCE": 2, "NONE": 3}

# ───────────────────────────────────────────────────────────────
# P.25 (2026-05-31) — GapDetector v2 부가 진단 4종 복구.
# P.24 (jingyu d39b1e0 머지) 의 theirs 적용 시 손실된 geunhyung a96365b 함수
# 4개를 jingyu multi-type 위에 재추가. detect() 응답 dict 에 backward-compat
# optional 필드로 동봉.
# ───────────────────────────────────────────────────────────────

# [R4] priority 가중치 — Naver Cloud 보안관제 실무 우선순위 체계 반영.
# priority 는 1(낮음)~10(높음). P1(>=10)=critical, P2(7~9)=high, P3(4~6)=mid, P4(<=3)=low.
_PRIORITY_WEIGHTS: dict[int, int] = {
    10: 10, 9: 7, 8: 7, 7: 7,
    6: 3, 5: 3, 4: 3,
    3: 1, 2: 1, 1: 1,
}

# [R1] ATT&CK for Cloud kill-chain 주요 9 tactic — 논문 매트릭스 구조 반영.
_KILL_CHAIN_TACTICS: list[str] = [
    "Initial Access", "Execution", "Persistence", "Privilege Escalation",
    "Defense Evasion", "Credential Access", "Discovery",
    "Lateral Movement", "Exfiltration", "Impact",
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
    """[R4] priority 가중 점수 — 단순 count 보다 P1 누락의 위험을 강하게 반영."""
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
    """[R1] ATT&CK kill-chain 단계별 커버리지 — 논문의 매트릭스 매핑 구조 반영."""
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
    total = len(set(_KILL_CHAIN_TACTICS) | covered_tactics)
    return {
        "covered": len(covered_tactics),
        "total": total,
        "byTactic": by_tactic,
        "missingTactics": missing,
    }


def _detect_time_gaps(db: Session, case_id: str) -> list[dict]:
    """[R3] anti-forensic 후보 시간 공백 — SentinelOne 'log deletion is forensic evidence'."""
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
        return []
    gaps: list[dict] = []
    for prev, curr in zip(times[:-1], times[1:]):
        diff = curr - prev
        mins = diff.total_seconds() / 60.0
        if mins >= _TIME_GAP_THRESHOLD_MINUTES:
            gaps.append({
                "from": prev.isoformat(),
                "to": curr.isoformat(),
                "durationMinutes": round(mins, 1),
                "suspicion": "anti_forensic_candidate",
            })
    return gaps


def _detect_bad_config(
    required_targets: list[CollectionTargetModel],
    corroborating_targets: list[CollectionTargetModel],
    collected_ids: set[str],
) -> list[str]:
    """[R2] Google Cloud bad log configuration heuristic — REQUIRED 0 + CORROBORATING > 0 비대칭."""
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
        if cor_rate - req_rate > 0.2:
            signals.append(
                f"REQUIRED 수집률 {round(req_rate * 100, 1)}% < "
                f"CORROBORATING 수집률 {round(cor_rate * 100, 1)}% — "
                "핵심 로그 우선순위 역전. 감사 정책 점검 필요."
            )
    return signals


class GapDetector:
    """갭 감지기 — 케이스 단위 분류 + gap_results INSERT (유형별 독립 판정)."""

    @staticmethod
    def _incident_types(case: IncidentCaseModel) -> list[str]:
        """판정 대상 사고유형 목록 — primary(케이스 확정값) + secondary(부 가설).

        중복 제거, primary 를 첫 항목으로 유지. secondary 가 없으면 [primary] 1개."""
        types: list[str] = []
        if case.incident_type:
            types.append(case.incident_type)
        for t in case.secondary_incident_types or []:
            if t and t not in types:
                types.append(t)
        return types or [case.incident_type]

    @classmethod
    def _detect_for_type(
        cls,
        db: Session,
        case: IncidentCaseModel,
        incident_type: str,
        collected_ids: set[str],
        total_ocsf_n: int,
        mapped_n: int,
    ) -> dict:
        """단일 사고유형에 대한 갭 판정 (DB 적재는 하지 않음)."""
        # 표시 전체 항목 (REQUIRED + CORROBORATING) — A안 완료율 분모용.
        all_targets = list(
            db.execute(
                select(CollectionTargetModel)
                .where(CollectionTargetModel.incident_type == incident_type)
                .where(CollectionTargetModel.csp.in_([case.csp, "all"]))
            ).scalars()
        )
        all_ids = {t.target_id for t in all_targets}

        # gap_type / 미수집 목록은 의미상 REQUIRED 기준 유지 (필수 증거 누락 = COLLECTION 갭).
        required_targets = [t for t in all_targets if t.evidence_role == "REQUIRED"]
        required_ids = {t.target_id for t in required_targets}
        missing_ids = required_ids - collected_ids
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

        # A안 (2026-06-04 사용자 요청) — 완료율 = 표시 전체 항목 중 수집 비율
        # (REQUIRED + CORROBORATING). 항목이 하나도 정의 안 된 경우(UNCLASSIFIED 등) None.
        completion_rate = (
            round(len(all_ids & collected_ids) / len(all_ids) * 100, 2)
            if all_ids
            else None
        )

        if missing_ids:
            gap_type = "COLLECTION"
            summary = (
                f"[{incident_type}] 필수 증거 {len(required_ids)}건 중 "
                f"{len(missing_ids)}건 미수집. 미수집 항목: "
                f"{', '.join(sorted(missing_ids))[:200]}"
            )
            recommendation = (
                f"Layer 0(사고 접수)으로 복귀하여 {incident_type} 누락 로그를 추가 수집하세요."
            )
        elif total_ocsf_n == 0:
            gap_type = "EVIDENCE"
            summary = f"[{incident_type}] 수집은 완료됐으나 정규화된 OCSF 이벤트가 없습니다."
            recommendation = "POST /api/analysis/normalize 를 호출하여 정규화를 먼저 수행하세요."
        elif mapped_n == 0:
            gap_type = "INTERPRETATION"
            summary = (
                f"[{incident_type}] OCSF 이벤트 {total_ocsf_n}건이 정규화됐으나 "
                f"ATT&CK 매핑이 0건. 수집된 로그가 공격 시그니처와 일치하지 않습니다."
            )
            recommendation = "AI 셰르파에 브리핑을 요청하거나 사고유형 분류를 재검토하세요."
        elif mapped_n / total_ocsf_n < _INTERPRETATION_THRESHOLD:
            gap_type = "INTERPRETATION"
            summary = (
                f"[{incident_type}] 매핑률 {round(mapped_n / total_ocsf_n * 100, 2)}% — "
                f"OCSF {total_ocsf_n}건 중 {mapped_n}건만 매핑."
            )
            recommendation = "매핑 안 된 이벤트는 AI 셰르파 브리핑 또는 수사관 직접 판단이 필요합니다."
        else:
            gap_type = "NONE"
            req_repr = (
                f"필수 증거 {len(required_ids)}건 모두 수집, "
                if required_ids
                else "필수 증거 미정의, "
            )
            summary = (
                f"[{incident_type}] 갭 없음. {req_repr}"
                f"OCSF {total_ocsf_n}건 중 {mapped_n}건 매핑 "
                f"(매핑률 {round(mapped_n / total_ocsf_n * 100, 2)}%)."
            )
            recommendation = "Layer 4 수사 보드로 진행하세요."

        return {
            "incident_type": incident_type,
            "gap_type": gap_type,
            "missing": missing_info,
            "summary": summary,
            "recommendation": recommendation,
            "completionRate": completion_rate,
        }

    @classmethod
    def detect(cls, db: Session, case_id: str) -> Optional[dict]:
        """케이스의 갭을 분석하고 gap_results 에 INSERT 후 응답 dict 반환.

        반환 dict 는 기존 단일 결과 필드(전체 worst 기준)를 그대로 유지하면서
        `incidentTypes`·`perType` 두 필드를 추가한다 (하위 호환)."""
        case = db.get(IncidentCaseModel, case_id)
        if case is None:
            return None

        # ── 케이스 전역 카운트 (사고유형 무관) ──
        collected_ids = set(
            db.execute(
                select(distinct(RawEventModel.matched_target_id))
                .where(RawEventModel.case_id == case_id)
                .where(RawEventModel.matched_target_id.is_not(None))
            ).scalars()
        )
        total_ocsf_n = len(
            db.execute(
                select(OCSFEventModel)
                .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
                .where(RawEventModel.case_id == case_id)
            ).all()
        )
        mapped_n = len(
            db.execute(
                select(AttackEventModel)
                .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
                .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
                .where(RawEventModel.case_id == case_id)
            ).all()
        )

        # ── 유형별 독립 판정 ──
        types = cls._incident_types(case)
        per_type = [
            cls._detect_for_type(
                db, case, t, collected_ids, total_ocsf_n, mapped_n
            )
            for t in types
        ]

        # ── 전체(worst) 판정 — gap_results 적재 + 하위 호환 top-level 필드 ──
        worst = min(per_type, key=lambda r: _SEVERITY_RANK.get(r["gap_type"], 99))

        # 미수집 필수 증거 union (target_id 기준 dedup) — 보고서/KPI 일관성.
        union_missing: dict[str, dict] = {}
        for r in per_type:
            for m in r["missing"]:
                union_missing.setdefault(m["target_id"], m)
        missing_info = list(union_missing.values())

        is_multi = len(types) >= 2
        if is_multi:
            collection_types = [r["incident_type"] for r in per_type if r["gap_type"] == "COLLECTION"]
            if collection_types:
                summary = (
                    f"확정 사고유형 {len(types)}종 중 {len(collection_types)}종에서 "
                    f"필수 증거 미수집: {', '.join(collection_types)}. "
                    f"전체 미수집 항목 {len(missing_info)}건."
                )
                recommendation = (
                    "Layer 0(사고 접수)으로 복귀하여 각 사고유형별 누락 로그를 추가 수집하세요. "
                    "유형별 상세는 perType 항목을 참조하세요."
                )
            else:
                summary = (
                    f"확정 사고유형 {len(types)}종 전체에서 필수 증거 수집 완료. "
                    f"전체 판정: {worst['gap_type']}."
                )
                recommendation = worst["recommendation"]
        else:
            summary = worst["summary"]
            recommendation = worst["recommendation"]

        # A안 (2026-06-04) — 전체 완수율 = 모든 유형 표시 항목(REQUIRED+CORROBORATING)
        # union 중 수집 비율. (정의된 항목이 하나도 없으면 None.)
        all_scope_ids: set[str] = set()
        for t in types:
            ids = set(
                db.execute(
                    select(CollectionTargetModel.target_id)
                    .where(CollectionTargetModel.incident_type == t)
                    .where(CollectionTargetModel.csp.in_([case.csp, "all"]))
                ).scalars()
            )
            all_scope_ids |= ids
        completion_rate = (
            round(len(all_scope_ids & collected_ids) / len(all_scope_ids) * 100, 2)
            if all_scope_ids
            else None
        )

        # ── P.25 (2026-05-31) — v2 부가 진단 4종 계산 ──
        # 모든 사고유형의 REQUIRED/CORROBORATING target 합집합으로 priority 가중·
        # bad-config 분석. tactic 커버리지·시간 갭은 케이스 전역 (사고유형 무관).
        all_required_targets: list[CollectionTargetModel] = []
        all_corroborating_targets: list[CollectionTargetModel] = []
        seen_req_ids: set[str] = set()
        seen_cor_ids: set[str] = set()
        for t in types:
            req = list(
                db.execute(
                    select(CollectionTargetModel)
                    .where(CollectionTargetModel.incident_type == t)
                    .where(CollectionTargetModel.csp.in_([case.csp, "all"]))
                    .where(CollectionTargetModel.evidence_role == "REQUIRED")
                ).scalars()
            )
            for tgt in req:
                if tgt.target_id not in seen_req_ids:
                    seen_req_ids.add(tgt.target_id)
                    all_required_targets.append(tgt)
            cor = list(
                db.execute(
                    select(CollectionTargetModel)
                    .where(CollectionTargetModel.incident_type == t)
                    .where(CollectionTargetModel.csp.in_([case.csp, "all"]))
                    .where(CollectionTargetModel.evidence_role == "CORROBORATING")
                ).scalars()
            )
            for tgt in cor:
                if tgt.target_id not in seen_cor_ids:
                    seen_cor_ids.add(tgt.target_id)
                    all_corroborating_targets.append(tgt)

        priority_score = _compute_priority_score(all_required_targets, collected_ids)
        tactic_coverage = _compute_tactic_coverage(db, case_id)
        time_gaps = _detect_time_gaps(db, case_id)
        bad_config_signals = _detect_bad_config(
            all_required_targets, all_corroborating_targets, collected_ids
        )

        # ── DB 적재 (전체 1행만 — 기존 소비자 호환) ──
        gap = GapResultModel(
            case_id=case_id,
            gap_type=worst["gap_type"],
            missing_required=missing_info if missing_info else None,
            note=summary,
        )
        db.add(gap)
        db.commit()
        db.refresh(gap)

        return {
            "gap_id": gap.gap_id,
            "case_id": case_id,
            "gap_type": worst["gap_type"],
            "missing": missing_info,
            "summary": summary,
            "recommendation": recommendation,
            "completionRate": completion_rate,
            "created_at": (gap.detected_at or datetime.utcnow()).isoformat(),
            # ── multi-type (2026-05-31) ──
            "incidentTypes": types,
            "perType": per_type,
            # ── P.25 (2026-05-31) v2 부가 진단 복구 — backend → frontend V-4 패널 ──
            "priorityScore": priority_score,           # [R4]
            "tacticCoverage": tactic_coverage,         # [R1]
            "timeGaps": time_gaps,                     # [R3]
            "badConfigSignals": bad_config_signals,    # [R2]
        }
