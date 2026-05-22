"""collection_targets 매칭 룰.

LogIngestor 에서 분리한 순수 함수 모음.
- DB 의존성 없음 → 단위 테스트 용이
- (csp, incident_type) 조합별 매칭 함수를 등록

지원 범위 (2026-05-21 갱신):
  · CREDENTIAL_THEFT     × {naver, nhn}  — 5+5 target
  · PRIVILEGE_ESCALATION × {naver, nhn}  — 4+5 target
  · DATA_EXFILTRATION    × {naver, nhn}  — 3+3 target
  · AUDIT_LOG_TAMPERING  × {naver, nhn}  — 4+4 target  ← 신규 (2026-05-21)

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
    """NCP raw event → DE target_id (CT-NCP-DE-001~003).

    핵심 패턴 (synthetic ncp_data_exfiltration.json 기반):
      · Request/Complete For Exporting To Object Storage  → 데이터 유출 본행위
      · Disable AccessKey                                  → 흔적 지움 (보강)
      · Login                                              → 초기 접근 보강
    """
    action = (ev.get("action") or "").strip()
    action_l = action.lower()
    product = (ev.get("product_name") or "").strip()

    if "exporting to object storage" in action_l or (
        product in {"Object Storage", "ObjectStorage"} and "export" in action_l
    ):
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
}


def match(csp: str, incident_type: str, ev: dict) -> Optional[str]:
    """(csp, incident_type) 에 등록된 매처 호출, 없으면 None."""
    fn = _REGISTRY.get((csp, incident_type))
    if fn is None:
        return None
    return fn(ev)
