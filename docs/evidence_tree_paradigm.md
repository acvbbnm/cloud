# Evidence Tree — 단서 기반 동적 결정 트리 패러다임 (byungwoo)

> 작성: 2026-05-25
> 상태: 설계 확정, 구현 대기
> 이전: `docs/bayesian_phase3_4_guide.md` (Phase 1~4 완료, byungwoo 브랜치)

---

## 1. 사용자 비전 — "어두운 맵을 단서로 밝혀가는 수사"

### 비유
> *"게임 속 어두운 맵을 단서로 밝혀가는 과정.
> 사고유형이 정해져 있으면 전체 맵의 크기는 정해져 있고 (8 사고유형 = boundary),
> 단서를 찾을수록 그쪽 방향의 길이 열린다.
> 도달점이 어디가 될지 모른다 — 단서들이 수사관을 한 사고유형으로 안내한다."*

### 학술 명칭
- **Inductive Search** (Peirce 1903 — Abductive Reasoning)
- **Bayesian Belief Propagation** (Pearl 1988 — Causal Networks)
- **Fog of War / Information Frontier Exploration** (Game AI, McKinsey 2019 — Decision under Uncertainty)
- 임상 진단 시스템 정통 — **MYCIN 1976**, **CADUCEUS 1982**, **IBM Watson Health**

---

## 2. 현재 시스템의 본질적 한계 (전환 사유)

### 현재 = Decision Tree (Top-down Deductive)
```
Q1 "어떻게 알게 됐나?" → "CSP 알람" → Q2A → Q3_CRED → Q4_CRED → ... → CRED lane 만
                                              ↓
                                  다른 사고유형 변별 기회 차단
```

### 문제점
1. **한 답변 = 한 lane 라우팅** → 트리 진행 중 다른 사고유형은 모두 비활성
2. **베이즈 모델 부정합** — 확률 모델은 모든 가설을 동시에 추적해야 하는데 트리가 그 기회 차단
3. **수사 직관 불일치** — 형사는 단서를 모아 가능성을 좁히지, 미리 한 사고유형 선언하지 않음

### 새 패러다임 — Evidence Tree (Bottom-up Abductive)
```
[Root: uniform prior 12.5% × 8]
  ↓ 단서 1 입력 "외부 IP 새벽 로그인"
[단서 1] CRED 45% / PHISH 30% / INSIDER 10% / ...
  ├─ 다음 단서 후보: MFA 우회 (CRED) / 이메일 클릭 (PHISH) / 내부망→외부 (INSIDER)
  ↓ 사용자가 MFA 우회 선택
[단서 2] CRED 70% / PHISH 20% / ...
  ├─ 다음 단서 후보: AccessKey 신규 / Tor 출구 / 권한 변경
  ↓ ...
[단서 N] CRED 85% — confidence 도달 → 마무리
```

---

## 3. 핵심 설계 원칙

| 원칙 | 내용 |
|---|---|
| **Prior = Uniform (1/8)** | Jaynes Maximum Entropy. 모든 사고유형 동등 시작. |
| **트리 노드 = 단서** | "질문" 이 아니라 "확정된 사실" (관측된 IoC) |
| **트리 children = 다음 단서 후보** | 정적 옵션 X. 매 단계 동적 계산 (Information Gain 기반) |
| **트리 깊이 = 무한** | confidence 임계 (85%+) 도달 또는 사용자 종료 시 마무리 |
| **시각화 = 그대로** | TriageTreeMinimap / TriageTreeGraph 그대로 사용 |
| **결정 트리 보존** | 기존 22 노드 = "단서 카탈로그" 로 재해석. 사용자 막힐 때 표준 가이드 |
| **MVP 단순화** | 단서 = "확인됨" 만. negative evidence 는 Phase 2 |

---

## 4. UI 동작 명세 (3가지 단서 입력 경로)

### 4.1 단서 후보 클릭 (가장 일반)
- 현재 트리 leaf 노드에 children candidates (점선 회색)
- 클릭 → 채택 → 단서 노드 확정 (실선 초록) + 사후확률 갱신 + 다음 후보 자동 생성

### 4.2 직접 입력
- 좌측 `CluesInput` 패널 (현재 자산 재활용)
- 사용자가 자유 단서 입력 (예: IP=`115.91.214.5`)
- 트리에 단서 노드 추가 + 다음 후보 갱신

### 4.3 로그 파일 등록 → 자동 단서 추출
- `PartialLogAnalysis` 패널 (현재 자산 재활용)
- 로그 분석 → 매핑된 ATT&CK 기법들을 **단서 후보로 자동 추가**
- 사용자가 후보 중 선택해서 트리에 채택

---

## 5. 자료구조

### `ClueTreeNode` (신설)

```python
@dataclass
class ClueTreeNode:
    node_id: str                    # uuid
    parent_id: Optional[str]        # 트리 부모 (root 면 None)
    depth: int                      # root=0
    clue: dict                      # {type, value, weight_key, source}
    score_delta: dict[str, float]   # 이 단서가 각 사고유형 사후확률에 미친 영향
    posterior_after: dict[str, float]  # 이 단서 채택 후 사후확률 스냅샷
    accepted_at: datetime
    children_candidates: list[dict] # 다음 후보 (아직 채택 X)
                                     # [{candidate_id, clue_template, expected_info_gain, rationale}]
```

### `ClueTree` (전체 트리)

```python
@dataclass
class ClueTree:
    case_id: str
    root_id: str                     # 시작 노드 (uniform prior)
    nodes: dict[str, ClueTreeNode]   # node_id → node
    current_leaf_id: str             # 가장 최근 채택 단서 (다음 채택 위치)
    posterior_current: dict[str, float]  # 현재 사후확률
    confidence_reached: bool         # ≥85% 도달 여부
    incident_type_recommendation: Optional[str]
```

### DB 영속화
- `incident_cases.triage_state` JSON 칼럼에 `ClueTree` 직렬화
- 페이지 새로고침해도 트리 보존

---

## 6. 백엔드 API

### 6.1 신규 API

| 엔드포인트 | 입력 | 출력 |
|---|---|---|
| `POST /api/clue-tree/start` | `caseId` | `{tree, candidates}` (root + 초기 후보) |
| `POST /api/clue-tree/expand` | `caseId, parent_node_id, clue` | `{node, posterior, candidates, confidence_reached}` |
| `POST /api/clue-tree/suggest` | `caseId, current_leaf_id` | `{candidates}` (다음 후보 재계산) |
| `GET /api/clue-tree?caseId=` | — | `{tree}` 현재 상태 조회 |

### 6.2 기존 API 재활용
- `POST /api/triage/analyze` — 단서 → 사후확률 갱신 (현재 그대로)
- `POST /api/triage/analyze-logs` — 로그 → 단서 후보 추출 (현재 그대로)

### 6.3 환경변수
- `TRIAGE_MODE=evidence_tree` — 새 모드 (기존 `additive` / `bayesian` 과 공존)

---

## 7. 다음 단서 후보 알고리즘 (Phase D)

### Information Gain (KL Divergence)

각 가능 단서 *c* 에 대해:
```
IG(c) = H(P) - E[H(P | c)]
      = sum_h P(h) × P(c | h) × log(P(h | c) / P(h))
```

- `H(P)` = 현재 사후확률 분포의 entropy
- `H(P | c)` = 단서 c 채택 후 entropy
- IG 가 큰 단서 = 가장 변별력 높음

### 후보 선정 알고리즘
```python
def suggest_next_clues(posterior, accepted_clues, k=3):
    # 1. 모든 가능 단서 (weights.json:clue_types + decision_tree 변환) 풀
    # 2. 이미 채택된 단서 제외
    # 3. 각 단서의 expected information gain 계산
    # 4. 상위 K개 반환

    candidates = []
    for clue_type, weights in CLUE_CATALOG.items():
        if clue_type in accepted_clues:
            continue
        ig = compute_info_gain(posterior, weights)
        candidates.append((clue_type, ig))
    candidates.sort(key=lambda x: -x[1])
    return candidates[:k]
```

### Fallback (IG 모두 낮을 때)
- 사후확률 상위 2 사고유형의 `next_clue_graph.json` 권장 단서 활용
- 사용자에게 "결정 트리 보조 가이드" 옵션 제공

---

## 8. 프론트 UI 동작

### V-1 Step 3 새 레이아웃
```
┌─────────────────────────────────────────────────────────┐
│ [Evidence Tree 시각화 — 메인]                            │
│   현재 트리 + 다음 단서 후보 3개 (점선)                  │
│   클릭하면 후보 → 단서로 채택, 트리 자라남               │
├─────────────────────────────────────────────────────────┤
│ [단서 직접 입력] (CluesInput)                            │
│ [로그 파일 등록 → 단서 후보 자동 추가] (PartialLogAnalysis)│
├─────────────────────────────────────────────────────────┤
│ [결정 트리 보조 가이드 — 접힘]                            │
│   "어떤 단서부터 시작해야 할지 모르겠다면 펼치기"          │
└─────────────────────────────────────────────────────────┘

[우측 sticky]
신뢰도 게이지 (사후확률 1위 %)
사고유형 신뢰도 (상위 2)
8종 비교 ⛶ (클릭 → 오버레이)
```

### 트리 노드 시각화
- 채택된 단서: 실선 초록 (현재 자산: TriageTreeMinimap 의 selected 옵션 스타일)
- 후보 (children): 점선 회색 (현재 자산: 미선택 옵션 스타일)
- Information Gain 표시: 각 후보 옆에 작은 게이지 (변별력 시각화)

---

## 9. 기존 자산 재활용 매트릭스

| 기존 | 새 모델에서 역할 | 마이그레이션 |
|---|---|---|
| `weights.json:clue_types` (22종) | likelihood P(E\|H) 그대로 | 변경 0 |
| `decision_tree.json` (22 노드) | **단서 카탈로그**로 변환 (예: `Q5_CRED:tor_vpn` → "Tor 출구 IP" 단서) | 자동 추출 스크립트 |
| `next_clue_graph.json` | 다음 단서 후보 기본 풀 + IG 계산 입력 | 그대로 사용 |
| `bayesian.py` 모듈 | `bayes_update` 그대로, `weights_to_likelihood` 단서용으로도 사용 | 변경 0 |
| `priors.json` | uniform (1/8) 로 갱신 | 1줄 수정 |
| `TriageTreeMinimap` / `TriageTreeGraph` | 그대로 — 노드 라벨만 단서로 | 라벨 매핑 |
| `CluesInput` / `PartialLogAnalysis` | 단서 입력 메인 채널로 격상 | 응답 처리만 갱신 |
| `NextCluePanel` | Information Gain 알고리즘으로 강화 | 핵심 로직 신설 |
| `HypothesisScoreBar` / `ConfidenceGauge` | 사후확률 표시 그대로 | 변경 0 (이미 % 모드 지원) |

---

## 10. 47 시나리오 마이그레이션

### 현재
```python
"steps": [
    ("Q1_inception", ["csp_alert"]),
    ("Q2A_alert_type", ["abnormal_login"]),
    ("Q3_CRED", ["fail_then_success"]),
    ...
]
```

### 신규 (단서 시퀀스)
```python
"clues": [
    {"type": "incident_source", "value": "csp_alert"},
    {"type": "alert_pattern", "value": "abnormal_login"},
    {"type": "auth_pattern", "value": "fail_then_success"},
    ...
]
```

기존 22 노드 → 22 단서 카탈로그 자동 변환. 47 시나리오는 단서 시퀀스 시뮬레이션으로 보존.

---

## 11. 구현 계획 — Phase A~F 점진

| Phase | 작업 | 시간 | 위험 |
|---|---|---|---|
| **5.0** | Prior uniform (1/8) 변경 (priors.json 1줄) | 5분 | 0 |
| **A** | `ClueTreeNode` 자료구조 + 단서 카탈로그 자동 추출 (decision_tree.json → clue_catalog.json) | 1.5h | 낮음 |
| **B** | 백엔드 API 4종 + Information Gain 알고리즘 | 2.5h | 중간 |
| **C** | 프론트 트리 UI — 노드 클릭 → 채택 → 자라기 | 2h | 낮음 |
| **D** | `NextCluePanel` Information Gain 통합 + 후보 시각화 | 1.5h | 낮음 |
| **E** | V-1 Step 3 레이아웃 재설계 (트리 메인, 입력 메인 통합) | 1h | 낮음 |
| **F** | 47 시나리오 단서 시퀀스 마이그레이션 + e2e 회귀 검증 | 1.5h | 중간 |
| **G** | DiscoveryIntroModal 갱신 — "단서로 맵 밝히기" 안내 | 30분 | 0 |
| **합계** | **~11시간** | | |

각 Phase 마다 commit → push → 검증. 단계별 안전.

---

## 12. Risk + Mitigation

| Risk | 영향 | Mitigation |
|---|---|---|
| 47 시나리오 outcome 변동 | e2e 회귀 | 단서 시퀀스 시뮬레이션으로 베이지안 모드 임계값 fitting (Phase F) |
| 단서 카탈로그 부족 (22 → ?) | 후보 빈약 | 기존 22 + decision_tree 추출 = 50+ 단서로 시작. 추후 KB case_db 130 케이스 분석 추가 |
| Information Gain 계산 비용 | API 응답 지연 | 단서당 O(8) — 50 × 8 = 400 연산. 1ms 미만 |
| UI 학습 곡선 | 사용자 혼란 | DiscoveryIntroModal 갱신 + 트리 보조 가이드 fallback 유지 |
| 무한 깊이 — 메모리 | 트리 너무 커짐 | confidence ≥ 85% 도달 시 자동 권장 종료. 30 노드 hard limit |

---

## 13. 학술 변호 메시지 (Evidence Tree 전환 후)

> **본 시스템은 결정 트리 (deductive classification) 가 아니라 단서 기반 Evidence Tree (abductive reasoning + Bayesian belief propagation) 패러다임을 채택합니다.**
>
> - **Prior**: Uniform (Jaynes Maximum Entropy) — 사전 편향 없음
> - **Likelihood**: 단서별 학술 인용 가중치 (weights.json) — Verizon DBIR · MITRE ATT&CK · NIST 정합
> - **Next clue selection**: Information Gain (KL divergence) 최대 단서 동적 추천 — Shannon 1948 정합
> - **Decision tree (보조)**: 단서 미수렴 시 표준 질문 가이드 fallback
>
> **학술 전통**: 임상 진단 시스템 (MYCIN 1976, CADUCEUS 1982, IBM Watson Health) 의 abductive reasoning 패턴.
>
> **본 시스템 차별점**:
> - 클라우드 침해사고 도메인 특화 (한국 NCP/NHN 8 사고유형)
> - 결정성 100% — 같은 단서 시퀀스 → 같은 사후확률
> - AI 비판단 — 베이즈 산술 + Information Gain 계산만, LLM 미개입
> - "어두운 맵 밝히기" 메타포 — 수사관 직관 정합

### 논문 키워드
*Evidence-based incident classification · Abductive reasoning · Bayesian belief propagation · Information Gain · Dynamic Decision Tree · Cloud security forensics*

---

## 14. 참고 자료

- **Pearl 1988** — Probabilistic Reasoning in Intelligent Systems: Networks of Plausible Inference
- **Peirce 1903** — Abductive Reasoning (Hypothesis Selection)
- **Shockley & Buchanan 1976** — MYCIN: A Knowledge-Based Consultant for Infectious Diseases
- **Shannon 1948** — A Mathematical Theory of Communication (Information Gain)
- **Jaynes 1968** — Prior Probabilities (Maximum Entropy)
- **MITRE ATT&CK Cloud Matrix v14** — 단서 → 사고유형 매핑 표준
- **Verizon DBIR 2024** — 침해사고 통계 (Phase 1 prior, Phase 5.0 에서 uniform 으로 대체)

---

## 15. 진행 체크리스트

- [ ] **Phase 5.0** — priors.json uniform (1/8) 적용 + 베이지안 모드 검증 (47/47 회귀 확인)
- [ ] **Phase A** — `ClueTreeNode` 자료구조 + clue_catalog.json 자동 추출 + 단위 테스트
- [ ] **Phase B** — 백엔드 API 4종 (`/api/clue-tree/*`) + Information Gain 알고리즘
- [ ] **Phase C** — 프론트 트리 UI 노드 클릭·채택·자라기
- [ ] **Phase D** — NextCluePanel Information Gain 통합
- [ ] **Phase E** — V-1 Step 3 레이아웃 재설계
- [ ] **Phase F** — 47 시나리오 단서 시퀀스 마이그레이션 + e2e 회귀
- [ ] **Phase G** — DiscoveryIntroModal "어두운 맵 밝히기" 안내 갱신

각 Phase 완료 시 이 체크리스트 갱신 + 동일 커밋에 push.
