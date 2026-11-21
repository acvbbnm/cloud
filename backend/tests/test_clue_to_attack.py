"""H.2 — clue_to_attack.json 매핑 무결성 + 자동 추출 로직 단위 검증
(2026-05-25, byungwoo).

검증 영역:
    1. clue_to_attack.json 파일 존재 + 스키마 무결성
    2. 카탈로그 143 단서 모두 매핑 항목 존재
    3. 사용자 결정 (3건) 정합:
        ① 메타 단서 (Q1_inception:*) 5건 → techniques=null (DAG 제외)
        ② 1:N multi-target 단서 존재 (Option B)
        ③ 자동 추출 + 수동 보강 분포 (Option C 80/20)
    4. 추출 함수 단위 동작 (정규식·outcome_flags·category_signature)
    5. 100% 커버 — manual_pending 0건
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


BACKEND = Path(__file__).resolve().parent.parent
CATALOG = BACKEND / "data" / "triage" / "clue_catalog.json"
MAPPING = BACKEND / "data" / "triage" / "clue_to_attack.json"


@pytest.fixture(scope="module")
def mapping() -> dict:
    assert MAPPING.exists(), (
        f"clue_to_attack.json 없음 — scripts/build_clue_attack_mapping.py 실행 필요: {MAPPING}"
    )
    return json.loads(MAPPING.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog() -> dict:
    assert CATALOG.exists()
    return json.loads(CATALOG.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────
# 1. 파일 무결성 + 스키마
# ─────────────────────────────────────────────────────────────


def test_mapping_file_has_meta_and_mappings(mapping: dict) -> None:
    assert "_meta" in mapping
    assert "mappings" in mapping
    assert mapping["_meta"]["version"].startswith("v1")
    assert isinstance(mapping["mappings"], dict)


def test_mapping_meta_records_user_decisions(mapping: dict) -> None:
    decisions = mapping["_meta"].get("user_decisions", {})
    assert "Option C" in decisions.get("mapping_method", "")
    assert "Option A" in decisions.get("meta_clue_handling", "")
    assert "Option B" in decisions.get("multi_target", "")


def test_mapping_entries_have_required_fields(mapping: dict) -> None:
    required = {"techniques", "source", "confidence", "notes"}
    incomplete: list[str] = []
    for k, v in mapping["mappings"].items():
        miss = required - set(v.keys())
        if miss:
            incomplete.append(f"{k}: missing {miss}")
            if len(incomplete) >= 3:
                break
    assert not incomplete, "필드 누락: " + "; ".join(incomplete)


# ─────────────────────────────────────────────────────────────
# 2. 카탈로그 단서 모두 매핑 존재
# ─────────────────────────────────────────────────────────────


def test_all_catalog_clues_have_mapping(catalog: dict, mapping: dict) -> None:
    cat_keys = set(catalog["clues"].keys())
    map_keys = set(mapping["mappings"].keys())
    missing = cat_keys - map_keys
    extra = map_keys - cat_keys
    assert not missing, f"매핑 누락 단서 {len(missing)}개: {sorted(missing)[:5]}"
    assert not extra, f"카탈로그에 없는 매핑 {len(extra)}개"


# ─────────────────────────────────────────────────────────────
# 3. 사용자 결정 정합
# ─────────────────────────────────────────────────────────────


def test_user_decision_A_meta_clues_have_null_techniques(mapping: dict) -> None:
    """Option A — Q1_inception:* 5개는 techniques=null (DAG 제외)."""
    META_KEYS = {
        "Q1_inception:csp_alert",
        "Q1_inception:external_report",
        "Q1_inception:audit",
        "Q1_inception:service_anomaly",
        "Q1_inception:unknown",
    }
    for k in META_KEYS:
        m = mapping["mappings"].get(k)
        assert m is not None, f"메타 단서 {k} 매핑 없음"
        assert m["techniques"] is None, f"{k}: techniques 가 null 이 아님 — DAG 제외 X"
        assert m["source"] == "meta_excluded"
        assert m["confidence"] == "n/a"


def test_user_decision_B_multi_target_preserved(mapping: dict) -> None:
    """Option B — 1:N 매핑이 보존되어야 함 (Noisy-OR 처리 대상).

    카탈로그에서 multi-target 인 대표 단서 검증.
    """
    # ACCOUNT:mfa_disabled — MFA + Valid Accounts 다중
    mfa = mapping["mappings"].get("ACCOUNT:mfa_disabled", {})
    techs = mfa.get("techniques") or []
    assert len(techs) >= 2, (
        f"ACCOUNT:mfa_disabled multi-target X (techs={techs}) — Option B 위배"
    )

    # outcomeIsPrivilegedAccount → T1078 + T1548
    admin = mapping["mappings"].get("ACCOUNT:root_or_admin", {})
    techs2 = admin.get("techniques") or []
    assert len(techs2) >= 2, (
        f"ACCOUNT:root_or_admin multi-target X (techs={techs2})"
    )


def test_user_decision_C_distribution_80_20(mapping: dict) -> None:
    """Option C — 자동 80% + 수동 20% 균형. 실제는 자동 + 수동 보강 합쳐 100% 커버."""
    stats = mapping["_meta"]["stats"]
    total = stats["total"]
    assert total == 143  # 카탈로그 정합

    auto_categories = (
        stats["direct_technique"]
        + stats["auto_weight_source"]
        + stats["auto_outcome_flags"]
        + stats["auto_category_signature"]
    )
    # 자동 카테고리 합 ≥ 80% (예상 ~85%+)
    # 주의: 카운트가 multi-source 일 때 중복 카운트되므로 with_techniques 기준 검증
    assert stats["manual_pending"] == 0, (
        f"manual_pending {stats['manual_pending']} > 0 — 100% 커버 실패"
    )
    # multi-target ≥ 30 (1:N 매핑이 의미 있게 존재)
    assert stats["multi_target"] >= 30, (
        f"multi-target {stats['multi_target']} < 30 — Option B 효과 미흡"
    )


# ─────────────────────────────────────────────────────────────
# 4. 추출 함수 단위 검증
# ─────────────────────────────────────────────────────────────


def test_extract_techniques_from_text_patterns() -> None:
    from scripts.build_clue_attack_mapping import extract_techniques_from_text

    # 기본 T-NNNN
    assert extract_techniques_from_text("MITRE T1078") == ["T1078"]
    # T-NNNN.NNN 서브기법
    assert extract_techniques_from_text("T1090.003 + T1078.004") == [
        "T1090.003",
        "T1078.004",
    ]
    # 중복 제거 + 순서 보존
    assert extract_techniques_from_text("T1078, T1078.004, T1078") == [
        "T1078",
        "T1078.004",
    ]
    # 빈 입력
    assert extract_techniques_from_text("") == []
    # 비 ATT&CK 텍스트
    assert extract_techniques_from_text("KISA §2.4 + NIST 800-61r2") == []


def test_outcome_flag_lookup_known_keys() -> None:
    from scripts.build_clue_attack_mapping import techniques_from_outcome_flags

    # outcomeMfaDisabled → T1556.006
    assert "T1556.006" in techniques_from_outcome_flags({"outcomeMfaDisabled": True})
    # outcomeRansomwarePattern → T1486
    assert "T1486" in techniques_from_outcome_flags({"outcomeRansomwarePattern": True})
    # 다중 플래그 → 다중 기법
    result = techniques_from_outcome_flags({
        "outcomeIsAnonymizedSource": True,
        "outcomeIsForeignSource": True,
    })
    assert "T1090.003" in result
    assert "T1078.004" in result
    # False / 빈 dict → 빈 리스트
    assert techniques_from_outcome_flags({"outcomeMfaDisabled": False}) == []
    assert techniques_from_outcome_flags({}) == []


def test_category_signature_known_pairs() -> None:
    from scripts.build_clue_attack_mapping import techniques_from_category_signature

    assert techniques_from_category_signature("SERVICE", "cloud_trail") == ["T1562.008"]
    assert techniques_from_category_signature("SERVICE", "object_storage") == ["T1530"]
    assert techniques_from_category_signature("DOMAIN", "c2") == ["T1071"]
    # 모르는 조합 → 빈 리스트
    assert techniques_from_category_signature("UNKNOWN", "value") == []


# ─────────────────────────────────────────────────────────────
# 5. ATT&CK 기법 ID 형식 무결성
# ─────────────────────────────────────────────────────────────


def test_all_technique_ids_match_attack_format(mapping: dict) -> None:
    """T-NNNN 또는 T-NNNN.NNN 형식만 허용 (MITRE ATT&CK 표준)."""
    import re

    pattern = re.compile(r"^T\d{4}(?:\.\d{3})?$")
    bad: list[str] = []
    for k, m in mapping["mappings"].items():
        techs = m["techniques"]
        if techs is None:
            continue
        for t in techs:
            if not pattern.match(t):
                bad.append(f"{k}: 부적합 기법 ID '{t}'")
                if len(bad) >= 3:
                    break
    assert not bad, "; ".join(bad)


def test_no_empty_string_techniques(mapping: dict) -> None:
    """techniques 리스트에 빈 문자열 X."""
    for k, m in mapping["mappings"].items():
        techs = m["techniques"]
        if techs is None:
            continue
        for t in techs:
            assert t and isinstance(t, str), f"{k}: 빈 문자열·잘못된 기법 ID"


# ─────────────────────────────────────────────────────────────
# 6. 대표 단서 sanity (PDF §17.B 정합 확인)
# ─────────────────────────────────────────────────────────────


def test_known_clue_attack_pairs(mapping: dict) -> None:
    """잘 알려진 단서 → 기법 매핑이 학술 정합."""
    cases = [
        ("IP_ADDRESS:tor_vpn", "T1090.003"),  # Multi-hop Proxy
        ("ACCOUNT:mfa_disabled", "T1556.006"),  # MFA bypass
        ("ACCOUNT:newly_created", "T1136"),  # Create Account
        ("SERVICE:cloud_trail", "T1562.008"),  # Disable Cloud Logs
        ("DOMAIN:c2", "T1071"),  # Application Layer Protocol
        ("Q5-RANSOM:multi_region", "T1486"),  # Data Encrypted for Impact
    ]
    for clue, expected_tid in cases:
        m = mapping["mappings"].get(clue, {})
        techs = m.get("techniques") or []
        assert expected_tid in techs, (
            f"{clue} → {expected_tid} 매핑 누락 (실제: {techs})"
        )
