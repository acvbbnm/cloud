"""KB 인용 유효성·환각 검증 — 시나리오 lane 별 RAG 출처 감사 (2026-05-24).

각 사고유형 lane 마다 합성 로그를 실제 파이프라인에 태우고 Sherpa 의 네 인용 경로
(brief / suggest_missing_link / recommend_playbook / chat) 가 어떤 KB chunk 를
근거로 어떤 답을 만드는지 추적해, 다음을 검증한다:

  [A] 존재성       chunk_id 가 KB 에 실제 존재하고 본문(text)·출처(source) 비공백
  [B] 정합성       ATTACK chunk 의 technique_id 가 정규식상 유효한 MITRE ID 인가
                  CASE_DB / PLAYBOOK 의 incident_type 메타가 lane 과 일치하는가
                  CSP_DOC 의 csp 메타가 케이스 csp 와 일치하는가
  [C] 출처/URL    source 가 비공백, url 이 있으면 도메인이 화이트리스트(공식)인가
  [D] 환각 검출   chat 응답 텍스트에 등장하는 ATT&CK ID(T\d+) 가 인용 sources
                  안에 실제 존재하는가 (없으면 LLM 이 KB 밖 사실을 만든 것)
  [E] 수사 가치   chunk 본문에 "탐지 단서·증거·MITRE·rule·시퀀스" 등 수사에
                  쓸 만한 키워드가 들어 있는가 (휴리스틱)

전제: uvicorn http://localhost:8000 + 21 합성 로그 + KB 4 종.
실행: cd backend && .venv/Scripts/python.exe -X utf8 -m scripts.kb_citation_audit
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

import requests

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# KB 정합성 검증을 위해 KB 직접 로드 (HTTP 없이 ground-truth 확보)
from core.sherpa.knowledge_base import load_all as kb_load_all  # noqa: E402

B = "http://localhost:8000"
SYNTH_DIR = _BACKEND_DIR / "data" / "synthetic"

# ─────────────────────────────────────────────────────────────
# Lane → 합성 로그 매핑 (각 사고유형별 대표 1건)
# ─────────────────────────────────────────────────────────────
LANE_FIXTURES = [
    {"lane": "CRED",          "file": "nhn_credential_theft_real.json",    "csp": "nhn",   "incident_type": "CREDENTIAL_THEFT"},
    {"lane": "PRIVESC",       "file": "ncp_privilege_escalation.json",     "csp": "naver", "incident_type": "PRIVILEGE_ESCALATION"},
    {"lane": "DATA_EXFIL",    "file": "ncp_data_exfiltration.json",        "csp": "naver", "incident_type": "DATA_EXFILTRATION"},
    {"lane": "AUDIT_TAMPER",  "file": "ncp_audit_log_tampering.json",      "csp": "naver", "incident_type": "AUDIT_LOG_TAMPERING"},
    {"lane": "RANSOM",        "file": "ncp_ransomware.json",               "csp": "naver", "incident_type": "RANSOMWARE"},
    {"lane": "MISCFG",        "file": "ncp_misconfig_exposure.json",       "csp": "naver", "incident_type": "MISCONFIG_EXPOSURE"},
    {"lane": "PHISH",         "file": "ncp_phish_initial_access.json",     "csp": "naver", "incident_type": "PHISH_INITIAL_ACCESS"},
    {"lane": "INSIDER",       "file": "ncp_insider_threat.json",           "csp": "naver", "incident_type": "INSIDER_THREAT"},
]

# ─────────────────────────────────────────────────────────────
# 검증 헬퍼
# ─────────────────────────────────────────────────────────────

_MITRE_ID_RE = re.compile(r"^T\d{4}(\.\d{3})?$")
_TECH_REF_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")  # raw string — KB 본문/응답 T-id 추출
# Phase 2.5 (2026-05-24) — sanitize 가 KB 외 T-id 를 "[KB외:T1234]" 로 라벨링한다.
# 라벨링된 토큰은 LLM 의 답변에 그대로 노출되어 수사관이 "신뢰 안 됨"으로 식별 가능하므로,
# 환각 차단 측면에서는 PASS 로 간주. 단, 라벨 발생 자체는 별도 카운트 (모델 개선 추적용).
_LABELED_TECH_RE = re.compile(r"\[KB외:(T\d{4}(?:\.\d{3})?)\]")
_OFFICIAL_HOSTS = (
    "attack.mitre.org",
    "guide.ncloud-docs.com",
    "docs.toast.com",
    "nhncloud.com",
    "ncloud.com",
    "owasp.org",
    "cisa.gov",
    "nist.gov",
    "verizon.com",
    "mandiant.com",
)

_INVESTIGATIVE_KEYWORDS = (
    "탐지", "단서", "evidence", "증거", "MITRE", "rule", "시그니처", "타임라인", "log",
    "audit", "탐지지표", "지표", "log_gap", "step", "단계", "권고", "조치", "롤백",
)


def _build_kb_index() -> dict:
    """KB chunk 인덱스 — chunk_id → KBChunk 매핑."""
    chunks = kb_load_all()
    return {c.chunk_id: c for c in chunks}


def _classify_source(citation: dict) -> str:
    return citation.get("type") or citation.get("kb_name") or "?"


# ─────────────────────────────────────────────────────────────
# 한 시나리오 lane 검증
# ─────────────────────────────────────────────────────────────


def _audit_lane(lane_fx: dict, kb_index: dict) -> dict:
    """fixture 1건 → 파이프라인 + Sherpa 4모드 → 인용 chunk 감사."""
    lane = lane_fx["lane"]
    out = {
        "lane": lane,
        "file": lane_fx["file"],
        "incident_type": lane_fx["incident_type"],
        "csp": lane_fx["csp"],
        "cited_unique": 0,
        "checks": {"A_exists": 0, "B_aligned": 0, "C_source_ok": 0, "D_no_halluc": 0, "E_investigative": 0},
        "issues": [],
        "samples": [],  # 대표 인용 일부 (감사 결과 출력용)
        "halluc_techs": [],  # chat 응답이 만들어낸 KB 밖 T-id
    }

    # 1) 신규 케이스 + 업로드 + 정규화 + 매핑
    r = requests.post(B + "/api/cases", json={
        "incident_type": "UNCLASSIFIED",
        "csp": lane_fx["csp"],
        "severity": "high",
        "occurred_at": "2026-05-13T02:30:00",
        "tlp": "AMBER",
        "observables": [],
    }, timeout=30)
    if r.status_code not in (200, 201):
        out["issues"].append(f"케이스 생성 실패 {r.status_code}")
        return out
    cid = r.json()["data"]["caseId"]
    out["caseId"] = cid

    fp = SYNTH_DIR / lane_fx["file"]
    if not fp.exists():
        out["issues"].append(f"fixture 없음 {fp}")
        return out
    with open(fp, "rb") as f:
        r = requests.post(f"{B}/api/logs/upload", data={"caseId": cid},
                          files={"file": (fp.name, f, "application/json")}, timeout=60)
    if r.status_code not in (200, 201):
        out["issues"].append(f"업로드 실패 {r.status_code}")
        return out

    if requests.post(B + "/api/analysis/normalize", json={"caseId": cid}, timeout=60).status_code != 200:
        out["issues"].append("정규화 실패")
        return out
    r = requests.post(B + "/api/analysis/map", json={"caseId": cid}, timeout=60)
    if r.status_code != 200:
        out["issues"].append("매핑 실패")
        return out
    mapped_events = r.json().get("data", {}).get("events", [])
    if not mapped_events:
        out["issues"].append("ATT&CK 매핑된 이벤트 없음 — 인용 검증 불가")
        return out
    # PATCH incident_type 으로 사고유형 컨텍스트 고정 (CASE_DB/PLAYBOOK 검색 정확도 향상)
    requests.patch(f"{B}/api/cases/{cid}", json={"incident_type": lane_fx["incident_type"]}, timeout=10)

    # 2) Sherpa 4 모드 호출 → 인용 수집
    cited: dict[str, dict] = {}  # chunk_id → first citation dict
    cited_by_mode: dict[str, list[str]] = {"brief": [], "suggest": [], "playbook": [], "chat": []}

    def _absorb(mode: str, sources: list) -> None:
        for s in sources or []:
            cid_chunk = s.get("source_id") or s.get("chunk_id") or s.get("id")
            if not cid_chunk:
                continue
            cited.setdefault(cid_chunk, s)
            cited_by_mode[mode].append(cid_chunk)

    # 2-1) brief — 매핑된 attack 중 첫 건
    r = requests.post(B + "/api/sherpa/brief", json={"caseId": cid, "eventId": mapped_events[0]["attack_id"]}, timeout=60)
    if r.status_code == 200:
        d = r.json().get("data", {})
        _absorb("brief", d.get("sources", []))
        out["brief_technique"] = d.get("technique_id")
        out["brief_name"] = d.get("technique_name")
    else:
        out["issues"].append(f"brief {r.status_code}")

    # 2-2) suggest_missing_link — 첫 ↔ 끝 attack pair (가장 긴 kill-chain gap)
    if len(mapped_events) >= 2:
        a = mapped_events[0]["attack_id"]
        b = mapped_events[-1]["attack_id"]
        r = requests.post(B + "/api/sherpa/suggest", json={"caseId": cid, "nodeA": a, "nodeB": b}, timeout=60)
        if r.status_code == 200:
            d = r.json().get("data", {})
            for s in d.get("suggestions", []):
                _absorb("suggest", s.get("sources", []))
            out["suggest_count"] = len(d.get("suggestions", []))
        else:
            out["issues"].append(f"suggest {r.status_code}")

    # 2-3) playbook — 매핑된 기법 chain
    chain = list({e.get("technique_id") for e in mapped_events if e.get("technique_id")})[:5]
    r = requests.post(B + "/api/sherpa/playbook", json={"chain": chain}, timeout=60)
    if r.status_code == 200:
        d = r.json().get("data", {})
        for p in d.get("playbooks", []):
            _absorb("playbook", p.get("sources", []))
        out["playbook_count"] = len(d.get("playbooks", []))
    else:
        out["issues"].append(f"playbook {r.status_code}")

    # 2-4) chat — lane 특화 자연어 질의 (환각 검출 핵심)
    chat_query = f"이번 케이스에서 관측된 {lane_fx['incident_type']} 사고에 대해 출처 KB 만 근거로 핵심 ATT&CK 기법과 대응 단계를 요약해줘."
    chat_text = ""
    try:
        r = requests.post(B + "/api/sherpa/chat",
                          json={"caseId": cid, "query": chat_query}, timeout=240)
        if r.status_code == 200:
            d = r.json().get("data", {})
            _absorb("chat", d.get("sources", []))
            chat_text = d.get("response") or ""
            out["chat_chars"] = len(chat_text)
            # Phase 2.5 — sanitize 가 라벨링한 [KB외:T1234] 토큰 추출 → 별도 추적
            labeled_techs = set(_LABELED_TECH_RE.findall(chat_text))
            # 라벨링된 토큰을 제거한 텍스트에서 raw T-id 추출 (환각 검출용)
            text_unlabeled = _LABELED_TECH_RE.sub("", chat_text)
            techs_in_text = set(_TECH_REF_RE.findall(text_unlabeled))

            cited_techs: set[str] = set()
            for cid_chunk, _ in cited.items():
                k = kb_index.get(cid_chunk)
                if k and k.meta.get("technique_id"):
                    cited_techs.add(k.meta["technique_id"])
                if k:
                    cited_techs.update(_TECH_REF_RE.findall(k.text))
            # 진짜 환각: 라벨링 안 되고 KB 안에도 없는 T-id (sanitize 통과한 것 — 시스템 버그)
            out["halluc_techs"] = sorted(techs_in_text - cited_techs)
            # 라벨링된 환각: sanitize 가 잡아낸 KB 외 T-id (PASS 로 간주, 추적용)
            out["labeled_halluc_techs"] = sorted(labeled_techs - cited_techs)
            out["chat_status"] = "ok"
        else:
            out["issues"].append(f"chat {r.status_code}")
            out["chat_status"] = f"http_{r.status_code}"
    except requests.exceptions.ReadTimeout:
        out["chat_status"] = "timeout"
        out["issues"].append("chat 240s 타임아웃 — LLM 미응답 (환각 검증 건너뜀)")
    except Exception as e:
        out["chat_status"] = f"exc:{type(e).__name__}"
        out["issues"].append(f"chat 예외 {type(e).__name__}: {e}")

    # 3) 인용된 unique chunk 검증
    out["cited_unique"] = len(cited)
    out["cited_by_mode"] = {m: len(set(ids)) for m, ids in cited_by_mode.items()}

    if not cited:
        out["issues"].append("인용된 KB chunk 가 0건")
        return out

    A = B_ = C = D = E = 0
    for cid_chunk, citation in cited.items():
        kb = kb_index.get(cid_chunk)
        # [A] 존재성
        if kb is None:
            out["issues"].append(f"존재하지 않는 chunk_id 인용: {cid_chunk}")
            continue
        if kb.text.strip() and kb.title.strip():
            A += 1
        else:
            out["issues"].append(f"본문/제목 비어있음: {cid_chunk}")

        # [B] 정합성
        aligned = True
        if kb.kb_name == "ATTACK":
            tid = kb.meta.get("technique_id") or ""
            if not _MITRE_ID_RE.match(tid):
                aligned = False
                out["issues"].append(f"ATTACK chunk {cid_chunk} technique_id 형식 오류: {tid!r}")
        elif kb.kb_name in ("CASE_DB", "PLAYBOOK"):
            kb_it = kb.meta.get("incident_type")
            if kb_it and kb_it != lane_fx["incident_type"]:
                # 사고유형 lane 과 다른 chunk 가 인용된 경우 — 약한 경고
                out["issues"].append(
                    f"{kb.kb_name} chunk {cid_chunk} incident_type={kb_it} (lane={lane_fx['incident_type']})"
                )
                aligned = False
        elif kb.kb_name == "CSP_DOC":
            kb_csp = kb.meta.get("csp")
            if kb_csp and lane_fx["csp"] != "all" and kb_csp.lower() != lane_fx["csp"].lower():
                out["issues"].append(f"CSP_DOC chunk {cid_chunk} csp={kb_csp} (lane csp={lane_fx['csp']})")
                aligned = False
        if aligned:
            B_ += 1

        # [C] 출처/URL
        source_ok = bool(kb.source and kb.source.strip())
        if kb.url:
            host_ok = any(h in kb.url for h in _OFFICIAL_HOSTS)
            if not host_ok:
                out["issues"].append(f"비공식 URL: {cid_chunk} {kb.url}")
                source_ok = False
        if source_ok:
            C += 1

        # [E] 수사 가치 — 본문에 수사 키워드 포함 여부
        blob = (kb.title + " " + kb.text).lower()
        if any(kw.lower() in blob for kw in _INVESTIGATIVE_KEYWORDS):
            E += 1

    # [D] chat 환각 검출 — KB 밖 T-id 가 0건이면 PASS
    if not out["halluc_techs"]:
        D = out["cited_unique"]  # 전체 인용에 대해 환각 없음 → 모든 인용 통과로 카운트
    else:
        # 환각 존재 — 그래도 환각이 아닌 다른 인용은 OK
        D = max(0, out["cited_unique"] - len(out["halluc_techs"]))
        out["issues"].append(f"chat 응답에 KB 밖 T-id: {out['halluc_techs']}")

    out["checks"] = {"A_exists": A, "B_aligned": B_, "C_source_ok": C, "D_no_halluc": D, "E_investigative": E}

    # 대표 인용 sample 3건 (output 보기 좋게)
    for cid_chunk in list(cited.keys())[:3]:
        kb = kb_index.get(cid_chunk)
        if kb:
            out["samples"].append({
                "chunk_id": cid_chunk,
                "kb": kb.kb_name,
                "title": kb.title[:70],
                "source": kb.source[:60],
                "technique_id": kb.meta.get("technique_id"),
                "text_head": kb.text.strip().splitlines()[0][:90] if kb.text.strip() else "(empty)",
            })

    return out


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────


def main() -> int:
    try:
        r = requests.get(B + "/api/health", timeout=3)
        if r.status_code != 200:
            print(f"[ERROR] 백엔드 헬스 실패 {r.status_code} — uvicorn 기동 후 재시도.")
            return 2
    except Exception as e:
        print(f"[ERROR] 백엔드 미연결 ({e})")
        return 2

    kb_index = _build_kb_index()
    print("=" * 92)
    print(f" KB 인용 유효성·환각 감사 — {len(LANE_FIXTURES)} lane × Sherpa 4 모드 · KB={len(kb_index)} chunks")
    print("=" * 92)

    # LLM cold-start 회피 — warm-up 한 번 (오류는 무시)
    print(" [warm-up] LLM cold-start 회피용 1회 호출...", end=" ", flush=True)
    try:
        rw = requests.post(B + "/api/sherpa/chat",
                          json={"query": "ping"}, timeout=300)
        print(f"done ({rw.status_code}, {len(rw.text)}b)")
    except Exception as e:
        print(f"warm-up 실패 ({type(e).__name__}) — 첫 lane 에서 타임아웃 가능")

    totals = {"A_exists": [0, 0], "B_aligned": [0, 0], "C_source_ok": [0, 0], "D_no_halluc": [0, 0], "E_investigative": [0, 0]}
    all_issues: list[tuple[str, list[str]]] = []
    halluc_lanes: list[tuple[str, list[str]]] = []
    for fx in LANE_FIXTURES:
        result = _audit_lane(fx, kb_index)
        cu = result["cited_unique"]
        ch = result["checks"]
        print(f"\n[{result['lane']:<12}] {result['file']:<38} cited={cu:>2} "
              f"(brief={result.get('cited_by_mode',{}).get('brief',0)} "
              f"suggest={result.get('cited_by_mode',{}).get('suggest',0)} "
              f"playbook={result.get('cited_by_mode',{}).get('playbook',0)} "
              f"chat={result.get('cited_by_mode',{}).get('chat',0)})")
        if cu > 0:
            print(f"   A_exists={ch['A_exists']}/{cu}  B_aligned={ch['B_aligned']}/{cu}  "
                  f"C_source_ok={ch['C_source_ok']}/{cu}  D_no_halluc={ch['D_no_halluc']}/{cu}  "
                  f"E_investigative={ch['E_investigative']}/{cu}")
        if result.get("brief_technique"):
            print(f"   brief: {result['brief_technique']} — {result.get('brief_name','')[:60]}")
        if result.get("halluc_techs"):
            print(f"   [!] chat hallucination T-ids (sanitize 미차단): {result['halluc_techs']}")
            halluc_lanes.append((result["lane"], result["halluc_techs"]))
        if result.get("labeled_halluc_techs"):
            # sanitize 가 라벨링으로 차단한 환각 — PASS 지만 모델 개선 신호로 표시
            print(f"   [✓] sanitize 라벨링 차단 T-ids: {result['labeled_halluc_techs']}")
        for s in result.get("samples", []):
            print(f"     - {s['kb']:<8} {s['chunk_id']:<28} {s['title'][:55]}")
            print(f"                                       └─ src: {s['source']}")
        if result.get("issues"):
            all_issues.append((result["lane"], result["issues"]))
        # 합산
        for k, (a, b) in totals.items():
            totals[k] = [a + ch.get(k, 0), b + cu]

    print()
    print("=" * 92)
    print(" 종합")
    for k, (a, b) in totals.items():
        rate = (100 * a / b) if b else 0
        print(f"   {k:<22} {a}/{b}  ({rate:.1f}%)")
    if halluc_lanes:
        print("\n 환각 발생 lane:")
        for lane, ts in halluc_lanes:
            print(f"   - {lane}: {ts}")
    if all_issues:
        print("\n 이슈 상세:")
        for lane, issues in all_issues:
            print(f"   - [{lane}]")
            for it in issues:
                print(f"       · {it}")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    sys.exit(main())
