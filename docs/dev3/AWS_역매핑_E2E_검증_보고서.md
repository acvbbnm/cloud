# AWS 역매핑 시나리오 — E2E 대시보드 검증 보고서

> **작성일**: 2026-05-21
> **환경**: dev3 워크트리 단독, 백엔드 `127.0.0.1:8000` + 프론트엔드 `127.0.0.1:5173`
> **테스트 대상**: 16편 raw 로그 생성 + 대표 4편 E2E (RANSOM/MISCFG/PHISH/INSIDER)
> **목적**: AWS 역매핑 시나리오를 NCP/NHN raw 로그로 변환하여 실제 시스템 파이프라인의 동작·정확도·간극 검증

---

## 0. TL;DR

| 항목 | 결과 |
|---|---|
| **백엔드 기동** | ✅ uvicorn 정상, `/api/health` 200 |
| **프론트엔드 기동** | ✅ vite 정상, HTTP 200 |
| **raw 로그 생성** | ✅ 16편 / 139 이벤트 (NCP 67 + NHN 72) |
| **E2E 8단계 통과율** | **8/8 × 4 케이스 = 32/32 (100%)** HTTP 응답 정상 |
| **OCSF 정규화** | ✅ 4/4 케이스 100% (총 37건) |
| **ATT&CK 매핑** | ⚠️ 평균 54.7% (RANSOM 81.8%, MISCFG 11.1%, PHISH 85.7%, INSIDER 40%) |
| **갭 감지** | ⚠️ 매핑률 40%도 `NONE` 판정 (임계값 의문) |
| **사고유형 자동 분류** | ❌ **4/4 모두 오분류** — 항상 `PRIVILEGE_ESCALATION` 1위 |
| **보드 자동 노드** | ⚠️ nodes=0/edges=0 — 수동 생성 필요(설계 의도 불명) |
| **RAG (case_db)** | ❌ 새로 추가한 16 REMAP 청크 0건 검색됨 — ATT&CK 1건만 반환 |
| **LLM 요약** | ⚠️ summary_len=0 (깡통 LLM, PROGRESS.md 기재된 예상 동작) |

**결론**: 파이프라인 자체는 모두 동작. 하지만 **신규 4종 사고유형의 분류·매핑·RAG 검색 정확도가 낮음** — 사용자가 본 문서 §11에서 식별한 룰 보강 후보 13건이 *실제 분석 정확도에 직접 영향* 확인.

---

## 1. 작업 절차

### 1.1 raw 로그 생성

- 입력: `backend/data/kb/case_db.json` 의 `CASE-REMAP-*` 청크 16개 (앞서 추가됨)
- 변환 스크립트: `scripts/synthesize_remap_logs.py`
  - NCP timeline → Cloud Activity Tracer raw JSON (16 필드)
  - NHN timeline → Cloud Trail raw JSON (18 필드)
- 출력: `data/test_logs/remap/CASE-REMAP-*.json` × 16 + `_index.json`
- 통계: **139 이벤트 (NCP 67 + NHN 72)**

### 1.2 서버 기동

```
# 백엔드 (dev3/backend/)
python -m uvicorn main:app --host 127.0.0.1 --port 8000
# 응답: {"status":"ok","data":{"server":"running","db":"connected","ollama":"unknown","chromadb":"unknown"}}

# 프론트엔드 (dev3/frontend/)
npm run dev   # http://127.0.0.1:5173/ HTTP 200
```

### 1.3 E2E 시퀀스 (4편 × 8단계)

| 단계 | API | 검증 항목 |
|---|---|---|
| 1 | POST /api/cases (UNCLASSIFIED) | 케이스 생성 |
| 2 | POST /api/logs/upload (multipart) | raw 로그 파싱 + raw_events 적재 |
| 3 | POST /api/analysis/normalize | OCSF 정규화율 |
| 4 | POST /api/analysis/map | ATT&CK 매핑률 + rule_id 분포 |
| 5 | POST /api/analysis/gap | gap_type + missing |
| 6 | GET /api/analysis/attack | tactic 분포 |
| 7 | GET /api/board | chain_nodes/edges 자동 생성 여부 |
| 8 | GET /api/sherpa/validate-incident-type | 자동 사고유형 추정 |

테스트 러너: `scripts/e2e_remap_test.py` · 산출물: `data/test_logs/remap/e2e_report.json`

---

## 2. 단계별 결과 요약

### 2.1 시나리오 4편 통계

| 시나리오 | 기대 사고유형 | CSP | raw | OCSF | 매핑 | 매핑률 | gap | 자동분류 1위 |
|---|---|---|---|---|---|---|---|---|
| CASE-REMAP-NCP-RANSOM-001 | RANSOMWARE | NCP | 11 | 11 | 9 | **81.82%** | NONE | PRIVILEGE_ESCALATION (1.0) |
| CASE-REMAP-NHN-MISCFG-001 | MISCONFIG_EXPOSURE | NHN | 9 | 9 | 1 | **11.11%** | INTERPRETATION | PRIVILEGE_ESCALATION (0.5) |
| CASE-REMAP-NCP-PHISH-001 | PHISH_INITIAL_ACCESS | NCP | 7 | 7 | 6 | **85.71%** | NONE | PRIVILEGE_ESCALATION (1.0) |
| CASE-REMAP-NHN-INSIDER-001 | INSIDER_THREAT | NHN | 10 | 10 | 4 | **40.0%** | NONE | PRIVILEGE_ESCALATION (1.0) |

### 2.2 사고유형 자동 분류 상세 (validate-incident-type)

각 케이스에서 후보 사고유형의 score_ratio (matched / expected_techniques):

**RANSOMWARE 케이스 결과**:
1. PRIVILEGE_ESCALATION — **1.0** (2/2 기법 관측) ← 1위
2. CREDENTIAL_THEFT — 0.6 (3/5)
3. DATA_EXFILTRATION — 0.5 (1/2)
4. INSIDER_THREAT — 0.5 (2/4)
5. PHISH_INITIAL_ACCESS — 0.33 (1/3)
6. **RANSOMWARE — 0.25 (1/4) ← 기대값, 6위**

> 핵심 누락: T1486 (Data Encrypted), T1490 (Inhibit Recovery), T1567

**MISCONFIG_EXPOSURE 케이스 결과**:
1. PRIVILEGE_ESCALATION — 0.5 ← 1위
2. PHISH_INITIAL_ACCESS — 0.33
3. RANSOMWARE — 0.25
4. **MISCONFIG_EXPOSURE — 0.25 (1/4) ← 기대값, 4위**

> 핵심 누락: T1190 (Exploit Public-Facing App), T1530, T1580 (Cloud Infra Discovery) — NHN raw 룰셋에 *전혀 매핑되지 않음*

**PHISH_INITIAL_ACCESS 케이스 결과**:
1. PRIVILEGE_ESCALATION — 1.0 ← 1위
2. INSIDER_THREAT — 0.5
3. CREDENTIAL_THEFT — 0.4
4. **PHISH_INITIAL_ACCESS — 0.33 (1/3) ← 기대값, 4위**

> 핵심 누락: T1556 (Modify Authentication), T1566 (Phishing 자체)

**INSIDER_THREAT 케이스 결과**:
1. PRIVILEGE_ESCALATION — 1.0 ← 1위
2. CREDENTIAL_THEFT — 0.6
3. **INSIDER_THREAT — 0.5 (2/4) ← 기대값, 3위**

> 핵심 누락: T1530 (Data from Cloud Storage), T1562 (Disable/Modify Cloud Logs)

---

## 3. 잘 동작하는 영역 ✅

1. **OCSF 정규화 파이프라인**: 4/4 케이스 모두 **100% 정규화 성공** (37건, 실패 0)
2. **NCP·NHN 시간 파서**: NCP의 `YYYY-MM-DD HH:MM:SS UTC` 와 NHN의 ISO8601 `+0000` 두 형식 모두 정상 처리
3. **ATT&CK 룰 매핑 — 기존 4종 시그니처**:
   - RANSOM(NCP) 81.8%, PHISH(NCP) 85.7% — 두 케이스 모두 *기존 4종 시그니처*(Login·Create AccessKey·Attach policy·Export 등)가 풍부해서 룰 매칭 잘 됨.
4. **gap 분류기의 가설 능력**:
   - MISCFG(NHN) 매핑률 11.11% → 정확히 `gap_type=INTERPRETATION` 으로 판정 (의미상 정합)
5. **validate-incident-type 의 ranked list 제공**:
   - candidate_types 가 모든 사고유형에 대해 `matched`/`expected`/`score_ratio`/`reason`(누락 기법 목록) 까지 반환 → UI에서 *상위 N개 표시*로 활용 가능.
6. **API 응답 일관성**: 전 8단계 32회 호출 모두 200/201, 응답 스키마 `{status, data}` 통일.
7. **REMAP 시나리오의 학술 정합**: knowledge.py 의 `related_techniques` 정의가 본 문서 §1.4 표와 정확히 동기화됨 (RANSOMWARE 의 T1486/T1490 등).

---

## 4. 발견된 문제 ⚠️ / 버그 ❌

### 4.1 ❌ [HIGH] 사고유형 자동 분류 — 모든 케이스 PRIVILEGE_ESCALATION 으로 오분류

**증상**: 4/4 케이스 모두 1위 추천이 `PRIVILEGE_ESCALATION` (score_ratio 0.5~1.0). 기대 사고유형은 3~6위.

**원인 분석**:
- `IncidentTypeKnowledge["PRIVILEGE_ESCALATION"].related_techniques` 가 **2개만** (T1098, T1136 등) → 적은 매칭으로 score_ratio 1.0 쉽게 달성.
- 신규 4종(RANSOM/MISCFG/PHISH/INSIDER)의 `related_techniques` 는 4개 이상이고 그 중 *클라우드 raw 로그로 검출 불가한 기법*(T1486, T1190, T1566, T1530, T1562) 비중이 큼 → score_ratio 0.25~0.5 로 깎임.

**제안**:
- (a) 가중치 도입: 검출하기 어려운 기법은 weight 0.3, 쉬운 기법은 weight 1.0 — 평균 ratio 산출.
- (b) **`PRIVILEGE_ESCALATION` 의 related_techniques 확장**: T1078, T1078.001, T1078.004 추가 (이렇게 하면 다른 사고유형도 PrivEsc 라고 오분류되는 일이 줄어듦 — 단 false positive 가 늘어날 수 있어 평가 필요).
- (c) **이벤트 빈도 가중** 도입: 단순 *기법 존재 여부*가 아닌 *해당 기법이 몇 건 관측됐는가*로 score 계산. RANSOMWARE 의 Impact 4건 + Exfiltration 2건은 PrivEsc 의 단순 PrivEsc 1건보다 우세해야 함.

**검증 데이터 — RANSOM 케이스의 실제 tactic 분포** (Impact 4, Exfil 2, Lateral 1, Persistence 1, IA 1) vs PrivEsc 단 1건이 안 나옴에도 1위로 잡힘.

### 4.2 ❌ [HIGH] 신규 4종 핵심 기법이 NCP/NHN attack_rules 에 누락

**증상**:
- RANSOMWARE: T1486 (Data Encrypted for Impact), T1490 (Inhibit System Recovery) — 룰 없음
- MISCONFIG_EXPOSURE: T1190 (Exploit Public-Facing), T1580 (Cloud Infra Discovery), T1530 — 룰 없음
- PHISH_INITIAL_ACCESS: T1566 (Phishing), T1566.001, T1556 (Modify Auth Process) — 룰 없음
- INSIDER_THREAT: T1562.008 (Disable Cloud Logs), T1530 — 룰 없음

**영향**:
- MISCFG(NHN) 케이스: 9건 중 1건만 매핑 (11.11%) — *대부분 NHN 액션*(`container.list`, `container.metadata.update`, `object.download`)이 룰 없음.
- INSIDER(NHN) 케이스: 10건 중 4건만 (40%) — *비표준 시각·직무 외 접근* 같은 행위 패턴 룰 없음.

**제안**: AWS_역매핑_시나리오.md §11.2 의 **13개 신설 후보** 우선순위:

| 우선순위 | rule_id | 검출 대상 |
|---|---|---|
| P0 | **R-NHN-012** | `event_id.object_storage.object.download` (단독) — MISCFG/EXFIL 검출 핵심 |
| P0 | **R-NCP-012** | `Delete Tracer` / `Disable Auto Export` — AUDIT_LOG_TAMPERING + RANSOM T1490 |
| P1 | **R-NCP-014** | `Delete Bucket` burst — RANSOM T1490 |
| P1 | **R-NHN-013** | `s3credential.delete` burst (3건/5분) — AUDIT_LOG_TAMPERING |
| P1 | **R-NHN-014** | `instance_action.stop` burst — RANSOM T1489+T1490 |
| P2 | **R-NCP/NHN-016** | FAIL→SUCCESS 시간차 (MFA OTP relay 검출) — PHISH 핵심 |
| P2 | **R-NCP/NHN-018** | 비표준 시각 사내 IP 동작 — INSIDER 핵심 |

### 4.3 ⚠️ [MEDIUM] gap_detector 의 매핑률 임계값 부재(또는 비정합)

**증상**:
- INSIDER(NHN) **매핑률 40.0% → gap_type=NONE** ("갭 없음. 필수 증거 0건 모두 수집…")
- MISCFG(NHN) **매핑률 11.11% → gap_type=INTERPRETATION** (정확)
- 즉 *11%는 INTERPRETATION 인데 40%는 NONE* — 분기 기준이 매핑률보다는 *필수 증거 0건*(case incident_type=UNCLASSIFIED 라서) 에 좌우되는 듯.

**제안**:
- UNCLASSIFIED 케이스에서 매핑률이 *일정 threshold (예: 60%)* 미만이면 INTERPRETATION 으로 일관 분류.
- 또는 `gap_results` 응답에 *매핑 안 된 활동 목록*(missing_actions) 별도 필드 제공 → 수사관에게 결정권 이양.

### 4.4 ⚠️ [MEDIUM] 보드 자동 노드 생성 흐름 부재

**증상**: 4/4 케이스에서 `GET /api/board → nodes=0, edges=0`. POST /api/analysis/gap 의 recommendation 은 "Layer 4 수사 보드로 진행하세요" 인데 막상 보드에 노드가 없음.

**원인**: V-5 보드는 **수사관이 매핑된 ATT&CK 이벤트를 수동으로 노드로 만드는 워크플로** — *자동 노드 생성 흐름 없음*. POST /api/board/nodes 호출 필요.

**확인 필요**:
- 이게 설계 의도(수사관 결정권)인지, V-5 UI에 *자동 변환 버튼*이 있어야 하는지 합의 필요.
- 시연 시나리오에서 V-5 화면이 *attack_events 자동 표시 + "노드로 추가" 버튼*을 제공한다면 OK. 그렇지 않다면 *완전 빈 보드*로 시작.

### 4.5 ❌ [HIGH] RAG 검색에서 case_db.json 청크 검출 안 됨

**증상**:
- 4 케이스 모두 `POST /api/sherpa/brief` 응답의 `sources` 가 **단 1개**, 모두 *ATT&CK 청크*(예: `ATTACK-T1531-001`).
- 새로 추가한 **REMAP 청크 16개**(특히 `CASE-REMAP-NCP-RANSOM-001` 같은 직접 매칭 가능 청크)가 **단 한 건도 검색되지 않음**.

**원인 추정** (코드 미확인, 단순 관측):
- `sherpa.py` 의 깡통 RAG가 *기법 ID 기반 1:1 매칭*만 사용 — `attack.json` 의 ATTACK 청크만 반환.
- `case_db.json` 의 CASE_DB 청크는 *기법 ID 외 incident_type/csp 기반 검색이 필요*하나 구현 안 됨.

**제안**: `RAGRetriever` 가 `case_db` KB 도 점수화에 포함 — 적어도 *동일 incident_type + 동일 csp 청크*를 후순위로 첨부. CASE_DB 청크 검색이 안 되면 *역매핑 시나리오 작성 자체의 활용 가치가 RAG 측면에서 0*.

### 4.6 ⚠️ [LOW] LLM 요약 빈 응답

**증상**: 모든 brief 의 `summary_len=0`.

**원인**: PROGRESS.md 1-4 항목 *"깡통 RAG 동작 (키워드+점수화) · ChromaDB 미구현"* 명시 — **예상된 동작**. Ollama 미연결, LLM 추상화만 존재.

**제안**: 시연 직전 Ollama 컨테이너 기동 + 모델(`llama3.1:8b`) 로딩 절차 필수. 시연 시 *summary 비어 있으면 *깡통 모드* 식별 표시*.

### 4.7 ⚠️ [LOW] `IngestionStats.to_dict()` 응답에 `parsed_count` 키 부재

**증상**: `/api/logs/upload` 응답 data 키에 `parsed_count`/`matched_count` 가 직접 없어서 테스트 스크립트가 `?` 출력. 응답 구조 확인 필요.

**제안**: 응답 스키마 일관성 검토 (`stats.to_dict()` 의 키 이름이 OpenAPI 문서와 일치하는지).

---

## 5. 시나리오별 상세 진단

### 5.1 RANSOMWARE (NCP) — Colonial Pipeline 역매핑

- **잘 됨**: 11 raw → 11 OCSF → 9 매핑 (81.8%). Impact 4건(`Shutdown Server Instance` × 3 + `Disable AccessKey`) + Exfiltration 2건(Request/Complete For Exporting To Object Storage) 정확 검출.
- **문제**: 핵심 RANSOMWARE 시그니처(T1486 암호화·T1490 백업 무력화)가 raw 단서로 *부재* — `Delete Bucket` 2건은 *NCP attack_rules 에 룰 없음*. RANSOMWARE 가설 1위가 안 나오는 본질적 원인.
- **대응**: R-NCP-014 (`Delete Bucket` burst) 신설 + knowledge.py 의 RANSOMWARE 에 *T1531 추가* (자기 키 삭제도 영향 단서).

### 5.2 MISCONFIG_EXPOSURE (NHN) — Verkada 역매핑

- **잘 됨**: 9 raw → 9 OCSF (100%). 시퀀스 자체(공개 변경 → 다운로드 burst → reset)는 timeline 으로 정확 표현.
- **문제**: **9건 중 8건 미매핑** — `event_id.iam.org.selected`, `iam.member.list`, `object_storage.container.list/metadata.update`, `object.download` 모두 룰 없음.
- **대응**: R-NHN-012 (download), R-NHN-015 (공유 계정 식별), Discovery 류 5건에 대한 메타 룰 신설 필요. **이 케이스가 §11 보강 후보의 가장 강력한 정당성**.

### 5.3 PHISH_INITIAL_ACCESS (NCP) — Twilio 0ktapus 역매핑

- **잘 됨**: 7 raw → 7 OCSF → 6 매핑 (85.7%). FAIL→SUCCESS 16초 차 + 즉시 password 변경 + PrivEsc 시퀀스가 시각 패턴까지 보존.
- **문제**: T1566 (Phishing) 자체는 룰 없음. raw 로그만으로는 *PHISH인지 자체적 CRED_THEFT인지* 변별 어려움 — 분류 결과도 CREDENTIAL_THEFT(0.4) 가 PHISH(0.33) 보다 위.
- **대응**: R-NCP-016 (FAIL→SUCCESS 시간차 10~30초 룰) 신설 — 이 룰 1건만 추가해도 PHISH 가 본 케이스에서 1위로 올라올 가능성 있음.

### 5.4 INSIDER_THREAT (NHN) — Coinbase 역매핑

- **잘 됨**: 10 raw → 10 OCSF → 4 매핑 (40%). Login + role.update + s3credential.create/delete 매핑.
- **문제**: 핵심 INSIDER 시그니처 *비표준 시각·직무 외 자원·다운로드 burst* 가 룰화 안 됨. T1530 (download)·T1562 (감사 우회) 미매핑.
- **대응**: R-NHN-012 + R-NHN-018 (비표준 시각) + R-NHN-019 (직무 diff) 셋이 모두 필요.

---

## 6. 산출물 위치

| 파일 | 용도 |
|---|---|
| `scripts/synthesize_remap_logs.py` | case_db.json `CASE-REMAP-*` → raw 로그 16개 변환기 |
| `scripts/e2e_remap_test.py` | E2E 8단계 테스트 러너 |
| `data/test_logs/remap/CASE-REMAP-*.json` × 16 | raw NCP/NHN 로그 (139 이벤트) |
| `data/test_logs/remap/_index.json` | 16편 메타 인덱스 |
| `data/test_logs/remap/e2e_report.json` | 4편 E2E 결과 JSON |
| `docs/dev3/AWS_역매핑_시나리오.md` | 원본 시나리오 (선행 작업) |
| `docs/dev3/AWS_역매핑_E2E_검증_보고서.md` | **이 문서** |

---

## 7. 다음 단계 (제안)

### 7.1 우선순위 P0 (시연 전 필수)

1. **사고유형 분류 가중치 도입** (§4.1 (a) 또는 (c)) — *4/4 오분류는 시연 결정타*
2. **R-NHN-012 (`object.download`) 룰 신설** — MISCFG 11% → 정상 매핑률 회복
3. **RAG에 case_db 청크 포함** (§4.5) — 16편 REMAP 청크 활용 가능

### 7.2 우선순위 P1 (다음 스프린트)

4. R-NCP-012 (Delete Tracer / Disable Auto Export)
5. R-NCP-014 (Delete Bucket burst)
6. R-NHN-013/014 (s3credential.delete / instance.stop burst)

### 7.3 우선순위 P2 (룰 백로그)

7. R-NCP/NHN-016 (FAIL→SUCCESS 시간차 — PHISH 검출 핵심)
8. R-NCP/NHN-018 (비표준 시각 사내 IP — INSIDER)
9. R-NCP/NHN-019 (직무 범위 diff — INSIDER)
10. gap_detector 임계값 정합 (§4.3)
11. board 자동 노드 생성 정책 합의 (§4.4)

---

## 8. 핵심 결론

> **본 E2E 검증은 AWS_역매핑_시나리오.md §11 의 룰 보강 후보 13건이 *추상적 백로그가 아닌 실측 성능 차이*임을 입증한다.**
>
> - 기존 4종(CRED·PRIV·EXFIL·AUDIT)은 매핑률 80%+ — 시연 가능 수준.
> - 신규 4종(RANSOM·MISCFG·PHISH·INSIDER)은 매핑률 11~85% 편차 + 4/4 오분류 — **§11 신설 룰 13건 중 P0/P1 7건은 시연 전 처리 권고**.
>
> 단, 파이프라인 골격(케이스→업로드→정규화→매핑→갭→보드→검증)은 *100% HTTP 200*로 동작하며, validate-incident-type 의 candidate_types ranked list 는 *UI 표시 → 수사관 확정* 워크플로의 강한 기반이다.
