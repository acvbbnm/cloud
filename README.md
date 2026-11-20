# AI Sherpa

NCP와 NHN Cloud에서 침해사고가 의심될 때 먼저 확보할 로그와 다음에 확인할 단서를 안내하는 조사 도구입니다.

2026년 1학기 · 세종대학교 정보보호 캡스톤 · 4인 팀 · 김병우 팀장

사고 추적 엔진, 수집 가이드, 로그 정규화, 조사 보드와 보고서 연동을 맡았습니다.

[최종 제출본](https://github.com/acvbbnm/cloud/tree/4bee0efe71e27249f05af0dc017abf80f9cc9f59) · [공동 저술 논문](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/_team_paper.pdf) · [검증 기록](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/3%EC%B6%95_%EA%B2%80%EC%A6%9D_%EB%B3%B4%EA%B3%A0%EC%84%9C.md)

시연에서는 합성 사례를 등록한 뒤 Object Storage 활동을 단서로 추가하고, 사고 유형 후보와 다음 확인 항목을 살펴봅니다.

![사고를 등록하고 Object Storage 활동을 단서로 추가하는 시연](docs/images/readme-demo.gif)

## 작업 기록

- [사고 접수와 단서 추천](docs/triage.md)에서 새 단서가 사고 후보와 수집 목록에 어떻게 반영되는지 볼 수 있습니다.
- [로그 수집과 정규화](docs/log-normalization.md)에서 두 클라우드의 로그를 같은 필드로 비교하고 원본을 확인하는 방법을 설명합니다.
- [조사 보드와 보고서](docs/investigation-board.md)에서 확인한 근거가 보드와 보고서로 이어지는 과정과 데이터 구조를 볼 수 있습니다.

[로컬 실행](docs/LOCAL_RUN.md)
