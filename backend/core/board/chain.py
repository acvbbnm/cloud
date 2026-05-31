"""Layer 4 — ChainNode / ChainEdge 도메인.

설계서 5.4.6절 + 모듈별_구현_명세.md.

DB 모델(ChainNodeModel / ChainEdgeModel) 을 래핑하여 CRUD 와 직렬화를 캡슐화한다.
API 응답 형식은 frontend types/index.ts 의 BoardNode / BoardEdge 와 일치해야 한다.

Phase O (2026-05-26 byungwoo) — Evidence Board 통합:
  · type='attack' 노드 (기존) + type='clue' 노드 (신규) 양립
  · clue 노드는 attack_id=NULL + meta={type:'clue', clue_key:..., stage:N, source:...}
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from core.intake.info_gain import load_catalog
from db.models import (
    AttackEventModel,
    ChainEdgeModel,
    ChainNodeModel,
)


# ── P.34 (2026-05-31 사용자 피드백) — 보드 라벨 풍부화 헬퍼 ─────────
#   "보드에서 보이는 정보는 intake 와 똑같은게 아니라 약간 어떤 로그인지
#    어떤 단서인지 설명이 나오는게 맞지않나"
#   → V-1 intake 단서 트리는 short_label (식별자) 만으로 충분 (사고유형 선택
#     보조). V-5 수사 보드는 단서 의미를 풀어쓴 한 줄 설명이 필요.

_CLUE_DESC_PATH = Path(__file__).parent.parent.parent / "data" / "triage" / "clue_descriptions.json"


@lru_cache(maxsize=1)
def _load_clue_descriptions() -> dict:
    """clue_descriptions.json 의 descriptions 매핑 (clue_key → meta dict).

    파일 부재·파싱 실패 시 빈 dict (보드 라벨 fallback 동작 보장).
    """
    try:
        with open(_CLUE_DESC_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("descriptions", {}) if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _explainer(short: Optional[str], desc: Optional[str], max_chars: int = 48) -> str:
    """단서 라벨의 *풀이* (헤더 다음에 붙일 한 줄 설명).

    clue_descriptions 패턴 분석 (143개):
        대다수가 ``카테고리 — '단서명'. 본문 설명.`` 형식.
        첫 마침표(``. ``) 이전은 헤더 (카테고리·short_label 반복),
        그 이후가 진짜 풀이 본문.

    동작:
        1. 첫 ``. `` 이후 부분을 풀이로 사용 (헤더 중복 자동 차단)
        2. 단일 문장 desc (마침표 없음) 면 short 헤더 prefix 제거 후 사용
        3. 풀이 내 두 번째 ``. `` 까지만 (간결성)
        4. max_chars 초과 시 말줄임표
        5. 헤더와 완전히 동일하면 빈 문자열 (합성 skip)
    """
    if not desc:
        return ""
    s = desc.strip()
    first_dot = s.find(". ")
    if first_dot >= 0:
        # 마침표 이후 = 진짜 풀이 본문. 헤더 중복 자동 제거.
        s = s[first_dot + 2 :].strip()
    elif short and s.startswith(short):
        # 단일 문장 + 헤더 prefix → 헤더 제거
        s = s[len(short) :].lstrip(" —·:-").strip()
    # 풀이 내 두 번째 마침표·줄바꿈까지만 (간결성)
    for sep in [". ", "\n"]:
        idx = s.find(sep)
        if idx >= 0:
            s = s[:idx]
            break
    s = s.strip().rstrip(".·→-").strip()
    if len(s) > max_chars:
        s = s[: max_chars - 1].rstrip() + "…"
    # 헤더와 *완전히* 동일할 때만 합성 skip
    if short and s == short:
        return ""
    return s


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
        """attack_id 가 주어지면 ATT&CK 기반 기본 라벨 추출.

        P.34 (사용자: "어떤 로그인지 설명이 나오게") — 기존 `T1078.004 · 전술`
        → `T1078.004 · 기법명` 으로 풍부화 (수사관이 ID 만 봐선 의미 모름).
        technique_name 부재 시 tactic 으로 fallback.
        호출 측에서 label 미지정 시 사용. 없으면 None.
        """
        if not attack_id:
            return None
        att = db.get(AttackEventModel, attack_id)
        if att is None:
            return None
        tech_name = (att.technique_name or "").strip()
        if tech_name:
            return f"{att.technique_id} · {tech_name}"
        # technique_name 없으면 기존 동작 (tactic) 으로 fallback
        return f"{att.technique_id} · {att.tactic}"

    @staticmethod
    def derive_label_from_clue(clue_key: Optional[str]) -> Optional[str]:
        """Phase O — clue_catalog 에서 단서 라벨 추출.

        P.34 (사용자: "보드에서 보이는 정보는 intake 와 똑같은게 아니라 약간
        어떤 단서인지 설명이 나오는게 맞지않나") — V-1 intake 단서 트리는
        식별자 (short_label) 만 노출 → V-5 수사 보드는 한 줄 풀이를 합성하여
        수사관이 노드만 봐도 의미 파악 가능하도록.

        합성 우선순위:
            1. clue_descriptions[clue_key].description 의 첫 구절이 있으면
               `{short_label} — {풀이}` 형태로 합성
            2. description 없으면 short_label / label / clue_key 순 fallback

        ChainGraphCanvas 의 라벨 truncate (32 글자) 가 자동 처리하므로 길이
        부담 없음. hover title 로 full 라벨 노출됨.
        """
        if not clue_key:
            return None
        try:
            catalog = load_catalog().get("clues", {})
        except FileNotFoundError:
            catalog = {}
        entry = catalog.get(clue_key) or {}
        short = entry.get("short_label") or entry.get("label") or clue_key

        # P.34 — description 한 줄 풀이 합성 (헤더 중복 제거 후)
        desc_meta = _load_clue_descriptions().get(clue_key) or {}
        desc_text = (
            desc_meta.get("description")
            if isinstance(desc_meta, dict)
            else None
        )
        explainer = _explainer(short, desc_text, max_chars=44)

        if explainer:
            return f"{short} — {explainer}"
        return short

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
