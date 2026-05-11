"""DB 초기화 — 테이블 생성 + 시드 데이터 로딩.

사용법: python -m db.init_db
"""
import json
from pathlib import Path

from db.models import Base, CollectionTargetModel
from db.session import engine, SessionLocal
from config import settings


def create_tables() -> None:
    """모든 테이블 생성."""
    Base.metadata.create_all(bind=engine)
    print("[OK] 테이블 생성 완료")


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
    seed_collection_targets()
    print("[OK] DB 초기화 완료")


if __name__ == "__main__":
    init()
