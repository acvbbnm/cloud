# AI Sherpa

NCP와 NHN Cloud의 침해사고를 조사할 때 먼저 확보할 로그와 다음 단서를 찾는 도구입니다.

2026년 1학기 · 세종대학교 정보보호 캡스톤 · 4인 팀 · 김병우 팀장

사고 추적 엔진, 수집 가이드, 로그 정규화, 조사 보드와 보고서 연동을 맡았습니다.

[최종 제출본](https://github.com/acvbbnm/cloud/tree/4bee0efe71e27249f05af0dc017abf80f9cc9f59) · [공동 저술 논문](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/_team_paper.pdf) · [검증 기록](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/3%EC%B6%95_%EA%B2%80%EC%A6%9D_%EB%B3%B4%EA%B3%A0%EC%84%9C.md)

합성 사례 시연에서는 Object Storage 활동을 추가한 뒤, 어느 로그를 더 확인하면 사고 유형 후보를 구분할 수 있는지 보여줍니다.

![사고를 등록하고 Object Storage 활동을 단서로 추가하는 시연](docs/images/readme-demo.gif)

## 작업 기록

- [사고 접수와 단서 추천](docs/triage.md) · 확보한 단서로 사고 유형 후보와 수집 목록을 갱신합니다.
- [로그 수집과 정규화](docs/log-normalization.md) · 공통 필드로 비교하고 원본 로그를 확인합니다.
- [조사 보드와 보고서](docs/investigation-board.md) · 사건별 근거를 정리하고 보고서로 내보냅니다.

[로컬 실행](docs/LOCAL_RUN.md)
