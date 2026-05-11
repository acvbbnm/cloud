# AI Sherpa — 프로젝트 AI 코딩 지침

> 이 파일은 모든 AI 코딩 도구(Claude Code, Cursor 등)가 참조하는 **공유 규칙**입니다.
> 팀원 전원이 동일한 파일을 사용하여 코드 스타일, 구조, 네이밍을 통일합니다.

---

## 🤖 AI에게 — 이 폴더에서 작업을 시작하기 전 부팅 시퀀스

> 사용자(개발자)가 새 기능 구현을 요청하면, AI는 다음 순서로 컨텍스트를 잡은 뒤에 첫 코드를 작성한다.

1. **설계서 구조 파악** — [`docs/설계서_읽는법.md`](docs/설계서_읽는법.md) 의 2·3·5절 훑기 (시스템이 무엇이고 어디에 무엇이 적혀 있는지)
2. **다음 할 일 식별** — [`.claude/구현/구현_체크리스트.md`](.claude/구현/구현_체크리스트.md) 에서 비어 있는 `[ ]` 항목 중 사용자의 요청에 맞는 항목 선택
3. **모듈 명세 확인** — [`.claude/구현/모듈별_구현_명세.md`](.claude/구현/모듈별_구현_명세.md) 에서 해당 모듈의 입출력·핵심 로직·의존 관계 확인
4. **API 계약 확인** — 백엔드 API라면 [`.claude/구현/API_계약서.md`](.claude/구현/API_계약서.md) 에서 요청/응답 스키마 고정값 확인
5. **본 CLAUDE.md 규칙 준수** — 디렉토리 구조·네이밍·금지 사항(아래) 그대로 따른다
6. **작업 후 체크리스트 갱신** — 구현이 끝나면 같은 커밋에 체크리스트의 해당 항목을 `[ ] → [x]` 로 갱신한다

### 동시 작업 시 충돌 회피 (담당자 사전 고정 없음 — 선착순 모델)

- 작업 시작 전 `git fetch` 후 다른 사람의 feature 브랜치 목록을 확인해 **같은 체크리스트 항목**을 동시에 잡지 않는다
- 공유 진입 파일은 **추가만 한다 (수정·삭제 금지, 부득이할 때 PR 리뷰 1명 이상 필수)**:
  - `backend/main.py` — 라우터 등록만, 비즈니스 로직 금지
  - `backend/db/models.py` — DB 담당자만 수정 (스키마 변경은 별도 합의)
  - `frontend/src/App.tsx`, `frontend/src/main.tsx` — 라우팅 진입점
  - `frontend/src/types/index.ts` — 가능하면 도메인별 파일에서 re-export 형태로만 추가
- 라우터·뷰·타입은 **계층/도메인별로 별도 파일에 분리**되어 있으므로(아래 디렉토리 구조 참조), 본인 담당 파일만 편집하면 충돌이 거의 없다
- 의존성(`package.json`, `requirements.txt`) 변경은 PR 본문에 변경 사유 명기 + 팀장 확인 후 머지

---

## 프로젝트 개요

- **프로젝트명**: AI Sherpa — 국내 멀티 클라우드 침해사고 분석 시스템
- **아키텍처**: 5계층 파이프라인 (Layer 0 사고접수 → Layer 1 로그수집 → Layer 2 분석 → Layer 3 AI셰르파 → Layer 4 시각화/보고)
- **백엔드**: Python 3.10+ / FastAPI / SQLite / SQLAlchemy
- **프론트엔드**: React 18 + TypeScript + Tailwind CSS + Vite
- **AI**: Llama 3.1 8B (Ollama) + LlamaIndex + ChromaDB
- **상태관리**: Zustand
- **API 통신**: axios + React Query
- **시각화**: D3.js + react-flow
- **보고서**: Jinja2 + python-docx
- **핵심 원칙**: 오프라인(폐쇄망) 동작, AI는 판단하지 않고 검색·요약·제안만 수행

---

## 디렉토리 구조 (절대 준수)

```
backend/
  main.py                     # FastAPI 엔트리포인트
  config.py                   # 환경 설정
  api/                        # REST 라우터 (계층별 1파일)
    intake.py                 # /api/cases, /api/guide
    ingestion.py              # /api/logs/*
    analysis.py               # /api/analysis/*
    sherpa.py                 # /api/sherpa/*
    board.py                  # /api/board/*
    report.py                 # /api/report/*
  core/                       # 비즈니스 로직 (계층별 패키지)
    intake/                   # Layer 0
    ingestion/                # Layer 1
    analysis/                 # Layer 2
    sherpa/                   # Layer 3
    board/                    # Layer 4
  db/
    models.py                 # SQLAlchemy 모델 (9개 테이블)
    session.py                # DB 세션
  data/                       # 정적 JSON 데이터
    mapping_rules/            # OCSF 필드 매핑
    attack_rules/             # ATT&CK 매핑 룰
    kb/                       # 지식베이스 원본 (4종)
    collection_targets/       # 수집 대상 카탈로그

frontend/
  src/
    views/                    # 8개 뷰 (V1_Setup ~ V8_Sherpa)
    components/               # 공통 컴포넌트
    stores/                   # Zustand 스토어
    api/                      # API 호출 래퍼
    hooks/                    # 커스텀 훅
    types/                    # TypeScript 타입 정의
```

새 파일을 만들 때 반드시 위 구조를 따른다. 임의의 위치에 파일을 생성하지 않는다.

---

## Python 백엔드 규칙

### 코드 스타일
- **포맷터**: black (line-length 100)
- **import 순서**: stdlib → 서드파티 → 로컬, 각 그룹 사이 빈 줄 1개
- **타입 힌트**: 모든 함수에 파라미터 타입 + 리턴 타입 명시
- **docstring**: 클래스와 public 메서드에 한국어 docstring 작성

```python
# ✅ 올바른 예시
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from db.session import get_db
from core.intake.incident_case import IncidentCase


router = APIRouter(prefix="/api/cases", tags=["intake"])


@router.post("")
async def create_case(req: CreateCaseRequest, db: Session = Depends(get_db)) -> dict:
    """사고 케이스를 신규 생성한다."""
    case = IncidentCase.create(
        incident_type=req.incident_type,
        csp=req.csp,
        severity=req.severity,
        system_config=req.system_config,
    )
    return {"status": "ok", "data": {"caseId": case.case_id}}
```

### 네이밍
- **파일명**: snake_case (`incident_case.py`, `gap_detector.py`)
- **클래스**: PascalCase (`IncidentCase`, `OCSFNormalizer`, `AttackMapper`)
- **함수/변수**: snake_case (`create_case`, `case_id`)
- **상수**: UPPER_SNAKE_CASE (`MAX_FILE_SIZE`, `DEFAULT_PAGE_SIZE`)
- **DB 테이블명**: snake_case 복수형 (`incident_cases`, `raw_events`, `attack_events`)
- **DB 칼럼명**: snake_case (`case_id`, `incident_type`, `created_at`)

### 클래스명 (설계서 기준 — 변경 금지)
```
Layer 0: IncidentCase, CollectionGuide, CollectionTarget, IncidentTypeKnowledge
Layer 1: LogIngestor, RawEvent, IngestionStats
Layer 2: OCSFNormalizer, AttackMapper, MappingRule, GapDetector, OCSFEvent, AttackEvent, GapResult
Layer 3: AISherpa, RAGRetriever, LLMEngine, KnowledgeBase, ChatSession
Layer 4: InvestigationBoard, ChainNode, ChainEdge, ReportGenerator
Common: ActionLog
```

> **User 클래스 없음**: 설계서 5.1절 영속화 정책에 따라 MVP는 단일 수사관 로컬 데스크톱 배포를 가정하므로 인증·권한 미사용. `action_logs.actor` 컬럼에 고정 라벨(`"investigator"`)을 기록한다. 다중 사용자·역할 분리는 Phase 2 확장 범위.

### API 라우터 규칙
- 라우터 파일 1개 = 1개 계층 (intake.py, ingestion.py, analysis.py, sherpa.py, board.py, report.py)
- prefix는 `/api/` 로 시작
- 태그는 계층명 (tags=["intake"], tags=["analysis"] 등)
- Pydantic 모델로 요청/응답 스키마 정의

### API 응답 형식 (통일)
```python
# 성공
{"status": "ok", "data": { ... }}

# 에러
{"status": "error", "message": "설명", "code": "ERROR_CODE"}

# 페이지네이션
{"items": [...], "total": 100, "page": 1, "pageSize": 20}
```

### DB 모델 규칙
- SQLAlchemy Declarative Base 사용
- PK는 VARCHAR(36) UUID (uuid.uuid4()로 생성)
- FK는 동일 타입으로 선언하고 ForeignKey 명시
- created_at/updated_at 자동 설정
- JSON 칼럼은 SQLAlchemy JSON 타입 사용

```python
# ✅ 올바른 DB 모델 예시
class IncidentCase(Base):
    __tablename__ = "incident_cases"

    case_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_type = Column(String(32), nullable=False)  # 5종 enum
    csp = Column(String(16), nullable=False)             # naver/nhn/all
    severity = Column(String(8), nullable=False)          # critical/high/medium/low
    occurred_at = Column(DateTime, nullable=False)
    system_config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
```

### 에러 처리
- FastAPI HTTPException 사용
- 400: 입력 검증 실패
- 404: 리소스 미존재
- 500: 서버 내부 오류 (로깅 필수)

```python
if not case:
    raise HTTPException(status_code=404, detail={"message": "케이스를 찾을 수 없습니다", "code": "CASE_NOT_FOUND"})
```

---

## TypeScript 프론트엔드 규칙

### 코드 스타일
- **세미콜론**: 사용
- **따옴표**: 작은따옴표 (`'`)
- **들여쓰기**: 2칸
- **import 순서**: react → 서드파티 → 로컬 컴포넌트 → 로컬 유틸 → 타입, 각 그룹 사이 빈 줄

```tsx
// ✅ 올바른 예시
import { useState, useEffect } from 'react';

import { useQuery } from '@tanstack/react-query';

import { KpiCard } from '@/components/KpiCard';
import { Sidebar } from '@/components/Sidebar';

import { useCaseStore } from '@/stores/useCaseStore';
import { createCase } from '@/api/intake';

import type { IncidentCase, CreateCaseReq } from '@/types';
```

### 네이밍
- **파일명**: PascalCase for 컴포넌트 (`KpiCard.tsx`, `Step0_CSPCards.tsx`)
- **파일명**: camelCase for 유틸/훅/API (`useCaseStore.ts`, `client.ts`)
- **컴포넌트**: PascalCase (`KpiCard`, `SetupWizard`)
- **훅**: useCamelCase (`useCaseStore`, `useLogUpload`)
- **변수/함수**: camelCase (`caseId`, `handleSubmit`)
- **상수**: UPPER_SNAKE_CASE (`API_BASE_URL`)
- **타입/인터페이스**: PascalCase (`IncidentCase`, `GapResult`)

### 뷰 디렉토리 구조 (V1~V8)
```
views/
  V1_Setup/
    index.tsx                 # 뷰 엔트리 (라우터에서 import)
    Step0_CSPCards.tsx
    Step1_TypeCards.tsx
    Step2_SystemConfig.tsx
    Step3_GuideChecklist.tsx
  V2_Logs/
    index.tsx
    DropZone.tsx
    EventPreviewTable.tsx
  ...
```

각 뷰 폴더의 `index.tsx`가 해당 뷰의 메인 컴포넌트이다.

### 컴포넌트 작성 규칙
- 함수형 컴포넌트 + 화살표 함수 사용
- Props 인터페이스는 컴포넌트 파일 상단에 정의
- default export 사용

```tsx
// ✅ 올바른 컴포넌트 예시
interface KpiCardProps {
  label: string;
  value: number | string;
  color?: string;
}

const KpiCard = ({ label, value, color = 'blue' }: KpiCardProps) => {
  return (
    <div className={`rounded-lg bg-gray-800 p-4 border-t-2 border-${color}-500`}>
      <p className="text-sm text-gray-400">{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
    </div>
  );
};

export default KpiCard;
```

### Zustand 스토어 규칙
- 파일명: `use[도메인]Store.ts`
- 인터페이스 먼저 정의 후 create
- 액션은 set 함수로 처리

```tsx
// ✅ 올바른 스토어 예시
import { create } from 'zustand';

interface CaseState {
  caseId: string | null;
  csp: string | null;
  incidentType: string | null;
  currentStep: number;
  setCaseId: (id: string) => void;
  setStep: (step: number) => void;
  reset: () => void;
}

export const useCaseStore = create<CaseState>((set) => ({
  caseId: null,
  csp: null,
  incidentType: null,
  currentStep: 0,
  setCaseId: (id) => set({ caseId: id }),
  setStep: (step) => set({ currentStep: step }),
  reset: () => set({ caseId: null, csp: null, incidentType: null, currentStep: 0 }),
}));
```

### API 호출 래퍼 규칙
- `api/client.ts`: axios 인스턴스 (baseURL 설정)
- 계층별 파일: `api/intake.ts`, `api/logs.ts`, `api/analysis.ts` 등
- mock 전환 가능하도록 작성

```tsx
// api/client.ts
import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
});

export default client;
```

```tsx
// api/intake.ts
import client from './client';
import type { CreateCaseReq, CaseResponse } from '@/types';

export const createCase = async (data: CreateCaseReq): Promise<CaseResponse> => {
  const res = await client.post('/api/cases', data);
  return res.data.data;
};

export const getGuide = async (caseId: string) => {
  const res = await client.get('/api/guide', { params: { caseId } });
  return res.data.data;
};
```

### UI/스타일 규칙
- 다크 테마 기본 (bg-gray-900 + text-white)
- Tailwind 유틸리티 클래스 사용, 인라인 style 지양
- 3-zone 레이아웃: 좌측 Sidebar(w-56) + 메인 콘텐츠(flex-1) + SherpaFab(플로팅)
- 색상 팔레트:
  - 배경: gray-900, gray-800
  - 주요 텍스트: white, gray-100
  - 보조 텍스트: gray-400
  - 강조(파란): blue-500, blue-400
  - 성공: green-500
  - 경고: yellow-500
  - 위험: red-500
  - REQUIRED 배지: red-600 배경
  - CORROBORATING 배지: yellow-600 배경

---

## 타입 정의 (types/index.ts — 프론트엔드·백엔드 공유 기준)

```typescript
// ── 사고 유형 (5종, 설계서 5.2절 incident_cases 테이블 기준) ──
type IncidentType = 'CREDENTIAL_THEFT' | 'PRIVILEGE_ESCALATION' | 'DATA_EXFILTRATION' | 'AUDIT_LOG_TAMPERING' | 'MULTI_CSP_LATERAL';

// ── CSP ──
type CSP = 'naver' | 'nhn' | 'all';

// ── 심각도 ──
type Severity = 'critical' | 'high' | 'medium' | 'low';

// ── 증거 역할 ──
type EvidenceRole = 'REQUIRED' | 'CORROBORATING';

// ── 갭 유형 ──
type GapType = 'NONE' | 'COLLECTION' | 'EVIDENCE' | 'INTERPRETATION';

// ── 체인 노드 상태 (설계서 5.2절 chain_nodes 테이블 기준) ──
type NodeStatus = 'PENDING' | 'CONFIRMED' | 'REJECTED';

// ── 액션 로그 동작 ──
type ActionType = 'ACCEPT' | 'REJECT' | 'EDIT_REPORT' | 'FINALIZE_REPORT' | 'EXPORT_REPORT';
```

이 타입명과 값은 백엔드 DB enum과 정확히 일치해야 한다. 임의로 변경하지 않는다.

---

## DB 테이블 (9개 — 변경 시 팀 합의 필수)

| # | 테이블명 | 핵심 역할 |
|---|--------|---------|
| 1 | incident_cases | 사고 케이스 메타데이터 |
| 2 | collection_targets | 수집 대상 카탈로그 (지식베이스) |
| 3 | raw_events | 원본 로그 + SHA-256 |
| 4 | ocsf_events | OCSF 정규화 이벤트 |
| 5 | attack_events | ATT&CK 매핑 결과 |
| 6 | gap_results | 갭 판정 결과 |
| 7 | chain_nodes | 공격 체인 노드 (※ 설계서 8컬럼 + `label` 1컬럼 추가 — 보드 UI 노드 표시용, 팀 합의 사항) |
| 8 | chain_edges | 체인 엣지 (방향성) |
| 9 | action_logs | 수사관 조작 이력 |

---

## REST API 엔드포인트 (22개 — 변경 시 팀 합의 필수)

### Layer 0 — 사고 접수
- `POST /api/cases` → 케이스 생성
- `GET /api/cases/{caseId}` → 상세 조회
- `PATCH /api/cases/{caseId}` → 구성 수정
- `GET /api/guide?caseId=` → 체크리스트 생성

### Layer 1 — 로그 수집
- `POST /api/logs/upload` → 로그 업로드 (multipart)
- `GET /api/logs?caseId=&page=&pageSize=` → 이벤트 목록
- `GET /api/logs/{eventId}` → 원본 이벤트

### Layer 2 — 분석
- `POST /api/analysis/normalize` → OCSF 정규화
- `POST /api/analysis/map` → ATT&CK 매핑
- `GET /api/analysis/ocsf?caseId=` → OCSF 결과 조회
- `GET /api/analysis/attack?caseId=` → ATT&CK 결과 조회
- `POST /api/analysis/gap` → 갭 감지

### Layer 3 — AI 셰르파
- `POST /api/sherpa/brief` → 컨텍스트 브리핑
- `POST /api/sherpa/suggest` → 빠진 고리 후보
- `POST /api/sherpa/playbook` → 플레이북 추천
- `POST /api/sherpa/chat` → 자연어 질의

### Layer 4 — 보드 / 보고서
- `POST /api/board/nodes` → 노드 추가
- `PATCH /api/board/nodes/{nodeId}` → 수락/거부
- `POST /api/board/edges` → 엣지 추가
- `GET /api/board?caseId=` → 보드 상태
- `POST /api/report` → 보고서 초안
- `PATCH /api/report/{caseId}` → 섹션 수정
- `GET /api/report/{caseId}/export?format=` → 내보내기

### 공통
- `GET /api/actions?caseId=` → 액션 로그
- `GET /api/health` → 헬스 체크

---

## 금지 사항

1. **설계서에 정의된 클래스명, 테이블명, API 경로를 임의로 변경하지 않는다**
2. **db/models.py는 DB 담당자만 수정한다** (스키마 변경 영향이 크기 때문)
3. **main.py에 비즈니스 로직을 넣지 않는다** (라우터 등록만)
4. **외부 CDN을 사용하지 않는다** (오프라인 동작 필수, SNF-01)
5. **AI가 판단/결정하는 코드를 작성하지 않는다** (AI는 검색·요약·제안만, 수사관이 수락/거부)
6. **console.log / print 디버깅을 커밋하지 않는다**
7. **하드코딩된 절대 경로를 사용하지 않는다** (config.py에서 관리)
8. **`.env` 파일을 커밋하지 않는다** (`.env.example`만 커밋)

---

## 커밋 메시지 규칙

```
feat: 새 기능 추가
fix: 버그 수정
refactor: 리팩토링 (기능 변경 없음)
docs: 문서 수정
test: 테스트 추가/수정
chore: 빌드, 설정 변경
```

예시:
```
feat: POST /api/cases 사고 케이스 생성 API 구현
feat: V-2 로그 수집 DropZone 컴포넌트 구현
fix: OCSF 정규화 시 NHN eventTime 파싱 오류 수정
refactor: AttackMapper 규칙 로딩을 startup 시 1회로 변경
```

---

## 자주 참조하는 설계서 위치

| 구현 대상 | 설계서 섹션 |
|---------|----------|
| DB 스키마 | 5.1절 ERD + 5.2절 테이블 명세 |
| 클래스 설계 | 5.4절 패키지별 클래스 다이어그램 |
| REST API | 5.6절 API 명세 |
| 화면 설계 | 5.7절 화면 정의서 + UI Mockup |
| 데이터 흐름 | 4.2절 DFD Level-1 |
| 객체 상호작용 | 4.3절 시퀀스 다이어그램 (UC-01~08) |
| OCSF 필드 매핑 | 5.2.1절 CSP별 필드 매핑 실증 분석 |
| ATT&CK 매핑 룰 | 5.2.2절 매핑 실증 분석 |
| KB JSON 스키마 | 5.3절 (KB-1 ~ KB-4) |
| 화면 전환 흐름 | 5.7.2절 화면 흐름도 + 전환 트리거 표 |
