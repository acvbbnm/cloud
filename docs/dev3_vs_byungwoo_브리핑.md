# dev3 → byungwoo 브리핑 — Evidence Tree 패러다임 전환

> 작성: 2026-05-26, byungwoo
> 대상: 로그아웃팀 (jingyu, geunhyung, jinkyu)
> 범위: `dev3` 머지 직후 시점 → 현 `byungwoo` 브랜치 39 commits
> 변경량: **56 파일, +15,396 / −135**

---

## 0. 한 줄 요약

> *dev3 의 정적 결정 트리 + 누적 합산 점수* 를 → *동적 단서 트리 + Bayesian Network (Noisy-OR) 인과 추론* 으로 전환.
> **사용자 비전 "어두운 맵을 단서로 밝혀가는 수사" 정합** + **PDF 청사진 (BAN paper IEEE 2023) 의 폐쇄망·캡스톤 제약 하 학술 정합 구현**.

---

## 1. 출발 의도 — 왜 바꿨나

### 1.1 dev3 결정 트리의 본질적 한계

```
dev3 흐름:
  Q1 "어떻게 알게 됐나?" → "CSP 알람" → Q2A → Q3_CRED → Q4_CRED → ... → CRED lane 만
                                              ↓
                                  다른 사고유형 변별 기회 차단
```

3가지 문제:
1. **한 답변 = 한 lane 라우팅** → 트리 진행 중 다른 사고유형은 비활성
2. **베이즈 모델 부정합** — 확률 모델은 모든 가설을 동시에 추적해야 하는데 트리가 차단
3. **수사 직관 불일치** — 형사는 단서를 모아 가능성을 좁히지, 미리 한 사고유형 선언하지 않음

### 1.2 사용자 비전

> *"게임 속 어두운 맵을 단서로 밝혀가는 과정. 사고유형이 정해져 있으면 전체 맵의 크기는 정해져 있고 (8 사고유형 = boundary), 단서를 찾을수록 그쪽 방향의 길이 열린다."*

→ Bottom-up Abductive (귀납적 가설 좁히기) 패러다임.

### 1.3 PDF 청사진 정합 (외부 학술 근거)

`사고 조사 트리 구조화 연구.pdf` (11 페이지) 의 단서-맵 트리 아키텍처:
1. ATT&CK 매핑 (TRAM NLP) → 우리는 폐쇄망·AI 비판단 원칙상 NLP X, 정적 룰 유지
2. **Bayesian Network DAG + CPT** → 본 작업의 핵심 채택
3. Neo4j Graph DB → 우리는 networkx 인메모리 (Phase J)
4. SOAR 자동 대응 → 우리는 V-7 수사보드 [확정] 클릭 (수사관 결정)

---

## 2. 핵심 알고리즘 변경 4종

### 2.1 사전확률 (Prior)

| | dev3 | byungwoo |
|---|---|---|
| 분포 | Verizon DBIR 2024 통계 (RANSOM 27% 등) | **Uniform 1/8 (Jaynes 1968 Max Entropy)** |
| 근거 | 임의 분배 — 한국 NCP/NHN 도메인과 무관 | 사전 정보 없음 가정. 첫 단서가 횃불 |

**근거**: 사용자 피드백 *"왜 랜섬웨어가 처음에 27프로니"* + Jaynes (1968) Maximum Entropy Principle.

### 2.2 점수 누적 → 베이즈 갱신

| | dev3 (additive) | byungwoo (bayes_net) |
|---|---|---|
| 수식 | `score[h] += weight[h]` | `posterior[h] ∝ posterior[h] × P(c\|h)` |
| 범위 | 0 ~ 180 (절대 점수) | 0 ~ 1 (확률) |
| 임계값 | high_conf=90, auto_skip=130 | 0.65 + gap 0.20 (depth 5+) |
| smoothing | 없음 | **Laplace add-k=5** (0 곱하기 차단) |
| Marginalization | X | **있음** (Pearl 1988) — 미관찰 단서 처리 |

### 2.3 다음 단서 추천

| | dev3 | byungwoo |
|---|---|---|
| 메커니즘 | 결정 트리의 다음 노드 옵션 (정적) | **Information Gain (Shannon 1948 KL divergence)** 동적 정렬 |
| 후보 풀 | 현재 Q-노드의 5개 옵션 | **143 단서 카탈로그** 전체 (decision_tree 99 + clue_types 24 + ATT&CK 27) |
| 후보 개수 | 5 (고정) | **5/3/2 (entropy 기반 동적)** — 모호할수록 많이, 수렴할수록 적게 |
| 인과 추론 | 없음 | **Noisy-OR Bayesian Network** — Atomic Red Team + ATT&CK Flow 학습 |

### 2.4 confidence 도달 정책 (사용자 피드백 반영)

| | dev3 | byungwoo |
|---|---|---|
| 도달 시 | 자동 종료 → V-2 진행 | **알림만, 사용자 [확정] 클릭** (자동 종료 X) |
| 임계값 | 단일 (90/130) | **depth 별 차등** — 최소 단서 3개 채택 후 허용 |
| depth 1-2 | (해당 없음) | **절대 차단** (auto_confirm=1.01) ← 사용자 피드백 |
| depth 3+ | (해당 없음) | 0.80 → 0.75 → 0.65 점진 완화 |

---

## 3. 새 자료구조 + API

### 3.1 자료구조

**ClueTreeNode + ClueTree** (`core/intake/clue_tree.py` 384 줄)
- `parent_id`, `depth`, `clue_key`, `score_delta`, `posterior_after`
- `children_candidates: list[ClueCandidate]` — 각 노드가 결정 시점의 후보 보존
- DB 영속화 — `incident_cases.triage_state["evidence_tree"]` JSON

### 3.2 REST API 신규 5종

| 메서드 | 경로 | 역할 |
|---|---|---|
| POST | `/api/clue-tree/start` | 빈 트리 시작 (cold-start, 후보 0개) |
| POST | `/api/clue-tree/expand` | 단서 채택 → 베이즈 갱신 + 다음 후보 |
| POST | `/api/clue-tree/suggest` | 현 leaf 후보 재계산 |
| GET | `/api/clue-tree?caseId=` | 트리 상태 조회 |
| POST | `/api/clue-tree/reset` | cold-start 재시작 |
| GET | **`/api/guide/preview?caseId=&incidentType=`** | **가설별 가이드 미리보기 (Phase K)** |
| GET | `/api/clue-tree/explain/{clue_key}` | 후보 추천 근거 상세 |

### 3.3 환경변수

```bash
TRIAGE_MODE=additive        # dev3 호환 (기본)
TRIAGE_MODE=bayesian        # 베이즈 갱신만 (Phase 3)
TRIAGE_MODE=bayes_net       # BN + Noisy-OR (현재 권장, Phase H.4)
TRIAGE_MODE=evidence_tree   # 단서 트리 + V-1 Step3 새 UI (Phase E)
```

---

## 4. PDF 청사진 정합 — Phase H 학술 구현

### 4.1 합성 데이터 (PDF §2 보강안)

기업 기밀 침해 데이터 대신 MITRE 공개 자원 3종 학습:
- **Atomic Red Team** — 334 atomic YAML (prerequisite 64%) → technique 간 인과 edge
- **ATT&CK Flow** — 40 실제 사고 시퀀스 (Black Basta·Conti·Equifax·FIN13 등)
- **ATT&CK STIX** — 25,843 objects (189 APT × 18,220 group→technique uses)

**총 ~수만 transition signal** = PDF 의 "수만 침해사고 데이터" 와 학술적 등가.

### 4.2 Noisy-OR Bayesian Network (PDF §3 정합)

**왜 Noisy-OR 인가**:
- 풀 CPT: 143 단서 × 2^143 조합 = 계산 불가능
- Noisy-OR (Pearl 1988): 부모 노드 독립 가정 → 파라미터 **지수 → 선형** 축소
- pgmpy `NoisyOrCPD` 클래스 — Python 폐쇄망 친화 (5MB)

**파라미터** (`data/triage/clue_cpt_noisyor.json`):
- 단서별 leak probability (자발 발생)
- edge별 inhibitor probability (부모 → 자식 활성화 차단 확률)

### 4.3 학술 변호 (논문·발표)

> *"BAN paper (IEEE 2023) 의 Bayesian Network 패러다임을 따르되, 폐쇄망·캡스톤 제약 하에서:*
> *(1) 합성 데이터 — Atomic Red Team + ATT&CK Flow + Groups 공개 자원*
> *(2) Noisy-OR (Pearl 1988) — CPT 파라미터 지수 → 선형 축소*
> *(3) pgmpy — 학술 표준 확률 그래픽 모델 라이브러리, 결정성 100%*
> *(4) 폐쇄망 운영 — 학습 1회 (외부 PC), 운영은 정적 JSON 만 사용"*

---

## 5. 검증 결과

### 5.1 e2e 회귀 (3 모드 비교)

| 모드 | 결과 | 비고 |
|---|---|---|
| **additive** (dev3 호환) | **47/47** | 회귀 0 — dev3 머지 안전 |
| **bayesian** | 47/47 | INSIDER T3 4건 composite 가설 허용 정책 정합 |
| **evidence_tree** | 47/47 | 47 시나리오 단서 시퀀스 학술 정합 입증 |

`scripts/e2e_tree_e4_test.py` + `scripts/e2e_evidence_tree_test.py` 두 스위트 통과.

### 5.2 pytest

- `test_clue_tree`: 21 PASS
- `test_clue_tree_service`: 14 PASS (DB 영속화 + cold-start + depth throttle)
- `test_info_gain`: 16 PASS (KL divergence + Marginalization on/off)
- `test_bayes_net`: pgmpy NoisyOrCPD 추론 검증
- `test_collection_guide_v2`: 65 PASS (preview 회귀 0)
- `test_clue_to_attack`: 단서 → ATT&CK 매핑 무결성

**합계 신규 pytest: 137건** (기존 fail 7건도 동시 해결, `aef5cd9`)

### 5.3 새 e2e 검증

| 시연 | 결과 |
|---|---|
| **Cold-start** — 빈 트리 + 횃불 안내 → 첫 단서 후 후보 등장 | ✓ |
| **fan-out 트리** — 각 depth 마다 후보 수평 펼침, 선택된 후보 = 다음 anchor | ✓ |
| **depth throttle** — 단서 1-2개에서 reached=False, 3개부터 알림 | ✓ |
| **가이드 preview** — 상위 가설 클릭 → inline expand + 풀 가이드 모달 | ✓ |

---

## 6. UI 변경 (V-1 Step 3 새 화면)

```
┌────────────────────────────────────────────────────┬──────────────────────────┐
│ [메인 col-span-8]                                   │ [우 sticky col-span-4]    │
│                                                     │                          │
│  Card: Evidence Tree (또는 Compass 360° 탭 토글)    │  ConfidenceGauge          │
│    ◆ 수사 시작 (Uniform 1/8)                        │   (entropy 게이지)         │
│      ↓                                               │                          │
│    [채택 단서 N] ━━ fan-out 후보들                  │  HypothesisScoreBar       │
│      ↓                  (점선, IG 게이지)           │   ▼ 클릭 → inline 가이드  │
│    [채택 단서 N+1]  ✏ 직접 입력 슬롯               │     max-h-80 + 스크롤      │
│                                                     │     [전체 가이드 보기 →]   │
│  Card: 단서 직접 입력 / 부분 로그 분석              │     [+ 가이드 추천 단서]   │
│                                                     │                          │
│                                                     │  NextCluePanel IG         │
│  ✛ LogAnalysisFab (플로팅 실시간 로그 분석)         │   ↻ 재계산 + ATT&CK badge │
│                                                     │                          │
│                                                     │  [확정 가능 알림]         │
│                                                     │   (depth ≥ 3 + 임계)      │
└────────────────────────────────────────────────────┴──────────────────────────┘
```

### 신규 컴포넌트

| 파일 | 줄수 | 역할 |
|---|---|---|
| `ClueTreeView.tsx` | 481 | react-flow 단서 트리 (TriageTreeMinimap drift anchor 패턴) |
| `IncidentTypeCompass.tsx` | 501 | Phase I 360° 컴퍼스 시각화 (탭 토글) |
| `LogAnalysisFab.tsx` | 408 | 플로팅 실시간 로그 분석 패널 |
| `NextCluePanel.tsx` | +381 | IG 모드 + outcome_flags badge + 추천 이유 expand |
| `GuidePreviewModal.tsx` | 276 | Phase K 풀 가이드 팝업 |
| `HypothesisScoreBar.tsx` | +363 | inline 가이드 미리보기 + 단서 추가 |
| `DiscoveryIntroModal.tsx` | +185 | "어두운 맵 밝히기" 안내 (mode 분기) |
| `guideToClueMatcher.ts` | 133 | 가이드 → 단서 휴리스틱 매핑 (14 룰) |

---

## 7. Phase 진행 보드

| Phase | 내용 | 상태 | 핵심 commit |
|---|---|---|---|
| 5.0 | Prior Uniform 전환 | ✓ | `d9d8f8e` |
| A | ClueTreeNode + 143 단서 카탈로그 | ✓ | `176ad5f` |
| B | API 4종 + Information Gain | ✓ | `e95ad08` |
| C | 프론트 트리 UI | ✓ | `706858c` |
| D | NextCluePanel IG + outcome_flags | ✓ | `6bd29b1` |
| E | V-1 Step3 evidence_tree 모드 배선 | ✓ | `666d0e5` |
| F | 47 시나리오 e2e 회귀 (43/47) | ✓ | `604506e` |
| G | DiscoveryIntroModal + reset 엔드포인트 | ✓ | `fe21776` |
| **H** | **BN + Noisy-OR + pgmpy (PDF 정합 핵심)** | ✓ | `17589eb` |
| I | 사고유형 360° 컴퍼스 시각화 | ✓ | `941cfca` |
| J | networkx GDS (PageRank·Label Propagation) | ✓ | `9b7cd17` |
| **K** | **사고유형 가이드 통합 (preview + 모달)** | ✓ | `1b5afe4` |
| K-fix | depth 차등 임계값 (사용자 피드백) | ✓ | `adda0ac` |

---

## 8. 학술 인용 (논문·발표용)

### 8.1 기본 패러다임
- **Pearl 1988** — Probabilistic Reasoning in Intelligent Systems (Bayesian Belief Propagation + Noisy-OR §3.2.2)
- **Peirce 1903** — Abductive Reasoning (Hypothesis Selection)
- **Shannon 1948** — A Mathematical Theory of Communication (Information Gain)
- **Jaynes 1968** — Prior Probabilities (Maximum Entropy)

### 8.2 도메인 표준
- **MITRE ATT&CK Cloud Matrix v14** — 단서 → 사고유형 매핑 표준
- **MITRE Atomic Red Team** (Red Canary) — TTP YAML 정의, 합성 데이터 표준
- **MITRE ATT&CK Flow** (Center for Threat-Informed Defense) — 실제 사고 시퀀스
- **Verizon DBIR 2024** — 침해사고 통계

### 8.3 외부 청사진
- **BAN — Predicting APT Attack Based on Bayesian Network With MITRE ATT&CK** (IEEE Xplore 2023)
- **Microsoft Security Blog — Automating threat actor tracking** (2021)
- **Google Chronicle — Rule-to-Outcome Workflow** — Outcome Contract 패턴
- **Palo Alto — Cloud Token Theft Response Playbook** — Verdict Decision Tree

### 8.4 라이브러리
- **pgmpy** (Ankan & Panda 2015) — Python Library for Probabilistic Graphical Models (UC Berkeley·CMU 표준)
- **networkx** — Phase J GDS (PageRank·Label Propagation)

---

## 9. 팀원 합의 필요 사항

1. **dev3 → byungwoo 머지**: 56 파일 변경 — additive 호환 보장 (TRIAGE_MODE 기본값) 확인 필요
2. **의존성 추가**: `pgmpy>=0.1.25` + `pyyaml>=6.0` + `networkx>=3.0` — `requirements.txt` 반영
3. **외부 데이터**: `backend/data/triage/external_sources/` (250 MB) — zip 별도 전달 (gitignore)
4. **DB 스키마 무변경**: `incident_cases.triage_state` JSON 컬럼 sub-key 만 추가 — 마이그레이션 불필요

---

## 10. 다음 단계 후보 (사용자 확정 대기)

- **L. Negative evidence UI** — Marginalization 의 음성 단서 명시 입력
- **M. CPT 학습 데이터 보강** — Atomic 외 KISA 사례·DBIR 통계 통합
- **N. V-7 수사보드 연동** — Evidence Tree → ChainNode 자동 시드

---

## 11. 핵심 참고 문서

- `docs/evidence_tree_paradigm.md` — 패러다임 전환 설계서 §1~§19 (818줄)
- `docs/bayesian_phase3_4_guide.md` — 베이지안 모드 전환 가이드
- `사고 조사 트리 구조화 연구.pdf` — 외부 청사진 (PDF, 사용자 검토 자료)

---

**문의**: byungwoo (팀장).
**다음 회의**: dev3 머지 합의 시 + 다음 단계 L/M/N 선택.
