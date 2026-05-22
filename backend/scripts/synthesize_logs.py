"""합성 NCP/NHN raw 로그 생성기.

목적
----
실 raw 로그(NCP 81 + NHN 147)는 김병우 PC에 있고 민감 정보(이메일·UUID·세션쿠키)라
git 공유 불가. 시연 노트북·다른 팀원 환경·CI 에서도 V-2 업로드 → 풀 파이프라인이
동작하도록, 다음 3개 정의와 100% 호환되는 raw 로그를 코드로 생성한다.

  - `data/mapping_rules/{ncp_cloudtrail,nhn_cloud_trail}.json`
  - `data/attack_rules/rules.json` (22룰)
  - `core/ingestion/matchers.py` (collection_targets 매칭)

시나리오 4종
------------
  ncp_none         — NCP CREDENTIAL_THEFT, 모든 REQUIRED 수집 → 갭 NONE
  ncp_collection   — NCP CREDENTIAL_THEFT, IAM-003 누락 → 갭 COLLECTION
  nhn_none         — NHN CREDENTIAL_THEFT, 모든 REQUIRED 수집 → 갭 NONE
  nhn_collection   — NHN CREDENTIAL_THEFT, IAM-002 누락 → 갭 COLLECTION

설계 결정
---------
  - 공격자 IP `115.91.214.5` 공유 — 실 raw에서 관찰된 멀티 CSP 연계 패턴 유지
  - 시간순 Kill Chain (Initial Access → Persistence → Lateral Movement → Impact/Exfil)
  - `--seed` 옵션으로 결정성 보장. 동일 인자면 동일 결과
  - NCP eventTime 두 형식(Unix ms / 'YYYY-MM-DD HH:MM:SS UTC') 혼합 — 파서 강건성 검증
  - NHN eventTime `+0000` ISO8601

사용 예
-------
  # 단일 시나리오
  python -m scripts.synthesize_logs --scenario ncp_none --out data/synthetic/ncp_none.json

  # 4종 일괄 생성 (시연 노트북 셋업 시 권장)
  python -m scripts.synthesize_logs --all --out-dir data/synthetic
"""
import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

# ───────────────────────────────────────────────────────────
# 상수
# ───────────────────────────────────────────────────────────
ATTACKER_IP = "115.91.214.5"  # 실 raw에서 NCP/NHN 양쪽 공유한 외부 IP
NORMAL_IPS = ["172.30.10.5", "192.168.1.20", "172.30.10.6"]


# ───────────────────────────────────────────────────────────
# 시간 포매터
# ───────────────────────────────────────────────────────────
def _utc_string(dt: datetime) -> str:
    """NCP 콘솔 응답 형식 'YYYY-MM-DD HH:MM:SS UTC'."""
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _unix_ms(dt: datetime) -> int:
    """NCP Tracer Export 형식 Unix ms."""
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def _iso_with_offset(dt: datetime) -> str:
    """NHN 형식 ISO8601 with '+0000' offset (밀리초 포함)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000+0000")


# ───────────────────────────────────────────────────────────
# NCP event factory
# ───────────────────────────────────────────────────────────
def _ncp_event(
    *,
    action: str,
    result: str,
    when: datetime,
    actor: str,
    ip: str,
    product_name: str = "SubAccount",
    user_type: str = "SUB_ACCOUNT",
    use_unix_ms: bool = False,
) -> dict:
    """matchers.ncp_credential_theft 와 mapping_rules/ncp_cloudtrail.json 형식 준수."""
    return {
        "historyId": f"h-{uuid.uuid4().hex[:12]}",
        "nrn": f"nrn:ncp:iam:KR:5000000:account/{actor}",
        "regionCode": "KR",
        "regionName": "Korea, Republic of",
        "resourceType": "Account",
        "productName": product_name,
        "actionUserType": user_type,
        "actionSubAccountNo": str(random.randint(10_000_000, 99_999_999)),
        "sourceType": "CONSOLE",
        "domainCode": "kr",
        "action": action,
        "actionResultType": result,
        "eventTime": _unix_ms(when) if use_unix_ms else _utc_string(when),
        "content": {
            "actionUserName": actor,
            "sourceIp": ip,
            "productData": {},
        },
    }


# ───────────────────────────────────────────────────────────
# NHN event factory
# ───────────────────────────────────────────────────────────
def _nhn_event(
    *,
    event_id: str,
    result: str,
    when: datetime,
    user_name: str,
    user_id: str,
    user_id_no: str,
    ip: str,
) -> dict:
    """matchers.nhn_credential_theft 와 mapping_rules/nhn_cloud_trail.json 형식 준수."""
    response = (
        '{"result":"success"}'
        if result == "SUCCESS"
        else '{"result":"fail","reason":"unauthorized"}'
    )
    return {
        "eventLogUuid": str(uuid.uuid4()),
        "eventTime": _iso_with_offset(when),
        "eventId": event_id,
        "result": result,
        "userName": user_name,
        "userIp": ip,
        "userId": user_id,
        "userIdNo": user_id_no,
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "eventSourceType": "ADMIN_CONSOLE",
        "orgId": "org-synthetic-001",
        "projectId": "p-synthetic-001",
        "projectName": "main-project",
        "appKey": "appkey-synthetic-001",
        "tenantId": "tenant-synthetic-001",
        "request": "{}",
        "response": response,
    }


# ───────────────────────────────────────────────────────────
# 시나리오 — NCP Kill Chain
# ───────────────────────────────────────────────────────────
def scenario_ncp_kill_chain(
    *, start: datetime, include_iam_003: bool = True
) -> list[dict]:
    """NCP CREDENTIAL_THEFT Kill Chain.

    Args:
        start: 시뮬레이션 시작 시각 (UTC).
        include_iam_003: False면 IAM-003(Server Console + Decrypt) 빠짐 → COLLECTION 갭.
    """
    events: list[dict] = []
    # 실 raw(activity_logs_full.json) 의 시뮬레이션 계정명과 통일 — kb/case_db.json 사례와 정합
    attacker = "attack-sim"
    t = start

    # 베이스라인 — 정상 사용자 Login 2건
    for normal_user in ("alice", "bob"):
        events.append(
            _ncp_event(
                action="Login",
                result="SUCCESS",
                when=t,
                actor=normal_user,
                ip=random.choice(NORMAL_IPS),
            )
        )
        t += timedelta(seconds=random.randint(10, 30))

    # Initial Access — brute-force(FAIL × 2) + SUCCESS
    t = start + timedelta(minutes=5)
    for _ in range(2):
        events.append(
            _ncp_event(
                action="Login",
                result="FAIL",
                when=t,
                actor=attacker,
                ip=ATTACKER_IP,
            )
        )
        t += timedelta(seconds=random.randint(2, 6))
    events.append(
        _ncp_event(
            action="Login",
            result="SUCCESS",
            when=t,
            actor=attacker,
            ip=ATTACKER_IP,
        )
    )
    t += timedelta(minutes=1)

    # 자격증명·권한 변경 (IAM-002) — Persistence
    for action in (
        "Create AccessKey",
        "Change password",
        "Create sub account",
        "Attach policy to sub account",
    ):
        events.append(
            _ncp_event(
                action=action,
                result="SUCCESS",
                when=t,
                actor=attacker,
                ip=ATTACKER_IP,
                product_name="SubAccount",
            )
        )
        t += timedelta(minutes=random.randint(1, 3))

    # Server Console 접근 (IAM-003) — COLLECTION 시나리오에선 생략
    if include_iam_003:
        events.append(
            _ncp_event(
                action="Access Server Connect Console",
                result="SUCCESS",
                when=t,
                actor=attacker,
                ip=ATTACKER_IP,
                product_name="Server",
            )
        )
        t += timedelta(minutes=1)
        events.append(
            _ncp_event(
                action="Decrypt root password",
                result="SUCCESS",
                when=t,
                actor=attacker,
                ip=ATTACKER_IP,
                product_name="Server",
            )
        )
        t += timedelta(minutes=2)

    # Object Storage 데이터 유출 (IAM-004) — Exfiltration
    # 의도적으로 Unix ms 형식 사용해 두 시간 포맷 동시 검증
    for action in (
        "Request For Exporting To Object Storage",
        "Complete For Exporting To Object Storage",
    ):
        events.append(
            _ncp_event(
                action=action,
                result="SUCCESS",
                when=t,
                actor=attacker,
                ip=ATTACKER_IP,
                product_name="Object Storage",
                use_unix_ms=True,
            )
        )
        t += timedelta(minutes=1)

    # 인프라 조작 (IAM-005) — Impact
    for action in ("Start Server Instance", "Shutdown Server Instance"):
        events.append(
            _ncp_event(
                action=action,
                result="SUCCESS",
                when=t,
                actor=attacker,
                ip=ATTACKER_IP,
                product_name="Server",
            )
        )
        t += timedelta(minutes=random.randint(1, 2))

    # 흔적 제거 (IAM-002) — Impact
    events.append(
        _ncp_event(
            action="Disable AccessKey",
            result="SUCCESS",
            when=t,
            actor=attacker,
            ip=ATTACKER_IP,
            product_name="SubAccount",
        )
    )

    return events


# ───────────────────────────────────────────────────────────
# 시나리오 — NHN Kill Chain
# ───────────────────────────────────────────────────────────
def scenario_nhn_kill_chain(
    *, start: datetime, include_iam_002: bool = True
) -> list[dict]:
    """NHN CREDENTIAL_THEFT Kill Chain.

    Args:
        start: 시뮬레이션 시작 시각 (UTC).
        include_iam_002: False면 IAM-002(role 변경) 빠짐 → COLLECTION 갭.
            (실제 NHN raw 147건도 IAM-002 누락이 관찰되어 같은 패턴 재현)
    """
    events: list[dict] = []
    attacker = "attack"
    attacker_id = "attack@victim.org"
    attacker_no = "uuid-attacker-001"
    t = start

    # 베이스라인 — 정상 사용자 Login
    for user_name, email in (("alice", "alice@victim.org"), ("bob", "bob@victim.org")):
        events.append(
            _nhn_event(
                event_id="event_id.iam.login",
                result="SUCCESS",
                when=t,
                user_name=user_name,
                user_id=email,
                user_id_no=f"uuid-{user_name}",
                ip=random.choice(NORMAL_IPS),
            )
        )
        t += timedelta(seconds=random.randint(10, 30))

    # Initial Access — brute-force + SUCCESS
    t = start + timedelta(minutes=5)
    for _ in range(2):
        events.append(
            _nhn_event(
                event_id="event_id.iam.login",
                result="FAIL",
                when=t,
                user_name=attacker,
                user_id=attacker_id,
                user_id_no=attacker_no,
                ip=ATTACKER_IP,
            )
        )
        t += timedelta(seconds=random.randint(3, 8))
    events.append(
        _nhn_event(
            event_id="event_id.iam.login",
            result="SUCCESS",
            when=t,
            user_name=attacker,
            user_id=attacker_id,
            user_id_no=attacker_no,
            ip=ATTACKER_IP,
        )
    )
    t += timedelta(minutes=1)

    # 조직/프로젝트 컨텍스트 (IAM-001)
    for event_id in ("event_id.iam.org.selected", "event_id.iam.project.selected"):
        events.append(
            _nhn_event(
                event_id=event_id,
                result="SUCCESS",
                when=t,
                user_name=attacker,
                user_id=attacker_id,
                user_id_no=attacker_no,
                ip=ATTACKER_IP,
            )
        )
        t += timedelta(seconds=30)

    # 권한 변경 (IAM-002) — COLLECTION 시나리오에선 생략
    if include_iam_002:
        events.append(
            _nhn_event(
                event_id="event_id.iam.member.role.update",
                result="SUCCESS",
                when=t,
                user_name=attacker,
                user_id=attacker_id,
                user_id_no=attacker_no,
                ip=ATTACKER_IP,
            )
        )
        t += timedelta(minutes=2)

    # 자격증명 조작 (IAM-003) — Persistence
    for event_id in (
        "event_id.iaas.s3credential.create",
        "event_id.iaas.keypair.create",
        "event_id.iaas.identity.password_change",
    ):
        events.append(
            _nhn_event(
                event_id=event_id,
                result="SUCCESS",
                when=t,
                user_name=attacker,
                user_id=attacker_id,
                user_id_no=attacker_no,
                ip=ATTACKER_IP,
            )
        )
        t += timedelta(minutes=random.randint(1, 2))

    # 프로젝트 권한 (IAM-004) — Privilege Escalation
    events.append(
        _nhn_event(
            event_id="event_id.project.product.enable",
            result="FAIL",  # 시연용 — FAIL 케이스도 raw에 섞임
            when=t,
            user_name=attacker,
            user_id=attacker_id,
            user_id_no=attacker_no,
            ip=ATTACKER_IP,
        )
    )
    t += timedelta(seconds=30)
    events.append(
        _nhn_event(
            event_id="event_id.project.member.update",
            result="SUCCESS",
            when=t,
            user_name=attacker,
            user_id=attacker_id,
            user_id_no=attacker_no,
            ip=ATTACKER_IP,
        )
    )
    t += timedelta(minutes=1)

    # Impact (IAM-005)
    events.append(
        _nhn_event(
            event_id="event_id.iaas.instance_action.stop",
            result="SUCCESS",
            when=t,
            user_name=attacker,
            user_id=attacker_id,
            user_id_no=attacker_no,
            ip=ATTACKER_IP,
        )
    )
    t += timedelta(minutes=2)
    events.append(
        _nhn_event(
            event_id="event_id.iaas.vpc.delete_end",
            result="SUCCESS",
            when=t,
            user_name=attacker,
            user_id=attacker_id,
            user_id_no=attacker_no,
            ip=ATTACKER_IP,
        )
    )
    t += timedelta(minutes=1)

    # 흔적 제거 (IAM-003)
    events.append(
        _nhn_event(
            event_id="event_id.iaas.s3credential.delete",
            result="SUCCESS",
            when=t,
            user_name=attacker,
            user_id=attacker_id,
            user_id_no=attacker_no,
            ip=ATTACKER_IP,
        )
    )

    return events


# ───────────────────────────────────────────────────────────
# 시나리오 — NCP Privilege Escalation
# ───────────────────────────────────────────────────────────
def scenario_ncp_privilege_escalation(*, start: datetime) -> list[dict]:
    """NCP 점진적 권한 상승 시나리오.

    dev3 방향(빈 케이스 → 단서 분석 → 사고유형 분류)에 활용:
      - 정상 Login 후 권한 변경(Create sub + Attach policy 다수)이 누적되는 패턴
      - 단서로 사고유형 PRIVILEGE_ESCALATION 분류 가능
      - matchers.py 의 CREDENTIAL_THEFT 룰엔 일부만 매칭(SubAccount=IAM-002 한 묶음)
    """
    events: list[dict] = []
    attacker = "attack-sim"
    t = start

    # 정상 사용자 베이스라인
    for normal_user in ("alice", "bob", "charlie"):
        events.append(
            _ncp_event(
                action="Login",
                result="SUCCESS",
                when=t,
                actor=normal_user,
                ip=random.choice(NORMAL_IPS),
            )
        )
        t += timedelta(seconds=random.randint(15, 45))

    # 공격자 정상 로그인 (위장)
    t = start + timedelta(minutes=8)
    events.append(
        _ncp_event(
            action="Login",
            result="SUCCESS",
            when=t,
            actor=attacker,
            ip=ATTACKER_IP,
        )
    )
    t += timedelta(minutes=2)

    # 권한 상승 체인 (PE 핵심 — Sub Account + Policy 작업 다수)
    for action in (
        "Create sub account",
        "Attach policy to sub account",
        "Create sub account",
        "Attach policy to sub account",
        "Replace policy to sub account",
        "Create Login Key",
        "Create AccessKey",
    ):
        events.append(
            _ncp_event(
                action=action,
                result="SUCCESS",
                when=t,
                actor=attacker,
                ip=ATTACKER_IP,
                product_name="SubAccount",
            )
        )
        t += timedelta(minutes=random.randint(1, 4))

    return events


# ───────────────────────────────────────────────────────────
# 시나리오 — NHN Privilege Escalation
# ───────────────────────────────────────────────────────────
def scenario_nhn_privilege_escalation(*, start: datetime) -> list[dict]:
    """NHN 점진적 권한 상승 시나리오."""
    events: list[dict] = []
    attacker = "attack"
    attacker_id = "attack@victim.org"
    attacker_no = "uuid-attacker-001"
    t = start

    # 정상 베이스라인
    for user_name, email in (
        ("alice", "alice@victim.org"),
        ("bob", "bob@victim.org"),
    ):
        events.append(
            _nhn_event(
                event_id="event_id.iam.login",
                result="SUCCESS",
                when=t,
                user_name=user_name,
                user_id=email,
                user_id_no=f"uuid-{user_name}",
                ip=random.choice(NORMAL_IPS),
            )
        )
        t += timedelta(seconds=random.randint(15, 45))

    # 공격자 위장 로그인
    t = start + timedelta(minutes=8)
    events.append(
        _nhn_event(
            event_id="event_id.iam.login",
            result="SUCCESS",
            when=t,
            user_name=attacker,
            user_id=attacker_id,
            user_id_no=attacker_no,
            ip=ATTACKER_IP,
        )
    )
    t += timedelta(minutes=2)

    # 권한 상승 체인 — IAM role + org member + project member 단계적
    for event_id in (
        "event_id.iam.member.role.update",
        "event_id.org.iam.member.update",
        "event_id.org.iam.member.add",
        "event_id.iam.member.role.update",
        "event_id.project.product.enable",
        "event_id.project.member.update",
        "event_id.project.member.update",
    ):
        events.append(
            _nhn_event(
                event_id=event_id,
                result="SUCCESS",
                when=t,
                user_name=attacker,
                user_id=attacker_id,
                user_id_no=attacker_no,
                ip=ATTACKER_IP,
            )
        )
        t += timedelta(minutes=random.randint(1, 4))

    return events


# ───────────────────────────────────────────────────────────
# 시나리오 — NCP Data Exfiltration
# ───────────────────────────────────────────────────────────
def scenario_ncp_data_exfiltration(*, start: datetime) -> list[dict]:
    """NCP Object Storage 대량 Export 시나리오 — Exfiltration 단서 다수."""
    events: list[dict] = []
    attacker = "attack-sim"
    t = start

    # 정상 베이스라인
    for normal_user in ("alice", "bob"):
        events.append(
            _ncp_event(
                action="Login",
                result="SUCCESS",
                when=t,
                actor=normal_user,
                ip=random.choice(NORMAL_IPS),
            )
        )
        t += timedelta(seconds=random.randint(10, 30))

    # 공격자 로그인
    t = start + timedelta(minutes=10)
    events.append(
        _ncp_event(
            action="Login",
            result="SUCCESS",
            when=t,
            actor=attacker,
            ip=ATTACKER_IP,
        )
    )
    t += timedelta(minutes=2)

    # Object Storage 대량 Export (Request/Complete 페어 다수)
    for _ in range(5):
        events.append(
            _ncp_event(
                action="Request For Exporting To Object Storage",
                result="SUCCESS",
                when=t,
                actor=attacker,
                ip=ATTACKER_IP,
                product_name="Object Storage",
                use_unix_ms=True,
            )
        )
        t += timedelta(seconds=random.randint(20, 90))
        events.append(
            _ncp_event(
                action="Complete For Exporting To Object Storage",
                result="SUCCESS",
                when=t,
                actor=attacker,
                ip=ATTACKER_IP,
                product_name="Object Storage",
                use_unix_ms=True,
            )
        )
        t += timedelta(minutes=random.randint(1, 3))

    # AccessKey 폐기 (흔적 제거)
    events.append(
        _ncp_event(
            action="Disable AccessKey",
            result="SUCCESS",
            when=t,
            actor=attacker,
            ip=ATTACKER_IP,
            product_name="SubAccount",
        )
    )

    return events


# ───────────────────────────────────────────────────────────
# 시나리오 — NHN Data Exfiltration
# ───────────────────────────────────────────────────────────
def scenario_nhn_data_exfiltration(*, start: datetime) -> list[dict]:
    """NHN Object Storage 대량 업로드 시나리오 — Exfiltration 단서."""
    events: list[dict] = []
    attacker = "attack"
    attacker_id = "attack@victim.org"
    attacker_no = "uuid-attacker-001"
    t = start

    # 정상 베이스라인
    for user_name, email in (
        ("alice", "alice@victim.org"),
        ("bob", "bob@victim.org"),
    ):
        events.append(
            _nhn_event(
                event_id="event_id.iam.login",
                result="SUCCESS",
                when=t,
                user_name=user_name,
                user_id=email,
                user_id_no=f"uuid-{user_name}",
                ip=random.choice(NORMAL_IPS),
            )
        )
        t += timedelta(seconds=random.randint(10, 30))

    # 공격자 로그인 + 자격증명 발급
    t = start + timedelta(minutes=10)
    events.append(
        _nhn_event(
            event_id="event_id.iam.login",
            result="SUCCESS",
            when=t,
            user_name=attacker,
            user_id=attacker_id,
            user_id_no=attacker_no,
            ip=ATTACKER_IP,
        )
    )
    t += timedelta(minutes=1)
    events.append(
        _nhn_event(
            event_id="event_id.iaas.s3credential.create",
            result="SUCCESS",
            when=t,
            user_name=attacker,
            user_id=attacker_id,
            user_id_no=attacker_no,
            ip=ATTACKER_IP,
        )
    )
    t += timedelta(minutes=2)

    # Object Storage 대량 업로드 (외부로 데이터 이동 단서)
    for _ in range(6):
        events.append(
            _nhn_event(
                event_id="event_id.object_storage.object.upload",
                result="SUCCESS",
                when=t,
                user_name=attacker,
                user_id=attacker_id,
                user_id_no=attacker_no,
                ip=ATTACKER_IP,
            )
        )
        t += timedelta(seconds=random.randint(15, 60))

    # 자격증명 삭제 (흔적 제거)
    events.append(
        _nhn_event(
            event_id="event_id.iaas.s3credential.delete",
            result="SUCCESS",
            when=t,
            user_name=attacker,
            user_id=attacker_id,
            user_id_no=attacker_no,
            ip=ATTACKER_IP,
        )
    )

    return events


# ───────────────────────────────────────────────────────────
# 시나리오 레지스트리
# ───────────────────────────────────────────────────────────
SCENARIOS: dict[str, Callable[[datetime], list[dict]]] = {
    # CREDENTIAL_THEFT 두 변형 (NONE / COLLECTION)
    "ncp_none": lambda start: scenario_ncp_kill_chain(start=start, include_iam_003=True),
    "ncp_collection": lambda start: scenario_ncp_kill_chain(
        start=start, include_iam_003=False
    ),
    "nhn_none": lambda start: scenario_nhn_kill_chain(start=start, include_iam_002=True),
    "nhn_collection": lambda start: scenario_nhn_kill_chain(
        start=start, include_iam_002=False
    ),
    # 사고유형 확장 — dev3 "빈 케이스 → 단서 분석 → 사고유형 분류" 흐름 지원용
    "ncp_privilege_escalation": lambda start: scenario_ncp_privilege_escalation(start=start),
    "nhn_privilege_escalation": lambda start: scenario_nhn_privilege_escalation(start=start),
    "ncp_data_exfiltration": lambda start: scenario_ncp_data_exfiltration(start=start),
    "nhn_data_exfiltration": lambda start: scenario_nhn_data_exfiltration(start=start),
}


# ───────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────
def _write(events: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] {path}: {len(events)} events")


def main() -> None:
    parser = argparse.ArgumentParser(description="합성 NCP/NHN raw 로그 생성기")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()))
    parser.add_argument("--all", action="store_true", help="등록된 모든 시나리오 일괄 생성")
    parser.add_argument("--out", type=Path, help="단일 시나리오 출력 경로")
    parser.add_argument("--out-dir", type=Path, help="--all 출력 디렉토리")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--start",
        type=lambda s: datetime.fromisoformat(s),
        default=datetime(2026, 5, 13, 2, 30, 0),
        help="시작 시간 ISO 8601 (기본 2026-05-13 02:30:00)",
    )
    args = parser.parse_args()

    if args.all:
        if not args.out_dir:
            parser.error("--all 사용 시 --out-dir 필수")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for name, factory in SCENARIOS.items():
            random.seed(args.seed)  # 시나리오마다 동일 시드 → 재현성
            events = factory(args.start)
            _write(events, args.out_dir / f"{name}.json")
    else:
        if not args.scenario or not args.out:
            parser.error("--scenario 와 --out 모두 필요 (또는 --all 사용)")
        random.seed(args.seed)
        events = SCENARIOS[args.scenario](args.start)
        _write(events, args.out)


if __name__ == "__main__":
    main()
