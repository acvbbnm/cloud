# 베이지안 사고유형 분류 — Phase 3+4 작업 가이드

> 작성: 2026-05-25 byungwoo 브랜치 / Phase 1+2 완료 (`4bfeb04`) 후속.
> 목적: 다른 환경에서 pull → 이어서 Phase 3+4 진행할 수 있는 셀프 컨테인드 명세.

---

## 1. 사전 컨텍스트 (Phase 1+2 완료 상태)

### 신규 인프라
- `backend/data/triage/priors.json` — Verizon DBIR 2024 prior 8 사고유형 (합=1.0)
- `backend/core/intake/bayesian.py` — 베이즈 함수 모듈 (순수 함수, 부작용 0)
- `backend/tests/test_bayesian.py` — 단위 15 케이스 (모두 PASS)

### 핵심 API
```python
from core.intake.bayesian import (
    initial_posterior,      # 베이즈 시작점 = priors + UNCLASSIFIED=0
    weights_to_likelihood,  # 정수 점수 → 확률 (Laplace smoothing)
    bayes_update,           # 1-step 사후확률 갱신 (정규화 합=1)
    confidence_level,       # 임계값 분류 (auto_confirm/propose_single/...)
    top_n,                  # 상위 N 가설
    load_priors,            # priors.json 캐시 로딩
)
```

### 시뮬레이션 결과 (수기 검증)
| 시나리오 | Q1~Q6 | 최종 사후확률 | 분류 |
|---|---|---|---|
| CRED+Tor | 자격증명 풀체인 | CRED 69.7% / PHISH 24.9% | propose_composite |
| RANSOM | 랜섬 풀체인 | RANSOMWARE 99.8% | auto_confirm |
| INSIDER+baseline | 내부자 + P5 baseline | INSIDER 93.4% | auto_confirm |

---

## 2. Phase 3 — triage.py 통합 (예상 2시간)

### 목표
기존 누적 합산 모드와 베이지안 모드를 **환경변수 토글** 로 공존. 회귀 없이 점진 전환.

### 작업 항목

#### 3.1 환경변수 정의 (`backend/config.py`)
```python
# 추가
TRIAGE_MODE: str = os.getenv("TRIAGE_MODE", "additive")  # "additive" | "bayesian"
```

#### 3.2 `triage.py` 분기 도입
**위치**: `core/intake/triage.py:55` `_initial_scores`, `core/intake/triage.py:288` `next_question`

기존 함수 시그니처 유지하고 내부에서 모드 분기:
```python
from config import settings
from core.intake.bayesian import (
    initial_posterior, weights_to_likelihood, bayes_update, confidence_level,
)

def _initial_scores() -> dict[str, float]:
    if settings.TRIAGE_MODE == "bayesian":
        return initial_posterior()  # priors + UNCLASSIFIED=0, 합=1.0
    # 기존
    return {t: 0 for t in INCIDENT_TYPES_8} | {"UNCLASSIFIED": 0}


def _apply_weight(scores: dict, weight_key: str, all_weights: dict) -> dict:
    if settings.TRIAGE_MODE == "bayesian":
        w = all_weights.get(weight_key, {})
        if not w:
            return scores  # 가중치 없으면 변동 없음
        lk = weights_to_likelihood(w)
        return bayes_update(scores, lk)
    # 기존 누적 합산
    ...
```

#### 3.3 `evaluate_recommendation` 분기
**위치**: `core/intake/triage.py` 의 `evaluate_recommendation` 함수

```python
def evaluate_recommendation(scores: dict) -> dict:
    if settings.TRIAGE_MODE == "bayesian":
        cl = confidence_level(scores)
        # 기존 응답 스키마와 호환되게 변환
        return {
            "primary": {
                "incident_type": cl["primary"],
                "score": int(cl["primary_prob"] * 100),  # 0~100 표시
            },
            "secondary": {...} if cl["secondary"] else None,
            "outcome": cl["recommended_action"],
            "gap": int(cl["gap"] * 100),
        }
    # 기존 절대 점수 기반
    ...
```

### 검증 (3.4)
```bash
# 기본 모드 (회귀 0)
.venv/Scripts/python.exe -X utf8 -m scripts.e2e_tree_e4_test
# 기대: 47/47 PASS

# 베이지안 모드
TRIAGE_MODE=bayesian .venv/Scripts/python.exe -X utf8 -m scripts.e2e_tree_e4_test
# 기대: 47 시나리오 중 일부 outcome 변동 — Phase 3.5 에서 fitting
```

### 3.5 임계값 fitting (47 시나리오 PASS 회복)

베이지안 임계값 (`confidence_level` 의 hardcoded 0.85/0.70/0.50) 을 시나리오 결과에 맞춰 조정. 후보:
- `auto_confirm`: 0.85 → 0.80 검토
- `propose_single`: 0.70 → 0.60 검토
- `propose_composite`: 0.50 → 0.40 검토

각 시도마다 47 시나리오 PASS 카운트 측정. Sweet spot 찾기.

**자동 fitting 스크립트 아이디어** (`backend/scripts/bayesian_threshold_fit.py` 신설):
```python
# 임계값 grid search — auto_confirm ∈ {0.75, 0.80, 0.85}, propose_single ∈ {0.55, 0.60, 0.65, 0.70}, ...
# 각 조합으로 47 시나리오 돌리고 PASS 카운트 최대인 조합 출력
```

---

## 3. Phase 4 — 프론트 % 표시 (예상 2시간)

### 작업 파일 3종

#### 4.1 `HypothesisScoreBar.tsx`
- 현재: 절대 점수 (0~180)
- 변경: 백분율 (0~100%)
- props 에 `mode: 'additive' | 'bayesian'` 추가 → 자동 단위 결정
- 또는 백엔드 응답에 `unit` 필드 (`'percent'` 또는 `'score'`) 포함시켜 그대로 표시

#### 4.2 `HypothesisBreakdownChart.tsx`
- 같이 백분율 표시
- 분해 detail 에서 "Q5-CRED:tor_vpn → +14.3%p (likelihood 0.41)" 형식
- 절대 점수 변동 → 확률 변동으로

#### 4.3 `ConfidenceGauge.tsx`
- 기존 12% (15/130) 표시 → 신뢰도 직접 매칭 (사후확률 그대로)
- 임계값 마크 위치 70% / 85% 로 조정

### 한국어 라벨
- "가설 점수" → "사고유형 신뢰도"
- "15/130점" → "84%"
- "high_confidence 90점" → "확신 70%"
- "auto_skip 130점" → "자동 확정 85%"

### 백엔드 응답 확장 권장
응답 스키마에 `scoring_mode` + `unit` 명시:
```json
{
  "scores": {"CREDENTIAL_THEFT": 0.84, ...},
  "scoring_mode": "bayesian",
  "unit": "probability",
  "thresholds": {"auto_confirm": 0.85, "propose_single": 0.70, ...}
}
```

---

## 4. 작업 순서 권장

```
1. branch checkout: git checkout byungwoo && git pull
2. Phase 3.1 config.py 환경변수 추가 (5분)
3. Phase 3.2 triage.py 분기 도입 (30분)
4. Phase 3.3 evaluate_recommendation 분기 (20분)
5. Phase 3.4 회귀 검증 (TRIAGE_MODE=additive 로 47/47 PASS 확인) — 안전 체크포인트
6. Phase 3.5 베이지안 모드 시나리오 돌려서 PASS 카운트 측정
7. Phase 3.5 임계값 fitting (grid search) → sweet spot 적용
8. 커밋 push (Phase 3 완료)
9. Phase 4.1~3 프론트 % 표시 + 백엔드 응답 unit 확장
10. 커밋 push (Phase 4 완료)
```

---

## 5. Phase 3 회귀 위험 + 안전장치

### 위험
- 베이지안 임계값과 기존 47 시나리오 expect_outcome 불일치
- 일부 사고유형 1위 변동 가능 (prior 의 영향)

### 안전장치
- **환경변수 default = "additive"** (기존 동작 보장)
- 베이지안은 명시적 `TRIAGE_MODE=bayesian` 일 때만
- E2E 두 모드 모두 PASS 확인 후 dev3 머지

---

## 6. Phase 3+4 완료 후 학술 변호 메시지

```
"본 시스템의 사고유형 분류는 베이즈 정리 + Verizon DBIR 2024 prior 로 산출합니다.
같은 답변 시퀀스는 항상 같은 사후확률을 산출하며 (결정성 100%),
AI 는 KB 검색·요약만 수행할 뿐 가설 점수에 개입하지 않습니다 (CLAUDE.md 정합).
임계값 (70% 제시 / 85% 자동확정) 도 외부 표준 (NIST SP 800-61r2 confidence levels)
을 참고했습니다."
```

논문 키워드: **Bayesian incident classification**, **Verizon DBIR prior**, **deterministic posterior**, **threshold fitting via 47 scenarios**

---

## 7. 참고 자료

- arXiv 2505.09048 — Bayesian Network for Cybersecurity Risk (2026)
- k9 Security — Severity is no longer a triage input (2026.05)
- Verizon DBIR 2024 — Top 4 patterns 통계
- NIST SP 800-61r2 §3.2.6 — Incident Prioritization (confidence concept)
