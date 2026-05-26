# Neo4j 재현 가이드 — 단서 그래프 시각화 (옵션 B)

> **목적**: paradigm doc §17.E "한정 도입 (시연용 시각화 보조)" 정합. 팀원이 본인 노트북에 Neo4j 를 띄우고 PoC 적재본을 Browser 로 확인.
>
> **출처**: 이지호(easy) Discord 가이드 + byungwoo 6 보완점 통합.
>
> **상태**: easy `3aa5879` 산출물 기준 · byungwoo 데이터 (`clue_to_attack.json`/`priors.json`/`clue_catalog.json`) 필요 (이미 보유 시 cherry-pick 불필요).
>
> **소요**: 첫 회 약 15분 (zip 다운로드 + JDK 설치 포함). 두 번째부터 ~3분 (부팅 + 적재).

---

## 0. 개요 — 무엇을 하는가

| 항목 | 값 |
|---|---|
| Neo4j 역할 | 시연 영상 Browser 캡처 + 발표 자료 그래프 시각화만 |
| 메인 영속화 | SQLite 9 테이블 (변경 0). `models.py` 무변경, 설계서 5.1 ERD 무변경 |
| 적재 데이터 | 단서 카탈로그 143 + ATT&CK 기법 45 + 사고유형 8 + 카테고리 6 |
| 그래프 크기 | 244 노드 + 385 엣지 (`docs/neo4j_poc_결과보고.md` §2.3) |
| 양방향 동기화 | 없음. 시연 직전 `import_clue_graph.py` 1회 단방향 export |
| 앱 런타임 의존 | 0건. Neo4j 죽어도 메인 V-1 → V-8 시스템 정상 |

---

## 1. 사전 요구사항

| 항목 | 값 |
|---|---|
| OS | Windows 10/11 (영문 경로 강제) |
| Python | **3.10+** (3.14 사용 검증됨, CLAUDE.md 호환) |
| Java | **JDK 17 또는 21 권장** · JDK 25 동작은 함 (Neo4j unsupported 경고) |
| 디스크 여유 | ~200 MB (Neo4j 145MB + Java 200MB + DB 데이터) |
| 외부망 | **최초 다운로드 시점만 필요**. 이후 폐쇄망 OK |

### 1-1. JDK 설치 (없을 때만)

[Eclipse Adoptium Temurin 21](https://adoptium.net/temurin/releases/?version=21) — Windows x64 MSI 권장.

설치 후 PowerShell:

```powershell
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-21.0.5.11-hotspot'
# 본인 설치 경로로 — Get-ChildItem 'C:\Program Files\Eclipse Adoptium\' 로 확인
& "$env:JAVA_HOME\bin\java.exe" -version
# → openjdk version "21.0.x" 등 출력되면 OK
```

영구 적용: 시스템 환경변수 `JAVA_HOME` 추가 + `PATH` 에 `%JAVA_HOME%\bin` 추가.

---

## 2. Neo4j Community Edition 5.26.26 설치

### 2-1. 다운로드 (~144.7 MB)

https://dist.neo4j.org/neo4j-community-5.26.26-windows.zip

> ⚠️ Neo4j 5.x LTS 마지막 마이너. 6.x 는 라이선스/API 변화 — PoC 코드는 **5.x 전제**.

### 2-2. 압축 해제

**반드시 영문 경로**. 예시: `C:\neo4j-poc\`

```powershell
# PowerShell 예시 (다운로드 zip 위치 = 본인 다운로드 폴더)
Expand-Archive -Path "$env:USERPROFILE\Downloads\neo4j-community-5.26.26-windows.zip" `
               -DestinationPath C:\neo4j-poc-tmp\
Move-Item C:\neo4j-poc-tmp\neo4j-community-5.26.26 C:\neo4j-poc
Remove-Item C:\neo4j-poc-tmp -Recurse
```

> ❌ **한국어 경로 금지** — `C:\Users\사용자\` 등이면 Java 가 `conf` 파일 못 읽어서 Browser UI 가 안 뜸. 한글 ID 폴더면 `C:\neo4j-poc\` 같은 영문 디렉토리로 분리 권장.

### 2-3. Browser UI 압축 해제 (5.26 특이사항, 이지호 발견)

5.26 빌드는 Browser 가 별도 zip 으로 packaged 됨:

```powershell
# C:\neo4j-poc\web\ 안에 neo4j-browser-2026.05.11+0.zip 같은 파일 있으면:
$webZip = Get-ChildItem C:\neo4j-poc\web\*.zip | Select-Object -First 1
if ($webZip) {
  Expand-Archive -Path $webZip.FullName -DestinationPath C:\neo4j-poc\web\ -Force
  # → C:\neo4j-poc\web\browser\index.html 생성 확인
  Test-Path C:\neo4j-poc\web\browser\index.html
}
```

> 본인 환경에서 zip 파일이 없거나 `web\browser\index.html` 가 이미 있으면 이 단계 skip. **재확인 부탁** — 이 단계는 easy 환경 특수 케이스일 수도 있음.

### 2-4. 폐쇄망 통신 차단 (paradigm §17.E 정합)

`C:\neo4j-poc\conf\neo4j.conf` 끝에 추가:

```ini
# Anonymous Usage Data 비활성 (폐쇄망 시연 정합)
dbms.usage_report.enabled=false
```

> 외부 통신 차단 — Neo4j 가 기본으로 익명 통계 데이터를 전송하는데 폐쇄망에선 hang 유발 가능. PoC 보고서 §5 후속 #1.

---

## 3. Neo4j 부팅

### 3-1. 콘솔 모드 (시연 권장)

별도 PowerShell 창에서:

```powershell
$env:NEO4J_HOME = 'C:\neo4j-poc'
$env:JAVA_HOME  = 'C:\Program Files\Eclipse Adoptium\jdk-21.0.5.11-hotspot'  # 본인 경로
& "$env:NEO4J_HOME\bin\neo4j.bat" console
```

### 3-2. 부팅 완료 확인

다음 메시지가 뜨면 OK:

```
Started.
Bolt enabled on localhost:7687.
HTTP enabled on localhost:7474.
```

> ⚠️ 이 메시지 뜨기 전에 `reset_password.py` 돌리면 `ConnectionRefusedError`. **반드시 "Bolt enabled" 메시지 대기**. 보통 ~8초.

---

## 4. 데이터 적재

### 4-1. PoC 스크립트 받기

`backend/scripts/neo4j_poc/` 가 본인 브랜치에 없으면:

```powershell
git fetch origin
git checkout origin/easy -- backend/scripts/neo4j_poc/
# → import_clue_graph.py / demo_queries.py / reset_password.py 3개 받음
```

> byungwoo 브랜치에는 이미 6d66cf3 commit 으로 포함. dev3 / geunhyung 브랜치는 위 명령 필요.

### 4-2. byungwoo 데이터 cherry-pick (easy / 구버전 브랜치만)

본인 브랜치에 다음 3 파일이 있는지 확인:

```powershell
Test-Path backend/data/triage/clue_to_attack.json    # Phase H.2 산출
Test-Path backend/data/triage/priors.json             # Phase L 보강
Test-Path backend/data/triage/clue_catalog.json       # Phase A 산출
```

셋 다 True 면 skip. 하나라도 False 면:

```powershell
git checkout origin/byungwoo -- backend/data/triage/clue_to_attack.json `
                                 backend/data/triage/priors.json `
                                 backend/data/triage/clue_catalog.json
```

> ✅ **byungwoo 브랜치 본인**: 위 3개 모두 보유 — cherry-pick 불필요.
> ❌ **easy / dev3 / geunhyung**: cherry-pick 필요.

### 4-3. Python neo4j driver 설치

```powershell
pip install "neo4j>=6.2.0"
# 또는 백엔드 venv 안에서:
cd cloud\backend
.venv\Scripts\python.exe -m pip install "neo4j>=6.2.0"
```

> ⚠️ `requirements.txt` 에 미포함 (PoC 단계). 본격 통합 시 추가 검토.

### 4-4. 비밀번호 초기화 (최초 1회만)

Neo4j 5.x 는 첫 부팅 시 `neo4j/neo4j` 가 expired 상태로 잡혀서 강제 변경 필요:

```powershell
cd cloud
.venv\Scripts\python.exe backend\scripts\neo4j_poc\reset_password.py
# → 비밀번호 'sherpa-poc-2026' 으로 설정
```

> 한 번 변경 후엔 같은 비번 그대로 — 재실행 불필요. DB 디렉토리 삭제 시에만 다시 실행.

### 4-5. 그래프 적재

```powershell
$env:PYTHONIOENCODING = 'utf-8'
.venv\Scripts\python.exe backend\scripts\neo4j_poc\import_clue_graph.py
```

기대 출력:

```
[ClueCategory] MERGE 6
[NextClueHint] MERGE 19
[Clue]         MERGE 143
[IncidentType] MERGE 8
[Technique]    MERGE 45
[PIVOT_TO]     19  [LEADS_TO]   10  [BOOSTS]   19
[OF_CATEGORY]  143 [MAPS_TO]    194
Total: 244 nodes + 385 relationships
```

`MERGE` 라 idempotent — 여러 번 돌려도 중복 없음.

---

## 5. Browser 사용

### 5-1. 접속

http://localhost:7474/browser/

| 항목 | 값 |
|---|---|
| Connect URL | `neo4j://localhost:7687` (또는 `bolt://localhost:7687`) |
| Username | `neo4j` |
| Password | `sherpa-poc-2026` |
| Database | `neo4j` (기본) |

> `bolt://` 는 단일 노드 직접 연결, `neo4j://` 는 routing 가능. PoC 단일 노드라 둘 다 동작.

### 5-2. 시연 쿼리 (`demo_queries.py` Q1~Q7)

좌측 상단 `$` 입력 박스에 Cypher 복사 → Ctrl+Enter:

| Q# | 시연 임팩트 |
|---|---|
| Q1 | LEADS_TO 룰 그래프 — 단서 → 다음 단서 (Discord 김병우 비전 직접 시각화) |
| Q3 | 8 사고유형별 boost 합계 — Bayesian posterior 강도 |
| Q4 | ATT&CK 기법 Top 5 — T1078.004 / T1078 / T1090.003 / T1098 / T1486 |

> Q1·Q3·Q4 가 시연 영상 캡처 후보. 시연 대본 `docs/시연_대본.md` §4-A 참조.

### 5-3. Cypher 콘솔 출력 (Browser 없이도 확인 가능)

```powershell
.venv\Scripts\python.exe backend\scripts\neo4j_poc\demo_queries.py
# → 7 쿼리 결과 콘솔 출력 (Browser 안 띄울 때 대안)
```

---

## 6. 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `Bolt enabled` 메시지 안 뜸 | JDK 미설치 / JAVA_HOME 오타 | `& "$env:JAVA_HOME\bin\java.exe" -version` 확인 |
| `conf 파일 읽기 실패` | 한국어 경로 | 영문 경로 (`C:\neo4j-poc`) 로 이동 |
| `ConnectionRefusedError` (reset_password) | Bolt 부팅 전 실행 | "Bolt enabled" 메시지 후 재실행 |
| Browser http://localhost:7474 안 뜸 | `web/browser/index.html` 없음 | §2-3 web zip 압축 해제 단계 확인 |
| `Authentication failure` | `reset_password.py` 미실행 또는 DB 초기화 후 재실행 미수행 | `reset_password.py` 1회 실행 |
| Q1 결과 0건 | `import_clue_graph.py` 미실행 또는 부분 실행 | `import_clue_graph.py` 재실행 (idempotent) |
| `FileNotFoundError: clue_to_attack.json` | easy/dev3 브랜치에서 데이터 미보유 | §4-2 cherry-pick |
| Neo4j 가 외부 통신 시도 | `usage_report.enabled` true | §2-4 conf 추가 |

---

## 7. 정리 / 폐기

PoC 종료 후 디스크 회복:

```powershell
# Neo4j 프로세스 종료 (콘솔 모드면 Ctrl+C)
# DB 데이터 삭제 (필요 시)
Remove-Item C:\neo4j-poc\data\databases\neo4j -Recurse
# 전체 폐기
Remove-Item C:\neo4j-poc -Recurse
```

`reset_password.py` 비밀번호는 PoC 한정 + 로컬 단일 노드 + 폐쇄망 → 폐기 후 별도 secret 정리 불필요.

---

## 8. 관련 문서

- `docs/neo4j_poc_결과보고.md` — 4 옵션 비교 + 옵션 B 권고 배경
- `docs/evidence_tree_paradigm.md` §17.E — 한정 도입 정책
- `docs/시연_대본.md` §4-A — Browser 캡처 시연 단락
- `docs/시연_체크리스트.md` §0·§8 — 사전준비 + 시연 직전 점검
- `backend/scripts/neo4j_poc/` — PoC 산출물 3개

---

## 9. 결정 권고 (paradigm §17.E 정합)

- ✅ **메인 영속화 SQLite 유지** — 9 테이블 ERD 변경 없음
- ✅ **시연 영상 Browser 캡처만** — 발표 임팩트 보조
- ✅ **시연 직전 1회 import** — 양방향 동기화 X
- ❌ **메인 DB 이관 (옵션 A) 금지** — 설계서 변경 + 5/29 마감 리스크

본 가이드 절차로 1회 부팅 후, Browser Q1·Q3·Q4 캡처 3장이 시연 영상에 포함되면 옵션 B 목표 달성.
