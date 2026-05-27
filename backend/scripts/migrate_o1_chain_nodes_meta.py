"""Phase O.1 마이그레이션 — chain_nodes 에 meta JSON 컬럼 추가 (2026-05-26, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §24 Phase O Evidence Board

동기:
    단서를 V-5 1st-class 보드 노드로 격상 (사용자 비전 2026-05-26).
    type='clue' 노드는 attack_id=NULL + meta={'type': 'clue', 'clue_key': ...}
    구조로 저장. 기존 ATT&CK 노드는 meta=NULL 유지 (legacy 호환).

idempotent — 컬럼이 이미 있으면 skip.

사용
----
    cd backend && .venv/Scripts/python.exe -m scripts.migrate_o1_chain_nodes_meta
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from config import settings


def main() -> int:
    db_url = settings.DB_URL
    if not db_url.startswith("sqlite:///"):
        print(f"[FATAL] SQLite 외 DB 미지원: {db_url}")
        return 2

    db_path = db_url.replace("sqlite:///", "")
    if not Path(db_path).exists():
        # 새 DB — init_db 가 처리
        print(f"DB 없음 ({db_path}) — init_db 실행 시 자동 생성됨. 마이그레이션 skip.")
        return 0

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        # 기존 컬럼 확인
        cur.execute("PRAGMA table_info(chain_nodes)")
        cols = [row[1] for row in cur.fetchall()]
        if "meta" in cols:
            print("✓ chain_nodes.meta 이미 존재 — skip")
            return 0

        cur.execute("ALTER TABLE chain_nodes ADD COLUMN meta JSON")
        conn.commit()
        print("✓ chain_nodes.meta JSON 컬럼 추가 완료")

        # 확인
        cur.execute("PRAGMA table_info(chain_nodes)")
        cols_after = [row[1] for row in cur.fetchall()]
        print(f"  현재 컬럼 ({len(cols_after)}개): {cols_after}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
