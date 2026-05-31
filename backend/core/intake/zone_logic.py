"""Phase M.1 — 2-zone 컴퍼스 + ATT&CK Kill Chain 정합 추론 (2026-05-26, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §21·§22.2

사용자 비전 (paradigm doc §21.1)
--------------------------------
    "트리깊이 + 핵심단서? 코어단서? 같은 느낌이면 좋겠는데. 게임에서도 어느정도
     맵을 탐험해야 보스 나오잖아. 코어단서 — 보스, 트리깊이 — 맵탐색의 역할인거지."

→ Zone 전환 = 맵 탐색 (depth) + 보스 단서 (강한 likelihood) 모두 충족.

핵심 함수
---------
    - `is_zone2_unlocked(tree, posterior)`  : Zone 1 → 2 트리거 평가
    - `core_clue_likelihood(tree)`          : 채택 단서 중 가장 강한 P(c|h)
    - `should_regress(posterior)`            : Zone 2 → 1 자동 회귀 조건
    - `compute_attack_chain(posterior)`      : Top 3 가설을 ATT&CK Kill Chain 순으로

학술 정합
---------
    - MITRE ATT&CK Kill Chain (TA0001 Initial Access → TA0040 Impact)
    - Pearl 1988 Bayesian Belief Propagation (posterior entropy)
    - 단일 가설 확정 X — 복합 공격 chain 가정 (paradigm §21.1 비전 ②)

설계 결정 (paradigm doc §21.8)
------------------------------
    - 트리거 N=3, M=0.45 (시연 후 fit 예정)
    - Top 3 가설 chain (단일 우세도 chain 표시 — 이전 단계 추론 가능성 유지)
    - 회귀 허용 (Zone 2 → Zone 1, 사용자 명시 + 자동 entropy/gap 조건)
"""
from __future__ import annotations

from core.intake.bayesian import top_n
from core.intake.clue_tree import ClueTree, posterior_entropy
from core.intake.info_gain import load_catalog, weights_to_likelihood


# ─────────────────────────────────────────────────────────────
# 사고유형 → ATT&CK Kill Chain 단계 매핑 (paradigm §21.5)
# ─────────────────────────────────────────────────────────────


KILL_CHAIN_ORDER: dict[str, int] = {
    "PHISH_INITIAL_ACCESS": 1,     # TA0001 Initial Access
    "CREDENTIAL_THEFT": 2,         # TA0006 Credential Access
    "PRIVILEGE_ESCALATION": 3,     # TA0004 Privilege Escalation
    "INSIDER_THREAT": 4,           # TA0008 Lateral Movement
    "MISCONFIG_EXPOSURE": 4,       # TA0007 Discovery (Misconfig 사전 노출)
    "AUDIT_LOG_TAMPERING": 5,      # TA0005 Defense Evasion
    "DATA_EXFILTRATION": 6,        # TA0010 Exfiltration
    "RANSOMWARE": 7,               # TA0040 Impact
}


# ─────────────────────────────────────────────────────────────
# 트리거 임계값 (paradigm §21.8 #1 — 시연 후 fit)
# ─────────────────────────────────────────────────────────────


TRIGGER_MIN_DEPTH: int = 3
TRIGGER_MIN_LIKELIHOOD: float = 0.25
# V1.fix.12 (2026-05-31 byungwoo · 사용자: "Zone 2 도달 너무 느리다 — 4개면 도달") —
#   depth ≥ TRIGGER_RELAXED_DEPTH 만으로 Zone 2 진입 (likelihood 무관). 약한 단서
#   여러 개 누적도 "맵 충분히 탐색" 으로 인정. is_zone2_unlocked OR 분기.
TRIGGER_RELAXED_DEPTH: int = 4
#
# 변경 이력:
#   · P.10 (cap=20): TRIGGER 0.40→0.30
#   · P.13: 0.40→0.30 calibration
#   · P.26 (cap=15): 0.30→0.25 추가 calibration
#   · V1.fix.12: RELAXED_DEPTH=4 추가 (OR 조건)

# 회귀 임계값 (paradigm §21.8.1)
#
# V1.fix.9 (2026-05-31 byungwoo · 사용자 검증: "한 번 강등되면 다시 안 돌아간다") —
#   entropy 임계 2.0 → 2.7 보정. 8 가설 max entropy=3.0 에서 2.0 이하는 거의 단일
#   우세 (Top1 ≈ 0.55+) 필요 — 시연 시나리오에서 도달 어려움. 실측:
#     · 강한 CRED 단서 1개 후 H=2.64, gap=0.32 → 정상 Zone 2 인데 regress=True
#     · 반대방향 단서 추가 후 H=2.96, gap=0.099 → regress 마땅 (양쪽 모두 True)
#   2.7 로 올려 "거의 uniform (Top1·Top2 미세 차)" 상태만 회귀 권고. Zone 2 안정성 ↑.
#   paradigm doc §21.8 "트리거 임계값 — 시연 후 fit 예정" 정합.
REGRESS_ENTROPY_THRESHOLD: float = 2.7
REGRESS_GAP_THRESHOLD: float = 0.10

# Top 몇 개 chain (paradigm §21.8 #2)
ATTACK_CHAIN_TOP_N: int = 3


# ─────────────────────────────────────────────────────────────
# 핵심 단서 (보스 단서) — 가장 강한 likelihood
# ─────────────────────────────────────────────────────────────


def core_clue_likelihood(tree: ClueTree) -> float:
    """채택된 단서 중 가장 강한 likelihood (보스 단서) 반환.

    paradigm §21.4 의 ②번 트리거 — 트리에 채택된 단서들의 카탈로그 weights 를
    likelihood 로 변환했을 때 max(P(c|h)) 의 최댓값.

    단서가 카탈로그에 없거나 weights 비어있으면 그 단서는 무시. 모든 단서가
    그렇거나 트리가 root 만 있으면 0.0 반환.
    """
    try:
        catalog = load_catalog().get("clues", {})
    except FileNotFoundError:
        return 0.0

    max_lk = 0.0
    for node in tree.nodes.values():
        if node.clue_key == "__ROOT__" or node.clue_key not in catalog:
            continue
        weights = catalog[node.clue_key].get("weights", {})
        if not weights:
            continue
        lk = weights_to_likelihood(weights)
        if not lk:
            continue
        max_lk = max(max_lk, max(lk.values()))
    return max_lk


# ─────────────────────────────────────────────────────────────
# Zone 1 → Zone 2 트리거
# ─────────────────────────────────────────────────────────────


def is_zone2_unlocked(tree: ClueTree, posterior: dict[str, float]) -> bool:
    """게임 RPG 비유 — 맵 탐색 + 보스 단서 (paradigm §21.4 · V1.fix.12 보정).

    Zone 2 진입 조건 (OR):
      A. **맵 충분히 탐색**: depth ≥ TRIGGER_RELAXED_DEPTH (=4)
         → 약한 단서들만 누적해도 4개 이상이면 진입. 사용자 피드백: "Zone 2
            도달이 너무 느리다 — 단서 4개 정도면 도달 가까운 정도"
      B. **보스 단서 발견**: depth ≥ TRIGGER_MIN_DEPTH (=3) AND
                            max(P(c|h)) ≥ TRIGGER_MIN_LIKELIHOOD (=0.25)
         → 강한 단서 1개로 빠른 진입 (기존 동작 유지).

    posterior 인자는 향후 확장 (예: confidence 결합 트리거) 대비.
    """
    # ① 맵 탐색 — 트리 깊이 (root depth=0 이므로 채택 단서 수 = max depth)
    depth = max((n.depth for n in tree.nodes.values()), default=0)
    if depth < TRIGGER_MIN_DEPTH:
        return False

    # V1.fix.12 — depth ≥ 4 만으로도 Zone 2 (likelihood 무관)
    if depth >= TRIGGER_RELAXED_DEPTH:
        return True

    # ② 보스 단서 — 가장 강한 likelihood (depth=3 일 때)
    return core_clue_likelihood(tree) >= TRIGGER_MIN_LIKELIHOOD


# ─────────────────────────────────────────────────────────────
# Zone 2 → Zone 1 회귀
# ─────────────────────────────────────────────────────────────


def should_regress(posterior: dict[str, float], stage: int = 1) -> bool:
    """Zone 2 → Zone 1 자동 회귀 조건 (paradigm §21.8.1).

    1. entropy ≥ REGRESS_ENTROPY_THRESHOLD (uniform 근처 — 다시 모호)
    2. Top1 vs Top2 gap < REGRESS_GAP_THRESHOLD (우세 사라짐)

    둘 중 하나라도 True 면 회귀 권고. UI 는 자동 강제 X — 알림만 + 사용자
    [Zone 1 으로 회귀] 버튼.

    Phase N.4 정합 (2026-05-26): stage ≥ 2 에서는 회귀 권고 OFF.
      이유 — Multi-Stage 진입 직후 새 baseline (anchor 가설 0 + 나머지 12-30%
      분포) 은 entropy 가 자연스레 높음. 이건 "다시 모호" 가 아니라 "새 광범위
      탐색 시작" 이 정상 상태. 사용자 입장에서 "막 확정했는데 왜 회귀?!" 인지
      부조화를 차단.
    """
    if stage >= 2:
        return False

    H = posterior_entropy(posterior)
    if H >= REGRESS_ENTROPY_THRESHOLD:
        return True

    top = top_n(posterior, n=2)
    if len(top) >= 2 and (top[0][1] - top[1][1]) < REGRESS_GAP_THRESHOLD:
        return True

    return False


# ─────────────────────────────────────────────────────────────
# 복합 가설 chain — ATT&CK Kill Chain 정합 (paradigm §21.5)
# ─────────────────────────────────────────────────────────────


def compute_attack_chain(posterior: dict[str, float]) -> list[dict]:
    """Top N 가설을 Kill Chain 단계 순으로 재정렬 (paradigm §21.5).

    각 항목
    --------
        {
          "hypothesis": str,      # 사고유형 (IncidentType)
          "probability": float,   # 사후확률 (0~1)
          "kill_chain_phase": int # KILL_CHAIN_ORDER 매핑 단계 (1~7, 미정 시 99)
        }

    Top N (=ATTACK_CHAIN_TOP_N) 가 부족하면 가능한 만큼만 반환 (빈 list 안전).
    동일 phase 가설이 둘 이상이면 입력 확률 내림차순이 보조 정렬 기준.

    paradigm §21.8 #2·#3 — 단일 가설 우세도 Top 3 chain 표시 (이전 단계 추론).
    """
    topn = top_n(posterior, n=ATTACK_CHAIN_TOP_N)
    if not topn:
        return []

    # Kill Chain 단계 순 정렬 (보조 정렬: 확률 내림차순)
    chain = sorted(
        topn,
        key=lambda x: (KILL_CHAIN_ORDER.get(x[0], 99), -x[1]),
    )
    return [
        {
            "hypothesis": h,
            "probability": float(p),
            "kill_chain_phase": KILL_CHAIN_ORDER.get(h, 99),
        }
        for h, p in chain
    ]
