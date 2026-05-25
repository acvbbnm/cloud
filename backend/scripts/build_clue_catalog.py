"""Phase A.2 — 단서 카탈로그 자동 추출 스크립트 (2026-05-25, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §5, §9, §17.A

입력
----
    backend/data/triage/decision_tree.json  — 22 question 노드 × 99 options
    backend/data/triage/weights.json        — likelihood weights + clue_types + partial_techniques

출력
----
    backend/data/triage/clue_catalog.json   — Evidence Tree 패러다임의 단서 카탈로그

추출 규칙
---------
A. `decision_tree.json` 각 question 의 option 1개 → 단서 1개
   - clue_key = option.weight_key (예: "Q5_CRED:tor_vpn")
   - category = node_id (예: "Q5_CRED")
   - value    = option.id
   - label    = option.label
   - source   = "decision_tree"
   - weights  = weights.json:decision_tree_answers[weight_key]  (있으면)
B. `weights.json:clue_types` 각 항목 (24개) → 단서 1개
   - clue_key = key (예: "IP_ADDRESS:tor_vpn")
   - source   = "clue_input"
C. `weights.json:partial_analysis_techniques` 각 ATT&CK 기법 ID → 단서 1개
   - clue_key = "TECHNIQUE:{id}" (예: "TECHNIQUE:T1078.004")
   - source   = "log_analysis"

PDF §17.A 채택 — `outcome_flags` 정형화
---------------------------------------
각 단서에 정형 Boolean·enum 정보 추가 (Google Chronicle Rule-to-Outcome 패턴).
weight_key 패턴 기반 휴리스틱으로 자동 생성. Phase B 에서 API 응답에 동봉.

실행
----
    python backend/scripts/build_clue_catalog.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# 경로 — 스크립트 위치 기준
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
DATA_DIR = BACKEND_DIR / "data" / "triage"

DECISION_TREE_PATH = DATA_DIR / "decision_tree.json"
WEIGHTS_PATH = DATA_DIR / "weights.json"
OUTPUT_PATH = DATA_DIR / "clue_catalog.json"


# ─────────────────────────────────────────────────────────────
# Outcome flags 휴리스틱 (PDF §17.A — Google Chronicle 패턴)
# ─────────────────────────────────────────────────────────────


def derive_outcome_flags(clue_key: str, label: str, category: str) -> dict:
    """단서의 weight_key·label 패턴에서 정형 Boolean·enum 추출.

    Google Chronicle Rule-to-Outcome 패턴 정합. Phase B API 응답에 동봉되어
    프론트 분기 로직 간소화 + GenAI 셰르파 환각 방지에 사용.

    반환 예시
    --------
        {"outcomeIsAnonymizedSource": True, "outcomeSourceCategoryHint": "tor_vpn"}
        {"outcomeIsExternalReport": True}
        {"outcomeIsPrivilegeChange": True, "outcomeChangeKind": "create_account"}
    """
    flags: dict = {}
    key_low = clue_key.lower()
    label_low = label.lower()

    # ── IP / 출처 ─────────────────────────
    if "tor" in key_low or "vpn" in key_low or "tor" in label_low or "vpn" in label_low:
        flags["outcomeIsAnonymizedSource"] = True
        flags["outcomeSourceCategoryHint"] = "tor_vpn"
    if "non_korean" in key_low or "비국내" in label or "외부 ip" in label_low:
        flags["outcomeIsForeignSource"] = True
    if "multi_account" in key_low or "다중 계정" in label:
        flags["outcomeIsMultiAccountAccess"] = True

    # ── 알람·신고 출처 ────────────────────
    if category == "Q1_inception":
        if "csp_alert" in key_low:
            flags["outcomeAlertSource"] = "csp_native"
        elif "external_report" in key_low:
            flags["outcomeIsExternalReport"] = True
        elif "audit" in key_low:
            flags["outcomeIsAuditDiscovery"] = True
        elif "service_anomaly" in key_low:
            flags["outcomeIsServiceAnomaly"] = True

    # ── 인증·계정 ─────────────────────────
    if "mfa" in key_low or "mfa" in label_low:
        if "disable" in key_low or "비활성" in label or "off" in key_low:
            flags["outcomeMfaDisabled"] = True
        elif "bypass" in key_low or "우회" in label:
            flags["outcomeMfaBypass"] = True
    if "fail_then_success" in key_low or "fail" in key_low and "success" in key_low:
        flags["outcomeAuthFailThenSuccess"] = True
    if "privilege_change" in key_low or "권한 변경" in label or "권한 상승" in label:
        flags["outcomeIsPrivilegeChange"] = True
    if "newly_created" in key_low or "신규 생성" in label or "create_account" in key_low:
        flags["outcomeIsAccountCreation"] = True
    if "root_or_admin" in key_low or "관리자" in label or "root" in label_low:
        flags["outcomeIsPrivilegedAccount"] = True
    if "inactive_to_active" in key_low or "휴면" in label:
        flags["outcomeIsDormantAwakening"] = True

    # ── 데이터·스토리지 ───────────────────
    if "object_storage" in key_low or "오브젝트 스토리지" in label or "s3" in label_low:
        flags["outcomeServiceCategory"] = "object_storage"
    if "ransomware_pattern" in key_low or ".locked" in label or ".encrypted" in label or "랜섬" in label:
        flags["outcomeRansomwarePattern"] = True
    if "exfil" in key_low or "유출" in label or "download" in label_low or "다운로드" in label:
        flags["outcomeIsDataExfiltration"] = True

    # ── 로그·감사 변조 ────────────────────
    if "audit_log" in key_low or "감사 로그" in label or "cloud_trail" in key_low:
        if "disable" in key_low or "비활성" in label or "off" in key_low or "tamper" in label_low:
            flags["outcomeAuditLogTampered"] = True

    # ── 시각·시간 윈도우 ──────────────────
    if "off_hours" in key_low or "비표준 시각" in label or "야간" in label or "새벽" in label:
        flags["outcomeOffHoursActivity"] = True

    # ── API·실행 burst ─────────────────────
    if "api_burst" in key_low or "burst" in label_low or "대량" in label:
        flags["outcomeBurstActivity"] = True

    # ── 설정 노출 ──────────────────────────
    if "misconfig" in key_low or "설정 오류" in label or "public" in key_low or "공개" in label:
        flags["outcomeIsMisconfiguration"] = True

    # ── 피싱·소셜 ──────────────────────────
    if "phish" in key_low or "피싱" in label or "email_click" in key_low:
        flags["outcomeIsPhishing"] = True

    # ── 내부자 시그널 ──────────────────────
    if "insider" in key_low or "내부자" in label:
        flags["outcomeIsInsiderSignal"] = True
    if "scope_within" in key_low or "직무 내" in label:
        flags["outcomeIsInScope"] = True

    return flags


def short_label(label: str, max_len: int = 30) -> str:
    """긴 label 을 트리 노드 표시용 짧은 버전으로 축약.

    괄호 부연 설명 제거 + max_len 자르기.
    """
    base = label.split("(")[0].strip()
    if len(base) > max_len:
        return base[: max_len - 1].rstrip() + "…"
    return base or label[:max_len]


# ─────────────────────────────────────────────────────────────
# 추출 로직
# ─────────────────────────────────────────────────────────────


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def extract_weights_for_key(
    weights_data: dict, weight_key: str
) -> tuple[Optional[dict[str, int]], Optional[str]]:
    """weight_key 로 decision_tree_answers / clue_types / partial 에서 weights + source 추출.

    반환: (weights_dict_with_no_source, source_label) 또는 (None, None) 정의 없음.
    """
    sections = ["decision_tree_answers", "clue_types", "partial_analysis_techniques"]
    for sec in sections:
        block = weights_data.get(sec, {})
        if weight_key in block:
            entry = block[weight_key]
            src = entry.get("source", "")
            clean = {k: v for k, v in entry.items() if isinstance(v, (int, float))}
            return clean, src
    return None, None


def extract_from_decision_tree(
    tree_data: dict, weights_data: dict
) -> list[dict]:
    """decision_tree.json 의 각 question.option → 단서 1개로 추출."""
    out: list[dict] = []
    nodes = tree_data.get("nodes", {})

    for node_id, node in nodes.items():
        if node.get("type") != "question":
            continue
        options = node.get("options", [])
        for opt in options:
            weight_key = opt.get("weight_key") or f"{node_id}:{opt.get('id')}"
            label = opt.get("label", opt.get("id", weight_key))
            value = opt.get("id", "")

            weights, src = extract_weights_for_key(weights_data, weight_key)
            outcome_flags = derive_outcome_flags(weight_key, label, node_id)

            out.append({
                "clue_key": weight_key,
                "category": node_id,
                "value": value,
                "label": label,
                "short_label": short_label(label),
                "source": "decision_tree",
                "has_weights": weights is not None,
                "weights": weights or {},
                "weight_source": src or "",
                "outcome_flags": outcome_flags,
            })
    return out


def extract_from_clue_types(weights_data: dict) -> list[dict]:
    """weights.json:clue_types 항목 → 단서 1개."""
    out: list[dict] = []
    clue_types = weights_data.get("clue_types", {})
    for key, entry in clue_types.items():
        # 카테고리:값 분리
        category, _, value = key.partition(":")
        src = entry.get("source", "")
        weights = {k: v for k, v in entry.items() if isinstance(v, (int, float))}
        # label — 직접 단서 입력은 weight_key 자체를 label 로 (사용자 입력 자유 텍스트 기반이므로)
        label_map = _CLUE_TYPE_LABELS.get(key, key.replace("_", " "))
        outcome_flags = derive_outcome_flags(key, label_map, category)

        out.append({
            "clue_key": key,
            "category": category,
            "value": value,
            "label": label_map,
            "short_label": short_label(label_map),
            "source": "clue_input",
            "has_weights": True,
            "weights": weights,
            "weight_source": src,
            "outcome_flags": outcome_flags,
        })
    return out


def extract_from_partial_techniques(weights_data: dict) -> list[dict]:
    """weights.json:partial_analysis_techniques (ATT&CK 기법) → 단서 1개."""
    out: list[dict] = []
    techniques = weights_data.get("partial_analysis_techniques", {})
    for tid, entry in techniques.items():
        clue_key = f"TECHNIQUE:{tid}"
        tactic = entry.get("tactic", "")
        src = entry.get("source", "")
        weights = {k: v for k, v in entry.items() if isinstance(v, (int, float))}
        label = f"ATT&CK {tid}" + (f" ({tactic})" if tactic else "")
        outcome_flags = {"outcomeAttackTechniqueId": tid}
        if tactic:
            outcome_flags["outcomeAttackTactic"] = tactic

        out.append({
            "clue_key": clue_key,
            "category": "TECHNIQUE",
            "value": tid,
            "label": label,
            "short_label": short_label(label),
            "source": "log_analysis",
            "has_weights": True,
            "weights": weights,
            "weight_source": src,
            "outcome_flags": outcome_flags,
        })
    return out


# clue_types 키 → 사용자 표시 label (직접 입력 채널)
_CLUE_TYPE_LABELS: dict[str, str] = {
    "IP_ADDRESS:non_korean": "비국내 IP 출처",
    "IP_ADDRESS:tor_vpn": "Tor·VPN exit node 출처",
    "IP_ADDRESS:multi_account": "다중 계정에서 동일 IP 접근",
    "IP_ADDRESS:multi_csp_observed": "다중 CSP 에서 동일 IP 관측",
    "ACCOUNT:privilege_changed": "계정 권한 변경 발생",
    "ACCOUNT:newly_created": "신규 계정 생성",
    "ACCOUNT:inactive_to_active": "휴면 계정의 활성화",
    "ACCOUNT:root_or_admin": "Root·관리자 계정 활동",
    "ACCOUNT:mfa_disabled": "MFA 비활성화 상태",
    "HASH:known_malicious": "알려진 악성 파일 해시 매치",
    "HASH:unknown": "미확정 해시 (악성 미확정)",
    "DOMAIN:c2": "C2 도메인 통신 확인",
    "DOMAIN:dga": "DGA 도메인 패턴 확인",
    "TIME_WINDOW:off_hours": "비표준 시각 활동",
    "SERVICE:object_storage": "Object Storage 서비스 관련",
    "SERVICE:iam": "IAM 서비스 관련",
    "SERVICE:cloud_trail": "감사 로그 (CloudTrail/Audit Log) 서비스 관련",
    "SERVICE:multi_csp": "다중 CSP 서비스 시그널",
    "IP_ADDRESS:generic": "IP 단서 (variant 미상)",
    "ACCOUNT:generic": "계정 단서 (variant 미상)",
    "HASH:generic": "파일 해시 단서 (악성 미확정)",
    "DOMAIN:generic": "도메인 단서 (variant 미상)",
    "TIME_WINDOW:generic": "시각 윈도우 단서",
    "SERVICE:generic": "서비스명 단서",
}


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────


def build_catalog() -> dict:
    tree_data = load_json(DECISION_TREE_PATH)
    weights_data = load_json(WEIGHTS_PATH)

    clues_a = extract_from_decision_tree(tree_data, weights_data)
    clues_b = extract_from_clue_types(weights_data)
    clues_c = extract_from_partial_techniques(weights_data)

    # 중복 키 통합 — clue_input(B) 이 decision_tree(A) 와 동일 weight_key 면
    # 두 source 모두 보존 (둘 다 사용 가능하다는 의미)
    seen: dict[str, dict] = {}
    for entry in clues_a + clues_b + clues_c:
        k = entry["clue_key"]
        if k not in seen:
            seen[k] = entry
        else:
            # 중복 — 기존 entry 에 추가 source 표기
            existing = seen[k]
            srcs = set([existing.get("source", "")])
            srcs.add(entry.get("source", ""))
            existing["source"] = ",".join(sorted(s for s in srcs if s))
            # outcome_flags 병합
            existing["outcome_flags"].update(entry.get("outcome_flags", {}))

    catalog = {
        "_meta": {
            "version": "v1-clue-catalog",
            "generated": datetime.utcnow().isoformat() + "Z",
            "generator": "backend/scripts/build_clue_catalog.py",
            "sources": [
                str(DECISION_TREE_PATH.relative_to(BACKEND_DIR)),
                str(WEIGHTS_PATH.relative_to(BACKEND_DIR)),
            ],
            "purpose": "Evidence Tree 패러다임의 단서 풀 — docs/evidence_tree_paradigm.md §5, §9, §17.A",
            "extraction_rules": {
                "decision_tree": "node.options[].weight_key → clue_key",
                "clue_input": "weights.json:clue_types[] → clue_key",
                "log_analysis": "weights.json:partial_analysis_techniques[] → TECHNIQUE:{id}",
            },
            "outcome_flags_note": "PDF §17.A 채택 — Google Chronicle Rule-to-Outcome 정형화 패턴. Phase B API 응답에 동봉.",
            "counts": {
                "from_decision_tree": len(clues_a),
                "from_clue_types": len(clues_b),
                "from_partial_techniques": len(clues_c),
                "total_unique": len(seen),
            },
        },
        "clues": seen,
    }
    return catalog


def main() -> int:
    if not DECISION_TREE_PATH.exists():
        print(f"[error] missing: {DECISION_TREE_PATH}", file=sys.stderr)
        return 1
    if not WEIGHTS_PATH.exists():
        print(f"[error] missing: {WEIGHTS_PATH}", file=sys.stderr)
        return 1

    catalog = build_catalog()

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    counts = catalog["_meta"]["counts"]
    print(f"[ok] wrote {OUTPUT_PATH.relative_to(BACKEND_DIR)}")
    print(f"     decision_tree: {counts['from_decision_tree']}")
    print(f"     clue_types   : {counts['from_clue_types']}")
    print(f"     partial_tech : {counts['from_partial_techniques']}")
    print(f"     total unique : {counts['total_unique']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
