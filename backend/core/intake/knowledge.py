"""Layer 0 — IncidentTypeKnowledge.

설계서 5.4.2절 + 모듈별_구현_명세.md `IncidentTypeKnowledge` 항목.
사고유형별 관련 ATT&CK 기법 + 핵심 서비스를 제공한다.
MVP는 하드코딩 dict, 추후 data/kb/incident_types.json 등으로 외부화 가능.
"""
from typing import Optional


_KNOWLEDGE: dict[str, dict] = {
    "CREDENTIAL_THEFT": {
        "related_techniques": ["T1078.004", "T1098.001", "T1136.003", "T1552", "T1531"],
        "tactics": ["Initial Access", "Persistence", "Credential Access", "Impact"],
        "key_services": {
            "naver": ["Sub Account", "Cloud Activity Tracer", "Server"],
            "nhn": ["IAM", "Cloud Trail", "S3 Credential", "Keypair"],
        },
    },
    "PRIVILEGE_ESCALATION": {
        "related_techniques": ["T1098", "T1078.004"],
        "tactics": ["Privilege Escalation"],
        "key_services": {
            "naver": ["Sub Account", "Resource Manager"],
            "nhn": ["IAM", "Project", "Role Group"],
        },
    },
    "DATA_EXFILTRATION": {
        "related_techniques": ["T1537", "T1567"],
        "tactics": ["Exfiltration"],
        "key_services": {
            "naver": ["Object Storage", "Cloud Activity Tracer"],
            "nhn": ["Object Storage", "Cloud Trail"],
        },
    },
    "AUDIT_LOG_TAMPERING": {
        "related_techniques": ["T1562.008", "T1070"],
        "tactics": ["Defense Evasion"],
        "key_services": {
            "naver": ["Cloud Activity Tracer"],
            "nhn": ["Cloud Trail"],
        },
    },
    # MULTI_CSP_LATERAL 항목은 2026-05-19 사용자 결정으로 제거.
    # 환경 변수 multi_cloud (m-010) 만 보조 boost 로 유지.

    # ── dev3 C-1 신규 4종 (2026-05-19) ──
    "RANSOMWARE": {
        "related_techniques": ["T1486", "T1490", "T1078", "T1567"],
        "tactics": ["Initial Access", "Execution", "Impact", "Exfiltration"],
        "key_services": {
            "naver": ["Object Storage", "Server", "KMS"],
            "nhn": ["Object Storage", "Instance", "Secure Key Manager"],
        },
    },
    "MISCONFIG_EXPOSURE": {
        "related_techniques": ["T1190", "T1078.001", "T1530", "T1580"],
        "tactics": ["Initial Access", "Discovery"],
        "key_services": {
            "naver": ["Object Storage", "VPC", "ACG"],
            "nhn": ["Object Storage", "VPC", "Security Group"],
        },
    },
    "PHISH_INITIAL_ACCESS": {
        "related_techniques": ["T1566", "T1566.001", "T1078.004", "T1556"],
        "tactics": ["Initial Access", "Credential Access"],
        "key_services": {
            "naver": ["Sub Account", "Cloud Activity Tracer"],
            "nhn": ["IAM", "Cloud Trail"],
        },
    },
    "INSIDER_THREAT": {
        "related_techniques": ["T1078", "T1098", "T1530", "T1562.008"],
        "tactics": ["Initial Access", "Persistence", "Collection", "Defense Evasion"],
        "key_services": {
            "naver": ["Sub Account", "Object Storage", "Cloud Activity Tracer"],
            "nhn": ["IAM", "Object Storage", "Cloud Trail"],
        },
    },
}


class IncidentTypeKnowledge:
    """사고유형별 도메인 지식 — ATT&CK 기법·핵심 서비스 매핑."""

    @classmethod
    def lookup(cls, incident_type: str) -> Optional[dict]:
        """incident_type에 해당하는 지식 객체를 반환한다. 없으면 None."""
        return _KNOWLEDGE.get(incident_type)
