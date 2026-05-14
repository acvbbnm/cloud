"""Layer 4 — ChainNode / ChainEdge 도메인.

설계서 5.4.6절 + 모듈별_구현_명세.md.

DB 모델(ChainNodeModel / ChainEdgeModel) 을 래핑하여 CRUD 와 직렬화를 캡슐화한다.
API 응답 형식은 frontend types/index.ts 의 BoardNode / BoardEdge 와 일치해야 한다.
"""
from typing import Optional

from sqlalchemy.orm import Session

from db.models import (
    AttackEventModel,
    ChainEdgeModel,
    ChainNodeModel,
)


class ChainNode:
    """수사 보드 노드."""

    @classmethod
    def create(
        cls,
        db: Session,
        case_id: str,
        label: str,
        attack_id: Optional[str] = None,
        is_ai_suggested: bool = False,
        pos_x: Optional[int] = None,
        pos_y: Optional[int] = None,
        status: str = "CONFIRMED",
    ) -> ChainNodeModel:
        """노드를 신규 생성한다.

        - AI 제안 노드는 attack_id 없이 생성 가능 (NULL 허용)
        - 수동 추가 시 status=CONFIRMED, AI 제안은 호출 측에서 명시 가능
        """
        node = ChainNodeModel(
            case_id=case_id,
            attack_id=attack_id,
            label=label,
            status=status,
            is_ai_suggested=is_ai_suggested,
            pos_x=pos_x,
            pos_y=pos_y,
        )
        db.add(node)
        db.commit()
        db.refresh(node)
        return node

    @classmethod
    def get_by_id(cls, db: Session, node_id: str) -> Optional[ChainNodeModel]:
        return db.get(ChainNodeModel, node_id)

    @classmethod
    def update(
        cls,
        db: Session,
        node_id: str,
        status: Optional[str] = None,
        pos_x: Optional[int] = None,
        pos_y: Optional[int] = None,
        label: Optional[str] = None,
    ) -> Optional[ChainNodeModel]:
        """노드 상태·좌표·라벨 부분 갱신."""
        node = cls.get_by_id(db, node_id)
        if node is None:
            return None
        if status is not None:
            node.status = status
        if pos_x is not None:
            node.pos_x = pos_x
        if pos_y is not None:
            node.pos_y = pos_y
        if label is not None:
            node.label = label
        db.commit()
        db.refresh(node)
        return node

    @staticmethod
    def serialize(node: ChainNodeModel) -> dict:
        """ChainNodeModel → frontend BoardNode dict (snake_case 유지)."""
        return {
            "node_id": node.node_id,
            "attack_id": node.attack_id,
            "label": node.label or "",
            "status": node.status,
            "is_ai_suggested": bool(node.is_ai_suggested),
            "pos_x": node.pos_x if node.pos_x is not None else 0,
            "pos_y": node.pos_y if node.pos_y is not None else 0,
        }

    @staticmethod
    def derive_label_from_attack(
        db: Session, attack_id: Optional[str]
    ) -> Optional[str]:
        """attack_id 가 주어지면 ATT&CK 기반 기본 라벨 추출(`T1078.004` 등).

        호출 측에서 label 미지정 시 사용. 없으면 None.
        """
        if not attack_id:
            return None
        att = db.get(AttackEventModel, attack_id)
        if att is None:
            return None
        return f"{att.technique_id} · {att.tactic}"


class ChainEdge:
    """수사 보드 방향성 엣지."""

    @classmethod
    def create(
        cls,
        db: Session,
        case_id: str,
        from_node_id: str,
        to_node_id: str,
        label: Optional[str] = None,
    ) -> ChainEdgeModel:
        edge = ChainEdgeModel(
            case_id=case_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            label=label,
        )
        db.add(edge)
        db.commit()
        db.refresh(edge)
        return edge

    @staticmethod
    def serialize(edge: ChainEdgeModel) -> dict:
        return {
            "edge_id": edge.edge_id,
            "from_node_id": edge.from_node_id,
            "to_node_id": edge.to_node_id,
            "label": edge.label or "",
        }
