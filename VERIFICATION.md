# AI Sherpa — 검증 보고서

> 점검일: 2026-05-14 · 기준 커밋: `03af52c` (dev) · 점검자: 김병우 + AI 협업
> 이 문서는 **Phase 1 + Phase 2 완료 시점의 시스템 상태**를 객관적으로 기록합니다.
> Phase 3·4 진행과 함께 갱신됩니다.

---

## 1. 작업 범위 정리

### 5계층 파이프라인 진척도

| Layer | 백엔드 API | 비즈니스 로직 | 프론트엔드 | 시드/데이터 |
|---|---|---|---|---|
| **L0 사고 접수** | 4개 (`/api/cases`, `/api/guide`) ✅ | `IncidentCase` · `CollectionGuide` · `Knowledge` ✅ | V1 4단계 위저드 ✅ | `collection_targets` 10건 ✅ |
| **L1 로그 수집** | 3개 (`/api/logs/*`) ✅ | `LogIngestor` · NCP/NHN 파서 · `matchers.py` ✅ | V2 드롭존·미리보기 ✅ | NCP 81 + NHN 147 raw E2E 검증 ✅ |
| **L2 분석** | 5개 (`/api/analysis/*`) ✅ | `OCSFNormalizer` · `AttackMapper` · `GapDetector` ✅ | V3 OCSF · V4 Gap ✅ | `mapping_rules` 2개 · `attack_rules` 22룰 ✅ |
| **L3 AI 셰르파** | ❌ 미구현 | ❌ | V8 mock UI 만 | KB-1~4 JSON 만 (ChromaDB 임베딩 X) |
| **L4 보드 + 보고서** | ❌ 미구현 | ❌ | V5·V6·V7 mock UI | — |

**현재 진척도**: 5계층 중 **3계층(L0·L1·L2) 풀 연동 완료**, 2계층(L3·L4) UI만.

### 코드 규모

| 영역 | 라인 수 |
|---|---|
| 백엔드 (`backend/`) | 2,061 |
| 프론트엔드 (`frontend/src/`) | 2,528 |
| 시드 JSON | 662 |
| **합계** | **5,251** |

---

## 2. 기능 점검 — 실측 결과 (2026-05-14)

### ✅ 정상 동작

| 항목 | 검증 결과 |
|---|---|
| 정상 NCP 파이프라인 (case→upload 81건→normalize→map→gap) | **274ms 완료** |
| Pydantic enum 검증 (invalid `incident_type`) | HTTP 422 ✅ |
| 필수 필드 누락 | HTTP 422 ✅ |
| 존재하지 않는 caseId | HTTP 404 + `CASE_NOT_FOUND` ✅ |
| 잘못된 날짜 형식 | HTTP 422 ✅ |
| 빈 파일 업로드 | HTTP 400 + `EMPTY_FILE` ✅ |
| 깨진 JSON | HTTP 400 + 파싱 에러 메시지 ✅ |
| SHA-256 무결성 (파일 해시 = API 응답) | **완전 일치** ✅ |
| 페이지네이션 중복 없음 | ✅ |
| 갭 4종 분류 (COLLECTION / EVIDENCE / NONE) | 동작 ✅ |

### 🟡 한계 / 알려진 동작

| 항목 | 현재 동작 | 영향 / 권장 |
|---|---|---|
| 단일 객체 JSON 업로드 (배열 아닌 1개) | 201 + matched 1건 처리 | 의도 명세 추가 권장 |
| `PRIVILEGE_ESCALATION` 케이스에 NCP raw | matched=0/81, 모두 unmatched | UX 안내 없음 → "사고유형 미지원" 명시 필요 |
| 시드 없는 사고유형의 gap_type | EVIDENCE (REQUIRED 0건일 때) | 별도 `UNSUPPORTED_TYPE` 코드 권장 |

### ⚡ 성능 측정 (NHN 147건, SQLite + Python 3.14)

```
upload     :  29ms    multipart 수신·해시·파싱·bulk insert
normalize  :  84ms    147건 OCSF 변환·insert
map        :  53ms    22룰 × 147 OCSF event 매칭
gap        :  21ms    집합 비교·gap_results insert
─────────────────────
total      : 187ms    (1초 이내, 매우 빠름)
```

**평가**: 작은 데이터(수백 건)에 충분히 빠름. 대용량(수만~수십만 건) 미검증.

---

## 3. 운영 적합성 평가

### 🟢 운영급 수준 (production-ready)

| 영역 | 평가 |
|---|---|
| 데이터 무결성 | SHA-256 검증 + `raw_json` 원본 보존. 포렌식 측면 합당. |
| 에러 처리 | HTTP 422/400/404 정확. 사용자 친화적 message + 머신 친화적 code. |
| API 계약 | 모든 응답 envelope 일관 (`{status,data}`), 페이지네이션 통일. |
| 타입 안전성 | Pydantic Literal로 enum 강제, TS 타입과 백엔드 응답 1:1 매핑. |
| 무상태 설계 | DB만 외부 상태. SQLite → PostgreSQL 교체 시 코드 변경 최소. |
| 출처 추적성 | `mapping_rules`·`attack_rules` 각 항목에 `source_doc` URL. 학술 검증 가능. |

### 🔴 운영 전 보강 필요

| # | 항목 | 위험 / 영향 | 해결 방향 |
|---|---|---|---|
| 1 | **인증/권한 없음** | 누구나 임의 케이스 조회·수정·업로드 가능 | JWT + RBAC (수사관/관리자/뷰어) |
| 2 | **사고유형 1종만 구현** (CREDENTIAL_THEFT × 2 CSP) | 다른 4종 사고유형 미지원 | 시나리오별 시드 + 매처 추가, 매처 외부화(JSON) |
| 3 | **실 raw 샘플 적음** (NCP 81, NHN 147) | 매핑 룰 false positive/negative 통계 부족 | 더 많은 샘플 + 공식 문서 + condition 평가 |
| 4 | **대용량 미검증** | SQLite + bulk insert 단일 트랜잭션 한계 | 청크 처리 + PostgreSQL + asyncpg |
| 5 | **민감 정보 마스킹 없음** | raw_json에 이메일·IP·UUID 평문 저장 | PII 마스킹 옵션 + at-rest 암호화 |
| 6 | **보존/삭제 정책 없음** | raw_json 무기한. CSP 보존정책(90일) 위반 가능 | `retention_days` 기반 자동 만료 cron |
| 7 | **L3 AI 셰르파 미구현** | "해석 갭" 상황에 도움 못 줌 | Ollama + ChromaDB 임베딩 (Phase 3) |
| 8 | **L4 보드·보고서 미구현** | DOCX/PDF 출력 불가 → 외부 공유 못 함 | Jinja2 + python-docx (Phase 4) |
| 9 | **HTTPS 미적용** | 평문 통신. 사내라도 민감 데이터 노출 위험 | Reverse proxy + TLS, CORS 명시 화이트리스트 |
| 10 | **감사 추적 부분 구현** | `action_logs` 테이블 있으나 자동 기록 코드 없음 | 상태 변경 API에 ActionLog 자동 INSERT |

---

## 4. 시나리오별 사용 가능 여부

| 시나리오 | 사용 가능? | 이유 |
|---|---|---|
| **시연 (demo)** | ✅ 즉시 가능 | 풀 파이프라인 동작. NCP/NHN 두 시나리오 시각화 |
| **캡스톤 학술 발표** | ✅ 가능 | 정직한 한정(샘플 N건·5종 중 1종) 명시 시 변호 가능 |
| **사내 SOC 시범 운영** | 🟡 추가 필요 | 인증 + 4종 사고유형 시드 + 감사 자동화 |
| **상용 침해사고 플랫폼** | ❌ 상당한 추가 작업 | 위 ⓵~⑩ 모두 해소 + 멀티 테넌시 + HA |
| **CSP 운영팀 자체 PoC** | 🟡 OK | 자사 데이터 + 1~2개 사고유형으로 점진 확장 가능 |

---

## 5. 강점·약점 정리

### 강점
- **walking skeleton 패턴**으로 5계층을 깨끗하게 관통
- 각 계층이 분리되어 **부분 교체 가능** (SQLite → Postgres, 매처 → JSON 룰 등)
- 모든 데이터에 **출처 URL** 첨부 → 학술적 검증 가능
- 시드와 코드가 **실제 검증된 raw 로그 기반**으로 일치

### 약점
1. **사고유형 5종 중 1종만 구현** → 시연 후 "다른 사고는?" 질문 시 약함
2. **AI 셰르파 미구현** → 프로젝트명에 "AI"가 들어있는데 실제 LLM 0%
3. **인증·권한 미구현** → 단일 수사관 가정의 MVP, 실 운영 거리 멂
4. **단위/통합 테스트 코드 없음** → 모든 검증이 수동 E2E. pytest 0개

---

## 6. 권장 다음 작업 (학술/시연 가치 순)

1. **L3 AI 셰르파 (mock 응답 → 실 ChromaDB·Ollama)** — 논문 핵심
2. **사고유형 2개 추가** (PRIVILEGE_ESCALATION, DATA_EXFILTRATION) — 시드 + 매처
3. **L4 보드 + 보고서** — 수사 결과를 외부에 공유 가능하게
4. **pytest 테스트 코드** — 캡스톤 평가 시 +α

---

## 7. 점검 절차 재현 방법

```bash
cd cloud/backend
.venv/Scripts/python.exe -m db.init_db   # DB 초기화
.venv/Scripts/python.exe -m uvicorn main:app --port 8000  # 백엔드 띄우기

# 별도 터미널에서
cd cloud/frontend && npm run dev   # 프론트엔드 (localhost:5173)
```

위 보고서의 "기능 점검" 항목은 백엔드를 띄운 상태에서 curl 또는 Python urllib으로 직접 호출하여 측정. 측정 데이터는 `C:\Users\sasum\activity_logs_full.json` (NCP 81건) + `nhn_activity_logs.json` (NHN 147건).

⚠️ **민감 정보**: 위 raw 파일은 실제 NHN 콘솔에서 수집한 사용자 식별 정보가 포함되어 있어 git에 포함되지 않습니다. 다른 PC에서 재현 시 별도 전달 필요.
