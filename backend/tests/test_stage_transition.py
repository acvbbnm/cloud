"""Phase N.4 — Stage Transition Matrix 단위 테스트 (2026-05-26, byungwoo).

설계서: `docs/evidence_tree_paradigm.md` §23

검증 항목
---------
1. 8×8 매트릭스 완전성 — 모든 사고유형 row 보유, 각 row 합 = 1
2. anchor freeze — confirmed 가설은 다음 stage prior 0
3. 연관 가중치 — CRED → PRIV 높음, DATA → RANSOM 최고
4. 다단계 chain — 누적 시 모든 confirmed 가설 0 + 나머지 정규화
5. chain_description — 한국어 시퀀스
6. advance_to_next_stage — tree 객체 변경 정합
"""
from __future__ import annotations

import pytest

from core.intake.bayesian import initial_posterior
from core.intake.clue_tree import make_root
from core.intake.stage_transition import (
    STAGE_TRANSITION_MATRIX,
    advance_to_next_stage,
    chain_description,
    compute_stage_prior,
    get_transition_row,
    is_multistage,
)


HYPS_8 = list(STAGE_TRANSITION_MATRIX.keys())


# ─────────────────────────────────────────────────────────────
# 1. 매트릭스 완전성
# ─────────────────────────────────────────────────────────────


def test_matrix_has_8_rows() -> None:
    """8 사고유형 모두 row 보유."""
    expected = {
        "PHISH_INITIAL_ACCESS",
        "CREDENTIAL_THEFT",
        "PRIVILEGE_ESCALATION",
        "INSIDER_THREAT",
        "MISCONFIG_EXPOSURE",
        "AUDIT_LOG_TAMPERING",
        "DATA_EXFILTRATION",
        "RANSOMWARE",
    }
    assert set(STAGE_TRANSITION_MATRIX.keys()) == expected


def test_matrix_row_sums_to_one() -> None:
    """각 row 합 = 1.0 (UNCLASSIFIED 제외, 자기 자신 — = 0)."""
    for confirmed, row in STAGE_TRANSITION_MATRIX.items():
        total = sum(row.values())
        assert total == pytest.approx(1.0, abs=1e-6), (
            f"{confirmed} row sum = {total}"
        )
        # 자기 자신은 row 에 등장하지 않음 (anchor)
        assert confirmed not in row, f"{confirmed} 가 자기 row 에 포함됨"


# ─────────────────────────────────────────────────────────────
# 2. 연관 가중치 — 학술 정합 확인
# ─────────────────────────────────────────────────────────────


def test_phish_to_cred_highest() -> None:
    """PHISH → CRED 가 가장 높음 (ATT&CK Flow #4 Storm-0558 정석)."""
    row = STAGE_TRANSITION_MATRIX["PHISH_INITIAL_ACCESS"]
    top = max(row.items(), key=lambda x: x[1])
    assert top[0] == "CREDENTIAL_THEFT"
    assert top[1] >= 0.35


def test_cred_to_priv_or_data() -> None:
    """CRED → PRIV 가 가장 높고 DATA 도 상위 (탈취 후 흔한 다음)."""
    row = STAGE_TRANSITION_MATRIX["CREDENTIAL_THEFT"]
    top = max(row.items(), key=lambda x: x[1])
    assert top[0] == "PRIVILEGE_ESCALATION"
    assert row["DATA_EXFILTRATION"] >= 0.15


def test_data_to_ransom_highest() -> None:
    """DATA → RANSOM 가장 높음 (Mandiant double extortion 정석)."""
    row = STAGE_TRANSITION_MATRIX["DATA_EXFILTRATION"]
    top = max(row.items(), key=lambda x: x[1])
    assert top[0] == "RANSOMWARE"
    assert top[1] >= 0.45


def test_ransom_to_data_or_audit() -> None:
    """RANSOM → DATA 가장 높음 (협박용 백업) + AUDIT 두번째 (흔적 지움)."""
    row = STAGE_TRANSITION_MATRIX["RANSOMWARE"]
    top = max(row.items(), key=lambda x: x[1])
    assert top[0] == "DATA_EXFILTRATION"
    # AUDIT 2위 또는 그 이상
    sorted_h = sorted(row.items(), key=lambda x: -x[1])
    assert "AUDIT_LOG_TAMPERING" in [h for h, _ in sorted_h[:3]]


# ─────────────────────────────────────────────────────────────
# 3. compute_stage_prior — anchor freeze + 정규화
# ─────────────────────────────────────────────────────────────


def test_stage_prior_freezes_anchor() -> None:
    """확정 가설은 다음 stage prior 0."""
    prior = compute_stage_prior(["CREDENTIAL_THEFT"])
    assert prior["CREDENTIAL_THEFT"] == 0.0
    # 나머지 7 가설 합 = 1
    total = sum(prior[h] for h in HYPS_8)
    assert total == pytest.approx(1.0, abs=1e-6)


def test_stage_prior_multistage_freezes_all() -> None:
    """여러 stage 누적 시 모든 confirmed 가설 freeze."""
    prior = compute_stage_prior(["CREDENTIAL_THEFT", "PRIVILEGE_ESCALATION"])
    assert prior["CREDENTIAL_THEFT"] == 0.0
    assert prior["PRIVILEGE_ESCALATION"] == 0.0
    # 가장 최근 (PRIV) 의 transition row 기준 + CRED 제외 정규화
    # PRIV row 에서 CRED 0.05 제외 → 나머지 6 가설 합 = 1
    total = sum(prior[h] for h in HYPS_8)
    assert total == pytest.approx(1.0, abs=1e-6)


def test_stage_prior_cred_anchor_top() -> None:
    """CRED 확정 시 PRIV 가 다음 prior 최고 (정석 패턴)."""
    prior = compute_stage_prior(["CREDENTIAL_THEFT"])
    ranked = sorted(
        [(h, p) for h, p in prior.items() if h in HYPS_8 and p > 0],
        key=lambda x: -x[1],
    )
    assert ranked[0][0] == "PRIVILEGE_ESCALATION"


def test_stage_prior_empty_raises() -> None:
    """빈 confirmed 시퀀스 → ValueError."""
    with pytest.raises(ValueError):
        compute_stage_prior([])


def test_stage_prior_unknown_hypothesis_raises() -> None:
    """등록 안 된 가설 → ValueError."""
    with pytest.raises(ValueError):
        compute_stage_prior(["INVALID_TYPE"])


# ─────────────────────────────────────────────────────────────
# 4. is_multistage / chain_description
# ─────────────────────────────────────────────────────────────


def test_is_multistage_threshold() -> None:
    """multi-stage = confirmed ≥ 2."""
    assert is_multistage([]) is False
    assert is_multistage(["CREDENTIAL_THEFT"]) is False
    assert is_multistage(["CREDENTIAL_THEFT", "PRIVILEGE_ESCALATION"]) is True
    assert is_multistage(["CRED", "PRIV", "DATA"]) is True


def test_chain_description_korean() -> None:
    """한국어 chain 설명."""
    assert chain_description([]) == "(미확정)"
    assert chain_description(["CREDENTIAL_THEFT"]) == "자격증명 탈취"
    chain = ["CREDENTIAL_THEFT", "PRIVILEGE_ESCALATION", "DATA_EXFILTRATION"]
    assert chain_description(chain) == "자격증명 탈취 → 권한 상승 → 데이터 유출"


# ─────────────────────────────────────────────────────────────
# 5. advance_to_next_stage — tree 변경 정합
# ─────────────────────────────────────────────────────────────


def test_advance_to_next_stage_changes_posterior() -> None:
    """tree.posterior_current 가 새 baseline 으로 변경."""
    tree = make_root("case-test", initial_posterior())
    advance_to_next_stage(tree, "CREDENTIAL_THEFT")
    # 새 baseline = MATRIX["CREDENTIAL_THEFT"] (CRED 제외)
    assert tree.posterior_current["CREDENTIAL_THEFT"] == 0.0
    assert tree.posterior_current["PRIVILEGE_ESCALATION"] > 0.2
    assert tree.confidence_reached is False
    assert tree.incident_type_recommendation is None


def test_advance_to_next_stage_invalid_hypothesis() -> None:
    """등록 안 된 가설 → ValueError."""
    tree = make_root("case-test", initial_posterior())
    with pytest.raises(ValueError):
        advance_to_next_stage(tree, "INVALID")
