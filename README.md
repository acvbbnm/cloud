# AI Sherpa — 팀 개발자 가이드

> **로그아웃 팀 (김병우·이근형·이지호·최진규)** — 세종대 정보보호캡스톤 2026-1
> 국내 멀티 클라우드 침해사고 분석 시스템

이 저장소는 **AI 코딩 도구(Claude Code / Cursor / 등)에 폴더를 연결만 하면 AI가 스스로 다음 할 일을 찾아 작업할 수 있도록** 설계되어 있습니다. 처음 클론한 사람은 아래 30분 가이드만 따라가면 됩니다.

---

## ⚡ 30분 안에 작업 시작하기

### 1) 저장소 클론

```bash
git clone https://github.com/sasumm25-lab/cloud.git
cd cloud
git checkout dev
```

### 2) 자신의 작업 브랜치 만들기

브랜치명은 `feature/<영역>` 으로 통일합니다. 예시:
- `feature/db-schema`, `feature/layer0-api`, `feature/layer1-api`
- `feature/frontend-shell`, `feature/v2-logs`, `feature/v5-board`
- `feature/rag-kb`, `feature/report-export`

```bash
git checkout -b feature/<영역>
```

> ⚠ 시작 전 `git fetch` 후 **남이 같은 영역을 이미 잡고 있는지** 브랜치 목록을 확인하세요. 같은 항목을 두 명이 동시에 잡으면 머지 충돌이 생깁니다.

### 3) AI 도구에 이 폴더 연결

| 도구 | 방법 |
|---|---|
| **Claude Code** | 터미널에서 `cd cloud` → `claude` 실행. `CLAUDE.md` 가 자동으로 로드됩니다 |
| **Cursor** | `File → Open Folder` 로 `cloud/` 선택. `CLAUDE.md` 가 컨텍스트로 잡힙니다 |
| **기타 (Copilot 등)** | 첫 프롬프트에 "`CLAUDE.md` 와 `.claude/구현/` 폴더를 먼저 읽고 시작해줘" 라고 지시 |

### 4) AI에게 작업 시키기

AI는 [`CLAUDE.md`](CLAUDE.md) 최상단의 **"🤖 AI에게 — 부팅 시퀀스"** 에 따라:
1. [`docs/설계서_읽는법.md`](docs/설계서_읽는법.md) 로 시스템 구조 파악
2. [`.claude/구현/구현_체크리스트.md`](.claude/구현/구현_체크리스트.md) 에서 비어 있는 `[ ]` 항목 확인
3. [`.claude/구현/모듈별_구현_명세.md`](.claude/구현/모듈별_구현_명세.md) · [`.claude/구현/API_계약서.md`](.claude/구현/API_계약서.md) 로 입출력 확정
4. 코드 작성
5. 체크리스트의 해당 항목을 `[x]` 로 갱신

→ 사용자가 할 일은 "**Phase 1-2 의 Layer 0 API 구현해줘**" 같은 한 줄 지시면 충분합니다.

### 5) 환경 세팅

#### 백엔드

```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env       # 없으면 건너뜀
python -m db.init_db       # DB 파일 생성 + 시드 데이터
uvicorn main:app --reload  # http://localhost:8000
```

#### 프론트엔드

```bash
cd frontend
npm install
npm run dev                # http://localhost:5173
```

#### AI (RAG 담당자만)

```bash
ollama pull llama3.1:8b
ollama serve               # http://localhost:11434
```

---

## 📁 폴더 한눈에 보기

```
cloud/
├── README.md              ← 지금 이 파일 (팀 가이드)
├── CLAUDE.md              ← AI 코딩 지침 (네이밍·구조·계약, 절대 준수)
├── .gitignore
├── docs/
│   ├── 설계서_읽는법.md   ← 설계서 어디서 무엇을 봐야 하는지
│   └── 설계서_최종.pdf    ← (선택 배치) 그림·표 확인용
├── .claude/
│   └── 구현/
│       ├── 구현_체크리스트.md   ← Phase 1~4 진척도 (★ 핵심)
│       ├── 모듈별_구현_명세.md  ← 모듈 입출력·로직
│       └── API_계약서.md        ← 22개 API 요청/응답
├── backend/               ← Python / FastAPI
│   ├── main.py            (라우터 등록만)
│   ├── api/               (계층별 라우터 1파일)
│   ├── core/              (계층별 비즈니스 로직)
│   ├── db/                (models·session·init)
│   └── data/              (시드·KB·매핑 룰 JSON)
└── frontend/              ← React + TypeScript + Vite
    └── src/
        ├── views/V1_Setup ~ V8_Sherpa   (8개 화면)
        ├── components/    (공통 컴포넌트)
        ├── stores/        (Zustand)
        ├── api/           (axios 래퍼, 계층별)
        └── types/         (TS 타입)
```

---

## 🤝 협업 규칙 (한 페이지 요약)

| 항목 | 규칙 |
|---|---|
| **브랜치** | `dev` 에서 분기 → `feature/<영역>` → PR 로 `dev` 머지 → Phase 종료 시 `main` 머지 |
| **PR 리뷰** | 최소 1명 승인 후 머지 |
| **커밋 메시지** | `feat: / fix: / refactor: / docs: / test: / chore:` 프리픽스 (예: `feat: POST /api/cases 구현`) |
| **충돌 회피** | 같은 체크리스트 항목을 두 명이 잡지 않기. 공유 파일(`main.py`, `App.tsx`, `models.py`, `types/index.ts`)은 **추가만**, 수정은 리뷰 필수 |
| **진척도** | 작업 끝나면 **같은 커밋에** `구현_체크리스트.md` 의 해당 `[ ]` 를 `[x]` 로 변경하고 날짜 적기 |
| **금지** | 클래스명·테이블명·API 경로 임의 변경 / 외부 CDN 사용 / `.env` 커밋 / `console.log` 디버깅 커밋 |

---

## 🆘 막혔을 때

| 상황 | 어디를 본다 |
|---|---|
| **돌려보고 버그 찾고 싶다 (시연 리허설)** | **`docs/시연_체크리스트.md`** (NCP/NHN 풀 흐름 22+8 항목, UX 점검표) |
| 시스템이 뭐 하는 건지 잊었다 | `docs/설계서_읽는법.md` 의 1·2·3절 |
| 클래스명·테이블명을 모르겠다 | `CLAUDE.md` 의 "클래스명 (변경 금지)" / "DB 테이블 (9개)" 표 |
| API 요청/응답 스키마가 헷갈린다 | `.claude/구현/API_계약서.md` |
| 모듈이 무엇을 입출력하는지 모르겠다 | `.claude/구현/모듈별_구현_명세.md` |
| 다이어그램(그림)을 보고 싶다 | 팀 Google Drive 의 `AI셰르파_설계서_v2_완성.docx` 또는 `docs/설계서_최종.pdf` |
| 갭(Gap)·OCSF·ATT&CK 등 용어 | `docs/설계서_읽는법.md` 의 6절 약어표 |

---

## 📌 현재 단계

- Phase 1 (1주차): 기반 구축 — DB / Layer 0 / 프론트 셸 / RAG KB
- Phase 2 (2주차): 핵심 파이프라인 관통 — Layer 1·2 / V-2~V-4
- Phase 3 (3주차): 수사 보드 + AI 셰르파 — Layer 4 보드 / Layer 3 AI / V-5·V-6·V-8
- Phase 4 (4주차): 보고서 + 마무리 — V-7 / DOCX·PDF 내보내기 / 통합 테스트

> 자세한 체크리스트는 [`.claude/구현/구현_체크리스트.md`](.claude/구현/구현_체크리스트.md) 참조.
