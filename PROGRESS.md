# AI Sherpa — 진행 현황

> 마지막 업데이트: 2026-05-14 · 브랜치: `dev`
> 이 문서는 **팀이 같은 그림을 보기 위한 작업 메모**입니다. 작업 시작 전·종료 후 갱신해 주세요.

---

## 한눈에 보기

| Phase / Layer | 화면·모듈 | 프론트엔드 | 백엔드 | 데이터 |
|---|---|---|---|---|
| **Phase 1 — 기반 구축** | | | | |
| 1-1 DB 스키마 | `db/models.py` 9개 테이블 | — | ✅ 설계서 5.2절 정렬 | ✅ |
| 1-2 Layer 0 API | `/api/cases`, `/api/guide` | ✅ V1 실 API 연결 완료 | ✅ 4개 엔드포인트 동작 | ✅ |
| 1-3 프론트엔드 셸 | Sidebar, Header, V1 위저드 | ✅ 디자인 시스템 + V1 실 연동 | — | — |
| 1-4 RAG 지식베이스 | KB-1~4 JSON | — | ⏳ ChromaDB 임베딩 미구현 | 🟢 시드 작성 완료 |
| **Phase 2 — 핵심 파이프라인** | | | | |
| 2-1 Layer 1 로그 수집 | V2 드롭존·미리보기 | ✅ **V2 실 API 연결 완료** | ✅ **3개 엔드포인트 + 파서 + 매처 동작** | ✅ raw 228건 E2E 검증 |
| 2-2 Layer 2 분석 | V3 OCSF · V4 갭 | ✅ UI 완료 (mock) | ✅ **5개 엔드포인트 동작** | ✅ 정규화 100%, 매핑 76건 |
| **Phase 3 — 보드·셰르파** | | | | |
| 3-1 Layer 4 수사 보드 | V5 보드 | ✅ UI 완료 | ❌ 미구현 | 🎭 mock |
| 3-2 Layer 3 AI 셰르파 | V8 챗 · V6 ATT&CK 히트맵 | ✅ UI 완료 | ❌ 미구현 | 🎭 mock |
| **Phase 4 — 보고서** | | | | |
| 4-1 보고서 | V7 보고서 편집기 | ✅ UI 완료 | ❌ 미구현 | 🎭 mock |

범례: ✅ 완료 · ⏳ 대기 · ❌ 미구현 · 🎭 mock 데이터 · 🟢 시드 OK

**현재 상태**: Phase 1 + Phase 2-1 + Phase 2-2 백엔드 완료. **V1 → V2까지 풀 연동, Layer 2 분석 파이프라인(OCSF·ATT&CK·갭) 백엔드 완비**.

---

## 작업 내역

### 2026-05-14 — Layer 2 백엔드 1차 완성 (브랜치: `byungwoo` → `dev` 머지)

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
   - `GET  /api/logs?caseId=&page=&pageSize=`
   - `GET  /api/logs/{eventId}` — 원본 raw JSON 포함
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

### 백엔드 (이근형 · 최진규)

**우선순위 1 — V3 OCSF / V4 갭 프론트엔드 실 API 연결**:
- [ ] `api/analysis.ts` 신규 (`runNormalize` / `getOcsf` / `runMap` / `getAttack` / `runGap`)
- [ ] V3 OCSF: 좌측 raw vs 우측 OCSF 양면 비교, `unmapped_raw` 펼침. 정규화 실행 버튼
- [ ] V4 Gap: gap_type · missing 칩 · completionRate 도넛 · recommendation 영역 + `COLLECTION` 시 Layer 0 복귀 버튼 (이미 UI 있음)
- 시연용: NCP 케이스 = 'NONE'(완전), NHN 케이스 = 'COLLECTION'(미수집) 두 패턴 모두 보임

**우선순위 2 — Layer 1 매처 외부화·확장**:
- [ ] `core/ingestion/matchers.py` → JSON 룰 외부화 (`data/collection_targets/target_match_rules.json`)
- [ ] 4종 사고유형 매처 추가 (PRIVILEGE_ESCALATION / DATA_EXFILTRATION / AUDIT_LOG_TAMPERING / MULTI_CSP_LATERAL)
- [ ] 사고유형별 시드(`collection_targets/{csp}_{type}.json` 8개 신규)

### 프론트엔드

- [ ] V3 OCSF mock → 실 API 전환 (Layer 2 백엔드 완성 후, `api/analysis.ts` 신규)
- [ ] V4 갭 감지 mock → 실 API 전환
- [ ] V5 보드 mock → 실 API 전환 (Layer 4 백엔드 완성 후)
- [ ] V7 보고서 mock → 실 API 전환
- React Query 패턴은 V1/V2와 동일 (`useMutation`, `useQuery` + `useCaseStore.caseId` 의존)

### AI / RAG (이지호)

- [ ] `core/sherpa/embed_kb.py` — `data/kb/*.json` 4종을 ChromaDB로 임베딩
- [ ] `core/sherpa/rag_retriever.py` — `retrieve(query, k)` 유사도 검색
- [ ] `core/sherpa/llm_engine.py` — Ollama Llama 3.1 8B 호출 (오프라인)
- [ ] `api/sherpa.py` brief/chat 우선 구현

### 통합 테스트 / 데모

- [ ] Phase 2 완료 시점에 V1→V2→V3→V4 end-to-end 리허설
- [ ] 갭 감지 → Layer 0 복귀 흐름

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
.venv/Scripts/python.exe -m db.init_db          # DB 생성 + 시드 적재
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
git add <특정 파일들>     # git add . 지양
git commit -m "feat: ..."
git pull --rebase origin dev
git push
```

---

## 커밋 히스토리 (2026-05-14 기준)

```
(머지) Merge feat(layer2) OCSF 정규화 + ATT&CK 매핑 + 갭 감지 from byungwoo
f7a0123 feat(layer2): OCSF 정규화 + ATT&CK 매핑 + 갭 감지 — Layer 2 백엔드 1차
(머지) Merge feat(v2) V2 로그 수집 mock → 실 API 전환 from byungwoo
8034de1 feat(v2): V2 로그 수집 mock → 실 API 전환
(머지) Merge feat(layer1) 로그 수집 API 1차 from 2gu (이근형)
35eba2b feat(layer1): 로그 수집 API 1차 — NCP/NHN 파서 + LogIngestor + 라우터 3개  (이근형)
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
