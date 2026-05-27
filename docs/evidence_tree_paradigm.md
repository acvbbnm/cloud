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

### 4.0 **Cold-start 정책** (2026-05-25 추가, byungwoo)

> *"단서 하나를 시작으로 가능성의 트리와 다음 단서 후보를 통해서 결정트리가 진행되어 나가야 수사의 관점에 어울린다"* — 사용자 비전

**시작 시 후보 0개**. start_tree() 가 root 만 만들고 children_candidates 비움.
첫 단서 채택 후 expand_tree() 가 IG 후보 풀을 동적 생성.

**근거**:
- 비유 정합 — "어두운 맵" 은 시작 시 아무것도 보이지 않는 것이 자연
- 학술 정합 — Uniform prior (1/8) 에서 모든 단서의 IG 가 사실상 균등 → 추천 의미 미약. 첫 단서가 posterior 를 기울이면 변별력 등장
- UX 정합 — "꼬리에 꼬리를 무는 트리" — 시작은 사용자의 첫 관찰부터

**첫 단서 입력 방식**: §4.2 또는 §4.3 만 사용. §4.1 (후보 클릭) 은 첫 단서가 들어온 이후부터 가능.

### 4.1 단서 후보 클릭 (가장 일반, 첫 단서 후)
- 현재 트리 leaf 노드에 children candidates (점선 회색)
- 클릭 → 채택 → 단서 노드 확정 (실선 초록) + 사후확률 갱신 + 다음 후보 자동 생성

### 4.2 직접 입력 (첫 단서 진입점)
- 좌측 `CluesInput` 패널 (현재 자산 재활용)
- 사용자가 자유 단서 입력 (예: IP=`115.91.214.5`)
- 트리에 단서 노드 추가 + 다음 후보 갱신

### 4.3 로그 파일 등록 → 자동 단서 추출 (첫 단서 진입점)
- `PartialLogAnalysis` 패널 (현재 자산 재활용)
- 로그 분석 → 매핑된 ATT&CK 기법들을 **단서 후보로 자동 추가**
- 사용자가 후보 중 선택해서 트리에 채택

### 4.4 **1차 정찰 가이드 카드** (Phase N.1 신설, 2026-05-26 byungwoo)

> *사용자 비전: "지금 형태면 첫 단서로 특정 사고 한 쪽으로 쏠릴 확률 높아짐.
>  기본 가이드로 몇 가지 기본 단서·이상징후 같은 걸 입력 후 기본적인 몇 가지
>  정찰 데이터를 기반으로 확률 계산을 시작하자."*

**문제** (§4.0 cold-start 의 부작용):
강한 단서 1개만 채택하면 weights 가 한 사고유형에 ≥30 누적 → posterior 의 그
가설이 50%+ 도달 → 다음 IG 추천이 그 lane 에 편향 → **trap 발생**.

**해결**: cold-start 직후 사고유형 무관 약한 정찰 단서 (Q1 inception / Q2A
alert_type) 2-4개 먼저 누적 → posterior 약 비균등 → 그 후 자체 단서 입력 시
한 쪽 급격한 쏠림 차단.

**학술 정합**:
- NIST SP 800-86 §4.1 *Initial Triage* — Precursors and Indicators 우선 수집
- NIST SP 800-61r2 §3.2 — IDS·SIEM·외부 신고 등 사고 인지 신호 분류

**UI**:
- cold-start (`tree.path.length - 1 < 2`) + 미dismiss 시 `ReconClueCard` 노출
- Q1·Q2A 그룹 → 옵션 클릭 → `expand_tree(source='direct_input')` 호출
- depth ≥ 2 도달 시 자동 숨김 (또는 사용자 ✕ 클릭으로 영구 dismiss)
- 각 옵션 우측에 "주 변별 방향" 배지 (예: `자격증명 탈취 +15`) — 어떤 가설로
  약하게 기우는지 가시화

**API**:
- `GET /api/clue-tree/recon-options` → `{groups: [{node_id, question, options[]}]}`
- 카탈로그 prefix 매칭 (`Q1_inception:` / `Q2A:`) — has_weights 단서만

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

## 11. 구현 계획 — Phase A~H 점진

| Phase | 작업 | 시간 | 위험 |
|---|---|---|---|
| **5.0** | Prior uniform (1/8) 변경 (priors.json 1줄) | 5분 | 0 |
| **A** | `ClueTreeNode` 자료구조 + 단서 카탈로그 자동 추출 (decision_tree.json → clue_catalog.json) + **outcome_flags 정형화 (PDF §17)** | 1.5h | 낮음 |
| **B** | 백엔드 API 4종 + Information Gain 알고리즘 + **Marginalization (음성 증거 처리, PDF §17)** | 3h | 중간 |
| **C** | 프론트 트리 UI — 노드 클릭 → 채택 → 자라기 | 2h | 낮음 |
| **D** | `NextCluePanel` Information Gain 통합 + 후보 시각화 | 1.5h | 낮음 |
| **E** | V-1 Step 3 레이아웃 재설계 (트리 메인, 입력 메인 통합) | 1h | 낮음 |
| **F** | 47 시나리오 단서 시퀀스 마이그레이션 + e2e 회귀 검증 | 1.5h | 중간 |
| **G** | DiscoveryIntroModal 갱신 — "단서로 맵 밝히기" 안내 | 30분 | 0 |
| **H** (신설) | V-7 보드 강화 — networkx GDS 알고리즘 (PageRank·Label Propagation) 이식. PDF §17 채택안 #2. Evidence Tree 완성 후 별도 작업 | 2h | 중간 |
| **합계** | **~13시간** | | |

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

**§17 PDF 검토 (2026-05-25) 에서 추가**
- **BAN — Predicting APT Attack Based on Bayesian Network With MITRE ATT&CK** (IEEE Xplore, 2023) — TTP 이산 확률 변수 DAG + CPT + Marginalization
- **A Digital Twin-Assisted Threat Modeling Framework for Predicting APT Attack Flows in Industrial Control Systems** (MDPI 2024) — Bayesian Network 기반 공격 경로 예측
- **Microsoft Security Blog — Automating threat actor tracking: Understanding attacker behavior for intelligence and contextual alerting** (2021) — 베이지안 그래프 모델 + 조건부 의존성 학습
- **Google Chronicle — Rule-to-Outcome Workflow** — Outcome Contract 정형화 패턴 (`$outcomeIsTechnical`, `$outcomeUserRoleHint`)
- **Palo Alto Networks — Cloud Token Theft Response Playbook** — Verdict Decision Tree (InternalRange·VPNIPList 검증) 실무 사례
- **AWS Security Lake — Transform security logs into OCSF using configuration-driven ETL** — OCSF 다중 클라우드 정규화 청사진

---

## 15. 진행 체크리스트

- [x] **Phase 5.0** — priors.json uniform (1/8) 적용 (Jaynes 1968 Max Entropy) — 베이지안 모드 회귀 43/47, additive 47/47 유지. commit `d9d8f8e`
- [x] **Phase A** — `ClueTreeNode` 자료구조 + clue_catalog.json 자동 추출 + 단위 테스트 — 143 단서 (decision_tree 92 + clue_input 24 + log_analysis 27) + outcome_flags 94/143 + pytest 21/21 PASS. commit `176ad5f`
- [x] **Phase B** — 백엔드 API 4종 (`/api/clue-tree/*`) + Information Gain (KL divergence) + Marginalization (PDF §17.B BAN 정합) + ClueTreeService DB 영속화. pytest 29/29 PASS. commit `e95ad08`
- [x] **Phase C** — 프론트 트리 UI 노드 클릭·채택·자라기 — types/clueTree.ts + api/clueTree.ts + useClueTreeStore + ClueTreeView (react-flow 기반 ROOT→leaf→IG 후보 fan-out, IG 게이지). tsc 무에러 + vite 빌드 OK. commit `706858c`
- [x] **Phase D** — NextCluePanel Information Gain 통합 — IG 모드 (igCandidates·entropy·outcome_flags badge·rationale) 추가. ClueCandidate.outcome_flags 백엔드 dataclass → 응답 → 프론트 타입 전파. pytest 51/51 PASS (1 신규 outcome_flags 회귀 테스트 포함). commit `6bd29b1`
- [x] **Phase E** — V-1 Step 3 레이아웃 재설계 — Step3_EvidenceTreeDiscovery 신설 + TRIAGE_MODE=evidence_tree 백엔드 추가 + Step3_Discovery 가 mode 분기로 위임. ClueTreeView 메인 + NextCluePanel IG 사이드 + CluesInput 직접입력/PartialLogAnalysis 자동채택 3 경로 배선. confidence 도달 시 notify 카드 (사용자 결정 §16). tsc 무에러 + vite 빌드 OK + e2e 47/47 / 43/47 보존. commit `666d0e5`
- [x] **Phase F** — 47 시나리오 단서 시퀀스 마이그레이션 + e2e 회귀 — `scripts/e2e_evidence_tree_test.py` 신설. (Q_node, [option_id]) → decision_tree.json:weight_key → clue_catalog 매핑. composite 가설 허용 (legacy bayesian e2e 와 동일 정책). **결과 43/47 PASS — bayesian baseline 과 정확히 동일** (4 INSIDER T3 약한 시그널 한계 공유). additive 47/47 보존. commit `604506e`
- [x] **Phase G** — DiscoveryIntroModal "어두운 맵 밝히기" 안내 갱신 — `mode='evidence_tree'` prop 분기로 별도 영속화 키 + 패러다임 안내 콘텐츠 (5단계 흐름·4 컴포넌트·학술 근거). Step3_EvidenceTreeDiscovery 가 자동 노출. + `/api/clue-tree/reset` 엔드포인트 + ClueTreeView 헤더 ⟲ 초기화 버튼 (cold-start 마이그레이션 용). commit `fe21776`
- [x] **Phase H** (재정의 2026-05-25, byungwoo) — Bayesian Network + Noisy-OR 단서 추천. PDF §17.B BAN paper 의 단순화 정합 구현. 상세 §18.
  - [x] **H.2** clue_to_attack 매핑 (143 단서 100% 커버, 45 unique 기법, 46 multi-target). commit `5977a20`
  - [x] **H.3** Bayesian Network DAG + Noisy-OR 추론. **e2e 47/47 PASS** (INSIDER T3 약한 시그널 정합 향상). commit `6ed8459`
  - [x] **H.4** TRIAGE_MODE=bayes_net 통합 — config + clue_tree_service 분기 + info_gain.likelihood_fn 주입 + ClueCandidate.techniques 응답 + `/api/clue-tree/explain/{clue_key}` API + 프론트 ATT&CK badge UI + NextCluePanel BN hint. commit `17589eb`
- [x] **Phase I** (2026-05-26, byungwoo 사용자 비전) — IncidentTypeCompass 360° 시각화 + scoring_mode 분기 fix + closure stale fix. 사고유형 8개 anchor (12시→10:30 시계방향 45° 간격) + 사후확률 가중 무게중심 + 단서 누적 궤적 (polyline). 순수 SVG ~330줄. Step3 메인 카드에 🌳 트리 / 🧭 컴퍼스 탭 토글 (sessionStorage 영속화). 학술: Pearl 1988 Belief Simplex Projection + 사용자 비전 "미로 헤쳐나가듯" 메타포 직접 구현. commit TBD
- [x] **Phase J** (2026-05-26, byungwoo) — V-7 보드 networkx GDS (PageRank + Label Propagation) — PDF §17.C 채택 구현.
  - core/board/graph_analytics.py 신설 — build_graph / page_rank / label_propagation_communities / analyze_board
  - InvestigationBoard.get_state 응답에 `gds` 필드 동봉 (pagerank top-3 + communities)
  - pytest test_graph_analytics: 15/15 PASS (PageRank S3 핵심 표적 식별 + Label Propagation 군집 + 결정성 100%)
  - networkx 3.6.1 이미 설치됨 (의존성 추가 X)
  - 학술: Brin & Page 1998 PageRank, Zhu & Ghahramani 2002 LPA, Sheyner 2002 Carnegie Mellon Attack Graph

각 Phase 완료 시 이 체크리스트 갱신 + 동일 커밋에 push.

---

## 16. 사용자 설계 결정 (2026-05-25, byungwoo)

Phase A 착수 전 3가지 핵심 설계점 확정:

| 결정 | 선택 | 구현 영향 |
|---|---|---|
| **단서 카탈로그 추출** | **A. 옵션을 단서로** — 22 노드 × 평균 4.5 옵션 = **~99 단서** | `decision_tree.json` 의 각 option → 단서 1개. weight_key 그대로 likelihood 매핑. 추가로 `clue_types` 24개 + 일부 `partial_analysis_techniques` 합쳐 풀 ~120 단서 |
| **다음 후보 개수** | **동적 (entropy 기반)** | 사후확률 분포의 Shannon entropy 측정<br>• `H ≥ 2.5 bits` (모호) → 후보 **5개** 노출<br>• `1.5 ≤ H < 2.5` (보통) → 후보 **3개**<br>• `H < 1.5 bits` (수렴) → 후보 **2개**<br>※ 8 사고유형 균등 = 3.0 bits (uniform prior 시작점). 1 사고유형 100% = 0 bits. |
| **confidence 도달 시** | **알림만, 사용자 직접 종료** | `primary_prob ≥ 0.65 & gap ≥ 0.20` 도달 시 트리 자동 종료 X. UI 우측 sticky 패널에 "**사고유형 확정 가능: RANSOMWARE 89%** — [확정하고 다음 단계] 버튼" 노출. 사용자가 클릭 안 하면 트리 계속 자라기 가능 (추가 단서 채택 → 사후확률 재갱신). |

### 후보 개수 동적 산출 — 의사코드

```python
import math

def candidate_count(posterior: dict[str, float]) -> int:
    # UNCLASSIFIED 제외, 사고유형만으로 entropy 계산
    p = [v for k, v in posterior.items() if k != "UNCLASSIFIED" and v > 0]
    s = sum(p)
    if s == 0:
        return 5
    p = [x / s for x in p]
    H = -sum(x * math.log2(x) for x in p if x > 0)  # Shannon entropy
    if H >= 2.5:
        return 5
    if H >= 1.5:
        return 3
    return 2
```

### confidence 도달 알림 — UI 동작

```
[우측 sticky]
┌─────────────────────────────────────┐
│ 사고유형 확정 가능                  │
│ RANSOMWARE 89.2%                     │
│ (2위 INSIDER 4.1% · 격차 85.1%p)     │
│                                      │
│ [확정하고 V-2 로그 수집으로] →       │
│ [단서 더 채택]                       │
└─────────────────────────────────────┘
```

사용자 선택 없이 트리는 계속 자랄 수 있음. confidence 갱신 시 알림 카드 업데이트.

---

## 18. Phase H — Bayesian Network + Noisy-OR 단서 추천 상세 계획

> 작성: 2026-05-25, byungwoo
> 상태: 설계 확정, 단계별 의논·구현 대기

### 18.0 배경

**문제 진단** (Phase G 직후 시연 — 본 doc §17 PDF 검토 후 후속):
1. **의미 중복 추천** — 이미 `IP_ADDRESS:tor_vpn` 채택 후 `Q5-CRED:tor_vpn` 도 추천 (동일 정보)
2. **카테고리 monoculture** — top-7 전부 CRED 변별 단서, 다른 가설 변별 단서 0
3. **시퀀스/인과 무시** — Naive IG 는 현재 사후확률만 봄, 단서 i → 단서 j 인과 무시

PDF 청사진 (BAN paper IEEE 2023) 의 **Bayesian Network DAG + CPT** 패러다임이 답.
다만 PDF 의 진짜 BN 은 수만 침해 데이터로 학습 — 캡스톤 범위 초과.

### 18.1 사용자 제시 보완안 (2026-05-25)

3가지 학술 표준 결합:

**(A) 합성 데이터 생성 (사용자 제안 §2)**
- MITRE Atomic Red Team — 700+ ATT&CK 기법별 실행 YAML 정의
- MITRE ATT&CK Flow — 30+ 실제 사고 시퀀스 (Colonial Pipeline, SolarWinds, NotPetya …)
- MITRE ATT&CK Groups — 100+ APT 그룹별 기법 사용
- **샌드박스 실행 없이 YAML/JSON 정의 텍스트만 학습 소스로 활용** (캡스톤 인프라 제약 우회)

**(B) Noisy-OR 모델 (Pearl 1988, 사용자 제안 §3)**
- 풀 CPT: 143 단서 × 2^143 조합 = 계산 불가능
- Noisy-OR: 부모 노드 독립 가정 → 파라미터 지수 → 선형 축소
- 학술 표준 — 보안·리스크 평가 BN 의 정통 단순화

**(C) pgmpy 라이브러리**
- Python 확률 그래픽 모델 표준 라이브러리 (UC Berkeley·CMU 사용)
- `NoisyOrCPD` 클래스 — Noisy-OR 직접 표현
- pip 5MB, 폐쇄망 친화

### 18.2 학술 변호 (논문·발표)

> *"본 시스템은 BAN paper (IEEE 2023) 의 Bayesian Network 패러다임을 따르되,
> 폐쇄망·캡스톤 제약 하에서:
> (1) **합성 데이터** — 기업 기밀 침해 데이터 대신 MITRE 공개 자원 (Atomic Red Team
>     + ATT&CK Flow + ATT&CK Groups) 활용
> (2) **Noisy-OR (Pearl 1988)** — 풀 CPT 의 지수적 파라미터를 선형 스케일로 축소
> (3) **pgmpy** — 학술 표준 확률 그래픽 모델 라이브러리, 결정성 100%
> (4) **폐쇄망 운영** — 학습 1회 (외부 PC), 운영은 정적 JSON 만 사용"*

### 18.3 6단계 구현 계획

```
[1회 학습 — 개발자 PC]
  scripts/build_clue_dag.py
    ├─ H.1 Atomic Red Team + ATT&CK Flow + ATT&CK Groups 다운
    ├─ H.2 우리 143 단서 → ATT&CK 기법 매핑 (clue_to_attack.json)
    ├─ H.3 DAG 구조 학습 (clue_dag.json — 노드·엣지)
    └─ H.4 Noisy-OR 파라미터 추출 (clue_cpt_noisyor.json)
       ↓
[정적 JSON 출력 — 폐쇄망]
  data/triage/external_sources/  (다운받은 원천 데이터)
  data/triage/clue_to_attack.json (단서 ↔ ATT&CK 매핑)
  data/triage/clue_dag.json       (BN DAG 구조)
  data/triage/clue_cpt_noisyor.json (Noisy-OR 파라미터)
       ↓
[런타임 추론 — pgmpy]
  H.5 core/intake/clue_dag_inference.py
    ├─ pgmpy.NoisyOrCPD 로 P(c | accepted_clues) 계산
    └─ 기존 IG + Noisy-OR 가중 결합
  H.6 시연 + e2e 회귀 검증
```

### 18.4 단계별 상세 + 의논 포인트

#### H.1 — 데이터 수집 (~1h)

**작업**:
- `backend/data/triage/external_sources/` 디렉토리 생성
- Atomic Red Team `atomics/` 디렉토리 clone (또는 release zip)
- ATT&CK Flow corpus clone (`center-for-threat-informed-defense/attack-flow`)
- ATT&CK STIX (Groups + Techniques) 다운 (`mitre-attack/attack-stix-data`)

**의논 포인트**:
- 저장 방식 — git submodule vs 정적 zip 복사? (캡스톤은 정적 zip 권장 — 재현성)
- 어느 데이터셋부터? — Atomic Red Team 이 가장 크지만 ATT&CK Flow 가 직접 시퀀스 정보

#### H.2 — 단서 ↔ ATT&CK 매핑 (~1h)

**작업**:
- 우리 143 단서 중 27개는 이미 `TECHNIQUE:T1078.004` 직접 매핑
- 나머지 116개 (`Q5-CRED:tor_vpn`, `IP_ADDRESS:non_korean` 등) 룰 매핑
- 출력: `data/triage/clue_to_attack.json`

**의논 포인트**:
- 1:1 매핑 안 되는 단서 처리 — 예: `Q1_inception:csp_alert` 는 ATT&CK 기법 X (메타 정보)
- 1:N 매핑 — 예: `ACCOUNT:mfa_disabled` → T1556.006 (MFA Bypass) + T1078 (Valid Accounts)
- 자동 매핑 + 수동 검토 비율

#### H.3 — DAG 구조 학습 (~1h)

**작업**:
- ATT&CK Tactic 계층 = 1차 prior (Reconnaissance → Initial Access → Execution → ...)
- ATT&CK Flow JSON 의 실제 시퀀스 = co-occurrence edge
- ATT&CK Groups 의 기법 사용 패턴 = transition 보강
- 출력: `data/triage/clue_dag.json`

**의논 포인트**:
- Edge 임계값 — 몇 번 같이 등장하면 인과 edge? (예: ≥3 그룹 또는 ≥2 flow)
- Cycle 처리 — DAG 보장 위해 ATT&CK Tactic 단계 순서 강제

#### H.4 — Noisy-OR 파라미터 추출 (~1h)

**작업**:
- pgmpy 설치 (`pip install pgmpy`)
- 각 노드별 **leak probability** (부모 없을 때 자발 발생 확률)
- 각 엣지별 **inhibitor probability** (부모 활성화 시 자식 활성화 못할 확률)
- pgmpy `NoisyOrCPD` 객체로 직렬화
- 출력: `data/triage/clue_cpt_noisyor.json`

**의논 포인트**:
- Leak 추정 방식 — Laplace smoothing? (Verizon DBIR prior 단서별 분배?)
- Inhibitor 추정 — Atomic Red Team 빈도 / Flow co-occurrence 결합 가중치

#### H.5 — 알고리즘 통합 (~1h)

**작업**:
- `core/intake/clue_dag_inference.py` 신설
- pgmpy 추론 — `BayesianNetwork.query(['c_j'], evidence=accepted_clues)`
- 기존 IG 와 결합: `score(c) = α × IG(c) + β × P_noisyor(c | accepted_clues)`
- TRIAGE_MODE 환경변수 토글 — `evidence_tree` 기본 활성, fallback 가능

**의논 포인트**:
- α·β 가중치 — 0.5/0.5 시작? 시나리오 검증 후 조정
- pgmpy 추론 비용 — 후보 143개 × 추론 1번 = 응답 시간 영향? (벤치마크 필요)
- fallback — pgmpy 미설치/오류 시 기존 IG 로 자동 전환

#### H.6 — 시연 + 검증 (~1h)

**작업**:
- 시연 1·2·3 재실행 — 중복·monoculture 해소 확인
- e2e 회귀 — additive 47/47 / bayesian 43/47 / evidence_tree 43/47 유지
- 단위 테스트 — `tests/test_clue_dag_inference.py` 신설
- 시연 비교 — 현재 vs 개선 추천 5개 비교 표

**의논 포인트**:
- 합격 기준 — 시연 2 의 카테고리 다양성, 시연 3 의 중복 제거 확인
- e2e 회귀 임계값 — 약간의 PASS 률 변동 허용 (±2건)

### 18.5 학술 인용 보강 (paradigm doc §14)

**추가**:
- **Atomic Red Team (Red Canary)** — Open Source TTP Library, MITRE 공식 매핑
- **MITRE ATT&CK Flow Project** — Center for Threat-Informed Defense, Real-World Incident Sequences
- **pgmpy (Ankan & Panda 2015)** — Python Library for Probabilistic Graphical Models
- **Noisy-OR Model** (Pearl 1988, §3.2.2 — Bayesian Belief Propagation 의 단순화)

### 18.6 의존성 변경

- **pgmpy** 추가 (~5MB) — `requirements.txt` 갱신 필요
- byungwoo 브랜치 개발 단계 — 팀원 머지 시 PR 본문에 학술 변호 포함

### 18.7 H.1 직전 의논 결정 (2026-05-25, byungwoo)

**① 데이터 저장 방식**: **정적 zip + .gitignore** — 데이터 자체는 git 외부, 팀원에게 zip 따로 전달.
**② 데이터 소스 우선순위**: **Atomic Red Team → ATT&CK Flow corpus → ATT&CK STIX** (Atomic 먼저, 시퀀스 prerequisite 직접 추출 위해)
**③ Atomic Red Team 추출 대상**:
  - `attack_technique` (T-id)
  - `prerequisite_techniques` (있으면 transition edge 직접 학습)
  - `display_name` (디버그·발표 자료용)
  - 실행 명령·로그 패턴은 미사용 (실행 안 함)
**④ pgmpy 설치 시점**: **H.1 시작 시 미리** (requirements.txt 갱신 + venv 설치)

### 18.8 진행 체크리스트

- [ ] **H.1** — 외부 데이터 수집 (Atomic Red Team 우선 → ATT&CK Flow → STIX)
- [ ] **H.2** — 우리 143 단서 → ATT&CK 매핑 (`clue_to_attack.json`)
- [ ] **H.3** — DAG 구조 학습 (`clue_dag.json`)
- [ ] **H.4** — Noisy-OR 파라미터 추출 (`clue_cpt_noisyor.json`)
- [ ] **H.5** — pgmpy 추론 통합 (`clue_dag_inference.py`)
- [ ] **H.6** — 시연 + e2e 회귀 + 단위 테스트
- [ ] commit·push (단계마다 별도 commit + 사용자 확인 후 다음 진행)

---

## 17. 외부 청사진 정합성 — PDF 검토 (2026-05-25, byungwoo)

### 검토 문서
`사고 조사 트리 구조화 연구.pdf` (11 페이지) — *"단서 기반 시야 확장형 클라우드 침해사고 대응 트리 아키텍처: OCSF, 기계 학습 및 그래프 분석의 통합 모델"*

### 결론 — 비전 95% 일치

PDF p1 첫 문장 인용:
> *"제안된 '단서를 통해 꼬리에 꼬리를 물며 시야를 넓히고, 최종적으로 전체 맵(사고 유형)을 확정 짓는 트리 구조'는 현대 보안 오케스트레이션·자동화·대응(SOAR) 프레임워크가 지향해야 할 **가장 이상적인 의사결정 모델**을 정확히 묘사하고 있다."*

= `evidence_tree_paradigm.md` §1 "어두운 맵 밝히기" 비전과 사실상 동일. 학술·산업 표준 합치 외부 근거 1건 확보.

### 7-Layer 매칭표

| PDF 의 레이어 | 우리 시스템 | 정합도 |
|---|---|---|
| Root Node = Context Engine (Chronicle Rule-to-Outcome) | V-1 Step 1 + `Q1_inception` 5 옵션 | 70% — Outcome contract 정형화 보강 (§17.A) |
| 단서-맵 트리 비전 | `evidence_tree_paradigm.md` §1 | **95%** |
| OCSF 정규화 (AWS Security Lake) | Layer 2 `OCSFNormalizer` + NCP·NHN 룰 | 90% |
| TRAM NLP 매핑 (SciBERT) | Layer 2 `AttackMapper` (정적 룰) | 40% — **거부** (폐쇄망·AI 비판단 원칙) |
| Bayesian Network DAG + CPT | `bayesian.py` (1-step Naive Bayes) | 60% — **Marginalization 도입 (§17.B)** |
| Neo4j 그래프 DB | Layer 4 `InvestigationBoard` (SQLite) | 50% — **networkx GDS 이식 (§17.C, Phase H)** |
| SOAR 자동 플레이북 | Layer 3 sherpa playbook | 50% — 우리 원칙상 자동 대응 X 유지 |

### 17.A 채택 — Outcome Contract 정형화 (Phase A 통합)

PDF p1-2 참조 — 탐지 규칙이 SOAR 플레이북에 표준화된 Boolean·enum 정형값을 전달해 분기 폭발 억제.

**우리 적용**: `clue_catalog.json` 의 각 단서 항목에 `outcome_flags` 필드 추가.

```json
{
  "Q5_CRED:tor_vpn": {
    "label": "Tor·VPN exit node 출처 확인됨",
    "weights": { "CREDENTIAL_THEFT": 30, ... },
    "outcome_flags": {
      "outcomeIsAnonymizedSource": true,
      "outcomeSourceCategoryHint": "tor_vpn"
    }
  }
}
```

효과: Phase B `/api/clue-tree/expand` 응답에 정형 Boolean 동봉 → 프론트 분기 간소화 + GenAI 셰르파 환각 방지.

### 17.B 채택 — Marginalization (Phase B 베이즈 갱신 확장)

PDF p6-7 참조 — "보안 도구 비활성화는 관찰했는데 그 이전 도구 전송 로그는 못 찾았다" → 관찰되지 않은 변수 합산으로 87% 같은 구체 수치 도출.

**현재 우리**: `bayes_update` 에서 채택된 단서만 likelihood 곱. 미관찰 = 무처리.

**보강**: "기대됐는데 미관찰" 단서 N개에 대해 `(1 − P(c|h))` 별도 likelihood 곱.

```python
def bayes_update_with_negative(
    posterior: dict[str, float],
    positive_clues: list[dict],  # 관찰된 단서들
    expected_but_missing: list[dict],  # 기대됐으나 미관찰
) -> dict[str, float]:
    # positive: P(c|h) 곱
    # negative: (1 − P(c|h)) 곱 — 정보 추출
    ...
```

학술 정합: PDF ref 21 — BAN (IEEE Bayesian Network with MITRE ATT&CK). Pearl 1988 marginalization 정합.

### 17.C 채택 — networkx GDS 알고리즘 이식 (Phase H 신설)

PDF p7-8 참조 — PageRank·Label Propagation 으로 공격자 목표 자산 자동 식별 + blast radius 시각화.

**도입 대상**: V-7 보드 (`ChainNode`·`ChainEdge`) → 단서 트리 완성 후 노드·엣지 누적되면 networkx (in-memory, 폐쇄망 친화) 로 GDS 알고리즘 실행.

- **PageRank** → 공격자가 궁극적으로 노리는 중심 자산 자동 강조 (UI 노드 크기·색상)
- **Label Propagation** → 의심 계정 군집 → blast radius 시각화

**도입 방식**: Neo4j 없음. SQLite `chain_nodes`/`chain_edges` 그대로, networkx 는 분석 단계에서 in-memory 그래프 빌드. 의존성 1개 추가 (`networkx>=3.0`).

**시점**: Phase G 완료 (Evidence Tree V-1 통합 완성) 후 별도 작업.

### 17.D 거부 — SciBERT NLP 자동 매핑

PDF p3-4 — BERT 변종 + Hugging Face + Django + Docker 풀스택.

**거부 사유**:
1. CLAUDE.md 금지사항 #4 — 외부 CDN 사용 X (SNF-01 폐쇄망 원칙). Hugging Face 모델 로드 불가.
2. CLAUDE.md 금지사항 #5 — AI 판단 X. NLP 자동 분류 = AI 판단.

**대체**: 기존 `partial_analysis_techniques` 정적 룰 매핑 유지 + 로그 분석 결과를 단서 후보로 제시 (paradigm §4.3).

### 17.E 한정 도입 — Neo4j 그래프 DB (시연 시각화 보조)

PDF p7-8 — Neo4j + Cypher + GraphQL 풀스택.

**초기 거부 (2026-05-25)**: 폐쇄망 단일 데스크톱 + SQLite 9 테이블 설계서 확정 (DB 담당자 합의 사항).

**재검토 (2026-05-26, easy `3aa5879` PoC, Discord 김병우 제안)** — 244 노드 + 385 엣지 적재 성공. 4 옵션 비교 (`docs/neo4j_poc_결과보고.md` §5) 결과 **옵션 B 채택**:

| 옵션 | 채택 여부 | 사유 |
|---|---|---|
| A. 메인 DB 이관 (SQLite → Neo4j) | ❌ | 설계서 5.1 ERD 재작성 + DB 담당자 합의 + 5/29 마감 리스크 |
| **B. 시연용 시각화 보조** | ✅ | SQLite 메인 유지, read-only 미러 export. CLAUDE.md 9테이블 제약 미위반 |
| C. networkx + react-flow (§17.C) | △ | 메인 그래프 분석엔 그대로 유지 — Phase J 이미 도입 |
| D. 거부 입장 유지 (구 §17.E) | ❌ | 시연 임팩트 손실 |

**현재 운영 정책**:
- **메인 영속화**: SQLite 그대로 (`models.py` 무변경, 설계서 5.1 ERD 무변경)
- **Neo4j 사용처**: 시연 영상 Browser (http://localhost:7474) 캡처 + 발표 자료 그래프 시각화만
- **데이터 흐름**: 시연 직전 `python backend/scripts/neo4j_poc/import_clue_graph.py` 1회 실행 → `next_clue_graph.json` + `clue_to_attack.json` + `priors.json` → MERGE 적재. 양방향 동기화 X.
- **앱 런타임 의존**: 0건 (Neo4j 죽어도 시스템 정상 동작)
- **그래프 분석 알고리즘**: networkx in-memory 유지 (Phase J). Neo4j GDS plugin 미사용.

**산출물** (easy `3aa5879`):
- `backend/scripts/neo4j_poc/import_clue_graph.py` — idempotent MERGE
- `backend/scripts/neo4j_poc/demo_queries.py` — Cypher Q1~Q7
- `backend/scripts/neo4j_poc/reset_password.py` — 초기 비번 변경
- `docs/neo4j_poc_결과보고.md` — 보고서 + 옵션 비교
- `docs/neo4j_재현_가이드.md` — 팀원 재현 절차 (이지호 디스코드 가이드 + 6 보완점 통합)
- `neo4j-tools/` — Community Edition 5.26.26 (.gitignore, 144MB)

**대체 (그래프 분석)**: networkx (Python 라이브러리, in-memory) — Phase J 채택 (§17.C). Neo4j 는 시각화 전용.

---


## 19. Phase K — 사고유형 가이드 통합 (논의 정리, 2026-05-26 byungwoo)

### 19.1 사용자 비전

> "사고유형이 확정되어감에 따라 단서를 기반으로 다음단서 추천말고도 우리
> 수집가이드 만들어둔거도 참고해서 알려주면 좋을거같긴한데. 사고유형에따른
> 가이드니까 특정 사고유형으로 확률이 기울어갈수록 특정단서가 발견될 확률이
> 높아질테니까 오른쪽에 상위 2개 뜨는거 클릭하면 수집가이드도 엿보는게
> 가능하면 좋지않을까 싶은데"

### 19.2 기존 자산 (재활용 대상)

- `core/intake/collection_guide_v2.py` — `CollectionGuideV2.generate(db, caseId)`
- `api/intake.py` — `GET /api/guide/v2?caseId=` (case.incident_type 기반)
- `data/collection_targets/seed_targets.json` — 사고유형별 수집 대상 카탈로그
- 응답 구조: `phases` (Kill Chain 단계 그룹) + `targets` + `completionRate` +
  `applied_modifiers` + `environment_warnings` + 학술 인용 (KISA·NIST·ISO)

### 19.3 갭 — UNCLASSIFIED 상태 preview 불가

현재 `/api/guide/v2` 는 `case.incident_type` **확정된 후** 만 작동.
V-1 Step 3 (트리 진행 중, UNCLASSIFIED) 에서 상위 2 가설 가이드 엿보기 →
**preview API 신설 필요**.

### 19.4 사용자 결정 (AskUserQuestion 답변, 2026-05-26)

| # | 결정 | 답변 |
|---|---|---|
| 1 | 표시 방식 | **B. Inline expand** — 우측 가설 카드 안에서 펼침 (drawer/모달 아님) |
| 2 | 가이드 깊이 | "**해당 사고유형 수집가이드 페이지 열어서 볼 수 있게**" — 별도 페이지/모달 풀 가이드 노출 |
| 3 | API 방향 | **B. 새 endpoint 신설** — `/api/guide/preview?caseId=&incidentType=` |
| 4 | 단서 트리 연동 | "**가이드를 토대로 상위 옵션 하나에서 두개 더 제공**하는 형태" — 가이드 → 추가 단서 후보 2개 도출 |

### 19.5 구현 계획 (Phase K — 코드 작성 전 설계)

#### 단계 1 — 백엔드 preview API

```python
# api/intake.py
@router.get("/guide/preview")
async def guide_preview(
    caseId: str = Query(...),
    incidentType: IncidentType = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    """case 의 incident_type 대신 preview 용 임의 사고유형 가이드 생성.
    case.system_config 환경 보정은 그대로 적용 (실제 environment 정합)."""
    guide = CollectionGuideV2.generate_preview(db, caseId, incident_type=incidentType)
    return {"status": "ok", "data": guide}
```

- 기존 `CollectionGuideV2.generate` 시그니처 갱신 또는 신규 메서드 `generate_preview` 추가
- case.system_config 보정·environment_warnings 그대로 적용
- 응답 구조는 기존 `/api/guide/v2` 와 동일 (재활용)

#### 단계 2 — 프론트 inline expand UI

```tsx
// HypothesisScoreBar.tsx 확장
interface Props {
  ...
  onClickIncidentType?: (type: IncidentType) => void;  // 신규
  expandedType?: IncidentType | null;                    // 펼친 가설
  guidePreview?: GuidePreviewData;                       // 미리보기 데이터
}

// 카드 클릭 → onClickIncidentType(type) → 부모가 expandedType 설정
//   + API 호출하여 guidePreview 채움 → 카드 아래 expand 영역에 렌더
```

표시 항목 (간략):
- Kill Chain phase 별 수집 대상 Top 3
- 각 항목 우선순위 (REQUIRED / CORROBORATING)
- environment_warnings 표시
- **[전체 가이드 페이지 열기 →]** 버튼 — 별도 라우트 또는 모달

#### 단계 3 — "가이드 기반 단서 후보 2개 추가" 산출

> "가이드를 토대로 상위 옵션 하나에서 두개 더 제공" 사용자 요청 핵심.

해석: 가이드의 수집 대상 → 단서 카탈로그 매핑 → IG 후보 풀 + 보조 후보 2개.

매핑 룰 후보:
- `target.kill_chain_phase` + `target.collection_keywords` → `clue_catalog` 의 적합 단서 (휴리스틱)
- 또는 수동 매핑 표 `guide_target_to_clue.json` 신규 생성 (Phase H.2 의 outcome_flags 패턴 차용)

**Phase K.1 — MVP (간략 매핑)**:
- 가이드의 phase 별 첫 REQUIRED 항목 1~2개를 → "[+ 단서로 추가] 보조 버튼" 으로 노출
- 사용자가 클릭하면 단서 카탈로그에서 적합 키 찾아 expand
- 매핑 실패 시 직접 입력 안내

#### 단계 4 — 풀 가이드 페이지

옵션 A: 신규 라우트 `/guide/:caseId/:incidentType` (별도 페이지)
옵션 B: V-1 Setup 내부 step (cf. Step3_Discovery 와 같은 V-1 sub-step)
옵션 C: 풀 모달 (현재 trie 위 overlay)

→ **추가 결정 필요**.

### 19.6 미결 사항 (Phase K 시작 전 확인) — 2026-05-26 byungwoo 확정

| # | 항목 | 결정 |
|---|---|---|
| 1 | 풀 가이드 페이지 위치 | **모달 오버레이** ("클릭하면 팝업창처럼") — 트리 컨텍스트 유지, 라우팅 변경 X |
| 2 | "단서 추가 2개" 매핑 방식 | **C. 휴리스틱 → 부족 시 수동** — MVP keyword 자동 매핑, 실패 항목만 `guide_target_to_clue.json` 으로 수동 보강 |
| 3 | inline expand 영역 높이 | **A. 고정 max-h + 내부 스크롤** (max-h-80 정도). 우측 패널 길이 안정 |
| 4 | 확정 후 연동 | **B. 사용자 [확정] 클릭 후만** — confidence ≥0.65 시에도 preview 유지. 정식 `/api/guide/v2` 는 V-1 Step4 / V-2 에서 |

### 19.7 위험 / 영향

- 기존 `/api/guide/v2` 응답 구조 그대로 재활용 — 회귀 위험 0
- `CollectionGuideV2` 모듈 시그니처 확장 (preview 메서드) — 기존 호출부 영향 없도록 신규 메서드 추가 권장
- HypothesisScoreBar 의 `onExpand` (8종 비교) 와 새 `onClickIncidentType` 충돌 가능 — props 분리 명확화

### 19.8 진행 체크리스트 (Phase K)

- [x] **K.0** — 미결 사항 4건 (§19.6) 확정 (2026-05-26)
- [x] **K.1** — backend `/api/guide/preview` + `CollectionGuideV2.generate_preview` (commit `35631d2`)
- [x] **K.2** — HypothesisScoreBar inline expand + `InlineGuidePreview` + 가이드 캐시
- [x] **K.3** — GuidePreviewModal — 트리 위 풀 가이드 모달 (팝업창)
- [x] **K.4** — `utils/guideToClueMatcher.ts` 휴리스틱 (category_id 영문 + category_name 한국어 키워드 룰) — REQUIRED 우선 + 중복 차단 + 상위 2건 노출
- [x] **K.5** — tsc + vite build + pytest 116/116 + additive e2e 47/47 회귀 0

Phase K 완료 — 다음 commit 으로 paradigm doc + 모든 K.2~K.5 변경 일괄 push.

---

## 20. Phase L — 단서 메타 풍부화 (수사관 가독성)

> 작성: 2026-05-26, byungwoo
> 상태: 완료
> 사용자 피드백: *"다음 단서들 후보에 대한 설명은 어디서 보니. 저게 뭔지 알아야 저걸 찾아보고 단서 후보로 올릴 거 아니야. 저게 어떤 단서이고 왜 연관 있는지를 자세하게 설명해 줄 수 있어야 하는 거 아니니"*

### 20.1 문제 진단

기존 NextCluePanel 의 후보 카드는 다음만 표시:
- 라벨 ("Tor·VPN exit node 출처")
- category · clue_key
- IG 점수
- 한 줄 rationale ("CRED 변별력 최고 P(c|h)=0.45")

→ 수사관이 "**이 단서 실제로 어디서 찾지?**" 알 수 없음. 후보 채택 판단 불가.

### 20.2 5 메타 필드 (Phase L.1)

`scripts/build_clue_descriptions.py` 자동 생성 → `data/triage/clue_descriptions.json`:

| 필드 | 내용 | 자동 생성 룰 |
|---|---|---|
| `description` | 단서의 정의·의미 | label + outcome_flags 힌트 결합 |
| `how_to_find` | `{ncp, nhn, verify}` CSP 경로 | 카테고리별 템플릿 + 핵심 단서 수동 override |
| `examples` | 대표 사례 | 카테고리별 예시 풀 (Tor exit IP, .locked 파일 등) |
| `discrimination_explanation` | 변별력 한국어 풀이 | weights 분석 (강/중/약/무영향 4단계) |
| `academic_source` | 학술 인용 | weight_source 분리 (ISO 프레임워크 별도) |

**자동 생성 + 핵심 6 단서 수동 override** (사용자 결정 C — CSP 구체 경로):
- `IP_ADDRESS:tor_vpn`, `IP_ADDRESS:non_korean`
- `ACCOUNT:mfa_disabled`, `ACCOUNT:newly_created`
- `SERVICE:cloud_trail`
- `Q6-RANSOM:note_found`

### 20.3 백엔드 통합 (Phase L.2)

`core/intake/bayes_net.py:explain_clue` 응답에 5 메타 동봉:
```python
{
  "clue_key": "IP_ADDRESS:tor_vpn",
  "techniques": ["T1090.003"],
  "aggregated_likelihood": {...},
  "source": "bn",
  # L.2 신규
  "description": "접속 IP 가 공개 Tor 출구 노드 또는 익명 VPN ...",
  "how_to_find": {"ncp": "Cloud Insight → ...", "nhn": "...", "verify": "..."},
  "examples": ["115.91.214.5 (Tor exit, KR)", ...],
  "discrimination_explanation": "강한 시그널 — 자격증명 탈취 +30점. ...",
  "academic_source": "MITRE T1090.003",
  "iso_framework": "ISO 27035-1:2023 Assess & Decide",
}
```

`load_clue_descriptions()` 캐시 — `clue_descriptions.json` 1회 로드 후 메모리.

### 20.4 프론트 UI (Phase L.3)

NextCluePanel 의 기존 ▼ 추천 이유 expand 영역에 5 색상 코딩 섹션:

| 섹션 | 색상 | 내용 |
|---|---|---|
| 📖 단서 정의 | brand-teal | description |
| 🔍 어디서 찾나 | blue | NCP/NHN/verify 3행 |
| 📋 예시 | amber | examples 리스트 (mono font) |
| 💡 왜 변별력 있나 | emerald | discrimination_explanation |
| 📚 학술 근거 | purple | academic_source + iso_framework |

기존 "추론 경로 (BN vs legacy)" + "ATT&CK 기법별 영향" + "Top-3 likelihood" 그대로 보존.

### 20.5 검증

- 143 단서 모두 메타 생성 (override 6 + outcome 힌트 94 + 예시 0 누락)
- pytest 74/74 PASS (clue_tree + clue_tree_service + info_gain + bayes_net)
- additive e2e 47/47 PASS (회귀 0)
- API live: `IP_ADDRESS:tor_vpn` 응답에 description / NCP 경로 / examples / academic_source 모두 동봉 확인

### 20.6 산출물

| 파일 | 줄수 | 역할 |
|---|---|---|
| `scripts/build_clue_descriptions.py` | 432 | 자동 생성 스크립트 + override 6건 |
| `data/triage/clue_descriptions.json` | 143 entries | 메타 산출물 |
| `core/intake/bayes_net.py` | +52 | load_clue_descriptions + explain_clue 확장 |
| `frontend/src/types/clueTree.ts` | +18 | ExplainClueResponse 풍부 메타 필드 |
| `frontend/src/components/NextCluePanel.tsx` | +95 | 5 섹션 UI |

---

## 21. Phase M — 2-zone 컴퍼스 + 복합 가설 chain (논의 정리, 2026-05-26 byungwoo)

> 상태: 설계 정리, M.1 코드 착수 전 의논 단계

### 21.1 사용자 비전 (2 인용)

#### 비전 ① — 게임 RPG 비유 (Zone 1 → Zone 2 전환)

> *"트리깊이 + 핵심단서? 코어단서? 같은 느낌이면 좋겠는데.
> 게임에서도 어느정도 맵을 탐험해야 보스 나오잖아.
> 코어단서 — 보스, 트리깊이 — 맵탐색의 역할인거지."*

- **맵 탐색** = 트리 깊이 (단서 N개 채택) — 광범위 정보 수집
- **보스 발견** = 코어 단서 (가설 결정적 시그널) — 강력한 증거
- 둘 다 만족해야 Zone 2 "맵 열림"

#### 비전 ② — 복합 공격 chain (단일 사고유형 확정 부정)

> *"내가 원하는건 열려있는 가능성이고. 사실 하나의 공격유형만 일어난다는건
> 말이 안되잖아. 복합적으로 공격이 일어났을텐데 사고유형 하나만 확정해
> 가는 방식은 틀린 거 같은데. 흠 좋은 방법 없을까."*

→ 학술 정합 핵심: **MITRE ATT&CK Kill Chain** — 실제 침해는 단일 사고유형이 아니라 **단계 시퀀스**.

```
예시 실제 시나리오:
  PHISH (Initial Access TA0001)            ← Top 3 (지난 단계)
     ↓
  CRED THEFT (Credential Access TA0006)    ← Top 2 (이전 단계)
     ↓
  PRIV ESCALATION (TA0004)
     ↓
  DATA EXFILTRATION (TA0010)
     ↓
  RANSOM (Impact TA0040)                    ← Top 1 (현재 진행 중)
```

Top 1 가설 = "현재 가장 가능성 큰 단계", Top 2-3 = "이전 / 동반 단계". 단일 확정 X.

### 21.2 기존 컴퍼스 한계 (Diminishing Returns)

현재 `IncidentTypeCompass.tsx` 좌표 계산:

```python
radiusForDepth(depth)     # depth 1 → 8%·R, depth 15 → 85%·R
temperatureForDepth(depth)  # depth 1 → T=4 (평탄), depth 15 → T=1 (실제)
```

**관찰된 문제**:
- depth 1-5: 점이 크게 이동 (uniform → concentrated 변화 큼)
- depth 5-14: 점 거의 정지 (이미 95% 도달, 추가 단서 영향 미미)

**수학적으로는 정상** (베이즈 갱신 diminishing returns) — 그러나 사용자 직관과 불일치. 다른 가설로 전환 가능성 시각화 어려움.

### 21.3 사용자 결정 (2026-05-26)

| # | 항목 | 결정 |
|---|---|---|
| 1 | Zone 전환 트리거 | **depth ≥ N AND max(P(c\|h)) ≥ M** — 게임 비유 (맵 탐색 + 보스 단서) |
| 2 | Zone 2 추천 방식 | **복합 가설 chain** — 단일 확정 X. ATT&CK Kill Chain 단계 시퀀스 |
| 3 | 컴퍼스 시각 | **A. 동심원** (내부 원 + 외부 원 + 점 이동) |

### 21.4 Zone 1 → Zone 2 전환 알고리즘

```python
def is_zone2_unlocked(tree: ClueTree) -> bool:
    """게임 RPG 비유 — 맵 탐색 + 보스 단서 모두 충족."""
    # ① 맵 탐색 — 트리 깊이
    depth = max(node.depth for node in tree.nodes.values())
    if depth < 3:
        return False

    # ② 보스 단서 — 가장 강한 likelihood
    max_likelihood = 0.0
    for node in tree.nodes.values():
        if node.clue_key == "__ROOT__":
            continue
        # node.score_delta 의 최대 변화량 또는 카탈로그의 max P(c|h)
        weights = catalog[node.clue_key].get("weights", {})
        lk = weights_to_likelihood(weights)
        max_likelihood = max(max_likelihood, max(lk.values()))

    return max_likelihood >= 0.45
```

**N=3, M=0.45 초기값** — 사용자 시연 후 미세조정.

### 21.5 복합 가설 chain (ATT&CK Kill Chain 정합)

#### 가설 → Kill Chain 단계 매핑

| 사고유형 | ATT&CK Tactic | Kill Chain 단계 |
|---|---|---|
| PHISH_INITIAL_ACCESS | TA0001 Initial Access | 1 |
| CREDENTIAL_THEFT | TA0006 Credential Access | 2 |
| PRIVILEGE_ESCALATION | TA0004 Privilege Escalation | 3 |
| INSIDER_THREAT | TA0008 Lateral Movement | 4 |
| MISCONFIG_EXPOSURE | TA0007 Discovery (Misconfig 사전 노출) | 4 |
| AUDIT_LOG_TAMPERING | TA0005 Defense Evasion | 5 |
| DATA_EXFILTRATION | TA0010 Exfiltration | 6 |
| RANSOMWARE | TA0040 Impact | 7 |

#### Zone 2 추천 알고리즘

```python
def zone2_chain_candidates(posterior, accepted_clues) -> dict:
    """복합 가설 chain — Top 3 가설을 ATT&CK 단계로 정렬.

    각 가설별 단서 추천 분리. 사용자가 어느 단계 파볼지 선택.
    """
    top3 = sorted(
        [(h, p) for h, p in posterior.items() if h != "UNCLASSIFIED"],
        key=lambda x: -x[1],
    )[:3]

    # Kill Chain 단계 순으로 재정렬
    chain = sorted(top3, key=lambda x: KILL_CHAIN_ORDER[x[0]])

    # 각 가설마다 변별력 큰 단서 2-3개 추천
    per_hypothesis = {}
    for hyp, prob in chain:
        per_hypothesis[hyp] = top_clues_for_hypothesis(
            hyp, accepted_clues, k=3
        )
    return {
        "chain": chain,  # Kill Chain 시간순
        "per_hypothesis": per_hypothesis,
    }
```

### 21.6 컴퍼스 동심원 시각 설계

```
                    Zone 2 (외부 원, R · 100%)
            ╭─────────────────────────────────╮
           /  ◉ 사고유형 확정 영역             \
          /    "보스 발견 → 가설 chain 구체화"  \
         /                                       \
        │                                         │
        │      ╭─ Zone 1 (내부 원, R · 50%) ─╮    │
        │      │                              │    │
        │      │   ⊕ 광범위 탐색 영역          │    │
        │      │   "맵 탐색 단계"              │    │
        │      │                              │    │
        │      ╰──────────────────────────────╯    │
        │                                          │
         \                                        /
          \                                      /
           \                                    /
            ╰──────────────────────────────────╯

  • 점 위치:
    - Zone 1 미진입: 내부 원 안 (사후확률 좌표)
    - Zone 2 진입 후: 외부 원 부근 (1위 가설 anchor 쪽)

  • 동심원 사이 경계선: depth 3 + max_lk 0.45 트리거 후 "맵 열림" 애니메이션

  • 화살표·점선: 가설 chain (PHISH → CRED → IMPACT) 표시
```

### 21.7 구현 계획

#### M.0 — paradigm doc §21 정리 (본 섹션, 진행 중)

#### M.1 — 백엔드 zone 메타 + chain 추론 (~1h)

- `core/intake/clue_tree_service.py`:
  - `_build_response` 에 `zone` 필드 (1 또는 2) 추가
  - `is_zone2_unlocked()` 헬퍼 (`zone_logic.py` 신설)
- `core/intake/zone_logic.py` 신설:
  - `is_zone2_unlocked(tree, posterior)` — 트리거 평가
  - `compute_attack_chain(posterior)` — Top 3 → Kill Chain 순 재정렬
  - `core_clue(tree)` — 보스 단서 (가장 강한 likelihood 단서) 식별

#### M.2 — 프론트 동심원 시각 (~1.5h)

- `components/IncidentTypeCompass.tsx`:
  - `Zone 1 inner_circle` (R · 0.5) + `Zone 2 outer_ring` SVG 추가
  - 점 위치 — `zone === 2` 면 외부 원 anchor 가중평균, 아니면 내부 (현재 로직)
  - 전환 애니메이션: 점이 외부로 이동 + "🗺 맵 열림" 알림 카드

#### M.3 — Zone 2 chain UI (~1.5h)

- `components/AttackChainCard.tsx` 신설:
  - Top 3 가설을 Kill Chain 단계 순 시각화 (좌→우 화살표)
  - 각 가설 클릭 → 해당 가설별 단서 추천 expand
- `NextCluePanel.tsx` 에 `mode='chain'` props 추가:
  - Zone 1 (legacy) — 통합 IG 후보 풀
  - Zone 2 (chain) — Top 3 가설 분리 + 가설별 단서 그룹화

#### M.4 — paradigm doc 갱신 + 검증 + commit·push (~30분)

- §21 체크리스트 [x]
- pytest + e2e 회귀
- tsc + vite build

**총 ~5h**.

### 21.8 결정 사항 (2026-05-26 byungwoo 확정)

| # | 항목 | 결정 |
|---|---|---|
| 1 | 트리거 N·M 값 | **시연 후 fit** — 초기값 `N=3, M=0.45` 그대로 적용, 47 시나리오 검증으로 조정. **사전 측정 (`scripts/e2e_phase_m_zone_test.py`, 2026-05-26):** Zone 2 진입 19/47 (40.4%) · 회귀 0/47 · chain 정합 47/47 — 권장 범위 30~90% 안에 들어옴, 그대로 유지 |
| 2 | Top 몇 개 chain | **Top 3 기본** — "꼬리에 꼬리를 물며 확장 가능성도 열어둠" (장기적으로 4-5 확장 가능) |
| 3 | 단일 가설 우세 시 | **동일 Top 3 적용** — 95% 우세여도 chain 표시 (이전 단계 추론 가능성 유지) |
| 4 | Kill Chain 매핑 | **§21.5 표 그대로 진행** (필요 시 추후 보강) |
| 5 | Zone 2 → Zone 1 회귀 | **회귀 허용** — "갈피를 못 잡겠다 싶으면 회귀해서 다시 조사" |

#### 21.8.1 회귀 알고리즘 (결정 5)

Zone 2 진입 후라도 다음 조건 시 Zone 1 로 회귀 가능:

```python
def should_regress_to_zone1(tree, posterior) -> bool:
    """Zone 2 → Zone 1 회귀 — 가설 모호 + 사용자 명시 요청 시."""
    # 자동 회귀: 사후확률이 다시 모호해지면 (entropy 상승)
    H = entropy_bits(posterior)
    if H >= 2.0:  # uniform 에 가까움 — Zone 1 으로
        return True

    # Top 1 우세가 사라짐 (예: 새 약한 단서로 분포가 뒤집힘)
    top = top_n(posterior, n=2)
    if len(top) >= 2 and (top[0][1] - top[1][1]) < 0.10:
        # gap < 10% — 다시 모호
        return True

    return False  # 그 외에는 사용자 명시 [Zone 1 으로 회귀] 버튼만
```

**UI**: Zone 2 헤더에 `⤺ 광범위 탐색으로 회귀` 버튼 + entropy 상승 시 자동 알림.

### 21.9 위험 / 영향

- **컴퍼스 좌표 변경 시각**: 기존 사용자가 봤던 시각과 크게 다름 — 적응 필요
- **TRIAGE_MODE 호환**: additive·bayesian·bayes_net·evidence_tree 4 모드 모두 zone 필드 응답해야 — fallback 정책 명확화
- **paradigm doc §16 정합**: "단일 사고유형 자동 종료 X" 정책은 그대로. Zone 2 의 chain 도 사용자가 "확정" 클릭해야 V-2 진행

### 21.10 진행 체크리스트

- [x] **M.0** — paradigm doc §21 정리 (commit `77e85e0`)
- [x] **M.1** — 백엔드 `zone` 필드 + `zone_logic.py` + chain 추론 (byungwoo, 2026-05-26, commit `0cd7960`)
  - `core/intake/zone_logic.py` 신설 — `is_zone2_unlocked` / `core_clue_likelihood` / `should_regress` / `compute_attack_chain` + `KILL_CHAIN_ORDER`
  - `core/intake/clue_tree_service.py:_build_response` 응답에 `zone` / `attack_chain` / `core_clue_likelihood` / `regress_suggested` 4 필드 추가
  - `tests/test_zone_logic.py` 12 케이스 PASS (depth·likelihood·회귀·chain 순)
  - 회귀 검증: `tests/` 290 passed · evidence_tree e2e 47/47 · additive e2e 47/47
- [x] **M.2** — 컴퍼스 동심원 시각 + 전환 애니메이션 (byungwoo, 2026-05-26)
  - `types/clueTree.ts` — `AttackChainStep` 타입 + `ClueTreeResponse` 에 4 필드 추가
  - `components/IncidentTypeCompass.tsx` — 내부 원 (R·0.5, Zone 1 경계 amber) + 외부 원 (R, Zone 2 진입 시 emerald 강조) + Zone 라벨 + 헤더 Zone 배지 + 회귀 권고 배지 + 점 zone 2 boost (최소 R·0.55) + CSS transition 부드러운 이동 + 하단 zone-aware 안내
- [x] **M.3** — Zone 2 chain UI — AttackChainCard + NextCluePanel mode (byungwoo, 2026-05-26)
  - `components/AttackChainCard.tsx` 신설 — Top 3 가설 Kill Chain 가로 시각화 (좌 PHISH → 우 RANSOM) + 가설 클릭 토글 + 회귀 권고 알림 + 회귀 버튼
  - `components/NextCluePanel.tsx` — `mode='chain'` + `chainFilterHypothesis` props 추가. rationale 기반 가설 변별 단서 필터링 + 헤더 chain 배지 + 빈 결과 안내
  - `views/V1_Setup/Step3_EvidenceTreeDiscovery.tsx` — `chainFilterHypothesis` state + Zone 2 진입 시 `AttackChainCard` 노출 + Zone 1 회귀 시 자동 필터 해제 + `regress_suggested` 1회 토스트 알림
- [x] **M.4** — 검증 + commit·push (byungwoo, 2026-05-26, commit `af3dbda`)
  - frontend: `npx tsc --noEmit` 0 errors · `npx vite build` success (657 kB, 2.73s)
  - backend 회귀: pytest `tests/` 290 passed · evidence_tree e2e 47/47 · additive e2e 47/47
- [x] **M.5** — Phase M 통합 e2e 회귀 (byungwoo, 2026-05-26)
  - `scripts/e2e_phase_m_zone_test.py` 신설 — 47 시나리오 zone/chain/regress 정량 측정
  - **결과**: Zone 2 진입 19/47 (40.4%) · 회귀 0/47 · chain 정합 47/47
  - lane 별 Zone 2: RANSOM 78% · ROUTER 100% · INSIDER/MISCFG 33% · CRED 25% · SHORT/TERM 0%
  - 트리거 N=3, M=0.45 권장 범위 (30~90%) 안 → 그대로 유지. 시연 후 fit 불필요 가능성

## Phase N — 복합 가설 추적 강화 (2026-05-26, byungwoo)

> 사용자 비전 (2026-05-26 추가):
> 1. *"첫 단서로 특정 사고 한쪽 쏠림 방지" — 사고유형 무관 정찰 단서 먼저 누적*
> 2. *"99% 한 가설 쏠림 차단" — 복합 공격이 정상 (paradigm §21.1 ②)*
> 3. *"특정 단계 도달 후 그 사고유형에서 시작해서 연관된 다른 공격도 찾아가기" — 다단계 chain*

### N 체크리스트

- [x] **N.1** — 1차 정찰 단서 가이드 카드 (byungwoo, 2026-05-26, commit `b9f25ff`)
  - `GET /api/clue-tree/recon-options` — Q1·Q2A 그룹별 15 옵션 반환 (max weight ≤ 35)
  - `frontend/src/components/ReconClueCard.tsx` 신설 — cold-start (depth < 2) 노출
  - paradigm doc §4.4 신설 — NIST SP 800-86 §4.1 Initial Triage 정합
- [x] **N.2** — Robust Bayes ε-contamination Floor (byungwoo, 2026-05-26)
  - `core/intake/bayesian.py:apply_robust_floor` 신설 — Berger 1985 학술 정합
  - `bayes_update` 후처리 통합 — 8 가설 각 최소 1% floor (ε=0.08 default)
  - `settings.ROBUST_FLOOR_EPSILON` 환경변수 토글 (0=비활성, 0.08=권장)
  - 검증: 단위 테스트 8/8 PASS · evidence_tree e2e 47/47 · additive e2e 47/47 · Phase M e2e 19/47 동일
  - 효과: 단서 4회 누적 + 강한 likelihood 0.95 시 CRED 압축됨 (99%→92.08%), 나머지 7 가설 각 ≥1%
- [x] **N.3** — 가설별 신뢰도 시계열 sparkline (byungwoo, 2026-05-26, commit `b217de6`)
  - `components/HypothesisSparkline.tsx` 신설 — path 의 posterior_after[h] 시계열 SVG polyline
  - `AttackChainCard.tsx` 통합 — Top 3 가설 카드에 sparkline 동봉 (width 56 · height 14)
  - 학술 정합: MITRE ATT&CK Kill Chain (TA0001~TA0040) · Mandiant 2023 Dwell Time
  - 효과: 단일 99% 쏠림이 아닌 가설별 시간순 활성 곡선 시각화 — "어느 시점에 강했는가"
- [x] **N.4.1** — Stage Transition Matrix 백엔드 (byungwoo, 2026-05-26)
  - `core/intake/stage_transition.py` 신설 — 8×8 매트릭스 + compute_stage_prior + advance_to_next_stage
  - `core/intake/clue_tree.py` — ClueTree 에 `confirmed_hypotheses`, `stage` 필드 추가 (legacy 호환)
  - `core/intake/clue_tree_service.py:advance_stage` — 다음 stage 진입 + baseline 갱신 + 후보 재계산
  - `core/intake/clue_tree_service._build_response` — `stage`/`confirmed_hypotheses`/`is_multistage`/`chain_description` 4 필드 추가
  - `POST /api/clue-tree/advance-stage` 엔드포인트
  - `tests/test_stage_transition.py` 15/15 PASS · 전체 313/313 · e2e 47/47 · Phase M e2e 19/47 동일
  - **라이브 검증**: Stage 2 (CRED 확정) → PRIV 30%/DATA 20%/INSIDER 15%/RANSOM 12% / Stage 3 (CRED+PRIV) → DATA 31.6%/RANSOM 26.3%
- [x] **N.4.2** — Step 3 Stage 2 UI (byungwoo, 2026-05-26)
  - `frontend/src/components/MultiStageBoard.tsx` 신설 — 확정 가설 chain 시간순 가로 시각화 + Phase label + Stage 번호
  - `Step3_EvidenceTreeDiscovery.tsx` — 좌측 메인 상단 MultiStageBoard 노출 (confirmed ≥ 1) + 확정 카드에 [🔗 다음 단계 추적] 버튼 (수동) + [확정하고 V-2 로 →] 버튼 (legacy 단일) 양립 제공
  - `types/clueTree.ts` — ClueTreeResponse 에 stage/confirmed_hypotheses/is_multistage/chain_description 추가
  - `api/clueTree.ts:advanceClueTreeStage` + `stores/useClueTreeStore.ts:advanceStage` 액션
- [ ] **N.4.3** — V-7 보고서 multi-stage chain 통합

---

## 23. Phase N.4 — Multi-Stage Attack Chain (paradigm 완성형, 2026-05-26 byungwoo)

> *사용자 비전 (2026-05-26):*
> *"특정 단계 도달 후 그 사고유형에서 시작해서 연관된 다른 공격도 찾아가는걸 해보면 좋겠는데"*
> *"확정된 첫 사고유형의 위치가 시작점이 되도록. 확정 가설 빼고 이 사고유형이랑 밀접한 연관 가진 다른 사고유형 가중치가 조금 더 높으면 좋을거같은데"*

### 23.1 동기

paradigm §21.1 ② "복합 공격이 정상" 비전의 진짜 완성. 현재 Phase M chain UI 가 "동시 가능성" 만 보여줌. N.4 는 **시간순 단계 전이** 를 추적 — Stage 1 확정 → Stage 2 새 baseline → ...

### 23.2 학술 정합

- **MITRE ATT&CK Flow** (2023) — 9 published flows phase transition 빈도
- **Mandiant M-Trends 2024** — DATA → RANSOM 0.50 double extortion 정석
- **Verizon DBIR 2024** — 사고 패턴별 후속 단계 분포
- **1-step Markov Chain on ATT&CK Tactics** — 상태 = 가설, 전이 = 매트릭스
- **Atomic Red Team** (Phase H.1 외부 데이터) — 단일 기법 atomic chain 빈도

### 23.3 알고리즘

```
1. Stage 1 진행 (paradigm §1~§22)
   → CREDENTIAL_THEFT 92% 확정 (Robust Floor 1% N.2 적용)
   → 사용자 [확정하고 다음 단계 추적] 클릭

2. POST /api/clue-tree/advance-stage { confirmed_hypothesis: "CREDENTIAL_THEFT" }
   → confirmed_hypotheses = ["CREDENTIAL_THEFT"]
   → stage = 2
   → posterior_current = STAGE_TRANSITION_MATRIX["CREDENTIAL_THEFT"]
                       = {PRIV: 0.30, DATA: 0.20, INSIDER: 0.15, RANSOM: 0.12, ...}
   → CRED 자기 자신은 0 (anchor freeze)
   → confidence_reached = False (새 stage 진행 위해 reset)

3. Stage 2 단서 누적 (기존 expand_tree 동작 그대로)
   → Top 3 chain 시각화 (sparkline N.3)
   → confidence_reached 시 다시 [확정] 가능

4. 반복 — Stage 3 (예: PRIV 확정 → DATA 31.6%/RANSOM 26.3%)
```

### 23.4 매트릭스 핵심 패턴

| 확정 → 다음 (Top 1) | 가중치 | 근거 |
|---|---|---|
| PHISH → CRED | 0.40 | ATT&CK Flow #4 Storm-0558 정석 |
| CRED → PRIV | 0.30 | 탈취된 자격으로 권한 상승 |
| PRIV → DATA | 0.30 | 권한 상승 후 유출 (탈취 목적) |
| MISCFG → DATA | 0.30 | CSA Top Threats — public 노출 직결 |
| AUDIT → RANSOM | 0.35 | 흔적 지움 → 랜섬 동반 |
| **DATA → RANSOM** | **0.50** | Mandiant 2024 double extortion |
| **RANSOM → DATA** | **0.45** | 협박용 백업 (역방향) |
| INSIDER → DATA | 0.30 | 내부자 유출 정석 |

### 23.5 영향 / 위험

- **paradigm §16 정합**: 사용자가 [확정] 클릭해야 진행 — 자동 종료 X 정책 그대로
- **결정성 100%**: 같은 확정 시퀀스 → 같은 stage prior. 정적 매트릭스 (AI 비판단)
- **legacy 호환**: ClueTree 의 `confirmed_hypotheses`/`stage` 필드는 default [], 1 — 기존 트리 자연 호환
- **시연 임팩트**: "CRED → PRIV → DATA 3단계 복합 공격" 같은 자동 chain 보고서 — 경쟁 시스템 (CrowdStrike·Mandiant) 단일 케이스 종결 대비 차별화 최대

**팀원 위임**: byungwoo (팀장) 가 구현 안 함. §22 팀원 구현 가이드 참조.

---

## 22. Phase M 팀원 구현 가이드 (2026-05-26 byungwoo)

> 본 섹션은 Phase M.1~M.4 를 다른 팀원이 구현할 수 있도록 코드 스켈레톤·파일 위치·테스트 기준을 명시한다. byungwoo (팀장) 는 미결 5건 결정·설계 완료 (§21.8) 후 위임. 각 단계 commit 시 본 체크리스트 (§21.10) 갱신 + paradigm doc PR 동일 커밋에 포함.

### 22.1 공통 — 시작 전 부팅 시퀀스

1. `git fetch origin && git checkout byungwoo && git pull`
2. `docs/팀원_셋업_가이드.md` §2-3 따라 venv + npm install + external_sources 압축 해제
3. **본 doc §1~§21 통독** — Evidence Tree 패러다임·사용자 비전 이해 필수
4. **CLAUDE.md 규칙 준수** — 디렉토리 구조·네이밍·금지사항

---

### 22.2 M.1 — 백엔드 zone + chain 추론 (예상 ~1h)

#### M.1.1 — 신규 파일: `core/intake/zone_logic.py`

```python
"""Phase M (2026-05-26) — 2-zone 컴퍼스 + ATT&CK Kill Chain 정합 추론."""
from __future__ import annotations

from core.intake.bayesian import top_n
from core.intake.clue_tree import ClueTree, posterior_entropy
from core.intake.info_gain import load_catalog, weights_to_likelihood


# 사고유형 → ATT&CK Kill Chain 단계 (§21.5 표)
KILL_CHAIN_ORDER = {
    "PHISH_INITIAL_ACCESS": 1,
    "CREDENTIAL_THEFT": 2,
    "PRIVILEGE_ESCALATION": 3,
    "INSIDER_THREAT": 4,
    "MISCONFIG_EXPOSURE": 4,
    "AUDIT_LOG_TAMPERING": 5,
    "DATA_EXFILTRATION": 6,
    "RANSOMWARE": 7,
}

# 트리거 초기값 (시연 후 fit — §21.8 #1)
TRIGGER_MIN_DEPTH = 3
TRIGGER_MIN_LIKELIHOOD = 0.45

# 회귀 임계값 (§21.8.1)
REGRESS_ENTROPY_THRESHOLD = 2.0
REGRESS_GAP_THRESHOLD = 0.10


def core_clue_likelihood(tree: ClueTree) -> float:
    """채택된 단서 중 가장 강한 likelihood (보스 단서) 반환."""
    catalog = load_catalog().get("clues", {})
    max_lk = 0.0
    for node in tree.nodes.values():
        if node.clue_key == "__ROOT__" or node.clue_key not in catalog:
            continue
        weights = catalog[node.clue_key].get("weights", {})
        if not weights:
            continue
        lk = weights_to_likelihood(weights)
        if lk:
            max_lk = max(max_lk, max(lk.values()))
    return max_lk


def is_zone2_unlocked(tree: ClueTree, posterior: dict) -> bool:
    """게임 RPG 비유 — 맵 탐색 + 보스 단서 모두 충족."""
    # ① 맵 탐색 — 트리 깊이
    depth = max((n.depth for n in tree.nodes.values()), default=0)
    if depth < TRIGGER_MIN_DEPTH:
        return False

    # ② 보스 단서 — 가장 강한 likelihood
    return core_clue_likelihood(tree) >= TRIGGER_MIN_LIKELIHOOD


def should_regress(posterior: dict) -> bool:
    """Zone 2 → Zone 1 자동 회귀 조건 (§21.8.1)."""
    H = posterior_entropy(posterior)
    if H >= REGRESS_ENTROPY_THRESHOLD:
        return True
    top = top_n(posterior, n=2)
    if len(top) >= 2 and (top[0][1] - top[1][1]) < REGRESS_GAP_THRESHOLD:
        return True
    return False


def compute_attack_chain(posterior: dict) -> list[dict]:
    """Top 3 가설을 Kill Chain 단계 순으로 재정렬 (§21.5)."""
    top3 = top_n(posterior, n=3)
    chain = sorted(
        top3,
        key=lambda x: KILL_CHAIN_ORDER.get(x[0], 99),
    )
    return [
        {
            "hypothesis": h,
            "probability": p,
            "kill_chain_phase": KILL_CHAIN_ORDER.get(h, 99),
        }
        for h, p in chain
    ]
```

#### M.1.2 — 수정 파일: `core/intake/clue_tree_service.py`

`_build_response` 응답에 `zone` + `attack_chain` 필드 동봉:

```python
# 기존 imports 위에 추가
from core.intake.zone_logic import (
    compute_attack_chain,
    is_zone2_unlocked,
    should_regress,
)

# _build_response 안 (return dict 부분 수정)
def _build_response(tree: ClueTree) -> dict:
    # ... (기존 코드)
    confidence = evaluate_confidence(tree.posterior_current, depth=current_depth)

    # Phase M 신규 — zone + chain
    zone2 = is_zone2_unlocked(tree, tree.posterior_current)
    regress = zone2 and should_regress(tree.posterior_current)
    final_zone = 1 if (not zone2 or regress) else 2

    return {
        # ... (기존 필드)
        "confidence": confidence,
        # Phase M 신규
        "zone": final_zone,                                # 1 또는 2
        "attack_chain": compute_attack_chain(tree.posterior_current),
        "core_clue_likelihood": core_clue_likelihood(tree),
        "regress_suggested": regress,
    }
```

#### M.1.3 — 단위 테스트: `tests/test_zone_logic.py` (신규)

검증 케이스 (최소 8):
- depth < 3 → Zone 1 (트리거 미달)
- depth = 3 + max_lk < 0.45 → Zone 1
- depth = 3 + max_lk ≥ 0.45 → Zone 2 (트리거 충족)
- depth = 10 + max_lk = 0.30 → Zone 1 (보스 단서 약함)
- Zone 2 진입 후 entropy 2.5 bits → 회귀 권고
- Zone 2 진입 후 gap 5% → 회귀 권고
- compute_attack_chain — RANSOM 70 + CRED 20 + PHISH 5 → Kill Chain 순 (PHISH 1·CRED 2·RANSOM 7)
- compute_attack_chain — Top 3 미만 (가설 1개만) → 빈 chain 또는 부분 chain 안전

#### M.1.4 — 합격 기준

- pytest `tests/test_zone_logic.py` 통과
- 기존 `test_clue_tree_service.py`, `test_clue_tree.py` 회귀 0
- e2e `scripts/e2e_evidence_tree_test.py` 47/47 PASS (zone 도입이 기존 추론 영향 X)
- API live test:
  ```bash
  curl http://127.0.0.1:8000/api/clue-tree?caseId=<test> | jq '.data.zone, .data.attack_chain'
  ```

#### M.1.5 — commit 메시지 예시

```
feat(evidence-tree): M.1 — 2-zone 추론 + ATT&CK chain (작업자명)

paradigm doc §21·§22.2 정합:
  - core/intake/zone_logic.py 신설 (is_zone2_unlocked + compute_attack_chain + should_regress)
  - clue_tree_service._build_response 응답에 zone/attack_chain/core_clue_likelihood 추가
  - tests/test_zone_logic.py 8 케이스
검증: pytest <건> · e2e 47/47 회귀 0 · API live OK
```

---

### 22.3 M.2 — 프론트 동심원 시각 (예상 ~1.5h)

#### M.2.1 — 타입 추가: `frontend/src/types/clueTree.ts`

```ts
export interface AttackChainStep {
  hypothesis: IncidentType;
  probability: number;
  kill_chain_phase: number;
}

export interface ClueTreeResponse {
  // ... (기존 필드)
  // Phase M 신규
  zone: 1 | 2;
  attack_chain: AttackChainStep[];
  core_clue_likelihood: number;
  regress_suggested: boolean;
}
```

#### M.2.2 — 수정 파일: `frontend/src/components/IncidentTypeCompass.tsx`

추가 사항:
1. SVG 에 내부 원 (R · 0.5) `<circle r={R*0.5} stroke-dasharray="4 4" />` 그리기
2. 외부 원 (R · 1.0) 강조 — Zone 2 진입 시 색 변화
3. 점 위치 계산 — `zone === 2` 이면 외부 원 부근, 아니면 기존 로직
4. 헤더 라벨 — Zone 1 = "광범위 탐색", Zone 2 = "사고유형 chain 구체화"
5. 전환 애니메이션 — Zone 트랜지션 시 점 부드럽게 이동 (CSS transition)

```tsx
// 컴퍼스 SVG 안에 추가
<circle
  cx={center} cy={center} r={R * 0.5}
  stroke="rgba(255, 149, 0, 0.4)" strokeDasharray="4 4"
  fill="none"
/>
{response.zone === 1 && (
  <text x={center} y={center - R * 0.5 - 8} textAnchor="middle"
    className="text-[9px] fill-amber-400/60">
    Zone 1 · 광범위 탐색
  </text>
)}
{response.zone === 2 && (
  <text x={center} y={center - R - 8} textAnchor="middle"
    className="text-[10px] fill-brand-teal font-bold">
    🗺 Zone 2 · 사고유형 chain 구체화
  </text>
)}
```

#### M.2.3 — 전환 알림 카드 (선택)

Zone 1 → Zone 2 처음 진입 시 토스트 또는 inline 카드:

```
🗺 맵 열림 — 코어 단서 발견!
RANSOMWARE 가설 강 (P=0.47).
Top 3 가설 chain 구체화 단계로 진입.
```

#### M.2.4 — 합격 기준

- tsc --noEmit 0 errors
- vite build 성공
- 브라우저 시연:
  1. 단서 1-2개 입력 → 점이 내부 원 안 (Zone 1)
  2. 단서 3개 + 강한 likelihood 단서 → "Zone 2 열림" 알림 + 점 외부 이동
  3. Zone 2 진입 후 약한 단서 추가 → entropy 상승 → "회귀 권고" 표시

---

### 22.4 M.3 — Zone 2 chain UI (예상 ~1.5h)

#### M.3.1 — 신규 컴포넌트: `frontend/src/components/AttackChainCard.tsx`

ATT&CK Kill Chain Top 3 가설을 시간순 시각화:

```tsx
interface AttackChainCardProps {
  chain: AttackChainStep[];
  onSelectHypothesis: (h: IncidentType) => void;
  selectedHypothesis?: IncidentType | null;
}

// 시각:
//   [PHISH 5%] → [CRED 20%] → [RANSOM 70%]   ← 좌→우 화살표 (Kill Chain 순)
//   각 카드 클릭 → 해당 가설별 단서 추천 (NextCluePanel)
```

#### M.3.2 — 수정: `frontend/src/components/NextCluePanel.tsx`

`mode='chain'` props 추가:

```tsx
interface NextCluePanelProps {
  // ... (기존)
  mode?: 'standard' | 'chain';
  chainFilterHypothesis?: IncidentType | null;
}

// chain mode 일 때:
//   - chainFilterHypothesis 선택된 가설 변별 단서만 노출
//   - 미선택이면 통합 (Zone 1 동작)
//   - "→ AttackChainCard 의 가설 클릭" 안내
```

#### M.3.3 — 수정: `Step3_EvidenceTreeDiscovery.tsx`

`treeState.zone === 2` 일 때:
1. 우측 상단에 `<AttackChainCard>` 노출
2. 사용자가 가설 클릭하면 `chainFilterHypothesis` state 갱신
3. `<NextCluePanel mode="chain" chainFilterHypothesis={...} />` 로 전환
4. `regress_suggested` 시 토스트 + Zone 1 회귀 버튼

#### M.3.4 — 합격 기준

- Zone 2 진입 후 우측에 AttackChainCard 등장 — Kill Chain 시간순 (PHISH→CRED→RANSOM)
- 각 가설 카드 클릭 → 단서 후보 변경 (해당 가설 변별)
- "회귀 권고" 시 사용자에게 명확 알림 + [⤺ 광범위 탐색으로 회귀] 버튼

---

### 22.5 M.4 — 검증 + commit·푸시 (~30분)

```bash
# 백엔드
cd backend
.venv/Scripts/python.exe -m pytest tests/test_zone_logic.py tests/test_clue_tree.py tests/test_clue_tree_service.py -q
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/e2e_tree_e4_test.py | grep -E "결과:|lane 별:"
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/e2e_evidence_tree_test.py | grep -E "결과:|lane 별:"

# 프론트
cd frontend
npx tsc --noEmit
npx vite build

# paradigm doc §21.10 체크리스트 갱신
# 최종 commit + push origin byungwoo
```

#### 합격 기준 (전체 Phase M)

| 항목 | 합격선 |
|---|---|
| pytest 전체 | 220+ passed · 회귀 0 |
| additive e2e | 47/47 PASS |
| evidence_tree e2e | 47/47 PASS |
| tsc --noEmit | 0 errors |
| vite build | success |
| 브라우저 시연 | Zone 1 → 2 전환·chain 표시·회귀 모두 동작 |

---

### 22.6 작업 분배 제안 (선착순)

| 단계 | 작업 유형 | 추천 담당 | 예상 시간 |
|---|---|---|---|
| M.1 | 백엔드 알고리즘 + 테스트 | Python 강한 팀원 | ~1h |
| M.2 | 프론트 SVG·애니메이션 | React·시각화 익숙한 팀원 | ~1.5h |
| M.3 | 프론트 컴포넌트 + UX | React 강한 팀원 | ~1.5h |
| M.4 | 통합 검증 + commit | 누구나 | ~30분 |

각 단계 commit 시 본 doc 의 §21.10 체크리스트 + 담당자명 갱신.

### 22.7 문의

- 설계 의문: byungwoo (paradigm doc §21 작성자)
- 코드 컨벤션: `cloud/CLAUDE.md`
- 기존 자산 참조: §22.1 부팅 시퀀스 + 본 doc §9 (기존 자산 재활용 매트릭스)

