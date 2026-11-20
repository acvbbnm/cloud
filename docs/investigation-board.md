# 조사 보드와 보고서

조사 보드는 사건별 로그와 단서를 모아 검토하는 화면입니다. 최종 제출본에서는 근거를 모아 보고서 초안을 만들고 파일로 내보낼 수 있습니다.

## 사건별 근거 정리

조사자는 원본 로그와 ATT&CK 매핑 후보를 검토한 뒤 보드에 추가합니다. 아래 두 화면은 최종 제출본의 같은 사건을 보여줍니다.

[조사 보드 화면](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/draft_final_report/options/captures/V_board_with_case.png) · [보고서 화면](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/draft_final_report/options/captures/V_report_with_case.png) · [보고서 생성 코드](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/board/report_generator.py)

## 시스템 구성

~~~mermaid
flowchart LR
    LOG["NCP·NHN Cloud 로그"] -->|"업로드"| API["FastAPI"]
    API -->|"단서로 후보 점수 계산"| ENGINE["사고 추적 엔진"]
    API <-->|"사건·이벤트 저장 및 조회"| DB["SQLite"]
    API -->|"사건 기록 조회"| BOARD["조사 보드"]
    API -->|"초안 생성·내보내기"| REPORT["보고서"]
~~~

SQLite는 사건에 원본 이벤트와 정규화 결과를 연결해 저장합니다. 아래 그림은 조사 기록에 쓰이는 테이블 관계입니다.

~~~mermaid
erDiagram
    direction LR
    INCIDENT_CASES ||--o{ RAW_EVENTS : "원본 보관"
    RAW_EVENTS ||--o| OCSF_EVENTS : "필드 정규화"
    OCSF_EVENTS ||--o{ ATTACK_EVENTS : "기법 후보 연결"
    INCIDENT_CASES ||--o{ CHAIN_NODES : "보드에 기록"
~~~

[데이터 모델](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/db/models.py) · [검증 보고서](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/3%EC%B6%95_%EA%B2%80%EC%A6%9D_%EB%B3%B4%EA%B3%A0%EC%84%9C.md)
