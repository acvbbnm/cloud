# KB 인용 유효성·환각 감사 보고서 — 2026-05-24

> 실행: `cd backend && .venv/Scripts/python.exe -X utf8 -m scripts.kb_citation_audit`
> 전제: uvicorn http://localhost:8000 + Ollama llama3.1:8b + KB 4종 130 chunks
> 범위: 사고유형 lane 8건 × Sherpa 4모드 (brief / suggest_missing_link / recommend_playbook / chat) — 총 84 인용 chunk 감사

---

## 1. 종합 점수

| 검증 항목 | 통과율 | 의미 |
|----------|------:|------|
| **A 존재성** | **84 / 84 (100%)** | 모든 인용 chunk_id 가 KB 에 실재 — 환각 chunk_id 생성 없음 |
| **B 사고유형 정합** | 40 / 84 (47.6%) | PLAYBOOK keyword 검색이 lane 과 다른 사고유형 plays 까지 회수 |
| **C 출처 비공백** | 68 / 84 (81.0%) | CASE_DB 일부 `source` 필드 비어있음 |
| **D 환각 없음** | 72 / 84 (85.7%) | chat 응답이 인용 sources 밖 T-id 만듦 12건 |
| **E 수사 가치** | 82 / 84 (97.6%) | chunk 본문에 "탐지·증거·룰·타임라인" 등 실제 수사 단서 포함 |

---

## 2. 각 lane 별 결과

| Lane | 인용 unique | brief 1위 기법 | 환각 T-id | 비고 |
|------|:----:|------|------|------|
| CRED | 9 | T1098.001 Account Manipulation: Additional Cloud Credentials | T1552.001 | 정상 |
| PRIVESC | 9 | T1098.001 | T1068, T1069, T1078.004 | 환각 3건 |
| DATA_EXFIL | 12 | T1531 Account Access Removal | T1071.001 | 정상 |
| AUDIT_TAMPER | 11 | T1562.008 Disable or Modify Cloud Logs | (없음) | ✓ 환각 0 |
| RANSOM | 12 | T1562.008 | (없음) | ✓ 환각 0 |
| MISCFG | 12 | T1530 Data from Cloud Storage Object | T1114.001, T1135, T1210 | 환각 3건 |
| PHISH | 8 | T1136.003 Create Account: Cloud Account | T1190, T1218 | 환각 2건 |
| INSIDER | 11 | T1562.008 | T1078.004, T1550.003 | 환각 2건 |

---

## 3. 발견된 주요 이슈와 권고 조치

### 🔴 P1 — chat 응답 환각 (12건)

**증상**: LLM(llama3.1:8b)이 prompt context 밖 ATT&CK 기법을 만들어 답변에 섞음.
**위반 원칙**: CLAUDE.md "AI 는 판단·결정하지 않는다. 검색·요약·제안만 수행."

| Lane | 환각 T-id | KB 에 없음 |
|------|----------|------|
| CRED | T1552.001 (Credentials In Files) | ✓ |
| PRIVESC | T1068 / T1069 / T1078.004 | ✓ |
| DATA_EXFIL | T1071.001 (Application Layer Protocol) | ✓ |
| MISCFG | T1114.001 / T1135 / T1210 | ✓ |
| PHISH | T1190 / T1218 | ✓ |
| INSIDER | T1078.004 / T1550.003 | ✓ |

**권고 조치** (담당: Sherpa 모듈)
1. `backend/core/sherpa/llm_engine.py` 프롬프트 강화 — "출처 [N] 안에 명시된 technique_id 만 인용. 새 T-id 생성 시 응답 무효." 명시
2. 응답 post-filter — `_TECH_REF_RE` 로 응답에서 T-id 추출 후 sources 의 KB chunk text 안에 없는 T-id 를 자동 strike-through 또는 "(KB 외)" 라벨링
3. 또는 chat 응답에서 ATT&CK 인용 문장 자체를 차단하고 "ATT&CK 인용은 V-4 매핑 결과 참조" 로 redirect

### 🟠 P2 — PLAYBOOK lane 정합성 (44건)

**증상**: `recommend_playbook(chain)` 이 `kb_filter=["PLAYBOOK"]` 로 keyword 검색만 하니까, lane 무관하게 매칭률 높은 plays 가 다 잡힘. 특히 `PLAYBOOK-RANSOMWARE-001`, `PLAYBOOK-NIST-86-001`, `PLAYBOOK-KISA-001` 이 거의 모든 lane 에 반복 등장.

**예시** — CRED lane 에서 인용된 PLAYBOOK:
- ❌ `PLAYBOOK-RANSOMWARE-001` incident_type=RANSOMWARE (lane=CREDENTIAL_THEFT)
- ⚠️ `PLAYBOOK-NIST-86-001` incident_type=ALL → 공통 playbook 이라 OK 이지만, lane 정합 카운트에선 mismatch 처리됨

**권고 조치** (담당: Sherpa 모듈 + KB)
1. `AISherpa.recommend_playbook(chain, incident_type=None)` 시그니처 확장 — 케이스의 `incident_type` 전달받아 `incident_type IN (lane, "ALL")` 필터 추가
2. `backend/api/sherpa.py` 의 `/playbook` 핸들러에서 case 의 incident_type 같이 전달
3. KB 측: `incident_type="ALL"` 인 공통 playbook 은 정합성 위반이 아니므로 감사 로직에서도 `B_aligned` 에 카운트 (감사 스크립트 보완)

### 🟡 P3 — CASE_DB / PLAYBOOK 의 `source` 빈 필드 (16건)

**증상**: 가설 모델·합성 사례 chunk 다수가 `source` 미입력. 예: `CASE-NCP-RANSOMWARE-001`, `CASE-NHN-2026-04-05-001`.

**권고 조치** (담당: KB 큐레이션 — 진규/근형)
1. 가설 시나리오: `source = "AI Sherpa 합성 시나리오 (학습용)"` 명기
2. 역매핑 (Capital One 2019, Colonial Pipeline 2021 등): 원사건 URL 추가 (`url` 필드 활용)
3. 본문 마지막에 "본 사례는 NCP/NHN 환경 매핑을 위한 가설 모델임을 명시" 한 줄 추가 — V-8 KB 패널에서 수사관 오해 방지

---

## 4. 결정론 경로(brief / suggest / playbook) 평가 — 환각 없음 ✓

설계서 5.4.5절 RAGRetriever 는 LLM 호출 없이 KB chunk text 직접 인용 → 구조적으로 환각 불가능. 본 감사 결과 결정론 경로에서 **환각 0건** 확인.
brief 1위 인용은 모두 MITRE ATT&CK 공식 ID (T1098.001 / T1531 / T1562.008 / T1530 / T1136.003) — 인용 사실 정확성 100%.

---

## 5. 후속 작업 체크리스트

- [ ] **P1** — `llm_engine.py` 프롬프트 강화 + 응답 post-filter (담당: Sherpa)
- [ ] **P2** — `recommend_playbook` 시그니처 확장 + incident_type 필터 (담당: Sherpa + API)
- [ ] **P3** — CASE_DB / PLAYBOOK chunk 의 `source` / `url` 보강 (담당: KB)
- [ ] 감사 스크립트 보완 — `incident_type="ALL"` 공통 playbook 은 정합 위반 아님 (담당: byungwoo)
- [ ] 재감사 → P1·P2 완료 후 환각·정합률 재측정
