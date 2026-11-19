# AI Sherpa 로컬 실행

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
