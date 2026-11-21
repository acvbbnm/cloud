"""Phase O 통합 e2e — Evidence Tree → 보드 bridge 시나리오 (2026-05-26, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §24

각 단계 = 프론트 사용자 액션 1개 → 백엔드 API 호출 정합 검증.

검증 대상 (10 단계)
-------------------
  1. POST /api/cases                                  — 케이스 생성
  2. POST /api/board/nodes/from-clue-tree (tree 없음) — 404 EVIDENCE_TREE_NOT_FOUND
  3. POST /api/clue-tree/start                        — 트리 시작
  4. POST /api/clue-tree/expand × 2                   — 단서 채택 2개
  5. POST /api/board/nodes/from-clue-tree (정상)      — 2 clue 노드 + 1 엣지 생성
  6. 응답 필드 정합 — created_nodes/skipped/created_edges
  7. clue 노드 meta 5필드 (type/clue_key/stage/source/tree_node_id)
  8. POST /api/board/nodes/from-clue-tree 2회 — 멱등 (모두 skipped)
  9. POST /api/board/nodes {clue_key + attack_id}     — 400 NODE_TYPE_AMBIGUOUS
 10. GET /api/board                                   — 보드에 단서 노드 type='clue' 반영

사용 (외부 서버 의존성 X — TestClient in-process)
-------------------------------------------------
    cd backend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.e2e_phase_o_bridge_test

종료 코드: 0 (전체 통과) / 1 (실패 1건 이상)
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# backend/ 경로 보장
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from db.session import engine  # noqa: E402
from db.models import Base  # noqa: E402
from main import app  # noqa: E402


# 결과 누적
_results: list[tuple[bool, str, str]] = []
_fail_count = 0


def _log(step: str, passed: bool, detail: str = "") -> None:
    global _fail_count
    if not passed:
        _fail_count += 1
    _results.append((passed, step, detail))
    icon = "✓" if passed else "✗"
    prefix = "" if passed else "[FAIL] "
    print(f"  {prefix}{icon} {step:<54} {detail}")


def _check_keys(d: dict, *keys: str) -> tuple[bool, str]:
    missing = [k for k in keys if k not in d]
    if missing:
        return False, f"missing: {missing}"
    return True, ""


def main() -> int:
    print("=" * 84)
    print(" Phase O 통합 e2e — Evidence Tree → 보드 bridge 시나리오")
    print(f" 실행 시각: {datetime.now().isoformat(timespec='seconds')}")
    print(" 모드: TestClient in-process")
    print("=" * 84)

    # DB 스키마 보장 (in-process — 외부 서버 X)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    # ── 1. 케이스 생성 ──
    print("\n── 1. 케이스 생성 ──")
    r = client.post(
        "/api/cases",
        json={
            "title": "Phase O bridge e2e",
            "csp": "naver",
            "incident_type": "UNCLASSIFIED",
            "severity": "high",
            "occurred_at": "2026-05-26T15:00:00",
        },
    )
    if r.status_code not in (200, 201):
        _log("POST /api/cases", False, f"HTTP {r.status_code}")
        return 1
    case_id = r.json()["data"]["caseId"]
    _log("POST /api/cases", True, f"caseId={case_id[:8]}…")

    # ── 2. tree 없을 때 bridge → 404 ──
    print("\n── 2. tree 없을 때 bridge → 404 EVIDENCE_TREE_NOT_FOUND ──")
    r = client.post("/api/board/nodes/from-clue-tree", json={"caseId": case_id})
    detail: Any = r.json().get("detail", {})
    code = detail.get("code") if isinstance(detail, dict) else None
    _log(
        "POST /from-clue-tree (tree 없음)",
        r.status_code == 404 and code == "EVIDENCE_TREE_NOT_FOUND",
        f"HTTP {r.status_code} · code={code}",
    )

    # ── 3. 트리 시작 ──
    print("\n── 3. 트리 시작 ──")
    r = client.post("/api/clue-tree/start", json={"caseId": case_id})
    data = r.json()["data"]
    leaf = data["current_leaf_id"]
    _log("POST /api/clue-tree/start", r.status_code in (200, 201), f"leaf={leaf[:8]}…")

    # ── 4. 단서 2개 채택 ──
    print("\n── 4. 단서 2개 채택 ──")
    r = client.post(
        "/api/clue-tree/expand",
        json={
            "caseId": case_id,
            "parent_node_id": leaf,
            "clue_key": "Q1_inception:csp_alert",
            "source": "direct_input",
        },
    )
    if r.status_code not in (200, 201):
        _log("expand #1", False, f"HTTP {r.status_code}")
        return 1
    leaf = r.json()["data"]["current_leaf_id"]
    _log("expand #1 (Q1_inception:csp_alert)", True, f"path={len(r.json()['data']['path'])}")

    r = client.post(
        "/api/clue-tree/expand",
        json={
            "caseId": case_id,
            "parent_node_id": leaf,
            "clue_key": "IP_ADDRESS:tor_vpn",
            "source": "direct_input",
        },
    )
    if r.status_code not in (200, 201):
        _log("expand #2", False, f"HTTP {r.status_code}")
        return 1
    _log("expand #2 (IP_ADDRESS:tor_vpn)", True, f"path={len(r.json()['data']['path'])}")

    # ── 5. bridge (정상) ──
    print("\n── 5. bridge (정상, include_edges=True) ──")
    r = client.post(
        "/api/board/nodes/from-clue-tree",
        json={"caseId": case_id, "include_edges": True},
    )
    if r.status_code not in (200, 201):
        _log("POST /from-clue-tree", False, f"HTTP {r.status_code}")
        return 1
    bridge_data = r.json()["data"]

    # ── 6. 응답 필드 정합 ──
    ok, err = _check_keys(bridge_data, "created_nodes", "skipped", "created_edges")
    _log("응답 3 필드 (created_nodes/skipped/created_edges)", ok, err)

    created = bridge_data["created_nodes"]
    skipped = bridge_data["skipped"]
    edges = bridge_data["created_edges"]
    _log(
        "생성 수량 — clue 노드 2 + 엣지 1 + skip 0",
        len(created) == 2 and len(skipped) == 0 and len(edges) == 1,
        f"nodes={len(created)} edges={len(edges)} skipped={len(skipped)}",
    )

    # ── 7. clue 노드 meta 5필드 ──
    print("\n── 7. clue 노드 meta 5필드 정합 ──")
    n0 = created[0]
    ok_type = n0.get("type") == "clue"
    _log("created_nodes[0].type == 'clue'", ok_type, f"type={n0.get('type')}")
    meta = n0.get("meta", {})
    needed = ["type", "clue_key", "stage", "source", "tree_node_id"]
    missing = [k for k in needed if k not in meta]
    _log(
        f"meta 5 필드 {needed}",
        not missing,
        f"meta keys = {list(meta.keys())}",
    )

    # ── 8. 멱등 — 두 번째 호출 ──
    print("\n── 8. 멱등 — 두 번째 bridge 호출 ──")
    r = client.post("/api/board/nodes/from-clue-tree", json={"caseId": case_id})
    d2 = r.json()["data"]
    _log(
        "created=0 + skipped=2 (already_on_board)",
        len(d2["created_nodes"]) == 0 and len(d2["skipped"]) == 2,
        f"created={len(d2['created_nodes'])} skipped={len(d2['skipped'])}",
    )
    reasons = {s.get("reason") for s in d2["skipped"]}
    _log("skip reason = {already_on_board}", reasons == {"already_on_board"}, f"reasons={reasons}")

    # ── 9. attack_id + clue_key 동시 → 400 ──
    print("\n── 9. attack_id ⊕ clue_key 위반 → 400 NODE_TYPE_AMBIGUOUS ──")
    r = client.post(
        "/api/board/nodes",
        json={
            "caseId": case_id,
            "attack_id": "fake-attack-id",
            "clue_key": "Q1_inception:audit",
        },
    )
    detail = r.json().get("detail", {})
    code = detail.get("code") if isinstance(detail, dict) else None
    _log(
        "POST /api/board/nodes (둘 다 지정)",
        r.status_code == 400 and code == "NODE_TYPE_AMBIGUOUS",
        f"HTTP {r.status_code} · code={code}",
    )

    # ── 10. GET /api/board — 보드에 clue 노드 반영 ──
    print("\n── 10. GET /api/board — 보드 상태 ──")
    r = client.get(f"/api/board?caseId={case_id}")
    board = r.json()["data"]
    nodes = board.get("nodes", [])
    clue_nodes = [n for n in nodes if n.get("type") == "clue"]
    _log(
        "board.nodes 중 type='clue' 노드 ≥ 2",
        len(clue_nodes) >= 2,
        f"total nodes={len(nodes)} clue nodes={len(clue_nodes)}",
    )

    # ── 요약 ──
    print()
    print("=" * 84)
    passed = sum(1 for r in _results if r[0])
    total = len(_results)
    print(f" 결과: {passed}/{total} PASS   ·   실패: {_fail_count}")
    print("=" * 84)
    return 0 if _fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
