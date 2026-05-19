# AI Sherpa — 진행 현황

> 마지막 업데이트: 2026-05-19 · 브랜치: `dev3` (V-1 재설계 — B-3 DB 칼럼 확장 + B-2/V-8 백엔드 머지 완료)
> 이 문서는 **팀이 같은 그림을 보기 위한 작업 메모**입니다. 작업 시작 전·종료 후 갱신해 주세요.

---

## 한눈에 보기

| Phase / Layer | 화면·모듈 | 프론트엔드 | 백엔드 | 데이터 |
|---|---|---|---|---|
| **Phase 1 — 기반 구축** | | | | |
| 1-1 DB 스키마 | `db/models.py` 9개 테이블 | — | ✅ 설계서 5.2절 정렬 | ✅ |
| 1-2 Layer 0 API | `/api/cases`, `/api/guide` | ✅ V1 실 API 연결 완료 | ✅ 4개 엔드포인트 동작 | ✅ |
| 1-3 프론트엔드 셸 | Sidebar, Header, V1 위저드 | ✅ 디자인 시스템 + V1 실 연동 | — | — |
| 1-4 RAG 지식베이스 | KB-1~4 JSON | — | ✅ **깡통 RAG 동작** (키워드+점수화) · ChromaDB 미구현 | 🟢 시드 작성 완료 |
| **Phase 2 — 핵심 파이프라인** | | | | |
| 2-1 Layer 1 로그 수집 | V2 드롭존·미리보기 | ✅ V2 실 API 연결 완료 | ✅ 3개 엔드포인트 + 파서 + 매처 동작 | ✅ raw 228건 E2E 검증 |
| 2-2 Layer 2 분석 | V3 OCSF · V4 갭 | ✅ V3·V4 실 API 연결 완료 | ✅ 5개 엔드포인트 동작 | ✅ 정규화 100%, 매핑 76건 |
| **Phase 3 — 보드·셰르파** | | | | |
| 3-1 Layer 4 수사 보드 | V5 보드 | ✅ **V5 노드 + AI 브리핑 모두 실 API** | 🟡 백엔드 1차 (4개 엔드포인트, DB E2E 미검증) | — |
| 3-2 Layer 3 AI 셰르파 | V8 챗 · V6 ATT&CK 히트맵 | ✅ **V6·V8 모두 실 API** (V8 출처 칩 표시) | ✅ **1차 깡통 동작** (5 엔드포인트, LLM/RAG 추상화) | ✅ KB 4종 청크화 |
| **Phase 4 — 보고서** | | | | |
| 4-1 보고서 | V7 보고서 편집기 | ✅ **V7 실 API 연결 완료** (편집·저장·최종화·DOCX) | ✅ 백엔드 1차 (4개 엔드포인트, DOCX export 동작, PDF 501) | — |
| **Phase 5 — V-1 재설계 (dev3 분기)** | | | | |
| 5-1 Triage 데이터 | `data/triage/{decision_tree,weights,next_clue_graph}.json` | — | — | ✅ 학술 가중치 매트릭스 + 결정 트리 골격 |
| 5-2 프론트 V-1 Step 1 | `Step1_CaseMetadata` (빈 케이스 + UNCLASSIFIED) | ✅ TheHive·IRIS·NIST §3.2 정합 | — | — |
| 5-3 프론트 V-1 Step 2 | `Step2_Discovery` 3-panel (단서·부분분석·결정트리·시각화) | ✅ 사전 안내 모달 + 트리 시각화 미니맵 + 다음 단서 패널 | — | — |
| 5-4 프론트 스토어 | `useCaseStore` 확장 + `useTriageStore` 신규 | ✅ persist v1→v2 마이그레이션 + 트리 상태 영속화 | — | — |
| 5-5 백엔드 Triage API | `/api/triage/{start,next,analyze,confirm}` | — | ✅ **B-1 완료** — 4 라우터 + 평가 엔진 + UNCLASSIFIED enum | ✅ 가중치 누적 시뮬레이션 통과 |
| 5-6 백엔드 부분 로그 (B-2) | `/api/triage/analyze-logs` + `/api/triage/tree` | — | ✅ **B-2 완료** (jingyu 머지) — UploadFile + Layer 1·2 재사용 + 트리 시각화 직렬화 | — |
| 5-7 백엔드 DB 칼럼 (B-3) | `incident_cases.{title,tlp,observables,secondary_incident_types,triage_state}` | — | ✅ **B-3 완료** — 5 칼럼 추가 + idempotent 마이그레이션 + intake/triage 영속화 + E2E 통과 | — |
| 5-8 V-8 사후 검증 | `GET /api/sherpa/validate-incident-type` + `IncidentTypeReviewCard` | ✅ **완료** — ReviewCard 자동 노출 + 부 사고유형 등록·메인 격상 UI | ✅ **백엔드 완료** (jingyu 머지) — 관측 ATT&CK ↔ IncidentTypeKnowledge 정합성 점수화 | — |
| 5-9 Step 3 UNCLASSIFIED 분기 | `GET /api/guide/v2` UNCLASSIFIED 처리 | (재로드 동작) | ✅ **완료** (jingyu 머지) — Initial Access + Credential Access + Discovery phase fallback | — |
| 5-10 사고유형 9종 확장 (C-1) | 5종 → 9종 (RANSOMWARE·MISCONFIG·PHISH·INSIDER) | ⏳ 인계 대기 (`docs/dev3/C_사고유형_9종_확장.md`) | ⏳ 인계 대기 — weights·KB·Literal 갱신 | ⏳ KB 청크 24-28개 신규 |

범례: ✅ 완료 · ⏳ 대기 · ❌ 미구현 · 🎭 mock 데이터 · 🟢 시드 OK

**현재 상태**: **walking-skeleton 100% 종결** + **dev3 V-1 재설계 청사진 100% 완료**. V-1~V-8 **8/8 화면이 mock 없이 실 API와 통신**. dev3 분기에서 V-1 Step 1 사고유형 강제 선택을 폐기하고 빈 케이스 + 결정 트리 + AI 보조 패널 + Layer 2 부분 분석을 결합한 Discovery Loop 가 작동. V-8 사후 검증 카드(IncidentTypeReviewCard)가 Layer 2 매핑 결과로 사고유형 정합성을 자동 평가·보완 제안. Layer 3는 깡통 LLM/RAG(키워드+점수화+템플릿)로 동작 중이며, 인터페이스 보존하며 Ollama·ChromaDB로 후속 교체 예정.

---

## 작업 내역

### 2026-05-19 (밤) — C-1 사고유형 9종 확장 — 작업 지시서 등록 (다른 팀원 인계)

**배경**: 시연 중 가설 점수 패널에 5종만 표시 — KISA §3.3 (6-7종) / CSA Pandemic Eleven (11종) 대비 약함. 캡스톤 평가 변호력 강화 위해 9종으로 확장.

**확장 사고유형 (4종 신규)**:
- `RANSOMWARE` — CSA #5 + Verizon DBIR 24% + MITRE T1486
- `MISCONFIG_EXPOSURE` — CSA #3 + DBIR 빈도 1위 + MITRE T1190+T1530
- `PHISH_INITIAL_ACCESS` — CSA #2 + MITRE T1566
- `INSIDER_THREAT` — KISA §3.3 "불법적 자원 사용" + MITRE T1078

→ 9종 + UNCLASSIFIED = 총 10종 → **KISA §3.3 분류표 100% 정합 + CSA Pandemic Eleven 의 #1·2·3·5·7·11 커버**.

**작업 지시서**: `docs/dev3/C_사고유형_9종_확장.md`
- 변경 파일 매트릭스 (백엔드 + 프론트 + KB + 문서)
- 단계별 가이드 (데이터 → 코드 → 임베딩 → 프론트 → 시뮬레이션 → 문서)
- 가중치 자동 갱신 스크립트 가이드 (`backend/scripts/expand_weights_to_9.py`)
- KB 청크 작성 표준 + 예시 (RANSOMWARE 대표 청크 attack/playbook/case_db 3종)
- 시뮬레이션 검증 시나리오 S6~S9 (RANSOMWARE / MISCONFIG / PHISH / INSIDER)
- PR 가이드 + 4 커밋 분할 권고 + 체크리스트
- 위험·미해결 항목 5종

**예상 공수**: 1명 7-8h / 2명 분담 시 4-5h

**다음 담당자**: 팀원 1-2명 분담 가능. KB 청크 24-28개 작성이 가장 큰 부담 (3-4h).

### 2026-05-19 (저녁) — dev3 청사진 100% 완료: V-8 IncidentTypeReviewCard

**dev3 V-1 재설계 마지막 작업** — V-8 사후 검증 프론트 카드.

흐름:
1. V-8 진입 시 `caseId` 있으면 자동으로 `GET /api/sherpa/validate-incident-type` 호출
2. `status === 'CONSISTENT'` → 카드 숨김 (노이즈 X)
3. `status === 'REVIEW_NEEDED'` → 화면 상단에 amber 알림 카드 자동 노출
   - 현재 메인·부 사고유형 배지 표시
   - Layer 2 추가 매핑 기법 (extra_techniques) 코드 칩 8개+
   - candidate_types 리스트 — 각 항목에 [+ 부 사고유형] / [메인으로 격상] 버튼
4. 버튼 클릭 → `PATCH /api/cases/{caseId}` 로 영속화 → `useCaseStore` 동기화 → validation 재호출

특징:
- AI 제안만 (결정은 수사관) — CLAUDE.md SNF 원칙 정합
- "메인 격상" 시 기존 메인은 secondary 로 강등 (다중 사고유형 우아한 전환)
- 카드 우상단 ✕ 로 세션 dismiss 가능 (피로 최소화)
- staleTime 30초 — V-2 분석 직후 빈번 재호출 방지

학술 근거: AWS GuardDuty AttackSequence finding + Microsoft Defender XDR attack story.

신규/수정:
- `frontend/src/api/sherpa.ts` — getIncidentTypeValidation 추가
- `frontend/src/api/intake.ts` — updateCase + UpdateCaseReq 추가 (PATCH 호출 래퍼)
- `frontend/src/views/V8_Sherpa/IncidentTypeReviewCard.tsx` — 신규 (224줄)
- `frontend/src/views/V8_Sherpa/index.tsx` — caseId 있을 때 카드 자동 렌더

검증: `tsc --noEmit` 통과.

**🎉 dev3 청사진 100% 완료** — V-1 재설계의 9개 항목 (5-1 ~ 5-9) 전부 완성.
- 데이터 (decision_tree·weights·next_clue_graph)
- 프론트 (Step1 메타 + Step2 Discovery 3-panel + 트리 시각화 + 사전 안내)
- 백엔드 (Triage API 4 + B-2 멀티파트 + B-3 DB 칼럼 5종 + V-8 사후 검증)
- UI (UNCLASSIFIED Step3 fallback + V-8 ReviewCard)

남은 후속 (선택):
- E2E 시연 시나리오 갱신
- 캡스톤 발표 자료에 청사진 흐름 반영

### 2026-05-19 — dev3 B-3: incident_cases 칼럼 5종 확장 + jingyu 머지

**진규 브랜치 머지** (`ccf7de3` Merge `e706012`):
- B-2 완료: `POST /api/triage/analyze-logs` (multipart) — Layer 1·2 파이프라인 재사용, clue_time ±5분 윈도우 attack_events 필터
- 트리 시각화: `GET /api/triage/tree` + `Triage.tree_visualization()`
- Step 3 fallback: `GET /api/guide/v2` UNCLASSIFIED 분기 (Initial Access + Credential Access + Discovery phase)
- V-8 사후 검증: `GET /api/sherpa/validate-incident-type` — 관측 ATT&CK ↔ `IncidentTypeKnowledge.related_techniques` 점수화 → CONSISTENT / REVIEW_NEEDED + candidate_types

**B-3 DB 칼럼 확장** (이 커밋):
`incident_cases` 테이블에 V-1 재설계 칼럼 5종 추가:
- `title` VARCHAR(200) NULL — 사건 제목 (기존 row 호환 위해 nullable)
- `tlp` VARCHAR(16) NOT NULL DEFAULT 'AMBER' — TheHive 5 정보 공유 등급
- `observables` JSON NOT NULL DEFAULT '[]' — Observable 배열
- `secondary_incident_types` JSON NULL — V-8 사후 검증으로 추가될 부 사고유형
- `triage_state` JSON NULL — 결정 트리 진행 상태 전체 영속화

작업 단위:
1. `db/models.py` — `IncidentCaseModel` 5 칼럼 추가
2. `db/migrate_b3.py` — idempotent ALTER TABLE 마이그레이션 스크립트 (`PRAGMA table_info` 로 기존 칼럼 체크 후 skip)
3. `core/intake/incident_case.py` — `create()` / `update_config()` 신규 필드 수용 (incident_type 변경, observables 갱신, triage_state 통째 교체)
4. `api/intake.py` — `POST /api/cases` + `PATCH /api/cases/{caseId}` + `_serialize_case` 신규 5 필드 수용·응답
5. `api/triage.py` — `POST /api/triage/confirm` 의 `secondary_incident_types` · `triage_state` · `observables` 실 영속화 (이전 echo only → DB 반영)

검증 (TestClient E2E 4 단계):
- CREATE: UNCLASSIFIED + title + tlp + observables → 201 + 신규 필드 응답
- GET: 신규 5 필드 모두 노출
- PATCH: incident_type CREDENTIAL_THEFT 변경 + secondary + triage_state 갱신
- CONFIRM: incident_type DATA_EXFILTRATION 확정 + 4 필드 동시 영속화
→ **모든 단계 PASS**

마이그레이션 사용법:
```bash
python -m db.migrate_b3   # 기존 DB 사용자
# 신규 DB 는 init_db.py create_all() 가 자동 처리 (마이그 스크립트는 SKIP 만)
```

**dev3 청사진 잔여 작업** (백엔드는 100% 완료):
- ❌ V-8 IncidentTypeReviewCard 프론트 — `validate-incident-type` 호출 + 추가 사고유형 등록 UI
- (선택) E2E 시연 시나리오 + 보고서 갱신

### 2026-05-18 — dev3 분기: V-1 재설계 (Discovery Loop + 결정 트리 + Triage API)

**배경**: V-1 Step 1 의 "사고유형 5종 강제 선택" 이 글로벌 표준 (AWS Detective, MS Sentinel, GCP SCC, TheHive, DFIR-IRIS, NIST 800-61r2) 8 개 모두와 정반대 흐름임이 벤치마킹 조사로 확인. 사고유형은 **단서 → 분석 → 추정** 의 후행 분류여야 함. dev2 보존을 위해 별도 `dev3` 분기에서 재설계 진행.

**기획 단계** (커밋 `e958c7a`):
- `docs/dev3/V1_재설계_청사진.md` (35KB) — Step 0~3 + V-8 사후 검증 + Discovery Loop + DB·API·파일 매트릭스 + 일정 54h + 표준 매핑 10 종
- `docs/dev3/사용자_결정사항.md` — 8 항목 논의 트레이스
- `docs/dev3/가중치_설계_근거.md` (18KB) — 학술 인용 + 5 시나리오 시뮬레이션 + 임계값 산정
- `docs/벤치마크_클라우드_사고조사.md` (27KB) — 6 개 플랫폼 상세 비교
- `backend/data/triage/decision_tree.json` — Q1~Q3 + T_evaluate
- `backend/data/triage/weights.json` — 답변 25 + 단서 17 + ATT&CK 24 + env_modifier 13
- `backend/data/triage/next_clue_graph.json` — 단서 6 종 × 다음 단서 2~4 개

**프론트엔드 단계** (커밋 `83e4dd4` → `b74402f`):
- `types/index.ts` — `UNCLASSIFIED`·`TLP`·`Observable`·`Triage*` 타입 14 종 추가
- `useCaseStore` 확장 + persist v1→v2 마이그레이션
- `useTriageStore` 신규 — 트리 진행 상태 + 가설 점수 + recommendation 영속화
- `Step1_CaseMetadata` 신규 (Title · 시각 · Severity · TLP · UNCLASSIFIED 자동 안내)
- `Step1_TypeCards` 폐기 (호환성 보존)
- `Step2_Discovery` (550 줄) — 3-panel 레이아웃, 단서 입력(F-1), 부분 로그 분석(F-2), 다음 단서 패널(F-3), 트리 시각화 미니맵(F-4), 사전 안내 모달(F-5)
- `api/triage.ts` — 자동 mock fallback 포함 백엔드 4 라우터 호출

**백엔드 단계** (커밋 `aedf710`, B-1 완료):
- `backend/api/triage.py` (192 줄) — `/api/triage/{start, next, analyze, confirm}` 4 라우터
- `backend/core/intake/triage.py` (372 줄) — `Triage` 평가 엔진 + 정적 JSON 캐싱 + 점수 누적 + recommendation 평가
- `backend/api/intake.py` — `IncidentType` Literal 에 `UNCLASSIFIED` 추가
- `backend/main.py` — triage 라우터 등록
- 검증: Q1 csp_alert → Q2A 비정상로그인+비국내IP → Q3 fail_then_success → CRED 95 → `auto_confirm` 자동 발동 (학술 가중치 매트릭스 의도대로 작동)

**해결한 이슈**: 사용자 보고 "사고유형 선택 후 다음 레이어 못 감" — 옛 백엔드가 `UNCLASSIFIED` enum 거부(422) 로 `createCase` 실패. B-1 푸시 + 백엔드 재시작 후 자동 해소.

**설계 원칙** (인계 시 보존):
- 결정성 100% (정적 가중치만, 같은 입력 → 같은 출력)
- AI 판단 X (점수 산출만, 결정은 트리 + 사용자)
- stateless (클라이언트가 `hypothesis_scores`·`tree_path` 매 요청 전달)
- 임계값 단일 소스 (`weights.json thresholds`)

**남은 후속 작업**:
- B-2: 부분 로그 멀티파트 업로드 (`UploadFile` + Layer 1·2 재사용)
- B-3: `incident_cases` 신규 칼럼 (`title`, `tlp`, `observables`, `secondary_incident_types`, `triage_state`) — **CLAUDE.md 규칙상 DB 담당자 합의 필수**
- V-8 사후 검증: `IncidentTypeReviewCard` (Layer 2 매핑 vs 확정 사고유형 정합성)
- Step 3 UNCLASSIFIED 공통 가이드 분기

**참조 문서**:
- `docs/dev3/V1_재설계_청사진.md` — 전체 설계
- `docs/dev3/B_백엔드_인계.md` — B-1 검증 절차 + B-2/B-3 후속 작업 가이드
- `docs/dev3/가중치_설계_근거.md` — 학술 인용 + 시뮬레이션

### 2026-05-15 — 가이드 시스템 근거 보강 2-트랙 진행 (`dev` vs `dev2` 병행)

기존 `dev`의 수집 가이드(`CollectionGuide.generate()`)가 `system_config` 입력을 무시하고 `incident_type`+`csp` 두 필드만 사용한다는 점, collection_targets 5건 분류 근거가 부재한 점이 외부 표준 부재 학술 약점으로 식별됨. 외부 표준 6종(KISA / MITRE / NIST / ISO / Google Cloud / CSA) 분석 후 두 트랙 병행 결정.

**Track A — `dev` 브랜치: 기존 구조 유지 + 근거 메타 추가**

- 담당: dev 브랜치 작업자 (먼저 작업 시작 가능)
- 목표: 기존 시드·코드 구조 그대로, 각 항목에 외부 표준 출처 메타 추가
- 1차안 완료: [`docs/분석_설계_근거.md`](docs/분석_설계_근거.md) ([`71d61d4`](https://github.com/sasumm25-lab/cloud/commit/71d61d4))
- 남은 작업 (이어서 진행할 팀원에게):
 1. `data/collection_targets/{naver,nhn}_CREDENTIAL_THEFT.json` 각 항목에 `rationale` 객체 추가
 - `kisa_reference`: 침해사고 분석절차 안내서 해당절 인용
 - `mitre_techniques`: T1078.004 등 ATT&CK 매핑
 - `google_cloud_ref`: 1.5.1 등 카테고리 인용
 - `nist_evidence_type`: NIST SP 800-86 3.1 휘발성 계층
 - `use_case`: 한 줄 활용 시나리오
 2. `data/attack_rules/rules.json` 22 룰에 `rationale.mitre_url` + `kisa_reference` 추가
 3. `data/mapping_rules/{ncp,nhn}_*.json` 의 `source_doc` 필드 보강
 4. `frontend/src/views/V1_Setup/Step3_GuideChecklist.tsx` 각 항목 옆에 출처 칩 추가 (작은 UI 변경)
 5. `docs/근거_매핑.md` 신규 — 시드 ↔ 외부 표준 매핑 표
- 제약: 기존 코드 로직·시드 구조 변경 금지. 메타 추가만.
- PR base: `dev` (또는 새 personal feature 브랜치 → dev)

**Track B — `dev2` 브랜치: 외부 표준 기반 신규 가이드 시스템 재설계**

- 담당: 김병우 (sasumm25-lab) — 다른 계정/PC에서 이어서 작업 예정
- 목표: Google Cloud 9 카테고리 + MITRE Kill Chain + KISA 점검표를 채택해 가이드 시스템 자체를 재설계
- 청사진: [`docs/신규_수집가이드_설계.md`](docs/신규_수집가이드_설계.md) ([`102f3c0`](https://github.com/sasumm25-lab/cloud/commit/102f3c0), dev2 브랜치)
- Phase A~H 작업 정의 완료 (총 18~24h)
- 핵심 차이 (vs Track A):
 - 시드 단위: 사고유형 × CSP (5건) → 카테고리 × 다대다 매핑 (40~50건)
 - 가이드 입력: incident_type+csp 두 필드 → system_config 전체 동적 반영
 - 우선순위: 임의 → NIST 휘발성 계층
 - API: `GET /api/guide/v2` 신규 (기존 `/api/guide` 병행 유지)
 - UI: 단순 체크리스트 → Kill Chain 단계 매트릭스 + 출처 칩
- 충돌 회피: 별도 디렉토리 `collection_targets_v2/` + 별도 모듈 `collection_guide_v2.py` + 별도 컴포넌트 `Step3_GuideChecklist_V2.tsx`
- PR base: `dev2` → 양 트랙 비교 후 결정

**머지·채택 결정 (김병우)**

두 트랙 PR이 모두 완성되면 다음 기준으로 비교:
- 학술 변호 강도 / 시연 임팩트 / 개발 비용 / 기존 시스템 호환성 / 시드 가짓수 / 확장성
- 단일 채택 or 하이브리드 (v2 매트릭스 + v1 rationale 메타 둘 다)

**현재 진행 상황**:
- ✅ KISA 침해사고 분석절차 안내서 PDF (제2010-8호, 168 페이지) — 김병우 PC 로컬 확보
- ✅ MITRE ATT&CK Cloud Matrix v14 14 전술 매핑 확보
- ✅ Google Cloud Threat Intel 9 로그 카테고리 본문 추출
- ✅ NIST SP 800-86 휘발성 계층 / ISO 27037 4단계 / CSA Top Threats 11종 개요 확보
- ⏳ KrCERT "정보통신분야 침해사고 대응 안내서 개정본 (2025-08)" — 페이지에 다운로드 링크 없음, 다른 경로 필요
- ⏳ Ollama llama3.1:8b 다운로드 (87 KB/s, 20% / 12h — 사용자 PC 네트워크 제약)

### 2026-05-14 (저녁) — 합성 raw 로그 생성기 + 시연 노트북 대응 (브랜치: `easy`)

실 raw 로그(NCP 81 + NHN 147)는 김병우 PC에만 있고 민감 정보(이메일·UUID·세션쿠키)라 git 공유 불가. 시연 노트북·다른 팀원 환경·CI 에서도 V-2 업로드 → 풀 파이프라인이 동작하도록 합성 raw 로그 생성기를 추가.

1. **`scripts/synthesize_logs.py`** — CLI 합성기
 - 4종 시나리오: `ncp_none` · `ncp_collection` · `nhn_none` · `nhn_collection`
 - `data/mapping_rules` · `data/attack_rules` · `core/ingestion/matchers.py` 와 100% 호환되는 raw 스키마 생성
 - Kill Chain 시뮬레이션: Initial Access(brute-force) → Persistence(자격증명) → Lateral Movement → Exfiltration → Impact → 흔적 제거
 - 공격자 IP `115.91.214.5` 공유 — 실 raw에서 관찰된 멀티 CSP 연계 패턴 유지
 - NCP eventTime 두 형식(Unix ms + 'YYYY-MM-DD HH:MM:SS UTC') 의도적으로 혼합 → 파서 강건성 검증
 - `--seed` 옵션으로 재현성 보장
2. **`data/synthetic/*.json` 4개 커밋** — 시연자가 즉시 사용 가능
3. **`scripts/verify_synthetic.py`** — 4개 시나리오를 dev 풀 파이프라인(case→upload→normalize→map→gap)에 통과시켜 기대값(NONE/COLLECTION) 자동 단언
4. **검증 결과** (2026-05-14):
 - `ncp_none`: 16건 적재 → IAM-001~005 5/5 매칭 → 정규화 100% → ATT&CK 16/16 → **NONE, 100%** ✅
 - `ncp_collection`: 14건 → IAM-001/002/004/005 → 정규화 100% → ATT&CK 14/14 → **COLLECTION, CT-NCP-IAM-003 missing** ✅
 - `nhn_none`: 16건 → IAM-001~005 5/5 → 정규화 100% → ATT&CK 13/16 (org/project.selected 등은 attack_rules에 없음 — 정상) → **NONE, 100%** ✅
 - `nhn_collection`: 15건 → IAM-001/003/004/005 → 정규화 100% → ATT&CK 13/15 → **COLLECTION, CT-NHN-IAM-002 missing** ✅
5. **`docs/시연_체크리스트.md`** — "테스트 데이터" 섹션을 A(합성, 저장소 포함) / B(실 raw, 별도 전달) 2단계로 재편

### 2026-05-14 (시연 리허설 대응) — UX 안정화 3건 (브랜치: `geunhyung`)

`docs/시연_체크리스트.md` 5 "흔한 버그 후보" 중 코드 수정으로 명확히 개선 가능한 3건을 한 PR 로 묶어 처리. 시연 직전 발견 확률 높은 영역.

1. **`useCaseStore` localStorage 영속화** — caseId / csp / incidentType / severity / currentStep 가 새로고침 / 탭 이동 / 브라우저 재시작 후에도 유지. `zustand/middleware` 의 `persist` 사용 (store name: `ai-sherpa-case`, version 1, `partialize` 로 액션 함수 제외). 체크리스트 5 "V-1→V-2 caseId 전달" 이슈 대응.
2. **`useSherpaStore` 영속화** — sessionId + messages 영속화 (open 토글은 휘발 — 새로고침 시 닫혀 있는 게 자연). `onRehydrateStorage` 로 message id seq 충돌 방지. 체크리스트 5 "V-8 sessionId 새로고침 시 사라짐" 대응. 백엔드 서버 재시작 시 sessionId 유효하지 않으면 백엔드가 새 세션을 응답하므로 자동 복구됨.
3. **V-7 `beforeunload` 경고** — dirty Set 이 비어있지 않을 때만 페이지 떠나기 confirm 다이얼로그. `useEffect` cleanup 으로 누수 방지. 체크리스트 5 "V-7 dirty 추적 — 페이지 떠나기 전 미저장 변경 경고 없음" 대응.

검증: `tsc -b && vite build` 통과 (186 modules — persist 미들웨어 +1).

### 2026-05-14 (심야) — V-7 보고서 프론트 실 API 전환 (브랜치: `byungwoo`)

walking-skeleton의 마지막 mock 화면 제거. V-7 첫 진입 시 자동 초안 생성 → 8섹션 편집 → 저장/최종화/DOCX 다운로드까지 풀 흐름이 백엔드 4 엔드포인트와 통신. ([`2e79193`](https://github.com/sasumm25-lab/cloud/commit/2e79193))

1. **`api/report.ts` 신규** — `createReport / getReport / patchReport / downloadReportDocx` 4개. `downloadReportDocx` 는 `responseType: 'blob'` + `a[download]` 트리거로 파일 저장.
2. **`V7_Report/index.tsx` 전면 재작성**
 - caseId 가드 (V-2~V-5 패턴)
 - 첫 진입 시 `createReport(regenerate=false)` 자동 호출 → 8섹션 자동 초안 (`useQuery` 로 멱등 활용)
 - 섹션 6→8 확장: `evidence` + `comments` 추가 (백엔드 `ReportSections` 와 1:1)
 - **dirty 추적**: `Set<keyof ReportSections>` 로 편집된 섹션만 PATCH → 다른 섹션 덮어쓰기 방지
 - 서버 응답 갱신 시 dirty 한 필드는 보존, 나머지만 동기화
 - 버튼 4종: **AI 초안 재생성** / **저장(N)** / **DOCX** / **최종화**
 · 최종화 후 textarea readonly + 모든 편집 버튼 비활성
 · 미저장 변경 있으면 최종화 비활성 (안전 가드)
 - 상태 배지(draft 파랑 · edited 호박 · finalized 청록) + 백엔드 응답 패널 (V-2~6 동일 스타일)
3. **검증**: `tsc -b && vite build` 통과 (185 modules — `api/report.ts` 1 모듈 증가).

이로써 **walking-skeleton 8/8 화면이 모두 실 API 통신** 상태. 남은 mock 없음.

### 2026-05-14 (밤) — V-5 AI 브리핑 카드 실 API 연결 (브랜치: `byungwoo`)

V-5 우측 패널에 "[Layer 3 미구현 — mock 표시 중]" 라벨로 남아 있던 마지막 mock 영역 제거. ([`68751a4`](https://github.com/sasumm25-lab/cloud/commit/68751a4))

1. **`useQuery(postBrief)`** — 선택된 `boardNode.attack_id` 또는 `activeAttack.attack_id` 기준. 둘 다 없으면 eventId 미지정 → 백엔드가 케이스 최상위 위험도 attack 자동 선택. `queryKey` 에 attack_id 포함 → 선택 바뀔 때마다 자동 재호출. `staleTime` 5분.
2. **`BriefingPanel` 컴포넌트** (파일 하단) — 로딩/에러/빈 케이스/정상 4가지 상태. `technique_id` + `tactic` 배지, 신뢰도(low/medium/high) 색상 분기, `sources` 칩(ATTACK 보라 · PLAYBOOK 청록 · CSP_DOC 파랑 · CASE_DB 황색), `relatedTechniques` 표시.
3. 백엔드 응답 패널에 `sherpa 로딩/에러/✓` 상태 칩 추가.

### 2026-05-14 (밤) — Layer 3 미세 이슈 정정 (브랜치: `byungwoo`)

1차 코드의 일관성·정합성 문제 2건 수정. ([`8e60c66`](https://github.com/sasumm25-lab/cloud/commit/8e60c66))

1. **HTTP 404 일관성** — `intake/board/report.py` 의 `_case_not_found()` 헬퍼 패턴을 `sherpa.py` 에도 도입. brief/suggest/playbook 에서 caseId 존재 검증 후 없으면 `HTTPException(404, code=CASE_NOT_FOUND)`. 기존엔 HTTP 200 + `{status:error}` 를 반환해 다른 라우터와 응답 형식이 달랐음.
2. **`ChatRequest.history` 활용** — `AISherpa.chat` 이 history 파라미터를 받기만 하고 사용하지 않던 문제 해결. `session_id` 가 신규(빈 세션)일 때 history 를 `ChatSession` 에 미리 채워넣음 → 설계서 5.1절 "클라이언트가 history 배열을 매번 전달하여 컨텍스트를 유지한다(stateless 설계)" 정합. 기존 세션이면 무시(멱등성).

### 2026-05-14 (밤) — V-8 셰르파 채팅 실 API + 출처 칩 (브랜치: `byungwoo`)

walking-skeleton 중요한 한 조각. 채팅 입력 → `POST /api/sherpa/chat` 호출 → 출처 청크를 색상 칩으로 시각화. ([`7210699`](https://github.com/sasumm25-lab/cloud/commit/7210699))

1. **`types/index.ts`** — `SherpaSource / ChatRequest / SuggestRequest·Response / PlaybookRequest·Response / KbStatsResponse / KbEngineHealth` 타입군 추가.
2. **`api/sherpa.ts` 신규** — `postBrief / postChat / postSuggest / postPlaybook / getKbStats` 5개 래퍼.
3. **`stores/useSherpaStore.ts`** — `sessionId` 상태 + `sources` 필드 추가, `reset` 액션.
4. **`V8_Sherpa/index.tsx` 전면 재작성**
 - 정적 KB 카운트(`623·412…`) 제거 → `useQuery(getKbStats)` 실 통계
 - 채팅 입력 → `useMutation(postChat)` → 응답 `sources` 를 KB_TONE 색상 칩으로 렌더
 - 첫 응답의 `sessionId` 를 zustand에 저장해 후속 질의 재사용 (stateful)
 - 빠른 질의 3종: `T1078.004` · `NCP Tracer 보존` · `데이터 유출 플레이북`
 - `engine.engine === 'stub'` 일 때 "stub" 배지 + 안내 문구
 - 백엔드 응답 패널 (V-2~6 동일 스타일)
 - "AI는 판단하지 않습니다" 활용 안내 카드

### 2026-05-14 (밤) — Layer 3 AI 셰르파 백엔드 1차 (브랜치: `byungwoo`)

PROGRESS.md 권장(Ollama/ChromaDB 없이 mock 깡통으로 흐름 검증)에 따라, ChromaDB·Ollama 의존성 없이 동작하는 1차 스캐폴딩 구현. 인터페이스(`generate` / `retrieve`)는 실 모델 교체 시 그대로 사용 가능하도록 추상화. ([`6ce6e6f`](https://github.com/sasumm25-lab/cloud/commit/6ce6e6f), 643줄)

1. **`core/sherpa/knowledge_base.py`** — KB 4종(`attack/playbook/csp_doc/case_db.json`) 로더. 통일 형식 `KBChunk(chunk_id, kb_name, title, text, source, url, meta)` 로 변환·캐시. `case_db` 는 timeline / lessons_learned / evidence 를 텍스트로 풀어서 청크화.
2. **`core/sherpa/rag_retriever.py`** — 키워드 매칭 + 점수화 기반 `retrieve(query, k, kb_filter?)`. 토큰화는 영문/숫자/한글/.·_ 기준 ≥2자, 점수는 출현 횟수 × 길이 가중치. `retrieve_by_technique(technique_id)` 는 메타 직매칭 우선 + 키워드 fallback.
3. **`core/sherpa/llm_engine.py`** — 템플릿 기반 `generate(prompt, context)`. context 청크를 인용한 응답 + "수사관께서 직접 판단" 문구. `health()` 가 `engine: stub` 을 반환해 프론트에서 깡통 모드 표시.
4. **`core/sherpa/chat_session.py`** — 인메모리 세션 저장소. `get_or_create / append / history`.
5. **`core/sherpa/ai_sherpa.py`** — `AISherpa` 4가지 역할
 - `brief(case_id, event_id?)` — `attack_events ⋈ ocsf_events ⋈ raw_events` 조인으로 case 최상위 위험도 attack 자동 선택, technique_id 기반 KB 검색, 출처 첨부
 - `chat(case_id, session_id, query, history?)` — RAG retrieve(k=3) + LLM generate + 세션 누적
 - `suggest_missing_link(case_id, node_a, node_b)` — case 내 다른 기법을 위험도순으로 추천 (깡통)
 - `recommend_playbook(chain)` — PLAYBOOK 카테고리 KB 검색 (깡통)
6. **`api/sherpa.py`** — 5개 엔드포인트
 - `POST /api/sherpa/brief|chat|suggest|playbook`
 - `GET /api/sherpa/kb` (V-8 우측 패널용 KB 인덱스 통계 + engine.health)
7. **`main.py`** — `sherpa_router` 등록 (이근형의 `board_router/report_router` 와 함께).

설계 원칙 준수: 모든 응답에 `sources` 첨부, brief 에 `confidence` 필드, AI 가 결정·판단하지 않음. AST 문법 검증 6/6 통과.

### 2026-05-14 (오전) — 협업 인프라 정비 (브랜치: 직접 dev 커밋)

팀원 4명이 각자 다른 AI 도구로 작업해도 머지 충돌이 안 나도록 협업 운영 레이어 보강. ([`1cb94e4`](https://github.com/sasumm25-lab/cloud/commit/1cb94e4))

- `CLAUDE.md` 최상단에 **"🤖 AI 부팅 시퀀스"** 6단계 + **"동시 작업 충돌 회피"** 룰 추가 (선착순 모델, 공유 진입 파일은 추가만)
- `CLAUDE.md` — `Common.User` 제거(설계서 5.1절 MVP 인증 미사용 정합), `chain_nodes.label` 팀 합의 메모
- `README.md` 팀원용 30분 가이드 신설 (clone → AI 도구 연결 → 작업 흐름)
- `docs/설계서_읽는법.md` — 설계서 구조·다이어그램·약어표 가이드 (캡스톤 루트의 원본을 git 안으로 이관)
- `.claude/구현/*.md` 3종 — IncidentType 5종을 설계서 5.2절 기준으로 정정 (`iam-takeover → CREDENTIAL_THEFT` 외)
- `.gitignore` — 팀장 전용 `GIT_SETUP_가이드.md` 차단
- `backend/data/collection_targets/naver_CREDENTIAL_THEFT.json` — 새 enum 시드 추가 (옛 `naver_iam-takeover.json` 은 프론트엔드 enum 마이그레이션 시까지 유지)

### 2026-05-14 (자정 이후) — Layer 4 보고서 백엔드 1차 (브랜치: `geunhyung`)

V-7 프론트는 mock UI 만 있었고 백엔드는 미구현 상태였음. 보고서 초안 자동 생성 + JSON 영속화 + DOCX 내보내기까지 한 번에 구현.

1. **`config.py`** — `REPORTS_DIR` (data/reports), `EXPORTS_DIR` (exports) 추가, 자동 mkdir
2. **`.gitignore`** — `backend/data/reports/*.json`, `backend/exports/` 추가
3. **`core/board/report_generator.py`** — ReportGenerator
 - `generate_draft(db, case_id)`: case/raw/ocsf/attack/gap/chain 데이터를 종합해 **8 섹션 자동 초안** (overview/timeline/impact/attack_analysis/response/recommendation/evidence/comments)
 · 타임라인: OCSF 시간순 상위 20건
 · attack 집계: technique별 count + max_risk_score
 · 증거: collection_targets 카탈로그 vs 실제 matched_target_id 비교 (✓/✗ 마킹)
 · 권고: gap_type 별 분기 (COLLECTION → Layer 0 복귀 등)
 - JSON 영속화: `data/reports/{caseId}.json` (load/save/get_or_create/update_sections)
 - DOCX 내보내기: `python-docx`로 `exports/{caseId}.docx` 생성 (8 섹션 헤딩 + 본문)
4. **`api/report.py`** — 4개 엔드포인트
 - `POST /api/report` (regenerate 옵션) — 초안 생성, 응답에 8섹션 dict
 - `GET /api/report/{case_id}` — 저장된 보고서 조회
 - `PATCH /api/report/{case_id}` — sections 부분 갱신 + status 변경. `EDIT_REPORT` / `FINALIZE_REPORT` action_logs 자동 적재
 - `GET /api/report/{case_id}/export?format=docx` — `FileResponse` 다운로드. `EXPORT_REPORT` action_logs 적재. PDF 는 501 NotImplemented
5. **`main.py`** — `report_router` 등록
6. **검증** — AST syntax check 4/4 통과

응답 형식은 **frontend types/index.ts `ReportResponse / ReportSections` 와 8 섹션 키 1:1 일치**. V-7 프론트는 mock → 실 API 전환 시 타입 그대로 사용 가능.

PDF 내보내기는 LibreOffice 또는 wkhtmltopdf 의존성이 커서 후속 작업으로 미룸 (501 응답).

### 2026-05-14 (자정 무렵) — V-6 ATT&CK 히트맵 실 API 전환 (브랜치: `geunhyung`)

attack_events 데이터를 동적 집계해서 ATT&CK Cloud Matrix 형태로 시각화. 기존 mock(7기법 6전술 하드코딩) 폐기.

1. **`views/V6_Attack/index.tsx` 전면 재작성**
 - `useQuery(getAttack, page, 100)` — 한 페이지 100건 페이지네이션
 - `useMutation(runMap)` — 상단 "↻ ATT&CK 매핑 실행" 버튼으로 POST `/api/analysis/map` 트리거
 - `aggregate(items)` 함수: `(tactic, technique_id)` 그룹별 `count` + `max_risk_score` 집계
 - 히트맵: 전술 위험도 내림차순 정렬, max_risk 기반 색상 분기 (≥70 red / ≥40 amber / 그 외 blue)
 - 기법 상세 표: count 내림차순, 심각도 자동 분류 (Critical/High/Medium)
 - 백엔드 응답 패널 (V-2~5 동일 스타일): caseId / 페이지 / 기법 종수 / 전술 커버리지
2. **검증**: `tsc -b && vite build` 통과 (183 modules)

walking-skeleton 현황: V-1 → V-2 → V-3 → V-4 → V-5 → V-6 까지 풀 연동. 남은 mock: V-7 보고서 / V-8 셰르파 채팅 (둘 다 Layer 3/4 백엔드 미구현 종속).

### 2026-05-14 (밤) — V-5 수사 보드 프론트 실 API 전환 (브랜치: `geunhyung`)

직전 Layer 4 백엔드를 V-5 프론트와 연결. ATT&CK 매핑 결과 → 보드 노드 추가 → 수락/거부 흐름이 백엔드와 통신.

1. **`api/board.ts` 신규** — `getBoard / createNode / updateNode / createEdge` 4개 함수
2. **`views/V5_Board/index.tsx` 재작성**
 - caseId 가드 (V-2~4 패턴)
 - 백엔드 응답 패널 (chain_nodes / edges / ATT&CK 후보 카운트)
 - 메인 영역: `BoardCanvas` (드래그-드롭 캔버스 — 클라이언트 시각화 보조, 백엔드 미연동 유지)
 · "공격 체인 노드 (chain_nodes)" 카드 — `useQuery(getBoard).nodes` 표시. CONFIRMED/REJECTED 상태별 색상, REJECTED 는 strike-through
 · "ATT&CK 매핑 후보 (top 10)" 카드 — `useQuery(getAttack)` risk_score 내림차순 grid 2열
 - 우측 상세 카드:
 · 보드 노드 선택 시: 라벨/상태/유형/attack_id + ✓ 수락/✗ 거부 버튼 → `useMutation(updateNode)` PATCH (백엔드가 action_logs 자동 적재)
 · ATT&CK 후보 선택 시: 기법/전술/risk/시각 + "+ 보드에 추가" 버튼 → `useMutation(createNode)` POST (label 자동 생성)
 - 중복 추가 방지: `addedAttackIds` 집합으로 이미 보드에 있는 attack 카드는 opacity-60 + 버튼 비활성화
 - AI 셰르파 브리핑 카드는 "[Layer 3 미구현 — mock 표시 중]" 라벨로 명시
3. **검증** — `tsc -b && vite build` 통과 (184 modules)

walking-skeleton 현황: V-1 → V-2 → V-3 → V-4 → V-5 노드 패널까지 풀 연동. 남은 mock: V-6 ATT&CK 히트맵 / V-7 보고서 / V-8 셰르파 채팅.

### 2026-05-14 (밤) — Layer 4 수사 보드 백엔드 1차 (브랜치: `geunhyung`)

V-5 프론트는 mock 으로 작성되어 있었으나 백엔드가 미구현이어서 실 데이터 흐름이 막혀 있었음. Layer 4 의 노드/엣지 CRUD 4개 엔드포인트를 추가해 흐름을 뚫음.

> 참고: V-3/V-4 mock → 실 API 전환을 김병우(byungwoo)와 이근형이 동시 진행했고, 김병우 거(`e7da3ab`)가 dev 에 먼저 머지되어 그 거를 정답으로 채택. 이근형의 V-3/V-4 작업분(`87478ad`)은 폐기, Layer 4 백엔드 + V-5 프론트만 dev 위에 cherry-pick. `backup/2gu-before-dev-rebase` 태그에 폐기 전 상태 보존. 그리고 협업 공지에 맞춰 브랜치 이름 `2gu` → `geunhyung` 으로 변경.

1. **`core/board/chain.py`** — ChainNode / ChainEdge 도메인 객체
 - `ChainNode.create` — attack_id 옵셔널(AI 후보 노드는 NULL), 기본 status=CONFIRMED
 - `ChainNode.update` — status·pos·label 부분 갱신
 - `ChainNode.serialize` — frontend `BoardNode` 와 동일 형식 (snake_case, pos 기본 0)
 - `ChainNode.derive_label_from_attack` — attack_id 주어지면 `"T1078.004 · Initial Access"` 형태 라벨 자동 생성
 - `ChainEdge.create / serialize` — `BoardEdge` 형식
2. **`core/board/investigation_board.py`** — case 단위 집계
 - `get_state(case_id)` — nodes + edges 직렬화, case 미존재 시 None
 - `validate_edge` — self-loop 금지 + 노드 존재성 + 같은 case 소속 검증
3. **`api/board.py`** — 4개 엔드포인트
 - `POST /api/board/nodes` — attack_id 유효성 검증, label 미지정 시 자동 생성
 - `PATCH /api/board/nodes/{node_id}` — status 변경 시 `action_logs` 에 ACCEPT/REJECT 자동 적재 (CLAUDE.md actor='investigator')
 - `POST /api/board/edges` — `validate_edge` 통과해야 생성
 - `GET /api/board?caseId=` — `BoardResponse` 반환
4. **`main.py`** — `board_router` 등록
5. **검증** — AST syntax check 4/4 통과. DB E2E 는 다음 작업.

응답 형식은 **frontend `types/index.ts` 의 `BoardNode/BoardEdge/BoardResponse` 와 정확히 일치**하도록 작성. V-5 프론트는 mock → 실 API 전환 시 타입만 가져다 쓰면 됨.

### 2026-05-14 (저녁) — V3 OCSF + V4 Gap 실 API 연결 (브랜치: `byungwoo` → `dev` 머지)

Layer 2 백엔드와 V3/V4 위저드를 연결. **V1 → V2 → V3 → V4 풀 흐름**이 mock 없이 동작.

1. `types/index.ts`: OCSFEventItem 평탄화·AttackEventItem 갱신·NormalizeStats/MapStats/GapResultResponse/PaginatedData<T> 추가
2. `api/analysis.ts` 신규: `runNormalize / getOcsf / runMap / getAttack / runGap` (5종)
3. **V3 OCSF 재작성** ([`e7da3ab`](https://github.com/sasumm25-lab/cloud/commit/e7da3ab))
 - 「정규화 실행」 버튼 → `POST /api/analysis/normalize` (useMutation)
 - `GET /api/analysis/ocsf` 페이지네이션 + 샘플 selector 10개
 - 좌측 `unmapped_raw` (원본 JSON) / 우측 OCSF 평탄화 컬럼 양면 비교
 - FieldMappingTable: 시드 mapping_rules 핵심 매핑 정적 표
4. **V4 Gap 재작성**
 - 「갭 감지 실행」 버튼 → `POST /api/analysis/gap`
 - gap_type 4종 별 색·아이콘·메시지 + 조건부 CTA (COLLECTION→Layer 0, NONE→보드, INTERPRETATION→AI 셰르파)
 - completionRate 도넛 + missing 항목 리스트
5. `backend/config.py`: CORS_ORIGINS 에 `http://localhost:5174` 추가 (Vite 충돌 시 자동 fallback 대응)
6. **E2E 검증 완료**:
 - NCP 시나리오: V1→V2(81건 업로드)→V3(정규화 100%)→V4('NONE', 100%)
 - NHN 시나리오: V1→V2(147건)→V3(100%)→V4('COLLECTION', 66.67%, CT-NHN-IAM-002 미수집 정확히 짚음)

### 2026-05-14 (오후) — Layer 2 백엔드 1차 완성 (브랜치: `byungwoo` → `dev` 머지)

Layer 2 분석 파이프라인 3종 + API 5개를 구현. **시드 mapping_rules와 attack_rules 22룰이 드디어 코드에 연결**되어 실제 raw 로그가 OCSF → ATT&CK → 갭으로 흐름.

1. **`core/analysis/ocsf_normalizer.py`** ([`f7a0123`](https://github.com/sasumm25-lab/cloud/commit/f7a0123))
 - CSP별 mapping rule JSON 로딩·캐시 (`naver` → ncp_cloudtrail, `nhn` → nhn_cloud_trail)
 - field_mappings dot 표기 nested 접근 (`content.actionUserName` 등)
 - value_transforms: datetime 이중 형식(unix_ms / iso8601 / UTC 문자열), SUCCESS/FAIL → 200/500
 - 중복 정규화 skip (`event_id` UNIQUE 제약 활용)
 - 원본 JSON 전체를 `unmapped_raw` 에 보존
2. **`core/analysis/attack_mapper.py`** — attack_rules 22룰 로딩(정규식 사전 컴파일), csp 필터 + activity_name_pattern 매칭, 다중 매칭 시 base_risk_score 최댓값 룰 선택
3. **`core/analysis/gap_detector.py`** — required/collected/mapped 비교 → COLLECTION/EVIDENCE/INTERPRETATION/NONE 분류, completionRate 계산
4. **`api/analysis.py`** 5개 엔드포인트 (POST normalize · GET ocsf · POST map · GET attack · POST gap), `main.py` 등록
5. **E2E 검증 결과**:
 - NCP 81건 + NHN 147건 정규화율 100% (failed 0)
 - ATT&CK 매핑 76건 (NCP 45 / NHN 31) — R-NCP-007 Exfiltration 9건, R-NHN-002 Privilege Escalation 10건 등
 - 갭 판정: **NCP 'NONE'** (수사 보드 진행), **NHN 'COLLECTION'** (CT-NHN-IAM-002 미수집 — 권한 변경 이벤트가 raw에 없음을 정확히 짚어냄)

### 2026-05-14 (오전) — Layer 1 DB E2E 검증 + V2 실 API 연결 (브랜치: `byungwoo` → `dev` 머지)

walking-skeleton의 두 번째 고리(V1 → V2)가 mock 없이 실제 DB와 통신하는 형태로 완성. 진행 순서:

1. **Layer 1 백엔드 DB 적재 E2E 검증** (이근형의 [`35eba2b`](https://github.com/sasumm25-lab/cloud/commit/35eba2b) 코드 사용)
 - NCP `activity_logs_full.json` 81건 + NHN `nhn_activity_logs.json` 147건 = **총 228건 raw_events 적재**
 - SHA-256 해시 무결성 일치 (파일 실제 해시 = API 응답)
 - `matched_target_id` 시드 카탈로그와 정확 매칭
 · NCP: CT-NCP-IAM-001~005 모두 매칭 (12/3/2/13/37건)
 · NHN: CT-NHN-IAM-001/003/004/005 매칭 (25/6/15/8건)
 - 페이지네이션 + 단건 조회(raw 포함) + 404 케이스 정상
 - 이근형 브랜치 `origin/2gu` → `dev` 머지 ([`375265c`](https://github.com/sasumm25-lab/cloud/commit/375265c))

2. **V2 프론트엔드 mock → 실 API 전환** ([`8034de1`](https://github.com/sasumm25-lab/cloud/commit/8034de1))
 - `types/index.ts`: `RawEventItem` 백엔드 응답 형식(camelCase)과 일치. `IngestionStats` / `LogsListData` 타입 추가
 - `api/logs.ts` 신규: `uploadLogs(multipart)` / `getLogs(페이지네이션)` / `getEvent` 3개 함수
 - `views/V2_Logs/index.tsx` 대대적 재작성
 · mock 초기 데이터 제거
 · `useCaseStore.caseId` 미존재 시 V-1 안내 패널 (라우트 가드)
 · `useMutation` → `uploadLogs` (성공 시 `invalidate('logs')` → 자동 리프레시)
 · `useQuery` → `getLogs(page, pageSize=20)` + 페이지 이동 버튼
 · "백엔드 응답 ✓" 패널 (caseId / total / 마지막 업로드 stats / sha256)
 · "매칭 분포" 패널 (`byTarget` 동적 표시)
 · KPI 4개 실 데이터화 (총 raw_events / matched / unmatched / 파일)
 - `EventPreviewTable.tsx`: `id` 타입 `number → string` (UUID 대응)
 - 브라우저 E2E 검증 완료

3. **협업 워크플로 정착**
 - feature 브랜치 기반 협업 도입. 각자 사람 이름 브랜치 사용:
 · 김병우 → `byungwoo`, 이근형 → `2gu`, 최진규 → `jingyu`, 이지호 → `easy` (추정)
 - `feat/<기능>` 패턴은 일회성 작업용. 장기 작업은 personal branch + 작업 단위 PR → dev 머지

### 2026-05-13 — Layer 1 로그 수집 백엔드 1차 구현 (브랜치: `2gu`)

Layer 1 백엔드 골격을 코드로 구현. DB 적재 E2E 검증은 다음 작업에서 수행 예정.

1. **`core/ingestion/parsers/ncp.py`** — NCP Cloud Activity Tracer 파서
 - `eventTime` 양식 두 가지(Tracer Export Unix ms / 콘솔 "YYYY-MM-DD HH:MM:SS UTC") 모두 처리
 - BOM 강건성 (`utf-8-sig` 디코딩) — Tracer Export 파일 BOM 케이스 대비
 - 매칭에 필요한 필드만 평탄화(`action`, `product_name`, `actor_user_name`, `source_ip`, `event_time`, `result`), 원본은 `raw` 키로 보존
2. **`core/ingestion/parsers/nhn.py`** — NHN Cloud Trail 파서
 - ISO8601 `+0900` 포맷 처리, tz-aware → naive UTC 통일 (DB 컬럼이 naive 라 시스템 timezone 의존 제거)
3. **`core/ingestion/matchers.py`** — collection_targets 매칭 룰 (DB 의존성 없는 순수 함수)
 - NCP CREDENTIAL_THEFT: action/product 키워드로 IAM-001~005 분류
 - NHN CREDENTIAL_THEFT: `event_id.` prefix Regex 로 IAM-001~005 분류
 - `(csp, incident_type) → matcher fn` 레지스트리 패턴 → 향후 5종×2CSP 확장 시 함수만 추가
4. **`core/ingestion/log_ingestor.py`** — 통합 파이프라인
 - `verify_hash(content)` SHA-256
 - `parse(csp, content)` — case.csp 별 파서 디스패치 (`all` 일 때 NCP→NHN 순차 시도)
 - `ingest(db, case, filename, content)` — 파싱·매칭·`raw_events` bulk insert, `IngestionStats` 반환 (`totalEvents/matched/unmatched/byTarget/sha256/sourceFile`)
 - `list_events(...)`, `get_event(...)` 조회 헬퍼
 - 시드에 없는 target_id 매칭 시 unmatched 로 강등 (DB 정합성 보호)
5. **`api/ingestion.py`** — 3개 엔드포인트
 - `POST /api/logs/upload` — multipart (caseId + file)
 - `GET /api/logs?caseId=&page=&pageSize=`
 - `GET /api/logs/{eventId}` — 원본 raw JSON 포함
6. **`main.py`** — `ingestion_router` 등록
7. **단위 smoke test 통과** — 동적 합성 raw 6건 × 2 CSP 로 파서 변환 + 매처 분류 검증. 각 CSP 5/5 target 정확 분류, 미지원 케이스 None 반환.
8. **문서 동기화** — 체크리스트 1-2 (Layer 0, stale 이었음) + 2-1 (Layer 1 신규) 업데이트.

**남은 검증** (다음 작업):
- backend `.venv` 만들고 `python -m db.init_db` → uvicorn 띄워서 Swagger UI 에서 실제 NCP/NHN raw 파일 업로드 → `raw_events` 적재 + 매칭 결과 확인
- 빈 파일·잘못된 형식·존재하지 않는 caseId 등 에러 케이스 동작 확인
- V2 프론트엔드 mock → 실 API 전환 (`api/logs.ts` 신규 작성)

### 2026-05-12 — Phase 1 완성: 시드 + Layer 0 백엔드 + V1 실 연동

오늘의 변경은 walking-skeleton의 첫 번째 고리(사고 접수 → 수집 가이드)를 **mock이 아닌 진짜로** 동작하게 만든 작업입니다. 진행 순서대로:

1. **DB 스키마 정렬** ([`95df4b9`](https://github.com/sasumm25-lab/cloud/commit/95df4b9)) — `db/models.py` 9개 테이블을 설계서 5.2절 컬럼 명세에 100% 정렬. 평탄화 OCSF, `attack_events.ocsf_id` UQ, `action_logs.actor` 추가 등. `chain_nodes.label`만 팀 합의로 1컬럼 유지.
2. **체크리스트 동기화** ([`596ef30`](https://github.com/sasumm25-lab/cloud/commit/596ef30)) — 실제 코드 상태와 `.claude/구현/구현_체크리스트.md` 맞춤. 프론트 V1-V8 = `[x]`, 백엔드 API = `[ ]`.
3. **시드 데이터 v1** — NCP/NHN × CREDENTIAL_THEFT MVP 분량 JSON 7개 작성, 임시 `MVP_minimal` 메타 박음.
4. **공식 가이드 기반 정정** — `WebSearch` + `WebFetch`로 NCP Cloud Activity Tracer 가이드 + NHN Cloud Trail 가이드 정본 확보. 시드의 추정치를 모두 공식 필드명·서비스명·운영 정보(보존 90일 / 변조 감지 / 2.5시간 업로드 지연 등)로 교체.
5. **실제 raw log 발견** — `C:/Users/sasum/activity_logs_full.json` (NCP 81건) + `nhn_activity_logs.json` (NHN 147건). HTML 분석본의 분석 대상 원본이었음. NCP attack-sim 11건 + NHN attack 36건 Kill Chain 시뮬레이션 확인. 두 계정이 **동일 외부 IP 115.91.214.5 공유** → 멀티 CSP 연계 시나리오 검증.
6. **시드 v2 — 실제 raw 기반 재작성** ([`1c2d59d`](https://github.com/sasumm25-lab/cloud/commit/1c2d59d))
 - `mapping_rules/ncp_cloudtrail.json` — `action`/`actionResultType`/`content.actionUserName`/`content.sourceIp`로 정정. `eventTime`은 Unix ms(Export) + UTC 문자열(콘솔) 이중 형식.
 - `mapping_rules/nhn_cloud_trail.json` — 구 `nhn_cloud_audit.json` 폐기. `eventId`/`userName`/`userIp`/`result` 매핑.
 - `attack_rules/rules.json` — NCP 11룰 + NHN 11룰 = **22개**. 모든 룰의 `activity_name_pattern`이 raw log에 실제 등장하는 값에 매칭됨. 각 룰에 `real_log_count` + 출처 명시.
 - `collection_targets/` — `retention_days=90`, `storage_path` 채움. NHN은 "Cloud Trail"로 서비스명 통일. 구 `naver_iam-takeover.json` 삭제.
 - `kb/case_db.json` — 실제 시뮬 타임라인 3개 사례: NCP attack-sim 11건 (2시간 Kill Chain), NHN attack 36건 (20시간 Kill Chain), 멀티 CSP 연계 의심.
7. **모듈별 명세 정정** ([`cbd83e1`](https://github.com/sasumm25-lab/cloud/commit/cbd83e1)) — `모듈별_구현_명세.md` 80~87줄의 NCP 매핑 예시가 AWS CloudTrail 스키마였음. 실제 NCP/NHN 두 예시로 교체.
8. **Layer 0 API 구현** ([`4bc5582`](https://github.com/sasumm25-lab/cloud/commit/4bc5582))
 - `core/intake/incident_case.py` — `IncidentCase` (CRUD)
 - `core/intake/collection_guide.py` — `CollectionGuide.generate()` (priority 내림차순 + completionRate 계산)
 - `core/intake/knowledge.py` — `IncidentTypeKnowledge.lookup()` (5종 사고유형별 ATT&CK·서비스 매핑, 하드코딩)
 - `api/intake.py` — FastAPI 라우터 4개 (POST/GET/PATCH `/api/cases` + GET `/api/guide`). Pydantic `Literal`로 enum 검증, 응답은 `{"status":"ok","data":...}` envelope.
 - `main.py` — `intake_router` 등록.
 - `requirements.txt` — Python 3.14 호환을 위해 `pydantic>=2.10` 상향, 핀 형식 `>=`로 완화.
 - **E2E 검증**: POST → GET → PATCH → GET `/api/guide` + 404 케이스 동작 확인. SQLite `ai_sherpa.db` 생성 + 시드 10건 적재 확인.
9. **incidentType enum 5종 통일 + V1 실 연동** ([`04638b4`](https://github.com/sasumm25-lab/cloud/commit/04638b4))
 - 프론트가 옛 명칭(`iam-takeover/credential/webapp/insider/ransomware`)을 쓰고 있어 백엔드 검증 실패. 모든 프론트 코드를 백엔드 5종(`CREDENTIAL_THEFT/PRIVILEGE_ESCALATION/DATA_EXFILTRATION/AUDIT_LOG_TAMPERING/MULTI_CSP_LATERAL`)으로 통일.
 - `types/index.ts`, `meta.ts`(TYPE_META 재작성), `Step1_TypeCards`(orderedTypes), `Step3_GuideChecklist`(fallback) 일괄.
 - `main.tsx`에 `QueryClientProvider` 추가 (React Query v5).
 - `V1_Setup/index.tsx` Step2 onSubmit에서 `useMutation` → `createCase`. 성공 시 진짜 UUID를 `useCaseStore.setCaseId`에 저장 + 자동 Step3 진입.
 - `Step3_GuideChecklist`에 `useQuery` → `getGuide(caseId)`. 화면 상단에 "백엔드 응답 ✓ / caseId / 수집 대상 N건 / 칩 5개" 패널 추가.
 - 브라우저 E2E 검증 완료: V1 → POST `/api/cases` → 진짜 UUID 반환 → Step3에서 `GET /api/guide` 호출 → CT-NCP-IAM-001~005 칩 5개 표시.

### 2026-05-11 — DB 스키마 정렬 + 체크리스트 동기화 (요약)

위 1번·2번의 시작점. 작업 직전 메모리에 적힌 "설계서·models.py 스키마 불일치 다수, 작업 시작 전 합의 필요"를 해소한 단계.

### 2026-05-11 이전 — 프론트엔드 V1-V8 UI + 디자인 시스템 ([`a6e76b7`](https://github.com/sasumm25-lab/cloud/commit/a6e76b7))

이전 세션에서 완료. 디자인 토큰(ink/brand 컬러 + 타이포), 셸 컴포넌트(Header/Sidebar/PageHeader/PageBody/Card/KpiCard/Badge/Toast/SherpaFab), Zustand 스토어 4종, V1-V8 모든 화면. 백엔드 미존재로 전부 mock 데이터.

---

## 다음 할 일

walking-skeleton 8/8 화면이 mock 없이 실 API와 통신하는 상태. 남은 작업은 (a) Layer 3 깡통을 실 sLLM·벡터검색으로 교체, (b) 사고유형 확장, (c) 시연 리허설 세 갈래.

### AI / RAG — Layer 3 실 모델 통합 (우선)

깡통(키워드+점수화+템플릿)을 인터페이스 보존하며 교체:

- [ ] `core/sherpa/embed_kb.py` 신설 — `KBChunk` 를 sentence-transformer 로 임베딩하여 ChromaDB 컬렉션 적재 (startup 1회 또는 CLI 스크립트)
- [ ] `core/sherpa/rag_retriever.py` 교체 — 키워드 매칭 → ChromaDB cosine similarity. `retrieve(query, k)` 시그니처 유지
- [ ] `core/sherpa/llm_engine.py` 교체 — 템플릿 → Ollama `POST /api/generate` 호출. `OLLAMA_BASE_URL` 환경변수, 30초 timeout fallback (SNF-02)
- [ ] `LLMEngine.health()` 가 실 모델 응답 여부를 반환하도록 갱신 → V-8 "stub → connected" 배지 자동 전환
- [ ] `requirements.txt` — `chromadb`, `sentence-transformers`, (필요 시) `httpx` 추가

### 백엔드 — Layer 1 매처 외부화 + 사고유형 확장

- [ ] `core/ingestion/matchers.py` → JSON 룰 외부화 (`data/collection_targets/target_match_rules.json`)
- [ ] 4종 사고유형 매처 추가 (PRIVILEGE_ESCALATION / DATA_EXFILTRATION / AUDIT_LOG_TAMPERING / MULTI_CSP_LATERAL)
- [ ] 사고유형별 시드(`collection_targets/{csp}_{type}.json` 8개 신규)

### 프론트엔드 — 보조 작업

- [ ] V-5 보드 엣지 생성/삭제 UI (현재 `api/board/edges` 백엔드만 존재, 프론트 미연결)
- [ ] V-5 BoardCanvas 드래그앤드롭 → 백엔드 노드 좌표(`pos_x/pos_y`) 영속화
- [ ] V-7 PDF 내보내기 (현재 백엔드 501) — LibreOffice 또는 wkhtmltopdf 의존성 결정 후 구현
- [ ] 4종 추가 사고유형 시드 들어오면 V-1 Step1 카드 UI 갱신

### 통합 테스트 / 데모

- [ ] Phase 2/3 종결 시점 V-1 → V-2 → V-3 → V-4 → V-5 → V-6 → V-7 → V-8 end-to-end 리허설 (NCP + NHN 시나리오 각각)
- [ ] 갭 감지 → Layer 0 복귀 흐름 (V-4 → V-1 라우팅) 동작 확인
- [ ] AI 셰르파 깡통 vs 실 모델 응답 품질 비교 (시연 자료)
- [ ] 오프라인(인터넷 차단) 환경에서 전체 시나리오 동작 확인 (SNF-01)

---

## 알려진 제약 / 이슈

- **실제 raw 로그는 NCP 81건 + NHN 147건 — 양이 적음**. 매핑 룰 일반화 시 false positive/negative 가능. 시연용으로는 충분, 학술적 평가 시에는 "공식 문서 + N건 실증" 한정 명시.
- **민감 정보 포함된 raw 로그가 사용자 홈 디렉토리**에 있음 (이메일·UUID·세션쿠키). git에는 절대 커밋하지 않음. 다른 팀원에게 공유 시 마스킹 필요.
- **AI 셰르파(Layer 3)는 mock 응답으로 시작 권장** — Ollama Llama 3.1 8B + ChromaDB 셋업 시간이 길어서, 우선 mock으로 V8 흐름 검증 후 실 모델로 교체.
- **외부 CDN 사용 금지** (SNF-01, 오프라인 동작 필수): 폰트·아이콘·라이브러리 모두 로컬 번들.
- **AI는 판단/결정 코드 작성 금지**: 검색·요약·제안만. 수락/거부는 항상 수사관 권한.

---

## 작업 환경

### 백엔드 실행
```bash
cd cloud/backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m db.init_db # DB 생성 + 시드 적재
.venv/Scripts/python.exe -m uvicorn main:app --reload
# Swagger UI: http://localhost:8000/docs
```

### 프론트엔드 실행
```bash
cd cloud/frontend
npm install
npm run dev
# http://localhost:5173
```

### 권장 워크플로우
```bash
git switch dev
git pull --rebase origin dev
# (작업)
git status
git add <특정 파일들> # git add . 지양
git commit -m "feat: ..."
git pull --rebase origin dev
git push
```

---

## 커밋 히스토리 (2026-05-14 기준)

```
2e79193 feat(v7): 보고서 편집기 mock → 실 API 전환 — walking-skeleton 100%
(머지) Merge byungwoo into dev — Layer 3 1차 + V-5 brief + V-7·V-8 실 API
68751a4 feat(v5): AI 셰르파 브리핑 카드 실 API 연결 — walking-skeleton 완전 종결
8e60c66 fix(layer3): case 404 일관성 + chat history stateless 지원
7210699 feat(v8): AI 셰르파 채팅 mock → 실 API 전환 + 출처 칩
ec84268 Merge dev into byungwoo (Layer 4 보드/보고서 백엔드 흡수)
6ce6e6f wip(layer3): AI 셰르파 1차 스캐폴딩 — 깡통 LLM/RAG + 4 엔드포인트
7e16782 docs: VERIFICATION.md — Phase 2 종결 시점 시스템 검증 보고서
(머지) Merge #3 from geunhyung — Layer 4 보고서 백엔드
0b3b926 feat(layer4): 보고서 백엔드 1차 — 8섹션 자동 초안 + JSON 영속화 + DOCX export
9fabfd4 feat(v6): ATT&CK 히트맵 실 API 전환 — attack_events 동적 집계
e48826b feat(v5): 수사 보드 프론트 실 API 전환 — ATT&CK 후보 → 노드 추가/수락/거부
8f78a10 feat(layer4): 수사 보드 백엔드 1차 — 노드/엣지 CRUD 4개 엔드포인트
(머지) Merge feat(v3-v4) V3 OCSF + V4 Gap 실 API 전환 from byungwoo
e7da3ab feat(v3-v4): V3 OCSF + V4 Gap mock → 실 API 전환
(머지) Merge feat(layer2) OCSF 정규화 + ATT&CK 매핑 + 갭 감지 from byungwoo
f7a0123 feat(layer2): OCSF 정규화 + ATT&CK 매핑 + 갭 감지 — Layer 2 백엔드 1차
(머지) Merge feat(v2) V2 로그 수집 mock → 실 API 전환 from byungwoo
8034de1 feat(v2): V2 로그 수집 mock → 실 API 전환
(머지) Merge feat(layer1) 로그 수집 API 1차 from 2gu (이근형)
35eba2b feat(layer1): 로그 수집 API 1차 — NCP/NHN 파서 + LogIngestor + 라우터 3개 (이근형)
04638b4 feat(v1): incidentType 5종 통일 + V1 위저드 실 API 연결
4bc5582 feat(layer0): 사고 접수 API 4개 구현
cbd83e1 docs: 모듈별_구현_명세 NCP/NHN 매핑 예시 정정
1c2d59d feat(data): 시드 데이터 공식 가이드 + 실제 raw log 기반 재작성
596ef30 docs: 구현 체크리스트 실제 코드 상태와 동기화
95df4b9 refactor: db/models.py 설계서 5.2절 9개 테이블 명세에 정렬
1cb94e4 docs: AI 부팅 시퀀스·팀 README·설계서 읽는법 추가
636f896 docs: PROGRESS.md — 진행 현황 정리
a6e76b7 feat: 프론트엔드 V1-V8 뷰 구현 및 디자인 시스템 정립
5c7b8e3 chore: 프로젝트 초기 구조 + AI 코딩 지침 + 구현 가이드
```
