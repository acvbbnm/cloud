/**
 * V-1 Step 3 진입 사전 안내 모달.
 *
 * 첫 진입 시 단서·수사 방식을 안내. "다시 보지 않기" 체크 시
 * localStorage 영속화하여 두 번째 진입부터 자동 닫힘.
 *
 * Phase G (2026-05-25, byungwoo) — evidence_tree 모드용 "어두운 맵 밝히기"
 * 안내 분기 추가. scoringMode 별 다른 콘텐츠 노출.
 *
 * 학술 근거:
 *   - additive·bayesian: 청사진 §2 Step 2 진입 사전 안내 모달 명세
 *   - evidence_tree: docs/evidence_tree_paradigm.md §1·§4·§16 (사용자 비전)
 */
import { useState } from 'react';

const STORAGE_KEY = 'ai-sherpa-discovery-intro-hidden';
const STORAGE_KEY_EVIDENCE = 'ai-sherpa-discovery-intro-evidence-hidden';

export const hasDismissedDiscoveryIntro = (
  mode: 'additive' | 'bayesian' | 'evidence_tree' = 'additive',
): boolean => {
  try {
    const key = mode === 'evidence_tree' ? STORAGE_KEY_EVIDENCE : STORAGE_KEY;
    return localStorage.getItem(key) === '1';
  } catch {
    return false;
  }
};

interface DiscoveryIntroModalProps {
  open: boolean;
  onClose: () => void;
  /** 현재 백엔드 scoring 모드 — 안내 콘텐츠 분기 (Phase G). */
  mode?: 'additive' | 'bayesian' | 'evidence_tree';
}

const DiscoveryIntroModal = ({
  open,
  onClose,
  mode = 'additive',
}: DiscoveryIntroModalProps) => {
  const [dontShowAgain, setDontShowAgain] = useState(false);

  const handleClose = () => {
    if (dontShowAgain) {
      try {
        const key = mode === 'evidence_tree' ? STORAGE_KEY_EVIDENCE : STORAGE_KEY;
        localStorage.setItem(key, '1');
      } catch {
        // localStorage 비활성 환경 무시
      }
    }
    onClose();
  };

  if (!open) return null;

  const isEvidence = mode === 'evidence_tree';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/80 backdrop-blur-sm p-4 animate-fade-up"
      onClick={handleClose}
    >
      <div
        className="bg-ink-900 border border-ink-700/70 rounded-2xl max-w-2xl w-full p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[16px] font-bold text-ink-100">
            {isEvidence
              ? '🔦 어두운 맵을 단서로 밝혀가는 수사'
              : '어떤 단서를 입력해야 할까요?'}
          </h2>
          <button
            onClick={handleClose}
            className="text-ink-500 hover:text-ink-200 text-[20px] leading-none"
          >
            ×
          </button>
        </div>

        {isEvidence ? (
          // ── Evidence Tree 패러다임 안내 (Phase G) ──
          <>
            <p className="text-[12.5px] text-ink-300 leading-6 mb-4">
              이번 분석은 <b>Evidence Tree (단서 기반 동적 결정 트리)</b> 모드입니다.
              게임 속 어두운 맵을 횃불로 밝혀가듯, <b>단서 하나</b>를 시작으로 가능성의
              트리가 자라납니다.
            </p>

            <div className="bg-ink-950/60 border border-amber-700/30 rounded-lg px-4 py-3 mb-4">
              <div className="text-[12px] text-amber-200 font-semibold mb-2">
                🗺 진행 흐름
              </div>
              <ol className="space-y-1.5 text-[11.5px] text-ink-300 leading-5 list-decimal list-inside">
                <li>
                  <b>처음 — Uniform 1/8</b> (모든 사고유형 동일 확률). 후보 표시 X.
                </li>
                <li>
                  <b>첫 단서 입력</b> — 좌측{' '}
                  <span className="text-brand-teal">단서 직접 입력</span> 또는{' '}
                  <span className="text-brand-teal">부분 로그 분석</span> 으로 시작.
                </li>
                <li>
                  <b>가능성 트리</b> — 사후확률이 기울면서 변별력 높은 다음 단서 후보 등장
                  (Information Gain 정렬).
                </li>
                <li>
                  <b>꼬리에 꼬리</b> — 후보 클릭 또는 직접 입력으로 트리 깊이 자라기.
                </li>
                <li>
                  <b>사고유형 확정 가능</b> — 1위 확률 ≥65% + 격차 ≥20%p 도달 시
                  알림 카드 노출 (자동 종료 X, 사용자가 [확정] 클릭).
                </li>
              </ol>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-4">
              <div className="bg-ink-950 border border-ink-700/60 rounded-lg px-3 py-2">
                <div className="text-[11px] font-semibold text-ink-100 mb-1">
                  📍 단서 후보 시각화
                </div>
                <div className="text-[10.5px] text-ink-400 leading-4">
                  현재 leaf 의 점선 회색 후보 — 클릭하면 채택<br />
                  선택된 후보는 실선 초록으로 다음 단계 anchor
                </div>
              </div>
              <div className="bg-ink-950 border border-ink-700/60 rounded-lg px-3 py-2">
                <div className="text-[11px] font-semibold text-ink-100 mb-1">
                  ⚖ Information Gain
                </div>
                <div className="text-[10.5px] text-ink-400 leading-4">
                  Shannon entropy + Pearl marginalization<br />
                  변별력 큰 단서가 상단에 표시 (IG 막대)
                </div>
              </div>
              <div className="bg-ink-950 border border-ink-700/60 rounded-lg px-3 py-2">
                <div className="text-[11px] font-semibold text-ink-100 mb-1">
                  🎯 동적 후보 개수
                </div>
                <div className="text-[10.5px] text-ink-400 leading-4">
                  entropy 따라 5/3/2 개 동적 노출<br />
                  (모호할수록 많이, 수렴할수록 적게)
                </div>
              </div>
              <div className="bg-ink-950 border border-ink-700/60 rounded-lg px-3 py-2">
                <div className="text-[11px] font-semibold text-ink-100 mb-1">
                  🔁 트리 초기화
                </div>
                <div className="text-[10.5px] text-ink-400 leading-4">
                  잘못된 단서 시퀀스로 시작했다면<br />
                  헤더의 [⟲ 초기화] 로 cold-start 재시작
                </div>
              </div>
            </div>

            <div className="bg-ink-950/60 border border-ink-700/40 rounded-lg px-3 py-2 mb-4 text-[10.5px] text-ink-400 leading-5">
              <b className="text-ink-200">학술 근거</b>: Jaynes 1968 Max Entropy ·
              Pearl 1988 Bayesian Belief Propagation · Shannon 1948 Information Gain ·
              MITRE ATT&CK · Verizon DBIR. 결정성 100% (같은 단서 시퀀스 → 같은
              사후확률). AI 는 검색·요약·제안만, 결정은 수사관.
            </div>
          </>
        ) : (
          // ── Legacy additive/bayesian 안내 (기존 6종 단서 카탈로그) ──
          <>
            <p className="text-[12.5px] text-ink-300 leading-6 mb-4">
              <b>단서(Observable)</b> 는 사고를 처음 인지한 시점의 의심 정보입니다.
              아래 6종 중 가능한 것부터 입력하세요. 단서가 없으면 결정 트리만으로 진행해도 됩니다.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-4">
              {[
                { icon: '', label: 'IP 주소', source: 'CSP 콘솔 → 보안 알람 → 출처 IP' },
                { icon: '', label: '계정 (Account)', source: 'IAM 콘솔 → 활동 보고서' },
                { icon: '', label: '해시 (Hash)', source: 'EDR · VirusTotal 결과' },
                { icon: '', label: '도메인', source: 'C2 통신 탐지 / DNS exfil' },
                { icon: '', label: '시각 윈도우', source: '알람 발생 시점 ±5분' },
                { icon: '', label: '서비스명', source: '영향받은 클라우드 서비스' },
              ].map((c) => (
                <div
                  key={c.label}
                  className="bg-ink-950 border border-ink-700/60 rounded-lg px-3 py-2"
                >
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className="text-[14px]">{c.icon}</span>
                    <span className="text-[12px] font-semibold text-ink-100">
                      {c.label}
                    </span>
                  </div>
                  <div className="text-[10.5px] text-ink-400">→ {c.source}</div>
                </div>
              ))}
            </div>

            <div className="bg-ink-950/60 border border-ink-700/40 rounded-lg px-3 py-2 mb-4 text-[11px] text-ink-300 leading-5">
              ℹ <b>진행 방식</b>: 단서 → 결정 트리 답변 → 시스템 구성 입력의 누적 점수로
              사고유형을 추정합니다. AI 는 검색·요약·제안만 수행하며 결정은 수사관이 합니다.
            </div>
          </>
        )}

        <div className="flex items-center justify-between gap-3">
          <label className="flex items-center gap-1.5 text-[11px] text-ink-300 cursor-pointer">
            <input
              type="checkbox"
              checked={dontShowAgain}
              onChange={(e) => setDontShowAgain(e.target.checked)}
              className="accent-brand-teal"
            />
            다음부터 보지 않기
          </label>
          <button onClick={handleClose} className="btn-primary btn-sm">
            {isEvidence ? '첫 단서 입력하러 가기 →' : '시작하기 →'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DiscoveryIntroModal;
