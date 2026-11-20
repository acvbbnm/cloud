# AI Sherpa 로컬 실행

Python 3.13, Node.js 20 이상, npm을 준비합니다. 아래 명령은 README 시연의 기준인 최종 제출본을 실행합니다. 백엔드를 처음 시작하면 SQLite 테이블과 초기 데이터가 생성됩니다.

## 백엔드

~~~powershell
git clone --branch chore/submission-cleanup https://github.com/acvbbnm/cloud.git
cd cloud/backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
~~~

## 프론트엔드

복제를 시작한 폴더에서 새 터미널을 열고 프론트엔드를 실행합니다.

~~~powershell
cd cloud/frontend
npm ci
npm run dev -- --host 127.0.0.1
~~~

브라우저에서 [AI Sherpa](http://127.0.0.1:5173)를 엽니다. 채팅을 쓰려면 Ollama를 시작하고 `OLLAMA_BASE_URL`과 `LLM_MODEL`을 설정합니다. [환경 변수 예시](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/.env.example)

## 사용 예시

사고 접수에서 사례를 만들고 Object Storage 대량 활동을 단서로 추가합니다. 추천 항목을 연 뒤, 다음에 어떤 로그를 확인해야 유형 후보를 구분할 수 있는지 살펴봅니다.
