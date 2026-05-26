"""Phase L.1 — 단서 메타 풍부화 자동 생성 (2026-05-26 byungwoo).

문제: 사용자 피드백 — "단서가 뭔지·어디서 찾는지·왜 변별력 있는지 모름".
NextCluePanel 카드의 라벨·IG 만으로는 수사관이 후보로 채택할지 판단 불가.

해결: 143 단서 × 5 메타 자동 생성 → data/triage/clue_descriptions.json

생성 필드:
    description                — 단서의 정의·의미 (label 풀어쓰기)
    how_to_find                — NCP/NHN/verify 3경로 (카테고리 + 키워드 기반)
    examples                   — 카테고리별 대표 사례 풀
    discrimination_explanation — 사고유형 가중치 분석 → 한국어 풀이
    academic_source            — weight_source 강화 (인용 분리)

설계서: docs/evidence_tree_paradigm.md §20 (Phase L)
사용:   cd backend && .venv/Scripts/python.exe scripts/build_clue_descriptions.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path


_BACKEND = Path(__file__).resolve().parents[1]
TRIAGE = _BACKEND / "data" / "triage"
CATALOG_PATH = TRIAGE / "clue_catalog.json"
OUT_PATH = TRIAGE / "clue_descriptions.json"


# ─────────────────────────────────────────────────────────────
# 사고유형 한국어 + 정렬
# ─────────────────────────────────────────────────────────────

HYP_KO = {
    "CREDENTIAL_THEFT": "자격증명 탈취",
    "PRIVILEGE_ESCALATION": "권한 상승",
    "DATA_EXFILTRATION": "데이터 유출",
    "AUDIT_LOG_TAMPERING": "감사 로그 변조",
    "RANSOMWARE": "랜섬웨어",
    "MISCONFIG_EXPOSURE": "설정 오류 노출",
    "PHISH_INITIAL_ACCESS": "피싱 초기 침투",
    "INSIDER_THREAT": "내부자 위협",
}


# ─────────────────────────────────────────────────────────────
# 카테고리별 CSP 경로 + 일반 정의 템플릿
# ─────────────────────────────────────────────────────────────


# (category → {ncp, nhn, verify, definition_pattern, examples})
CATEGORY_GUIDE: dict[str, dict] = {
    "IP_ADDRESS": {
        "ncp": "Cloud Insight → 보안 알람 → 비정상 로그인/네트워크 → 출처 IP 열",
        "nhn": "Security Monitoring → 인증 시도 / Network Audit → IP 추적",
        "verify": "IPinfo.io · IPAddress.com · WHOIS 로 ASN/조직/지리정보 조회",
        "definition_template": "접속·요청 IP 의 출처·소속 ASN/조직 정보. {hint}",
        "examples_pool": [
            "115.91.214.5 (Tor exit)", "104.244.74.0/24 (NordVPN)",
            "1.2.3.4 (Korean ISP — 정상)", "45.0.0.0/8 (Russia/Eastern Europe)",
        ],
    },
    "ACCOUNT": {
        "ncp": "Sub Account → 사용자 관리 / Cloud Insight → IAM 활동 → 사용자명·역할",
        "nhn": "IAM → 사용자 / 그룹 → 활동 로그 / NHN Cloud Trail → 사용자 이벤트",
        "verify": "IAM 콘솔에서 계정 생성·MFA·권한 변경 이력 + Audit Log 시간순 확인",
        "definition_template": "사용자 계정·IAM 식별자의 상태·권한·활동 흔적. {hint}",
        "examples_pool": [
            "admin (Root 계정 활동)", "svc-deploy (서비스 계정)",
            "dormant-user01 (휴면 → 활성화)", "MFA off (이전 on → 비활성)",
        ],
    },
    "HASH": {
        "ncp": "Object Storage → 객체 메타데이터 / EDR 솔루션 (시스템 통합 시)",
        "nhn": "Object Storage → 파일 다이제스트 / 통합 보안 솔루션",
        "verify": "VirusTotal · HybridAnalysis · MISP 에서 해시 평판 조회",
        "definition_template": "파일/페이로드의 SHA-256·MD5 해시 + VirusTotal 평판. {hint}",
        "examples_pool": [
            "44d88612fea8a8f36de82e1278abb02f (EICAR test)",
            "ransom_note.txt 의 SHA-256", "unknown.exe (악성 미확정)",
        ],
    },
    "DOMAIN": {
        "ncp": "Global DNS / VPC → DNS 로그 / Cloud Insight → Outbound 통신",
        "nhn": "DNS Plus / Network → DNS 쿼리 로그",
        "verify": "도메인 등록일 (whois) · DGA 패턴 · ThreatFox/AlienVault OTX 조회",
        "definition_template": "외부 도메인 조회·통신 패턴 (C2·DGA·피싱). {hint}",
        "examples_pool": [
            "asdf9xc.com (DGA 패턴)", "evil-tracker.xyz (C2)",
            "secure-login-mfa.tk (피싱 typo-squat)",
        ],
    },
    "TIME_WINDOW": {
        "ncp": "Cloud Insight → 알람 시각 필터 + 활동 로그 시간대 정렬",
        "nhn": "Security Monitoring → 시간대 필터 / 사용자별 활동 시각",
        "verify": "한국 표준 업무 시각 (KST 09-18) 외 활동·주말·공휴일 활동 식별",
        "definition_template": "사고 발생·활동의 시각·요일·업무외 여부. {hint}",
        "examples_pool": [
            "03:00 KST 새벽 로그인", "토요일 02:00 권한 변경",
            "8시간 연속 자동화 패턴",
        ],
    },
    "SERVICE": {
        "ncp": "Cloud Insight → 서비스별 리소스 (Object Storage·IAM·Cloud Trail)",
        "nhn": "NHN Console → 서비스별 메뉴 (Object Storage·IAM·Cloud Audit)",
        "verify": "해당 서비스 콘솔의 활동 로그·정책 변경 이력 + 최근 N일 비교",
        "definition_template": "특정 클라우드 서비스 (IAM·Storage·Audit Log 등) 의 관여 흔적. {hint}",
        "examples_pool": [
            "Object Storage 정책 public 변경",
            "Cloud Trail 비활성 시점 발견",
            "IAM 권한 정책 다수 변경",
        ],
    },
    "TECHNIQUE": {
        "ncp": "(부분 로그 분석에서 자동 추출 — 직접 검색 불필요)",
        "nhn": "(부분 로그 분석에서 자동 추출)",
        "verify": "MITRE ATT&CK 공식 페이지에서 기법 정의·실제 사례 확인",
        "definition_template": "MITRE ATT&CK 의 표준화된 공격 기법 ID. {hint}",
        "examples_pool": [
            "T1078.004 Valid Accounts: Cloud Accounts",
            "T1486 Data Encrypted for Impact (랜섬웨어)",
            "T1562.008 Disable Cloud Logs",
        ],
    },
}


# Q* 카테고리 (결정 트리 옵션 기반) — 일반 템플릿
Q_GUIDE_TEMPLATE = {
    "ncp": "(결정 트리 보조 가이드) Cloud Insight → 보안 알람·이상 활동 패턴 확인",
    "nhn": "(결정 트리 보조 가이드) Security Monitoring → 사고 인지 경로 확인",
    "verify": "초동 인지 시점의 알람 메시지·신고 내용·감사 이력 종합 검토",
    "examples": ["해당 답변에 부합하는 상황을 시스템에서 확인"],
}


def category_guide_for(category: str) -> dict:
    """카테고리 → CSP 경로·예시·정의 템플릿 매핑."""
    if category in CATEGORY_GUIDE:
        return CATEGORY_GUIDE[category]
    # Q-prefix (Q1_inception, Q2A, Q3_CRED, Q4_RANSOM, ...)
    if category.startswith("Q"):
        return {
            "ncp": Q_GUIDE_TEMPLATE["ncp"],
            "nhn": Q_GUIDE_TEMPLATE["nhn"],
            "verify": Q_GUIDE_TEMPLATE["verify"],
            "definition_template": "결정 트리 {q} 단계의 가능 답변. {{hint}}".format(q=category),
            "examples_pool": Q_GUIDE_TEMPLATE["examples"],
        }
    # fallback
    return {
        "ncp": "(카테고리별 일반 경로 확인 필요)",
        "nhn": "(카테고리별 일반 경로 확인 필요)",
        "verify": "(수동 분석 필요)",
        "definition_template": "{hint}",
        "examples_pool": [],
    }


# ─────────────────────────────────────────────────────────────
# 가중치 분석 → 변별력 풀이
# ─────────────────────────────────────────────────────────────


def discrimination_text(weights: dict[str, float]) -> str:
    """사고유형 가중치 → 한국어 변별 풀이.

    Strong (≥25), Medium (10-24), Weak (5-9), Zero (0) 4단계.
    """
    if not weights:
        return "변별 가중치 정보 없음."

    pure = {h: float(v) for h, v in weights.items() if h in HYP_KO}
    if not pure:
        return "변별 가중치 정보 없음."

    sorted_w = sorted(pure.items(), key=lambda x: -x[1])
    strong = [(h, w) for h, w in sorted_w if w >= 25]
    medium = [(h, w) for h, w in sorted_w if 10 <= w < 25]
    weak = [(h, w) for h, w in sorted_w if 5 <= w < 10]
    zero_hyps = [h for h, w in sorted_w if w == 0]

    parts: list[str] = []
    if strong:
        s = ", ".join(f"{HYP_KO[h]} +{int(w)}점" for h, w in strong)
        parts.append(f"강한 시그널 — {s}")
    if medium:
        m = ", ".join(f"{HYP_KO[h]} +{int(w)}" for h, w in medium)
        parts.append(f"중간 — {m}")
    if weak:
        w_str = ", ".join(f"{HYP_KO[h]} +{int(w)}" for h, w in weak)
        parts.append(f"약함 — {w_str}")
    if zero_hyps:
        z = ", ".join(HYP_KO[h] for h in zero_hyps[:3])
        parts.append(f"무영향 — {z}{' 등' if len(zero_hyps) > 3 else ''}")

    return ". ".join(parts) + "."


# ─────────────────────────────────────────────────────────────
# definition hint — outcome_flags + label 결합
# ─────────────────────────────────────────────────────────────


_FLAG_HINTS = {
    "outcomeIsAnonymizedSource": "공격자가 신원을 익명화·은폐하려는 의도가 강함.",
    "outcomeIsForeignSource": "비국내 출처 — 외부 위협 행위자 가능성.",
    "outcomeIsMultiAccountAccess": "여러 계정에서 동일 출처 — 자격증명 공유·공격 인프라.",
    "outcomeAlertSource": "최초 사고 인지 경로 식별.",
    "outcomeIsExternalReport": "내부 탐지 실패 → 외부 신고로 인지.",
    "outcomeIsAuditDiscovery": "정기 감사 중 사후 발견 — 사고 지연 인지.",
    "outcomeIsServiceAnomaly": "서비스 이상 (장애·성능) 기반 인지.",
    "outcomeMfaDisabled": "MFA 비활성 — 인증 우회 표면 확장.",
    "outcomeMfaBypass": "MFA 우회 시도 — 자격증명 탈취 진행 중.",
    "outcomeAuthFailThenSuccess": "실패→성공 패턴 — brute-force·credential stuffing.",
    "outcomeIsPrivilegeChange": "권한 변경 — 권한 상승 또는 백도어 계정.",
    "outcomeIsAccountCreation": "신규 계정 생성 — 백도어·서비스 계정 우회.",
    "outcomeIsPrivilegedAccount": "관리자·Root 계정 활동 — 영향도 큼.",
    "outcomeIsDormantAwakening": "휴면 계정의 활성화 — 자격증명 도용 시그널.",
    "outcomeServiceCategory": "특정 서비스 (Object Storage·IAM·CloudTrail) 관여.",
    "outcomeRansomwarePattern": "랜섬웨어 직접 증거 — .locked/.encrypted 확장자·랜섬 노트.",
    "outcomeIsDataExfiltration": "데이터 외부 반출 시그널.",
    "outcomeAuditLogTampered": "감사 로그 변조·비활성 — 흔적 삭제 의도.",
    "outcomeOffHoursActivity": "비표준 시각 활동 — 자동화·내부자·외부 침투 의심.",
    "outcomeBurstActivity": "대량 활동 burst — 자동화·악성 스크립트.",
    "outcomeIsMisconfiguration": "설정 오류 노출 — 외부 직접 접근 위험.",
    "outcomeIsPhishing": "피싱 시도 — 초기 침투 경로.",
    "outcomeIsInsiderSignal": "내부자 위협 시그널.",
    "outcomeIsInScope": "직무 범위 내 활동 — 정상 가능성 높음 (약한 시그널).",
}


def definition_hint(outcome_flags: dict, fallback: str) -> str:
    """outcome_flags 에서 의미 추출 → 정의 hint."""
    hints: list[str] = []
    for k, v in (outcome_flags or {}).items():
        if k in _FLAG_HINTS:
            text = _FLAG_HINTS[k]
            # enum 값 (string) 인 경우 같이 표시
            if isinstance(v, str):
                text = text.replace("관여.", f"관여 (값: {v}).")
            hints.append(text)
    if not hints:
        return fallback
    return " ".join(hints[:2])  # 최대 2개 (중복 차단)


# ─────────────────────────────────────────────────────────────
# 핵심 단서별 수동 보강 (사용자 결정 C — CSP 구체 경로)
# ─────────────────────────────────────────────────────────────

# IG 상위·자주 노출되는 단서 우선. CATEGORY_GUIDE 의 일반 경로 외에
# 단서 특화 경로 추가.
SPECIFIC_OVERRIDES: dict[str, dict] = {
    "IP_ADDRESS:tor_vpn": {
        "description": (
            "접속 IP 가 공개 Tor 출구 노드 또는 익명 VPN 게이트웨이로 식별된 경우. "
            "공격자가 신원을 은닉하려는 강한 시그널."
        ),
        "how_to_find": {
            "ncp": "Cloud Insight → 보안 알람 → 비정상 로그인 → 클릭 → '출처 IP' → IPinfo 외부 조회",
            "nhn": "Security Monitoring → 인증 시도 → IP 컬럼 우클릭 → '평판 조회'",
            "verify": "torproject.org/exits, IPinfo.io 의 'tor' privacy detection, VPN provider ASN (NordVPN=AS46844 등)",
        },
        "examples": ["115.91.214.5 (Tor exit, KR)", "104.244.74.0/24 (NordVPN)", "185.220.101.X (Tor exit, DE)"],
    },
    "IP_ADDRESS:non_korean": {
        "description": "접속 IP 의 지리적 위치가 한국이 아닌 경우. 외부 위협 행위자·VPN 우회 시그널.",
        "how_to_find": {
            "ncp": "Cloud Insight → 보안 알람 → 비정상 로그인 → 'Geolocation' 컬럼 또는 IPinfo 조회",
            "nhn": "Security Monitoring → 위치 필터 'NOT KR' 또는 IP whois 확인",
            "verify": "MaxMind GeoLite2 / IPinfo.io / WHOIS 의 country 필드",
        },
        "examples": ["45.X.X.X (러시아)", "104.X.X.X (미국)", "117.X.X.X (중국)"],
    },
    "ACCOUNT:mfa_disabled": {
        "description": "사용자 계정의 MFA (Multi-Factor Authentication) 가 비활성 상태로 인증된 경우.",
        "how_to_find": {
            "ncp": "Sub Account → 사용자 관리 → 사용자 클릭 → 'MFA 사용 여부' Off + 로그인 시각 비교",
            "nhn": "IAM → 사용자 → MFA 상태 → '비활성' 사용자 + Cloud Trail 로그인 매칭",
            "verify": "콘솔 활동 로그 (IAM:UpdateUser, UpdateLoginProfile API 호출 이력)",
        },
        "examples": ["admin (MFA off)", "service-acc-01 (MFA 미설정)"],
    },
    "ACCOUNT:newly_created": {
        "description": "사고 발생 직전·중 새로 생성된 IAM 계정. 백도어 계정 설치 의심.",
        "how_to_find": {
            "ncp": "Sub Account → 사용자 관리 → 생성일 정렬 → 최근 N시간 내 계정",
            "nhn": "IAM → 사용자 → 생성일 컬럼 정렬 + Cloud Trail CreateUser API 추적",
            "verify": "API 호출자 (sourceUser) 식별 — 정상 관리자인지·탈취된 계정인지",
        },
        "examples": ["bd-service01 (사고 1시간 전 생성)", "tmp-admin (관리자 IAM 권한)"],
    },
    "SERVICE:cloud_trail": {
        "description": "감사 로그 (Cloud Trail · NHN Cloud Trail) 비활성·삭제·필터링 변경.",
        "how_to_find": {
            "ncp": "Cloud Insight → 알람 'audit_log_disabled' + Cloud Trail 콘솔 → '추적' 상태",
            "nhn": "Cloud Audit → 추적 상태 'Disabled' / 보존 정책 변경 이력",
            "verify": "T1562.008 매칭 — StopLogging·DeleteTrail·UpdateEventSelectors API 호출",
        },
        "examples": ["Trail 'main-audit' Disabled", "보존 7일 → 1일 변경", "S3 bucket 권한 변경"],
    },
    "Q6-RANSOM:note_found": {
        "description": "랜섬 노트 (요구문) 파일 발견 — 랜섬웨어 사고 직접 증거.",
        "how_to_find": {
            "ncp": "Object Storage → 버킷 객체 검색 'README'·'DECRYPT'·'.txt' 신규 생성",
            "nhn": "Object Storage → 객체 메타데이터 → 사고 시각 직전·직후 생성 파일",
            "verify": "파일 내용 분석 — 비트코인 지갑 주소·이메일·Tor 링크·요구액",
        },
        "examples": ["README-DECRYPT.txt", "HOW_TO_PAY.html", "_recover_files_.bin"],
    },
}


# ─────────────────────────────────────────────────────────────
# 메인 생성 로직
# ─────────────────────────────────────────────────────────────


def build_description(clue_key: str, entry: dict) -> dict:
    """단서 1건의 풍부 메타 dict 반환."""
    category = entry.get("category", "")
    label = entry.get("label", clue_key)
    weight_source = entry.get("weight_source", "").strip()
    outcome_flags = entry.get("outcome_flags", {})
    weights = entry.get("weights", {})

    # 1) override 우선 — 있으면 그대로
    override = SPECIFIC_OVERRIDES.get(clue_key, {})

    # 2) description
    if override.get("description"):
        description = override["description"]
    else:
        cat_guide = category_guide_for(category)
        hint = definition_hint(outcome_flags, label)
        tmpl = cat_guide.get("definition_template", "{hint}")
        description = tmpl.format(hint=hint)

    # 3) how_to_find
    if override.get("how_to_find"):
        how_to_find = override["how_to_find"]
    else:
        cat_guide = category_guide_for(category)
        how_to_find = {
            "ncp": cat_guide.get("ncp", ""),
            "nhn": cat_guide.get("nhn", ""),
            "verify": cat_guide.get("verify", ""),
        }

    # 4) examples
    if override.get("examples"):
        examples = override["examples"]
    else:
        cat_guide = category_guide_for(category)
        examples = list(cat_guide.get("examples_pool", []))[:3]

    # 5) discrimination_explanation
    disc = discrimination_text(weights)

    # 6) academic_source — weight_source 정제
    # 예: "MITRE T1090.003 [ISO 27035-1:2023 Assess & Decide]"
    src_clean = weight_source
    iso_match = re.search(r"\[ISO[^\]]+\]", weight_source)
    if iso_match:
        src_clean = src_clean.replace(iso_match.group(), "").strip()
    if not src_clean:
        src_clean = "내부 룰셋"

    return {
        "description": description,
        "how_to_find": how_to_find,
        "examples": examples,
        "discrimination_explanation": disc,
        "academic_source": src_clean,
        "iso_framework": iso_match.group()[1:-1] if iso_match else None,
    }


def main() -> int:
    if not CATALOG_PATH.exists():
        print(f"[error] {CATALOG_PATH} 없음 — build_clue_catalog.py 먼저 실행", file=sys.stderr)
        return 1

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    clues = catalog.get("clues", {})
    print(f"카탈로그 단서 수: {len(clues)}")

    descriptions: dict[str, dict] = {}
    has_override = 0
    has_outcome_hint = 0
    no_examples = 0

    for clue_key, entry in clues.items():
        d = build_description(clue_key, entry)
        descriptions[clue_key] = d
        if clue_key in SPECIFIC_OVERRIDES:
            has_override += 1
        if entry.get("outcome_flags"):
            has_outcome_hint += 1
        if not d["examples"]:
            no_examples += 1

    output = {
        "_meta": {
            "generated": datetime.utcnow().isoformat() + "Z",
            "generator": "scripts/build_clue_descriptions.py",
            "purpose": "Phase L.1 (2026-05-26 byungwoo) — 단서별 정의·CSP 경로·예시·변별 풀이·학술 근거",
            "source_catalog": str(CATALOG_PATH.relative_to(_BACKEND)),
            "total": len(descriptions),
            "specific_overrides": has_override,
            "with_outcome_hints": has_outcome_hint,
            "no_examples": no_examples,
            "design_doc": "docs/evidence_tree_paradigm.md §20",
        },
        "descriptions": descriptions,
    }

    OUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[ok] 출력: {OUT_PATH.relative_to(_BACKEND)}")
    print(f"     {len(descriptions)} 단서 · 특화 override {has_override} · outcome 힌트 {has_outcome_hint}")
    print(f"     예시 없음: {no_examples}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
