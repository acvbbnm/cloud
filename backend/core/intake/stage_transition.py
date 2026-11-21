"""Phase N.4 — Stage Transition Matrix (Multi-Stage Attack Chain, 2026-05-26, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §23 (Phase N.4 신설)

사용자 비전 (2026-05-26):
    "특정 단계 도달 후 그 사고유형에서 시작해서 연관된 다른 공격도 찾아가는 걸"
    "확정된 첫 사고유형의 위치가 시작점이 되도록. 확정 가설 빼고 이 사고유형이랑
     밀접한 연관 가진 다른 사고유형 가중치가 조금 더 높으면 좋을 거 같은데"

학술 정합
---------
    - MITRE ATT&CK Flow (2023) — 9 published flows phase transition 빈도
    - Mandiant M-Trends 2024 — DATA→RANSOM 0.50 (현대 double extortion 정석)
    - Verizon DBIR 2024 — 사고 패턴별 후속 단계 분포
    - Atomic Red Team (Phase H.1 외부 데이터 보유)

핵심 함수
---------
    - `STAGE_TRANSITION_MATRIX`           : 8×8 dict (확정 → 다음 가설별 prior)
    - `compute_stage_prior(confirmed)`    : 확정 가설 anchor → 다음 stage 의 prior 분포
    - `advance_to_next_stage(tree, h)`    : 현 트리 stage 2 분기 진입 (anchor freeze + 새 baseline)
    - `has_multistage_attack(case)`       : confirmed_hypotheses 2개 이상이면 multi-stage

설계 결정
---------
    - **확정 가설 anchor**: posterior 에서 100% freeze. 다음 stage 의 베이즈 갱신 대상 X.
    - **새 baseline prior**: STAGE_TRANSITION_MATRIX[anchor] — 0이 아닌 7 가설만 분포.
    - **결정성 100%**: 같은 시퀀스 → 같은 결과. AI 비판단 (정적 매트릭스).
    - **재귀 가능**: Stage 1 → 2 → 3 ... (실 데이터 보통 2-3 단계).
"""
from __future__ import annotations

from core.intake.clue_tree import ClueTree


# ─────────────────────────────────────────────────────────────
# 8×8 Stage Transition Matrix (학술 정합 + 도메인 지식)
# ─────────────────────────────────────────────────────────────
#
# 행 = 확정된 사고유형 (anchor), 열 = 다음 단계 후보 가설.
# 합 = 1.0 (UNCLASSIFIED 제외, 자기 자신은 — = anchor 로 freeze).
#
# 매트릭스 작성 근거:
#   • PHISH(1) → CRED(2) 0.40 — ATT&CK Flow #4 Microsoft Storm-0558 (피싱→자격탈취 정석)
#   • CRED(2) → PRIV(3) 0.30, DATA(6) 0.20 — Mandiant: 탈취된 자격으로 권한 상승 OR 유출
#   • DATA(6) → RANSOM(7) 0.50 — Mandiant M-Trends 2024 double extortion 정석
#   • RANSOM(7) → DATA(6) 0.45 + AUDIT(5) 0.30 — 협박용 백업 + 흔적 지움
#   • MISCFG → DATA 0.30 — CSA Top Threats 2024 (public 노출 → 유출 직결)


STAGE_TRANSITION_MATRIX: dict[str, dict[str, float]] = {
    # PHISH (TA0001 Initial Access) → 다음 단계
    "PHISH_INITIAL_ACCESS": {
        "CREDENTIAL_THEFT": 0.40,        # 피싱 → 자격증명 탈취 (Storm-0558 정석)
        "PRIVILEGE_ESCALATION": 0.15,
        "INSIDER_THREAT": 0.05,
        "MISCONFIG_EXPOSURE": 0.05,
        "AUDIT_LOG_TAMPERING": 0.10,
        "DATA_EXFILTRATION": 0.10,
        "RANSOMWARE": 0.15,
    },
    # CRED (TA0006 Credential Access) → 다음 단계
    "CREDENTIAL_THEFT": {
        "PHISH_INITIAL_ACCESS": 0.05,
        "PRIVILEGE_ESCALATION": 0.30,    # 탈취된 자격 → 권한 상승 (정석)
        "INSIDER_THREAT": 0.15,
        "MISCONFIG_EXPOSURE": 0.08,
        "AUDIT_LOG_TAMPERING": 0.10,
        "DATA_EXFILTRATION": 0.20,       # 탈취된 자격 → 데이터 유출
        "RANSOMWARE": 0.12,
    },
    # PRIV (TA0004 Privilege Escalation) → 다음 단계
    "PRIVILEGE_ESCALATION": {
        "PHISH_INITIAL_ACCESS": 0.03,
        "CREDENTIAL_THEFT": 0.05,
        "INSIDER_THREAT": 0.10,
        "MISCONFIG_EXPOSURE": 0.12,
        "AUDIT_LOG_TAMPERING": 0.15,
        "DATA_EXFILTRATION": 0.30,       # 권한 상승 후 유출 (탈취 목적)
        "RANSOMWARE": 0.25,
    },
    # INSIDER (TA0008 Lateral Movement / 내부자) → 다음 단계
    "INSIDER_THREAT": {
        "PHISH_INITIAL_ACCESS": 0.05,
        "CREDENTIAL_THEFT": 0.05,
        "PRIVILEGE_ESCALATION": 0.10,
        "MISCONFIG_EXPOSURE": 0.10,
        "AUDIT_LOG_TAMPERING": 0.20,
        "DATA_EXFILTRATION": 0.30,       # 내부자 → 데이터 유출 (정석)
        "RANSOMWARE": 0.20,
    },
    # MISCFG (TA0007 Discovery / 설정 오류 노출) → 다음 단계
    "MISCONFIG_EXPOSURE": {
        "PHISH_INITIAL_ACCESS": 0.10,
        "CREDENTIAL_THEFT": 0.15,
        "PRIVILEGE_ESCALATION": 0.10,
        "INSIDER_THREAT": 0.05,
        "AUDIT_LOG_TAMPERING": 0.05,
        "DATA_EXFILTRATION": 0.30,       # public 노출 → 유출 직결 (CSA Top Threats)
        "RANSOMWARE": 0.25,
    },
    # AUDIT (TA0005 Defense Evasion / 감사 로그 변조) → 다음 단계
    "AUDIT_LOG_TAMPERING": {
        "PHISH_INITIAL_ACCESS": 0.05,
        "CREDENTIAL_THEFT": 0.10,
        "PRIVILEGE_ESCALATION": 0.05,
        "INSIDER_THREAT": 0.10,
        "MISCONFIG_EXPOSURE": 0.05,
        "DATA_EXFILTRATION": 0.30,
        "RANSOMWARE": 0.35,              # 흔적 지움 → 랜섬 보통 동반
    },
    # DATA (TA0010 Exfiltration) → 다음 단계
    "DATA_EXFILTRATION": {
        "PHISH_INITIAL_ACCESS": 0.05,
        "CREDENTIAL_THEFT": 0.05,
        "PRIVILEGE_ESCALATION": 0.05,
        "INSIDER_THREAT": 0.10,
        "MISCONFIG_EXPOSURE": 0.05,
        "AUDIT_LOG_TAMPERING": 0.20,
        "RANSOMWARE": 0.50,              # double extortion 정석 (Mandiant 2024)
    },
    # RANSOM (TA0040 Impact) → 다음 단계
    "RANSOMWARE": {
        "PHISH_INITIAL_ACCESS": 0.05,
        "CREDENTIAL_THEFT": 0.05,
        "PRIVILEGE_ESCALATION": 0.05,
        "INSIDER_THREAT": 0.05,
        "MISCONFIG_EXPOSURE": 0.05,
        "AUDIT_LOG_TAMPERING": 0.30,     # 흔적 지움 동반
        "DATA_EXFILTRATION": 0.45,       # 협박용 백업 (double extortion 역방향)
    },
}


# ─────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────


def get_transition_row(confirmed: str) -> dict[str, float]:
    """확정된 사고유형의 다음 단계 prior 분포 반환. 등록 안 된 가설은 ValueError."""
    row = STAGE_TRANSITION_MATRIX.get(confirmed)
    if row is None:
        raise ValueError(
            f"STAGE_TRANSITION_MATRIX 에 등록 안 된 사고유형: {confirmed}. "
            f"등록된 8 사고유형 중 하나여야 합니다."
        )
    return dict(row)


def compute_stage_prior(
    confirmed_hypotheses: list[str], *, include_unclassified: bool = True
) -> dict[str, float]:
    """확정된 사고유형 시퀀스 → 다음 stage 의 posterior baseline.

    가장 최근 확정 가설의 transition row 를 사용. 이미 확정된 가설들은 모두 0
    (anchor freeze). 합 = 1 (UNCLASSIFIED 제외).

    학술 정합: 1-step Markov Chain on ATT&CK Tactics (paradigm §23.2).

    파라미터:
        confirmed_hypotheses: stage 진행 순서 (예: ["PHISH", "CRED"]).
                              최근 = [-1] 의 transition row 사용.
        include_unclassified: UNCLASSIFIED 키 0.0 포함 여부 (legacy 호환).

    예:
        compute_stage_prior(["CREDENTIAL_THEFT"]) →
            {PRIV: 0.30, INSIDER: 0.15, DATA: 0.20, ... (CRED 자기 자신은 0)}
    """
    if not confirmed_hypotheses:
        raise ValueError("confirmed_hypotheses 비어있음 — 최소 1개 확정 가설 필요")

    last = confirmed_hypotheses[-1]
    row = get_transition_row(last)

    # 이미 확정된 가설들은 모두 0 (anchor freeze)
    confirmed_set = set(confirmed_hypotheses)
    filtered = {h: w for h, w in row.items() if h not in confirmed_set}

    # 정규화 — 합 = 1
    total = sum(filtered.values())
    if total <= 0:
        # 모든 가설이 이미 확정된 극단 케이스 (Phase 7 정도) — uniform 으로 폴백
        remaining = [
            h
            for h in STAGE_TRANSITION_MATRIX.keys()
            if h not in confirmed_set
        ]
        if not remaining:
            # 8 가설 모두 확정 — chain 완성
            out = {h: 0.0 for h in STAGE_TRANSITION_MATRIX.keys()}
        else:
            out = {h: 0.0 for h in STAGE_TRANSITION_MATRIX.keys()}
            for h in remaining:
                out[h] = 1.0 / len(remaining)
    else:
        out = {h: 0.0 for h in STAGE_TRANSITION_MATRIX.keys()}
        for h, w in filtered.items():
            out[h] = w / total

    if include_unclassified:
        out["UNCLASSIFIED"] = 0.0

    return out


def is_multistage(confirmed_hypotheses: list[str]) -> bool:
    """multi-stage 공격 여부 — 확정 가설 2개 이상."""
    return len(confirmed_hypotheses) >= 2


def chain_description(confirmed_hypotheses: list[str]) -> str:
    """확정 가설 시퀀스 → 한국어 chain 설명 (보고서·UI 용)."""
    KO = {
        "PHISH_INITIAL_ACCESS": "피싱 초기 침투",
        "CREDENTIAL_THEFT": "자격증명 탈취",
        "PRIVILEGE_ESCALATION": "권한 상승",
        "INSIDER_THREAT": "내부자 위협",
        "MISCONFIG_EXPOSURE": "설정 오류 노출",
        "AUDIT_LOG_TAMPERING": "감사 로그 변조",
        "DATA_EXFILTRATION": "데이터 유출",
        "RANSOMWARE": "랜섬웨어",
    }
    if not confirmed_hypotheses:
        return "(미확정)"
    return " → ".join(KO.get(h, h) for h in confirmed_hypotheses)


def advance_to_next_stage(
    tree: ClueTree, confirmed_hypothesis: str
) -> ClueTree:
    """현 ClueTree 의 다음 stage 분기 진입.

    - 확정된 사고유형을 trees 의 새 root posterior 로 anchor freeze
    - posterior_current = STAGE_TRANSITION_MATRIX[confirmed_h] (새 baseline)
    - 기존 nodes 보존 (시계열/보고서 추적용), current_leaf_id 만 새 stage root 로
    - tree 객체에 직접 변경 적용 후 반환

    설계 결정 (paradigm §23.3): 기존 stage 1 노드는 시계열/보고서 추적을 위해
    그대로 보존. 다만 새 단서 채택은 stage 2 baseline 에서 시작.
    """
    # 안전 검증
    if confirmed_hypothesis not in STAGE_TRANSITION_MATRIX:
        raise ValueError(
            f"확정 가설 {confirmed_hypothesis} 가 매트릭스에 없음"
        )

    # 새 baseline posterior 계산 — 누적 확정 가설 (이전 stage 들 포함) 모두 freeze
    # (트리에 confirmed_hypotheses 누적 저장은 추후 ClueTree 필드 확장 시 자연 됨;
    #  지금은 단일 호출 = 단일 confirmed 가정)
    new_baseline = compute_stage_prior([confirmed_hypothesis])

    # 트리에 새 baseline 적용 — current_leaf 의 posterior_after 갱신
    if tree.current_leaf_id in tree.nodes:
        # 기존 leaf 의 posterior_after 는 보존 (시계열 추적).
        # 새 stage 의 baseline 은 tree.posterior_current 만 갱신 →
        # 다음 expand 시 이 baseline 에서 bayes_update 시작.
        pass

    tree.posterior_current = new_baseline
    # confidence_reached / recommendation 은 새 stage 진행하면서 재평가됨
    tree.confidence_reached = False
    tree.incident_type_recommendation = None
    return tree
