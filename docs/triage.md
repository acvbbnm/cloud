# 사고 접수와 단서 추천

## 수집할 로그를 고르는 문제

설문에서 조사 초기에 어떤 로그를 먼저 봐야 할지 정하기 어렵다는 응답이 있었다.

## 사고 후보와 다음 단서

1. 사고를 등록하고 NCP 또는 NHN Cloud 환경을 선택한다.
2. 확인한 단서를 반영해 사고 유형 후보의 점수를 갱신한다.
3. 사고 유형 후보를 구분하는 데 도움이 되는 단서를 정보이득 순으로 제시한다.
4. 수집 가이드에서 먼저 확보할 로그와 보강 증거를 확인한다.

## 시연에서 확인한 사례

합성 사례에서 Object Storage 대량 활동을 추가하자 데이터 유출과 랜섬웨어의 모델 점수가 각각 21%로 나왔다. 화면은 추가 단서가 필요하다고 표시하고 백업 상태와 운영자 권한을 확인할 항목으로 제시했다.

![관찰 단서와 사고 유형 후보를 함께 표시한 화면](images/readme-clues.png)

[사고 추적 엔진](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/intake/bayes_net.py) · [정보이득 계산](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/intake/info_gain.py) · [수집 가이드](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/intake/collection_guide_v2.py)
