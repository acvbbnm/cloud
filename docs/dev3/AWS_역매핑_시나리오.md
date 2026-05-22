# AWS 공개 침해사례 — NCP/NHN 역매핑 시나리오 (dev3 8종 체계)

> 본 문서는 AWS 공개 침해사례를 본 시스템(AI Sherpa)의 NCP/NHN 매핑 룰에 따라 **역매핑(reverse map)** 하여,
> NCP/NHN 환경에서 동일한 Kill Chain이 발생했다면 어떤 raw 로그 시퀀스로 관측되는지를
> **단서 단위(timeline 항목 단위)** 로 재구성한 학습/검증 자료다.
>
> - **dev3 사고유형 8종 체계** (MULTI_CSP_LATERAL 제거, RANSOMWARE/MISCONFIG_EXPOSURE/PHISH_INITIAL_ACCESS/INSIDER_THREAT 신규) × 2편 = **총 16편** (NCP 8 + NHN 8)
> - 모든 `action` 필드는 [`backend/data/attack_rules/rules.json`](../../backend/data/attack_rules/rules.json) 의 22개 룰 패턴과 매칭되도록 작성 (신규 4종은 부분 매칭 — §11 참조)
> - 모든 OCSF 필드 매핑은 [`backend/data/mapping_rules/`](../../backend/data/mapping_rules/) 두 룰셋(NCP/NHN)에 정합
> - 원본 사례 출처는 공개 보고서(인용 표시). 일부 시각·시퀀스는 학습용 합성(합성 표시).

---

## 0. 작성 의도

1. **dev3 C-1 학술 변호 자료**: 본 시스템 8 사고유형 분류가 글로벌 침해 패턴(Capital One, Code Spaces, Colonial Pipeline, MGM Resorts, Capital One, Verkada, Twilio 0ktapus, Twitter 2020, Tesla 2018, Coinbase 2023 등)을 NCP/NHN로 매핑 가능함을 입증.
2. **KB-4 CASE_DB 보강**: [`backend/data/kb/case_db.json`](../../backend/data/kb/case_db.json) 에 청크 16개 신규 추가 → RAG 검색 대상 확장.
3. **트리아지 검증 데이터**: 각 timeline은 [`backend/data/triage/decision_tree.json`](../../backend/data/triage/decision_tree.json) 의 Discovery Loop가 올바른 사고유형 가설로 수렴하는지 회귀 검증 가능.
4. **신규 4종 룰 보강 백로그 식별**: §11에 신규 4종 시나리오가 기존 22개 룰로 *부분만 매칭*되는 점을 명시 — R-NCP-012~ / R-NHN-012~ 신설 후보 도출.

---

## 1. 역매핑 방법론

### 1.1 NCP Cloud Activity Tracer 필드 매핑

| OCSF (정규화) | NCP Tracer (raw) | 비고 |
|---|---|---|
| `time` | `eventTime` | Unix ms 정수 또는 `YYYY-MM-DD HH:MM:SS UTC` 문자열 |
| `activity_name` | `action` | 매칭 키 — 본 문서 timeline 의 `action` 열 |
| `status_code` | `actionResultType` | `SUCCESS→200`, `FAIL→500` |
| `actor_user_name` | `content.actionUserName` | Sub Account 이름 |
| `src_endpoint_ip` | `content.sourceIp` | 외부 IP |

### 1.2 NHN Cloud Trail 필드 매핑

| OCSF (정규화) | NHN Cloud Trail (raw) | 비고 |
|---|---|---|
| `time` | `eventTime` | ISO8601 `+0000` |
| `activity_name` | `eventId` | `event_id.[카테고리].[작업]` 계층 코드 |
| `status_code` | `result` | `SUCCESS→200`, `FAIL→500` |
| `actor_user_name` | `userName` | 별도로 `userId`(이메일), `userIdNo`(UUID) 보존 |
| `src_endpoint_ip` | `userIp` | 외부 IP |

### 1.3 ATT&CK 매핑 룰 (요약 — rules.json 22건)

| Tactic | NCP rule_id | NCP `activity_name` | NHN rule_id | NHN `eventId` |
|---|---|---|---|---|
| Initial Access (T1078.004) | R-NCP-001 | `Login` | R-NHN-001 | `event_id.iam.login` |
| Persistence (T1098.001) | R-NCP-004, 005, 011 | `Create (AccessKey\|access key)`, `Change password`, `Create Login Key` | R-NHN-005, 007, 010 | `event_id.iaas.s3credential.create`, `event_id.iaas.identity.password_change`, `event_id.iaas.keypair.create` |
| Persistence (T1136.003) | R-NCP-009 | `Create sub account` | — | (R-NHN-004 등가) |
| Privilege Escalation (T1098) | R-NCP-010 | `(Attach\|Replace) policy to sub account` | R-NHN-002, 003, 004 | `event_id.project.product.enable`, `event_id.project.member.update`, `event_id.org.iam.member.(update\|add)` |
| Credential Access (T1552) | R-NCP-006 | `Decrypt root password` | — | — |
| Lateral Movement (T1021) | R-NCP-002 | `Access Server Connect Console` | — | — |
| Exfiltration (T1537/T1567) | R-NCP-007 | `(Request\|Complete) For Exporting To Object Storage` | R-NHN-011 | `event_id.object_storage.object.upload` |
| Impact (T1489) | R-NCP-003 | `(Start\|Shutdown) Server Instance` | R-NHN-008 | `event_id.iaas.instance_action.(stop\|shelve)` |
| Impact (T1485) | — | (NCP 매핑 없음) | R-NHN-009 | `event_id.iaas.vpc.delete_end` |
| Impact (T1531) | R-NCP-008 | `(Disable\|Remove) AccessKey` | R-NHN-006 | `event_id.iaas.s3credential.delete` |

### 1.4 dev3 신규 4종 MITRE 매핑 (knowledge.py 기준)

| 사고유형 | 핵심 기법 | NCP 핵심 서비스 | NHN 핵심 서비스 | 룰 매칭 |
|---|---|---|---|---|
| RANSOMWARE | T1486, T1490, T1078, T1567 | Object Storage, Server, Backup, KMS | Object Storage, Instance, Secure Key Manager | 부분(T1078/T1567/T1485/T1489 룰만) |
| MISCONFIG_EXPOSURE | T1190, T1078.001, T1530, T1580 | Object Storage, VPC, ACG | Object Storage, VPC, Security Group | 부분(T1078/T1530 일부, T1190·T1580 직접 매핑 없음) |
| PHISH_INITIAL_ACCESS | T1566, T1566.001, T1078.004, T1556 | IAM, Cloud Activity Tracer | IAM, Cloud Trail | 부분(T1078.004만, T1566은 클라우드 raw 외부 단서) |
| INSIDER_THREAT | T1078, T1098, T1530, T1562.008 | IAM, Object Storage, Activity Tracer | IAM, Object Storage, Cloud Trail | 부분(T1078/T1098 매핑, T1562.008·T1530 부분) |

> **신규 4종 매핑 한계**: dev3 attack_rules 는 5종 시기와 동일한 22개 룰(NCP 11 + NHN 11) — 신규 4종 전용 룰 없음. 본 문서 §11 *룰 보강 후보* 에 신설 백로그 명시.

---

## 2. CREDENTIAL_THEFT

### 2.1 NCP — Capital One 2019 (SSRF → IMDS → STS 토큰 탈취)

**AWS 원본 개요**
- **시기**: 2019-03 ~ 2019-07 (4개월 잠복)
- **행위자**: Paige Thompson (전 AWS 엔지니어)
- **vector**: WAF SSRF → EC2 메타데이터(`169.254.169.254/latest/meta-data/iam/security-credentials/`) → STS 임시 자격증명 탈취
- **핵심 AWS API**: `AssumeRole`, `ListBuckets`, `GetObject`

**역매핑 — AWS 동작 → NCP `action`**

| AWS 동작 | MITRE | NCP 등가 action | rule_id |
|---|---|---|---|
| SSRF 통한 IMDS 접근 | T1078.004 | `Login` (외부 IP) | R-NCP-001 |
| STS AssumeRole | T1552 | `Decrypt root password` | R-NCP-006 |
| 영속화 키 발급 | T1098.001 | `Create AccessKey` | R-NCP-004 |

**단서 단위 timeline (NCP raw — 학습용 합성, 2026-04-22 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 04:02:11 | thompson-ext | `Login` | SUCCESS | 198.51.100.7 | Initial Access (T1078.004) — 비국내 IP |
| 2 | 04:02:48 | thompson-ext | `Login` | SUCCESS | 198.51.100.7 | Initial Access — 재로그인 (IMDS 토큰 갱신 등가) |
| 3 | 04:04:33 | thompson-ext | `Decrypt root password` | SUCCESS | 198.51.100.7 | Credential Access (T1552) — STS 임시 자격 등가 |
| 4 | 04:06:09 | thompson-ext | `Create access key` | SUCCESS | 198.51.100.7 | Persistence (T1098.001) |
| 5 | 04:08:55 | thompson-ext | `Access Server Connect Console` | SUCCESS | 198.51.100.7 | Lateral Movement (T1021) |
| 6 | 04:11:02 | thompson-ext | `Login` | SUCCESS | 198.51.100.7 | Initial Access — 신규 키로 재진입 |
| 7 | 04:14:18 | thompson-ext | `Create sub account` | SUCCESS | 198.51.100.7 | Persistence (T1136.003) — 백도어 `thompson-bk` |
| 8 | 04:15:30 | thompson-ext | `Attach policy to sub account` | SUCCESS | 198.51.100.7 | Privilege Escalation (T1098) — `AdministratorAccess` 부여 |

**수사관 관점 재구성**
- **단서 1**: 비국내 IP → 트리아지 `Q2A:non_korean_ip` 매칭.
- **단서 3**: `Decrypt root password` 4분 내 발생 = 매우 드뭄 → CREDENTIAL_THEFT 가설 강한 양성.
- **단서 4·7·8**: AccessKey + Sub Account + 정책 부착 13분 내 burst → 자동화 도구 시그니처.

**lessons_learned**: AWS IMDS·STS 메커니즘은 NCP 직접 등가 없음 → *비국내 IP + Decrypt root + AccessKey burst* 3종 결합으로 검출. V-1 v2 1.5.7 priority 7 룰이 단서 1 자동 추출.

---

### 2.2 NHN — Uber 2016 (GitHub 키 노출 → 클라우드 침투)

**AWS 원본 개요**
- **시기**: 2016-10 ~ 2016-11 (공개 2017-11)
- **vector**: Uber 엔지니어의 private GitHub repo에 평문 AWS access key commit → GitHub 스캐닝 → AWS S3 접근 → 5700만 명 정보 다운로드
- **핵심 AWS API**: `GetCallerIdentity`, `ListBuckets`/`GetObject`, `iam:CreateAccessKey`

**역매핑 — AWS 동작 → NHN `eventId`**

| AWS 동작 | MITRE | NHN 등가 eventId | rule_id |
|---|---|---|---|
| GitHub 노출 키 사용 | T1078.004 | `event_id.iam.login` | R-NHN-001 |
| 영속화 키 | T1098.001 | `event_id.iaas.s3credential.create` | R-NHN-005 |
| 대량 다운로드 | T1530 | `event_id.object_storage.object.upload`(R-NHN-011 룰셋 활용) | R-NHN-011 |

**단서 단위 timeline (NHN raw — 학습용 합성, 2026-04-23 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 23:47:02 | dev-leaked | `event_id.iam.login` | SUCCESS | 104.28.10.55 | Initial Access — 비국내 IP + 비표준 시각 |
| 2 | 23:47:18 | dev-leaked | `event_id.iam.org.selected` | SUCCESS | 104.28.10.55 | Discovery |
| 3 | 23:47:42 | dev-leaked | `event_id.iam.project.selected` | SUCCESS | 104.28.10.55 | Discovery |
| 4 | 23:50:11 | dev-leaked | `event_id.iaas.s3credential.create` | SUCCESS | 104.28.10.55 | Persistence (T1098.001) |
| 5 | 23:52:33 | dev-leaked | `event_id.object_storage.container.list` | SUCCESS | 104.28.10.55 | Discovery |
| 6 | 23:55:08 | dev-leaked | `event_id.object_storage.object.upload` | SUCCESS | 104.28.10.55 | Exfiltration (T1567) |
| 7 | 00:14:50 | dev-leaked | `event_id.iaas.s3credential.delete` | SUCCESS | 104.28.10.55 | Impact (T1531) — 흔적 제거 |

**수사관 관점 재구성**
- **단서 1**: 비국내 IP + off_hours 동시 매칭.
- **단서 4** (3분 후 s3credential.create): 정상 사용자 베이스라인 초과 → CREDENTIAL_THEFT 가설.
- **단서 7**: 자기 자신 키 삭제 = 흔적 제거 의도 명확.

**lessons_learned**: GitHub 키 노출 vector 자체는 raw 로그로 직접 검출 불가 — 외부 위협 인텔리전스(시크릿 스캐너) 보조 필수. AWS `CreateAccessKey` ↔ NHN `s3credential.create` 의미 동등.

---

## 3. PRIVILEGE_ESCALATION

### 3.1 NCP — CloudGoat `iam_privesc_by_attachment`

**AWS 원본 개요**
- **시기**: 2018 이후 표준 PrivEsc 교보재 (Rhino Security Labs)
- **vector**: 낮은 권한 IAM 사용자가 `iam:AttachUserPolicy` 권한 → 자기 자신에게 `AdministratorAccess` 부착

**역매핑**

| AWS 동작 | MITRE | NCP 등가 | rule_id |
|---|---|---|---|
| `iam:AttachUserPolicy` self | T1098 | `Attach policy to sub account` | R-NCP-010 |
| `iam:CreateUser` 백도어 | T1136.003 | `Create sub account` | R-NCP-009 |

**단서 단위 timeline (NCP raw — 학습용 합성, 2026-04-15 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 14:02:11 | dev-user | `Login` | SUCCESS | 180.182.45.12 | Initial Access — 정상 사내 IP |
| 2 | 14:03:48 | dev-user | `Get Sub Account Policy List` | SUCCESS | 180.182.45.12 | Discovery — 자기 권한 정찰 |
| 3 | 14:05:33 | dev-user | `Create AccessKey` | SUCCESS | 180.182.45.12 | Persistence (T1098.001) |
| 4 | 14:06:09 | dev-user | `Attach policy to sub account` | SUCCESS | 180.182.45.12 | PrivEsc (T1098) — `NCP_AccessKey_Manage` self |
| 5 | 14:08:21 | dev-user | `Attach policy to sub account` | SUCCESS | 180.182.45.12 | PrivEsc — `NCP_ServerAdmin` self |
| 6 | 14:10:02 | dev-user | `Attach policy to sub account` | SUCCESS | 180.182.45.12 | PrivEsc — `AdministratorAccess` self |
| 7 | 14:12:30 | dev-user | `Create sub account` | SUCCESS | 180.182.45.12 | Persistence (T1136.003) — 백도어 `admin-tmp` |
| 8 | 14:13:48 | dev-user | `Attach policy to sub account` | SUCCESS | 180.182.45.12 | PrivEsc — `AdministratorAccess` to `admin-tmp` |
| 9 | 14:14:55 | dev-user | `Access Server Connect Console` | SUCCESS | 180.182.45.12 | Lateral Movement (T1021) |

**수사관 관점 재구성**
- **단서 4·5·6** (4분 내 Attach policy × 3): 단계적 권한 부착 = 자동화 도구 시그니처. CloudGoat·Pacu 류 표준 출력.
- **단서 7~8**: 자기 권한 상승만으로 부족 → 별도 영속화 계정 확보.

**lessons_learned**: AWS `iam:AttachUserPolicy` ↔ NCP `Attach policy to sub account` 동등. *Attach policy* 2분 내 3건 이상 burst는 정상 운영에서 극히 드물어 슬라이딩 윈도우 룰 1건으로 검출 가능.

---

### 3.2 NHN — LastPass 2022 (자동화 키 권한 확장)

**AWS 원본 개요**
- **시기**: 2022-08 (1차) → 2022-11 (권한 확장)
- **vector**: DevOps 엔지니어 노트북 침해 → 자동화 키 탈취 → 권한 확장(백업 S3 → 고객 데이터 S3)

**역매핑**

| AWS 동작 | MITRE | NHN 등가 | rule_id |
|---|---|---|---|
| `iam:UpdateAssumeRolePolicy` | T1098 | `event_id.project.member.update` | R-NHN-003 |
| 백도어 멤버 | T1136.003 | `event_id.org.iam.member.add` | R-NHN-004 |
| 영속화 | T1098.001 | `event_id.iaas.s3credential.create` | R-NHN-005 |

**단서 단위 timeline (NHN raw — 학습용 합성, 2026-04-15 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 22:30:08 | ops-bot | `event_id.iam.login` | SUCCESS | 211.234.108.55 | Initial Access — 자동화 키 |
| 2 | 22:31:12 | ops-bot | `event_id.iam.project.selected` | SUCCESS | 211.234.108.55 | Discovery |
| 3 | 22:32:45 | ops-bot | `event_id.iam.member.list` | SUCCESS | 211.234.108.55 | Discovery — 멤버 정찰 |
| 4 | 22:34:02 | ops-bot | `event_id.project.member.update` | SUCCESS | 211.234.108.55 | PrivEsc (T1098, R-NHN-003) — self → Admin |
| 5 | 22:35:11 | ops-bot | `event_id.project.product.enable` | FAIL | 211.234.108.55 | PrivEsc 시도 실패 (R-NHN-002) |
| 6 | 22:36:30 | ops-bot | `event_id.org.iam.member.add` | SUCCESS | 211.234.108.55 | Persistence — 백도어 `backup-user` (R-NHN-004) |
| 7 | 22:37:48 | ops-bot | `event_id.project.member.update` | SUCCESS | 211.234.108.55 | PrivEsc — `backup-user` → Admin (R-NHN-003) |
| 8 | 22:38:55 | ops-bot | `event_id.iaas.s3credential.create` | SUCCESS | 211.234.108.55 | Persistence (T1098.001) |

**수사관 관점 재구성**
- **단서 4**: self → Admin = actor와 target 동일인 권한 변경, 정상 운영에서 매우 드뭄.
- **단서 5 FAIL**: 의도 자체가 침해 단서.
- **단서 6~7**: 백도어 멤버 + Admin 부착 → 영속화.

**lessons_learned**: NHN IAM 권한 변경 시 admin 승인 워크플로 부재 — 자기 자신 role.update 1건만으로도 강한 양성. AWS `UpdateAssumeRolePolicy` 직접 등가 없음 → `project.member.update` + `org.iam.member.add` 조합으로 표현.

---

## 4. DATA_EXFILTRATION

### 4.1 NCP — Imperva 2019 (RDS 스냅샷 외부 export)

**AWS 원본 개요**
- **시기**: 2018-09 침해 → 2019-08 공개
- **vector**: AWS 마이그레이션 중 임시 자격증명 탈취 → RDS 스냅샷을 외부 계정으로 share/export

**역매핑**

| AWS 동작 | MITRE | NCP 등가 | rule_id |
|---|---|---|---|
| `rds:ModifyDBSnapshotAttribute` 외부 공유 | T1567 | `Request For Exporting To Object Storage` | R-NCP-007 |
| S3 PutObject external | T1567.002 | `Complete For Exporting To Object Storage` | R-NCP-007 |

**단서 단위 timeline (NCP raw — 학습용 합성, 2026-04-20 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 03:15:02 | data-eng | `Login` | SUCCESS | 115.91.214.5 | Initial Access — 외부 IP |
| 2 | 03:16:18 | data-eng | `Login` | SUCCESS | 115.91.214.5 | Initial Access — 재로그인 |
| 3 | 03:18:55 | data-eng | `Create AccessKey` | SUCCESS | 115.91.214.5 | Persistence (T1098.001) |
| 4 | 03:20:11 | data-eng | `Request For Exporting To Object Storage` | SUCCESS | 115.91.214.5 | Exfiltration (T1537) — DB 스냅샷 export |
| 5 | 03:35:42 | data-eng | `Complete For Exporting To Object Storage` | SUCCESS | 115.91.214.5 | Exfiltration |
| 6 | 03:36:11 | data-eng | `Request For Exporting To Object Storage` | SUCCESS | 115.91.214.5 | Exfiltration — 추가 스냅샷 |
| 7 | 03:39:50 | data-eng | `Complete For Exporting To Object Storage` | SUCCESS | 115.91.214.5 | Exfiltration |
| 8 | 03:42:33 | data-eng | `Disable AccessKey` | SUCCESS | 115.91.214.5 | Impact (T1531) — 흔적 제거 |

**수사관 관점 재구성**
- **단서 4·6** Export Request × 2: R-NCP-007 매칭 → T1537 강한 양성.
- **단서 5·7** Complete: Request/Complete 시간차로 데이터 크기 단서.
- **단서 8** 사후 키 비활성: 흔적 제거 명확.

**lessons_learned**: NCP `Cloud DB 백업 외부 공유` 별도 룰 없음 → R-NCP-013 신설 후보. AWS `rds:ModifyDBSnapshotAttribute` 직접 등가 없음 → Object Storage Export 로 치환.

---

### 4.2 NHN — Capital One 2019 (S3 대량 다운로드)

**AWS 원본 개요**: §2.1과 동일 사례, 데이터 유출 단계에 집중. 700+ 버킷에서 5.8GB 다운로드.

**역매핑**

| AWS 동작 | MITRE | NHN 등가 | rule_id |
|---|---|---|---|
| `s3:PutBucketPolicy` public-read | T1098.005 | `event_id.object_storage.container.metadata.update` (X-Container-Read='.r:*') | — |
| `s3:GetObject` × 다수 | T1530 | `event_id.object_storage.object.download` | (룰 없음 — R-NHN-011은 upload만) |

**단서 단위 timeline (NHN raw — 학습용 합성, 2026-04-20 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 11:08:02 | analytics | `event_id.iam.login` | SUCCESS | 210.179.55.88 | Initial Access — 외부 IP |
| 2 | 11:09:11 | analytics | `event_id.object_storage.container.list` | SUCCESS | 210.179.55.88 | Discovery |
| 3 | 11:11:48 | analytics | `event_id.object_storage.container.metadata.update` | SUCCESS | 210.179.55.88 | Defense Evasion (T1562) — X-Container-Read='.r:*' |
| 4 | 11:15:30 | analytics | `event_id.object_storage.object.download` | SUCCESS | 210.179.55.88 | Exfiltration (T1530) — 1.2GB |
| 5 | 11:18:55 | analytics | `event_id.object_storage.object.download` | SUCCESS | 210.179.55.88 | Exfiltration — 2.1GB |
| 6 | 11:22:18 | analytics | `event_id.object_storage.object.download` | SUCCESS | 210.179.55.88 | Exfiltration — 1.8GB |
| 7 | 11:25:42 | analytics | `event_id.object_storage.object.download` | SUCCESS | 210.179.55.88 | Exfiltration — 0.9GB |
| 8 | 11:32:11 | analytics | `event_id.iaas.s3credential.create` | SUCCESS | 210.179.55.88 | Persistence (T1098.001) — Pre-signed 등가 |
| 9 | 11:34:55 | analytics | `event_id.object_storage.object.download` | SUCCESS | 210.179.55.88 | Exfiltration — 2.9GB (총 8.9GB) |
| 10 | 11:35:30 | analytics | `event_id.object_storage.container.metadata.update` | SUCCESS | 210.179.55.88 | Defense Evasion — reset (위장) |

**수사관 관점 재구성**
- **단서 3 → 10**: 공개 변경 → 다운로드 → 비공개 reset = 흔적 위장 표준 시퀀스.
- **단서 4~7, 9**: 5건 download / 8.9GB / 27분.

**lessons_learned**: R-NHN-011은 upload만 — download burst 별도 룰 (R-NHN-012) 신설 후보. metadata.update 변경 *값 diff* 가 핵심 단서 — raw 의 request/response JSON 필드 보존 필수.

---

## 5. AUDIT_LOG_TAMPERING

### 5.1 NCP — Code Spaces 2014 (CloudTrail + 백업 일괄 삭제)

**AWS 원본 개요**
- **시기**: 2014-06 (12시간 만에 회사 폐업)
- **vector**: 콘솔 자격증명 탈취 → 협박 거부 → 모든 EC2/S3/RDS/EBS 백업 일괄 삭제 + CloudTrail 비활성화

**역매핑**

| AWS 동작 | MITRE | NCP 등가 | rule_id |
|---|---|---|---|
| `cloudtrail:StopLogging` | T1562.008 | `Disable Auto Export` | (룰 없음) |
| `cloudtrail:DeleteTrail` | T1562.001 | `Delete Tracer` | (룰 없음) |
| `ec2:TerminateInstances` × N | T1489 | `Shutdown Server Instance` × N | R-NCP-003 |

**단서 단위 timeline (NCP raw — 학습용 합성, 2026-04-10 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 03:30:02 | attack-sim | `Login` | SUCCESS | 115.91.214.5 | Initial Access |
| 2 | 03:32:11 | attack-sim | `Create AccessKey` | SUCCESS | 115.91.214.5 | Persistence (T1098.001) |
| 3 | 03:33:48 | attack-sim | `Disable Auto Export` | SUCCESS | 115.91.214.5 | Defense Evasion (T1562.008) |
| 4 | 03:34:30 | attack-sim | `Delete Tracer` | SUCCESS | 115.91.214.5 | Defense Evasion (T1562.001) — 감사 로그 삭제 |
| 5 | 03:35:50 | attack-sim | `Shutdown Server Instance` | SUCCESS | (audit OFF — 외부 export 사본만 존재) | Impact (T1489) |
| 6 | 03:36:33 | attack-sim | `Shutdown Server Instance` | SUCCESS | (audit OFF) | Impact (T1489) |
| 7 | 03:37:11 | attack-sim | `Delete Bucket` | SUCCESS | (audit OFF) | Impact (T1485) — 백업 데이터 파괴 |
| 8 | 03:38:55 | attack-sim | `Disable AccessKey` | SUCCESS | (audit OFF) | Impact (T1531) — 흔적 제거 |

**수사관 관점 재구성**
- **단서 3·4** Disable Auto Export → Delete Tracer 1분 내: 가장 강한 침해 단서. 이후 로그는 외부 export 사본 유일.
- **단서 4 이후 time gap > 10분**: 기록 단절 자체가 단서.

**lessons_learned**: AWS `DeleteTrail` ↔ NCP `Delete Tracer` 동등. NCP는 별도 룰화 안 됨 → R-NCP-012 신설 후보. 외부 Object Storage 자동 export + WORM 잠금이 사실상 유일 방어.

---

### 5.2 NHN — Tesla Cryptojacking 2018 (감사 alert 비활성 시도)

**AWS 원본 개요**
- **시기**: 2018-02 (RedLock 발견)
- **vector**: 노출된 Kubernetes 콘솔 → 컨테이너 내부 AWS 자격증명 → EC2에서 Monero 채굴 + alert 회피

**역매핑**

| AWS 동작 | MITRE | NHN 등가 | rule_id |
|---|---|---|---|
| `guardduty:UpdateDetector` 임계값 | T1562 | (NHN GuardDuty 등가 없음) | — |
| CloudTrail 변조 시도 | T1562.001 | `s3credential.delete` burst | R-NHN-006 |

**단서 단위 timeline (NHN raw — 학습용 합성, 2026-04-25 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 05:00:02 | attack | `event_id.iam.login` | SUCCESS | 115.91.214.5 | Initial Access |
| 2 | 05:02:11 | attack | `event_id.iaas.s3credential.create` | SUCCESS | 115.91.214.5 | Persistence — 임시 키 |
| 3 | 05:05:30 | attack | `event_id.iaas.instance.create` | SUCCESS | 115.91.214.5 | Initial Access + T1496 — 채굴용 인스턴스 |
| 4 | 05:10:18 | attack | `event_id.object_storage.container.metadata.update` | SUCCESS | 115.91.214.5 | Defense Evasion — CloudTrail-bucket 정책 변경 |
| 5 | 05:15:42 | attack | `event_id.project.product.enable` | FAIL | 115.91.214.5 | PrivEsc 시도 실패 — 외부 export 차단 시도 |
| 6 | 05:20:11 | attack | `event_id.iaas.s3credential.delete` | SUCCESS | 115.91.214.5 | Impact (T1531) — 키 1 |
| 7 | 05:22:33 | attack | `event_id.iaas.s3credential.delete` | SUCCESS | 115.91.214.5 | Impact — 키 2 |
| 8 | 05:24:06 | attack | `event_id.iaas.s3credential.delete` | SUCCESS | 115.91.214.5 | Impact — 키 3 (자기 자신) |

**수사관 관점 재구성**
- **단서 5 FAIL**: 외부 export 차단 시도 실패 → 의도 명시. NHN CloudTrail 외부 변조 어려움이 방어 자산.
- **단서 6~8 burst**: s3credential.delete 3건/4분 = AUDIT_LOG_TAMPERING 시그니처.

**lessons_learned**: NHN CloudTrail 자체 비활성 불가, 인증 봉쇄로 우회. R-NHN-013 (s3credential.delete burst) 신설 후보.

---

## 6. RANSOMWARE (dev3 신규)

### 6.1 NCP — Colonial Pipeline 2021 (DarkSide 그룹)

**AWS 원본 개요**
- **시기**: 2021-05-07 ~ 2021-05-12 (5일간 동부 미국 송유관 마비)
- **행위자**: DarkSide (러시아 후원 추정 랜섬웨어 그룹)
- **vector**: VPN 자격증명 탈취(MFA 미적용) → 회계망 침투 → 이중 협박(Double Extortion: 데이터 유출 후 암호화) → 회사가 4.4M USD 비트코인 지불
- **핵심 동작**:
  - 정상 자격증명으로 VPN/내부 시스템 진입
  - 데이터 외부 유출 후 일괄 암호화
  - 백업 무력화 시도 (T1490 Inhibit System Recovery)
- **MITRE**: T1078, T1567 (Exfiltration), T1486 (Data Encrypted for Impact), T1490 (Inhibit Recovery)

**역매핑 — AWS 동작 → NCP `action`**

| AWS 동작 | MITRE | NCP 등가 action | rule_id |
|---|---|---|---|
| 탈취 자격증명 로그인 | T1078.004 | `Login` | R-NCP-001 |
| 영속화 키 발급 | T1098.001 | `Create AccessKey` | R-NCP-004 |
| 데이터 외부 export (이중협박) | T1567 | `Request/Complete For Exporting To Object Storage` | R-NCP-007 |
| 운영 인스턴스 일괄 종료 | T1489 | `Shutdown Server Instance` × N | R-NCP-003 |
| 백업 버킷 삭제 (T1490) | T1490 | `Delete Bucket` × N (NCP 별도 룰 없음 — raw 기록) | — |
| AccessKey 사후 비활성 | T1531 | `Disable AccessKey` | R-NCP-008 |

**단서 단위 timeline (NCP raw — 학습용 합성, 2026-05-07 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 02:10:08 | ops-leaked | `Login` | SUCCESS | 185.193.88.42 | Initial Access (T1078.004) — VPN 자격증명 등가 |
| 2 | 02:11:45 | ops-leaked | `Create AccessKey` | SUCCESS | 185.193.88.42 | Persistence (T1098.001) |
| 3 | 02:14:22 | ops-leaked | `Access Server Connect Console` | SUCCESS | 10.0.20.55 | Lateral Movement (T1021) |
| 4 | 02:30:11 | ops-leaked | `Request For Exporting To Object Storage` | SUCCESS | 185.193.88.42 | Exfiltration (T1567) — 운영 데이터 외부 사본 (Double Extortion) |
| 5 | 03:45:50 | ops-leaked | `Complete For Exporting To Object Storage` | SUCCESS | 185.193.88.42 | Exfiltration — 75분 export 완료 |
| 6 | 03:48:33 | ops-leaked | `Shutdown Server Instance` | SUCCESS | 185.193.88.42 | Impact (T1489) — 운영 서버 1 |
| 7 | 03:49:11 | ops-leaked | `Shutdown Server Instance` | SUCCESS | 185.193.88.42 | Impact — 운영 서버 2 |
| 8 | 03:49:55 | ops-leaked | `Shutdown Server Instance` | SUCCESS | 185.193.88.42 | Impact — 운영 서버 3 |
| 9 | 03:52:18 | ops-leaked | `Delete Bucket` | SUCCESS | 185.193.88.42 | Impact (T1490) — 백업 버킷 1 (raw 기록 — NCP 룰 없음) |
| 10 | 03:53:02 | ops-leaked | `Delete Bucket` | SUCCESS | 185.193.88.42 | Impact (T1490) — 백업 버킷 2 |
| 11 | 03:55:30 | ops-leaked | `Disable AccessKey` | SUCCESS | 185.193.88.42 | Impact (T1531) — 흔적 제거 |

**수사관 관점 재구성**
- **단서 4·5** (75분 export): 이중협박의 *유출 단계*. R-NCP-007 매칭 → DATA_EXFILTRATION과 동일 시그니처지만, 후속 단서 6~10이 *암호화/파괴*로 이어지면 RANSOMWARE 가설로 수렴.
- **단서 6~8** Shutdown × 3건 2분 내: T1489 burst. *운영 시스템 일괄 중단* = RANSOMWARE의 *암호화 직전* 단서.
- **단서 9~10** Delete Bucket × 2: T1490 Inhibit System Recovery. NCP에는 별도 룰 없음 → raw 기록만 → §11 R-NCP-014 신설 후보.
- **수사 결론**: 단서 4~10의 *Exfil → Shutdown burst → Delete Bucket burst* 시퀀스는 RANSOMWARE 표준 패턴 (DarkSide/LockBit/BlackCat 공통). V-4 갭 감지에서 *암호화 자체*(T1486) 단서가 raw에 없으면 `EVIDENCE` 갭 — Object Storage 객체별 무결성 검증(SHA-256) 추가 수집 권고. PLAYBOOK-RANSOM-001 *Object Lock(WORM) 활성화 + 즉시 외부 사본 격리* 권고.

**lessons_learned**: Colonial Pipeline의 *이중협박* 패턴은 본 시스템에서 DATA_EXFILTRATION + RANSOMWARE 사고유형이 *동일 사건의 두 측면*임을 입증. RANSOMWARE 가설 양성 시 *반드시 Exfil 흔적 동시 조사*. NCP `Delete Bucket` 별도 룰화 + T1486 암호화 검출(Object 무결성 SHA-256 변화) 룰 신설 권고.

---

### 6.2 NHN — MGM Resorts 2023 (ALPHV/Scattered Spider)

**AWS 원본 개요**
- **시기**: 2023-09 (10일간 호텔·카지노 시스템 마비)
- **행위자**: ALPHV(BlackCat) + Scattered Spider (사회공학 전문 그룹)
- **vector**: LinkedIn으로 직원 신원 확인 → Help Desk에 비싱(전화 피싱)으로 MFA reset 요청 → 자격증명 우회 → Okta 침투 → 클라우드/온프레 광범위 침해 → vCenter 일괄 암호화
- **핵심 동작**:
  - 사회공학(IT 헬프데스크)으로 IAM 진입
  - 광범위 권한 확장
  - 가상화 인프라(vCenter) 일괄 암호화
  - 100M USD 손실 추정
- **MITRE**: T1566 (Phishing — voice), T1078.004, T1486, T1490

**역매핑 — AWS 동작 → NHN `eventId`**

| AWS 동작 | MITRE | NHN 등가 eventId | rule_id |
|---|---|---|---|
| 비싱 후 MFA reset → IAM 진입 | T1078.004 | `event_id.iam.login` | R-NHN-001 |
| 영속화 키 | T1098.001 | `event_id.iaas.s3credential.create` | R-NHN-005 |
| 광범위 권한 확장 | T1098 | `event_id.project.member.update`, `event_id.org.iam.member.add` | R-NHN-003, R-NHN-004 |
| 인스턴스 일괄 중단 (vCenter 등가) | T1489 | `event_id.iaas.instance_action.stop` × N | R-NHN-008 |
| VPC/인프라 파괴 (T1490) | T1485 | `event_id.iaas.vpc.delete_end` | R-NHN-009 |
| 자격증명 흔적 제거 | T1531 | `event_id.iaas.s3credential.delete` | R-NHN-006 |

**단서 단위 timeline (NHN raw — 학습용 합성, 2026-05-08 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 14:22:11 | helpdesk-reset | `event_id.iam.identity.password_change` | SUCCESS | 175.45.176.3 | Persistence (T1098.001, R-NHN-007) — MFA reset 등가 |
| 2 | 14:24:50 | helpdesk-reset | `event_id.iam.login` | SUCCESS | 175.45.176.3 | Initial Access — 비싱 후 진입 |
| 3 | 14:26:18 | helpdesk-reset | `event_id.iam.org.selected` | SUCCESS | 175.45.176.3 | Discovery |
| 4 | 14:28:42 | helpdesk-reset | `event_id.org.iam.member.add` | SUCCESS | 175.45.176.3 | Persistence — 백도어 `mgm-backup` |
| 5 | 14:30:11 | helpdesk-reset | `event_id.project.member.update` | SUCCESS | 175.45.176.3 | PrivEsc — `mgm-backup` → Admin |
| 6 | 14:35:30 | helpdesk-reset | `event_id.iaas.s3credential.create` | SUCCESS | 175.45.176.3 | Persistence (T1098.001) |
| 7 | 14:48:55 | helpdesk-reset | `event_id.object_storage.object.upload` | SUCCESS | 175.45.176.3 | Exfiltration (T1567) — 데이터 외부 사본 |
| 8 | 15:02:18 | helpdesk-reset | `event_id.iaas.instance_action.stop` | SUCCESS | 175.45.176.3 | Impact (T1489) — 인스턴스 1 |
| 9 | 15:02:48 | helpdesk-reset | `event_id.iaas.instance_action.stop` | SUCCESS | 175.45.176.3 | Impact — 인스턴스 2 |
| 10 | 15:03:22 | helpdesk-reset | `event_id.iaas.instance_action.shelve` | SUCCESS | 175.45.176.3 | Impact — 인스턴스 3 |
| 11 | 15:05:50 | helpdesk-reset | `event_id.iaas.vpc.delete_end` | SUCCESS | 175.45.176.3 | Impact (T1485) — VPC 삭제 (T1490 Inhibit Recovery 등가) |
| 12 | 15:08:11 | helpdesk-reset | `event_id.iaas.s3credential.delete` | SUCCESS | 175.45.176.3 | Impact (T1531) — 흔적 제거 |

**수사관 관점 재구성**
- **단서 1** (`identity.password_change`): MFA reset 등가 — Help Desk 비싱의 결과. **사회공학 vector**는 raw 로그에는 직접 안 나타남, *MFA reset이 인사 정상 절차 아닌 비표준 시각에 발생*이 핵심.
- **단서 4·5** (백도어 멤버 + Admin): MGM의 *광범위 권한 확장* 패턴 재현.
- **단서 7** Exfil → 단서 8~10 instance.stop burst → 단서 11 vpc.delete = Colonial Pipeline과 동일 *유출 → 중단 → 파괴* 시퀀스.
- **수사 결론**: 단서 1의 *password_change → login 2분 차*가 가장 강한 단서. PHISH_INITIAL_ACCESS와 RANSOMWARE의 *연계 시그니처*임을 보여줌 — V-8 Sherpa에서 두 사고유형 점수가 동시 상승.

**lessons_learned**: MGM 사례의 *사회공학(Help Desk 비싱)* vector는 클라우드 raw로 직접 검출 불가 → MFA reset 자동 알림(외부 채널) + Help Desk SOP에 *MFA reset 시 본인 영상 확인* 강제 필수. NHN `instance_action.stop` burst 별도 룰(R-NHN-014 후보) 권고.

---

## 7. MISCONFIG_EXPOSURE (dev3 신규)

### 7.1 NCP — Capital One 2019 (WAF SSRF 측면 — 설정 오류 관점)

**AWS 원본 개요** (§2.1과 동일 사례, MISCONFIG 측면 강조)
- **vector (MISCONFIG 관점)**:
  1. WAF가 외부에서 `169.254.169.254` 경로로 SSRF 가능 — *WAF 설정 오류*
  2. EC2 인스턴스 프로필이 *과도한 IAM 권한* (`s3:*`) 보유 — *IAM 최소권한 미적용*
  3. S3 버킷 액세스 로깅 비활성 — *모니터링 설정 오류*
- **MITRE**: T1190 (Exploit Public-Facing Application), T1078.001 (Default Accounts), T1530, T1580 (Cloud Discovery)

**역매핑 — AWS 동작 → NCP `action`**

| AWS 동작 | MITRE | NCP 등가 action | rule_id |
|---|---|---|---|
| WAF SSRF 익스플로잇 | T1190 | (클라우드 raw 외부 단서 — NCP 직접 매핑 없음) | — |
| 과도 권한 IAM 활용 | T1078.001 | `Login` + 과도 권한 동작 (raw 기록) | R-NCP-001 + raw |
| Cloud Discovery (정찰) | T1580 | `Get Sub Account Policy List`, `List Buckets` (NCP 별도 룰 없음) | — |
| S3 데이터 접근 | T1530 | `Access Server Connect Console` → Object Storage 접근 | R-NCP-002 |
| 영속화 | T1098.001 | `Create AccessKey` | R-NCP-004 |

**단서 단위 timeline (NCP raw — 학습용 합성, 2026-05-09 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 06:33:11 | misconfig-victim | `Login` | SUCCESS | 185.220.101.4 | Initial Access — Tor exit 등 비국내 IP |
| 2 | 06:35:08 | misconfig-victim | `Get Sub Account Policy List` | SUCCESS | 185.220.101.4 | Discovery (T1580) — 자기 권한 정찰 |
| 3 | 06:36:42 | misconfig-victim | `List Buckets` | SUCCESS | 185.220.101.4 | Discovery (T1580) — Object Storage 정찰 (raw 기록) |
| 4 | 06:39:55 | misconfig-victim | `Create AccessKey` | SUCCESS | 185.220.101.4 | Persistence (T1098.001) — 영속 키 |
| 5 | 06:42:11 | misconfig-victim | `Access Server Connect Console` | SUCCESS | 10.10.5.30 | Lateral Movement (T1021) — 과도 권한 활용 |
| 6 | 06:48:33 | misconfig-victim | `Request For Exporting To Object Storage` | SUCCESS | 185.220.101.4 | Exfiltration (T1567) → 결국 DATA_EXFIL로 전이 |
| 7 | 07:15:50 | misconfig-victim | `Complete For Exporting To Object Storage` | SUCCESS | 185.220.101.4 | Exfiltration |

**수사관 관점 재구성**
- **단서 2·3** (Get Policy List + List Buckets): *Discovery 단서가 본 raw에 별도 룰화 안 됨* — 정상 사용자의 베이스라인과 구분이 어렵다. **MISCONFIG_EXPOSURE 가설은 raw 로그 단독으로는 약함** — 외부 정황(WAF 설정 변경 이력, IAM 정책 감사 결과 등)이 결정적.
- **단서 4의 권한 범위**: AccessKey 발급 자체는 정상 동작이지만, *발급 직후 사용된 권한이 발급자 본래 직무 범위 초과*면 MISCONFIG 단서. **수사관은 V-1 v2 1.5.2 priority 9 룰의 *IAM 정책 정기 감사*에서 본 사용자의 정책 범위를 별도 확인**.
- **단서 5** (VPC 내부 IP): 외부 IP가 VPC 진입 → 과도 권한 활용 결과.
- **수사 결론**: MISCONFIG_EXPOSURE는 raw 단독 가설보다는 *DATA_EXFILTRATION + 설정 감사*의 조합. V-8 Sherpa에서 사후 분석 시 *IAM 권한 범위 vs 실제 사용 권한 diff* 자동 비교 룰 권고.

**lessons_learned**: Capital One 사례의 *3중 설정 오류*(WAF SSRF + IAM 과도 권한 + 액세스 로깅 비활성)는 클라우드 raw 로그로는 *결과 단계(데이터 접근)만 검출*. **MISCONFIG는 *예방* 영역 — 본 시스템의 V-1 v2 1.5.1·1.5.2 priority 10 룰의 *정기 감사 자동화*가 핵심**. R-NCP-015 *과도 권한 사용 룰* (정책 범위 vs 실제 사용 diff) 신설 후보.

---

### 7.2 NHN — Verkada 2021 (Slack 노출 super admin → 카메라 영상 노출)

**AWS 원본 개요**
- **시기**: 2021-03 (스위스 해커 그룹 발견 및 공개)
- **vector**: Verkada(보안 카메라 SaaS)의 super admin 계정 자격증명이 *Slack 메시지에 평문 공유* → 외부 스캔으로 발견 → 15만 대 카메라 영상 접근 (특수병원·여성 보호소·테슬라 공장 포함)
- **vector (MISCONFIG 관점)**:
  1. super admin 계정 자격증명을 평문 채팅에 공유 — *비밀 관리 설정 오류*
  2. 모든 카메라가 *전체 admin 단일 계정*으로 관리됨 — *권한 분리 미흡*
  3. 외부 인증 차단 ACL 없음 — *네트워크 설정 오류*
- **MITRE**: T1078.001 (Default/Shared Accounts), T1530, T1580

**역매핑 — AWS 동작 → NHN `eventId`**

| AWS 동작 | MITRE | NHN 등가 eventId | rule_id |
|---|---|---|---|
| 공유 자격증명으로 진입 | T1078.001 | `event_id.iam.login` | R-NHN-001 |
| 정찰 | T1580 | `event_id.iam.org.selected`, `iam.project.selected`, `iam.member.list` | — |
| 광범위 데이터 접근 | T1530 | `event_id.object_storage.container.metadata.update` + `object.download` | (R-NHN-011 부분) |

**단서 단위 timeline (NHN raw — 학습용 합성, 2026-05-10 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 11:08:11 | super-admin | `event_id.iam.login` | SUCCESS | 91.198.174.55 | Initial Access (T1078.001) — 공유 계정 |
| 2 | 11:08:45 | super-admin | `event_id.iam.org.selected` | SUCCESS | 91.198.174.55 | Discovery |
| 3 | 11:09:30 | super-admin | `event_id.iam.member.list` | SUCCESS | 91.198.174.55 | Discovery (T1580) — 전체 멤버 정찰 |
| 4 | 11:11:18 | super-admin | `event_id.object_storage.container.list` | SUCCESS | 91.198.174.55 | Discovery — 컨테이너 정찰 |
| 5 | 11:13:42 | super-admin | `event_id.object_storage.container.metadata.update` | SUCCESS | 91.198.174.55 | Defense Evasion — X-Container-Read='.r:*' (광범위 공개) |
| 6 | 11:16:11 | super-admin | `event_id.object_storage.object.download` | SUCCESS | 91.198.174.55 | Exfiltration (T1530) — 영상 파일 1.5GB |
| 7 | 11:22:55 | super-admin | `event_id.object_storage.object.download` | SUCCESS | 91.198.174.55 | Exfiltration — 영상 파일 2.8GB |
| 8 | 11:35:30 | super-admin | `event_id.object_storage.object.download` | SUCCESS | 91.198.174.55 | Exfiltration — 영상 파일 4.1GB |
| 9 | 11:52:18 | super-admin | `event_id.object_storage.container.metadata.update` | SUCCESS | 91.198.174.55 | Defense Evasion — reset (위장) |

**수사관 관점 재구성**
- **단서 1**: `super-admin` 같은 *공유 계정명* 자체가 MISCONFIG 단서. KISA §3.3 *권한 분리 미흡* 직접 대응.
- **단서 5 → 9** (공개 변경 → 다운로드 → 비공개 reset): §4.2와 동일 시퀀스 — *Capital One/Imperva류*. **하지만 MISCONFIG_EXPOSURE 가설의 차별점은 *공유 계정으로 발생*이라는 점**.
- **단서 1~4의 *비국내 IP + 공유 계정명 + 광범위 정찰* 조합**: 정상 운영자의 베이스라인과 구분 — 정상 super-admin은 *특정 프로젝트만* 접근, 비국내 IP에서 전 멤버·전 컨테이너 정찰은 드뭄.
- **수사 결론**: MISCONFIG_EXPOSURE 가설 양성. PLAYBOOK-MISCFG-001 *공유 super admin 즉시 분리 + IAM 정기 감사 활성화* 권고. V-8 Sherpa에서 *공유 계정 사용 빈도* 룰 권고.

**lessons_learned**: Verkada 사례의 *Slack 평문 공유*는 클라우드 raw 외부 vector — *공유 계정명 + 비국내 IP + 광범위 정찰* 3종이 결합되면 MISCONFIG 가설 양성. NHN의 *공유 계정 식별*(actor.actor_user_name 패턴 분석) 룰 신설 권고 (R-NHN-015 후보).

---

## 8. PHISH_INITIAL_ACCESS (dev3 신규)

### 8.1 NCP — Twilio 0ktapus 2022 (SMS 피싱 → Okta 토큰)

**AWS 원본 개요**
- **시기**: 2022-08 (Twilio 공개 2022-08-07)
- **행위자**: 0ktapus (Scattered Spider 전신)
- **vector**: Twilio 직원에게 *SMS 피싱*(`twilio-okta.com` 류 도메인) → 가짜 SSO 로그인 페이지에서 자격증명 + MFA OTP 입력 → 공격자 실시간으로 *진짜 Okta에 입력* → Twilio 콘솔 진입 → 1900+ 다운스트림 고객 영향
- **MITRE**: T1566.001 (Spearphishing Link), T1078.004, T1556 (Modify Authentication Process)

**역매핑 — AWS 동작 → NCP `action`**

| AWS 동작 | MITRE | NCP 등가 action | rule_id |
|---|---|---|---|
| 가짜 SSO에 자격증명 입력 → 진짜 Okta로 relay | T1566.001 | (피싱 자체는 클라우드 raw 외 단서) | — |
| Relay된 자격증명으로 콘솔 진입 | T1078.004 | `Login` (외부 IP) | R-NCP-001 |
| MFA reset 시도 | T1556 | `Change password` | R-NCP-005 |
| 영속화 | T1098.001 | `Create AccessKey` | R-NCP-004 |

**단서 단위 timeline (NCP raw — 학습용 합성, 2026-05-11 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 08:15:02 | phished-emp | `Login` | FAIL | 165.232.92.7 | Initial Access — 외부 IP 첫 시도 (자격증명만, MFA 미통과) |
| 2 | 08:15:18 | phished-emp | `Login` | SUCCESS | 165.232.92.7 | Initial Access — relay 된 MFA OTP로 성공 |
| 3 | 08:16:42 | phished-emp | `Change password` | SUCCESS | 165.232.92.7 | Persistence (T1098.001, R-NCP-005) — MFA bypass 후 영속 |
| 4 | 08:18:11 | phished-emp | `Create AccessKey` | SUCCESS | 165.232.92.7 | Persistence (T1098.001) |
| 5 | 08:20:30 | phished-emp | `Get Sub Account Policy List` | SUCCESS | 165.232.92.7 | Discovery |
| 6 | 08:23:55 | phished-emp | `Attach policy to sub account` | SUCCESS | 165.232.92.7 | PrivEsc (T1098) — 권한 확장 |
| 7 | 08:28:18 | phished-emp | `Access Server Connect Console` | SUCCESS | 10.5.40.22 | Lateral Movement (T1021) |

**수사관 관점 재구성**
- **단서 1 → 2 (16초 차)**: FAIL → SUCCESS *16초 차*는 **MFA OTP 입력 지연 시간**과 정확히 일치. 정상 사용자의 본인 MFA 입력은 보통 5~10초, *16초 + 비국내 IP*는 *실시간 relay 피싱*의 시그니처.
- **단서 3** (1분 후 password 변경): MFA bypass 후 즉시 비밀번호 변경 = 영속화 의도.
- **단서 4·6** (AccessKey + PrivEsc): 정상 직원의 권한 범위 초과.
- **수사 결론**: PHISH 자체는 raw로 직접 검출 불가하지만, *FAIL→SUCCESS 16초 차 + 비국내 IP + 직후 비밀번호 변경* 3종 결합이 강한 시그니처. V-8 Sherpa에서 *Login 시도 시간 패턴 분석* 룰 권고. PLAYBOOK-PHISH-001 *해당 직원 즉시 자격 회수 + 전사 비밀번호 강제 변경 + 이메일·SMS 피싱 캠페인 조사*.

**lessons_learned**: Twilio 0ktapus의 *MFA relay 피싱*은 클라우드 raw로 검출 어려우나, *FAIL/SUCCESS 시간 간격 + 외부 IP*로 *간접 추론* 가능. PHISH_INITIAL_ACCESS 사고유형은 *클라우드 raw + 외부 위협 인텔리전스(피싱 도메인 목록)*의 결합이 필수. R-NCP-016 *FAIL→SUCCESS 시간차 룰* 신설 후보.

---

### 8.2 NHN — Twitter 2020 (직원 비싱 → 내부 도구 접근)

**AWS 원본 개요**
- **시기**: 2020-07-15 (130개 유명 계정 비트코인 사기 트윗)
- **행위자**: Graham Ivan Clark 등 (17세 청소년 + 공범)
- **vector**: Twitter 직원에게 *전화 비싱(Vishing)* — IT부서 사칭 → 내부 VPN 로그인 페이지 자격증명 입력 유도 → 진짜 내부 도구에서 *Account Takeover* 기능 실행 → 130개 계정 변조 (Obama, Musk, Bezos, Apple 등)
- **MITRE**: T1566.004 (Phishing — voice), T1078.004, T1098 (Account Manipulation)

**역매핑 — AWS 동작 → NHN `eventId`**

| AWS 동작 | MITRE | NHN 등가 eventId | rule_id |
|---|---|---|---|
| 비싱으로 자격증명 획득 → 진입 | T1078.004 | `event_id.iam.login` | R-NHN-001 |
| 권한 확장 | T1098 | `event_id.project.member.update` | R-NHN-003 |
| 운영 데이터 변조 | T1098 | `event_id.iaas.identity.password_change` (계정 비밀번호 변경 등가) | R-NHN-007 |

**단서 단위 timeline (NHN raw — 학습용 합성, 2026-05-12 가정)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 13:32:08 | vished-emp | `event_id.iam.login` | FAIL | 121.78.196.4 | Initial Access — 자격증명 첫 시도 |
| 2 | 13:32:25 | vished-emp | `event_id.iam.login` | SUCCESS | 121.78.196.4 | Initial Access — 17초 차 성공 (relay 가능성) |
| 3 | 13:33:42 | vished-emp | `event_id.iaas.identity.password_change` | SUCCESS | 121.78.196.4 | Persistence (T1098.001, R-NHN-007) |
| 4 | 13:35:11 | vished-emp | `event_id.iam.project.selected` | SUCCESS | 121.78.196.4 | Discovery |
| 5 | 13:36:30 | vished-emp | `event_id.iam.member.list` | SUCCESS | 121.78.196.4 | Discovery — 전 멤버 정찰 |
| 6 | 13:39:55 | vished-emp | `event_id.project.member.update` | SUCCESS | 121.78.196.4 | PrivEsc (T1098, R-NHN-003) — self → Admin |
| 7 | 13:42:18 | vished-emp | `event_id.iaas.s3credential.create` | SUCCESS | 121.78.196.4 | Persistence (T1098.001) |
| 8 | 13:48:42 | vished-emp | `event_id.iaas.identity.password_change` | SUCCESS | 121.78.196.4 | Persistence — 다른 멤버 비밀번호 변경 (계정 탈취 등가) |

**수사관 관점 재구성**
- **단서 1 → 2** (17초 차 FAIL→SUCCESS): Twilio와 동일 시그니처 — MFA OTP relay 패턴.
- **단서 3** (1분 후 password_change): 영속화 우선순위.
- **단서 6** (self → Admin): NHN PrivEsc 표준 단서. 직원의 본래 직무 범위 초과.
- **단서 8** (다른 멤버 password_change): Twitter 사례의 *Account Takeover* 등가 — 자기 자신 외의 멤버 비밀번호를 변경. **이건 정상 운영에서 *admin 승인 워크플로 필수* — actor와 target이 다르고 actor가 admin이 아니라면 강한 양성**.
- **수사 결론**: 단서 1·2·6·8 4건이 16분 내 → PHISH_INITIAL_ACCESS 가설 + INSIDER_THREAT(다른 계정 변조) 동시 양성. V-8 Sherpa에서 두 사고유형 점수 동시 상승. PLAYBOOK-PHISH-002 권고.

**lessons_learned**: Twitter 2020의 *내부 도구 광범위 접근 + 타인 계정 변조*는 본 시스템의 PHISH_INITIAL_ACCESS + PRIVILEGE_ESCALATION + INSIDER_THREAT *3종 복합*. NHN `identity.password_change`의 *target ≠ actor* 케이스 별도 룰 (R-NHN-017) 신설 권고.

---

## 9. INSIDER_THREAT (dev3 신규)

### 9.1 NCP — Tesla 2018 (불만 직원 Martin Tripp의 데이터 유출 + 코드 변조)

**AWS 원본 개요**
- **시기**: 2018-06 (Tesla 공개 2018-06-17)
- **행위자**: Martin Tripp (전 Tesla 직원, 제조 분석 엔지니어)
- **vector**: 직원의 *정당한* 시스템 접근 권한으로 *코드를 변조* (제조 운영시스템에 의도된 버그 삽입) + *수 GB 내부 데이터를 외부로 유출* (제3자 언론에 제보). MITRE T1078(정당 자격증명) + T1565(Data Manipulation) + T1530.
- **vector (INSIDER 관점)**:
  1. 정상 자격증명으로 본인 직무 범위 내 작업 → raw 로그에 *정상 운영과 구분 어려움*
  2. **결정적 단서**: 데이터 export 시간이 *비표준 시각(야간·주말)*, 작업 범위가 *본인 직무 범위 초과*
- **MITRE**: T1078, T1098, T1530, T1562.008

**역매핑 — AWS 동작 → NCP `action`**

| AWS 동작 | MITRE | NCP 등가 action | rule_id |
|---|---|---|---|
| 정당 자격증명 로그인 | T1078 | `Login` (사내 IP) | R-NCP-001 |
| 운영 데이터 export | T1530 + T1567 | `Request/Complete For Exporting To Object Storage` | R-NCP-007 |
| 흔적 제거 (감사 로그 우회) | T1562.008 | `Disable Auto Export` (라이브 매핑 없음 — raw) | — |
| 영속화 | T1098 | `Create AccessKey` | R-NCP-004 |

**단서 단위 timeline (NCP raw — 학습용 합성, 2026-05-13 가정 — 토요일 야간)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 02:18:11 | mfg-eng-tripp | `Login` | SUCCESS | 10.5.20.110 | Initial Access (T1078) — **사내 IP + 비표준 시각** |
| 2 | 02:19:55 | mfg-eng-tripp | `Get Sub Account Policy List` | SUCCESS | 10.5.20.110 | Discovery — 자기 권한 확인 |
| 3 | 02:22:30 | mfg-eng-tripp | `Access Server Connect Console` | SUCCESS | 10.5.20.110 | Lateral Movement (T1021) — 본인 직무 서버 |
| 4 | 02:28:18 | mfg-eng-tripp | `Access Server Connect Console` | SUCCESS | 10.5.20.110 | Lateral Movement — **본인 직무 범위 초과 서버** (제조 라인 분석) |
| 5 | 02:35:42 | mfg-eng-tripp | `Create AccessKey` | SUCCESS | 10.5.20.110 | Persistence (T1098.001) — 야간 신규 발급 (드뭄) |
| 6 | 02:48:11 | mfg-eng-tripp | `Request For Exporting To Object Storage` | SUCCESS | 10.5.20.110 | Exfiltration (T1567) — 8.7GB 데이터 |
| 7 | 03:18:30 | mfg-eng-tripp | `Complete For Exporting To Object Storage` | SUCCESS | 10.5.20.110 | Exfiltration |
| 8 | 03:22:55 | mfg-eng-tripp | `Disable Auto Export` | SUCCESS | 10.5.20.110 | Defense Evasion (T1562.008) — 감사 export 차단 (라이브 룰 없음) |
| 9 | 03:25:18 | mfg-eng-tripp | `Disable AccessKey` | SUCCESS | 10.5.20.110 | Impact (T1531) — 야간 발급 키 자기 비활성 (흔적 제거) |

**수사관 관점 재구성**
- **단서 1** (사내 IP + 02:18 토요일): **외부 IP가 아닌 사내 IP**라는 점이 INSIDER_THREAT의 결정적 차별점. **비표준 시각**(주말 새벽) 단독으로는 약하지만 후속 단서와 결합 시 강한 양성.
- **단서 3 → 4** (본인 서버 → 본인 직무 외 서버): **권한 범위 vs 사용 범위 diff**가 INSIDER 핵심. *Manufacturing Engineer*가 제조 라인 분석 서버에 접근은 정상이지만 *다른 제품 라인이나 재무 시스템 접근*은 비정상. **V-8 Sherpa의 *직무 vs 사용 범위 diff* 룰이 필수**.
- **단서 5** (야간 AccessKey 발급): 정상 직원이 야간 신규 키 발급은 매우 드뭄.
- **단서 6·7** (8.7GB 야간 export): Tesla 사례의 *수 GB 데이터*에 정확히 대응.
- **단서 8** (Disable Auto Export): Tracer 감사 export 차단 시도 — AUDIT_LOG_TAMPERING과의 *조합 시그니처*.
- **단서 9** (자기 키 비활성): 야간 발급 → 야간 비활성 = 흔적 위장.
- **수사 결론**: 단서 1·4·5·8·9의 *사내 IP + 비표준 시각 + 직무 외 접근 + 흔적 위장* 5종 결합은 **INSIDER_THREAT 가설 강한 양성**. V-8 Sherpa의 *HR 데이터 연동*(퇴사 예정자 목록 등) 보조 단서 권고. PLAYBOOK-INSIDER-001 *해당 직원 즉시 권한 동결 + 법무팀 동시 통보*.

**lessons_learned**: Tesla Tripp 사례는 본 시스템의 *INSIDER_THREAT* 사고유형이 *외부 침입자 시그니처(외부 IP·자동화 burst)와 정반대 패턴*임을 입증. **INSIDER 검출은 *사내 IP + 시간대 이상 + 직무 외 접근* 조합 — 별도 룰셋 필요**. R-NCP-018 *비표준 시각 사내 IP 동작* + R-NCP-019 *직무 범위 vs 사용 범위 diff* 신설 후보.

---

### 9.2 NHN — Coinbase 2023 (외부 협력사 직원의 지원자 데이터 접근)

**AWS 원본 개요**
- **시기**: 2023-02 (Coinbase 공개 2023-02-19)
- **행위자**: 외부 채용 컨설팅사 직원 (정당 협력사 자격증명 보유, 별도 채용 프로세스에서 비싱 통과로 자격증명 탈취 의심)
- **vector**: 직원이 *합법적 채용 시스템 접근 권한*으로 *지원자 개인정보 일부 외부 유출* — Coinbase 사후 분석에서 *Authority Limit 초과 행동*으로 분류. T1078 + T1098 + T1530.
- **vector (INSIDER 관점)**:
  1. 외부 협력사 직원의 *정당한* 자격증명 — raw 로그에 *외부 IP에서 정상 접근으로 보임*
  2. **결정적 단서**: 평소 접근 빈도(주 5회 → 야간 다중 접근), 다운로드 패턴(단일 지원자 → 전체 목록)
- **MITRE**: T1078, T1098, T1530

**역매핑 — AWS 동작 → NHN `eventId`**

| AWS 동작 | MITRE | NHN 등가 eventId | rule_id |
|---|---|---|---|
| 협력사 자격증명 진입 | T1078 | `event_id.iam.login` | R-NHN-001 |
| 권한 자기 상승 시도 (실패) | T1098 | `event_id.project.member.update` (FAIL) | R-NHN-003 |
| 데이터 다운로드 | T1530 | `event_id.object_storage.object.download` | (R-NHN-011 부분) |
| 영속화 | T1098.001 | `event_id.iaas.s3credential.create` | R-NHN-005 |

**단서 단위 timeline (NHN raw — 학습용 합성, 2026-05-14 가정 — 일요일 야간)**

| # | time | actor | action | result | ip | tactic |
|---|---|---|---|---|---|---|
| 1 | 22:48:11 | contractor-hr | `event_id.iam.login` | SUCCESS | 222.108.46.18 | Initial Access (T1078) — **외부 IP + 일요일 야간** |
| 2 | 22:49:33 | contractor-hr | `event_id.iam.project.selected` | SUCCESS | 222.108.46.18 | Discovery |
| 3 | 22:50:18 | contractor-hr | `event_id.iam.member.list` | SUCCESS | 222.108.46.18 | Discovery — 멤버 정찰 |
| 4 | 22:52:42 | contractor-hr | `event_id.project.member.update` | FAIL | 222.108.46.18 | PrivEsc 시도 실패 (R-NHN-003) — 권한 자기상승 차단 |
| 5 | 22:54:11 | contractor-hr | `event_id.iaas.s3credential.create` | SUCCESS | 222.108.46.18 | Persistence (T1098.001) — **본인 직무 범위 외 자원용 키** |
| 6 | 22:58:30 | contractor-hr | `event_id.object_storage.container.list` | SUCCESS | 222.108.46.18 | Discovery |
| 7 | 23:02:55 | contractor-hr | `event_id.object_storage.object.download` | SUCCESS | 222.108.46.18 | Exfiltration (T1530) — 지원자 1 |
| 8 | 23:08:18 | contractor-hr | `event_id.object_storage.object.download` | SUCCESS | 222.108.46.18 | Exfiltration — 지원자 2 |
| 9 | 23:14:42 | contractor-hr | `event_id.object_storage.object.download` | SUCCESS | 222.108.46.18 | Exfiltration — 지원자 3 (이후 N건) |
| 10 | 23:48:30 | contractor-hr | `event_id.iaas.s3credential.delete` | SUCCESS | 222.108.46.18 | Impact (T1531) — 흔적 제거 |

**수사관 관점 재구성**
- **단서 1** (외부 IP + 일요일 22:48): 협력사 직원의 *정상 업무는 평일 09~18시* — **비표준 시각이 가장 강한 단서**. KISA §2.4 ⑥ + 트리아지 `Q2A:off_hours` 매칭.
- **단서 4 FAIL** (`project.member.update`): 권한 자기상승 시도가 *차단됨* — **차단됐다는 사실 자체가 *직무 범위 초과 의도* 명시**. 정상 직원은 권한 자기상승 시도 자체를 안 함.
- **단서 5** (자기 직무 외 자원용 키): AccessKey 발급 자체는 정상이지만 *발급 직후 사용 자원이 본인 직무 범위 외*면 강한 단서.
- **단서 7~9** (지원자 다운로드 burst): Coinbase 사례의 *지원자 정보 일괄 다운로드*에 정확히 대응. *정상 운영자라면 한 번에 1명*씩 처리 — *3명 이상 단시간 burst*는 매우 드뭄.
- **단서 10** (자기 키 삭제): 25분 만에 자기 발급 키 삭제 = 흔적 위장.
- **수사 결론**: 단서 1·4·5·7~9·10의 *외부 IP + 비표준 시각 + 권한 상승 시도 + 직무 외 자원 + 다운로드 burst + 흔적 제거* 6종 결합은 **INSIDER_THREAT 가설 강한 양성** (외부 협력사 케이스). V-8 Sherpa의 *협력사 자격증명 식별*(actor 메타데이터의 `userIdNo` 영역별 분류) 룰 권고. PLAYBOOK-INSIDER-002 *협력사 권한 분리·정기 감사·NDA 재검토* 권고.

**lessons_learned**: Coinbase 사례는 *외부 협력사* 케이스로 Tesla(§9.1)와 다름 — *외부 IP*이지만 *정당 자격증명 보유*. **INSIDER_THREAT는 *외부/내부 IP가 아닌 *직무 범위 vs 사용 범위*가 핵심 판단 기준***. 본 시스템 V-1 v2 1.5.2 priority 9 (IAM 정책) + 1.4 priority 10 (데이터 유출) 조합 매칭. R-NHN-019 *download burst (3건/5분)* + *권한 상승 시도 FAIL 1건 룰* 신설 후보.

---

## 10. case_db.json 청크 인덱스

본 문서의 16편은 [`backend/data/kb/case_db.json`](../../backend/data/kb/case_db.json) 에 다음 청크로 신규 추가됨:

| # | chunk_id | 사고유형 | CSP | 원본 사례 |
|---|---|---|---|---|
| 1 | `CASE-REMAP-NCP-CRED-001` | CREDENTIAL_THEFT | naver | Capital One 2019 (SSRF) |
| 2 | `CASE-REMAP-NHN-CRED-001` | CREDENTIAL_THEFT | nhn | Uber 2016 (GitHub) |
| 3 | `CASE-REMAP-NCP-PRIVESC-001` | PRIVILEGE_ESCALATION | naver | CloudGoat iam_privesc |
| 4 | `CASE-REMAP-NHN-PRIVESC-001` | PRIVILEGE_ESCALATION | nhn | LastPass 2022 |
| 5 | `CASE-REMAP-NCP-EXFIL-001` | DATA_EXFILTRATION | naver | Imperva 2019 |
| 6 | `CASE-REMAP-NHN-EXFIL-001` | DATA_EXFILTRATION | nhn | Capital One 2019 (S3) |
| 7 | `CASE-REMAP-NCP-AUDIT-001` | AUDIT_LOG_TAMPERING | naver | Code Spaces 2014 |
| 8 | `CASE-REMAP-NHN-AUDIT-001` | AUDIT_LOG_TAMPERING | nhn | Tesla Cryptojacking 2018 |
| 9 | `CASE-REMAP-NCP-RANSOM-001` | RANSOMWARE | naver | Colonial Pipeline 2021 |
| 10 | `CASE-REMAP-NHN-RANSOM-001` | RANSOMWARE | nhn | MGM Resorts 2023 |
| 11 | `CASE-REMAP-NCP-MISCFG-001` | MISCONFIG_EXPOSURE | naver | Capital One 2019 (WAF) |
| 12 | `CASE-REMAP-NHN-MISCFG-001` | MISCONFIG_EXPOSURE | nhn | Verkada 2021 |
| 13 | `CASE-REMAP-NCP-PHISH-001` | PHISH_INITIAL_ACCESS | naver | Twilio 0ktapus 2022 |
| 14 | `CASE-REMAP-NHN-PHISH-001` | PHISH_INITIAL_ACCESS | nhn | Twitter 2020 (Vishing) |
| 15 | `CASE-REMAP-NCP-INSIDER-001` | INSIDER_THREAT | naver | Tesla 2018 (Tripp) |
| 16 | `CASE-REMAP-NHN-INSIDER-001` | INSIDER_THREAT | nhn | Coinbase 2023 |

---

## 11. 미해결 매핑 한계 (룰 보강 후보)

본 역매핑 작업 중 발견된 NCP/NHN 매핑 룰의 한계 (특히 신규 4종):

### 11.1 기존 4종에서 발견 (jingyu 작업과 동일)

| # | AWS 동작 | 현 매핑 한계 | 보강 후보 |
|---|---|---|---|
| 1 | `cloudtrail:DeleteTrail` / `StopLogging` | NCP `Delete Tracer` raw만 — 별도 룰 없음 | **R-NCP-012** T1562.001/.008 |
| 2 | `rds:ModifyDBSnapshotAttribute` 외부 공유 | NCP 별도 매핑 없음 | **R-NCP-013** Cloud DB 백업 외부 공유 룰 |
| 3 | `s3:GetObject` 대량 다운로드 | NHN R-NHN-011은 upload만 | **R-NHN-012** object.download burst |
| 4 | `s3credential.delete` burst | NHN 별도 룰 없음 | **R-NHN-013** s3credential.delete burst |

### 11.2 신규 4종에서 발견 (dev3 C-1 추가 발굴)

| # | dev3 신규 사고유형 | AWS 동작 | 현 매핑 한계 | 보강 후보 |
|---|---|---|---|---|
| 5 | RANSOMWARE | `s3:DeleteBucket` × N (T1490) | NCP `Delete Bucket` 라이브 룰 없음 | **R-NCP-014** Object Storage 버킷 삭제 burst (T1490) |
| 6 | RANSOMWARE | `ec2:TerminateInstances` × N | NCP R-NCP-003은 Start/Shutdown 만 | (Shutdown burst 윈도우 룰) R-NCP-003 패턴 확장 |
| 7 | RANSOMWARE | `instance.stop` burst (NHN) | R-NHN-008 매칭은 되나 burst 별도 룰 없음 | **R-NHN-014** instance.stop burst (T1489+T1490) |
| 8 | MISCONFIG_EXPOSURE | `s3:ListBuckets`/`iam:Get*` 정찰 | T1580 매핑 룰 없음 | **R-NCP-015** 과도 권한 사용 (정책 범위 vs 사용 diff) |
| 9 | MISCONFIG_EXPOSURE | 공유 admin 계정 사용 | NHN 별도 식별 없음 | **R-NHN-015** 공유 계정 식별 (actor 패턴 분석) |
| 10 | PHISH_INITIAL_ACCESS | MFA OTP relay (FAIL→SUCCESS 빠른 차) | NCP/NHN 별도 룰 없음 | **R-NCP-016 / R-NHN-016** FAIL→SUCCESS 시간차 룰 (10~30초) |
| 11 | PHISH_INITIAL_ACCESS | 타인 계정 password_change | NHN R-NHN-007 매칭하나 *target ≠ actor* 구분 없음 | **R-NHN-017** identity.password_change target≠actor 룰 |
| 12 | INSIDER_THREAT | 정당 자격증명·사내 IP·비표준 시각 | NCP 사내 IP는 룰 없음 | **R-NCP-018** 비표준 시각 사내 IP 동작 룰 |
| 13 | INSIDER_THREAT | 직무 범위 vs 사용 범위 diff | NCP·NHN 둘 다 없음 | **R-NCP-019 / R-NHN-019** 직무 범위 diff 룰 (V-8 Sherpa 룰셋) |

→ **총 13개 신설 후보 룰** (NCP 9 + NHN 8, 일부 동명). dev3 C-1 단계에서 우선순위 매기는 백로그로 별도 관리 권장 (`.claude/구현/구현_체크리스트.md`).

### 11.3 raw 외부 단서 카테고리 (룰 신설 외 추가 입력 채널)

신규 4종은 *클라우드 raw 단독으로는 약함*. 다음 외부 단서 채널이 보조 필요:

| 사고유형 | 필수 외부 단서 |
|---|---|
| RANSOMWARE | Object 무결성 SHA-256 변화, KMS 키 사용 패턴 |
| MISCONFIG_EXPOSURE | IAM 정책 정기 감사 결과, WAF 설정 변경 이력 |
| PHISH_INITIAL_ACCESS | 외부 위협 인텔리전스(피싱 도메인 목록), 이메일 게이트웨이 로그 |
| INSIDER_THREAT | HR 시스템(퇴사 예정자), 직무 기술서 vs 실제 사용 권한 diff |

---

## 12. 변경 이력

| 날짜 | 작성자 | 내용 |
|---|---|---|
| 2026-05-20 | dev3 (jingyu) | 초안 (5종 × 2 = 10편) — jingyu 워크트리. |
| 2026-05-21 | dev3 (jingyu, dev3 워크트리) | dev3 C-1 8종 체계로 재작성 — MULTI_CSP_LATERAL 제외, 신규 4종(RANSOMWARE/MISCONFIG_EXPOSURE/PHISH_INITIAL_ACCESS/INSIDER_THREAT) 8편 추가. 총 16편. case_db.json 청크 16건 동시 추가. §11 신설 후보 룰 13건 식별. |
