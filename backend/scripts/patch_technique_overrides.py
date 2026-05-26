"""Phase L.6 — TECHNIQUE 27 단서의 'how_to_find' 를 실제 NCP/NHN 흔적으로 패치 (2026-05-26 byungwoo).

기존 (L.5): NCP/NHN 모두 "(자동) — ..." 로 표시 → 사용자에게 정보 가치 없음.
개선 (L.6): 실제 콘솔에서 해당 ATT&CK 기법의 흔적 찾는 구체 경로.

T-id 별 NCP/NHN/MITRE 경로 매핑. clue_overrides.json 의 TECHNIQUE:* entries 만 수정.

사용: cd backend && .venv/Scripts/python.exe scripts/patch_technique_overrides.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


_BACKEND = Path(__file__).resolve().parents[1]
OVERRIDES_PATH = _BACKEND / "data" / "triage" / "clue_overrides.json"


# ─────────────────────────────────────────────────────────────
# T-id → NCP / NHN / verify 매핑
# ─────────────────────────────────────────────────────────────

# (description 일부 유지, how_to_find 만 교체)
TECH_PATCH: dict[str, dict] = {
    "T1078.004": {
        "ncp": "Cloud Insight → 보안 알람 → 'Valid Accounts' 카테고리 + Sub Account 활동 로그 → 평소 패턴 외 로그인",
        "nhn": "Cloud Audit → SignIn 이벤트 → '성공' 필터 + IAM 활동 baseline 비교",
        "verify": "MITRE T1078.004 공식 (attack.mitre.org/techniques/T1078/004/) — Detection DS0002 (UserAccount Authentication)",
    },
    "T1110": {
        "ncp": "Cloud Insight → 보안 알람 → 'Brute Force' 또는 SignIn 실패 분당 N건 이상 + 출처 IP 집중도",
        "nhn": "Cloud Audit → SignInFailures 빈도 → 동일 계정/IP 시퀀스 → 성공 시점 매칭",
        "verify": "MITRE T1110 — attack.mitre.org/techniques/T1110/ + 5분 100+ 실패 패턴",
    },
    "T1556": {
        "ncp": "Sub Account → MFA 디바이스 변경 이력 + IAM:UpdateLoginProfile·DeleteVirtualMFADevice API 호출",
        "nhn": "IAM → 사용자 MFA 로그 + Cloud Audit MFA 관련 이벤트",
        "verify": "MITRE T1556 — attack.mitre.org/techniques/T1556/ + 변경 직후 비국내 IP 로그인 매칭",
    },
    "T1539": {
        "ncp": "Cloud Insight → 동일 세션 ID 다중 IP 사용 + Cookie/Token replay 시그널 (web proxy 로그)",
        "nhn": "통합 보안 → AitM (Adversary-in-the-Middle) 알람 + 세션 IP 추적",
        "verify": "MITRE T1539 — 0ktapus/Twilio 2022 사례 + evilginx2 proxy 패턴",
    },
    "T1552.005": {
        "ncp": "VPC Flow Log → 169.254.169.254 호출 비정상 빈도 + 의심 인스턴스 ID 추적",
        "nhn": "VPC → 인스턴스 메타데이터 API (IMDS) 접근 로그 + SSRF 패턴",
        "verify": "MITRE T1552.005 — IMDSv1 vs v2 사용 여부 + Capital One 2019 사례",
    },
    "T1098": {
        "ncp": "Cloud Insight → IAM 활동 → AttachUserPolicy·CreateAccessKey 시각 + 행위자",
        "nhn": "Cloud Audit → IAM:Update*·Put*Policy API 호출 빈도 + 신규 권한 매핑",
        "verify": "MITRE T1098 — attack.mitre.org/techniques/T1098/ + 권한 변경 baseline 일탈",
    },
    "T1136": {
        "ncp": "Sub Account → 사용자 관리 → 생성일 최근 N일 + Cloud Insight CreateUser API 호출 추적",
        "nhn": "IAM → 신규 사용자 생성 + Cloud Audit CreateUser API 행위자",
        "verify": "MITRE T1136 — 백도어 계정 패턴 (tmp-* · bd-* · service-* 이름 + 즉시 권한 부여)",
    },
    "T1484": {
        "ncp": "Cloud Insight → IAM 정책 변경 이력 → UpdateRole·PutRolePolicy 호출 + 신뢰 정책 변경",
        "nhn": "IAM → 역할 매핑 변경 + cross-account 신뢰 정책 → Cloud Audit 추적",
        "verify": "MITRE T1484 — 신뢰 정책에 외부 계정 ID 추가 패턴",
    },
    "T1548.005": {
        "ncp": "Cloud Insight → sts:AssumeRole 비정상 호출 빈도 + 권한 상승 매핑",
        "nhn": "Cloud Audit → AssumeRole 이벤트 + 호출자→대상 역할 매트릭스",
        "verify": "MITRE T1548.005 — 임시 자격증명 사용 후 광범위 활동 패턴",
    },
    "T1530": {
        "ncp": "Object Storage 액세스 로그 → GetObject 빈도 spike + 비표준 사용자 + 대량 다운로드",
        "nhn": "Object Storage → Access Log → 사용자×버킷 매트릭스에서 비정상 패턴",
        "verify": "MITRE T1530 — attack.mitre.org/techniques/T1530/ + Capital One 2019 사례 (S3)",
    },
    "T1537": {
        "ncp": "VPC Flow Log → outbound 트래픽 → 외부 클라우드 IP 대역 (AWS·GCP·Azure) + 대량 전송",
        "nhn": "VPC → outbound 패턴 분석 + 외부 CSP IP 대역 매칭",
        "verify": "MITRE T1537 — cross-cloud copy 패턴 + S3 sync to external bucket",
    },
    "T1567": {
        "ncp": "VPC DNS 로그 → dropbox.com·mega.nz·pastebin.com 등 외부 스토리지 도메인 통신",
        "nhn": "DNS Plus → outbound 도메인 → 외부 파일 공유 서비스 매칭",
        "verify": "MITRE T1567 — Exfiltration Over Web Service 도메인 리스트",
    },
    "T1213": {
        "ncp": "Application Log → Confluence·Wiki·GitLab API 대량 호출 + 비정상 사용자",
        "nhn": "동일 — 사내 정보 저장소 API 호출 빈도 + 다운로드 양",
        "verify": "MITRE T1213 — attack.mitre.org/techniques/T1213/",
    },
    "T1119": {
        "ncp": "Cloud Trail User-Agent → boto3·SDK·자동화 도구 + API 호출 분당 빈도 baseline 일탈",
        "nhn": "Cloud Audit → User-Agent 분석 + 5분 1000+ API 호출 패턴",
        "verify": "MITRE T1119 — 자동화된 데이터 수집 vs 정상 운영 도구 구분",
    },
    "T1562.008": {
        "ncp": "Cloud Trail → StopLogging·DeleteTrail·UpdateEventSelectors API 호출자·시각",
        "nhn": "Cloud Audit → 추적 정책 변경 이력 + 보존 정책 단축 매칭",
        "verify": "MITRE T1562.008 — attack.mitre.org/techniques/T1562/008/ + 활동 직전 audit 비활성",
    },
    "T1070": {
        "ncp": "Cloud Trail → DeleteObject·DeleteLogStream·history clear API + 활동 후 즉시 인멸",
        "nhn": "Cloud Audit → Delete* 이벤트 + 본인 활동 시각 비교",
        "verify": "MITRE T1070 — 활동 후 5-30분 내 흔적 인멸 패턴",
    },
    "T1578": {
        "ncp": "VPC → 신규 인스턴스 생성 이벤트 (CreateInstance·RunInstances) + 비표준 타입 (GPU)",
        "nhn": "Cloud Audit → 컴퓨트 자원 생성·이미지·스냅샷 변경",
        "verify": "MITRE T1578 — attack.mitre.org/techniques/T1578/ + Billing spike 매칭",
    },
    "T1021": {
        "ncp": "VPC Flow Log → SSH 22 / RDP 3389 outbound + 내부 lateral movement 패턴",
        "nhn": "VPC → 내부망 lateral 연결 + 분산 호스트 간 인증 시도",
        "verify": "MITRE T1021 — attack.mitre.org/techniques/T1021/ + 내부 lateral chain 추적",
    },
    "T1550": {
        "ncp": "Cloud Trail → 비표준 토큰·세션 ID 사용 + 행위자 식별 불일치",
        "nhn": "Cloud Audit → 동일 세션의 다중 IP·다중 User-Agent",
        "verify": "MITRE T1550 — pass-the-hash / stolen session token 패턴",
    },
    "T1136.003": {
        "ncp": "Sub Account → 신규 클라우드 계정 생성 + 즉시 권한 부여 + 비국내 IP 출처",
        "nhn": "IAM → CreateUser → AttachUserPolicy 시퀀스 (5분 내)",
        "verify": "MITRE T1136.003 — attack.mitre.org/techniques/T1136/003/",
    },
    "T1485": {
        "ncp": "Object Storage → DeleteObject 대량 호출 + version control 비활성 + lifecycle 단축",
        "nhn": "Cloud Audit → 대량 데이터 삭제 패턴 + 백업 정책 변경",
        "verify": "MITRE T1485 — attack.mitre.org/techniques/T1485/ + wiper 형 공격 (NotPetya)",
    },
    "T1486": {
        "ncp": "Object Storage → 신규 .locked·.encrypted suffix 객체 + PutObject 분당 빈도 (≥100)",
        "nhn": "Object Storage → 객체 메타 → 사고 시각 ±1h 신규 비표준 확장자 통계",
        "verify": "MITRE T1486 — 원본 vs 암호화 객체 크기 ≈ 동일 (덮어쓰기) + entropy ≥ 7.5",
    },
    "T1499": {
        "ncp": "Cloud Insight → DDoS 알람 + 네트워크 트래픽 spike + 분산 출처 IP 분포",
        "nhn": "Security Monitoring → 'DDoS Pattern' 알람 + 트래픽 그래프",
        "verify": "MITRE T1499 — attack.mitre.org/techniques/T1499/ + 시간당 패킷 수 baseline",
    },
    "T1490": {
        "ncp": "Backup → DeleteBackup·DeleteSnapshot API + Object Storage version control disable",
        "nhn": "Backup → 스냅샷 삭제 이력 + 백업 정책 변경",
        "verify": "MITRE T1490 — attack.mitre.org/techniques/T1490/ + 랜섬 직전 백업 파괴 패턴",
    },
    "T1190": {
        "ncp": "Public Endpoint → WAF 알람 + 비정상 요청 (SQLi·SSRF·RCE) + 외부 노출 자원",
        "nhn": "WAF·IPS → 공개 애플리케이션 exploit 시그널",
        "verify": "MITRE T1190 — attack.mitre.org/techniques/T1190/ + Log4Shell·SSRF 사례",
    },
    "T1566": {
        "ncp": "메일 보안 게이트웨이 → 피싱 메일 차단 이력 + 직원 신고 채널 + URL/첨부 평판",
        "nhn": "동일 — Mail Plus·통합 보안 솔루션의 피싱 차단 로그",
        "verify": "MITRE T1566 — PhishTank·OpenPhish 매칭 + AitM kit 도메인 식별",
    },
    "T1078.001": {
        "ncp": "Sub Account → admin·root·system 등 기본 계정 활성 여부 + 로그인 이력",
        "nhn": "IAM → 초기 자격증명 미변경 사용자 식별 + 로그인 매칭",
        "verify": "MITRE T1078.001 — attack.mitre.org/techniques/T1078/001/ + 기본 패스워드 사전 매칭",
    },
}


def patch() -> int:
    if not OVERRIDES_PATH.exists():
        print(f"[error] {OVERRIDES_PATH} 없음", file=sys.stderr)
        return 1

    data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    overrides = data.get("overrides", {})

    patched = 0
    missing: list[str] = []

    for tid, paths in TECH_PATCH.items():
        key = f"TECHNIQUE:{tid}"
        if key not in overrides:
            missing.append(key)
            continue
        overrides[key]["how_to_find"] = {
            "ncp": paths["ncp"],
            "nhn": paths["nhn"],
            "verify": paths["verify"],
        }
        patched += 1

    OVERRIDES_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[ok] TECHNIQUE how_to_find 패치 완료: {patched}/27")
    if missing:
        print(f"⚠ 누락: {missing}")
    print(f"     출력: {OVERRIDES_PATH.relative_to(_BACKEND)}")
    print(f"     다음: scripts/build_clue_descriptions.py 재실행 → clue_descriptions.json 갱신")
    return 0


if __name__ == "__main__":
    sys.exit(patch())
