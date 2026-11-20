# 로그 수집과 정규화

NCP와 NHN Cloud에서 수집한 이벤트를 같은 필드로 비교할 수 있도록 OCSF를 사용했습니다. 정규화 이벤트에서 원본을 다시 확인할 수 있습니다.

## 원본 로그에서 정규화 이벤트까지

1. 사건에 로그를 가져오면 원본 이벤트와 업로드 파일의 SHA-256을 기록합니다.
2. 정규화 모듈은 클라우드별 필드를 OCSF 필드에 대응시킵니다.
3. 대응하는 필드가 없는 값은 별도로 보존합니다.
4. 조사자는 정규화 화면에서 두 클라우드의 값을 비교한 뒤 원본 이벤트와 대조합니다.

## 시연 기록

시스템 흐름 보고서에서 로그를 가져와 정규화하고 수집 목록과 대조하는 화면을 볼 수 있습니다.

[시스템 흐름 보고서](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/docs/%EC%8B%9C%EC%8A%A4%ED%85%9C_%ED%94%8C%EB%A1%9C%EC%9A%B0_%EC%83%81%EC%84%B8%EB%B3%B4%EA%B3%A0%EC%84%9C.md) · [OCSF 정규화 코드](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/analysis/ocsf_normalizer.py) · [데이터 모델](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/db/models.py)
