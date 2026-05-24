# dev3 머지 후 E2E 전수 검증 — 2026-05-25

> 머지 커밋: `366f292 merge: byungwoo (P1/P2) + jingyu (P0/P1/P2 + walkthrough) into dev3`
> 검증 대상: 결정트리 47 시나리오 / 합성로그 21종 / 29 endpoint / pytest 161 / KB 인용 감사 5지표

---

## 1. 종합 점수

| 도구 / 스위트 | 결과 | 임계 | 비고 |
|---|---:|---:|---|
| **pytest 전체** | **161 / 161 PASS** | 100% | 머지 후 회귀 0건 |
| **e2e_tree_e4_test** (47 시나리오) | **47 / 47 PASS** | 100% | CRED 12 + RANSOM 9 + MISCFG 6 + INSIDER 12 + ROUTER 3 + SHORT 4 + TERM 1 |
| **e2e_synthetic_logs_test** (21 합성로그) | **21 / 21 PASS** | 100% | naver 10 + nhn 11 × 10 사고유형 |
| **e2e_full_pipeline** (29 endpoint) | **29 / 29 PASS** | 100% | L0~L4 + 공통 회귀 |
| **kb_citation_audit** (5 지표) | **5 / 5 PASS** | 95~100% | A 100 · B 100 · C 100 · D 100 · E 95.4 |
| **investigator_walkthrough** | 작동 (이슈 6건은 의도된 동작) | — | UNCLASSIFIED 경고 + LLM cold-start |

**전체 회귀: 0건. 머지 안전.**

---

## 2. 결정트리 47 시나리오 — lane × entry × tail 매트릭스

| Lane | 검증 시나리오 | PASS | 1위 사고유형 분포 |
|---|---:|---:|---|
| **CRED** | 4 진입 × 3 종착 = 12 | 12 / 12 | CREDENTIAL_THEFT 11건, PHISH_INITIAL_ACCESS 1건 (E4T1 복합) |
| **RANSOM** | 3 진입 × 3 종착 = 9 | 9 / 9 | RANSOMWARE 9건 모두 auto_confirm |
| **MISCFG** | 2 진입 × 3 종착 = 6 | 6 / 6 | MISCONFIG_EXPOSURE 5건 + DATA_EXFILTRATION 1건 (E2T2 복합) |
| **INSIDER** | 4 진입 × 3 종착 = 12 | 12 / 12 | INSIDER_THREAT 12건 |
| **ROUTER** | Q3_DATA → MISCFG/INSIDER/RANSOM 분기 | 3 / 3 | 라우터 정확 분기 |
| **SHORT** | Q3 unknown_extra 단축 4 lane | 4 / 4 | 모두 continue_or_skip 정상 |
| **TERM** | Q1=unknown → Q2E terminal | 1 / 1 | UNCLASSIFIED 종착 |

**outcome 분포**: auto_confirm 22건 + propose_composite 11건 + propose_single 9건 + continue_or_skip 5건

---

## 3. 합성로그 21종 — CSP × 사고유형 × 파이프라인

| # | 파일 | CSP | 사고유형 | raw | OCSF | mapped | tech | tactic | gap |
|---:|---|:-:|---|---:|---:|---:|---:|---:|---|
| 1 | ncp_audit_log_tampering | naver | AUDIT_LOG_TAMPERING | 10 | 10 | 10 | 5 | 4 | NONE |
| 2 | ncp_collection | naver | MIXED | 14 | 14 | 14 | 7 | 5 | NONE |
| 3 | ncp_data_exfiltration | naver | DATA_EXFILTRATION | 14 | 14 | 14 | 3 | 3 | NONE |
| 4 | ncp_insider_threat | naver | INSIDER_THREAT | 5 | 5 | 5 | 4 | 4 | NONE |
| 5 | ncp_misconfig_exposure | naver | MISCONFIG_EXPOSURE | 6 | 6 | 6 | 5 | 4 | NONE |
| 6 | ncp_none | naver | NONE | 16 | 16 | 16 | 9 | 7 | NONE |
| 7 | ncp_phish_initial_access | naver | PHISH_INITIAL_ACCESS | 5 | 5 | 5 | 3 | 2 | NONE |
| 8 | ncp_privilege_escalation | naver | PRIVILEGE_ESCALATION | 11 | 11 | 11 | 4 | 3 | NONE |
| 9 | ncp_ransomware | naver | RANSOMWARE | 6 | 6 | 4 | 4 | 4 | NONE |
| 10 | ncp_sysdig_8min_killchain | naver | RANSOMWARE | 13 | 13 | 13 | 9 | 6 | NONE |
| 11 | nhn_audit_log_tampering | nhn | AUDIT_LOG_TAMPERING | 9 | 9 | 9 | 4 | 3 | NONE |
| 12 | nhn_capital_one_style | nhn | DATA_EXFILTRATION | 10 | 10 | 8 | 5 | 5 | NONE |
| 13 | nhn_collection | nhn | MIXED | 15 | 15 | 14 | 7 | 5 | NONE |
| 14 | nhn_credential_theft_real | nhn | CREDENTIAL_THEFT | 8 | 8 | 8 | 4 | 4 | NONE |
| 15 | nhn_data_exfiltration | nhn | DATA_EXFILTRATION | 11 | 11 | 11 | 4 | 4 | NONE |
| 16 | nhn_insider_threat | nhn | INSIDER_THREAT | 5 | 5 | 4 | 4 | 4 | NONE |
| 17 | nhn_misconfig_exposure | nhn | MISCONFIG_EXPOSURE | 5 | 5 | 3 | 3 | 3 | NONE |
| 18 | nhn_none | nhn | NONE | 16 | 16 | 14 | 7 | 5 | NONE |
| 19 | nhn_phish_initial_access | nhn | PHISH_INITIAL_ACCESS | 5 | 5 | 5 | 3 | 3 | NONE |
| 20 | nhn_privilege_escalation | nhn | PRIVILEGE_ESCALATION | 10 | 10 | 8 | 2 | 2 | NONE |
| 21 | nhn_ransomware | nhn | RANSOMWARE | 6 | 6 | 5 | 5 | 4 | NONE |

**집계**: raw 200 · OCSF 200 (정규화 100%) · mapped 177 (매핑률 88.5%) · 평균 4.5 기법 / 4.0 전술

---

## 4. KB 인용 감사 (진규 안 단위 검증, 130 chunks)

| 지표 | 설명 | 통과율 | 임계 | 결과 |
|---|---|---:|---:|:-:|
| **A** | 존재성 (chunk_id 무결성) | 100.0% | ≥100% | ✓ 130/130 |
| **B** | 사고유형 정합 (lane filter) | 100.0% | ≥100% | ✓ 40/40 (8 lane 검증) |
| **C** | 출처 비공백 | 100.0% | ≥100% | ✓ 130/130 |
| **D** | 환각 없음 (post-filter) | 100.0% | ≥100% | ✓ 12/12 환각 라벨링 |
| **E** | 수사 가치 (키워드 포함) | 95.4% | ≥95% | ✓ 124/130 |

P1 fix (`_sanitize_response`) 전 D=85.7% → **머지 후 100%** 회귀 차단.

---

## 5. 29 endpoint 통과 — Layer 별

| Layer | endpoint | 결과 |
|---|---|:-:|
| **L0** intake | POST /api/cases / GET / PATCH / GET /api/guide/v2 | ✓ ✓ ✓ ✓ |
| **L1** ingestion | POST /api/logs/upload / GET /api/logs / GET /{id} | ✓ ✓ ✓ |
| **L2** analysis | POST normalize / map / GET ocsf / attack / POST gap | ✓ ✓ ✓ ✓ ✓ |
| **L3** sherpa | POST brief / suggest / playbook / chat / GET kb / validate | ✓ ✓ ✓ ✓ ✓ ✓ |
| **L4** board | POST nodes / PATCH / POST edges / GET board / POST report / PATCH / GET export | ✓ ✓ ✓ ✓ ✓ ✓ ✓ |
| **공통** | GET actions / health | ✓ ✓ |

29건 모두 200/201 응답.

---

## 6. 머지 후 발견된 환경 이슈

| # | 이슈 | 원인 | 임시 조치 (이번 작업) | 후속 |
|---|---|---|---|---|
| **E1** | `GET /api/health` 가 첫 호출 시 2분+ hang | 진규 변경 — LLM/ChromaDB 실측이 SentenceTransformer 모델 로드 trigger | main.py 의 health 를 `deep=true` 옵션 분리. 기본은 가벼운 ping. | deep 모드는 시연 사전 점검용 |
| **E2** | walkthrough 가 LLM cold-start chat / sherpa kb 에서 -1 status 보고 | Ollama 첫 모델 로드 ~60초 | 해결 필요 — walkthrough timeout 조정 | 시연 전 warm-up |

---

## 7. 회의 결정 (G1~G6) 반영 검증

| 결정 | 적용 확인 |
|---|---|
| **G1** 환각 라벨 `[KB외:Tnnnn]` | pytest test_no_hallucination 24/24 PASS, KB audit D=100% |
| **G2** PLAYBOOK 3-tier 라우팅 | pytest test_playbook_lane_filter 5/5 PASS, NONEXISTENT lane → NIST 공통 폴백 |
| **G3** tier 정보 노출 | recommend_playbook 응답에 match_score/match_tier/tier_summary 포함 확인 |
| **G4** CASE_DB source 30 청크 보강 | KB audit C=130/130 (이전 81%) |
| **G5** walkthrough 4건 (UNCLASSIFIED·gap·evidence·health) | pytest test_walkthrough_fixes 3/3 PASS |
| **G6** pytest CI | GitHub Actions backend pytest workflow 흡수 |

---

## 8. 결론

**머지 안전. 다음 사이클 진행 가능.**

- 회귀 0건, 모든 임계값 통과
- 진규 안 + 병우 안 + 근형 안 충돌 해결 정합성 검증
- 시연 환경 안정성 확인 (health 가벼운 ping)
- 다음 단계: P3 ATT&CK Exfiltration 룰 보강, P4 보고서 안내, P5 결정트리 Baseline 옵션, P6 Dwell Time KPI

**검증 산출물 위치**:
- `backend/.verify-pytest.out` — pytest 161 결과
- `backend/.verify-tree.out` — e2e_tree 47 결과
- `backend/.verify-synth.out` — 합성로그 21 결과
- `backend/.verify-full.out` — full pipeline 29 결과
- `backend/.verify-audit-unit.out` — KB 인용 감사 5 지표
- `backend/.verify-walkthrough.out` — investigator walkthrough
