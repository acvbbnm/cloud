# 조사 보드와 보고서

조사 중 확인한 로그와 단서를 사건 보드에 모으고, 검토한 내용에서 보고서 초안과 내보내기로 이어지게 했다.

## 보드에서 보고서까지

조사자는 사건에 붙은 로그와 단서를 보드에서 검토한다. 증거 사이의 관계를 정리한 뒤 보고서 초안을 만들고 내보낼 수 있다. 최종 제출본에는 사건을 불러온 조사 보드와 보고서 화면이 남아 있다.

[조사 보드 화면](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/draft_final_report/options/captures/V_board_with_case.png) · [보고서 화면](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/draft_final_report/options/captures/V_report_with_case.png) · [보고서 생성 코드](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/board/report_generator.py)

## 시스템 구성

~~~mermaid
flowchart LR
    UI["React · 사고 접수와 조사 보드"] --> API["FastAPI · 조사 API"]
    LOG["NCP·NHN 로그"] --> API
    API --> ENGINE["단서 갱신 · 수집 우선순위"]
    API --> DB["SQLite · 사건, 원본, 정규화 기록"]
    DB --> OUT["조사 보드 · 보고서"]
~~~

SQLite는 사건별로 원본과 정규화된 기록을 연결한다. 조사 보드에서 본 기록의 근거가 필요하면 같은 사건의 원본 로그를 확인할 수 있다.

~~~mermaid
erDiagram
    INCIDENT_CASES ||--o{ RAW_EVENTS : contains
    RAW_EVENTS ||--o| OCSF_EVENTS : normalizes
    OCSF_EVENTS ||--o{ ATTACK_EVENTS : matches
    INCIDENT_CASES ||--o{ CHAIN_NODES : groups
~~~

[데이터 모델](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/db/models.py) · [검증 보고서](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/3%EC%B6%95_%EA%B2%80%EC%A6%9D_%EB%B3%B4%EA%B3%A0%EC%84%9C.md)
