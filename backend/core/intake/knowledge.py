"""Layer 0 — IncidentTypeKnowledge.

설계서 5.4.2절 + 모듈별_구현_명세.md `IncidentTypeKnowledge` 항목.
사고유형별 관련 ATT&CK 기법 + 핵심 서비스를 제공한다.
MVP는 하드코딩 dict, 추후 data/kb/incident_types.json 등으로 외부화 가능.
"""
from typing import Optional


# HIGH 1 (2026-05-21): 진규 E2E 보고서 §4.1 발견 — 8 사고유형 related_techniques
# 크기 불균형으로 자동 분류가 PRIVILEGE_ESCALATION 으로 쏠림 (2개 기법만 매칭해도
# score_ratio 1.0 달성). 균형 + 클라우드 raw 로그 검출 가능 기법 우선으로 재구성.
#
# 원칙:
#   1. 각 사고유형 4-5 기법으로 균형 (score_ratio 비교 공정성)
#   2. NCP/NHN attack_rules 에서 매핑 가능한 기법 우선 (예: T1485 > T1486)
#   3. raw 검출 불가 기법 (T1486 암호화·T1190 웹 익스플로잇·T1566 피싱) 은 보조
#
# 학술 변호: MITRE ATT&CK Cloud Matrix v14 의 각 사고유형 대표 기법.
_KNOWLEDGE: dict[str, dict] = {
    "CREDENTIAL_THEFT": {
        "related_techniques": ["T1078.004", "T1098.001", "T1110", "T1552", "T1531"],
        "tactics": ["Initial Access", "Credential Access", "Persistence"],
        "key_services": {
            "naver": ["Sub Account", "Cloud Activity Tracer", "Server"],
            "nhn": ["IAM", "Cloud Trail", "S3 Credential", "Keypair"],
        },
    },
    "PRIVILEGE_ESCALATION": {
        # HIGH 1 fix: 2개 → 5개로 확장 (score_ratio 공정성 회복)
        "related_techniques": ["T1098", "T1098.001", "T1136.003", "T1484", "T1548.005"],
        "tactics": ["Privilege Escalation", "Persistence"],
        "key_services": {
            "naver": ["Sub Account", "Resource Manager"],
            "nhn": ["IAM", "Project", "Role Group"],
        },
    },
    "DATA_EXFILTRATION": {
        # HIGH 1 fix: 2개 → 5개로 확장 (T1530 추가 = NCP/NHN attack_rules 신규 P0)
        "related_techniques": ["T1530", "T1537", "T1567", "T1213", "T1119"],
        "tactics": ["Collection", "Exfiltration"],
        "key_services": {
            "naver": ["Object Storage", "Cloud Activity Tracer"],
            "nhn": ["Object Storage", "Cloud Trail"],
        },
    },
    "AUDIT_LOG_TAMPERING": {
        # HIGH 1 fix: 2개 → 4개 (T1531 AccessKey 삭제·T1070 Indicator Removal 세부)
        "related_techniques": ["T1562.008", "T1070", "T1070.004", "T1531"],
        "tactics": ["Defense Evasion", "Impact"],
        "key_services": {
            "naver": ["Cloud Activity Tracer"],
            "nhn": ["Cloud Trail"],
        },
    },
    # MULTI_CSP_LATERAL 항목은 2026-05-19 사용자 결정으로 제거.
    # 환경 변수 multi_cloud (m-010) 만 보조 boost 로 유지.

    # ── dev3 C-1 신규 4종 (2026-05-19) ──
    "RANSOMWARE": {
        # HIGH 1 fix: T1486·T1490 (검출 불가) → T1485·T1489·T1531 (raw 매핑 가능)
        # 진규 §5.1 권고 — T1531 (Account Access Removal) 추가
        "related_techniques": ["T1485", "T1489", "T1531", "T1486", "T1490"],
        "tactics": ["Impact", "Execution"],
        "key_services": {
            "naver": ["Object Storage", "Server", "KMS"],
            "nhn": ["Object Storage", "Instance", "Secure Key Manager"],
        },
    },
    "MISCONFIG_EXPOSURE": {
        # HIGH 1 fix: T1190 (raw 검출 불가) 보조로, T1530·T1580 우선
        "related_techniques": ["T1530", "T1580", "T1538", "T1078.001", "T1190"],
        "tactics": ["Initial Access", "Discovery"],
        "key_services": {
            "naver": ["Object Storage", "VPC", "ACG"],
            "nhn": ["Object Storage", "VPC", "Security Group"],
        },
    },
    "PHISH_INITIAL_ACCESS": {
        # HIGH 1 fix: T1566 (raw 검출 불가) 보조로, T1078.004·T1556·T1110 우선
        # 진규 §5.3 권고 — FAIL→SUCCESS 시간차로 PHISH 변별
        "related_techniques": ["T1078.004", "T1556", "T1110", "T1539", "T1566"],
        "tactics": ["Initial Access", "Credential Access"],
        "key_services": {
            "naver": ["Sub Account", "Cloud Activity Tracer"],
            "nhn": ["IAM", "Cloud Trail"],
        },
    },
    "INSIDER_THREAT": {
        # 이미 raw 매핑 가능 기법 위주 — 1개 추가
        "related_techniques": ["T1078", "T1098", "T1530", "T1562.008", "T1213"],
        "tactics": ["Initial Access", "Collection", "Defense Evasion"],
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
