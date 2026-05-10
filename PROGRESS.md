# AI Sherpa — 진행 현황

> 마지막 업데이트: 2026-05-11 · 브랜치: `dev`
> 이 문서는 **팀이 같은 그림을 보기 위한 작업 메모**입니다. 작업 시작 전·종료 후 갱신해 주세요.

---

## 한눈에 보기

| 계층 | 화면/모듈 | 프론트엔드 | 백엔드 | 데이터 |
|---|---|---|---|---|
| Layer 0 | V1 사고 접수 (4-스텝 위저드) | ✅ UI 완료 | ⏳ scaffolding | 🎭 mock |
| Layer 1 | V2 로그 수집 (드롭존 + 미리보기) | ✅ UI 완료 | ⏳ scaffolding | 🎭 mock |
| Layer 2 | V3 OCSF 정규화 | ✅ UI 완료 | ⏳ scaffolding | 🎭 mock |
| Layer 2 | V4 갭 감지 | ✅ UI 완료 | ⏳ scaffolding | 🎭 mock |
| Layer 3 | V5 수사 보드 (드래그앤드롭) | ✅ UI 완료 | ⏳ scaffolding | 🎭 mock |
| Layer 3 | V6 ATT&CK 매핑 | ✅ UI 완료 | ⏳ scaffolding | 🎭 mock |
| Layer 4 | V7 보고서 편집기 | ✅ UI 완료 | ⏳ scaffolding | 🎭 mock |
| 보조 | V8 AI 셰르파 RAG 챗 | ✅ UI 완료 | ⏳ scaffolding | 🎭 mock |
| 공통 | 디자인 시스템 + 라우팅 + 스토어 | ✅ 완료 | — | — |
| DB | `db/models.py` 9개 테이블 | — | ⚠️ 설계서와 불일치 다수 | — |

범례: ✅ 완료 · 🚧 진행 중 · ⏳ 대기 · 🎭 mock 데이터 사용 · ⚠️ 합의 필요

---

## 작업 내역

### 2026-05-11 — 프론트엔드 V1~V8 + 디자인 시스템 (`a6e76b7`)
- **디자인 토큰화**: ink 9단계 + brand 6컬러(blue/violet/teal/amber/red/purple) + display/h1/h2/h3 타이포 + cta-gradient/hero-gradient
- **셸 컴포넌트 신규**: Header, Sidebar, PageHeader, PageBody, Card, KpiCard, Badge, Toast, SherpaFab
- **Zustand 스토어 3종**: `useToastStore`, `useSherpaStore`, `useBoardStore`
- **V1~V8 모든 화면 구현**:
  - V1: CSP 선택 → 사고 유형(컨텍스트 패널) → 시스템 구성(4탭) → 수집 가이드(P1~P4 우선순위)
  - V2: 멀티 파일 드롭존 + 수집 현황 + 체크 가능 미리보기 + "수사 보드에 추가"
  - V3: 샘플 셀렉터 + RAW vs OCSF 양면 비교 + 필드 매핑 표
  - V4: 도넛 KPI + 3종 갭 카드(수집/증거/해석) + 증거 항목 테이블
  - V5: dot-grid 캔버스 + 로그 드래그앤드롭 + 추천 노드 + AI 브리핑 + 메모
  - V6: ATT&CK Cloud Matrix 히트맵 + 탐지 기법 상세 테이블
  - V7: 6 섹션 textarea 편집기 + AI 초안 / DOCX / PDF 내보내기 버튼
  - V8: RAG 풀-페이지 챗 + 추천 플레이북 + KB 인덱스
- **모든 페이지에 PageHeader 패턴 적용** (eyebrow + 큰 타이틀 + 설명 + 액션)

### 2026-05-10 — 프로젝트 초기 구조 + 협업 가이드 (`5c7b8e3`)
- `CLAUDE.md` 규칙 정의 (디렉토리 구조 / 네이밍 / API 응답 형식 / DB 모델 규칙)
- `backend/`, `frontend/` scaffolding
- `.gitignore`, `.gitattributes`

---

## 다음 할 일

### 백엔드 (이근형 · 최진규 · 백엔드 담당자)
- [ ] **DB 스키마 합의**: 설계서 5.2절 vs 현재 `db/models.py` 불일치 → 팀 합의 후 마이그레이션
- [ ] **Layer 0 API**:
  - `POST /api/cases` — 케이스 생성
  - `GET /api/cases/{caseId}` — 케이스 상세
  - `GET /api/guide?caseId=` — 수집 가이드 자동 생성
- [ ] **Layer 1 API**:
  - `POST /api/logs/upload` (multipart) — 파일 업로드 + SHA-256 검증
  - `GET /api/logs?caseId=&page=` — 이벤트 페이지네이션
- [ ] **Layer 2~4 API**: 설계서 5.6절 22개 엔드포인트 순차 구현
- [ ] `data/mapping_rules/`, `data/attack_rules/`, `data/kb/` JSON 파일 채우기

### 프론트엔드 (담당자: ?)
- [ ] **Mock → 실 API 연결**: `api/intake.ts` 패턴을 V2~V8 전부에 적용
  - `api/logs.ts`, `api/analysis.ts`, `api/board.ts`, `api/report.ts`, `api/sherpa.ts` 신규 파일 생성
  - 각 뷰의 mock 상수를 React Query 훅으로 교체
- [ ] **에러 / 로딩 상태 처리**: 현재 모든 데이터가 즉시 표시됨 → Skeleton, Error Boundary 추가 필요
- [ ] **react-router 경로 가드**: caseId 없이 V2~V7 진입 시 V1로 리다이렉트
- [ ] **반응형 점검**: 1024px 이하 사이드바 토글 미구현
- [ ] **접근성**: 키보드 네비게이션, aria-label, 다이얼로그 focus trap

### 데이터 / 지식베이스
- [ ] OCSF 1.3 매핑 규칙 JSON 작성 (NCP·NHN 각각)
- [ ] ATT&CK Cloud v14 매핑 룰 JSON 작성
- [ ] KB-1~KB-4 (사고 유형 / 수집 카탈로그 / 플레이북 / 보고서 양식) 작성

---

## 알려진 제약 / 이슈

- **`models.py` ↔ 설계서 5.2절 불일치**: DB 담당자(이근형·최진규)가 정리 중. 변경 시 팀 합의 필수.
- **`types/index.ts`는 백엔드 enum과 정확히 일치해야 함**: `IncidentType`(5종) / `CSP`(naver/nhn/all) / `Severity` / `EvidenceRole` / `GapType` / `NodeStatus` / `ActionType`. 임의 변경 금지.
- **외부 CDN 사용 금지** (오프라인 SNF-01): 폰트·아이콘·라이브러리 모두 로컬 번들.
- **AI는 판단/결정 코드 작성 금지**: 검색·요약·제안만. 수락/거부는 항상 수사관 권한.
- **현재 frontend 데이터는 모두 mock**: 시연용 더미 데이터로 가짜 흐름이 동작합니다. 실 사고 분석에는 백엔드 연결 필수.

---

## 디자인 시스템 메모 (frontend)

### 컬러 토큰 (`tailwind.config.js`)
- 배경: `bg-ink-950` (페이지) / `bg-ink-900` (헤더·사이드바) / `bg-ink-850`·`panel-gradient` (카드)
- 텍스트: `text-ink-100` (주) / `text-ink-300` (보조) / `text-ink-400` (캡션)
- 액센트: `brand-blue`(주 CTA) / `brand-teal`(성공·완료) / `brand-amber`(경고) / `brand-red`(위험) / `brand-purple`(MITRE·AI)

### 컴포넌트 클래스 (`index.css`)
- `panel`, `panel-pad`, `card-hover`
- `btn-primary`(그라디언트), `btn-ghost`, `btn-success`, `btn-danger`, `btn-sm`
- `input`, `chip`, `tag-{red,amber,teal,blue,purple,gray}`, `eyebrow`, `grad-text`
- `animate-fade-up` (페이지 전환 시)

### 모든 화면 공통 패턴
1. `<PageHeader eyebrow="Layer X · MX-Y" title="..." description="..." actions={...} />`
2. `<PageBody>` (max-w 1280px, px-12 py-8)
3. KPI 4개 → 메인 콘텐츠 → 보조 카드 순

### 주요 파일 위치
| 역할 | 경로 |
|---|---|
| 디자인 토큰 | `frontend/tailwind.config.js`, `frontend/src/index.css` |
| 라우팅 | `frontend/src/App.tsx` |
| 케이스 상태 | `frontend/src/stores/useCaseStore.ts` |
| 보드 상태 | `frontend/src/stores/useBoardStore.ts` |
| 셰르파 챗 | `frontend/src/stores/useSherpaStore.ts` |
| 토스트 | `frontend/src/stores/useToastStore.ts` |
| 공유 타입 | `frontend/src/types/index.ts` |
| API 래퍼 | `frontend/src/api/client.ts`, `intake.ts` |
| 사고 유형 카탈로그 | `frontend/src/views/V1_Setup/meta.ts` |

---

## 작업 흐름 (재확인용)

```bash
# 시작 전
git switch dev
git pull --rebase origin dev

# 작업

# 마무리
git status
git add <특정 파일들>          # git add . 지양
git commit -m "feat: ..."
git pull --rebase origin dev   # push 직전에 한 번 더
git push
```

큰 작업은 `feature/<이름>` 브랜치 → PR `dev` 흐름을 권장합니다.
