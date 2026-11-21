"""collection_targets 매칭 룰.

LogIngestor 에서 분리한 순수 함수 모음.
- DB 의존성 없음 → 단위 테스트 용이
- (csp, incident_type) 조합별 매칭 함수를 등록

지원 범위 (2026-05-22 갱신):
  · CREDENTIAL_THEFT     × {naver, nhn}  — 5+5 target
  · PRIVILEGE_ESCALATION × {naver, nhn}  — 4+5 target
  · DATA_EXFILTRATION    × {naver, nhn}  — 3+3 target
  · AUDIT_LOG_TAMPERING  × {naver, nhn}  — 8+8 target
  · RANSOMWARE           × {naver, nhn}  — 5+5 target  ← 신규 (2026-05-22)
  · MISCONFIG_EXPOSURE   × {naver, nhn}  — 4+4 target  ← 신규 (2026-05-22)
  · PHISH_INITIAL_ACCESS × {naver, nhn}  — 4+4 target  ← 신규 (2026-05-22)
  · INSIDER_THREAT       × {naver, nhn}  — 5+5 target  ← 신규 (2026-05-22)

설계 근거:
  · 시드(`data/collection_targets/*.json`)와 1:1 정합
  · NCP raw 패턴: actionName/productName 키워드 (parsers.ncp 결과 기반)
  · NHN raw 패턴: event_id prefix regex (parsers.nhn 결과 기반)

향후 확장: AUDIT_LOG_TAMPERING / MULTI_CSP_LATERAL 시 동일 패턴으로 매처 추가.
"""
import re
from typing import Callable, Optional


# ── NCP × CREDENTIAL_THEFT ─────────────────────────────────


def ncp_credential_theft(ev: dict) -> Optional[str]:
    """NCP raw event(parsers.ncp.parse 결과 한 건) → target_id 또는 None."""
    action = (ev.get("action") or "").strip()
    product = (ev.get("product_name") or "").strip()
    action_l = action.lower()

    if any(k in action_l for k in ("login", "logout", "mfa", "console login")):
        return "CT-NCP-IAM-001"
    if product == "SubAccount" or any(
        k in action
        for k in (
            "AccessKey",
            "Password",
            "AttachSubAccountPolicy",
            "DetachSubAccountPolicy",
            "CreateLoginProfile",
            "ChangePassword",
        )
    ):
        return "CT-NCP-IAM-002"
    if "Server Console" in action or "Decrypt" in action or "RootPassword" in action:
        return "CT-NCP-IAM-003"
    if product in {"Object Storage", "ObjectStorage"} or "Export" in action:
        return "CT-NCP-IAM-004"
    if product in {"Server", "VPC", "VServer"}:
        return "CT-NCP-IAM-005"
    return None


# ── NHN × CREDENTIAL_THEFT ─────────────────────────────────


_NHN_RULES: list[tuple[str, re.Pattern]] = [
    (
        "CT-NHN-IAM-001",
        re.compile(r"^event_id\.iam\.(login|logout|org\.selected|project\.selected)"),
    ),
    (
        "CT-NHN-IAM-002",
        re.compile(r"^event_id\.(iam\.member\.role|role_group)"),
    ),
    (
        "CT-NHN-IAM-003",
        re.compile(
            r"^event_id\.iaas\.(identity\.password_change|s3credential\.|keypair\.)"
        ),
    ),
    (
        "CT-NHN-IAM-004",
        re.compile(r"^event_id\.project\.(product\.enable|member\.)"),
    ),
    (
        "CT-NHN-IAM-005",
        re.compile(r"^event_id\.iaas\.(instance_action|vpc|volume)\."),
    ),
]


def nhn_credential_theft(ev: dict) -> Optional[str]:
    event_id = ev.get("event_id") or ""
    for target_id, pattern in _NHN_RULES:
        if pattern.match(event_id):
            return target_id
    return None


# ── NCP × PRIVILEGE_ESCALATION ─────────────────────────────


def ncp_privilege_escalation(ev: dict) -> Optional[str]:
    """NCP raw event → PE target_id (CT-NCP-PRIV-001~004).

    핵심 패턴 (synthetic ncp_privilege_escalation.json 기반):
      · Create sub account / Create AccessKey / Create Login Key   → 계정·자격증명 생성
      · Attach/Replace policy to sub account                       → 권한 부여
      · Login                                                       → 후속 로그인 (보강)
    """
    action = (ev.get("action") or "").strip()
    action_l = action.lower()
    product = (ev.get("product_name") or "").strip()

    if "create sub account" in action_l or "createsubaccount" in action_l.replace(" ", ""):
        return "CT-NCP-PRIV-001"
    if "attach policy" in action_l or "replace policy" in action_l or "attachsubaccountpolicy" in action_l.replace(" ", ""):
        return "CT-NCP-PRIV-002"
    if "create accesskey" in action_l or "create login key" in action_l or "createloginprofile" in action_l.replace(" ", ""):
        return "CT-NCP-PRIV-003"
    # Login 은 PE 시드의 corroborating — CT 매처와 우선순위 충돌 막기 위해 PE 컨텍스트에서만 매칭
    if action_l == "login" and product == "SubAccount":
        return "CT-NCP-PRIV-004"
    return None


# ── NHN × PRIVILEGE_ESCALATION ─────────────────────────────


_NHN_PRIV_RULES: list[tuple[str, re.Pattern]] = [
    # member.role.update — IAM 역할 변경 (가장 강한 권한 상승 신호)
    ("CT-NHN-PRIV-001", re.compile(r"^event_id\.iam\.member\.role\.")),
    # org IAM member add/update — 조직 단위 멤버 변동
    ("CT-NHN-PRIV-002", re.compile(r"^event_id\.org\.iam\.member\.")),
    # project member update — 프로젝트 단위
    ("CT-NHN-PRIV-003", re.compile(r"^event_id\.project\.member\.")),
    # project product enable — 프로젝트 권한 확장 (보강)
    ("CT-NHN-PRIV-004", re.compile(r"^event_id\.project\.product\.")),
    # login — 후속 로그인 (보강)
    ("CT-NHN-PRIV-005", re.compile(r"^event_id\.iam\.login")),
]


def nhn_privilege_escalation(ev: dict) -> Optional[str]:
    event_id = ev.get("event_id") or ""
    for target_id, pattern in _NHN_PRIV_RULES:
        if pattern.match(event_id):
            return target_id
    return None


# ── NCP × DATA_EXFILTRATION ────────────────────────────────


def ncp_data_exfiltration(ev: dict) -> Optional[str]:
    """NCP raw event → DE target_id (CT-NCP-DE-001~004).

    핵심 패턴 (synthetic ncp_data_exfiltration.json 기반):
      · Request/Complete For Exporting To Object Storage  → 데이터 유출 본행위 (-001)
      · Cross Account Put Object                          → 외부 계정 객체 복사 (-001)
      · Issue PreSigned URL External                      → 외부 공유 링크 발급 (-001)
      · HTTP Plain Upload                                 → 평문 HTTP 업로드 (-001)
      · Disable AccessKey                                 → 흔적 지움 (-002)
      · Login                                             → 초기 접근 (-003)

    Phase J fix (2026-05-26): 누락된 3 advanced exfil 패턴 추가
      — Cross Account Put Object / PreSigned URL / HTTP Plain Upload
      (test_matchers e2e 14/17 → 17/17 fix)
    """
    action = (ev.get("action") or "").strip()
    action_l = action.lower()
    product = (ev.get("product_name") or "").strip()

    # 데이터 유출 본행위 (다양한 경로 — 객체 저장소·외부 링크·평문 업로드)
    exfil_keywords = (
        "exporting to object storage",
        "cross account put object",
        "presigned url external",
        "presigned url",  # 변종 호환
        "http plain upload",
        "external upload",  # 변종 호환
    )
    if any(k in action_l for k in exfil_keywords):
        return "CT-NCP-DE-001"
    if product in {"Object Storage", "ObjectStorage"} and "export" in action_l:
        return "CT-NCP-DE-001"
    if "disable accesskey" in action_l or "disableaccesskey" in action_l.replace(" ", ""):
        return "CT-NCP-DE-002"
    if action_l == "login":
        return "CT-NCP-DE-003"
    return None


# ── NHN × DATA_EXFILTRATION ────────────────────────────────


_NHN_DE_RULES: list[tuple[str, re.Pattern]] = [
    # object_storage object upload/download — 데이터 유출 본행위
    ("CT-NHN-DE-001", re.compile(r"^event_id\.object_storage\.object\.")),
    # s3credential create/delete — 외부 액세스 키 발급/삭제 (유출 채널)
    ("CT-NHN-DE-002", re.compile(r"^event_id\.iaas\.s3credential\.")),
    # login — 초기 접근 보강
    ("CT-NHN-DE-003", re.compile(r"^event_id\.iam\.login")),
]


def nhn_data_exfiltration(ev: dict) -> Optional[str]:
    event_id = ev.get("event_id") or ""
    for target_id, pattern in _NHN_DE_RULES:
        if pattern.match(event_id):
            return target_id
    return None


# ── NCP × AUDIT_LOG_TAMPERING ──────────────────────────────


def ncp_audit_log_tampering(ev: dict) -> Optional[str]:
    """NCP raw event → AUDIT target_id (CT-NCP-AUDIT-001~004).

    핵심 패턴 (Anti-forensics 행위):
      · Activity Tracer 자체 비활성화/삭제                 → CT-NCP-AUDIT-001
      · Disable/Delete AccessKey                            → CT-NCP-AUDIT-002
      · Detach policy / Delete sub account                  → CT-NCP-AUDIT-003
      · Delete/Stop Server, Delete Bucket                   → CT-NCP-AUDIT-004
    """
    action = (ev.get("action") or "").strip()
    action_l = action.lower()
    product = (ev.get("product_name") or "").strip()

    # Tracer 자체 변조 — 가장 결정적 신호
    if "activity tracer" in action_l or "tracer" in action_l:
        return "CT-NCP-AUDIT-001"
    if "disable accesskey" in action_l or "delete accesskey" in action_l or "deactivate" in action_l:
        return "CT-NCP-AUDIT-002"
    if (
        "detach policy" in action_l
        or "delete sub account" in action_l
        or "delete policy" in action_l
        or "deletesubaccount" in action_l.replace(" ", "")
    ):
        return "CT-NCP-AUDIT-003"
    if (
        "delete server" in action_l
        or "stop server" in action_l
        or "delete bucket" in action_l
        or (product in {"Object Storage", "ObjectStorage"} and "delete" in action_l)
    ):
        return "CT-NCP-AUDIT-004"
    return None


# ── NHN × AUDIT_LOG_TAMPERING ──────────────────────────────


_NHN_AUDIT_RULES: list[tuple[str, re.Pattern]] = [
    # Trail 자체 변경 — 가장 결정적 신호
    ("CT-NHN-AUDIT-001", re.compile(r"^event_id\.cloud_trail\.")),
    # 자격증명 폐기 (anti-forensics)
    (
        "CT-NHN-AUDIT-002",
        re.compile(r"^event_id\.iaas\.(s3credential|keypair)\.delete"),
    ),
    # 멤버·역할 삭제
    (
        "CT-NHN-AUDIT-003",
        re.compile(
            r"^event_id\.(iam|org\.iam)\.member\.(delete|role\.delete)"
        ),
    ),
    # 인프라·데이터 파괴
    (
        "CT-NHN-AUDIT-004",
        re.compile(
            r"^event_id\.(iaas\.instance_action\.delete|object_storage\.bucket\.delete)"
        ),
    ),
]


def nhn_audit_log_tampering(ev: dict) -> Optional[str]:
    event_id = ev.get("event_id") or ""
    for target_id, pattern in _NHN_AUDIT_RULES:
        if pattern.match(event_id):
            return target_id
    return None


# ── NCP × RANSOMWARE ─────────────────────────────────────────


def ncp_ransomware(ev: dict) -> Optional[str]:
    """NCP raw → RANSOM target_id (CT-NCP-RANSOM-001~005)."""
    action = (ev.get("action") or "").strip()
    action_l = action.lower()
    product = (ev.get("product_name") or "").strip()

    # Object Storage 대량 조작 — Put/Get/Delete/Copy/Export
    if product in {"Object Storage", "ObjectStorage"} or any(
        k in action_l for k in ("putobject", "getobject", "deleteobject", "copyobject", "exporting to object storage")
    ):
        return "CT-NCP-RANSOM-001"
    # 서버 인스턴스 중지/재시작
    if any(k in action_l for k in ("shutdown server", "start server instance", "stop server", "restart server")):
        return "CT-NCP-RANSOM-002"
    # 백업·스냅샷 삭제
    if "snapshot" in action_l or ("delete" in action_l and ("backup" in action_l or "snapshot" in action_l)):
        return "CT-NCP-RANSOM-003"
    # 초기 접근
    if action_l == "login":
        return "CT-NCP-RANSOM-004"
    # 감사 로그 변조 (RANSOM 컨텍스트에서)
    if "tracer" in action_l or "disable auto export" in action_l:
        return "CT-NCP-RANSOM-005"
    return None


# ── NHN × RANSOMWARE ─────────────────────────────────────────


_NHN_RANSOM_RULES: list[tuple[str, re.Pattern]] = [
    # Object Storage 대량 조작
    ("CT-NHN-RANSOM-001", re.compile(r"^event_id\.object_storage\.object\.(upload|delete)")),
    # 인스턴스 정지/Shelve
    ("CT-NHN-RANSOM-002", re.compile(r"^event_id\.iaas\.instance_action\.(stop|shelve)")),
    # 인프라 파괴 (VPC/볼륨 삭제)
    ("CT-NHN-RANSOM-003", re.compile(r"^event_id\.iaas\.(vpc|volume)\.delete")),
    # IAM 인증
    ("CT-NHN-RANSOM-004", re.compile(r"^event_id\.iam\.login")),
    # Object Storage 다운로드 (이중협박)
    ("CT-NHN-RANSOM-005", re.compile(r"^event_id\.object_storage\.object\.download")),
]


def nhn_ransomware(ev: dict) -> Optional[str]:
    event_id = ev.get("event_id") or ""
    for tid, pat in _NHN_RANSOM_RULES:
        if pat.match(event_id):
            return tid
    return None


# ── NCP × MISCONFIG_EXPOSURE ────────────────────────────────


def ncp_misconfig_exposure(ev: dict) -> Optional[str]:
    """NCP raw → MISCONF target_id (CT-NCP-MISCONF-001~004)."""
    action = (ev.get("action") or "").strip()
    action_l = action.lower()
    product = (ev.get("product_name") or "").strip()

    # Object Storage ACL/버킷 정책
    if any(k in action_l for k in ("putbucketacl", "putbucketpolicy", "bucket policy", "bucket acl")):
        return "CT-NCP-MISCONF-001"
    # VPC/Security Group 변경
    if any(k in action_l for k in ("accesscontrolgroup", "putaccesscontrolgroup", "security group")) or (
        product == "VPC"
    ):
        return "CT-NCP-MISCONF-002"
    # Sub Account 기본 정책
    if "attach policy" in action_l or "replace policy" in action_l or "default policy" in action_l:
        return "CT-NCP-MISCONF-003"
    # 로그인 (노출 접근 확인)
    if action_l == "login":
        return "CT-NCP-MISCONF-004"
    return None


# ── NHN × MISCONFIG_EXPOSURE ────────────────────────────────


_NHN_MISCONF_RULES: list[tuple[str, re.Pattern]] = [
    # Object Storage container 메타데이터
    (
        "CT-NHN-MISCONF-001",
        re.compile(r"^event_id\.object_storage\.(container|account)\.metadata"),
    ),
    # Security Group / VPC
    ("CT-NHN-MISCONF-002", re.compile(r"^event_id\.iaas\.(security_group|vpc)\.")),
    # IAM 기본 계정·과도 권한
    ("CT-NHN-MISCONF-003", re.compile(r"^event_id\.(iam|org\.iam)\.member\.")),
    # Object Storage object 다운로드 (노출 확인)
    ("CT-NHN-MISCONF-004", re.compile(r"^event_id\.object_storage\.object\.download")),
]


def nhn_misconfig_exposure(ev: dict) -> Optional[str]:
    event_id = ev.get("event_id") or ""
    for tid, pat in _NHN_MISCONF_RULES:
        if pat.match(event_id):
            return tid
    return None


# ── NCP × PHISH_INITIAL_ACCESS ──────────────────────────────


def ncp_phish_initial_access(ev: dict) -> Optional[str]:
    """NCP raw → PHISH target_id (CT-NCP-PHISH-001~005).

    Phase J fix (2026-05-26): DNS Tunnel·C2 채널 패턴 추가 (CT-NCP-PHISH-005)
      — 피싱 후속 C2/exfil 채널 (MITRE T1071.004 DNS).
      (test_matchers e2e 5/6 → 6/6 fix)
    """
    action = (ev.get("action") or "").strip()
    action_l = action.lower()

    # Sub Account 인증
    if action_l == "login" or "mfa" in action_l or "console login" in action_l:
        return "CT-NCP-PHISH-001"
    # 자격증명 변경
    if any(k in action_l for k in ("change password", "create accesskey", "create login key")):
        return "CT-NCP-PHISH-002"
    # 백도어 계정 생성
    if "create sub account" in action_l:
        return "CT-NCP-PHISH-003"
    # 감사 로그 변조
    if "tracer" in action_l or "disable auto export" in action_l:
        return "CT-NCP-PHISH-004"
    # C2/exfil 채널 — DNS Tunnel·beacon·callback (MITRE T1071.004)
    if "dns tunnel" in action_l or "c2 callback" in action_l or "beacon" in action_l:
        return "CT-NCP-PHISH-005"
    return None


# ── NHN × PHISH_INITIAL_ACCESS ──────────────────────────────


_NHN_PHISH_RULES: list[tuple[str, re.Pattern]] = [
    # IAM 인증
    ("CT-NHN-PHISH-001", re.compile(r"^event_id\.iam\.login")),
    # 자격증명 변경
    (
        "CT-NHN-PHISH-002",
        re.compile(
            r"^event_id\.iaas\.(identity\.password_change|s3credential\.create|keypair\.create)"
        ),
    ),
    # IAM 멤버 초대·권한
    (
        "CT-NHN-PHISH-003",
        re.compile(r"^event_id\.(iam|org\.iam)\.member\.(add|role)"),
    ),
    # 리소스 조작 (후속 행위)
    ("CT-NHN-PHISH-004", re.compile(r"^event_id\.iaas\.instance_action\.")),
    # Phase J fix (2026-05-26) — C2 채널 (DNS tunnel·beacon·callback, MITRE T1071.004)
    (
        "CT-NHN-PHISH-005",
        re.compile(r"^event_id\.network\.(dns\.tunnel|c2|beacon)"),
    ),
]


def nhn_phish_initial_access(ev: dict) -> Optional[str]:
    event_id = ev.get("event_id") or ""
    for tid, pat in _NHN_PHISH_RULES:
        if pat.match(event_id):
            return tid
    return None


# ── NCP × INSIDER_THREAT ────────────────────────────────────


def ncp_insider_threat(ev: dict) -> Optional[str]:
    """NCP raw → INSIDER target_id (CT-NCP-INSIDER-001~005)."""
    action = (ev.get("action") or "").strip()
    action_l = action.lower()
    product = (ev.get("product_name") or "").strip()

    # Object Storage 대량 다운로드·내보내기
    if product in {"Object Storage", "ObjectStorage"} or "exporting to object storage" in action_l or "getobject" in action_l:
        return "CT-NCP-INSIDER-001"
    # 자기 권한 상승
    if "attach policy" in action_l or "replace policy" in action_l:
        return "CT-NCP-INSIDER-002"
    # 감사 로그 변조·삭제
    if "tracer" in action_l or "disable auto export" in action_l:
        return "CT-NCP-INSIDER-003"
    # 인증 (접근 패턴)
    if action_l == "login":
        return "CT-NCP-INSIDER-004"
    # 리소스 파괴
    if "delete server" in action_l or "delete bucket" in action_l:
        return "CT-NCP-INSIDER-005"
    return None


# ── NHN × INSIDER_THREAT ────────────────────────────────────


_NHN_INSIDER_RULES: list[tuple[str, re.Pattern]] = [
    # Object Storage 대량 다운로드
    ("CT-NHN-INSIDER-001", re.compile(r"^event_id\.object_storage\.object\.(download|upload)")),
    # IAM 권한 변경 (자기 상승)
    ("CT-NHN-INSIDER-002", re.compile(r"^event_id\.(iam|org\.iam)\.member\.role")),
    # 자격증명 삭제 (흔적 제거)
    ("CT-NHN-INSIDER-003", re.compile(r"^event_id\.iaas\.s3credential\.delete")),
    # IAM 인증 (접근 패턴)
    ("CT-NHN-INSIDER-004", re.compile(r"^event_id\.iam\.login")),
    # 인프라 파괴
    ("CT-NHN-INSIDER-005", re.compile(r"^event_id\.iaas\.instance_action\.delete")),
]


def nhn_insider_threat(ev: dict) -> Optional[str]:
    event_id = ev.get("event_id") or ""
    for tid, pat in _NHN_INSIDER_RULES:
        if pat.match(event_id):
            return tid
    return None


# ── 디스패처 ───────────────────────────────────────────────

# (csp, incident_type) → matcher fn
_REGISTRY: dict[tuple[str, str], Callable[[dict], Optional[str]]] = {
    ("naver", "CREDENTIAL_THEFT"): ncp_credential_theft,
    ("nhn", "CREDENTIAL_THEFT"): nhn_credential_theft,
    # dev3 (2026-05-19) — PE/DE 매처 추가
    ("naver", "PRIVILEGE_ESCALATION"): ncp_privilege_escalation,
    ("nhn", "PRIVILEGE_ESCALATION"): nhn_privilege_escalation,
    ("naver", "DATA_EXFILTRATION"): ncp_data_exfiltration,
    ("nhn", "DATA_EXFILTRATION"): nhn_data_exfiltration,
    # 2026-05-21 — AUDIT 매처 추가
    ("naver", "AUDIT_LOG_TAMPERING"): ncp_audit_log_tampering,
    ("nhn", "AUDIT_LOG_TAMPERING"): nhn_audit_log_tampering,
    # 2026-05-22 — dev3 C-1 신규 4종 매처 추가
    ("naver", "RANSOMWARE"): ncp_ransomware,
    ("nhn", "RANSOMWARE"): nhn_ransomware,
    ("naver", "MISCONFIG_EXPOSURE"): ncp_misconfig_exposure,
    ("nhn", "MISCONFIG_EXPOSURE"): nhn_misconfig_exposure,
    ("naver", "PHISH_INITIAL_ACCESS"): ncp_phish_initial_access,
    ("nhn", "PHISH_INITIAL_ACCESS"): nhn_phish_initial_access,
    ("naver", "INSIDER_THREAT"): ncp_insider_threat,
    ("nhn", "INSIDER_THREAT"): nhn_insider_threat,
}


def match(csp: str, incident_type: str, ev: dict) -> Optional[str]:
    """(csp, incident_type) 에 등록된 매처 호출, 없으면 None."""
    fn = _REGISTRY.get((csp, incident_type))
    if fn is None:
        return None
    return fn(ev)
