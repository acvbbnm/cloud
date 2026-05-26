"""Layer 4 — InvestigationBoard 도메인.

설계서 5.4.6절 + UC-06 시퀀스. case 단위로 chain_nodes + chain_edges 를 조회·집계한다.

API 응답 형식(frontend types/index.ts `BoardResponse`):
  { caseId, nodes: BoardNode[], edges: BoardEdge[], kpi: { dwellTime, ... } }
"""
from datetime import datetime
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

        PDF 결론 (Mandiant Median Dwell Time 10일 → 7일 단축) 정합 지표:
          · earliestEventTime  : min(raw_events.event_time) — 최초 침해 발생 추정
          · caseCreatedAt      : case.created_at — 수사 접수 (탐지 시각 proxy)
          · caseClosedAt       : case.closed_at — 격리 완료 (None 이면 진행 중)
          · dwellTimeSeconds   : 탐지 - 최초침해 (None 면 raw 이벤트 없음)
          · containmentSeconds : 격리완료 - 탐지 (closed_at 있을 때만)
          · totalSeconds       : 격리완료 - 최초침해 (전체 incident span)

        시연 메시징: Mandiant 7일 기준 비교 → 본 시스템이 즉시 탐지·격리 가이드 제공.
        """
        if case is None:
            case = db.get(IncidentCaseModel, case_id)
        if case is None:
            return {}

        # 최초 침해 발생 시각 — OCSF 정규화된 이벤트의 time 컬럼 (raw_events 자체는
        # 시간 컬럼이 없음 → OCSFEventModel.time JOIN). 정규화 안 되어 있으면 None.
        earliest = db.execute(
            select(func.min(OCSFEventModel.time))
            .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
            .where(RawEventModel.case_id == case_id)
        ).scalar_one_or_none()

        def _secs(later: Optional[datetime], earlier: Optional[datetime]) -> Optional[int]:
            if later is None or earlier is None:
                return None
            return max(0, int((later - earlier).total_seconds()))

        return {
            "earliestEventTime": earliest.isoformat() if earliest else None,
            "caseCreatedAt": case.created_at.isoformat() if case.created_at else None,
            "caseClosedAt": case.closed_at.isoformat() if case.closed_at else None,
            "dwellTimeSeconds": _secs(case.created_at, earliest),
            "containmentSeconds": _secs(case.closed_at, case.created_at),
            "totalSeconds": _secs(case.closed_at, earliest),
            "benchmarkSeconds": 7 * 24 * 60 * 60,  # Mandiant M-Trends 2024 median 7일
            "benchmarkSource": "Mandiant M-Trends 2024 — median dwell time 7d (PDF 결론)",
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
