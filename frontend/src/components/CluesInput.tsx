/**
 * 단서(Observable) 입력 컴포넌트 — V-1 Step 2 Discovery Loop 의 ① 단서.
 *
 * 6종 ClueType 폼:
 *   📡 IP_ADDRESS    — 의심 IP (분석 시 비국내 / 비표준 ASN 여부 가중치)
 *   👤 ACCOUNT       — 사용자명·이메일 (자기상승·동시 다지역 가중치)
 *   🔢 HASH          — SHA-256 (EDR·VirusTotal cross-ref)
 *   🌐 DOMAIN        — C2·DNS exfil 도메인
 *   🕐 TIME_WINDOW   — 사고 인지 시각 ±윈도우
 *   🖥 SERVICE       — 영향받은 클라우드 서비스 (Object Storage·IAM 등)
 *
 * 학술 근거: DFIR-IRIS IOC + NIST 800-61r2 표 3-2 + Velociraptor artifact.
 * 단서 추가 시 useCaseStore.addObservable 호출 → 백엔드 /api/triage/analyze 호출.
 */
import { useState } from 'react';

import Badge from '@/components/Badge';

import type { ClueType, Observable } from '@/types';

interface ClueVariant {
  id: string; // weight_key 의 후미 — 예: 'non_korean'
  label: string; // 한글 라벨
  hint?: string; // 보조 설명
}

interface ClueTypeMeta {
  type: ClueType;
  label: string;
  icon: string;
  placeholder: string;
  hint: string;
  /**
   * Q2 (2026-05-21): variant 토글 — 사용자가 단서 변종을 명시하면 weight_key 부착.
   *   미선택 시 generic fallback (Q1) 적용.
   *   각 variant.id 는 weights.json clue_types 의 `{TYPE}:{id}` 키와 매칭.
   */
  variants: ClueVariant[];
}

const CLUE_TYPES: ClueTypeMeta[] = [
  {
    type: 'IP_ADDRESS',
    label: 'IP 주소',
    icon: '📡',
    placeholder: '203.0.113.7',
    hint: 'CSP 콘솔 보안 알람 / sourceIp 필드',
    variants: [
      { id: 'non_korean', label: '비국내 IP', hint: '국가 코드 ≠ KR' },
      { id: 'tor_vpn', label: 'Tor / VPN exit', hint: '익명화 노드' },
      { id: 'multi_account', label: '다중 계정 사용', hint: '동일 IP·여러 계정' },
      { id: 'multi_csp_observed', label: 'NCP+NHN 양쪽 등장', hint: '멀티 CSP 시그널' },
    ],
  },
  {
    type: 'ACCOUNT',
    label: '계정',
    icon: '👤',
    placeholder: 'attacker@example.com 또는 attack-sim',
    hint: 'IAM 콘솔 활동 보고서 / actionUserName',
    variants: [
      { id: 'privilege_changed', label: '권한 변경 이력', hint: 'AttachPolicy 등' },
      { id: 'newly_created', label: '신규 생성', hint: '24h 내 CreateUser' },
      { id: 'inactive_to_active', label: '비활성→활성', hint: '휴면 계정 재활성' },
      { id: 'root_or_admin', label: 'Root·관리자', hint: '최고권한 계정' },
      { id: 'mfa_disabled', label: 'MFA 미적용', hint: '단일 실패 지점' },
    ],
  },
  {
    type: 'HASH',
    label: '파일 해시',
    icon: '🔢',
    placeholder: 'SHA-256 (64자)',
    hint: 'EDR / VirusTotal 결과',
    variants: [
      { id: 'known_malicious', label: 'VT 매칭', hint: 'VirusTotal 다중 엔진 탐지' },
      { id: 'unknown', label: '신규 미상', hint: '인텔 미발견' },
    ],
  },
  {
    type: 'DOMAIN',
    label: '도메인',
    icon: '🌐',
    placeholder: 'malicious.example.com',
    hint: 'C2 통신 탐지 / DNS exfil',
    variants: [
      { id: 'c2', label: 'C2 도메인', hint: '명령·제어 채널' },
      { id: 'dga', label: 'DGA 패턴', hint: '자동 도메인 생성' },
    ],
  },
  {
    type: 'TIME_WINDOW',
    label: '시각 윈도우',
    icon: '🕐',
    placeholder: '2026-05-18 14:00-15:00',
    hint: '알람 발생 시점 ±5분',
    variants: [
      { id: 'off_hours', label: '비업무 시각', hint: '야간·주말 패턴 (KISA §2.4 ⑤)' },
    ],
  },
  {
    type: 'SERVICE',
    label: '서비스명',
    icon: '🖥',
    placeholder: 'Object Storage / IAM / Server',
    hint: '영향받은 클라우드 서비스',
    variants: [
      { id: 'object_storage', label: 'Object Storage', hint: '데이터 유출·랜섬 표적' },
      { id: 'iam', label: 'IAM', hint: '권한·인증' },
      { id: 'cloud_trail', label: 'CloudTrail·Activity Tracer', hint: '감사 로그 자체' },
      { id: 'multi_csp', label: '다중 CSP', hint: '여러 CSP 서비스' },
    ],
  },
];

const CLUE_META_MAP = Object.fromEntries(
  CLUE_TYPES.map((c) => [c.type, c]),
) as Record<ClueType, ClueTypeMeta>;

interface CluesInputProps {
  observables: Observable[];
  onAdd: (observable: Observable) => void;
  onRemove: (index: number) => void;
  /** 단서 추가 직후 백엔드 /api/triage/analyze 호출 (옵션 — 부모가 처리) */
  onAfterAdd?: (observable: Observable) => void;
  disabled?: boolean;
}

const CluesInput = ({
  observables,
  onAdd,
  onRemove,
  onAfterAdd,
  disabled,
}: CluesInputProps) => {
  const [selectedType, setSelectedType] = useState<ClueType>('IP_ADDRESS');
  const [value, setValue] = useState('');
  const [note, setNote] = useState('');
  // Q2 (2026-05-21): variant 토글 — null 이면 generic fallback (Q1 5점)
  const [selectedVariant, setSelectedVariant] = useState<string | null>(null);

  const handleAdd = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    // Q2: variant 가 선택되어 있으면 weight_key 명시. 미선택 시 백엔드 generic fallback.
    const weightKey = selectedVariant ? `${selectedType}:${selectedVariant}` : null;
    const observable: Observable = {
      type: selectedType,
      value: trimmed,
      note: note.trim() || undefined,
      added_at: new Date().toISOString(),
      weight_key: weightKey,
    };
    onAdd(observable);
    onAfterAdd?.(observable);
    setValue('');
    setNote('');
    setSelectedVariant(null); // 추가 후 variant 리셋
  };

  // ClueType 변경 시 variant 초기화
  const handleTypeChange = (t: ClueType) => {
    setSelectedType(t);
    setSelectedVariant(null);
  };

  const meta = CLUE_META_MAP[selectedType];

  return (
    <div>
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider">
          📌 단서 입력 (Observable)
        </div>
        {observables.length > 0 && (
          <span className="text-[10.5px] text-brand-teal">
            ● {observables.length}개 누적
          </span>
        )}
      </div>

      {/* 타입 선택 — 6종 토글 칩 */}
      <div className="flex flex-wrap gap-1.5 mb-2">
        {CLUE_TYPES.map((c) => {
          const active = selectedType === c.type;
          return (
            <button
              key={c.type}
              onClick={() => handleTypeChange(c.type)}
              disabled={disabled}
              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-medium border transition-all ${
                active
                  ? 'bg-brand-teal/15 border-brand-teal/50 text-brand-teal'
                  : 'bg-ink-900 border-ink-700/70 text-ink-300 hover:border-brand-blue/40 hover:text-white'
              } disabled:opacity-40 disabled:cursor-not-allowed`}
            >
              <span>{c.icon}</span>
              <span>{c.label}</span>
            </button>
          );
        })}
      </div>

      {/* Q2 (2026-05-21): variant 토글 — 분류 명시 시 가중치 +15~35, 미선택 시 +5 generic */}
      {meta.variants.length > 0 && (
        <div className="mb-2">
          <div className="text-[10.5px] text-ink-500 mb-1">
            🏷 변종 분류 <span className="text-ink-600">(선택 — 명시 시 가중치 ↑, 미선택은 약한 fallback 5점)</span>
          </div>
          <div className="flex flex-wrap gap-1">
            <button
              onClick={() => setSelectedVariant(null)}
              disabled={disabled}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10.5px] border transition-all ${
                selectedVariant === null
                  ? 'bg-ink-700 border-ink-600 text-ink-100'
                  : 'bg-ink-900 border-ink-700/70 text-ink-400 hover:text-white'
              } disabled:opacity-40`}
              title="분류 미상 — Q1 generic fallback 5점 부여"
            >
              지정 안 함
            </button>
            {meta.variants.map((v) => {
              const active = selectedVariant === v.id;
              return (
                <button
                  key={v.id}
                  onClick={() => setSelectedVariant(active ? null : v.id)}
                  disabled={disabled}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10.5px] border transition-all ${
                    active
                      ? 'bg-brand-blue/15 border-brand-blue/50 text-brand-blue'
                      : 'bg-ink-900 border-ink-700/70 text-ink-300 hover:border-brand-blue/40 hover:text-white'
                  } disabled:opacity-40`}
                  title={v.hint}
                >
                  {v.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 입력 필드 — 값 + 메모 + [추가] */}
      <div className="flex flex-col gap-1.5">
        <div className="flex gap-2">
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            placeholder={meta.placeholder}
            disabled={disabled}
            className="input flex-1 text-[12px]"
          />
          <button
            onClick={handleAdd}
            disabled={!value.trim() || disabled}
            className="btn-primary btn-sm disabled:opacity-40"
          >
            + 추가
          </button>
        </div>
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="(선택) 메모 — 출처·맥락 등"
          disabled={disabled}
          className="input text-[11px]"
        />
        <p className="text-[10.5px] text-ink-500">💡 {meta.hint}</p>
      </div>

      {/* 누적된 단서 리스트 */}
      {observables.length > 0 ? (
        <div className="mt-3 space-y-1">
          {observables.map((o, i) => {
            const m = CLUE_META_MAP[o.type];
            // Q2: variant 라벨 추출 (weight_key 가 있으면 표시용 칩)
            const variantId = o.weight_key && o.weight_key.startsWith(`${o.type}:`)
              ? o.weight_key.substring(o.type.length + 1)
              : null;
            const variantLabel = variantId
              ? m?.variants.find((v) => v.id === variantId)?.label
              : null;
            return (
              <div
                key={`${o.type}-${i}-${o.value}`}
                className="flex items-start gap-2 bg-ink-900/60 border border-ink-700/70 rounded-lg px-2.5 py-1.5 text-[11.5px]"
              >
                <span className="text-[13px]">{m?.icon ?? '·'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <Badge tone="blue" size="sm">
                      {m?.label ?? o.type}
                    </Badge>
                    {variantLabel && (
                      <Badge tone="purple" size="sm">
                        {variantLabel}
                      </Badge>
                    )}
                    <code className="text-ink-100 font-mono text-[11px] break-all">
                      {o.value}
                    </code>
                  </div>
                  {o.note && (
                    <div className="text-[10.5px] text-ink-400 mt-0.5">
                      {o.note}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => onRemove(i)}
                  disabled={disabled}
                  className="text-ink-500 hover:text-red-400 text-[14px] leading-none px-1 disabled:opacity-40"
                  title="단서 제거"
                >
                  ×
                </button>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="mt-3 text-[10.5px] text-ink-500 leading-5">
          단서를 추가하면 우측 가설 점수에 즉시 반영됩니다.
          <br />
          단서가 없다면 결정 트리만으로 진행해도 됩니다.
        </p>
      )}
    </div>
  );
};

export default CluesInput;
