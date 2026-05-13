"""Layer 1 — LogIngestor 도메인.

설계서 5.4.3절 + 모듈별_구현_명세.md `LogIngestor` 항목 + UC-02 시퀀스.

책임:
  1) 업로드된 multipart 파일 수신
  2) SHA-256 해시 계산 (파일 단위, 무결성)
  3) CSP 별 파서로 raw event 추출 (NCP / NHN)
  4) raw_events 테이블에 적재
  5) collection_targets 카탈로그와 매칭하여 matched_target_id 채움
  6) IngestionStats 반환 (totalEvents / matched / unmatched / byTarget)

매칭 규칙:
  - case.incident_type + case.csp 조합으로 후보 collection_targets 추림
  - 현재는 CREDENTIAL_THEFT × {naver, nhn} 만 매칭 룰 구현 (MVP 분량)
  - 향후 확장 시 data/collection_targets/target_match_rules.json 으로 분리 권장
"""
import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from core.ingestion import matchers
from core.ingestion.parsers import ncp as ncp_parser
from core.ingestion.parsers import nhn as nhn_parser
from db.models import CollectionTargetModel, IncidentCaseModel, RawEventModel


# ─────────────────────────────────────────────────────────────
# 통계 결과 컨테이너
# ─────────────────────────────────────────────────────────────


@dataclass
class IngestionStats:
    """업로드 결과 통계."""

    total_events: int = 0
    matched: int = 0
    unmatched: int = 0
    by_target: dict[str, int] = field(default_factory=dict)
    sha256: str = ""
    source_file: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "totalEvents": self.total_events,
            "matched": self.matched,
            "unmatched": self.unmatched,
            "byTarget": self.by_target,
            "sha256": self.sha256,
            "sourceFile": self.source_file,
        }


# ─────────────────────────────────────────────────────────────
# LogIngestor
# ─────────────────────────────────────────────────────────────


class LogIngestor:
    """로그 수집 도메인 — 업로드→해시→파싱→적재→매칭 파이프라인."""

    # ── 1. 해시 ─────────────────────────────────────────────
    @staticmethod
    def verify_hash(content: bytes) -> str:
        """파일 바이트의 SHA-256 hex digest 반환."""
        return hashlib.sha256(content).hexdigest()

    # ── 2. 파싱 ─────────────────────────────────────────────
    @staticmethod
    def parse(csp: str, content: bytes) -> list[dict]:
        """csp 에 맞는 파서를 호출하여 평탄화 dict 리스트 반환."""
        if csp == "naver":
            return ncp_parser.parse(content)
        if csp == "nhn":
            return nhn_parser.parse(content)
        raise ValueError(f"지원하지 않는 csp: {csp}")

    # ── 3. 적재 ─────────────────────────────────────────────
    @classmethod
    def ingest(
        cls,
        db: Session,
        case: IncidentCaseModel,
        filename: Optional[str],
        content: bytes,
    ) -> IngestionStats:
        """업로드된 파일을 파싱·적재·매칭하고 IngestionStats 를 반환한다.

        - case.csp 가 'all' 일 경우 우선 'naver' 형식 시도 → 실패 시 'nhn'.
          (멀티 CSP 시나리오는 Phase 2 후반 확장)
        """
        sha256 = cls.verify_hash(content)

        # case.csp 결정 (all 일 경우 NCP 우선 시도)
        target_csps = [case.csp] if case.csp in ("naver", "nhn") else ["naver", "nhn"]

        parsed: list[dict] = []
        used_csp: Optional[str] = None
        last_error: Optional[Exception] = None
        for csp in target_csps:
            try:
                parsed = cls.parse(csp, content)
                used_csp = csp
                break
            except (ValueError, json.JSONDecodeError) as e:
                last_error = e
                continue
        if used_csp is None:
            raise ValueError(
                f"파일 파싱 실패 — 지원되는 형식이 아닙니다 ({last_error})"
            )

        # 매칭 후보 target_id 캐시 — case 의 incident_type+csp 카탈로그만 미리 로드
        valid_target_ids = {
            t.target_id
            for t in db.query(CollectionTargetModel)
            .filter(
                CollectionTargetModel.incident_type == case.incident_type,
                CollectionTargetModel.csp == used_csp,
            )
            .all()
        }

        stats = IngestionStats(sha256=sha256, source_file=filename)
        new_rows: list[RawEventModel] = []
        for ev in parsed:
            stats.total_events += 1
            target_id = matchers.match(used_csp, case.incident_type, ev)
            # 매칭은 했지만 시드에 없는 target_id 라면 unmatched 로 강등
            if target_id and target_id not in valid_target_ids:
                target_id = None
            if target_id:
                stats.matched += 1
                stats.by_target[target_id] = stats.by_target.get(target_id, 0) + 1
            else:
                stats.unmatched += 1

            new_rows.append(
                RawEventModel(
                    case_id=case.case_id,
                    csp=used_csp,
                    raw_json=json.dumps(ev["raw"], ensure_ascii=False),
                    sha256=sha256,
                    matched_target_id=target_id,
                    source_file=filename,
                )
            )

        db.bulk_save_objects(new_rows)
        db.commit()
        return stats

    # ── 5. 조회 ─────────────────────────────────────────────
    @classmethod
    def list_events(
        cls,
        db: Session,
        case_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[RawEventModel], int]:
        """case의 raw_events 페이지네이션 조회. (rows, total) 반환."""
        q = db.query(RawEventModel).filter(RawEventModel.case_id == case_id)
        total = q.count()
        rows = (
            q.order_by(RawEventModel.ingested_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return rows, total

    @classmethod
    def get_event(cls, db: Session, event_id: str) -> Optional[RawEventModel]:
        return db.get(RawEventModel, event_id)
