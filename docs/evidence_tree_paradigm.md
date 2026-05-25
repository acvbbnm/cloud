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
- [ ] **Phase J** (이전 Phase I, 보류) — V-7 보드 networkx GDS (PageRank·Label Propagation) — Evidence Tree 완성 후 별도

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

### 17.E 거부 — Neo4j 그래프 DB 도입

PDF p7-8 — Neo4j + Cypher + GraphQL 풀스택.

**거부 사유**: 폐쇄망 단일 데스크톱 + SQLite 9 테이블 설계서 확정 (DB 담당자 합의 사항).

**대체**: networkx (Python 라이브러리, in-memory) 로 GDS 알고리즘만 차용 (§17.C).

---
