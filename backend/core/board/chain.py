"""Layer 4 — ChainNode / ChainEdge 도메인.

설계서 5.4.6절 + 모듈별_구현_명세.md.

DB 모델(ChainNodeModel / ChainEdgeModel) 을 래핑하여 CRUD 와 직렬화를 캡슐화한다.
API 응답 형식은 frontend types/index.ts 의 BoardNode / BoardEdge 와 일치해야 한다.

Phase O (2026-05-26 byungwoo) — Evidence Board 통합:
  · type='attack' 노드 (기존) + type='clue' 노드 (신규) 양립
  · clue 노드는 attack_id=NULL + meta={type:'clue', clue_key:..., stage:N, source:...}
"""
from typing import Optional

from sqlalchemy.orm import Session

from core.intake.info_gain import load_catalog
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
        meta: Optional[dict] = None,
    ) -> ChainNodeModel:
        """노드를 신규 생성한다.

        - AI 제안 노드는 attack_id 없이 생성 가능 (NULL 허용)
        - 수동 추가 시 status=CONFIRMED, AI 제안은 호출 측에서 명시 가능
        - Phase O (2026-05-26): meta JSON 으로 단서 노드 (type='clue') 등 자유 메타 저장
        """
        node = ChainNodeModel(
            case_id=case_id,
            attack_id=attack_id,
            label=label,
            status=status,
            is_ai_suggested=is_ai_suggested,
            pos_x=pos_x,
            pos_y=pos_y,
            meta=meta,
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
        meta: Optional[dict] = None,
    ) -> Optional[ChainNodeModel]:
        """노드 상태·좌표·라벨·meta 부분 갱신.

        meta 는 dict 가 전달되면 기존 meta 와 shallow merge (Phase O 보드 편집 UX).
        명시 삭제는 빈 dict {} → 호출 측에서 직접 None 할당 처리.
        """
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
        if meta is not None:
            merged = dict(node.meta or {})
            merged.update(meta)
            node.meta = merged
        db.commit()
        db.refresh(node)
        return node

    @staticmethod
    def serialize(node: ChainNodeModel) -> dict:
        """ChainNodeModel → frontend BoardNode dict (snake_case 유지).

        Phase O — meta 가 있으면 응답에 동봉 (없으면 type='attack' 기본값).
        type 필드는 frontend BoardNode 식별 편의용 (clue|attack).
        """
        meta = node.meta or None
        node_type = (meta or {}).get("type", "attack") if meta else "attack"
        out = {
            "node_id": node.node_id,
            "attack_id": node.attack_id,
            "label": node.label or "",
            "status": node.status,
            "is_ai_suggested": bool(node.is_ai_suggested),
            "pos_x": node.pos_x if node.pos_x is not None else 0,
            "pos_y": node.pos_y if node.pos_y is not None else 0,
            "type": node_type,
        }
        if meta is not None:
            out["meta"] = meta
        return out

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

    @staticmethod
    def derive_label_from_clue(clue_key: Optional[str]) -> Optional[str]:
        """Phase O — clue_catalog 에서 단서 short_label 추출.

        - clue_key 미지정 시 None
        - 카탈로그에 키 없으면 clue_key 그대로 fallback (시연 시 누락 단서도 표시)
        """
        if not clue_key:
            return None
        try:
            catalog = load_catalog().get("clues", {})
        except FileNotFoundError:
            return clue_key
        entry = catalog.get(clue_key)
        if not entry:
            return clue_key
        return entry.get("short_label") or entry.get("label") or clue_key

    @staticmethod
    def build_clue_meta(
        clue_key: str,
        stage: int = 1,
        hypothesis: Optional[str] = None,
        source: str = "manual_drag",
        extra: Optional[dict] = None,
    ) -> dict:
        """Phase O — 단서 노드의 표준 meta dict 생성.

        호출 측은 이 결과를 ChainNode.create(..., meta=...) 로 전달.
        """
        meta: dict = {
            "type": "clue",
            "clue_key": clue_key,
            "stage": stage,
            "source": source,
        }
        if hypothesis:
            meta["hypothesis"] = hypothesis
        if extra:
            meta.update(extra)
        return meta


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

    @classmethod
    def get_by_id(cls, db: Session, edge_id: str) -> Optional[ChainEdgeModel]:
        return db.query(ChainEdgeModel).filter(ChainEdgeModel.edge_id == edge_id).first()

    @classmethod
    def delete(cls, db: Session, edge_id: str) -> bool:
        """엣지 1개 삭제. 존재하면 True, 미존재면 False."""
        edge = cls.get_by_id(db, edge_id)
        if edge is None:
            return False
        db.delete(edge)
        db.commit()
        return True

    @staticmethod
    def serialize(edge: ChainEdgeModel) -> dict:
        return {
            "edge_id": edge.edge_id,
            "from_node_id": edge.from_node_id,
            "to_node_id": edge.to_node_id,
            "label": edge.label or "",
        }
