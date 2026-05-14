# API 계약서 (프론트엔드-백엔드 인터페이스)

> 프론트엔드와 백엔드 팀이 **병렬 개발**할 수 있도록 모든 API의 요청/응답 형식을 확정합니다.
> 백엔드 미완성 시 프론트엔드는 이 문서의 mock 데이터로 개발합니다.

---

## 공통 규칙

### Base URL
```
http://localhost:8000
```

### 응답 형식
```json
// 성공
{ "status": "ok", "data": { ... } }

// 에러
{ "status": "error", "message": "설명", "code": "ERROR_CODE" }

// 페이지네이션
{ "items": [...], "total": 100, "page": 1, "pageSize": 20 }
```

### 공통 에러 코드
| HTTP | code | 설명 |
|------|------|------|
| 400 | VALIDATION_ERROR | 입력값 검증 실패 |
| 404 | NOT_FOUND | 리소스 미존재 |
| 409 | CONFLICT | 중복 리소스 |
| 500 | INTERNAL_ERROR | 서버 내부 오류 |

---

## Layer 0: 사고 접수

### POST /api/cases — 케이스 생성

**Request Body:**
```json
{
  "incident_type": "CREDENTIAL_THEFT",
  "csp": "naver",
  "severity": "high",
  "occurred_at": "2025-03-15T09:30:00Z",
  "system_config": {
    "vpc_id": "vpc-abc123",
    "region": "kr-standard",
    "services": ["Cloud Activity Tracer", "Sub Account", "Object Storage"]
  }
}
```

**Response (201):**
```json
{
  "status": "ok",
  "data": {
    "caseId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "incident_type": "CREDENTIAL_THEFT",
    "csp": "naver",
    "severity": "high",
    "occurred_at": "2025-03-15T09:30:00Z",
    "system_config": { "vpc_id": "vpc-abc123", "region": "kr-standard", "services": ["Cloud Activity Tracer", "Sub Account", "Object Storage"] },
    "created_at": "2025-03-15T10:00:00Z",
    "closed_at": null
  }
}
```

**Validation:**
- `incident_type`: `CREDENTIAL_THEFT | PRIVILEGE_ESCALATION | DATA_EXFILTRATION | AUDIT_LOG_TAMPERING | MULTI_CSP_LATERAL` (필수)
- `csp`: `naver | nhn | all` (필수)
- `severity`: `critical | high | medium | low` (필수)
- `occurred_at`: ISO 8601 (필수)
- `system_config`: JSON 객체 (선택)

---

### GET /api/cases/{caseId} — 케이스 상세 조회

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "caseId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "incident_type": "CREDENTIAL_THEFT",
    "csp": "naver",
    "severity": "high",
    "occurred_at": "2025-03-15T09:30:00Z",
    "system_config": { "vpc_id": "vpc-abc123", "region": "kr-standard", "services": ["Cloud Activity Tracer", "Sub Account", "Object Storage"] },
    "created_at": "2025-03-15T10:00:00Z",
    "closed_at": null
  }
}
```

**에러:** `404 CASE_NOT_FOUND`

---

### PATCH /api/cases/{caseId} — 구성 수정

**Request Body (일부 필드만 전송 가능):**
```json
{
  "severity": "critical",
  "system_config": {
    "vpc_id": "vpc-abc123",
    "region": "kr-standard",
    "services": ["Cloud Activity Tracer", "Sub Account", "Object Storage", "NAS"]
  }
}
```

**Response (200):** 수정된 케이스 전체 객체 (GET과 동일 형식)

---

### GET /api/guide?caseId={caseId} — 수집 체크리스트

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "caseId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "completionRate": 0,
    "targets": [
      {
        "target_id": "CT-NCP-IAM-001",
        "log_type": "Cloud Activity Tracer - API 호출 로그",
        "evidence_role": "REQUIRED",
        "priority": 10,
        "description": "IAM 관련 API 호출 기록 (CreateSubAccount, ChangePassword 등)",
        "collected": false
      },
      {
        "target_id": "CT-NCP-IAM-002",
        "log_type": "Sub Account 접근 기록",
        "evidence_role": "REQUIRED",
        "priority": 9,
        "description": "서브 계정 로그인 이력 및 권한 변경",
        "collected": false
      },
      {
        "target_id": "CT-NCP-IAM-003",
        "log_type": "Console Login 로그",
        "evidence_role": "REQUIRED",
        "priority": 8,
        "description": "콘솔 로그인 성공/실패 기록",
        "collected": false
      },
      {
        "target_id": "CT-NCP-IAM-004",
        "log_type": "Resource Manager 변경 로그",
        "evidence_role": "CORROBORATING",
        "priority": 5,
        "description": "리소스 그룹 및 정책 변경 이력",
        "collected": false
      },
      {
        "target_id": "CT-NCP-IAM-005",
        "log_type": "Object Storage 접근 로그",
        "evidence_role": "CORROBORATING",
        "priority": 4,
        "description": "오브젝트 스토리지 읽기/쓰기 로그",
        "collected": false
      }
    ]
  }
}
```

---

## Layer 1: 로그 수집

### POST /api/logs/upload — 로그 파일 업로드

**Request:** `multipart/form-data`
| 필드 | 타입 | 설명 |
|------|------|------|
| file | File | JSON/CSV 로그 파일 |
| caseId | string | 케이스 ID |

**Response (201):**
```json
{
  "status": "ok",
  "data": {
    "uploadId": "up-001",
    "fileName": "cloud_activity_tracer_2025-03.json",
    "fileHash": "sha256:a3f2b8c1d4e5f6...",
    "eventCount": 147,
    "matchedTargets": ["CT-NCP-IAM-001", "CT-NCP-IAM-003"],
    "csp": "naver",
    "timeRange": {
      "earliest": "2025-03-10T00:00:00Z",
      "latest": "2025-03-15T23:59:59Z"
    }
  }
}
```

---

### GET /api/logs?caseId={caseId}&page=1&pageSize=20 — 이벤트 목록

**Response (200):**
```json
{
  "items": [
    {
      "event_id": "evt-001",
      "case_id": "f47ac10b-...",
      "csp": "naver",
      "event_time": "2025-03-15T02:30:00Z",
      "event_name": "ConsoleLogin",
      "source_file": "cloud_activity_tracer_2025-03.json",
      "matched_target_id": "CT-NCP-IAM-003",
      "sha256_hash": "a3f2b8c1d4e5f6...",
      "created_at": "2025-03-15T10:05:00Z"
    },
    {
      "event_id": "evt-002",
      "case_id": "f47ac10b-...",
      "csp": "naver",
      "event_time": "2025-03-15T02:31:00Z",
      "event_name": "CreateSubAccount",
      "source_file": "cloud_activity_tracer_2025-03.json",
      "matched_target_id": "CT-NCP-IAM-001",
      "sha256_hash": "b4c3d2e1f0...",
      "created_at": "2025-03-15T10:05:00Z"
    }
  ],
  "total": 147,
  "page": 1,
  "pageSize": 20
}
```

---

### GET /api/logs/{eventId} — 원본 이벤트 상세

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "event_id": "evt-001",
    "case_id": "f47ac10b-...",
    "csp": "naver",
    "event_time": "2025-03-15T02:30:00Z",
    "event_name": "ConsoleLogin",
    "source_file": "cloud_activity_tracer_2025-03.json",
    "matched_target_id": "CT-NCP-IAM-003",
    "sha256_hash": "a3f2b8c1d4e5f6...",
    "raw_json": {
      "eventVersion": "1.0",
      "eventTime": "2025-03-15T02:30:00Z",
      "eventName": "ConsoleLogin",
      "userIdentity": {
        "type": "IAMUser",
        "userName": "attacker-user",
        "accountId": "12345678"
      },
      "sourceIPAddress": "203.0.113.42",
      "userAgent": "Mozilla/5.0...",
      "requestParameters": null,
      "responseElements": {
        "ConsoleLogin": "Success"
      }
    }
  }
}
```

---

## Layer 2: 분석

### POST /api/analysis/normalize — OCSF 정규화

**Request Body:**
```json
{
  "caseId": "f47ac10b-...",
  "eventIds": ["evt-001", "evt-002"]
}
```
`eventIds` 생략 시 해당 케이스의 모든 raw_events를 정규화합니다.

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "total": 147,
    "normalized": 145,
    "failed": 2,
    "normalizationRate": 98.6,
    "failedEvents": [
      { "event_id": "evt-099", "reason": "Unknown event format" }
    ]
  }
}
```

---

### GET /api/analysis/ocsf?caseId={caseId} — OCSF 결과 조회

**Query Params (선택):**
- `page`, `pageSize`: 페이지네이션
- `eventId`: 특정 이벤트만 조회

**Response (200):**
```json
{
  "items": [
    {
      "ocsf_id": "ocsf-001",
      "event_id": "evt-001",
      "class_uid": 3002,
      "category_uid": 3,
      "activity_id": 1,
      "activity_name": "Logon",
      "time": 1710470400,
      "actor": {
        "user": {
          "name": "attacker-user",
          "type": "IAMUser",
          "account_uid": "12345678"
        }
      },
      "src_endpoint": {
        "ip": "203.0.113.42"
      },
      "status_code": "Success",
      "severity_id": 2,
      "unmapped": {
        "raw_request": null,
        "raw_response": { "ConsoleLogin": "Success" }
      }
    }
  ],
  "total": 145,
  "page": 1,
  "pageSize": 20
}
```

---

### POST /api/analysis/map — ATT&CK 매핑

**Request Body:**
```json
{
  "caseId": "f47ac10b-..."
}
```

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "total_ocsf": 145,
    "mapped": 12,
    "unmapped": 133,
    "mappingRate": 8.3,
    "events": [
      {
        "attack_id": "atk-001",
        "ocsf_id": "ocsf-001",
        "technique_id": "T1078.004",
        "technique_name": "Valid Accounts: Cloud Accounts",
        "tactic": "Initial Access",
        "rule_id": "R001",
        "risk_score": 8.5,
        "event_time": "2025-03-15T02:30:00Z",
        "activity_name": "Logon"
      },
      {
        "attack_id": "atk-002",
        "ocsf_id": "ocsf-005",
        "technique_id": "T1098",
        "technique_name": "Account Manipulation",
        "tactic": "Persistence",
        "rule_id": "R003",
        "risk_score": 9.0,
        "event_time": "2025-03-15T02:31:00Z",
        "activity_name": "CreateSubAccount"
      }
    ]
  }
}
```

---

### GET /api/analysis/attack?caseId={caseId} — ATT&CK 결과 조회

**Response (200):** 위 `events` 배열과 동일 형식 (페이지네이션 적용)
```json
{
  "items": [ /* attack_event 객체들 */ ],
  "total": 12,
  "page": 1,
  "pageSize": 20
}
```

---

### POST /api/analysis/gap — 갭 감지

**Request Body:**
```json
{
  "caseId": "f47ac10b-..."
}
```

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "gap_id": "gap-001",
    "case_id": "f47ac10b-...",
    "gap_type": "COLLECTION",
    "missing": [
      {
        "target_id": "CT-NCP-IAM-002",
        "log_type": "Sub Account 접근 기록",
        "evidence_role": "REQUIRED",
        "priority": 9
      }
    ],
    "summary": "필수 증거 5건 중 1건 미수집. Sub Account 접근 기록이 필요합니다.",
    "recommendation": "Layer 0으로 복귀하여 추가 로그를 수집하세요.",
    "completionRate": 80.0,
    "created_at": "2025-03-15T10:30:00Z"
  }
}
```

**gap_type별 의미:**
| gap_type | 설명 | 권장 행동 |
|----------|------|----------|
| NONE | 갭 없음 | Layer 4(수사 보드)로 진행 |
| COLLECTION | 필수 증거 미수집 | Layer 0으로 복귀 → 추가 수집 |
| EVIDENCE | 증거 있으나 매핑 실패 | 수사관 직접 판단 필요 |
| INTERPRETATION | 매핑 불가 이벤트 존재 | AI 셰르파 브리핑 권장 |

---

## Layer 3: AI 셰르파

### POST /api/sherpa/brief — 컨텍스트 브리핑

**Request Body:**
```json
{
  "caseId": "f47ac10b-...",
  "eventId": "atk-001"
}
```

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "technique_id": "T1078.004",
    "technique_name": "Valid Accounts: Cloud Accounts",
    "tactic": "Initial Access",
    "briefing": "이 이벤트는 해외 IP(203.0.113.42)에서 새벽 2시 30분에 콘솔 로그인한 기록입니다. T1078.004(클라우드 유효 계정 사용) 기법에 해당하며, 공격자가 탈취된 자격증명을 사용하여 최초 접근한 것으로 판단됩니다. 일반적으로 이 기법 이후 T1098(계정 조작) 또는 T1530(클라우드 스토리지 데이터 수집)으로 이어지는 패턴이 관찰됩니다.",
    "sources": [
      { "source_id": "ATT&CK-T1078.004", "type": "ATTACK", "title": "Valid Accounts: Cloud Accounts" },
      { "source_id": "CASE-2024-001", "type": "CASE_DB", "title": "국내 금융기관 IAM 탈취 사례" }
    ],
    "relatedTechniques": ["T1098", "T1530", "T1098.001"],
    "confidence": "high"
  }
}
```

---

### POST /api/sherpa/chat — 자연어 질의

**Request Body:**
```json
{
  "caseId": "f47ac10b-...",
  "sessionId": "sess-001",
  "query": "공격자가 어떤 경로로 권한을 상승시켰을 가능성이 있나요?",
  "history": [
    { "role": "user", "content": "이전 질문..." },
    { "role": "assistant", "content": "이전 응답..." }
  ]
}
```

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "sessionId": "sess-001",
    "response": "수집된 로그를 분석한 결과, 공격자는 다음 경로로 권한 상승을 시도한 것으로 보입니다:\n\n1. T1078.004 - 탈취된 IAM 계정으로 콘솔 로그인 (2025-03-15 02:30)\n2. T1098 - CreateSubAccount API로 새 서브 계정 생성 (2025-03-15 02:31)\n3. T1098.001 - 해당 서브 계정에 관리자 권한 부여 (2025-03-15 02:33)\n\n이러한 패턴은 KB-4(침해사고 사례DB)의 '국내 금융기관 IAM 탈취' 사례와 유사합니다.",
    "sources": [
      { "source_id": "ATT&CK-T1098", "type": "ATTACK", "title": "Account Manipulation" },
      { "source_id": "ATT&CK-T1098.001", "type": "ATTACK", "title": "Additional Cloud Credentials" },
      { "source_id": "CASE-2024-001", "type": "CASE_DB", "title": "국내 금융기관 IAM 탈취 사례" }
    ]
  }
}
```

---

### POST /api/sherpa/suggest — 빠진 고리 후보

**Request Body:**
```json
{
  "caseId": "f47ac10b-...",
  "nodeA": "atk-001",
  "nodeB": "atk-003"
}
```

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "suggestions": [
      {
        "technique_id": "T1098",
        "technique_name": "Account Manipulation",
        "tactic": "Persistence",
        "reason": "T1078(Initial Access) → T1098(Persistence) → T1530(Collection)은 IAM 탈취의 전형적인 공격 체인입니다. 수집 로그에서 CreateSubAccount 이벤트(evt-002)가 이 후보에 해당합니다.",
        "candidateEvents": ["evt-002"],
        "confidence": "medium",
        "sources": [
          { "source_id": "ATT&CK-T1098", "type": "ATTACK" }
        ]
      }
    ]
  }
}
```

---

### POST /api/sherpa/playbook — 플레이북 추천

**Request Body:**
```json
{
  "caseId": "f47ac10b-...",
  "chain": ["T1078.004", "T1098", "T1530"]
}
```

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "playbooks": [
      {
        "playbook_id": "PB-IAM-001",
        "title": "IAM 계정 탈취 대응 플레이북",
        "steps": [
          "1. 탈취된 계정 즉시 비활성화",
          "2. 모든 액세스 키 교체",
          "3. 공격자가 생성한 서브 계정/역할 삭제",
          "4. MFA 강제 적용",
          "5. 영향받은 리소스 접근 로그 검토"
        ],
        "sources": [
          { "source_id": "PB-IAM-001", "type": "PLAYBOOK" }
        ]
      }
    ]
  }
}
```

---

## Layer 4: 수사 보드

### POST /api/board/nodes — 노드 추가

**Request Body:**
```json
{
  "case_id": "f47ac10b-...",
  "attack_id": "atk-001",
  "label": "콘솔 로그인 (해외 IP)",
  "is_ai_suggested": false,
  "pos_x": 100,
  "pos_y": 200
}
```

**Response (201):**
```json
{
  "status": "ok",
  "data": {
    "node_id": "node-001",
    "case_id": "f47ac10b-...",
    "attack_id": "atk-001",
    "label": "콘솔 로그인 (해외 IP)",
    "status": "CONFIRMED",
    "is_ai_suggested": false,
    "pos_x": 100,
    "pos_y": 200,
    "created_at": "2025-03-15T11:00:00Z"
  }
}
```

---

### PATCH /api/board/nodes/{nodeId} — 노드 수락/거부

**Request Body:**
```json
{
  "status": "CONFIRMED",
  "label": "수정된 라벨 (선택)"
}
```

**Response (200):** 수정된 노드 전체 객체

---

### POST /api/board/edges — 엣지 추가

**Request Body:**
```json
{
  "case_id": "f47ac10b-...",
  "from_node_id": "node-001",
  "to_node_id": "node-002",
  "label": "자격증명 사용"
}
```

**Response (201):**
```json
{
  "status": "ok",
  "data": {
    "edge_id": "edge-001",
    "case_id": "f47ac10b-...",
    "from_node_id": "node-001",
    "to_node_id": "node-002",
    "label": "자격증명 사용",
    "created_at": "2025-03-15T11:05:00Z"
  }
}
```

---

### GET /api/board?caseId={caseId} — 보드 전체 상태

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "caseId": "f47ac10b-...",
    "nodes": [
      {
        "node_id": "node-001",
        "attack_id": "atk-001",
        "label": "콘솔 로그인 (해외 IP)",
        "status": "CONFIRMED",
        "is_ai_suggested": false,
        "pos_x": 100,
        "pos_y": 200
      },
      {
        "node_id": "node-002",
        "attack_id": "atk-002",
        "label": "서브 계정 생성",
        "status": "CONFIRMED",
        "is_ai_suggested": true,
        "pos_x": 300,
        "pos_y": 200
      }
    ],
    "edges": [
      {
        "edge_id": "edge-001",
        "from_node_id": "node-001",
        "to_node_id": "node-002",
        "label": "자격증명 사용"
      }
    ]
  }
}
```

---

## Layer 4: 보고서

### POST /api/report — 보고서 초안 생성

**Request Body:**
```json
{
  "caseId": "f47ac10b-..."
}
```

**Response (201):**
```json
{
  "status": "ok",
  "data": {
    "caseId": "f47ac10b-...",
    "sections": {
      "overview": "2025년 3월 15일 새벽, 해외 IP에서 IAM 계정 탈취를 통한 침해사고 발생...",
      "timeline": "02:30 콘솔 로그인 → 02:31 서브 계정 생성 → 02:33 권한 상승 → ...",
      "impact": "영향받은 서비스: Sub Account, Object Storage...",
      "attack_analysis": "MITRE ATT&CK 분석 결과: T1078.004 → T1098 → T1530...",
      "response": "대응 조치 사항...",
      "recommendation": "권고사항: MFA 강제 적용, 접근 키 교체...",
      "evidence": "증거 목록 및 해시값...",
      "comments": ""
    },
    "status": "DRAFT",
    "created_at": "2025-03-15T12:00:00Z"
  }
}
```

---

### PATCH /api/report/{caseId} — 섹션 수정

**Request Body:**
```json
{
  "section": "overview",
  "content": "수정된 사고 개요 내용..."
}
```

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "caseId": "f47ac10b-...",
    "section": "overview",
    "content": "수정된 사고 개요 내용...",
    "updated_at": "2025-03-15T12:30:00Z"
  }
}
```

---

### GET /api/report/{caseId}/export?format=docx — 내보내기

**Query Params:**
- `format`: `docx | pdf` (필수)

**Response:** 파일 다운로드 (Content-Type: application/octet-stream)
- `Content-Disposition: attachment; filename="report_{caseId}.docx"`

---

## 공통 엔드포인트

### GET /api/actions?caseId={caseId} — 액션 로그

**Response (200):**
```json
{
  "items": [
    {
      "log_id": "log-001",
      "case_id": "f47ac10b-...",
      "action": "ACCEPT",
      "target_type": "chain_node",
      "target_id": "node-002",
      "detail": "AI 제안 노드 수락",
      "created_at": "2025-03-15T11:30:00Z"
    }
  ],
  "total": 5,
  "page": 1,
  "pageSize": 20
}
```

---

### GET /api/health — 헬스 체크

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "server": "running",
    "db": "connected",
    "ollama": "available",
    "chromadb": "available",
    "version": "0.1.0"
  }
}
```

---

## Mock 데이터 활용 가이드

프론트엔드 개발자는 백엔드 미완성 시 위 응답 예시를 그대로 mock으로 사용합니다.

### 방법 1: API 래퍼에서 분기
```typescript
// api/intake.ts
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

export const createCase = async (data: CreateCaseReq): Promise<CaseResponse> => {
  if (USE_MOCK) {
    return MOCK_CASE_RESPONSE;  // 이 파일의 Response 예시 사용
  }
  const res = await client.post('/api/cases', data);
  return res.data.data;
};
```

### 방법 2: MSW (Mock Service Worker)
```typescript
// mocks/handlers.ts
import { rest } from 'msw';

export const handlers = [
  rest.post('/api/cases', (req, res, ctx) => {
    return res(ctx.json({
      status: 'ok',
      data: { caseId: 'f47ac10b-...', /* ... */ }
    }));
  }),
];
```

---

## TypeScript 타입 정의 (프론트엔드 참조)

이 API 계약서에 맞는 TypeScript 타입은 `frontend/src/types/index.ts`에 정의합니다.

```typescript
// 주요 타입 (CLAUDE.md의 공유 타입과 일치)
type IncidentType = 'CREDENTIAL_THEFT' | 'PRIVILEGE_ESCALATION' | 'DATA_EXFILTRATION' | 'AUDIT_LOG_TAMPERING' | 'MULTI_CSP_LATERAL';
type CSP = 'naver' | 'nhn' | 'all';
type Severity = 'critical' | 'high' | 'medium' | 'low';
type EvidenceRole = 'REQUIRED' | 'CORROBORATING';
type GapType = 'NONE' | 'COLLECTION' | 'EVIDENCE' | 'INTERPRETATION';
type NodeStatus = 'CONFIRMED' | 'REJECTED';

// API 요청/응답 인터페이스
interface CreateCaseReq {
  incident_type: IncidentType;
  csp: CSP;
  severity: Severity;
  occurred_at: string;
  system_config?: Record<string, unknown>;
}

interface CaseResponse {
  caseId: string;
  incident_type: IncidentType;
  csp: CSP;
  severity: Severity;
  occurred_at: string;
  system_config: Record<string, unknown> | null;
  created_at: string;
  closed_at: string | null;
}

interface CollectionTargetItem {
  target_id: string;
  log_type: string;
  evidence_role: EvidenceRole;
  priority: number;
  description: string;
  collected: boolean;
}

interface GuideResponse {
  caseId: string;
  completionRate: number;
  targets: CollectionTargetItem[];
}

interface UploadResponse {
  uploadId: string;
  fileName: string;
  fileHash: string;
  eventCount: number;
  matchedTargets: string[];
  csp: CSP;
  timeRange: { earliest: string; latest: string };
}

interface RawEventItem {
  event_id: string;
  case_id: string;
  csp: CSP;
  event_time: string;
  event_name: string;
  source_file: string;
  matched_target_id: string | null;
  sha256_hash: string;
  created_at: string;
}

interface OCSFEventItem {
  ocsf_id: string;
  event_id: string;
  class_uid: number;
  category_uid: number;
  activity_id: number;
  activity_name: string;
  time: number;
  actor: { user: { name: string; type: string; account_uid: string } };
  src_endpoint: { ip: string };
  status_code: string;
  severity_id: number;
  unmapped: Record<string, unknown>;
}

interface AttackEventItem {
  attack_id: string;
  ocsf_id: string;
  technique_id: string;
  technique_name: string;
  tactic: string;
  rule_id: string;
  risk_score: number;
  event_time: string;
  activity_name: string;
}

interface GapResultResponse {
  gap_id: string;
  case_id: string;
  gap_type: GapType;
  missing: { target_id: string; log_type: string; evidence_role: EvidenceRole; priority: number }[];
  summary: string;
  recommendation: string;
  completionRate: number;
  created_at: string;
}

interface BriefingResponse {
  technique_id: string;
  technique_name: string;
  tactic: string;
  briefing: string;
  sources: { source_id: string; type: string; title: string }[];
  relatedTechniques: string[];
  confidence: string;
}

interface ChatResponse {
  sessionId: string;
  response: string;
  sources: { source_id: string; type: string; title: string }[];
}

interface BoardNode {
  node_id: string;
  attack_id: string | null;
  label: string;
  status: NodeStatus;
  is_ai_suggested: boolean;
  pos_x: number;
  pos_y: number;
}

interface BoardEdge {
  edge_id: string;
  from_node_id: string;
  to_node_id: string;
  label: string;
}

interface BoardResponse {
  caseId: string;
  nodes: BoardNode[];
  edges: BoardEdge[];
}

interface ReportSections {
  overview: string;
  timeline: string;
  impact: string;
  attack_analysis: string;
  response: string;
  recommendation: string;
  evidence: string;
  comments: string;
}

interface ReportResponse {
  caseId: string;
  sections: ReportSections;
  status: string;
  created_at: string;
}
```
