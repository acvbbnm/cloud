"""collection_targets 매칭 룰.

LogIngestor 에서 분리한 순수 함수 모음.
- DB 의존성 없음 → 단위 테스트 용이
- (csp, incident_type) 조합별 매칭 함수를 등록
- MVP 범위: CREDENTIAL_THEFT × {naver, nhn}

향후 확장: data/collection_targets/target_match_rules.json 으로 룰 외부화 고려.
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


# ── 디스패처 ───────────────────────────────────────────────

# (csp, incident_type) → matcher fn
_REGISTRY: dict[tuple[str, str], Callable[[dict], Optional[str]]] = {
    ("naver", "CREDENTIAL_THEFT"): ncp_credential_theft,
    ("nhn", "CREDENTIAL_THEFT"): nhn_credential_theft,
}


def match(csp: str, incident_type: str, ev: dict) -> Optional[str]:
    """(csp, incident_type) 에 등록된 매처 호출, 없으면 None."""
    fn = _REGISTRY.get((csp, incident_type))
    if fn is None:
        return None
    return fn(ev)
