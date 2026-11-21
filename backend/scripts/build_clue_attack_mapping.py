"""H.2 — 단서 → ATT&CK 매핑 자동 추출 + 수동 보강 (2026-05-25, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §17.B (BAN paper 정합)

목표
----
clue_catalog.json 의 143 단서를 ATT&CK 기법 ID 로 매핑하여 Bayesian Network
DAG 의 노드·조건부 의존성 입력으로 활용. PDF p5-7 의 TTP 이산 확률 변수 모델
구현 토대.

사용자 결정 (3건)
----------------
① 매핑 방식 = Option C — 자동 + 수동 검토 (80/20)
② 매핑 불가 메타 단서 = Option A — null 매핑, DAG 제외 (Q1_inception:*)
③ 1:N 매핑 = Option B — 모든 매핑 보존, Noisy-OR 가 자연 처리

자동 추출 7-tier 전략
---------------------
    Tier 1 — direct_technique : category=TECHNIQUE → value 직접 (confidence=high)
    Tier 2 — meta_excluded    : Q1_inception:* → null (DAG 제외, IG 만 사용)
    Tier 3 — weight_source 정규식 : T-NNNN[.NNN] 패턴 추출 (confidence=high)
    Tier 4 — outcome_flags    : Google Chronicle 정형 플래그 → ATT&CK 매핑
    Tier 5 — 카테고리·값 시그너처 : SERVICE:cloud_trail → T1562.008 등
    Tier 6 — manual_supplements : 도메인 지식 1:N 확장 + 누락 보강
    Tier 7 — manual_pending   : 자동 실패, 수동 검토 필요 (출력에 source 명시)

출력
----
    backend/data/triage/clue_to_attack.json
    {
      "_meta": {...},
      "mappings": {
        "<clue_key>": {
          "techniques": ["T1090.003", "T1078.004"] | null,
          "source": "auto:direct|weight_source|outcome_flags|category|manual_supplement|meta_excluded|manual_pending",
          "confidence": "high|medium|low|n/a",
          "notes": "..."
        }
      }
    }
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
CATALOG_PATH = BACKEND_DIR / "data" / "triage" / "clue_catalog.json"
OUTPUT_PATH = BACKEND_DIR / "data" / "triage" / "clue_to_attack.json"

# ATT&CK 기법 ID 정규식 (T-NNNN 또는 T-NNNN.NNN)
ATTACK_PATTERN = re.compile(r"T(\d{4})(?:\.(\d{3}))?")


# ─────────────────────────────────────────────────────────────
# Tier 2 — 메타 단서 (DAG 외부 처리)
# ─────────────────────────────────────────────────────────────


META_EXCLUDED_KEYS: set[str] = {
    # Q1_inception — 사고 인지 경로 (방어자 메타데이터, 공격자 TTP 아님)
    "Q1_inception:csp_alert",
    "Q1_inception:external_report",
    "Q1_inception:audit",
    "Q1_inception:service_anomaly",
    "Q1_inception:unknown",
}


# ─────────────────────────────────────────────────────────────
# Tier 4 — outcome_flags → ATT&CK 매핑 룰 (PDF §17.A Google Chronicle 정형)
# ─────────────────────────────────────────────────────────────


# 플래그 키 (대소문자 무시) → 기법 ID 리스트
OUTCOME_FLAG_TO_ATTACK: dict[str, list[str]] = {
    "outcomeIsAnonymizedSource": ["T1090.003"],  # Multi-hop Proxy / Tor
    "outcomeIsForeignSource": ["T1078.004"],  # Valid Accounts: Cloud
    "outcomeIsMultiAccountAccess": ["T1078.004"],
    "outcomeMfaDisabled": ["T1556.006", "T1078"],  # MFA + Valid Accounts (사용자 결정 ③ 예시)
    "outcomeMfaBypass": ["T1556.006", "T1111"],  # MFA Request Generation
    "outcomeAuthFailThenSuccess": ["T1110"],  # Brute Force
    "outcomeIsPrivilegeChange": ["T1098"],  # Account Manipulation
    "outcomeIsAccountCreation": ["T1136"],  # Create Account
    "outcomeIsPrivilegedAccount": ["T1078", "T1548"],  # Valid Accounts + Abuse Elevation
    "outcomeIsDormantAwakening": ["T1078"],  # Valid Accounts (dormant→active)
    "outcomeRansomwarePattern": ["T1486"],  # Data Encrypted for Impact
    "outcomeIsDataExfiltration": ["T1530", "T1567"],  # Cloud Storage + Web Exfil
    "outcomeAuditLogTampered": ["T1562.008"],  # Disable Cloud Logs
    "outcomeOffHoursActivity": ["T1078"],  # Valid Accounts (anomalous timing)
    "outcomeBurstActivity": ["T1078.004"],  # Cloud Accounts (API burst)
    "outcomeIsMisconfiguration": ["T1190", "T1078.004"],  # Public-facing app + Cloud cred
    "outcomeIsPhishing": ["T1566"],  # Phishing
    "outcomeIsInsiderSignal": ["T1078"],  # Valid Accounts (insider)
}


def techniques_from_outcome_flags(flags: dict) -> list[str]:
    """outcome_flags 의 True/존재 키들을 기법 ID 로 매핑."""
    out: list[str] = []
    for key, value in flags.items():
        if not value:
            continue
        if key in OUTCOME_FLAG_TO_ATTACK:
            for t in OUTCOME_FLAG_TO_ATTACK[key]:
                if t not in out:
                    out.append(t)
    return out


# ─────────────────────────────────────────────────────────────
# Tier 5 — 카테고리·값 시그너처 (단서 의미 도메인 지식)
# ─────────────────────────────────────────────────────────────


# (category, value_pattern) → 기법 리스트. value_pattern 은 정확 일치 또는 부분 일치
CATEGORY_VALUE_SIGNATURE: dict[tuple[str, str], list[str]] = {
    # 단서 입력 6종 ClueType — value 별 기법
    ("SERVICE", "cloud_trail"): ["T1562.008"],  # Disable Cloud Logs
    ("SERVICE", "object_storage"): ["T1530"],  # Data from Cloud Storage Object
    ("SERVICE", "iam"): ["T1078", "T1098"],  # Valid Accounts + Account Manipulation
    ("SERVICE", "multi_csp"): ["T1078.004"],  # Cloud Accounts multi-tenancy
    ("DOMAIN", "c2"): ["T1071"],  # Application Layer Protocol
    ("DOMAIN", "dga"): ["T1568.002"],  # Domain Generation Algorithms
    ("HASH", "known_malicious"): ["T1204"],  # User Execution
}


def techniques_from_category_signature(category: str, value: str) -> list[str]:
    out: list[str] = []
    key = (category, value)
    if key in CATEGORY_VALUE_SIGNATURE:
        out.extend(CATEGORY_VALUE_SIGNATURE[key])
    return out


# ─────────────────────────────────────────────────────────────
# Tier 6 — 수동 보강 (auto 추출이 단일/누락된 단서의 도메인 지식 1:N 확장)
# ─────────────────────────────────────────────────────────────


# (clue_key) → (techniques, notes) — 자동 추출 결과를 덮어쓰지 않고 합집합으로 추가
MANUAL_SUPPLEMENTS: dict[str, tuple[list[str], str]] = {
    # ── Q2A 알람 종류 (CSP 알람 패턴) ──
    "Q2A:non_korean_ip": (["T1078.004"], "비국내 IP — Cloud Accounts 침해 시그널"),
    "Q2A:api_burst": (["T1078.004", "T1580"], "API burst — Cloud 자원 탐색 + 자격증명 남용"),
    "Q2A:off_hours": (["T1078"], "비표준 시각 활동 — Valid Accounts 변별"),
    "Q2A:misconfig_alert": (["T1190", "T1078.004"], "misconfig 노출 → Public-facing Exploit"),
    "Q2A:phishing_kit_detect": (["T1566"], "피싱 키트 탐지"),

    # ── Q2B 외부 신고 내용 ──
    "Q2B:data_exposed": (["T1530"], "데이터 외부 노출 → Cloud Storage 유출"),
    "Q2B:abnormal_billing": (["T1496"], "비정상 과금 → Resource Hijacking (mining)"),
    "Q2B:multi_csp_suspicious": (["T1078.004"], "멀티 CSP 의심 → Cloud Accounts 횡적 이동"),
    "Q2B:ransom_note_visible": (["T1486"], "랜섬 노트 가시화"),
    "Q2B:insider_complaint": (["T1078"], "내부자 제보 — Valid Accounts 오남용"),

    # ── Q2C 감사 패턴 ──
    "Q2C:iam_burst": (["T1136", "T1098"], "신규 IAM 다수 + 권한 변경"),
    "Q2C:permission_changes": (["T1098"], "권한 변경 다수"),
    "Q2C:log_gap": (["T1562.008"], "감사 로그 누락"),
    "Q2C:data_access": (["T1530"], "비정상 데이터 액세스"),

    # ── Q2D 서비스 이상 ──
    "Q2D:performance_drop": (["T1496"], "성능 저하 — Resource Hijacking 가능성"),
    "Q2D:resource_abuse": (["T1496"], "자원 abuse — crypto mining"),
    "Q2D:data_destruction": (["T1485"], "데이터 파괴 — Disk Wipe"),
    "Q2D:lockout": (["T1531"], "계정 lockout — Account Access Removal"),

    # ── Q3 라우터 + 단축 경로 ──
    "Q3:fail_then_success": (["T1110"], "실패→성공 패턴 — Brute Force"),
    "Q3:multi_region_concurrent": (["T1078.004"], "동시 다지역 — Cloud Accounts 공유 침해"),

    # ── Q3_DATA · Q3_INSIDER · Q3_IMPACT 분기 ──
    "Q3_DATA:storage_policy_public": (["T1530", "T1190"], "Storage policy 공개 → 유출 + 외부 침투"),
    "Q3_DATA:s3_credential_change": (["T1098", "T1078.004"], "S3 자격 변경"),
    "Q3_DATA:multi_csp_pivot": (["T1078.004"], "멀티 CSP pivot"),
    "Q3_DATA:billing_spike": (["T1496"], "billing spike — Resource Hijacking"),
    "Q3_INSIDER:off_hours_priv": (["T1078", "T1098"], "비표준 시각 권한 변경"),
    "Q3_INSIDER:multiple_iam_changes": (["T1098"], "다수 IAM 변경"),
    "Q3_INSIDER:gradual_priv_creep": (["T1098"], "점진적 권한 상승"),
    "Q3_INSIDER:self_audit_disable": (["T1562.008"], "본인 감사 비활성"),
    "Q3_IMPACT:mass_encrypt": (["T1486"], "대량 암호화"),
    "Q3_IMPACT:backup_deletion": (["T1490"], "백업 삭제 — Inhibit System Recovery"),
    "Q3_IMPACT:ransom_extension": (["T1486"], "비표준 확장자"),
    "Q3_IMPACT:storage_destruction": (["T1485"], "Storage 파괴"),

    # ── Q4-CRED 인증 분기 ──
    "Q4-CRED:mfa_token_reuse": (["T1556.006", "T1111"], "MFA 토큰 재사용"),
    "Q4-CRED:mfa_registration_change": (["T1556.006"], "MFA 등록 변경"),
    "Q4-CRED:mfa_not_applied": (["T1556.006"], "MFA 미적용 — 인증 약화"),
    "Q4-CRED:audit_log_tampered": (["T1562.008"], "인증 감사 로그 변조"),

    # ── Q4-RANSOM ──
    "Q4-RANSOM:bulk_putobject_encrypted_ext": (
        ["T1486"],
        "대량 PutObject + 비표준 확장자",
    ),
    "Q4-RANSOM:backup_destroyed": (["T1490"], "백업 파괴"),
    "Q4-RANSOM:backup_intact": ([], "백업 무결 — RANSOM 가능성 감소 (TTP 없음)"),
    "Q4-RANSOM:backup_missing": ([], "백업 운영 부재 — 약한 시그널 (TTP 단정 불가)"),

    # ── Q4-MISCFG ──
    "Q4-MISCFG:short_term_public": (["T1078.004"], "단기 노출 — Cloud Accounts 일시 misconfig"),
    "Q4-MISCFG:long_term_public": (["T1078.004", "T1190"], "장기 노출 — 외부 자산화"),
    "Q4-MISCFG:timing_unknown": ([], "시점 불명 — 약한 시그널 (TTP 단정 불가)"),

    # ── Q4-INSIDER ──
    "Q4-INSIDER:scope_excess": (["T1078", "T1098"], "직무 초과"),
    "Q4-INSIDER:scope_within": ([], "직무 내 정상 활동 (TTP 없음)"),
    "Q4-INSIDER:partner_account": (["T1199"], "협력사 계정 — Trusted Relationship"),

    # ── Q5-CRED 행위자 ──
    "Q5-CRED:tor_vpn": (["T1090.003"], "Tor·VPN exit"),
    "Q5-CRED:internal_ip": (["T1078"], "사내 IP 행위자"),
    "Q5-CRED:actor_unknown": ([], "행위자 미상 — TTP 단정 불가"),
    "Q5-CRED:baseline_deviation": (["T1078.004"], "베이스라인 일탈 (UEBA anomaly)"),

    # ── Q5-RANSOM 범위 ──
    "Q5-RANSOM:single_instance": (["T1486"], "단일 인스턴스 영향"),
    "Q5-RANSOM:storage_wide": (["T1486"], "Storage 전체 영향"),
    "Q5-RANSOM:multi_region": (["T1486"], "멀티 리전 영향"),

    # ── Q5-MISCFG ──
    "Q5-MISCFG:operator": ([], "운영자 실수 — 인적 요인 (TTP 없음)"),
    "Q5-MISCFG:automation_script": (["T1078.004"], "자동화 스크립트 자격증명 abuse"),
    "Q5-MISCFG:actor_unknown": ([], "행위자 미상"),

    # ── Q5-INSIDER ──
    "Q5-INSIDER:internal_endpoint": (["T1078"], "사내 단말 origin"),
    "Q5-INSIDER:internal_vpn": (["T1078"], "사내 VPN"),
    "Q5-INSIDER:trace_deletion": (["T1070"], "흔적 삭제 — Indicator Removal"),
    "Q5-INSIDER:no_data_extract": ([], "외부 유출 없음 (TTP 없음)"),

    # ── Q6-CRED 결과 ──
    "Q6-CRED:priv_change": (["T1098"], "후속 권한 변경"),
    "Q6-CRED:storage_download": (["T1530"], "후속 다운로드"),
    "Q6-CRED:function_persist": (["T1547"], "신규 함수 지속성 — Persistence"),
    "Q6-CRED:no_follow": ([], "후속 행동 없음 (TTP 없음)"),
    "Q6-CRED:no_followup": ([], "후속 행동 없음 (TTP 없음)"),  # 이름 변종

    # ── IP / HASH / SERVICE 일반·기타 ──
    "IP_ADDRESS:multi_csp_observed": (
        ["T1078.004", "T1199"],
        "다중 CSP 관측 — Cloud Accounts + Trusted Relationship",
    ),
    "HASH:unknown": ([], "미확정 해시 — 약한 시그널 (TTP 단정 불가)"),

    # ── *:generic — variant 미상 (약한 시그널, TTP 없음) ──
    "IP_ADDRESS:generic": ([], "IP 일반 단서 — variant 미상 (TTP 없음)"),
    "ACCOUNT:generic": ([], "계정 일반 단서 — variant 미상 (TTP 없음)"),
    "HASH:generic": ([], "해시 일반 단서 — variant 미상 (TTP 없음)"),
    "DOMAIN:generic": ([], "도메인 일반 단서 — variant 미상 (TTP 없음)"),
    "TIME_WINDOW:generic": ([], "시각 일반 단서 — variant 미상 (TTP 없음)"),
    "SERVICE:generic": ([], "서비스 일반 단서 — variant 미상 (TTP 없음)"),

    # ── Q6-RANSOM 결과 ──
    "Q6-RANSOM:note_found": (["T1486"], "랜섬 노트"),
    "Q6-RANSOM:double_extortion": (["T1486", "T1567"], "이중 협박 (암호화+유출)"),
    "Q6-RANSOM:no_note": ([], "노트 없음 — 약한 RANSOM 시그널"),

    # ── Q6-MISCFG 결과 ──
    "Q6-MISCFG:pii": (["T1530"], "PII 유출"),
    "Q6-MISCFG:trade_secret": (["T1530"], "영업비밀 유출"),
    "Q6-MISCFG:no_external_access": ([], "외부 접근 없음"),

    # ── Q6-INSIDER 결과 ──
    "Q6-INSIDER:data_external": (["T1567"], "데이터 외부 전송"),
    "Q6-INSIDER:iam_self_delete": (["T1070", "T1531"], "IAM 자기 삭제"),
    "Q6-INSIDER:scope_complete": ([], "직무 범위 내 완료 (TTP 없음)"),

    # ── 약한 시그널 / 미상 ──
    "Q3:unknown_extra": ([], "기타 정보 — 단정 불가"),
    "Q2D:response_delay": ([], "응답 지연 — 약한 시그널"),
}


# ─────────────────────────────────────────────────────────────
# 추출 함수
# ─────────────────────────────────────────────────────────────


def extract_techniques_from_text(text: str) -> list[str]:
    """텍스트에서 T-NNNN[.NNN] 패턴 추출, 중복 제거 + 순서 보존."""
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for major, minor in ATTACK_PATTERN.findall(text):
        tid = f"T{major}" + (f".{minor}" if minor else "")
        if tid not in seen:
            seen.add(tid)
            out.append(tid)
    return out


def map_one_clue(clue_key: str, entry: dict) -> dict:
    """단서 1건 → 매핑 결과 dict (techniques, source, confidence, notes)."""

    # Tier 2 — 메타 단서 (DAG 제외)
    if clue_key in META_EXCLUDED_KEYS:
        return {
            "techniques": None,
            "source": "meta_excluded",
            "confidence": "n/a",
            "notes": "사고 인지 경로 — DAG 외부 처리, IG 만 사용",
        }

    category = entry.get("category", "")
    value = entry.get("value", "")

    # Tier 1 — 직접 TECHNIQUE
    if category == "TECHNIQUE":
        return {
            "techniques": [value],
            "source": "auto:direct",
            "confidence": "high",
            "notes": "category=TECHNIQUE 직접 매핑",
        }

    techs: list[str] = []
    sources_used: list[str] = []

    # Tier 3 — weight_source 정규식
    weight_source = entry.get("weight_source", "")
    t_src = extract_techniques_from_text(weight_source)
    if t_src:
        techs.extend(t_src)
        sources_used.append("weight_source")

    # Tier 4 — outcome_flags 룩업
    flags = entry.get("outcome_flags", {})
    t_flags = techniques_from_outcome_flags(flags)
    for t in t_flags:
        if t not in techs:
            techs.append(t)
    if t_flags:
        sources_used.append("outcome_flags")

    # Tier 5 — 카테고리·값 시그너처
    t_sig = techniques_from_category_signature(category, value)
    for t in t_sig:
        if t not in techs:
            techs.append(t)
    if t_sig:
        sources_used.append("category_signature")

    # Tier 6 — 수동 보강 (1:N 확장)
    if clue_key in MANUAL_SUPPLEMENTS:
        supp_techs, supp_notes = MANUAL_SUPPLEMENTS[clue_key]
        # 수동 보강이 빈 리스트면 = 명시적 "TTP 없음"
        if not supp_techs:
            if not techs:
                # 자동 추출도 없음 → 명시적 null (약한 시그널)
                return {
                    "techniques": [],
                    "source": "manual_supplement:no_ttp",
                    "confidence": "n/a",
                    "notes": supp_notes,
                }
            # 자동 추출 결과는 보존 (수동에서 명시적 null 의미가 약함)
        else:
            for t in supp_techs:
                if t not in techs:
                    techs.append(t)
            sources_used.append("manual_supplement")

    if techs:
        # 다중 source 일 경우 source 키에 모두 표기
        if sources_used:
            return {
                "techniques": techs,
                "source": "auto:" + "+".join(sources_used),
                "confidence": (
                    "high"
                    if "weight_source" in sources_used or "manual_supplement" in sources_used
                    else "medium"
                ),
                "notes": "",
            }

    # Tier 7 — 자동 실패 (수동 검토 대기)
    return {
        "techniques": [],
        "source": "manual_pending",
        "confidence": "low",
        "notes": "자동 추출 실패 — 수동 검토 필요",
    }


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────


def build_mapping() -> dict:
    if not CATALOG_PATH.exists():
        print(f"[error] catalog not found: {CATALOG_PATH}", file=sys.stderr)
        sys.exit(1)
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    clues: dict = catalog.get("clues", {})

    mappings: dict[str, dict] = {}
    stats: dict[str, int] = {
        "total": 0,
        "direct_technique": 0,
        "meta_excluded": 0,
        "auto_weight_source": 0,
        "auto_outcome_flags": 0,
        "auto_category_signature": 0,
        "manual_supplement": 0,
        "manual_supplement_no_ttp": 0,
        "manual_pending": 0,
        "with_techniques": 0,
        "multi_target": 0,  # 2+ 기법
    }
    all_techniques: set[str] = set()

    for clue_key, entry in clues.items():
        m = map_one_clue(clue_key, entry)
        mappings[clue_key] = m
        stats["total"] += 1

        src = m["source"]
        if src == "auto:direct":
            stats["direct_technique"] += 1
        elif src == "meta_excluded":
            stats["meta_excluded"] += 1
        elif src == "manual_pending":
            stats["manual_pending"] += 1
        elif src == "manual_supplement:no_ttp":
            stats["manual_supplement_no_ttp"] += 1
        else:
            if "weight_source" in src:
                stats["auto_weight_source"] += 1
            if "outcome_flags" in src:
                stats["auto_outcome_flags"] += 1
            if "category_signature" in src:
                stats["auto_category_signature"] += 1
            if "manual_supplement" in src:
                stats["manual_supplement"] += 1

        if m["techniques"]:
            stats["with_techniques"] += 1
            if len(m["techniques"]) >= 2:
                stats["multi_target"] += 1
            for t in m["techniques"]:
                all_techniques.add(t)

    stats["unique_techniques_referenced"] = len(all_techniques)

    return {
        "_meta": {
            "version": "v1-clue-to-attack",
            "generated": datetime.utcnow().isoformat() + "Z",
            "generator": "backend/scripts/build_clue_attack_mapping.py",
            "source_catalog": str(CATALOG_PATH.relative_to(BACKEND_DIR)),
            "purpose": (
                "Bayesian Network DAG 노드·조건부 의존성 입력 — PDF §17.B BAN paper 정합. "
                "단서 → ATT&CK 기법 다중 매핑 (Noisy-OR 처리)."
            ),
            "user_decisions": {
                "mapping_method": "Option C — 자동 + 수동 검토 (80/20)",
                "meta_clue_handling": "Option A — null 매핑, DAG 외부 처리",
                "multi_target": "Option B — 모든 매핑 보존, Noisy-OR 자연 처리",
            },
            "extraction_tiers": [
                "Tier 1: direct_technique (category=TECHNIQUE)",
                "Tier 2: meta_excluded (Q1_inception:*)",
                "Tier 3: auto:weight_source (T-NNNN 정규식)",
                "Tier 4: auto:outcome_flags (Google Chronicle 정형)",
                "Tier 5: auto:category_signature (카테고리·값 도메인 룰)",
                "Tier 6: manual_supplement (1:N 확장)",
                "Tier 7: manual_pending (수동 검토 대기)",
            ],
            "stats": stats,
        },
        "mappings": mappings,
    }


def main() -> int:
    result = build_mapping()
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    stats = result["_meta"]["stats"]
    print(f"[ok] wrote {OUTPUT_PATH.relative_to(BACKEND_DIR)}")
    print()
    print("=== Mapping distribution ===")
    print(f"  total clues                : {stats['total']}")
    print(f"  with techniques (DAG nodes): {stats['with_techniques']}")
    print(f"  multi-target (2+ 기법)     : {stats['multi_target']}")
    print(f"  unique techniques refed    : {stats['unique_techniques_referenced']}")
    print()
    print("=== By source ===")
    print(f"  direct_technique           : {stats['direct_technique']:3}")
    print(f"  meta_excluded              : {stats['meta_excluded']:3}")
    print(f"  auto:weight_source         : {stats['auto_weight_source']:3}")
    print(f"  auto:outcome_flags         : {stats['auto_outcome_flags']:3}")
    print(f"  auto:category_signature    : {stats['auto_category_signature']:3}")
    print(f"  manual_supplement          : {stats['manual_supplement']:3}")
    print(f"  manual_supplement_no_ttp   : {stats['manual_supplement_no_ttp']:3}")
    print(f"  manual_pending             : {stats['manual_pending']:3}")
    print()

    # Pending 목록 노출 (수동 검토 필요)
    pending = [k for k, m in result["mappings"].items() if m["source"] == "manual_pending"]
    if pending:
        print(f"⚠ Manual review pending ({len(pending)}):")
        for k in pending[:15]:
            entry_src = result["mappings"][k]
            print(f"   - {k:42}  {entry_src['notes']}")
        if len(pending) > 15:
            print(f"   ... + {len(pending) - 15} more")
    else:
        print("✓ No manual review pending — 100% covered")

    return 0


if __name__ == "__main__":
    sys.exit(main())
