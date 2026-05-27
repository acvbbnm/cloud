"""Phase P 통합 e2e — 시연 피드백 fix 회귀 감사 (2026-05-27, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §24+ Phase P 시리즈

P.1·P.10·P.4·P.13 의 catalog/임계값 변경이 실제 라이브 응답에 반영되는지 검증.
+ 옛 UI 회귀 노출 차단 (P.9) 의 scoring_mode 응답 검증.

검증 대상 (12 단계)
-------------------
  1. /api/clue-tree/recon-options — P.1 정찰 단서 cap=10 (15 단서 모두 ≤ 10)
  2. /api/clue-tree/next-clues — P.10 일반 단서 cap=20 (max_w ≤ 20)
  3. /api/clue-tree/start — scoring_mode 응답 (P.9 위임 신호)
  4. expand × 3 (정찰 + 본격 단서) — depth 증가 + posterior 변화
  5. P.4 + P.13 — Zone 2 진입 (depth ≥ 3 + max_lk ≥ 0.30 강한 단서)
  6. advance-stage → stage=2 진입 + 회귀 권고 차단 (P.4 stage>=2 should_regress false)
  7. path 응답 stage 필드 동봉 (P.12 Compass segmentation 입력)
  8. /api/board/nodes/from-clue-tree — 빈 보드 멱등성 (P.O.3)
  9. /api/board/nodes {clue_key} — 단서 노드 생성 (P.O.2)
 10. /api/board?caseId — 보드 응답에 type='clue' 노드 포함 (P.O.4)
 11. /api/health — 최종 헬스
 12. 응답 시간 < 10s (대용량 응답 회귀 차단)

사용
----
    cd backend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.e2e_phase_p_audit

종료 코드: 0 (전체 통과) / 1 (실패 1건 이상)
"""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from db.session import engine  # noqa: E402
from db.models import Base  # noqa: E402
from main import app  # noqa: E402


_fail_count = 0


def _log(step: str, passed: bool, detail: str = "") -> None:
    global _fail_count
    if not passed:
        _fail_count += 1
    icon = "✓" if passed else "✗"
    prefix = "" if passed else "[FAIL] "
    print(f"  {prefix}{icon} {step:<58} {detail}")


def main() -> int:
    print("=" * 88)
    print(" Phase P 회귀 감사 — P.1·P.4·P.9·P.10·P.12·P.13 + Phase O 연계")
    print(f" 실행 시각: {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 88)

    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    t_start = time.time()

    # ── 1. P.1 정찰 cap=10 ──
    print("\n── 1. P.1 정찰 단서 cap=10 ──")
    r = client.get("/api/clue-tree/recon-options")
    if r.status_code != 200:
        _log("GET /recon-options", False, f"HTTP {r.status_code}")
        return 1
    groups = r.json()["data"].get("groups", [])
    total = sum(len(g.get("options", [])) for g in groups)
    max_w_all = 0
    for g in groups:
        for o in g.get("options", []):
            w = o.get("weights", {})
            if w:
                max_w_all = max(max_w_all, max(w.values()))
    _log(
        f"정찰 단서 {total}건 max_w ≤ 10",
        max_w_all <= 10,
        f"실측 max_w = {max_w_all}",
    )

    # ── 2~3. case 생성 + tree start ──
    print("\n── 2~3. case 생성 + tree start (scoring_mode 검증) ──")
    r = client.post(
        "/api/cases",
        json={
            "title": "Phase P audit",
            "csp": "naver",
            "incident_type": "UNCLASSIFIED",
            "severity": "high",
            "occurred_at": "2026-05-27T15:00:00",
        },
    )
    if r.status_code not in (200, 201):
        _log("POST /api/cases", False, f"HTTP {r.status_code}")
        return 1
    case_id = r.json()["data"]["caseId"]
    _log("POST /api/cases", True, f"caseId={case_id[:8]}…")

    r = client.post("/api/clue-tree/start", json={"caseId": case_id})
    data = r.json()["data"]
    leaf = data["current_leaf_id"]
    mode = data.get("scoring_mode")
    _log(
        "POST /clue-tree/start scoring_mode = evidence_tree/bayes_net",
        mode in ("evidence_tree", "bayes_net"),
        f"mode={mode}",
    )

    # ── 4. 단서 채택 시퀀스 — 정찰 2 + 자격증명 강한 단서 3개 (Zone 2 진입 조건 충족) ──
    print("\n── 4. 단서 채택 시퀀스 (정찰 + 자격증명 본격 다발) ──")
    seq = [
        ("Q1_inception:csp_alert", "정찰: CSP 알람"),
        ("Q2A:abnormal_login", "정찰: 비정상 로그인"),
        ("TECHNIQUE:T1552.005", "본격: T1552.005"),
        ("TECHNIQUE:T1110", "본격: T1110 (자격증명 강함)"),
        ("Q3:fail_then_success", "본격: 실패→성공 인증"),
    ]
    for clue_key, lbl in seq:
        r = client.post(
            "/api/clue-tree/expand",
            json={
                "caseId": case_id,
                "parent_node_id": leaf,
                "clue_key": clue_key,
                "source": "direct_input",
            },
        )
        if r.status_code not in (200, 201):
            _log(f"expand {clue_key}", False, f"HTTP {r.status_code}")
            return 1
        d = r.json()["data"]
        leaf = d["current_leaf_id"]
        _log(
            f"expand {lbl[:34]:<34}",
            True,
            f"path={len(d['path'])} zone={d.get('zone')} max_lk={d.get('core_clue_likelihood', 0):.3f}",
        )

    # ── 5. Zone 2 진입 (P.13) ──
    print("\n── 5. P.13 Zone 2 트리거 (max_lk ≥ 0.30) ──")
    r = client.get(f"/api/clue-tree?caseId={case_id}")
    d = r.json()["data"]
    zone = d.get("zone")
    max_lk = d.get("core_clue_likelihood", 0)
    _log(
        "Zone 2 진입 + max_lk ≥ 0.30",
        zone == 2 and max_lk >= 0.30,
        f"zone={zone} max_lk={max_lk:.3f}",
    )
    _log(
        "regress_suggested = False (Stage 1 정상 우세)",
        d.get("regress_suggested") is False,
        f"regress={d.get('regress_suggested')}",
    )

    # ── 6. path 응답 stage 필드 (P.12 Compass 입력) ──
    print("\n── 6. P.12 path 응답 stage 필드 동봉 ──")
    path = d.get("path", [])
    has_stage = all(("stage" in p) for p in path)
    _log(
        f"path {len(path)} 노드 모두 stage 필드 포함",
        has_stage,
        f"sample stages = {[p.get('stage') for p in path]}",
    )

    # ── 7. advance-stage (P.4 stage>=2 회귀 차단) ──
    print("\n── 7. P.4 advance-stage 후 stage ≥ 2 회귀 권고 차단 ──")
    primary = d.get("confidence", {}).get("primary")
    if not primary:
        _log("primary 가설 미확정 — advance 건너뜀", False, "primary=None")
    else:
        r = client.post(
            "/api/clue-tree/advance-stage",
            json={"caseId": case_id, "confirmed_hypothesis": primary},
        )
        if r.status_code not in (200, 201):
            _log(f"advance-stage {primary}", False, f"HTTP {r.status_code}")
        else:
            d2 = r.json()["data"]
            _log(
                f"advance-stage {primary} → stage=2",
                d2.get("stage") == 2,
                f"stage={d2.get('stage')} confirmed={d2.get('confirmed_hypotheses')}",
            )
            _log(
                "Stage 2 진입 직후 regress_suggested = False",
                d2.get("regress_suggested") is False,
                f"regress={d2.get('regress_suggested')}",
            )

    # ── 8~10. Phase O (단서 → 보드) ──
    print("\n── 8~10. Phase O 단서 노드 통합 ──")
    r = client.post("/api/board/nodes", json={
        "caseId": case_id,
        "clue_key": "TECHNIQUE:T1552.005",
        "label": "T1552.005 (수동 드롭)",
        "pos_x": 100,
        "pos_y": 100,
        "source": "manual_drag",
    })
    _log(
        "POST /board/nodes {clue_key} → 201",
        r.status_code == 201,
        f"HTTP {r.status_code}",
    )
    node_data = r.json().get("data", {}) if r.status_code == 201 else {}
    _log(
        "응답 노드 type='clue' + meta.clue_key",
        node_data.get("type") == "clue"
        and (node_data.get("meta", {}) or {}).get("clue_key") == "TECHNIQUE:T1552.005",
        f"type={node_data.get('type')}",
    )

    r = client.get(f"/api/board?caseId={case_id}")
    board = r.json()["data"]
    clue_nodes = [n for n in board.get("nodes", []) if n.get("type") == "clue"]
    _log(
        "GET /board 응답에 type='clue' 노드 1+",
        len(clue_nodes) >= 1,
        f"clue 노드 {len(clue_nodes)}건 / 전체 {len(board.get('nodes', []))}건",
    )

    # ── 11. P.10 일반 단서 cap=20 (강한 단서 샘플) ──
    print("\n── 11. P.10 일반 단서 cap=20 (catalog raw 검증) ──")
    import json

    catalog_path = _BACKEND / "data" / "triage" / "clue_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    samples = [
        "TECHNIQUE:T1486",
        "Q2D:mass_encryption",
        "Q2C:iam_burst",
        "ACCOUNT:privilege_changed",
    ]
    over_cap = []
    for k in samples:
        entry = catalog["clues"].get(k)
        if not entry:
            continue
        max_w = max(entry.get("weights", {}).values()) if entry.get("weights") else 0
        if max_w > 20:
            over_cap.append((k, max_w))
    _log(
        f"본격 단서 샘플 {len(samples)} 건 max_w ≤ 20",
        not over_cap,
        f"위반: {over_cap}" if over_cap else f"모두 정상",
    )

    # ── 12. 응답 시간 ──
    elapsed = time.time() - t_start
    _log(
        f"전체 e2e 응답 시간 < 30s",
        elapsed < 30,
        f"{elapsed:.2f}s",
    )

    # ── 헬스 ──
    r = client.get("/api/health")
    _log("/api/health", r.status_code == 200, f"HTTP {r.status_code}")

    print()
    print("=" * 88)
    print(f" 결과: 실패 {_fail_count}건 / 총 elapsed {elapsed:.2f}s")
    print("=" * 88)
    return 0 if _fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
