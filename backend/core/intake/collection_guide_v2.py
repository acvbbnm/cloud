"""Layer 0 — CollectionGuideV2 (외부 표준 6종 기반 v2 수집 가이드 생성기).

설계서 dev2 청사진 (`docs/신규_수집가이드_설계.md`  4) 구현.

기존 `collection_guide.py` (v1) 와 **병행 동작**:
  - v1 `/api/guide`            : incident_type + csp 두 필드만 사용, 시드 5건
  - v2 `/api/guide/v2`         : system_config 전체 동적 반영, 카테고리 9개 매트릭스

5 단계 흐름:
  1) 사고유형 → Kill Chain 단계 (`incident_type_phases.json`)
  2) 각 phase 에 매칭되는 카테고리 시드 수집 (`categories/*.json`)
  3) system_config → environment_modifiers 적용 (BOOST/ADD)
  4) NIST/KISA 휘발성 우선순위 정렬
  5) Kill Chain 단계별 그룹화 + applied_modifiers 로그

외부 표준 인용:
  - Google Cloud Threat Intel — 1.x 로그 카테고리 분류
  - MITRE ATT&CK Cloud Matrix v14 — Kill Chain 12 전술
  - KISA 침해사고 분석절차 안내서 (제2010-8호) 2.4 초기 대응 점검표
  - NIST SP 800-86 3.1 휘발성 계층
  - ISO/IEC 27037:2012 디지털 증거 처리 4단계
  - CSA Top Threats to Cloud Computing 2024
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from core.intake.modifier_eval import eval_operator, resolve_field
from db.models import (
    AttackEventModel,
    IncidentCaseModel,
    OCSFEventModel,
    RawEventModel,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Kill Chain Phase 메타데이터 (MITRE ATT&CK Cloud Matrix v14, 12 전술)
# 카테고리 시드의 kill_chain_phases 와 매핑되는 한국어명·MITRE URL·KISA 참조
# ─────────────────────────────────────────────────────────────
_PHASE_METADATA: dict[str, dict] = {
    "Initial Access": {
        "phase_id": "TA0001",
        "phase_ko": "초기 침투",
        "description": "공격자가 환경에 처음 진입하는 단계 (자격증명 남용, 피싱, 공인 IP 노출 노출 등).",
        "mitre_url": "https://attack.mitre.org/tactics/TA0001/",
        "kisa_reference": "KISA 2.4 사고 탐지 - 비인가 접속",
    },
    "Execution": {
        "phase_id": "TA0002",
        "phase_ko": "실행",
        "description": "악성 코드·명령이 클라우드 자원에서 실행되는 단계.",
        "mitre_url": "https://attack.mitre.org/tactics/TA0002/",
        "kisa_reference": "KISA 3.3 불법적인 자원 사용",
    },
    "Persistence": {
        "phase_id": "TA0003",
        "phase_ko": "영속성 확보",
        "description": "공격자가 재로그인 없이도 접근을 유지할 수 있는 백도어(AccessKey·Sub Account 등) 확보.",
        "mitre_url": "https://attack.mitre.org/tactics/TA0003/",
        "kisa_reference": "KISA 2.4 + 3.3",
    },
    "Privilege Escalation": {
        "phase_id": "TA0004",
        "phase_ko": "권한 확대",
        "description": "현재 권한을 넘어서는 권한(관리자·정책 변경 등)을 획득.",
        "mitre_url": "https://attack.mitre.org/tactics/TA0004/",
        "kisa_reference": "KISA 3.3 불법적인 자원 사용 (권한 침해)",
    },
    "Stealth": {
        "phase_id": "TA0005",
        "phase_ko": "은닉",
        "description": "탐지를 회피하기 위해 흔적 제거·로그 변조 등을 수행.",
        "mitre_url": "https://attack.mitre.org/tactics/TA0005/",
        "kisa_reference": "KISA 3.3 데이터 손상·변조",
    },
    "Defense Impairment": {
        "phase_id": "TA0112",
        "phase_ko": "방어 무력화",
        "description": "보안 도구·감사 로그 자체를 비활성화하거나 삭제.",
        "mitre_url": "https://attack.mitre.org/tactics/TA0112/",
        "kisa_reference": "KISA 3.3 데이터 손상·변조 (로그)",
    },
    "Credential Access": {
        "phase_id": "TA0006",
        "phase_ko": "자격증명 접근",
        "description": "사용자 비밀번호·AccessKey·root 비밀번호 등 자격증명 탈취.",
        "mitre_url": "https://attack.mitre.org/tactics/TA0006/",
        "kisa_reference": "KISA 3.3 불법적인 자원 사용 (계정 도용)",
    },
    "Discovery": {
        "phase_id": "TA0007",
        "phase_ko": "환경 탐색",
        "description": "클라우드 환경의 리소스·계정·정책 등을 열거.",
        "mitre_url": "https://attack.mitre.org/tactics/TA0007/",
        "kisa_reference": "KISA 3.3 불법적인 자원 사용",
    },
    "Lateral Movement": {
        "phase_id": "TA0008",
        "phase_ko": "횡이동",
        "description": "한 시스템에서 다른 시스템·서비스·CSP 로 이동.",
        "mitre_url": "https://attack.mitre.org/tactics/TA0008/",
        "kisa_reference": "KISA 3.3 불법적인 자원 사용 (확장)",
    },
    "Collection": {
        "phase_id": "TA0009",
        "phase_ko": "데이터 수집",
        "description": "탈취·유출 대상 데이터를 식별·수집.",
        "mitre_url": "https://attack.mitre.org/tactics/TA0009/",
        "kisa_reference": "KISA 3.3 정보 누설",
    },
    "Exfiltration": {
        "phase_id": "TA0010",
        "phase_ko": "데이터 유출",
        "description": "수집한 데이터를 외부로 반출 (Pre-signed URL, Object Storage 다운로드 등).",
        "mitre_url": "https://attack.mitre.org/tactics/TA0010/",
        "kisa_reference": "KISA 3.3 정보 누설",
    },
    "Impact": {
        "phase_id": "TA0040",
        "phase_ko": "영향·파괴",
        "description": "서비스 중단·자원 삭제·데이터 파괴.",
        "mitre_url": "https://attack.mitre.org/tactics/TA0040/",
        "kisa_reference": "KISA 3.3 데이터 손상·변조",
    },
}


# ─────────────────────────────────────────────────────────────
# 데이터 로딩 (startup 1회 캐싱)
# ─────────────────────────────────────────────────────────────


def _v2_dir() -> Path:
    """`backend/data/collection_targets_v2/` 경로."""
    return settings.DATA_DIR / "collection_targets_v2"


_cache: dict[str, object] = {}


def _load_categories() -> list[dict]:
    """9 카테고리 시드 JSON 모두 로딩 + 캐싱."""
    if "categories" in _cache:
        return _cache["categories"]  # type: ignore[return-value]
    out: list[dict] = []
    cat_dir = _v2_dir() / "categories"
    if not cat_dir.exists():
        logger.warning("v2 categories directory missing: %s", cat_dir)
        _cache["categories"] = []
        return []
    for f in sorted(cat_dir.glob("*.json")):
        with open(f, encoding="utf-8") as fp:
            out.append(json.load(fp))
    _cache["categories"] = out
    return out


def _load_incident_phases() -> dict:
    """`incident_type_phases.json` 로딩."""
    if "phases" in _cache:
        return _cache["phases"]  # type: ignore[return-value]
    p = _v2_dir() / "incident_type_phases.json"
    if not p.exists():
        logger.warning("incident_type_phases.json missing: %s", p)
        _cache["phases"] = {"incident_types": {}}
        return _cache["phases"]
    with open(p, encoding="utf-8") as fp:
        _cache["phases"] = json.load(fp)
    return _cache["phases"]


def _load_modifiers() -> dict:
    """`environment_modifiers.json` 로딩."""
    if "modifiers" in _cache:
        return _cache["modifiers"]  # type: ignore[return-value]
    p = _v2_dir() / "environment_modifiers.json"
    if not p.exists():
        logger.warning("environment_modifiers.json missing: %s", p)
        _cache["modifiers"] = {"modifiers": [], "fallback_modifiers": []}
        return _cache["modifiers"]
    with open(p, encoding="utf-8") as fp:
        _cache["modifiers"] = json.load(fp)
    return _cache["modifiers"]


def _load_technique_tactic_map() -> dict[str, str]:
    """`attack_rules/rules.json` → {technique_id: tactic} 매핑 로딩 + 캐싱.

    Phase L (2026-05-31) — 단서 루프 기법 ID 를 Kill Chain 단계(전술)로 환산하기 위함.
    rules.json 의 tactic 은 사람이 읽는 전술명("Credential Access" 등) 으로 본 모듈의
    _PHASE_METADATA 키 / 카테고리 kill_chain_phases 와 동일 네임스페이스.

    서브기법(T1078.004)·기반기법(T1078) 양쪽 키를 모두 등록해 단서·로그가 어느 쪽
    표기를 쓰든 전술 환산이 가능하게 한다.
    """
    if "tech_tactic" in _cache:
        return _cache["tech_tactic"]  # type: ignore[return-value]
    out: dict[str, str] = {}
    p = settings.DATA_DIR / "attack_rules" / "rules.json"
    if not p.exists():
        logger.warning("attack_rules/rules.json missing: %s", p)
        _cache["tech_tactic"] = out
        return out
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        _cache["tech_tactic"] = out
        return out
    rules = doc.get("rules") if isinstance(doc, dict) else doc
    for r in rules or []:
        if not isinstance(r, dict):
            continue
        tid = r.get("technique_id")
        tactic = r.get("tactic")
        if not tid or not tactic:
            continue
        out.setdefault(tid, tactic)
        # 기반기법 키도 등록 (서브기법만 알려진 경우의 폴백)
        base = tid.split(".", 1)[0]
        out.setdefault(base, tactic)
    _cache["tech_tactic"] = out
    return out


def invalidate_cache() -> None:
    """테스트·시드 핫리로드용. 운영에서는 startup 후 호출 X."""
    _cache.clear()


# ─────────────────────────────────────────────────────────────
# 핵심 5단계 로직
# ─────────────────────────────────────────────────────────────


def _lookup_phases(incident_type: str) -> list[str]:
    """사고유형 → primary + secondary phases + applicable_categories[*].phase (중복 제거).

    incident_type_phases.json 의 applicable_categories 항목에 명시된 phase 도
    합집합에 포함해야 'AUDIT_LOG_TAMPERING 외 사고유형에서도 1.7(Stealth) 카테고리가
    적용된다' 같은 명시적 시드 의도를 백엔드가 그대로 따른다.

    primary → secondary → applicable_categories 순으로 dedup. 원본 순서를 유지해
    Kill Chain UI 그룹 표시 시 'primary 단계 먼저' 시각화가 유지된다.

    UNCLASSIFIED 처리 (2026-05-18 dev3):
      사고유형 미확정 상태에서는 Initial Access · Credential Access · Discovery 의
      세 phase 만 우선 노출 (KISA 2.4 사고 탐지 단계의 공통 점검표). 사용자가
      트리아주 진행 후 확정하면 정상 5종 분기로 복귀.
    """
    if incident_type == "UNCLASSIFIED":
        # KISA 2.4 초기 대응 점검표 — 사고 유형 식별 전 공통 수집 항목
        return ["Initial Access", "Credential Access", "Discovery"]

    pdata = _load_incident_phases().get("incident_types", {}).get(incident_type)
    if not pdata:
        return []
    seen: set[str] = set()
    out: list[str] = []
    sources: list[list] = [
        list(pdata.get("primary_phases", [])),
        list(pdata.get("secondary_phases", [])),
        [
            ac.get("phase")
            for ac in pdata.get("applicable_categories", [])
            if ac.get("phase")
        ],
    ]
    for src in sources:
        for p in src:
            if p and p not in seen:
                seen.add(p)
                out.append(p)
    return out


def _categories_for_phases(phases: list[str], csp: str) -> list[dict]:
    """주어진 phases 중 하나 이상에 매칭되는 카테고리만 필터.

    csp 필터: 'all' 이면 두 CSP 매핑이 모두 있는 카테고리만 통과시키지 않고
    그냥 통과 (현재 9 카테고리 모두 NCP+NHN 양쪽 매핑 보유).
    """
    out: list[dict] = []
    phase_set = set(phases)
    for cat in _load_categories():
        cat_phases = set(cat.get("kill_chain_phases", []))
        if cat_phases & phase_set:
            # 카테고리 깊은 복사 — modifier 가 priority 를 수정해도 시드 원본 보호
            out.append(json.loads(json.dumps(cat, ensure_ascii=False)))
    return out


# ── modifier operator 평가 ──────────────────────────────────


def _apply_effect(
    effect: dict | str,
    categories: list[dict],
    extra_targets: list[dict],
    *,
    parent: Optional[dict] = None,
) -> None:
    """단일 effect 를 적용 (in-place).

    effect 가 dict 면 secondary_effects 원소 (effect/category_id/boost/...),
    str + parent 면 primary effect (effect 키만 따로 + parent 본체에서 값 읽음).
    """
    if isinstance(effect, str):
        # primary — parent 에서 값 읽기
        eff_kind = effect
        src = parent or {}
    else:
        eff_kind = effect.get("effect", "")
        src = effect

    if eff_kind == "BOOST_CATEGORY":
        cid = src.get("category_id")
        boost = int(src.get("boost", 0))
        if not cid or boost == 0:
            return
        for cat in categories:
            if cat.get("category_id") == cid:
                # 우선순위 = volatility_priority 기본 + 누적 boost
                cat["__boost"] = cat.get("__boost", 0) + boost
        return

    if eff_kind == "BOOST_PHASE":
        phase = src.get("kill_chain_phase")
        boost = int(src.get("boost", 0))
        if not phase or boost == 0:
            return
        for cat in categories:
            if phase in cat.get("kill_chain_phases", []):
                cat["__boost"] = cat.get("__boost", 0) + boost
        return

    if eff_kind == "ADD_TARGET":
        tgt = src.get("target")
        if tgt:
            extra_targets.append({**tgt, "__from_modifier": src.get("target_id")})
        return

    if eff_kind == "NO_MODIFY":
        return


def _apply_environment_modifiers(
    categories: list[dict],
    system_config: Optional[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """system_config 입력값에 따라 카테고리에 BOOST/ADD 적용.

    Returns:
        (boosted_categories, extra_targets, applied_modifiers_log)
    """
    mods_doc = _load_modifiers()
    applied: list[dict] = []
    extra_targets: list[dict] = []

    sc = system_config or {}

    # system_config 가 비어있으면 fallback_modifiers 만 안내 (NO_MODIFY)
    if not sc:
        for fb in mods_doc.get("fallback_modifiers", []):
            applied.append({
                "id": fb.get("id"),
                "effect": fb.get("effect"),
                "reason": fb.get("reason"),
            })
        return categories, extra_targets, applied

    for m in mods_doc.get("modifiers", []):
        field = m.get("field", "")
        operator = m.get("operator", "")
        expected = m.get("value")
        actual = resolve_field(sc, field)
        if not eval_operator(actual, operator, expected):
            continue

        # primary effect 적용
        _apply_effect(m.get("effect", ""), categories, extra_targets, parent=m)

        # secondary_effects 적용
        for sec in m.get("secondary_effects", []) or []:
            _apply_effect(sec, categories, extra_targets)

        applied.append({
            "id": m.get("id"),
            "field": field,
            "matched_value": actual,
            "effect": m.get("effect"),
            "category_id": m.get("category_id"),
            "kill_chain_phase": m.get("kill_chain_phase"),
            "boost": m.get("boost"),
            "secondary": [
                {
                    "effect": s.get("effect"),
                    "category_id": s.get("category_id"),
                    "kill_chain_phase": s.get("kill_chain_phase"),
                    "boost": s.get("boost"),
                }
                for s in (m.get("secondary_effects") or [])
            ],
            "reason": m.get("reason"),
            "source": m.get("source"),
        })

    return categories, extra_targets, applied


def _compute_priority(cat: dict) -> int:
    """기본 volatility_priority + modifier 부스팅 + 단서 부스팅 누적."""
    base = int(cat.get("volatility_priority", 0))
    return base + int(cat.get("__boost", 0)) + int(cat.get("__clue_boost", 0))


def _priority_basis(cat: dict) -> str:
    """우선순위 산출 근거 한 줄 (UI 표시용)."""
    base = int(cat.get("volatility_priority", 0))
    boost = int(cat.get("__boost", 0))
    clue_boost = int(cat.get("__clue_boost", 0))
    basis = cat.get("volatility_basis", f"NIST 휘발성 P{base}")
    if boost > 0:
        basis = f"{basis} + 환경 보정 +{boost}"
    if clue_boost > 0:
        basis = f"{basis} + 단서 연관 +{clue_boost}"
    return basis


def _summarize_csp_mapping(cat: dict) -> dict[str, str]:
    """csp_mapping → V-1 화면 표시용 짧은 텍스트.

    예: { "naver": "action: Login / Logout / Console Login",
          "nhn":   "eventId: event_id.iam.login" }
    """
    out: dict[str, str] = {}
    cm = cat.get("csp_mapping", {}) or {}
    for csp, spec in cm.items():
        parts: list[str] = []
        if spec.get("action_patterns"):
            ap = spec["action_patterns"]
            parts.append("action: " + " / ".join(ap[:3]) + ("…" if len(ap) > 3 else ""))
        if spec.get("event_id_patterns"):
            ep = spec["event_id_patterns"]
            parts.append("eventId: " + " / ".join(ep[:3]) + ("…" if len(ep) > 3 else ""))
        out[csp] = " · ".join(parts) if parts else (spec.get("log_source") or "")
    return out


def _collection_methods_from_csp_mapping(cat: dict) -> dict[str, dict]:
    """csp_mapping → '어떻게 수집하나' 응답 구조.

    각 CSP 별로 (log_source, action_patterns, event_id_patterns, collection_steps,
    cli_hint, field_locations, example_raw) 를 묶어서 KB 패널 렌더링에 그대로 사용.

    Returns:
        예: {
            "naver": {
                "log_source": "Cloud Activity Tracer",
                "patterns": ["Login", "Logout", "Console Login"],
                "collection_steps": [...4 단계...],
                "cli_hint": "...",
                "field_locations": {...},
                "example_raw": {...}
            },
            "nhn": {...}
        }
    """
    out: dict[str, dict] = {}
    cm = cat.get("csp_mapping", {}) or {}
    for csp, spec in cm.items():
        out[csp] = {
            "log_source": spec.get("log_source") or "",
            "patterns": list(spec.get("action_patterns") or spec.get("event_id_patterns") or []),
            "pattern_kind": "action" if spec.get("action_patterns") else ("eventId" if spec.get("event_id_patterns") else ""),
            "collection_steps": list(spec.get("collection_steps") or []),
            "cli_hint": spec.get("cli_hint") or "",
            "field_locations": spec.get("field_locations") or {},
            "example_raw": spec.get("example_raw") or {},
            "note": spec.get("note") or "",
        }
    return out


def _sources_from_kb(cat: dict) -> list[dict]:
    """카테고리의 kb_source(primary + secondary) → API 응답 sources 배열."""
    out: list[dict] = []
    kb = cat.get("kb_source", {}) or {}
    pri = kb.get("primary")
    if pri:
        out.append({
            "std": pri.get("standard"),
            "ref": pri.get("section"),
            "title": pri.get("title"),
            "url": pri.get("url"),
        })
    for sec in kb.get("secondary", []) or []:
        out.append({
            "std": sec.get("standard"),
            "ref": sec.get("section"),
            "title": sec.get("title"),
            "url": sec.get("url"),
        })
    return out


def _group_by_phase(
    categories: list[dict],
    phases: list[str],
    collected_map: Optional[dict[str, bool]] = None,
) -> dict[str, dict]:
    """phase 별로 카테고리들을 묶어서 응답 형식으로 변환.

    각 카테고리는 phases 여러 개에 속할 수 있어서, 본 사고유형의 phases 마다 등장.
    phase 안에서는 priority 내림차순 정렬.

    Phase G (2026-05-22) — `collected_map` 이 주어지면 target.collected 를 갱신.
    `_compute_collection_status` 가 산출한 {category_id: bool} 매핑을 사용.

    참고: ADD_TARGET 환경 경고는 phase 와 무관한 권고이므로 본 함수에서 처리하지 않고
    응답 상단의 `environment_warnings` 영역으로 분리한다 (`_format_env_warnings`).
    """
    collected_map = collected_map or {}
    grouped: dict[str, dict] = {}

    for phase in phases:
        meta = _PHASE_METADATA.get(phase, {
            "phase_ko": phase,
            "description": "",
            "mitre_url": "",
            "kisa_reference": "",
        })

        phase_targets: list[dict] = []

        for cat in categories:
            if phase not in cat.get("kill_chain_phases", []):
                continue
            priority = _compute_priority(cat)
            cat_id = cat.get("category_id")
            target = {
                "category_id": cat_id,
                "category_name": cat.get("category_name"),
                "evidence_role": cat.get("evidence_role"),
                "priority": priority,
                "priority_basis": _priority_basis(cat),
                "rationale": cat.get("rationale"),
                "use_cases": list(cat.get("use_cases") or []),
                "csp_specific": _summarize_csp_mapping(cat),
                "collection_methods": _collection_methods_from_csp_mapping(cat),
                "sources": _sources_from_kb(cat),
                # Phase G: raw_events.action / eventId 매칭 결과
                "collected": bool(collected_map.get(cat_id, False)),
                # Phase L: 단서 루프 신호(전술)와 연관되어 부스트된 단계인지
                "clue_relevant": int(cat.get("__clue_boost", 0)) > 0,
            }
            phase_targets.append(target)

        # priority 내림차순 정렬
        phase_targets.sort(key=lambda t: t.get("priority", 0), reverse=True)

        grouped[phase] = {
            "phase_id": meta.get("phase_id"),
            "phase_name": meta.get("phase_ko"),
            "phase_description": meta.get("description"),
            "mitre_url": meta.get("mitre_url"),
            "kisa_reference": meta.get("kisa_reference"),
            "targets": phase_targets,
        }

    return grouped


def _format_env_warnings(extra_targets: list[dict]) -> list[dict]:
    """ADD_TARGET 으로 추가된 환경 보정 권고 항목을 응답 형식으로 변환.

    phase 와 무관한 글로벌 경고이므로 phase 그룹화에서 빠지고 별도 영역으로 노출.
    같은 target_id 가 여러 modifier 에서 트리거되어도 1회만.
    """
    seen: set[str] = set()
    out: list[dict] = []
    for et in extra_targets:
        key = et.get("__from_modifier") or et.get("category_name") or ""
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "category_id": et.get("category_id"),
            "category_name": et.get("category_name"),
            "evidence_role": et.get("evidence_role"),
            "priority": int(et.get("priority", 0)),
            "rationale": et.get("rationale"),
            "from_modifier": et.get("__from_modifier"),
        })
    out.sort(key=lambda x: x.get("priority", 0), reverse=True)
    return out


# ─────────────────────────────────────────────────────────────
# Phase G — raw_events 매칭 기반 수집 진행도 산출
# ─────────────────────────────────────────────────────────────


def _action_matches(action: str, patterns: list[str]) -> bool:
    """NCP `action` 필드 vs `csp_mapping.naver.action_patterns` 매칭 (대소문자 무시 substring/equal)."""
    if not action or not patterns:
        return False
    act = action.strip().lower()
    for p in patterns:
        p_l = (p or "").strip().lower()
        if not p_l:
            continue
        # 정확 일치 또는 부분 매칭 (양방향) — 카테고리 시드의 패턴이 raw 보다
        # 더 구체/더 일반 둘 다 가능
        if p_l == act or p_l in act or act in p_l:
            return True
    return False


def _event_id_matches(event_id: str, patterns: list[str]) -> bool:
    """NHN `eventId` 필드 vs `csp_mapping.nhn.event_id_patterns` 매칭.

    카테고리 시드 패턴이 prefix 형태(`event_id.iam.login`, `event_id.cloud_trail.*`)이므로
    와일드카드 끝 `.*` 제거 후 startswith 매칭. 정확 일치도 허용.
    """
    if not event_id or not patterns:
        return False
    eid = event_id.strip()
    for p in patterns:
        p_clean = (p or "").rstrip(".*").rstrip(".").strip()
        if not p_clean:
            continue
        if eid == p_clean or eid.startswith(p_clean + ".") or eid.startswith(p_clean):
            return True
    return False


def _compute_collection_status(
    db: Session,
    case_id: str,
    csp: str,
    categories: list[dict],
) -> tuple[float, dict[str, bool]]:
    """case 의 raw_events 를 스캔해 카테고리별 수집 여부를 산출한다.

    동작:
      1. raw_events.raw_json 에서 NCP `action` / NHN `eventId` 필드 추출
      2. 각 category 의 `csp_mapping[csp]` 패턴과 매칭
      3. (completion_rate, {category_id: collected_bool}) 반환

    completion_rate 분모 정책:
      · REQUIRED 카테고리만 카운트 (GapDetector 와 정합)
      · REQUIRED 가 없으면 전체 카테고리로 fallback
    """
    if not categories:
        return 0.0, {}

    rows = list(
        db.execute(
            select(RawEventModel.raw_json).where(RawEventModel.case_id == case_id)
        ).scalars()
    )
    if not rows:
        return 0.0, {c.get("category_id"): False for c in categories}

    # 관측된 action(NCP) / event_id(NHN) 집합 — 중복 제거로 매칭 비용 절감
    observed_actions: set[str] = set()
    observed_event_ids: set[str] = set()
    for raw_str in rows:
        try:
            r = json.loads(raw_str)
        except Exception:
            continue
        if not isinstance(r, dict):
            continue
        a = r.get("action")
        if isinstance(a, str):
            observed_actions.add(a)
        e = r.get("eventId") or r.get("event_id")
        if isinstance(e, str):
            observed_event_ids.add(e)

    collected_map: dict[str, bool] = {}
    for cat in categories:
        cat_id = cat.get("category_id")
        if not cat_id:
            continue
        csp_map = (cat.get("csp_mapping") or {}).get(csp, {})
        action_patterns = csp_map.get("action_patterns") or []
        event_id_patterns = csp_map.get("event_id_patterns") or []
        matched = False
        # NCP 측 매칭
        if action_patterns and observed_actions:
            for a in observed_actions:
                if _action_matches(a, action_patterns):
                    matched = True
                    break
        # NHN 측 매칭 (case csp 와 무관하게 양쪽 모두 확인 — 환경 보정·통합 시나리오 대비)
        if not matched and event_id_patterns and observed_event_ids:
            for e in observed_event_ids:
                if _event_id_matches(e, event_id_patterns):
                    matched = True
                    break
        collected_map[cat_id] = matched

    # A안 (2026-06-04 사용자 요청) — 완료율 분모 = 화면에 표시되는 전체 항목
    # (REQUIRED + CORROBORATING). "보이는 N개 중 M개 = M/N%" 직관과 1:1 정합.
    # (이전: REQUIRED-only 분모 → 보조 항목이 빠져 4/5 수집이 100%로 표기되던 문제)
    total = len(collected_map)
    collected = sum(1 for v in collected_map.values() if v)
    rate = round(collected / total * 100, 2) if total else 0.0
    return rate, collected_map


# ─────────────────────────────────────────────────────────────
# v1 시드 풍부 메타 로더 (2026-05-23 사이클 6)
# ─────────────────────────────────────────────────────────────
# v1 collection_targets/{csp}_{TYPE}.json 의 풍부 필드 (hint/cmd/layer/
# mitre_techniques 등) 를 V-1 Step 4 가 활용할 수 있도록 응답에 포함.
# v2 categories 와는 별도 데이터 — 사고유형별 구체 수집 방법·CLI 명령 노출용.


def _load_v1_seed_targets(incident_type: str, csp: str) -> list[dict]:
    """v1 collection_targets/{csp}_{incident_type}.json 로딩 (없으면 빈 리스트)."""
    path = settings.DATA_DIR / "collection_targets" / f"{csp}_{incident_type}.json"
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(rows, list):
        return []
    # 응답용 슬림화 — V-1 Step 4 가 표시할 필드만
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        out.append({
            "target_id": r.get("target_id"),
            "log_type": r.get("log_type"),
            "description": r.get("description"),
            "evidence_role": r.get("evidence_role"),
            "priority": r.get("priority"),
            "storage_path": r.get("storage_path"),
            "retention_days": r.get("retention_days"),
            # 사이클 6 풍부화 필드
            "layer": r.get("layer"),
            "hint": r.get("hint"),
            "cmd": r.get("cmd"),
            "auto_collectible": r.get("auto_collectible"),
            "mitre_techniques": r.get("mitre_techniques") or [],
        })
    # priority 내림차순 + evidence_role REQUIRED 우선
    out.sort(key=lambda x: (x.get("evidence_role") != "REQUIRED", -(x.get("priority") or 0)))
    return out


# ─────────────────────────────────────────────────────────────
# Phase L (2026-05-31) — 단서 루프 신호 반영 (동적 우선순위·강조)
# ─────────────────────────────────────────────────────────────
# 가이드는 더 이상 "사고유형 + system_config" 만 보는 정적 매트릭스가 아니라,
# 단서 루프(Evidence Tree)가 확보한 두 가지 신호를 함께 반영한다:
#   1) 확보된 ATT&CK 기법 ID  — (a) 채택 단서 → clue_to_attack 매핑,
#                               (b) 업로드 로그 → attack_events 매핑
#   2) 확보된 Observable        — case.observables (ip/cve/hash/domain/...)
# 기법은 전술(Kill Chain 단계) 로 환산해 해당 단계의 카테고리를 우선순위 부스트하고,
# v1 seed_target 은 기법 ID 교집합으로 강조(clue_relevant)·상단 정렬한다.
# 이 신호는 "수집 항목을 새로 만들지" 않는다 — 표준 기반 정적 카탈로그의 우선순위·강조만
# 바꾼다(AI 가 판단하지 않는다는 원칙 유지). 신호가 없으면 기존 동작과 100% 동일.

_CLUE_PHASE_BOOST = 40  # 단서 연관 단계 카테고리에 더하는 우선순위 가중치


def _accepted_clue_keys(case: IncidentCaseModel) -> list[str]:
    """triage_state.evidence_tree 에서 채택된(루트 제외) 단서 clue_key 목록."""
    ts = case.triage_state or {}
    if not isinstance(ts, dict):
        return []
    et = ts.get("evidence_tree")
    if not isinstance(et, dict):
        return []
    nodes = et.get("nodes") or {}
    root_id = et.get("root_id")
    out: list[str] = []
    for nid, node in nodes.items():
        if not isinstance(node, dict):
            continue
        if nid == root_id or node.get("parent_id") is None:
            continue  # 루트(uniform prior) 는 단서 아님
        ck = node.get("clue_key")
        if ck:
            out.append(ck)
    return out


_TECHNIQUE_ID_RE = re.compile(r"^T\d{4}(?:\.\d{3})?$")


def _clue_techniques(case: IncidentCaseModel) -> set[str]:
    """채택 단서 → ATT&CK 기법 ID 집합.

    두 경로를 합집합:
      1) `TECHNIQUE:T1021` 처럼 단서 키에 기법 ID 가 직접 들어간 경우 (direct_input·log_analysis)
      2) 일반 단서 키 → clue_to_attack 매핑 (`Q2A:abnormal_login` → [T1078.004])
    """
    keys = _accepted_clue_keys(case)
    if not keys:
        return set()
    out: set[str] = set()
    # 1) 키에 박힌 기법 ID 직접 추출
    for k in keys:
        if ":" in k:
            _, _, val = k.partition(":")
            val = val.strip()
            if _TECHNIQUE_ID_RE.match(val):
                out.add(val)
    # 2) clue_to_attack 매핑
    try:
        from core.intake import bayes_net  # lazy — 순환 import·startup 비용 회피

        mappings = bayes_net.load_clue_to_attack().get("mappings", {})
    except Exception:
        mappings = {}
    for k in keys:
        techs = (mappings.get(k) or {}).get("techniques") or []
        for t in techs:
            if t:
                out.add(t)
    return out


def _evidenced_techniques(db: Session, case_id: str) -> tuple[set[str], set[str]]:
    """업로드 로그 → attack_events 매핑된 (기법 ID 집합, 전술 집합).

    attack_events 는 case_id 가 없으므로 ocsf_events → raw_events.case_id 로 조인.
    """
    try:
        rows = db.execute(
            select(AttackEventModel.technique_id, AttackEventModel.tactic)
            .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
            .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
            .where(RawEventModel.case_id == case_id)
        ).all()
    except Exception:
        return set(), set()
    techs: set[str] = set()
    tactics: set[str] = set()
    for tid, tactic in rows:
        if tid:
            techs.add(tid)
        if tactic:
            tactics.add(tactic)
    return techs, tactics


def _techniques_to_tactics(techniques: set[str]) -> set[str]:
    """기법 ID 집합 → 전술명 집합 (rules.json 매핑, 서브/기반기법 폴백)."""
    if not techniques:
        return set()
    tmap = _load_technique_tactic_map()
    out: set[str] = set()
    for t in techniques:
        tactic = tmap.get(t) or tmap.get(t.split(".", 1)[0])
        if tactic:
            out.add(tactic)
    return out


def _normalize_observables(case: IncidentCaseModel) -> list[dict]:
    """case.observables → 슬림 표시용 리스트."""
    obs = case.observables or []
    if not isinstance(obs, list):
        return []
    out: list[dict] = []
    for o in obs:
        if not isinstance(o, dict):
            continue
        val = o.get("value")
        if not val:
            continue
        out.append({
            "type": o.get("type") or "other",
            "value": val,
            "confidence": o.get("confidence"),
            "source": o.get("source"),
        })
    return out


def _collect_clue_signals(db: Session, case: IncidentCaseModel) -> dict:
    """단서 루프 신호를 한 번에 수집해 가이드 빌더에 전달할 dict 로 반환.

    Returns dict:
        clue_techniques     : 채택 단서에서 유래한 기법 ID 집합
        evidenced_techniques: attack_events(업로드 로그) 기법 ID 집합
        signal_techniques   : 위 둘의 합집합
        signal_tactics      : signal_techniques + attack_events.tactic 의 전술 집합
        observables         : 정규화된 observable 리스트
        observable_summary  : [{type, count}] 빈도 요약
        has_signal          : 신호가 하나라도 있으면 True
    """
    clue_techs = _clue_techniques(case)
    evidenced_techs, evidenced_tactics = _evidenced_techniques(db, case.case_id)
    signal_techs = clue_techs | evidenced_techs
    signal_tactics = _techniques_to_tactics(signal_techs) | evidenced_tactics

    observables = _normalize_observables(case)
    type_counts: dict[str, int] = {}
    for o in observables:
        type_counts[o["type"]] = type_counts.get(o["type"], 0) + 1
    observable_summary = [
        {"type": t, "count": c}
        for t, c in sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    has_signal = bool(signal_techs or signal_tactics or observables)
    return {
        "clue_techniques": clue_techs,
        "evidenced_techniques": evidenced_techs,
        "signal_techniques": signal_techs,
        "signal_tactics": signal_tactics,
        "observables": observables,
        "observable_summary": observable_summary,
        "has_signal": has_signal,
    }


def _apply_clue_boost(categories: list[dict], signal_tactics: set[str]) -> set[str]:
    """signal_tactics 와 겹치는 kill_chain_phases 카테고리에 단서 부스트 적용 (in-place).

    Returns: 부스트된 category_id 집합 (UI 강조·정렬용).
    """
    boosted: set[str] = set()
    if not signal_tactics:
        return boosted
    for cat in categories:
        cat_phases = set(cat.get("kill_chain_phases", []))
        if cat_phases & signal_tactics:
            cat["__clue_boost"] = cat.get("__clue_boost", 0) + _CLUE_PHASE_BOOST
            cid = cat.get("category_id")
            if cid:
                boosted.add(cid)
    return boosted


def _annotate_seed_targets(
    seed_targets: list[dict], signal_techniques: set[str]
) -> list[dict]:
    """seed_target.mitre_techniques ∩ signal_techniques → matched_techniques/clue_relevant.

    clue_relevant 인 항목을 (기존 REQUIRED·priority 정렬은 보존한 채) 상단으로 끌어올린다.
    """
    if not seed_targets:
        return seed_targets
    for t in seed_targets:
        techs = t.get("mitre_techniques") or []
        matched = sorted(
            {
                mt
                for mt in techs
                if mt in signal_techniques
                or mt.split(".", 1)[0] in signal_techniques
                or any(s.split(".", 1)[0] == mt for s in signal_techniques)
            }
        )
        t["matched_techniques"] = matched
        t["clue_relevant"] = bool(matched)
    # 단서 연관 우선 → 기존 정렬 키(REQUIRED 우선, priority 내림차순) 보존
    seed_targets.sort(
        key=lambda x: (
            not x.get("clue_relevant", False),
            x.get("evidence_role") != "REQUIRED",
            -(x.get("priority") or 0),
        )
    )
    return seed_targets


# ─────────────────────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────────────────────


class CollectionGuideV2:
    """v2 가이드 생성기 — 외부 표준 6종 기반 매트릭스 + system_config 동적 반영."""

    SOURCE_STANDARDS: list[str] = [
        "Google Cloud Threat Intel — Cloud Log Configurations (인프라 로깅 1.x 분류)",
        "MITRE ATT&CK Cloud Matrix v14 (Kill Chain 12 전술)",
        "KISA 침해사고 분석절차 안내서 (제2010-8호) 2.4 + 3.3",
        "NIST SP 800-86 3.1 (휘발성 계층)",
        "ISO/IEC 27037:2012 (디지털 증거 처리)",
        "CSA Top Threats to Cloud Computing 2024",
    ]

    @classmethod
    def generate(cls, db: Session, case_id: str) -> Optional[dict]:
        """사고 케이스 → v2 가이드 생성 (case.incident_type 사용).

        Returns:
            응답 dict (청사진  5 형식) 또는 case 미존재 시 None.
        """
        case = db.get(IncidentCaseModel, case_id)
        if case is None:
            return None
        return cls._build_guide(db, case, case.incident_type, preview=False)

    @classmethod
    def generate_preview(
        cls, db: Session, case_id: str, incident_type: str
    ) -> Optional[dict]:
        """Phase K (2026-05-26 byungwoo) — preview 가이드.

        V-1 Step 3 트리아주 진행 중 (case.incident_type=UNCLASSIFIED) 에
        상위 가설별 가이드 미리보기. system_config 환경 보정 그대로 적용.

        Args:
            case_id: 케이스 ID — system_config·csp 출처
            incident_type: preview 대상 사고유형 (case.incident_type 무시)

        Returns:
            응답 dict 에 `"preview": True` 마커 추가, 그 외는 generate() 와 동일.
        """
        case = db.get(IncidentCaseModel, case_id)
        if case is None:
            return None
        return cls._build_guide(db, case, incident_type, preview=True)

    @classmethod
    def _build_guide(
        cls,
        db: Session,
        case: IncidentCaseModel,
        incident_type: str,
        *,
        preview: bool,
    ) -> dict:
        """generate / generate_preview 의 공통 빌더 — incident_type 만 분기."""
        case_id = case.case_id
        csp = case.csp
        system_config = case.system_config or {}

        # 1) 사고유형 → Kill Chain 단계
        phases = _lookup_phases(incident_type)

        # 2) phase 에 매칭되는 카테고리 시드
        categories = _categories_for_phases(phases, csp)

        # 3) system_config → modifier 적용
        categories, extra_targets, applied_modifiers = _apply_environment_modifiers(
            categories, system_config
        )

        # 3.5) Phase L — 단서 루프 신호 수집 + 동적 우선순위 부스트
        # 채택 단서·업로드 로그의 ATT&CK 기법 → 전술 환산 → 해당 단계 카테고리 부스트.
        # 신호가 없으면 boosted = ∅ 이라 기존 동작과 동일.
        clue_signals = _collect_clue_signals(db, case)
        clue_boosted_ids = _apply_clue_boost(
            categories, clue_signals["signal_tactics"]
        )

        # 4) Phase G — raw_events 매칭 기반 수집 진행도 산출
        # preview 모드에서도 동일 — 이미 업로드된 로그가 가이드 항목과 매칭되는지
        # 미리 확인 가능 (예: 사고유형 확정 전이라도 "이 가설이면 70% 수집됨")
        completion_rate, collected_map = _compute_collection_status(
            db, case_id, csp, categories
        )

        # 5) phase 별 그룹화 + 정렬 (정렬은 _group_by_phase 내부에서 priority 기준)
        grouped = _group_by_phase(categories, phases, collected_map)

        # 6) 사이클 6 — v1 시드 풍부 메타 (hint/cmd/mitre_techniques) 추가 노출
        #    Phase L — 단서 기법 ID 교집합으로 강조·상단 정렬
        seed_targets = _annotate_seed_targets(
            _load_v1_seed_targets(incident_type, csp),
            clue_signals["signal_techniques"],
        )

        # 7) 응답 조립 — environment_warnings 는 phase 와 분리하여 별도 영역
        return {
            "caseId": case_id,
            "incidentType": incident_type,
            "csp": csp,
            "completionRate": completion_rate,
            "phases": grouped,
            "environment_warnings": _format_env_warnings(extra_targets),
            "applied_modifiers": applied_modifiers,
            "source_standards": cls.SOURCE_STANDARDS,
            # 2026-05-23 사이클 6 — v1 시드 풍부 메타 (V-1 Step 4 가이드 표시용)
            "seed_targets": seed_targets,
            # Phase L (2026-05-31) — 단서 루프 신호 요약 (UI 강조·배지·근거 표시용)
            "clue_signals": {
                "has_signal": clue_signals["has_signal"],
                "clue_techniques": sorted(clue_signals["clue_techniques"]),
                "evidenced_techniques": sorted(clue_signals["evidenced_techniques"]),
                "signal_techniques": sorted(clue_signals["signal_techniques"]),
                "signal_tactics": sorted(clue_signals["signal_tactics"]),
                "boosted_category_ids": sorted(clue_boosted_ids),
                "observables": clue_signals["observables"],
                "observable_summary": clue_signals["observable_summary"],
            },
            "version": "v2",
            # Phase K — 클라이언트가 preview 응답인지 식별 (학술·로그 트레이스용)
            "preview": preview,
        }
