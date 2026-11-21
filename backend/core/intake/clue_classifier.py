"""Layer 0 — 단서(Observable) 자동 variant 분류기.

Q3 (2026-05-21): CluesInput 사용자가 variant 토글 안 해도 백엔드가 단서 value
자동 분석 → variant 추정 → weight_key 부착. variant 명시되어 있으면 사용자
선택 우선 (자동 추정 skip).

폐쇄망 호환 — 외부 API 호출 X. 정적 룰 + 정규식만 사용.

지원 자동 탐지:
  - IP_ADDRESS — 사설 IP / Tor·VPN known exit / 로컬 자동 탐지
                  비국내 IP 는 외부 IP DB 의존이라 자동 탐지 제외 (사용자 토글)
  - ACCOUNT    — 'root' / 'admin' / 'administrator' 키워드 → root_or_admin
  - DOMAIN     — DGA 패턴 (랜덤 영숫자 길이) → dga
  - HASH       — SHA-256 형식 검증 / 해시 길이로 type 추정
  - TIME_WINDOW — 비업무 시각 (00:00-07:00, 22:00-24:00) → off_hours
  - SERVICE    — 키워드 매칭 (object storage / iam / cloud trail / activity tracer)

학술 근거: NIST 800-61r2 §3.2 표 3-2 indicator 자동 분류 패턴
          + DFIR-IRIS IOC enrichment 모듈 (오프라인 룰셋 대체)
"""
from __future__ import annotations

import ipaddress
import re
from datetime import datetime
from typing import Optional


# ── IP 분류 룰 ──────────────────────────────────────────────

# Tor·VPN exit node 부분 패턴 (대표 ASN 일부 + 알려진 호스팅 대역)
# 정확한 IP DB 없이 휴리스틱만 — 운영급 IP 인텔로 대체 권장
_TOR_VPN_PREFIXES = (
    "185.220.",  # Tor 다수 exit
    "199.249.",  # Tor 다수 exit
    "23.129.64.",  # Tor 다수
    "185.100.",  # Tor 다수
    "192.42.116.",  # Tor exit
)


def _classify_ip(value: str) -> Optional[str]:
    """IP 주소 자동 variant 분류.

    Returns:
        'tor_vpn' / None (사설 IP 또는 미상)
        비국내 IP 는 GeoIP DB 의존이라 자동 분류 제외 — 사용자 명시(Q2) 권장.
    """
    try:
        ip = ipaddress.ip_address(value.strip())
    except ValueError:
        return None

    # 사설·내부 IP — 단서로 부적합. 가중치 없음.
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        return None

    # Tor·VPN known prefix 매칭
    for prefix in _TOR_VPN_PREFIXES:
        if value.startswith(prefix):
            return "tor_vpn"

    # 그 외 공인 IP — 비국내 여부는 GeoIP DB 필요 (오프라인 미지원)
    return None


# ── ACCOUNT 분류 룰 ─────────────────────────────────────────

_ADMIN_KEYWORDS = ("root", "admin", "administrator", "superuser", "sudo")


def _classify_account(value: str) -> Optional[str]:
    """계정명 자동 variant 분류.

    Returns:
        'root_or_admin' — 'root', 'admin', 'administrator' 등 포함 시
        None — 일반 사용자명
    """
    lower = value.strip().lower()
    for kw in _ADMIN_KEYWORDS:
        # 단어 경계 또는 @ 앞부분 매칭 (예: 'admin@', 'root.', 'adminuser')
        if (
            lower == kw
            or lower.startswith(kw + "@")
            or lower.startswith(kw + ".")
            or lower.startswith(kw + "-")
            or lower.startswith(kw + "_")
            or lower.endswith("@" + kw + ".com")
        ):
            return "root_or_admin"
    return None


# ── DOMAIN 분류 룰 ──────────────────────────────────────────

_DGA_LABEL_RE = re.compile(r"^[a-z0-9]{12,}$")


def _classify_domain(value: str) -> Optional[str]:
    """도메인 자동 variant 분류.

    DGA 탐지 휴리스틱:
      - SLD(2nd-level) 라벨 길이 12+ AND
      - 라벨 내 모음 비율 < 30% (랜덤 문자열 추정)

    Returns:
        'dga' — DGA 패턴 의심
        None — 정상 도메인 또는 미상 (C2 는 외부 인텔 필요 — 사용자 명시 권장)
    """
    parts = value.strip().lower().split(".")
    if len(parts) < 2:
        return None
    sld = parts[-2] if len(parts) >= 2 else ""
    if not _DGA_LABEL_RE.match(sld):
        return None
    # 모음 비율
    vowels = sum(1 for c in sld if c in "aeiouy")
    if vowels / len(sld) < 0.3:
        return "dga"
    return None


# ── HASH 분류 룰 ────────────────────────────────────────────

_HASH_LEN_MAP = {32: "md5", 40: "sha1", 64: "sha256"}


def _classify_hash(value: str) -> Optional[str]:
    """해시 값 형식 검증만 (variant 분류는 외부 인텔 필요 — 사용자 명시)."""
    v = value.strip().lower()
    if not re.fullmatch(r"[a-f0-9]+", v):
        return None
    if len(v) in _HASH_LEN_MAP:
        # 형식은 유효하지만 known_malicious 판정은 외부 DB 필요 → fallback
        return None
    return None


# ── TIME_WINDOW 분류 룰 ─────────────────────────────────────

_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")


def _classify_time(value: str) -> Optional[str]:
    """시각 윈도우 자동 variant 분류.

    비업무 시각 — 22:00-24:00 또는 00:00-07:00 의 hour 포함 시 'off_hours'.

    Returns:
        'off_hours' — 비업무 시각 패턴 (KISA §2.4 ⑤)
        None — 업무 시각
    """
    hours = [int(m.group(1)) for m in _TIME_RE.finditer(value)]
    if not hours:
        return None
    for h in hours:
        if h >= 22 or h < 7:
            return "off_hours"
    return None


# ── SERVICE 분류 룰 ─────────────────────────────────────────

_SERVICE_KEYWORDS = (
    ("object_storage", ("object storage", "objectstorage", "s3", "blob")),
    ("iam", ("iam", "identity", "sub account", "subaccount")),
    ("cloud_trail", ("cloud trail", "cloudtrail", "activity tracer", "audit log")),
    ("multi_csp", ("multi csp", "multi-csp", "multicsp")),
)


def _classify_service(value: str) -> Optional[str]:
    """서비스명 자동 variant 분류 — 키워드 매칭."""
    lower = value.strip().lower()
    for variant, keywords in _SERVICE_KEYWORDS:
        for kw in keywords:
            if kw in lower:
                return variant
    return None


# ── 통합 dispatch ───────────────────────────────────────────


_CLASSIFIERS = {
    "IP_ADDRESS": _classify_ip,
    "ACCOUNT": _classify_account,
    "DOMAIN": _classify_domain,
    "HASH": _classify_hash,
    "TIME_WINDOW": _classify_time,
    "SERVICE": _classify_service,
}


def classify_clue(clue: dict) -> Optional[str]:
    """단서 자동 variant 분류 (Q3 핵심 함수).

    Args:
        clue: Observable dict — {type, value, weight_key?, ...}

    Returns:
        variant id (예: 'root_or_admin', 'tor_vpn') 또는 None.
        None 인 경우 호출자가 generic fallback (Q1) 적용.

    동작:
      - clue.weight_key 가 이미 설정되어 있으면 자동 분류 skip (사용자 명시 우선).
      - type 별 classifier 함수 호출 → variant 반환.
    """
    if clue.get("weight_key"):
        # 사용자가 이미 명시 — 자동 분류 skip
        return None
    ctype = clue.get("type")
    value = clue.get("value", "")
    if not ctype or not value:
        return None
    classifier = _CLASSIFIERS.get(ctype)
    if classifier is None:
        return None
    return classifier(value)


def enrich_clue(clue: dict) -> dict:
    """단서에 자동 분류된 variant 적용 — Triage.analyze 진입 직전 호출.

    Returns:
        enriched clue dict (weight_key 가 추가됨, 사본).
    """
    if clue.get("weight_key"):
        return dict(clue)
    variant = classify_clue(clue)
    out = dict(clue)
    if variant:
        out["weight_key"] = f"{clue['type']}:{variant}"
        out["_auto_classified"] = True  # 트레이스 — UI 에서 "자동 분류" 배지 표시 가능
    return out
