# collection_targets_v2 — 신규 수집 카탈로그 (dev2)

> 외부 표준 6종 기반 카테고리 매트릭스 시드. `collection_targets/` (v1)과 병행 존재.
> 청사진: [`docs/신규_수집가이드_설계.md`](../../../docs/신규_수집가이드_설계.md)
> 인수인계: [`docs/외부_표준_분석맥락.md`](../../../docs/외부_표준_분석맥락.md)

---

## 0. 구조

```
collection_targets_v2/
├── README.md                          # 이 파일
├── incident_type_phases.json          # 사고유형 → MITRE Kill Chain 단계 매핑
├── environment_modifiers.json         # system_config 입력 → 가이드 보정 규칙
└── categories/
    ├── 1.5.1.json   # 클라우드 인증 - 인증 기록
    ├── 1.5.2.json   # 클라우드 인증 - 권한·구성 변경
    ├── 1.5.3.json   # 클라우드 인증 - 계정 생성
    ├── 1.5.4.json   # 클라우드 인증 - 실패 인증
    ├── 1.5.5.json   # 클라우드 인증 - 서비스 API 액세스
    ├── 1.5.7.json   # 클라우드 인증 - 위험 기반 검색
    ├── 1.7.json     # 클라우드 로깅 - 메타 (감사 로그 변조)
    ├── 1.4.json     # 파일 스토리지 - 데이터 접근/유출
    └── 1.8.json     # 네트워킹 - 인프라 조작
```

총 9개 카테고리. Google Cloud Threat Intel "Cloud Log Configurations" 분류에서
NCP/NHN IaaS 환경에 직접 적용 가능한 카테고리만 채택 (Email, Code Repository,
DB는 NCP/NHN MVP 범위 밖이라 제외).

## 1. 카테고리 ID 체계

`{대분류}.{중분류}[.세부]` — Google Cloud Threat Intel 분류번호 그대로 사용.

- **1.x** 클라우드 서비스 단일 보안 영역
- **2.x** 클라우드 협업 도구 (이메일·파일 공유) — 본 MVP 미사용
- 세부 숫자 (`1.5.1`, `1.5.2` 등)는 동일 대분류 내 항목 식별자

## 2. 시드 항목 스키마

각 카테고리 JSON은 다음 필드를 포함:

| 필드 | 타입 | 의미 |
|---|---|---|
| `category_id` | string | 예: "1.5.1" |
| `category_name` | string | 한국어 명칭 |
| `kb_source` | object | 외부 표준 출처 (primary URL + secondary 인용) |
| `applicable_incident_types` | string[] | 5종 enum 중 적용 가능한 사고유형 (다대다) |
| `kill_chain_phases` | string[] | MITRE 전술 명칭 |
| `evidence_role` | "REQUIRED" \| "CORROBORATING" | NIST SP 800-86 evidence type |
| `volatility_priority` | int (1~10) | NIST 휘발성 계층 기반 |
| `volatility_basis` | string | priority 부여 근거 (표준 인용) |
| `rationale` | string | 한국어 활용 설명 |
| `use_cases` | string[] | 구체 활용 시나리오 |
| `csp_mapping` | object | NCP / NHN 각 CSP의 실제 raw 패턴 |
| `retention_days_default` | int | CSP 기본 보존 기간 |
| `applicable_environments` | object | system_config 조건 (보정 트리거) |

## 3. 사고유형 ↔ 카테고리 다대다 매핑

각 카테고리의 `applicable_incident_types` 합집합으로 도출:

| 사고유형 | 적용 카테고리 |
|---|---|
| CREDENTIAL_THEFT | 1.5.1 / 1.5.2 / 1.5.3 / 1.5.4 / 1.5.5 / 1.5.7 |
| PRIVILEGE_ESCALATION | 1.5.2 / 1.5.3 / 1.5.5 |
| DATA_EXFILTRATION | 1.4 / 1.5.5 / 1.8 |
| AUDIT_LOG_TAMPERING | 1.7 (전체) / 1.5.2 |
| MULTI_CSP_LATERAL | 1.5.1 / 1.5.5 / 1.8 / 양쪽 CSP |

## 4. 외부 표준 출처 매핑

| 우리 카테고리 | Google Cloud | KISA | MITRE | NIST |
|---|---|---|---|---|
| 1.5.1 | §1.5.1 인증 기록 | §2.4 점검표 ⑥ 네트워크 연결 | T1078.004 | §3.1 휘발성 P10 |
| 1.5.2 | §1.5.2 권한 변경 | §2.4 점검표 ④ 권한 변경 | T1098 | P9 |
| 1.5.3 | §1.5.3 계정 생성 | §3.1 표 3-3 | T1136.003 | P9 |
| 1.5.4 | §1.5.4 실패 인증 | §2.4 점검표 ⑥ 실패 시도 | T1110 | P9 |
| 1.5.5 | §1.5.5 API 액세스 | §2.6 시스템 활동 | (다수) | P7 |
| 1.5.7 | §1.5.7 위험 기반 검색 | — | — | P8 |
| 1.7 | §1.7.1~4 로깅 메타 | §3.1 로그 무결성 | T1070, T1562.008 | P10 (휘발) |
| 1.4 | §1.4 파일 스토리지 | 표 3-7 데이터 이동 | T1537, T1567 | P5 (보존) |
| 1.8 | §1.8 네트워킹 | 표 3-7 네트워크 변경 | T1021, T1485 | P6 |

## 5. CSP별 raw 매핑 정합성

NCP `Cloud Activity Tracer` 와 NHN `Cloud Trail` 의 실제 raw 로그(`activity_logs_full.json`,
`nhn_activity_logs.json`) 분석 결과 + 공식 가이드(`csp_doc.json`) 기반.

NCP는 통합 로그(action 필드)이므로 카테고리 분류가 `action` 키워드/패턴 기반.
NHN은 `event_id.[카테고리].[작업]` prefix로 자연 분류.

## 6. dev v1 시드와 호환성

기존 v1 시드(`collection_targets/{csp}_{type}.json` 5건/사고유형)는 그대로 유지.
v2는 별도 디렉토리에서 병행. 두 시스템 비교 후 채택 결정.

v1 ↔ v2 매핑 (참고):
- v1 CT-NCP-IAM-001 (Sub Account 인증) ↔ v2 1.5.1
- v1 CT-NCP-IAM-002 (자격증명·권한 변경) ↔ v2 1.5.2 + 1.5.3
- v1 CT-NCP-IAM-003 (Server Console) ↔ v2 1.5.5 (API 액세스 일부)
- v1 CT-NCP-IAM-004 (Object Storage) ↔ v2 1.4
- v1 CT-NCP-IAM-005 (리소스 변경) ↔ v2 1.8 + 일부 1.5.2

## 7. 작업 진행 순서 (Phase A)

- [x] 인덱스 README (이 파일)
- [ ] `categories/1.5.1.json` ~ `1.5.7.json` (인증 6개)
- [ ] `categories/1.7.json` (로깅 메타)
- [ ] `categories/1.4.json` (파일 스토리지)
- [ ] `categories/1.8.json` (네트워킹)
- [ ] `incident_type_phases.json` (Phase B)
- [ ] `environment_modifiers.json` (Phase B)
- [ ] `CollectionGuideV2` 백엔드 구현 (Phase C)
- [ ] API `GET /api/guide/v2` (Phase D)
- [ ] 프론트 V2 UI (Phase E)
