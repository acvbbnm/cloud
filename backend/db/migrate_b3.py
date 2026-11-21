"""DB 마이그레이션 — dev3 B-3: incident_cases 신규 칼럼 5종.

V-1 재설계 청사진 §5.2 정합.
  + title                     VARCHAR(200) NULL          — 사건 제목 (기존 row 호환 위해 NULL 허용)
  + tlp                       VARCHAR(16)  NOT NULL DEFAULT 'AMBER'
  + observables               JSON         NOT NULL DEFAULT '[]'
  + secondary_incident_types  JSON         NULL
  + triage_state              JSON         NULL

특징:
  - idempotent — 이미 칼럼이 있으면 스킵.
  - 신규 DB 환경에서는 init_db.py 의 create_all() 이 이미 5종 칼럼을 포함하므로
    본 스크립트는 SKIP 만 출력하고 종료.
  - 기존 DB (dev2 / 이전 dev3) 사용자는 본 스크립트로 ALTER TABLE 5회 실행.

사용법:
  python -m db.migrate_b3
"""
from sqlalchemy import text

from db.session import engine


# (칼럼명, ALTER TABLE DDL) 튜플 5개
_ADDITIONS: list[tuple[str, str]] = [
    ("title", "ALTER TABLE incident_cases ADD COLUMN title VARCHAR(200)"),
    (
        "tlp",
        "ALTER TABLE incident_cases ADD COLUMN tlp VARCHAR(16) NOT NULL DEFAULT 'AMBER'",
    ),
    (
        "observables",
        "ALTER TABLE incident_cases ADD COLUMN observables JSON NOT NULL DEFAULT '[]'",
    ),
    (
        "secondary_incident_types",
        "ALTER TABLE incident_cases ADD COLUMN secondary_incident_types JSON",
    ),
    (
        "triage_state",
        "ALTER TABLE incident_cases ADD COLUMN triage_state JSON",
    ),
]


def _existing_columns(conn) -> set[str]:
    """incident_cases 의 현재 칼럼명 집합 (SQLite PRAGMA)."""
    rows = conn.execute(text("PRAGMA table_info(incident_cases)")).fetchall()
    # PRAGMA table_info 결과: (cid, name, type, notnull, dflt_value, pk)
    return {row[1] for row in rows}


def migrate_b3() -> dict[str, str]:
    """B-3 칼럼 5종 추가. 이미 존재하는 칼럼은 SKIP.

    Returns:
        {column_name: "added" | "skipped"} 결과 dict.
    """
    result: dict[str, str] = {}
    with engine.connect() as conn:
        existing = _existing_columns(conn)
        for col_name, ddl in _ADDITIONS:
            if col_name in existing:
                result[col_name] = "skipped"
                print(f"[SKIP] {col_name} 이미 존재")
                continue
            conn.execute(text(ddl))
            conn.commit()
            result[col_name] = "added"
            print(f"[OK] 추가: {col_name}")
    return result


if __name__ == "__main__":
    print("──── dev3 B-3 마이그레이션 시작 ────")
    summary = migrate_b3()
    added = sum(1 for v in summary.values() if v == "added")
    skipped = sum(1 for v in summary.values() if v == "skipped")
    print(f"──── 완료: 추가 {added}건 / 스킵 {skipped}건 ────")
