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
  - 확정 사고유형 전체(주 case.incident_type + 부 secondary_incident_types) × case.csp
    조합으로 후보 collection_targets 추림 (GapDetector 와 동일 범위)
  - 8종 사고유형 × {naver, nhn} 매처 구현 (core/ingestion/matchers.py)
  - 매칭은 주 유형 우선, 미매치 시 부 유형 순차 시도 — 첫 유효 매치 채택
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

        # 확정된 모든 사고유형(주 + 부) — GapDetector._incident_types 와 동일 범위.
        # 복합 케이스에서 부 유형 타깃이 영원히 미매칭되어 갭 감지가 항상 0%/COLLECTION
        # 으로 떨어지던 버그 fix (2026-06-05). primary 를 첫 항목으로 유지(매칭 우선순위).
        confirmed_types: list[str] = [case.incident_type]
        for t in case.secondary_incident_types or []:
            if t and t not in confirmed_types:
                confirmed_types.append(t)

        # 매칭 후보 target_id 캐시 — 확정 유형 전체 × csp 카탈로그 미리 로드
        valid_target_ids = {
            t.target_id
            for t in db.query(CollectionTargetModel)
            .filter(
                CollectionTargetModel.incident_type.in_(confirmed_types),
                CollectionTargetModel.csp == used_csp,
            )
            .all()
        }

        stats = IngestionStats(sha256=sha256, source_file=filename)
        new_rows: list[RawEventModel] = []
        # CRED 서브계정 catch-all (ncp_credential_theft 의 product=="SubAccount" 규칙).
        # 다른 유형의 *구체적* 매칭이 있으면 이 generic 매치는 양보한다.
        generic_targets = {"CT-NCP-IAM-002"}
        for ev in parsed:
            stats.total_events += 1
            # 확정 유형별 매칭 후보를 모두 수집 (primary 우선 순서 유지) 후,
            # CRED 서브계정 catch-all 보다 다른 유형의 구체적 매칭을 우선 채택한다.
            # 복합 케이스에서 권한상승 행위(Create sub account / Attach policy 등)가
            # CRED(IAM-002)로 흡수돼 부 유형 수집 완료율이 0% 되던 버그 fix (2026-06-05).
            # (matched_target_id 는 이벤트당 1개 컬럼이므로 단일 target 만 기록)
            cands: list[str] = []
            for itype in confirmed_types:
                cand = matchers.match(used_csp, itype, ev)
                if cand and cand in valid_target_ids and cand not in cands:
                    cands.append(cand)
            specific = [c for c in cands if c not in generic_targets]
            target_id: Optional[str] = (
                specific[0] if specific else (cands[0] if cands else None)
            )
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

    # ── 6. 표시용 필드 추출 (V-2 COLLECT 로그 테이블) ──────────
    @staticmethod
    def extract_display_fields(csp: str, raw: Optional[dict]) -> dict:
        """raw event dict → 표시용 4필드 (time / event_name / source_ip / user).

        V-2 COLLECT 로그 목록 테이블의 Timestamp·Event Name·Source IP·User 컬럼용.
        OCSF 전체 정규화 없이 CSP 포맷별 핵심 필드만 추출한다.
        - time 은 ISO8601 로 정규화 (파싱 실패 시 원본 문자열 fallback).
        - NHN: eventTime / eventId / userIp / userName(또는 userId)
        - NCP(naver): eventTime / action / content.sourceIp / content.actionUserName
        """
        empty = {"time": None, "event_name": None, "source_ip": None, "user": None}
        if not isinstance(raw, dict):
            return empty

        def _as_str(value: object) -> Optional[str]:
            return value if isinstance(value, str) else None

        if csp == "nhn":
            dt = nhn_parser.parse_event_time(raw.get("eventTime"))
            return {
                "time": dt.isoformat() if dt else _as_str(raw.get("eventTime")),
                "event_name": raw.get("eventId"),
                "source_ip": raw.get("userIp"),
                "user": raw.get("userName") or raw.get("userId"),
            }
        # naver (NCP)
        content = raw.get("content") if isinstance(raw.get("content"), dict) else {}
        dt = ncp_parser.parse_event_time(raw.get("eventTime"))
        return {
            "time": dt.isoformat() if dt else _as_str(raw.get("eventTime")),
            "event_name": raw.get("action"),
            "source_ip": content.get("sourceIp") or raw.get("sourceIp"),
            "user": content.get("actionUserName") or raw.get("actionUserName"),
        }
