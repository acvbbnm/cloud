# 로그 수집과 정규화

NCP와 NHN Cloud의 로그는 같은 활동을 서로 다른 필드에 기록할 수 있다. 조사자가 두 환경의 기록을 비교하고 필요할 때 원래 로그를 다시 볼 수 있도록 원본과 정규화 이벤트를 연결했다.

## 처리 흐름

1. 사건에 로그를 가져오고 원본 기록과 해시를 보존한다.
2. 클라우드별 필드를 OCSF 공통 필드에 매핑한다.
3. 공통 필드로 옮겨지지 않은 값은 따로 보존한다.
4. 정규화 이벤트에서 원본으로 돌아가 값과 출처를 대조한다.

## 확인할 수 있는 자료

최종 제출본의 시스템 흐름 보고서에는 로그 수집 화면, 정규화 화면, 수집 목록과 제출된 로그를 비교하는 화면이 기록돼 있다. 데이터 모델에서는 사건, 원본 이벤트, 정규화 이벤트가 어떻게 연결되는지 확인할 수 있다.

[시스템 흐름 보고서](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/%EC%8B%9C%EC%8A%A4%ED%85%9C_%ED%94%8C%EB%A1%9C%EC%9A%B0_%EC%83%81%EC%84%B8%EB%B3%B4%EA%B3%A0%EC%84%9C.md) · [OCSF 정규화 코드](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/analysis/ocsf_normalizer.py) · [데이터 모델](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/db/models.py)
