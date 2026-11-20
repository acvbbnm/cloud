# 조사 보드와 보고서

사건 보드에 조사 로그와 단서를 모았다. 확인한 근거를 보고서 초안에 넣어 내보낼 수 있다.

## 사건별 근거 정리

조사자는 사건에 붙은 로그와 단서를 검토하고, 관련 근거를 보드에서 연결한다. 아래 화면은 최종 제출본에서 같은 사건의 조사 보드와 보고서를 연 예다.

[조사 보드 화면](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/draft_final_report/options/captures/V_board_with_case.png) · [보고서 화면](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/draft_final_report/options/captures/V_report_with_case.png) · [보고서 생성 코드](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/board/report_generator.py)

## 시스템 구성

~~~mermaid
flowchart LR
    UI["조사 화면"] --> API["조사 API"]
    LOG["NCP·NHN 로그"] -->|"로그 가져오기"| API
    API --> ENGINE["사고 후보·단서"]
    API -->|"사건·로그 저장"| DB["SQLite"]
    DB -->|"사건 근거 조회"| OUT["보드·보고서"]
~~~

SQLite에 사건별 원본과 정규화 이벤트를 연결해 저장한다. 조사 보드에서 기록을 검토하다 원본 로그를 열 수 있다.

~~~mermaid
erDiagram
    direction LR
    INCIDENT_CASES ||--o{ RAW_EVENTS : "원본 로그"
    RAW_EVENTS ||--o| OCSF_EVENTS : "정규화"
    OCSF_EVENTS ||--o{ ATTACK_EVENTS : "기법 매핑"
    INCIDENT_CASES ||--o{ CHAIN_NODES : "조사 보드"
~~~

[데이터 모델](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/db/models.py) · [검증 보고서](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/3%EC%B6%95_%EA%B2%80%EC%A6%9D_%EB%B3%B4%EA%B3%A0%EC%84%9C.md)
