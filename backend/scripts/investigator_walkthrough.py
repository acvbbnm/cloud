"""수사관 시점 E2E 검증 — 골든 시나리오 (NCP Sysdig 8분 Killchain).

목적:
  - 백엔드 API V1→V8 풀 흐름을 실제 사용자처럼 순회
  - 각 단계 응답이 시연_대본.md 기대값과 일치하는지 검증
  - 발견된 이슈를 종합 리포트로 출력 (보완점 정리)

사용:
  cd backend && python -m scripts.investigator_walkthrough

기대 출력:
  단계별 ✓/✗ + 응답 요약 + 마지막에 발견된 이슈 목록.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

import httpx

BASE = "http://127.0.0.1:8000"
SCENARIO = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "ncp_sysdig_8min_killchain.json"
TIMEOUT = 30.0
# 2026-05-25 — LLM cold-start (첫 chat / sherpa-kb 호출) 대응. chat 첫 호출 시 Ollama
# 모델 로드 + ChromaDB 임베더 초기화로 60~120s 까지 갈 수 있어 별도 큰 timeout.
TIMEOUT_LLM = 180.0

# 검증 결과 누적
issues: list[str] = []


def _log(msg: str) -> None:
    print(msg, flush=True)


def _hr() -> None:
    _log("-" * 70)


def _check(cond: bool, ok_msg: str, fail_msg: str) -> bool:
    if cond:
        _log(f"  ✓ {ok_msg}")
        return True
    _log(f"  ✗ {fail_msg}")
    issues.append(fail_msg)
    return False


def _post(path: str, body: dict, **kwargs) -> tuple[int, Any]:
    try:
        r = httpx.post(f"{BASE}{path}", json=body, timeout=TIMEOUT, **kwargs)
        return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
    except Exception as e:
        return -1, str(e)


def _get(path: str, **kwargs) -> tuple[int, Any]:
    try:
        r = httpx.get(f"{BASE}{path}", timeout=TIMEOUT, **kwargs)
        return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
    except Exception as e:
        return -1, str(e)


def _patch(path: str, body: dict) -> tuple[int, Any]:
    try:
        r = httpx.patch(f"{BASE}{path}", json=body, timeout=TIMEOUT)
        return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
    except Exception as e:
        return -1, str(e)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    _log("=" * 70)
    _log("수사관 시점 E2E 검증 — NCP Sysdig 8분 Killchain")
    _log("=" * 70)

    # ── 0. health check ──
    # 2026-05-25: /api/health 가 가벼운 ping 으로 분리됨 (server/db 만).
    # ollama/chromadb 실측은 /api/health?deep=true 명시적 호출.
    _log("\n[0] 사전 헬스 체크 (deep=true 로 ollama·chromadb 실측)")
    status, body = _get("/api/health?deep=true")
    _check(status == 200, f"backend /api/health 응답 {status}", f"backend 죽음 (status={status})")
    if isinstance(body, dict):
        _log(f"  data: {json.dumps(body.get('data', {}), ensure_ascii=False)}")
        ollama_status = body.get("data", {}).get("ollama")
        if ollama_status not in ("ollama", "running"):
            issues.append(f"ℹ health 엔드포인트가 ollama 실측 안 함 (현재 '{ollama_status}')")

    # ── 1. V-1 Step 0~1: case 생성 ──
    _log("\n[V-1 Step 0~1] POST /api/cases (UNCLASSIFIED, 후속 단서로 사고유형 추론)")
    create_payload = {
        "title": "NCP 콘솔 비정상 로그인 알람",
        "csp": "naver",
        "severity": "critical",
        "occurred_at": "2026-05-19T14:00:00Z",
        "incident_type": "UNCLASSIFIED",
        "tlp": "RED",
    }
    status, body = _post("/api/cases", create_payload)
    _check(
        status == 200 or status == 201,
        f"케이스 생성 응답 {status}",
        f"케이스 생성 실패 (status={status}, body={body})",
    )
    case_id: Optional[str] = None
    if isinstance(body, dict):
        data = body.get("data", {})
        case_id = data.get("caseId") or data.get("case_id")
        if not case_id:
            issues.append(f"응답에 caseId 없음: {body}")
        else:
            _log(f"  caseId = {case_id}")

    if not case_id:
        _log("[FATAL] caseId 없이 진행 불가")
        return 1

    # ── 2. V-1 Step 3: Discovery Loop — observable 추가 (PATCH) ──
    _log("\n[V-1 Step 3] PATCH /api/cases/{caseId} (observables + system_config)")
    patch_payload = {
        "observables": [
            {"type": "ip", "value": "185.220.101.42", "confidence": "high", "source": "Tor exit node"},
            {"type": "username", "value": "dev-ops-admin", "confidence": "high"},
        ],
        "system_config": {
            "object_storage": True,
            "public_ip": True,
            "activity_tracer": "enabled",
            "mfa": False,
        },
    }
    status, body = _patch(f"/api/cases/{case_id}", patch_payload)
    _check(status == 200, f"PATCH 응답 {status}", f"PATCH 실패 (status={status}, body={body})")

    # GET 으로 적용 확인
    status, body = _get(f"/api/cases/{case_id}")
    _check(status == 200, f"GET case 응답 {status}", f"GET 실패 (status={status})")
    if isinstance(body, dict):
        data = body.get("data", {})
        obs = data.get("observables", [])
        _check(
            isinstance(obs, list) and len(obs) >= 2,
            f"observables 적용됨 ({len(obs)}건)",
            f"observables 적용 안 됨: {obs}",
        )

    # ── 3. V-1 Step 4: Guide V2 (체크리스트) ──
    _log("\n[V-1 Step 4] GET /api/guide/v2?caseId=")
    status, body = _get(f"/api/guide/v2?caseId={case_id}")
    if status == 404:
        # 어쩌면 /api/guide 만 있을지도
        status2, body2 = _get(f"/api/guide?caseId={case_id}")
        if status2 == 200:
            _check(False, "", "guide/v2 미존재 (404) — 구버전 /api/guide 만 사용 가능")
            body = body2
        else:
            _check(False, "", f"guide·guide/v2 모두 실패 (v2={status}, v1={status2})")
    else:
        _check(status == 200, f"guide/v2 응답 {status}", f"guide/v2 실패 (status={status})")
    if isinstance(body, dict):
        data = body.get("data", {})
        rate = data.get("completionRate") or data.get("completion_rate")
        _log(f"  completionRate: {rate} (V-2 업로드 전이므로 0% 기대)")

    # ── 4. V-2: 로그 업로드 (multipart) ──
    _log("\n[V-2] POST /api/logs/upload (13건 ncp_sysdig)")
    if not SCENARIO.exists():
        _check(False, "", f"시나리오 파일 없음: {SCENARIO}")
    else:
        with SCENARIO.open("rb") as f:
            files = {"file": (SCENARIO.name, f, "application/json")}
            data = {"caseId": case_id}
            try:
                r = httpx.post(
                    f"{BASE}/api/logs/upload",
                    data=data,
                    files=files,
                    timeout=TIMEOUT,
                )
                status, body = r.status_code, r.json() if "application/json" in r.headers.get("content-type", "") else r.text
            except Exception as e:
                status, body = -1, str(e)
        # /api/logs/upload 는 신규 raw_events 생성이라 201 정상
        _check(status in (200, 201), f"업로드 응답 {status}", f"업로드 실패 (status={status}, body={body})")
        if isinstance(body, dict):
            d = body.get("data", {})
            # 실제 응답 키: totalEvents (raw 전체) / matched (카탈로그 매칭)
            uploaded = d.get("totalEvents", d.get("uploaded", d.get("total", 0)))
            matched = d.get("matched", 0)
            _log(f"  업로드: {uploaded}건, 매칭: {matched}건 (기대: 13건 / UNCLASSIFIED 면 matched=0 정상)")
            _check(uploaded == 13, f"uploaded={uploaded}", f"uploaded 기대 13 ≠ 실제 {uploaded}")
            # UNCLASSIFIED 케이스의 matched=0 은 P5 walkthrough fix 가 의도한 경고 동작
            if matched == 0 and any(w.get("code") == "UNCLASSIFIED_CASE" for w in d.get("warnings", [])):
                _log("  ℹ matched=0 은 UNCLASSIFIED 의 의도된 경고 — 회귀 아님")

    # ── 5. V-3 OCSF 정규화 ──
    _log("\n[V-3] POST /api/analysis/normalize")
    status, body = _post("/api/analysis/normalize", {"caseId": case_id})
    _check(status == 200, f"normalize 응답 {status}", f"normalize 실패 (status={status}, body={body})")
    if isinstance(body, dict):
        d = body.get("data", {})
        normalized = d.get("normalized", d.get("total", 0))
        _log(f"  정규화: {normalized}건 (기대 13)")

    # ── 6. V-3 ATT&CK 매핑 ──
    _log("\n[V-3 / V-6] POST /api/analysis/map")
    status, body = _post("/api/analysis/map", {"caseId": case_id})
    _check(status == 200, f"map 응답 {status}", f"map 실패 (status={status}, body={body})")
    if isinstance(body, dict):
        d = body.get("data", {})
        mapped = d.get("mapped", 0)
        _log(f"  매핑: {mapped}건")

    # ── 7. V-4 Gap detection ──
    _log("\n[V-4] POST /api/analysis/gap")
    status, body = _post("/api/analysis/gap", {"caseId": case_id})
    _check(status == 200, f"gap 응답 {status}", f"gap 실패 (status={status}, body={body})")
    if isinstance(body, dict):
        d = body.get("data", {})
        gap_type = d.get("gap_type") or d.get("gapType")
        completion = d.get("completionRate") or d.get("completion_rate")
        _log(f"  gap_type: {gap_type}, completionRate: {completion}")

    # ── 8. V-5 보드 상태 조회 ──
    _log("\n[V-5] GET /api/board?caseId=")
    status, body = _get(f"/api/board?caseId={case_id}")
    _check(status == 200, f"board 응답 {status}", f"board 실패 (status={status})")
    if isinstance(body, dict):
        d = body.get("data", {})
        nodes = d.get("nodes", [])
        edges = d.get("edges", [])
        _log(f"  nodes: {len(nodes)}, edges: {len(edges)} (초기 0/0 기대)")

    # ── 8-2. V-5 노드 추가 ──
    _log("\n[V-5] POST /api/board/nodes (T1078.004 후보 추가)")
    # attack 이벤트 ID 가져오기
    status, body = _get(f"/api/analysis/attack?caseId={case_id}")
    attack_id = None
    if isinstance(body, dict):
        attacks = body.get("data", {}).get("items", []) or body.get("data", [])
        for a in attacks:
            if isinstance(a, dict) and a.get("technique_id", "").startswith("T1078"):
                attack_id = a.get("attack_id") or a.get("attackId")
                break
    if attack_id:
        node_payload = {
            "caseId": case_id,
            "attackId": attack_id,
            "label": "T1078.004 (Initial Access)",
            "pos_x": 100,
            "pos_y": 100,
        }
        status, body = _post("/api/board/nodes", node_payload)
        _check(
            status == 200 or status == 201,
            f"노드 추가 응답 {status}",
            f"노드 추가 실패 (status={status}, body={body})",
        )
    else:
        _check(False, "", "attack_id 못 찾음 — 노드 추가 skip")

    # ── 9. V-7 보고서 생성 ──
    _log("\n[V-7] POST /api/report")
    status, body = _post("/api/report", {"caseId": case_id})
    # POST /api/report 는 신규 보고서 생성이라 201 정상
    _check(
        status in (200, 201),
        f"report 응답 {status}",
        f"report 실패 (status={status}, body={body})",
    )
    if isinstance(body, dict):
        d = body.get("data", {})
        sections = d.get("sections", {})
        section_count = len(sections) if isinstance(sections, dict) else len(sections or [])
        # 2026-05-25 P4: 9번째 섹션 (scope_disclaimer) 추가됨.
        _log(f"  sections: {section_count} (기대 ≥9, P4 scope_disclaimer 포함)")
        _check(section_count >= 9, f"sections={section_count}", f"sections={section_count} (9 미만)")

    # ── 10. V-8 사후 검증 ──
    _log("\n[V-8] GET /api/sherpa/validate-incident-type?caseId=")
    status, body = _get(f"/api/sherpa/validate-incident-type?caseId={case_id}")
    _check(status == 200, f"validate 응답 {status}", f"validate 실패 (status={status})")
    if isinstance(body, dict):
        d = body.get("data", {})
        verdict = d.get("verdict")
        review_status = d.get("status")
        message = d.get("message", "")
        _log(f"  status: {review_status}, verdict: {verdict}")
        _log(f"  message: {message[:100]}")

    # ── 11. V-8 chat (Ollama 미연결 시 fallback 메시지) ──
    # 2026-05-25 — chat 첫 호출은 LLM cold-start 60~120s 가능. TIMEOUT_LLM 사용.
    _log("\n[V-8] POST /api/sherpa/chat (간단 쿼리, LLM cold-start 시 최대 180s 대기)")
    chat_payload = {
        "caseId": case_id,
        "query": "T1078.004 자격증명 남용에 대해 알려주세요",
    }
    try:
        r = httpx.post(f"{BASE}/api/sherpa/chat", json=chat_payload, timeout=TIMEOUT_LLM)
        status, body = r.status_code, r.json() if "application/json" in r.headers.get("content-type", "") else r.text
    except Exception as e:
        status, body = -1, str(e)
    _check(status == 200, f"chat 응답 {status}", f"chat 실패 (status={status})")
    if isinstance(body, dict):
        d = body.get("data", {})
        text = d.get("text") or d.get("response", "")
        sources = d.get("sources", [])
        _log(f"  텍스트 길이: {len(text)} chars, 출처: {len(sources)}건")
        # Ollama 미연결 시 fallback 메시지 확인
        if "추가 확인 필요" in text or "fallback" in text.lower() or "응답이 지연" in text or "답변할 수 없습니다" in text:
            issues.append("ℹ Ollama 미연결 — chat 응답이 fallback 텍스트 (실 LLM 검증 불가)")

    # ── 12. V-8 KB stats ──
    # 2026-05-25 — kb 첫 호출 시 ChromaDB embedder cold-start 가능 (TIMEOUT_LLM).
    _log("\n[V-8] GET /api/sherpa/kb (ChromaDB cold-start 시 최대 180s 대기)")
    try:
        r = httpx.get(f"{BASE}/api/sherpa/kb", timeout=TIMEOUT_LLM)
        status, body = r.status_code, r.json() if "application/json" in r.headers.get("content-type", "") else r.text
    except Exception as e:
        status, body = -1, str(e)
    _check(status == 200, f"sherpa/kb 응답 {status}", f"sherpa/kb 실패 (status={status})")
    if isinstance(body, dict):
        d = body.get("data", {})
        total = d.get("total") or sum(d.get("by_category", {}).values() or [0])
        engine_info = d.get("engine", {})
        rag_info = d.get("rag", {})
        _log(f"  KB total: {total}")
        _log(f"  engine: {json.dumps(engine_info, ensure_ascii=False)[:120]}")
        _log(f"  rag: {json.dumps(rag_info, ensure_ascii=False)[:120]}")

    # ── 종합 리포트 ──
    _log("\n" + "=" * 70)
    _log("종합 결과")
    _log("=" * 70)
    if not issues:
        _log("✓ 모든 단계 통과 — 이슈 없음.")
    else:
        _log(f"⚠ 발견된 이슈 {len(issues)}건:")
        for i, msg in enumerate(issues, 1):
            _log(f"  {i}. {msg}")

    return 0 if not any(i.startswith("✗") or "실패" in i or "FATAL" in i for i in issues) else 1


if __name__ == "__main__":
    sys.exit(main())
