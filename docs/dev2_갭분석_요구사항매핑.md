# dev2 갭 분석 — 설계서 요구사항 ↔ 현재 구현 매핑

> 작성: 2026-05-16 · 브랜치: `dev2` · 회의용 요약(우선순위 P0/P1/P2)
>
> P0 = 이번 주 시연 필수 · P1 = 회의 후 1~2주 · P2 = 정식 마감 / 후속

현재 dev2는 **walking-skeleton 8/8 + V2 가이드 + Ollama RAG**까지 통합된 상태. 22 API 모두 등록되어 있고, 풀 파이프라인(V-1~V-8)이 mock 없이 동작한다. 남은 갭은 **데이터 폭(시드·KB)**과 **AI 응답 품질(프롬프트·모델)** 두 축에 집중되어 있다.

---

## 1. 🔧 더 구현해야 할 것 (코드)

| ID | 항목 | 어디 | 왜 필요 | 우선순위 | 추정 |
|---|---|---|---|---|---|
| C1 | **V2 가이드 ↔ V-4 갭 결과 연결** | `core/analysis/gap_detector.py` + `Step3_GuideChecklist_V2.tsx` | 현재 V2 가이드는 *생성*만 됨. V-4에서 COLLECTION 갭이 떴을 때 누락된 카테고리를 V2 매트릭스에 빨간색으로 되돌려 표시해야 "L0 복귀 → V2 재계산" 시연 임팩트가 산다. | P0 | 4h |
| C2 | **V2 가이드 v1 호환 모드 또는 토글 디폴트** | `frontend/src/views/V1_Setup/index.tsx` | 시연에서 v1/v2 토글 위치/디폴트가 불명확. v2를 디폴트로 두되 갭 감지(V-4)는 여전히 v1 collection_targets 기준 → **시연 시 v2 매트릭스 = 보여주기용, 갭은 v1 기준**임을 UI에서 안내해야 혼란이 없다. | P0 | 2h |
| C3 | **PDF 내보내기 (현재 501)** | `core/board/report_generator.py::export_pdf()` | 시연 마지막 단계에서 DOCX만 가능. `docx2pdf` 또는 `weasyprint` 한 가지 채택. 오프라인 동작 위해 `weasyprint` 권장(SNF-01). | P1 | 6h |
| C4 | **V-5 BoardCanvas 노드 위치 저장** | `chain_nodes` 테이블 + `PATCH /api/board/nodes` | 현재 드래그 위치가 백엔드에 저장 안 됨(PROGRESS.md 명시). 새로고침 시 노드 초기화 → 시연 중 사고 가능. | P1 | 3h |
| C5 | **`POST /api/sherpa/suggest` 실 동작화** | `core/sherpa/ai_sherpa.py::suggest_missing_link()` | 현재 깡통(케이스 내 다른 기법 위험도 순). 백로그 B3(공격 체인 자동 추정)와 연결. LLM에 "nodeA→nodeB Kill Chain 중간 기법은?" 묻고 KB 참조. | P2 | 8h |
| C6 | **5 사고유형별 V1 가이드 시드 분기 코드** | `core/intake/collection_guide.py` | v1 `generate()`는 CREDENTIAL_THEFT만 시드되어 다른 4 사고유형은 빈 체크리스트. v2가 incident_type_phases.json으로 커버하긴 하지만, v1 갭 감지를 위해선 시드 필요(D2). | P1 | 시드 작성과 묶음 |
| C7 | **V-7 dirty 변경 beforeunload 경고** | `frontend/src/views/V7_Report/index.tsx` | 시연 체크리스트 §5 알려진 한계. 편집 후 페이지 이탈 시 경고 없음. | P2 | 1h |
| C8 | **`/api/sherpa/kb` 응답 시간 측정/캐시** | `api/sherpa.py` | V-8 우측 패널 첫 로드가 느림(임베더 첫 로딩). startup lifespan에서 warmup. | P2 | 2h |

**합계 P0: ~6h · P1: ~9h · P2: ~11h**

---

## 2. 📚 지식베이스에 쌓아야 할 것 (데이터)

| ID | 카테고리 | 현재 | 필요 | 출처 | 우선순위 | 추정 |
|---|---|---|---|---|---|---|
| D1 | **KB-1 ATTACK** | 3 청크 (T1078.004 / T1136.003 / T1098.001 — CREDENTIAL_THEFT만) | 5 사고유형 핵심 기법 각 2~3개 = **12~15 청크** (T1531·T1485·T1567·T1098 등 attack_rules에 이미 등장) | MITRE ATT&CK Cloud Matrix v14 | P0 | 3h |
| D2 | **v1 collection_targets** | naver/nhn × CREDENTIAL_THEFT = 2 파일 (5건 each) | 5 사고유형 × 2 CSP = **10 파일** (8 추가). 시연 시나리오 B의 NHN 갭 복귀처럼 다른 사고유형도 동일 흐름이 가능해야 변호 가능 | KISA 침해사고 분석절차 안내서 §3 / NCP·NHN 공식 문서 | P0 | 6h |
| D3 | **KB-2 PLAYBOOK** | 2 청크 (계정 탈취·증거 보존만) | 사고유형별 대응 절차 5~7 청크 (특히 DATA_EXFILTRATION, AUDIT_LOG_TAMPERING 누락) | KISA §4 대응 절차 / NIST SP 800-61r2 | P1 | 4h |
| D4 | **KB-4 CASE_DB** | 5 청크 (NCP·NHN 합성·실 사례) | 멀티 CSP 횡적 이동 사례 1건 더, 권한 상승 사례 1건 — 시연 중 V-8 "유사 사례" 검색 시 hit 풀이 너무 좁음 | 합성 데이터 생성 또는 공개 침해사고 사례 | P1 | 3h |
| D5 | **attack_rules/rules.json** | 22 룰 (NCP 11 + NHN 11), 모두 CREDENTIAL_THEFT 시나리오 기반 | T1567(Exfiltration), T1485(Data Destruction), T1537(Transfer Data) 등 활성 기법들에 대한 **CSP 매핑 규칙** 추가 (현재 매핑은 룰만 있고 raw 로그 패턴이 시연 데이터에 없음) | NCP Cloud Activity Tracer / NHN Cloud Trail 이벤트 코드 카탈로그 | P1 | 5h |
| D6 | **mapping_rules/{ncp,nhn}_cloud_trail.json** | NCP 5 필드 / NHN 5 필드 매핑 | OCSF 핵심 필드 약 10개 더 (resource, target_user, action_result_message, severity 등). 현재 V-3 정규화는 minimum viable 5 필드만 채워짐 | OCSF v1.1 스키마 §Authentication, §API Activity | P2 | 4h |
| D7 | **KISA 인용 강화** (§2.4 점검표, §3 표 3-3) | v2 카테고리 시드 9개에 KISA 인용 일부만 | §2.4 "6항목 점검표" 전부, §3 "공격 이벤트 매트릭스" 칼럼별 인용 — 학술 변호 강도 | KISA 침해사고 분석절차 안내서 PDF | P1 | 3h |
| D8 | AWS/Azure 카테고리 확장 | NCP/NHN만 매핑 | **MVP 범위 밖**으로 보류. 단, v2 README에 "본 시드는 NCP/NHN 한정" 명시 | — | P2 | — |

**시연 직전 필수(P0): D1 + D2 = ~9h**

---

## 3. 🤖 AI 튜닝해야 할 것 (셰르파)

| ID | 항목 | 현재 동작 | 문제점 | 제안 | 효과 | 우선순위 | 추정 |
|---|---|---|---|---|---|---|---|
| A1 | **CSP 용어 강제** | LLM이 "NCP Cloud Trail"이라고 답한 사례 발생 | 실제는 NCP = **Cloud Activity Tracer**, NHN = **Cloud Trail**. KB에는 정확히 들어 있으나 모델이 일반화하여 혼동 | `SYSTEM_PROMPT` 에 용어 강제 1줄 추가: *"NCP의 로그 서비스는 'Cloud Activity Tracer'이며, 'Cloud Trail'은 NHN 서비스다. 절대 혼동하지 말 것."* | 가장 빈번한 오답 1건 제거 | P0 | 0.5h |
| A2 | **출처 인용 형식 강제** | 본문에 [1] 인용은 잘 되지만 출처 칩과 매칭 안 되는 경우 발생 | 모델이 [1]만 쓰고 [2], [3]을 안 쓰는 경우 = 출처 칩 클릭 검증 시 흠 | 시스템 프롬프트에 *"제공된 청크 N개 중 사용한 것은 모두 인용. 사용하지 않았다면 출처 칩에서 빼야 함을 표시."* + `_build_user_prompt` 에서 후처리로 미인용 출처 제거 | 출처 칩 신뢰도↑, 백로그 U3 자연 연결 | P0 | 2h |
| A3 | **한국어 면책 문구 정착** | 시스템 프롬프트 §6에 "※ 최종 판단은 수사관께서 직접 수행해 주세요." 명시되어 있으나 모델이 빠뜨릴 때 있음 | 8B 모델은 자주 누락 | `LLMEngine.generate()` 응답 후처리에서 면책 문구 없으면 자동 append (이미 fallback 메시지엔 들어 있음) | 100% 보장 | P0 | 0.5h |
| A4 | **RAG retrieval — keyword vs ChromaDB** | ChromaDB 의미 검색 우선 + 키워드 fallback (rag_retriever.py) | k=3 고정. 일부 한국어 쿼리는 점수 < 0.2로 떨어져 키워드로 보강됨 → 결과 품질 흔들림 | k=5로 늘리고 상위 3건만 LLM에 전달, MMR(다양성) 필터 추가. 또는 임베딩 모델을 **`jhgan/ko-sroberta-multitask`** 로 교체 (한국어 특화) | RAG hit 품질 + 의미 검색 활성화 비율↑ | P1 | 3h |
| A5 | **gpt-oss:20b 폴백 정책** | 현재 RAM 부족 자동 fallback → llama3.1:8b 동작 | 의도된 동작이나 사용자가 보면 "왜 20b 안 쓰지?" 혼란. CPU에서 8B도 100초 소요 | `.env` 디폴트를 `llama3.1:8b`로 변경 + V-8 우측 KB 패널에 "현재 모델: llama3.1:8b (사유: 시연 노트북 RAM 16GB)" 표시 | 일관된 시연 + 사용자 혼란 제거 | P0 | 1h |
| A6 | **응답 시간 100초+ UX** | 첫 응답까지 약 100초 (CPU + llama3.1:8b) | V-8에 "로딩…" 만 표시 → 사용자가 멈춘 줄 알고 다시 입력 시도 | (1) 스트리밍 응답(`stream=true`) 적용 → 토큰 단위 표시 (2) "예상 응답 시간: 90초" 안내 (3) `LLM_NUM_PREDICT=300`로 단축 | 체감 응답 시간 1/3 | P1 | 4h |
| A7 | **brief/suggest/playbook 프롬프트 검토** | `brief`는 LLM 미사용(KB 직접 인용), `suggest`/`playbook`도 깡통 | brief는 결정론적 검색이라 안전한데 매번 같은 톤. suggest는 LLM에 위임 시 가치↑ | brief에 `LLMEngine.generate()` 호출 1줄 추가 (KB 청크 → 자연어 요약), `suggest`도 LLM 옵션화 | V-5 브리핑이 생동감 있게 변함 | P2 | 4h |
| A8 | **chat 세션 메모리 한도** | `ChatSession`이 메모리 누적 (서버 인메모리) | 장시간 시연 시 누적 → 토큰 폭증 → 응답 더 느려짐 | 최근 N=6 메시지만 LLM 컨텍스트에 전달 (`chat_session.py::history()` 슬라이스) | 안정성↑ | P2 | 1h |

**시연 직전 필수(P0): A1+A2+A3+A5 = ~4h** (프롬프트 1줄·후처리·.env 변경만 — 코드 변경 최소)

---

## 4. 권장 시연 직전 작업 순서 (이번 주)

1. **A5** `.env` LLM_MODEL → `llama3.1:8b` (5분) — 시연 안정성 즉시 ↑
2. **A1+A2+A3** 시스템 프롬프트 1회 수정 + 응답 후처리 (3h) — 가장 자주 보이는 오답 제거
3. **D1+D2** KB 3→12 청크, v1 시드 2→10 파일 (9h) — 시연 시나리오 B(NHN COLLECTION 복귀)가 다른 사고유형에서도 작동
4. **C1** V-4 갭 결과를 V2 매트릭스에 되돌려 표시 (4h) — 시연 임팩트 차별화

**총 P0 작업량: ~16h (2~3일)**

이후 회의 결정에 따라 D3·D5·A4·A6 등 P1 항목을 1~2주 내 처리하면 학술 변호와 시연 다양성이 동시에 강화된다.
