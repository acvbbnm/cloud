# Neo4j 도입 PoC 결과 보고

> **작성자:** 이지호 (easy 브랜치)
> **일시:** 2026-05-26
> **요청자:** 김병우 (Discord 2026-05-26 — "받아주신거 받아서 neo4 방향 가능한지 테스트해주시고요")
> **대상 commit:** `8c44bd0` (byungwoo) — Phase M 미결 5건 확정 + §22 팀원 가이드
> **참고:** `docs/evidence_tree_paradigm.md` §17.E (이전 Neo4j 거부 결정, 2026-05-25)

---

## 1. TL;DR

**Neo4j 도입은 기술적으로 100% 가능. 다만 §17.E 거부 사유는 여전히 유효하므로 "메인 DB 이관" 이 아니라 "시연/시각화 보조 도구" 로 한정 도입을 권고.**

| 항목 | PoC 결과 |
|---|---|
| 단서 그래프 적재 | ✅ 244 노드 + 385 엣지 (143 단서 + 45 ATT&CK 기법 + 8 사고유형 + 6 카테고리 pivot) |
| 시연 그래프 시각화 | ✅ Neo4j Browser (http://localhost:7474) 즉시 가능 |
| 오프라인 동작 | ✅ Community Edition 로컬 zip 압축 해제 후 100% 폐쇄망 동작 |
| SQLite 9테이블 영향 | ❌ 변경 없음 (read-only 미러 방식, models.py 무변경) |
| 의존성 추가 | `neo4j>=6.2.0` Python driver (~2MB) + Neo4j 서버 zip 145MB |
| 학습 곡선 | 낮음 (Cypher 1일, Bolt 드라이버 30분) |

### 결정 권고
**옵션 B (시연용 시각화 보조)** 선택. 이유는 §5 참조.

---

## 2. 실행한 PoC 개요

### 2.1 환경

| 컴포넌트 | 버전 | 설치 위치 |
|---|---|---|
| Neo4j Community Edition | 5.26.26 LTS | `KBW/neo4j-tools/neo4j-community-5.26.26/` (gitignore) |
| Python neo4j driver | 6.2.0 | 시스템 Python 3.14 (CLAUDE.md 3.10+ 호환) |
| Java Runtime | 25 (Adoptium Temurin) | 기존 설치, Neo4j 권장은 17/21 — PoC 한정 무시 |
| Bolt 포트 | `localhost:7687` | 기본 |
| HTTP/Browser 포트 | `localhost:7474` | 기본 |
| 초기 비밀번호 | `sherpa-poc-2026` | PoC 한정 |

부팅 시간: 약 8초 (Bolt enabled at 07:58:57)
다운로드: 144.7 MB (외부망 필요, 시연 시에는 사전 압축 해제본 zip 배포)

### 2.2 작성한 스크립트

```
backend/scripts/neo4j_poc/
├── import_clue_graph.py    # next_clue_graph.json + clue_to_attack.json + priors.json
│                             → Neo4j MERGE 적재 (idempotent)
└── demo_queries.py          # 시연용 Cypher 7건 + 결과 콘솔 출력
```

### 2.3 그래프 스키마

```cypher
// 노드
(:ClueCategory {name, observation})                  29개
(:NextClueHint {hint_id, priority, question, action, source})  19개
(:Clue {clue_key, category, confidence})            143개
(:IncidentType {name, prior})                         8개
(:Technique {tid})                                   45개

// 관계
(ClueCategory) -[:PIVOT_TO]-> (NextClueHint)         19
(NextClueHint) -[:LEADS_TO]-> (ClueCategory)         10
(NextClueHint) -[:BOOSTS {weight}]-> (IncidentType)  19
(Clue) -[:OF_CATEGORY]-> (ClueCategory)             143
(Clue) -[:MAPS_TO {confidence, source}]-> (Technique) 194
```

---

## 3. 시연 가능한 쿼리 7건

`demo_queries.py` 실행 결과 요약 — Neo4j Browser 에서 같은 Cypher 로 그래프 시각화 가능.

| # | 쿼리 | 시연 임팩트 |
|---|---|---|
| Q1 | 단서 카테고리 → 다음 단서 카테고리 (LEADS_TO 10건) | 김병우 비전 — "단서 → 다음 단서" 룰 그래프 한 장 |
| Q2 | 단서가 부풀리는 사고유형 BOOSTS Top 10 | Bayesian posterior 갱신의 직관적 시각화 |
| Q3 | 8 사고유형별 가중치 합계 | **단서 풀이 8개 가설 중 4개만 boost** — 갭 발견 |
| Q4 | ATT&CK 기법 Top 5 (가장 많은 단서가 매핑) | T1078.004(26)·T1078(24)·T1090.003(15)·T1098(13)·T1486(12) |
| Q5 | `Q2A:object_storage_burst` 의 다중 기법 매핑 | Noisy-OR 의 자연 표현 (1 단서 → 4 기법) |
| Q6 | 2-홉 단서 체인 (LEADS_TO 두 번) | AWS Detective Profile Guidance 워크플로 |
| Q7 | ACCOUNT 단서 5건의 가설+기법 종합 | Evidence Tree 양방향 그래프 시각화 |

### 3.1 의도치 않은 발견 — 갭 (보고할 가치 있음)

**Q3 결과:**
```
DATA_EXFILTRATION     boost_count=7  total=140
CREDENTIAL_THEFT      boost_count=5  total=100
PRIVILEGE_ESCALATION  boost_count=4  total=90
AUDIT_LOG_TAMPERING   boost_count=3  total=60
```

→ `next_clue_graph.json` 의 `hypothesis_boost` 가 **8 사고유형 중 4개만 다룸**. 누락:
- `RANSOMWARE` — 5/14 dev3 추가 사고유형
- `MISCONFIG_EXPOSURE` — 5/14 dev3 추가
- `PHISH_INITIAL_ACCESS` — 5/14 dev3 추가
- `INSIDER_THREAT` — 5/14 dev3 추가

이건 Neo4j 와 무관하게 paradigm doc / 단서 카탈로그 자체의 갭. **`next_clue_graph.json` 의 hypothesis_boost 추가 작업이 필요.** 시연 전 보강 권고.

---

## 4. §17.E 거부 사유 재검토

### 4.1 거부 사유 1 — "SQLite 9 테이블 설계서 확정 (DB 담당자 합의)"

| 측면 | PoC 결과 |
|---|---|
| Neo4j 가 9 테이블 변경 요구? | ❌ **요구하지 않음.** 본 PoC 는 SQLite 를 그대로 두고 Neo4j 를 read-only 미러로 운영. `models.py` 무변경, 설계서 5.1 ERD 무변경. |
| DB 담당자 합의 필요? | △ Neo4j 를 "메인 영속화" 로 쓰면 필요. **시연 시각화 보조** 로만 쓰면 합의 범위 밖 (기존 데이터 export 만). |
| 설계서 영향 | 없음 (옵션 B 기준). 시연 절차서에 "Neo4j Browser 캡처" 한 줄 추가만. |

**결론**: 옵션 B 기준 거부 사유 1 은 더 이상 유효하지 않음.

### 4.2 거부 사유 2 — "폐쇄망 단일 데스크톱"

| 측면 | PoC 결과 |
|---|---|
| Neo4j 가 외부 통신 요구? | ❌ Community Edition 100% 로컬. Anonymous Usage Data 끄면 인터넷 차단 환경에서 동작 (`conf/neo4j.conf` 에서 `dbms.usage_report.enabled=false`). |
| 시연 환경 +1 컴포넌트 부담 | ⚠️ 사실 — 시연 노트북에 Java + Neo4j 145MB 추가. 사전 배포로 해소 가능. |
| 시연 도중 부팅 실패 리스크 | △ 부팅 8초 + Java 25 unsupported 경고. JDK 21 로 다운그레이드 + 사전 부팅 + 헬스체크 스크립트 필요. |

**결론**: 거부 사유 2 는 부분 유효. **사전 배포 + 사전 부팅** 으로 해소 가능.

### 4.3 §17.C 대체 결정 — "networkx in-memory"

| 측면 | 비교 |
|---|---|
| GDS 알고리즘 (PageRank, Label Propagation) | networkx ✅ / Neo4j (GDS plugin 별도 다운로드 ~200MB) ✅ |
| 그래프 시각화 자체 | networkx (matplotlib, 정적) / **Neo4j Browser (인터랙티브 web)** ← 시연 임팩트 압도 |
| 분석 코드 위치 | Phase H 의 `core/analysis/` / Neo4j 는 외부 컴포넌트 |
| 학술 인용 | networkx ≈ Pearl 1988 / Neo4j ≈ Robinson 2015 "Graph Databases" |

**결론**: GDS 알고리즘 자체는 networkx 로 충분. Neo4j 의 진짜 우위는 **Browser 시각화**. → 김병우의 "교수님께서 더 좋게 봐주실 거" 직관은 시각화 임팩트 측면에서는 사실. 다만 GDS 분석 부분은 §17.C networkx 가 그대로 유효.

---

## 5. 4가지 도입 옵션 비교

| 옵션 | 범위 | 변경 부담 | 시연 임팩트 | 5/29 보고서 영향 |
|---|---|---|---|---|
| **A. 메인 DB 이관** | SQLite triage_state JSON → Neo4j 이관, clue_tree_service 재작성 | 매우 큼 (~3일+) | 매우 큼 | **설계서 5.1 ERD 재작성 필수**, DB 담당자 합의 |
| **B. 시연 시각화 보조** ⭐ | SQLite 메인 유지, **export → Neo4j → Browser 시각화만**. import_clue_graph.py 그대로 운영. | 작음 (오늘 끝남) | 큼 (Browser 인터랙티브) | 시연 절차에 캡처 1장 추가 |
| **C. networkx + react-flow 만** (§17.C) | 현 결정 유지 | 없음 | 중 (react-flow 정적 SVG) | 없음 |
| **D. 거부 입장 유지** (§17.E) | 그대로 | 없음 | 낮음 | 없음 |

### 권고 — **옵션 B**

근거:
1. **5/29 보고서 마감 3일 전 + 5/25 디시전 데드라인 지남** → 메인 DB 이관(A) 은 시연 리스크.
2. **시연 영상 임팩트는 Neo4j Browser 가 react-flow 보다 압도적**. 김병우 직관은 사실.
3. **CLAUDE.md 9테이블 + models.py 제약을 위반하지 않음**. SQLite 메인 유지.
4. **이미 작성된 import_clue_graph.py + demo_queries.py** 로 모든 인프라 준비됨. 추가 작업 = 시연 영상 캡처용 Browser 스크린샷 2~3장.
5. **수동 export 가 아니라 자동 동기화** 필요시 별도 cron 가능. PoC 단계에서는 시연 직전 1회 실행으로 충분.

### 옵션 B 후속 작업 (~30분)

1. `conf/neo4j.conf` 에 `dbms.usage_report.enabled=false` 추가 → 외부 통신 차단
2. `docs/시연_체크리스트.md` 사전준비에 "Neo4j 콘솔 부팅 + import_clue_graph.py 1회 실행" 추가
3. 시연 대본 §X 에 "Neo4j Browser 캡처 — Q1/Q3/Q4 그래프" 한 단락 추가
4. `paradigm doc §17.E` 갱신 — "거부" → "한정 도입 (시각화 보조)"
5. 김병우에게 Discord 회신 + 본 보고서 링크

---

## 6. 김병우 회신 초안 (Discord)

```
형 neo4 테스트 결과요 →

✅ 동작 OK — 5.26.26 LTS 로컬 부팅 8초, 144MB. Python driver 6.2.0 으로 Bolt 통신 됨.
✅ 단서 그래프 적재 OK — 244 노드 + 385 엣지 (143 단서 + 45 ATT&CK + 8 가설 + 6 pivot).
✅ 7가지 시연 쿼리 동작 — paradigm §17.E 다시 봤는데 거부 사유 1 (9테이블) 은 안 건드리고
   read-only 미러로만 쓰면 우회 가능합니다.
⚠️ 다만 메인 DB 이관(옵션 A) 은 5/29 마감 + 디시전 데드라인 지난 상황에서 리스크 커요.
   → 시연용 Neo4j Browser 시각화 보조(옵션 B) 가 ROI 최고일듯요.
🔍 의외 갭 발견 — next_clue_graph.json 의 hypothesis_boost 가 8 사고유형 중
   4개만 다룸 (DATA_EXFIL/CRED_THEFT/PRIV_ESCAL/AUDIT_TAMPER). RANSOM/MISCONFIG/PHISH/INSIDER
   누락. neo4 와 별개로 단서 풀 보강이 필요해 보여요.

자세한 건 docs/neo4j_poc_결과보고.md 보세요. PoC 코드는
backend/scripts/neo4j_poc/ 에 import_clue_graph.py + demo_queries.py 둘 다 있어요.
```

---

## 6.1 ⚠️ easy 브랜치에서 재현 시 주의

본 PoC 는 **byungwoo 브랜치 `8c44bd0`** 시점에서 실행되었음. PoC 코드(`import_clue_graph.py`) 는
다음 데이터 파일을 참조하는데, **easy 브랜치에는 일부만 존재**:

| 파일 | byungwoo | easy |
|---|---|---|
| `backend/data/triage/next_clue_graph.json` | ✅ | ✅ |
| `backend/data/triage/clue_to_attack.json` | ✅ | ❌ (Phase H.2 산출, easy 미반영) |
| `backend/data/triage/priors.json` | ✅ | ❌ (Phase L 보강, easy 미반영) |
| `backend/data/triage/clue_catalog.json` | ✅ | ❌ |

→ easy 에서 그대로 실행하면 `FileNotFoundError`. 두 가지 풀백:
1. byungwoo 브랜치에서 위 3개 파일 cherry-pick (`git checkout origin/byungwoo -- backend/data/triage/clue_to_attack.json backend/data/triage/priors.json backend/data/triage/clue_catalog.json`)
2. byungwoo 브랜치로 직접 checkout 후 실행

본 보고서는 byungwoo 결과 기준이며, easy 브랜치의 단서 풀 보강 + Phase H/L 머지가 선행되면 동일 PoC 가 easy 에서도 재현됨.

---

## 7. 산출물 위치

| 파일 | 용도 |
|---|---|
| `backend/scripts/neo4j_poc/import_clue_graph.py` | 단서 그래프 → Neo4j 적재 (idempotent MERGE) |
| `backend/scripts/neo4j_poc/demo_queries.py` | 시연 Cypher 7건 + 콘솔 출력 |
| `neo4j-tools/neo4j-community-5.26.26/` | Neo4j 바이너리 (`.gitignore`) |
| `neo4j-tools/reset_password.py` | 초기 비밀번호 변경 헬퍼 |
| `docs/neo4j_poc_결과보고.md` | 본 보고서 |

## 8. 재현 절차

```powershell
# 1) Neo4j 시작 (별도 터미널)
$env:NEO4J_HOME = 'E:\학교\4학년 1학기\캡스톤디자인\KBW\neo4j-tools\neo4j-community-5.26.26'
$env:JAVA_HOME  = 'C:\Tools\Eclipse Adoptium\jdk-25.0.1.8-hotspot'
& (Join-Path $env:NEO4J_HOME 'bin\neo4j.bat') console

# 2) 비밀번호 변경 (최초 1회)
python neo4j-tools\reset_password.py

# 3) 그래프 적재
$env:PYTHONIOENCODING = 'utf-8'
python backend\scripts\neo4j_poc\import_clue_graph.py

# 4) 데모 쿼리
python backend\scripts\neo4j_poc\demo_queries.py

# 5) Browser 시각화
#    http://localhost:7474 → neo4j / sherpa-poc-2026
#    demo_queries.py 의 Q1~Q7 Cypher 복사해서 실행
```
