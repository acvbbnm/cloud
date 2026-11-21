# dev3 백엔드 인계 메모 — B-1 완료

> 작성일: 2026-05-18
> 단계: **B-1 (Triage API 라우터 + 평가 엔진) 완료**
> 다음 단계: B-2 (멀티파트 부분 로그 업로드) / B-3 (DB 칼럼 확장)

---

## B-1 완료 — 무엇이 들어갔나

### 신규 파일

**`backend/api/triage.py`** (192줄) — 4개 라우터

| 메서드 | 경로 | 역할 |
|---|---|---|
| POST | `/api/triage/start` | 트리 시작 (root 노드 + 초기 점수) |
| POST | `/api/triage/next` | 답변 → 다음 노드 + 점수 갱신 + T_evaluate 도달 시 recommendation |
| POST | `/api/triage/analyze` | 단서·기법 ID → 가설 점수 보강 |
| POST | `/api/triage/confirm` | `incident_cases.incident_type` 갱신 (UNCLASSIFIED 포함) |

**`backend/core/intake/triage.py`** (372줄) — 평가 엔진

- 정적 JSON 캐싱 (`_load_json` + `_cache`)
- 5 사고유형 점수 누적 (`_accumulate`, `_accumulate_many`)
- 트리 노드 직렬화 (`_serialize_node`)
- recommendation 평가 (`evaluate_recommendation` — auto_confirm / propose_composite / propose_single / continue_or_skip)
- `Triage` 클래스 — `start()`, `next_question()`, `analyze()`, `evaluate()` 공개 API

### 수정 파일

**`backend/api/intake.py`** — IncidentType Literal 에 `UNCLASSIFIED` 추가 (1줄)
**`backend/main.py`** — triage 라우터 등록 (2줄, 라우터 import 1 + include 1)

---

## 검증 결과 (시뮬레이션 1)

시나리오: 자격증명 탈취 — Q1 CSP 알람 → Q2A 비정상 로그인 + 비국내 IP → Q3 실패→성공

| 단계 | CRED | PRIV | DATA | AUDIT | MULTI |
|---|---|---|---|---|---|
| Q1 `csp_alert` | 15 | 10 | 5 | 5 | 0 |
| Q2A `abnormal_login` + `non_korean_ip` | **60** | 20 | 10 | 5 | 0 |
| Q3 `fail_then_success` → T_evaluate | **95** | 20 | 10 | 5 | 0 |

**recommendation outcome**: `auto_confirm`
**근거**: CRED 95 ≥ auto_skip_tree(90), gap 75 ≥ gap_to_2nd(20)
**예상 동작**: 클라이언트가 추가 사용자 클릭 없이 사고유형 = CREDENTIAL_THEFT 자동 확정

→ 학술 가중치 매트릭스 (`backend/data/triage/weights.json`) 가 실 시나리오에서 의도대로 작동.

---

## 설계 원칙 (인계 시 보존 필수)

1. **결정성 100%** — 같은 입력 → 같은 출력. 가중치 계산은 `weights.json` 정적 JSON 만 사용.
2. **AI 판단 X** — 사고유형 결정은 트리 + 사용자. 백엔드는 점수만 산출.
3. **stateless** — 클라이언트가 `hypothesis_scores` 와 `tree_path` 를 매 요청 전달. 서버 세션 X.
   - DB 영속화는 **B-3 작업으로 분리** — `incident_cases.triage_state` JSON 칼럼 후속 추가.
4. **임계값 단일 소스** — `weights.json` 의 `thresholds` 필드 외 임계값 하드코딩 금지.

---

## 프론트엔드 정합 (이미 완료)

- `frontend/src/api/triage.ts` — 백엔드 4개 라우터 호출 + 자동 mock fallback
- `frontend/src/views/V1_Setup/Step2_Discovery.tsx` (550줄) — 결정 트리 + 단서 + 부분 분석 + 다음 단서 + 시각화 UI 완성
- `frontend/src/stores/useTriageStore.ts` — 트리 진행 상태 영속화

→ 백엔드 B-1 푸시 후 사용자 환경에서 백엔드 재시작만 하면 **end-to-end Discovery Loop 작동**.

---

## ⚠ 이슈 — "사고유형 선택 후 다음 레이어 못 감" 원인

dev3 push 직전까지 **B-1 백엔드가 untracked 상태**였음 → 사용자 백엔드 미실행 / 옛 백엔드 실행 시:

1. `/api/triage/*` 라우터 부재 → 프론트가 mock fallback 으로 트리는 진행
2. `recommendation` 산출 → "✓ 확정" 버튼 표시
3. 버튼 클릭 → `createCase` (`/api/cases`) 호출
4. **옛 백엔드는 `UNCLASSIFIED` enum 거부 (422)** → 케이스 생성 실패 → setStep(3) 불가
5. 사용자 입장: "사고유형 선택했는데 다음 단계 안 감"

이 커밋 push 이후:
- 사용자가 백엔드 재시작 (`uvicorn main:app`) 하면 자동 해결
- 단, **DB 세션 재생성 필요 없음** — incident_cases 스키마는 그대로 (incident_type 은 String(32))

---

## 다음 단계 후보 (B-2, B-3)

### B-2 — 부분 로그 멀티파트 업로드

현재 `/api/triage/analyze` 는 클라이언트가 OCSF 정규화·ATT&CK 매핑을 마친 `technique_ids` 만 전달받음.
실제로는 사용자가 로그 파일을 드래그하면 백엔드가:
1. 파일 수신 (multipart/form-data)
2. 단서 시각 ±5분 윈도우 추출
3. Layer 1 ingest → Layer 2 OCSF + map 재사용
4. 결과 `technique_ids` 를 점수에 누적

→ 별도 라우터 `POST /api/triage/analyze-logs` (multipart) 신설 권장
→ 또는 기존 `/analyze` 에 `UploadFile` optional 추가

### B-3 — DB 영속화 (incident_cases 칼럼 추가)

청사진 §5.2 에 명시된 신규 칼럼 4개:
- `title` (String 200, nullable=False)
- `tlp` (String 16, default 'AMBER')
- `observables` (JSON, default [])
- `secondary_incident_types` (JSON, nullable=True)
- `triage_state` (JSON, nullable=True) — 트리 진행 상태 영속화

**주의 — CLAUDE.md 정책**: `db/models.py` 는 DB 담당자(이근형·최진규)만 수정. 합의 후 진행.

마이그레이션:
- SQLite 라 ALTER TABLE 가능
- 기존 row 는 default 값 채움
- 단, `title` 은 NOT NULL 이라 기존 row 는 `case_id 일부` 로 fallback

---

## 즉시 검증 절차 (다른 사람이 이어받을 때)

```bash
cd backend
./.venv/Scripts/python.exe -c "from api.triage import router; from core.intake.triage import Triage; print(Triage.start())"
```

→ `next_node` 의 `id` 가 `Q1_inception` 으로 나오면 OK.

```bash
# 백엔드 기동
./.venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000

# 다른 터미널에서 curl 검증
curl -X POST http://localhost:8000/api/triage/start \
  -H "Content-Type: application/json" \
  -d '{"caseId": "TEST"}'
```

`{"status":"error","message":"케이스를 찾을 수 없습니다", ...}` 가 나오면 라우터 등록·import 정상 (404 는 caseId 미존재 때문, 정상).

기존 케이스 ID 로 호출하면 `{"status":"ok","data":{"next_node": {"id":"Q1_inception",...}}}` 응답.
