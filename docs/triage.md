# 사고 접수와 단서 추천

## 수집할 로그를 고르는 문제

침해사고 초동에는 볼 수 있는 로그가 많고, 처음 확인한 활동만으로 사고 유형을 가르기 어려울 수 있다. 설문에서 먼저 확인할 로그를 고르는 일이 어렵다는 점을 확인했다.

## 사고 후보와 다음 단서

1. 사고를 등록하고 NCP 또는 NHN Cloud 환경을 선택한다.
2. 확인한 단서를 반영해 사고 유형 후보의 점수를 갱신한다.
3. 정보이득을 기준으로 현재 후보를 가르는 데 도움이 되는 단서를 정렬한다.
4. 수집 가이드에서 먼저 확보할 로그와 보강 증거를 확인한다.

## 시연에서 확인한 사례

합성 사례에서 Object Storage 대량 활동을 추가하자 데이터 유출과 랜섬웨어 후보가 모델 점수 21%로 같았다. 화면은 단서가 더 필요하다고 표시했고 백업 상태와 운영자 권한 등 다음 확인 항목을 보여줬다. 이 수치는 시연에 사용한 합성 입력의 모델 점수다.

![관찰 단서와 사고 유형 후보를 함께 표시한 화면](images/readme-clues.png)

[사고 추적 엔진](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/intake/bayes_net.py) · [정보이득 계산](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/intake/info_gain.py) · [수집 가이드](https://github.com/acvbbnm/cloud/blob/4bee0efe71e27249f05af0dc017abf80f9cc9f59/backend/core/intake/collection_guide_v2.py)
