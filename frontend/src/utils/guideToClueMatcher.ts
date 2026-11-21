/**
 * Phase K.4 — 가이드 수집 대상 → 단서 카탈로그 휴리스틱 매핑 (2026-05-26 byungwoo).
 *
 * 사용자 결정 (paradigm doc §19.6 — C 옵션): 휴리스틱 자동 → 부족 시 수동 보강.
 *
 * 입력: GuideV2Target (가이드의 수집 대상 1건)
 * 출력: 매칭되는 clue_catalog 키 0~N개 + 매핑 근거
 *
 * 매핑 룰 (휴리스틱, 우선순위 순):
 *   1. category_id 키워드 → ClueType (IP_ADDRESS / ACCOUNT / SERVICE / TIME_WINDOW
 *      / HASH / DOMAIN)
 *   2. category_name 한국어 키워드 매핑 (보조)
 *   3. 매핑 실패 시 generic clue (e.g., SERVICE:generic)
 *
 * 실패 케이스는 console.warn 으로 로깅 → 수동 매핑 표 보강 후보.
 */
import type { ClueType, GuideV2Target } from '@/types';

/** 가이드 target → 단서 카탈로그 후보 (clue_key + 매핑 근거). */
export interface GuideClueMatch {
  /** clue_catalog.json 키 (예: "IP_ADDRESS:generic"). */
  clue_key: string;
  /** UI 표시용 단서 카테고리. */
  clue_type: ClueType;
  /** 매핑 근거 (rationale 표시용). */
  matched_by: 'category_id' | 'category_name_ko' | 'fallback';
  /** 매칭된 키워드. */
  matched_keyword: string;
}

// ── category_id 키워드 룰 (영문) ──
const ID_RULES: Array<{ pattern: RegExp; clue_type: ClueType; key: string }> = [
  { pattern: /(login|auth|credential|mfa|iam|account|user)/i, clue_type: 'ACCOUNT', key: 'ACCOUNT:generic' },
  { pattern: /(ip|geo|network|firewall|vpn|tor|origin)/i, clue_type: 'IP_ADDRESS', key: 'IP_ADDRESS:generic' },
  { pattern: /(storage|s3|bucket|object|backup|encryption|ransom)/i, clue_type: 'SERVICE', key: 'SERVICE:generic' },
  { pattern: /(audit|cloudtrail|log|trace|api|cloud_logging)/i, clue_type: 'SERVICE', key: 'SERVICE:generic' },
  { pattern: /(time|window|schedule|off_hour|night)/i, clue_type: 'TIME_WINDOW', key: 'TIME_WINDOW:generic' },
  { pattern: /(hash|signature|malware|file|edr|virustotal)/i, clue_type: 'HASH', key: 'HASH:generic' },
  { pattern: /(domain|dns|c2|phishing|url)/i, clue_type: 'DOMAIN', key: 'DOMAIN:generic' },
];

// ── category_name 한국어 키워드 룰 (보조) ──
const KO_RULES: Array<{ pattern: RegExp; clue_type: ClueType; key: string }> = [
  { pattern: /계정|인증|로그인|권한|MFA|IAM/, clue_type: 'ACCOUNT', key: 'ACCOUNT:generic' },
  { pattern: /IP|네트워크|방화벽|VPN|출처|지리/, clue_type: 'IP_ADDRESS', key: 'IP_ADDRESS:generic' },
  { pattern: /스토리지|버킷|객체|백업|암호화|랜섬/, clue_type: 'SERVICE', key: 'SERVICE:generic' },
  { pattern: /감사|로그|trace|API/, clue_type: 'SERVICE', key: 'SERVICE:generic' },
  { pattern: /시각|시간|윈도우|야간|새벽/, clue_type: 'TIME_WINDOW', key: 'TIME_WINDOW:generic' },
  { pattern: /해시|파일|악성|EDR/, clue_type: 'HASH', key: 'HASH:generic' },
  { pattern: /도메인|DNS|C2|피싱|URL/, clue_type: 'DOMAIN', key: 'DOMAIN:generic' },
];

/**
 * 가이드 target 1건 → 단서 매칭 1건 (가장 강한 룰).
 * 매칭 실패 시 null.
 */
export const matchGuideTargetToClue = (
  target: GuideV2Target,
): GuideClueMatch | null => {
  const cid = target.category_id ?? '';
  const cname = target.category_name ?? '';

  // 1) category_id 키워드
  for (const rule of ID_RULES) {
    const m = cid.match(rule.pattern);
    if (m) {
      return {
        clue_key: rule.key,
        clue_type: rule.clue_type,
        matched_by: 'category_id',
        matched_keyword: m[0],
      };
    }
  }

  // 2) category_name 한국어
  for (const rule of KO_RULES) {
    const m = cname.match(rule.pattern);
    if (m) {
      return {
        clue_key: rule.key,
        clue_type: rule.clue_type,
        matched_by: 'category_name_ko',
        matched_keyword: m[0],
      };
    }
  }

  // 3) 실패 — 수동 매핑 보강 후보 (콘솔 로깅으로 향후 분석)
  // (개발 모드에서만 노출 — 운영 시 noop)
  if (typeof import.meta !== 'undefined' && import.meta.env?.DEV) {
    // 시연·개발 단계에서만 fallback 키 노출
    return null;
  }
  return null;
};

/**
 * 가이드의 phases 에서 REQUIRED 우선 → 단서 매칭 → 중복 제거 → 상위 K개 반환.
 *
 * Phase K.4 사용자 결정: "상위 옵션 하나에서 두개 더 제공" — K=2 기본.
 */
export const extractGuideBasedClueCandidates = (
  phases: Record<string, { targets: GuideV2Target[] }>,
  excludeClueKeys: Set<string> = new Set(),
  k: number = 2,
): GuideClueMatch[] => {
  const out: GuideClueMatch[] = [];
  const seenKeys = new Set<string>(excludeClueKeys);

  // REQUIRED 우선 → CORROBORATING 보조
  const required: GuideV2Target[] = [];
  const corroborating: GuideV2Target[] = [];
  for (const phaseId of Object.keys(phases)) {
    const phase = phases[phaseId];
    for (const t of phase.targets ?? []) {
      if (t.evidence_role === 'REQUIRED') required.push(t);
      else corroborating.push(t);
    }
  }

  const ordered = [...required, ...corroborating];
  for (const t of ordered) {
    if (out.length >= k) break;
    const match = matchGuideTargetToClue(t);
    if (!match) continue;
    if (seenKeys.has(match.clue_key)) continue; // 중복 차단
    seenKeys.add(match.clue_key);
    out.push(match);
  }

  return out;
};
