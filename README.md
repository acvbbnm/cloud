# AI Sherpa

NCP와 NHN Cloud에서 침해사고가 의심될 때 확보할 로그와 다음에 확인할 단서를 안내하는 도구입니다.

2026년 1학기 · 세종대학교 정보보호 캡스톤 · 4인 팀 · 김병우 팀장

[최종 제출본](https://github.com/acvbbnm/cloud/tree/4bee0efe71e27249f05af0dc017abf80f9cc9f59) · [공동 저술 논문](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/_team_paper.pdf) · [검증 기록](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/3축_검증_보고서.md)

![AI Sherpa 시연 · 사건을 등록하고 Object Storage 활동 단서를 선택해 가설과 다음 단서를 확인](docs/images/readme-demo.gif)

합성 사례를 등록하고 Object Storage 활동을 관찰 단서로 추가하는 장면입니다.

## 직접 맡은 기능

| 기능 | 구현 |
| --- | --- |
| [사고 추적 엔진](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/intake/bayes_net.py) | 확인된 단서로 사고 유형 가설을 갱신하고, [정보이득](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/intake/info_gain.py)으로 다음에 볼 로그 후보를 정렬했습니다. |
| [수집 가이드](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/intake/collection_guide_v2.py) | 현재 가설과 클라우드 환경에 따라 먼저 확보할 로그와 보강 증거를 구분했습니다. |
| [로그 정규화](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/analysis/ocsf_normalizer.py) | NCP·NHN 원본을 OCSF 공통 필드로 바꾸면서 원래 로그와 해시, 매핑되지 않은 필드를 보존했습니다. |
| [보고서 연동](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/board/report_generator.py) | 조사 보드에서 확인한 근거가 보고서 초안과 내보내기로 이어지게 했습니다. |

## 다음 단서를 추천하고 판단을 보류한 이유

실무자 8명의 설문에서 초동에 어떤 로그를 먼저 봐야 할지 정하기 어려운 점을 확인했습니다. 예를 들어 Object Storage의 대량 활동만으로는 데이터 유출과 설정 오류 노출을 구분하기 어렵습니다. 가설 순위를 보여주고, 두 가설을 가장 잘 가를 단서를 우선 제시하도록 설계했습니다.

위 시연에서는 대량 활동 단서를 선택하자 데이터 유출과 랜섬웨어 가설이 각각 21%로 동률이었습니다. 도구는 단서 부족을 표시하고 백업 상태와 운영자 권한 등 다음 확인 항목을 추천했습니다. 표시된 값은 합성 사례의 모델 점수입니다.

![확인된 단서와 후보 사고 유형의 관계를 표시한 화면](docs/images/readme-clues.png)

## 시스템과 증거 데이터

~~~mermaid
flowchart LR
    UI["React · 사고 접수와 조사 보드"] --> API["FastAPI · 조사 API"]
    LOG["NCP·NHN 로그"] --> API
    API --> ENGINE["단서 갱신 · 수집 우선순위"]
    API --> DB["SQLite · 사건, 원본, 정규화 기록"]
    DB --> OUT["조사 보드 · 보고서"]
~~~

OCSF는 두 클라우드의 서로 다른 필드를 비교하는 데 썼습니다. SQLite에서 사건과 원본 로그를 연결하고, 정규화 이벤트가 원본을 가리키게 해 해석을 다시 검토할 수 있게 했습니다.

~~~mermaid
erDiagram
    INCIDENT_CASES ||--o{ RAW_EVENTS : contains
    RAW_EVENTS ||--o| OCSF_EVENTS : normalizes
    OCSF_EVENTS ||--o{ ATTACK_EVENTS : matches
    INCIDENT_CASES ||--o{ CHAIN_NODES : groups
~~~

[데이터 모델](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/db/models.py) · [로컬 실행](docs/LOCAL_RUN.md)
