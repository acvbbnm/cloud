"""DB 초기화 — 테이블 생성 + 시드 데이터 로딩 + dev3 컬럼 마이그레이션.

사용법: python -m db.init_db
"""
import json
from pathlib import Path

from sqlalchemy import inspect, text

from db.models import Base, CollectionTargetModel
from db.session import engine, SessionLocal
from config import settings


# dev3 §5.2 — incident_cases 신규 5컬럼.
# SQLite ALTER TABLE ADD COLUMN 으로 안전하게 추가 (NOT NULL 제약 없는 형태).
_DEV3_COLUMNS = {
    "title": "VARCHAR(200)",
    "tlp": "VARCHAR(16) DEFAULT 'AMBER'",
    "observables": "JSON",
    "secondary_incident_types": "JSON",
    "triage_state": "JSON",
}


def create_tables() -> None:
    """모든 테이블 생성 (멱등). 기존 테이블은 건드리지 않음."""
    Base.metadata.create_all(bind=engine)
    print("[OK] 테이블 생성 완료")


def _migrate_dev3_columns() -> None:
    """incident_cases 에 dev3 신규 5컬럼 추가 (멱등).

    SQLite 는 ALTER TABLE ADD COLUMN 지원. 컬럼 존재 시 skip.
    기존 row 는 NULL 또는 default(AMBER) 값으로 채워짐.
    """
    insp = inspect(engine)
    if "incident_cases" not in insp.get_table_names():
        # create_tables() 가 먼저 호출되었어야 함 — 신규 row 는 신 스키마로 생성됨
        return

    existing_cols = {c["name"] for c in insp.get_columns("incident_cases")}
    added: list[str] = []
    with engine.begin() as conn:
        for col_name, col_def in _DEV3_COLUMNS.items():
            if col_name in existing_cols:
                continue
            conn.execute(
                text(f"ALTER TABLE incident_cases ADD COLUMN {col_name} {col_def}")
            )
            added.append(col_name)
    if added:
        print(f"[OK] incident_cases 컬럼 추가: {', '.join(added)}")
    else:
        print("[SKIP] incident_cases dev3 컬럼 이미 존재")


def seed_collection_targets() -> None:
    """collection_targets 시드 데이터 로딩."""
    db = SessionLocal()
    try:
        existing = db.query(CollectionTargetModel).count()
        if existing > 0:
            print(f"[SKIP] collection_targets 이미 {existing}건 존재")
            return

        seed_dir = settings.COLLECTION_TARGETS_DIR
        if not seed_dir.exists():
            print(f"[WARN] 시드 디렉토리 없음: {seed_dir}")
            return

        count = 0
        for json_file in sorted(seed_dir.glob("*.json")):
            with open(json_file, "r", encoding="utf-8") as f:
                targets = json.load(f)

            for t in targets:
                model = CollectionTargetModel(
                    target_id=t["target_id"],
                    incident_type=t["incident_type"],
                    csp=t["csp"],
                    log_type=t["log_type"],
                    evidence_role=t["evidence_role"],
                    storage_path=t.get("storage_path"),
                    retention_days=t.get("retention_days"),
                    priority=t.get("priority", 5),
                    description=t.get("description"),
                )
                db.add(model)
                count += 1

        db.commit()
        print(f"[OK] collection_targets {count}건 시드 완료")
    finally:
        db.close()


def init() -> None:
    """DB 초기화 전체 실행."""
    create_tables()
    _migrate_dev3_columns()
    seed_collection_targets()
    print("[OK] DB 초기화 완료")


if __name__ == "__main__":
    init()
