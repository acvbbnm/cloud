"""Layer 4 — InvestigationBoard 도메인.

설계서 5.4.6절 + UC-06 시퀀스. case 단위로 chain_nodes + chain_edges 를 조회·집계한다.

API 응답 형식(frontend types/index.ts `BoardResponse`):
  { caseId, nodes: BoardNode[], edges: BoardEdge[], kpi: { dwellTime, ... } }
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.board.chain import ChainEdge, ChainNode
from core.board.graph_analytics import analyze_board
from db.models import (
    ChainEdgeModel,
    ChainNodeModel,
    IncidentCaseModel,
    OCSFEventModel,
    RawEventModel,
)


# ── Dwell Time 벤치마크 (근거 자료 기반) ──────────────────────────
#
# Mandiant M-Trends 2024 (FY2023 침해 데이터, 글로벌) — 출처값:
#   · global median dwell time = 10일
#   · ransomware            = 6일   (median)
#   · non-ransomware        = 13일  (median)
#   · 외부 통보(notified)    = 9일   / 내부 탐지(internal) = 13일
# 보조 근거:
#   · IBM Cost of a Data Breach 2024 — mean time to identify ≈ 194일 (mean, 참고)
#   · Verizon DBIR 2024 — 탐지까지 수일~수주 분포
#
# 판단 정책 (median 10일 + 분포 기반 4등급):
#   median(10d) 를 중심으로 사분위 개념을 적용한 임계 — 사용자에게 학술 수치를
#   노출하지 않고 '우수/평균/주의/심각' 등급 라벨만 보여준다 (출처는 작게 tooltip).
DWELL_BENCHMARK_MEDIAN_DAYS = 10           # Mandiant M-Trends 2024 글로벌 median
DWELL_GRADE_THRESHOLDS_DAYS = {
    "excellent": 1,    #  ≤ 1일  — 우수 (즉시 탐지, 상위 ~10%)
    "good": 10,        #  ≤ 10일 — 평균 이내 (글로벌 median 이하)
    "warning": 30,     #  ≤ 30일 — 주의 (median 초과, IBM/Verizon 분포 상위권)
    # > 30일           —  심각 (장기 잠복, 즉시 대응 체계 보강 필요)
}
DWELL_BENCHMARK_SOURCE = "Mandiant M-Trends 2024 (global median dwell 10d)"


def _dwell_grade(dwell_seconds: Optional[int]) -> dict:
    """dwell 초 → 등급 라벨 + 색 + 한 줄 평가. 근거 수치는 source 에만 노출.

    반환: {grade, label, tone, message, source}
    """
    if dwell_seconds is None:
        return {
            "grade": "unknown",
            "label": "측정 불가",
            "tone": "gray",
            "message": "정규화된 OCSF 이벤트가 필요합니다",
            "source": DWELL_BENCHMARK_SOURCE,
        }
    days = dwell_seconds / 86400.0
    th = DWELL_GRADE_THRESHOLDS_DAYS
    if days <= th["excellent"]:
        grade, label, tone = "excellent", "매우 빠름", "teal"
        msg = "글로벌 상위권 — 즉시 탐지 수준"
    elif days <= th["good"]:
        grade, label, tone = "good", "평균 이내", "teal"
        msg = "글로벌 중앙값 이하 — 양호한 탐지 역량"
    elif days <= th["warning"]:
        grade, label, tone = "warning", "평균 초과", "amber"
        msg = "글로벌 중앙값 초과 — 탐지 지연 주의"
    else:
        grade, label, tone = "critical", "장기 잠복", "red"
        msg = "장기 미탐지 — 탐지 체계 보강 권고"
    return {
        "grade": grade,
        "label": label,
        "tone": tone,
        "message": msg,
        "source": DWELL_BENCHMARK_SOURCE,
    }


class InvestigationBoard:
    """수사 보드 — case 단위 노드·엣지 상태 조회."""

    @classmethod
    def get_state(cls, db: Session, case_id: str) -> Optional[dict]:
        """case 의 보드 전체 상태 반환. case 미존재 시 None.

        반환: { caseId, nodes: [...], edges: [...] }
        """
        case = db.get(IncidentCaseModel, case_id)
        if case is None:
            return None

        nodes = list(
            db.execute(
                select(ChainNodeModel)
                .where(ChainNodeModel.case_id == case_id)
                .order_by(ChainNodeModel.created_at)
            ).scalars()
        )
        edges = list(
            db.execute(
                select(ChainEdgeModel)
                .where(ChainEdgeModel.case_id == case_id)
                .order_by(ChainEdgeModel.created_at)
            ).scalars()
        )

        nodes_ser = [ChainNode.serialize(n) for n in nodes]
        edges_ser = [ChainEdge.serialize(e) for e in edges]
        # Phase J — networkx GDS 분석 (PageRank + Label Propagation)
        # 그래프 비어있어도 안전 (빈 결과 반환)
        gds = analyze_board(nodes_ser, edges_ser, pagerank_top_k=3)

        return {
            "caseId": case_id,
            "nodes": nodes_ser,
            "edges": edges_ser,
            "kpi": cls.compute_kpi(db, case_id, case),
            "gds": gds,  # Phase J 신규
        }

    @classmethod
    def compute_kpi(
        cls,
        db: Session,
        case_id: str,
        case: Optional[IncidentCaseModel] = None,
    ) -> dict:
        """Phase 2.5 (P6, 2026-05-25) — Dwell Time KPI.
        2026-05-31 fix — 탐지 시각: case.occurred_at 우선, fallback case.created_at.

        Mandiant 의 Dwell Time 정의: "최초 침해 → 조직이 사고를 인지(detected)"
        → 수사관이 V-1 Step 1 에서 입력한 occurred_at 이 진짜 인지 시각.
        case.created_at (DB INSERT 시각) 은 인지 후 시스템 등록 시각 = proxy.

        벤치마크: Mandiant M-Trends 2024 글로벌 median dwell time = 10일.
        판단: _dwell_grade() 가 median(10d) + 분포 기반 4등급 (우수/평균/주의/심각).
          · earliestEventTime  : min(ocsf_events.time) — 최초 침해 발생 추정
          · detectedAt         : case.occurred_at (사용자 입력) 우선 / fallback created_at
          · caseCreatedAt      : case.created_at — DB INSERT (proxy 보존)
          · caseClosedAt       : case.closed_at — 격리 완료 (None 이면 진행 중)
          · dwellTimeSeconds   : 탐지(detectedAt) - 최초침해
          · containmentSeconds : 격리완료 - 탐지(detectedAt)
          · totalSeconds       : 격리완료 - 최초침해 (전체 incident span)
          · dwellSource        : 'occurred_at' | 'created_at' (어느 값 썼는지 표시)
          · grade              : {grade, label, tone, message, source} — UI 등급 표시
        """
        if case is None:
            case = db.get(IncidentCaseModel, case_id)
        if case is None:
            return {}

        # OCSF 정규화된 이벤트의 시각 — min(최초 침해 추정) + max(시나리오 종료)
        ocsf_q = (
            select(
                func.min(OCSFEventModel.time),
                func.max(OCSFEventModel.time),
            )
            .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
            .where(RawEventModel.case_id == case_id)
        )
        earliest, latest = db.execute(ocsf_q).one_or_none() or (None, None)

        # 탐지 시점: 사용자 입력 occurred_at 우선, 없으면 created_at fallback
        detected_at = case.occurred_at or case.created_at
        dwell_source = "occurred_at" if case.occurred_at else "created_at"

        def _secs(later: Optional[datetime], earlier: Optional[datetime]) -> Optional[int]:
            if later is None or earlier is None:
                return None
            return max(0, int((later - earlier).total_seconds()))

        # ── Dwell Time 계산 — 합성 로그 자동 감지 + spread 기반 보정 ──
        # 합성 로그 (시연용 ncp_sysdig_8min_killchain.json 등) 는 시각이 과거에
        # 박혀있어 raw dwell 이 수십~수백일이 됨 (예: 83일). Mandiant 7d 비교
        # 메시징 의미가 없음.
        #
        # 정책 (2026-06-03 사용자 피드백 "제대로 작동"):
        #   1. earliest 가 detected 보다 30일 이상 과거 → 합성 로그 의심
        #      → spread (latest-earliest) 를 dwell 로 사용 (시나리오 내부 시간)
        #   2. 30일 이하 → raw 계산 그대로 (실 케이스)
        #   3. 정규화 X → None
        SYNTH_THRESHOLD_DAYS = 30
        raw_dwell = _secs(detected_at, earliest)
        signal_spread = _secs(latest, earliest)
        synthetic_adjusted = False
        dwell_time_seconds = raw_dwell
        effective_earliest = earliest
        effective_latest = latest
        if (
            raw_dwell is not None
            and raw_dwell > SYNTH_THRESHOLD_DAYS * 24 * 3600
            and signal_spread is not None
        ):
            # 합성 로그 감지 — 로그에 박힌 시각이 과거(예: 3개월 전)라 raw dwell 이
            # 비현실적. 시나리오 내부 spread (latest-earliest) 를 진짜 dwell 로 쓰고,
            # 표시 타임라인을 [detected-spread → detected] 로 재정렬한다.
            #   · effective_earliest = detected - spread  (최초 침해 추정, 표시용)
            #   · effective_latest   = detected           (탐지 시점에 종료로 정렬)
            # → UI 타임라인이 earliest ≤ latest ≤ detected 로 일관 (역순 방지).
            synthetic_adjusted = True
            dwell_time_seconds = signal_spread
            effective_earliest = detected_at - timedelta(seconds=signal_spread)
            effective_latest = detected_at

        return {
            "earliestEventTime": effective_earliest.isoformat() if effective_earliest else None,
            "rawEarliestEventTime": earliest.isoformat() if earliest else None,
            "latestEventTime": effective_latest.isoformat() if effective_latest else None,
            "rawLatestEventTime": latest.isoformat() if latest else None,
            "detectedAt": detected_at.isoformat() if detected_at else None,
            "caseCreatedAt": case.created_at.isoformat() if case.created_at else None,
            "caseClosedAt": case.closed_at.isoformat() if case.closed_at else None,
            "dwellTimeSeconds": dwell_time_seconds,
            "signalSpreadSeconds": signal_spread,
            "containmentSeconds": _secs(case.closed_at, detected_at),
            "totalSeconds": _secs(case.closed_at, earliest),
            # 벤치마크 — Mandiant M-Trends 2024 글로벌 median 10일 (기존 7일 → 정정).
            "benchmarkSeconds": DWELL_BENCHMARK_MEDIAN_DAYS * 24 * 60 * 60,
            "benchmarkSource": DWELL_BENCHMARK_SOURCE,
            "dwellSource": dwell_source,
            "syntheticAdjusted": synthetic_adjusted,
            # 4등급 판정 (excellent/good/warning/critical) — 근거 수치는 grade.source 에만.
            "grade": _dwell_grade(dwell_time_seconds),
        }

    @classmethod
    def validate_edge(
        cls, db: Session, case_id: str, from_node_id: str, to_node_id: str
    ) -> Optional[str]:
        """엣지 추가 전 검증. 실패 시 에러 메시지 반환, OK 면 None.

        - from/to 노드가 모두 존재해야 함
        - 두 노드가 동일 case 에 속해야 함
        - self-loop 금지
        """
        if from_node_id == to_node_id:
            return "from_node_id 와 to_node_id 가 동일합니다 (self-loop 금지)"
        from_node = ChainNode.get_by_id(db, from_node_id)
        to_node = ChainNode.get_by_id(db, to_node_id)
        if from_node is None or to_node is None:
            return "from_node 또는 to_node 가 존재하지 않습니다"
        if from_node.case_id != case_id or to_node.case_id != case_id:
            return "엣지 양 끝 노드가 요청 case 와 다른 case 에 속합니다"
        return None
