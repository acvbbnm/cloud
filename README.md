# AI Sherpa

NCP와 NHN Cloud에서 침해사고가 의심될 때 먼저 확보할 로그와 다음에 확인할 단서를 안내하는 조사 도구입니다.

세종대학교 정보보호 캡스톤 · 로그아웃 팀 4인 · 김병우 팀장

[최종 제출본](https://github.com/acvbbnm/cloud/tree/4bee0efe71e27249f05af0dc017abf80f9cc9f59) · [설계 문서](docs/설계서_읽는법.md) · [검증 기록](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/3축_검증_보고서.md)

![AI Sherpa의 사고 유형과 연결된 단서를 표시한 화면](docs/images/readme-clues.png)

## 조사 흐름

- 사고 유형과 클라우드 환경에 따라 수집할 로그를 정렬합니다. 로그가 들어오면 파일 SHA-256과 원문을 보존하고 OCSF 공통 필드로 변환합니다.
- 확인한 단서로 사고 가설의 점수를 갱신합니다. 어떤 로그를 확인하면 가설을 더 잘 가를 수 있는지 정보이득으로 계산합니다.
- ATT&CK 매핑과 수집 누락은 검토 후보로 표시합니다. 수사 보드에서 근거를 연결하고 보고서 초안으로 내보낼 수 있습니다.

초동대응 실무자 8명에게 원인 분석과 로그 확인 과정의 어려움을 물었습니다. 조사 순서를 정하기 어렵다는 응답을 수집 가이드와 단서 추천에 반영했습니다. 저는 사고 추적 엔진, 수집 가이드, 로그 정규화와 보고서 연동을 맡았습니다. [공동 저술 논문](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/_team_paper.pdf) · [단서 추천 코드](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/intake/info_gain.py)

## Windows에서 실행

Python 3.13, Node.js 20 이상, npm이 필요합니다. 아래 명령은 최종 제출 브랜치를 사용합니다. API가 처음 열릴 때 SQLite 테이블과 초기 데이터를 생성합니다.

백엔드 터미널

~~~powershell
git clone --branch chore/submission-cleanup https://github.com/acvbbnm/cloud.git
cd cloud/backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
~~~

다른 터미널에서 복제한 저장소의 프론트엔드를 실행합니다.

~~~powershell
cd cloud/frontend
npm ci
npm run dev -- --host 127.0.0.1
~~~

브라우저에서 http://127.0.0.1:5173을 엽니다. 채팅 기능을 쓰는 경우에는 Ollama를 별도로 실행하고 [환경 변수 예시](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/.env.example)의 `OLLAMA_BASE_URL`과 `LLM_MODEL`을 맞춥니다.

## 사용 예시

사고 접수에서 데이터 유출이 의심되는 사례를 만든 뒤 Object Storage 활동 단서를 확인합니다. 다음 단서 후보에 나오는 로그를 한 개씩 확인하면서 유출과 설정 오류 노출 가설의 순위가 어떻게 달라지는지 볼 수 있습니다.

Python · FastAPI · SQLite · React · TypeScript
