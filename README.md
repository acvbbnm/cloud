# AI Sherpa

NCP와 NHN Cloud에서 침해사고를 조사할 때 어떤 로그부터 확보해야 할지 안내하는 도구입니다. 이미 확보한 단서를 입력하면 사고 유형 후보와 다음에 확인할 항목이 바뀝니다.

2026년 1학기 · 세종대학교 정보보호 캡스톤 · 4인 팀 · 김병우 팀장

사고 추적 엔진, 수집 가이드, 로그 정규화, 조사 보드와 보고서 연동을 맡았습니다.

## 결과물

**[보고서와 시연](report/README.md)**에서 사고 등록, 단서 추천, 조사 보드와 보고서 화면을 순서대로 봅니다.

[공동 저술 논문 PDF](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/_team_paper.pdf) · [최종 제출 코드](https://github.com/acvbbnm/cloud/tree/4bee0efe71e27249f05af0dc017abf80f9cc9f59)

## 조사 과정

| 단계 | 확인할 수 있는 내용 |
| --- | --- |
| [사고 접수와 단서 추천](docs/triage.md) | Object Storage 활동을 추가했을 때 달라지는 유형 후보와 다음 수집 항목 |
| [로그 수집과 정규화](docs/log-normalization.md) | NCP·NHN Cloud 필드를 OCSF로 옮기고 원본과 대조하는 과정 |
| [조사 보드와 보고서](docs/investigation-board.md) | 사건별 근거를 정리하는 화면, 시스템 구성과 데이터 모델 |

[최종 제출본 로컬 실행](docs/LOCAL_RUN.md)
