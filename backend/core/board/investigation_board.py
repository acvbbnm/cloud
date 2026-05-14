"""Layer 4 — InvestigationBoard 도메인.

설계서 5.4.6절 + UC-06 시퀀스. case 단위로 chain_nodes + chain_edges 를 조회·집계한다.

API 응답 형식(frontend types/index.ts `BoardResponse`):
  { caseId, nodes: BoardNode[], edges: BoardEdge[] }
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.board.chain import ChainEdge, ChainNode
from db.models import ChainEdgeModel, ChainNodeModel, IncidentCaseModel


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

        return {
            "caseId": case_id,
            "nodes": [ChainNode.serialize(n) for n in nodes],
            "edges": [ChainEdge.serialize(e) for e in edges],
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
