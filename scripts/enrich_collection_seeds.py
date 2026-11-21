"""사이클 6 — 신규 5필드로 collection_targets 시드 풍부화.

대상: AUDIT 외 7 사고유형 × 2 CSP = 14 파일. AUDIT 시드는 이미 동일 형식.

추가 필드:
  · layer              : 'cloud' | 'network' | 'endpoint'
  · hint               : 수집 방법 한 줄 가이드 (NHN/NCP Console 메뉴 경로)
  · cmd                : CLI 자동 수집 명령 (없으면 None)
  · cmd_path           : cmd 결과 파일 경로 (현재 None)
  · auto_collectible   : 자동 수집 가능 여부 (True: API/CLI, False: 수동)
  · mitre_techniques   : 연관 ATT&CK 기법 ID 배열

target_id 별 휴리스틱 매핑 — log_type/description 키워드로 추론. 멱등 (이미 있으면 skip).
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "backend" / "data" / "collection_targets"

# target_id 패턴별 메타데이터 추론 룰
# (pattern_keyword, layer, auto_collectible, base_techniques, hint_template, cmd_template)
RULES = [
    # ── 인증·로그인 계열 ──
    {
        "match": ["인증", "로그인", "IAM-001", "IAM-003", "IAM-004", "PHISH-001", "CRED", "INSIDER-004", "RANSOM-004"],
        "layer": "cloud",
        "hint_ncp": "NCP Console → Monitoring → Activity Tracer → action: Login/MFA Login 필터",
        "hint_nhn": "NHN Console → Governance & Audit → CloudTrail → event_id.iam.login 필터",
        "cmd_ncp": "ncloud iam getSubAccountList --output json > iam_users.json",
        "cmd_nhn": None,
        "auto_collectible": True,
        "techniques": ["T1078.004", "T1110"],
    },
    # ── Object Storage / 데이터 유출 ──
    {
        "match": ["Object Storage", "object_storage", "Export", "Bucket", "버킷", "데이터", "DE-001", "DE-002", "DE-003", "INSIDER-001", "RANSOM-001", "RANSOM-005"],
        "layer": "cloud",
        "hint_ncp": "NCP Console → Object Storage → 버킷 → 접근 로그 + Activity Tracer Export 이벤트 필터",
        "hint_nhn": "NHN Console → Storage → Object Storage → 컨테이너 액세스 로그 + CloudTrail object 이벤트",
        "cmd_ncp": "ncloud storage getBucketList --output json > buckets.json",
        "cmd_nhn": None,
        "auto_collectible": True,
        "techniques": ["T1530", "T1537", "T1567"],
    },
    # ── 권한 변경 / 정책 ──
    {
        "match": ["정책", "권한", "policy", "PRIV-001", "PRIV-002", "PRIV-003", "MISCONF-003", "INSIDER-002", "Sub Account"],
        "layer": "cloud",
        "hint_ncp": "NCP Console → Monitoring → Activity Tracer → AttachPolicy / Create sub account 이벤트",
        "hint_nhn": "NHN Console → Governance & Audit → CloudTrail → iam.member.role.update 필터",
        "cmd_ncp": "ncloud iam listSubAccountPolicy --output json > policies.json",
        "cmd_nhn": None,
        "auto_collectible": True,
        "techniques": ["T1098", "T1098.001", "T1136.003"],
    },
    # ── 자격증명 변경 ──
    {
        "match": ["AccessKey", "자격증명", "credential", "password", "Login Key", "keypair", "s3credential", "IAM-002", "PHISH-002"],
        "layer": "cloud",
        "hint_ncp": "NCP Console → IAM → AccessKey / Login Key 관리 + Activity Tracer Create/Disable AccessKey 이벤트",
        "hint_nhn": "NHN Console → Governance & Audit → CloudTrail → s3credential.create / keypair.create 필터",
        "cmd_ncp": "ncloud iam getAccessKeyList --output json > access_keys.json",
        "cmd_nhn": None,
        "auto_collectible": True,
        "techniques": ["T1098.001", "T1552", "T1556"],
    },
    # ── 서버 / VPC / 네트워킹 ──
    {
        "match": ["서버", "Server", "VPC", "리소스", "Network", "instance", "Security Group", "INSIDER-005", "RANSOM-002", "RANSOM-003", "MISCONF-002"],
        "layer": "network",
        "hint_ncp": "NCP Console → Server / VPC → Activity Tracer → instance/vpc.delete 이벤트",
        "hint_nhn": "NHN Console → Compute → Instance / VPC → CloudTrail iaas.instance/vpc 필터",
        "cmd_ncp": "ncloud server getServerInstanceList --output json > servers.json",
        "cmd_nhn": None,
        "auto_collectible": True,
        "techniques": ["T1485", "T1489"],
    },
]

# 매칭 안 되면 기본값
DEFAULT = {
    "layer": "cloud",
    "hint_ncp": "NCP Console → Monitoring → Activity Tracer 에서 관련 이벤트 필터",
    "hint_nhn": "NHN Console → Governance & Audit → CloudTrail 에서 관련 이벤트 필터",
    "cmd_ncp": None,
    "cmd_nhn": None,
    "auto_collectible": True,
    "techniques": [],
}

NEW_FIELDS = ["layer", "hint", "cmd", "cmd_path", "auto_collectible", "mitre_techniques"]


def infer_meta(target_id: str, log_type: str, description: str, csp: str) -> dict:
    """target_id / log_type / description 으로 메타 추론."""
    haystack = f"{target_id} {log_type} {description}".lower()
    for rule in RULES:
        if any(kw.lower() in haystack for kw in rule["match"]):
            return {
                "layer": rule["layer"],
                "hint": rule[f"hint_{csp_to_ck(csp)}"],
                "cmd": rule[f"cmd_{csp_to_ck(csp)}"],
                "cmd_path": None,
                "auto_collectible": rule["auto_collectible"],
                "mitre_techniques": list(rule["techniques"]),
            }
    # fallback
    return {
        "layer": DEFAULT["layer"],
        "hint": DEFAULT[f"hint_{csp_to_ck(csp)}"],
        "cmd": DEFAULT[f"cmd_{csp_to_ck(csp)}"],
        "cmd_path": None,
        "auto_collectible": DEFAULT["auto_collectible"],
        "mitre_techniques": list(DEFAULT["techniques"]),
    }


def csp_to_ck(csp: str) -> str:
    return "ncp" if csp == "naver" else "nhn"


def enrich_file(path: Path) -> tuple[int, int]:
    """파일 풍부화 — (확장된 행 수, 총 행 수). 멱등."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    enriched = 0
    for row in rows:
        # 5필드 모두 있으면 skip
        if all(f in row for f in NEW_FIELDS):
            continue
        meta = infer_meta(
            row.get("target_id", ""),
            row.get("log_type", ""),
            row.get("description", ""),
            row.get("csp", "naver"),
        )
        for f, v in meta.items():
            if f not in row:
                row[f] = v
        enriched += 1
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return enriched, len(rows)


def main() -> None:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    files = sorted(p for p in DATA.glob("*.json") if "AUDIT" not in p.name)
    print(f"대상: {len(files)} 파일 (AUDIT 제외)")
    print()
    total_enriched = 0
    total_rows = 0
    for p in files:
        e, t = enrich_file(p)
        total_enriched += e
        total_rows += t
        marker = "✓" if e == t else ("=" if e == 0 else "~")
        print(f"  {marker} {p.name:50s} {e}/{t} 행 풍부화")
    print()
    print(f"총: {total_enriched}/{total_rows} 행 풍부화 완료")


if __name__ == "__main__":
    main()
