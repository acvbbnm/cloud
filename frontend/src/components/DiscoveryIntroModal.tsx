/**
 * V-1 Step 2 진입 사전 안내 모달 (사용자 결정 #7).
 *
 * 첫 진입 시 단서 6종을 어디서 찾는지 안내. "다시 보지 않기" 체크 시
 * localStorage 영속화하여 두 번째 진입부터 자동 닫힘.
 *
 * 학술 근거: 청사진 §2 Step 2 진입 사전 안내 모달 명세.
 */
import { useState } from 'react';

const STORAGE_KEY = 'ai-sherpa-discovery-intro-hidden';

export const hasDismissedDiscoveryIntro = (): boolean => {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
};

interface DiscoveryIntroModalProps {
  open: boolean;
  onClose: () => void;
}

const DiscoveryIntroModal = ({ open, onClose }: DiscoveryIntroModalProps) => {
  const [dontShowAgain, setDontShowAgain] = useState(false);

  const handleClose = () => {
    if (dontShowAgain) {
      try {
        localStorage.setItem(STORAGE_KEY, '1');
      } catch {
        // localStorage 비활성 환경 무시
      }
    }
    onClose();
  };

  if (!open) return null;

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
             어떤 단서를 입력해야 할까요?
          </h2>
          <button
            onClick={handleClose}
            className="text-ink-500 hover:text-ink-200 text-[20px] leading-none"
          >
            ×
          </button>
        </div>

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
          ℹ <b>표준 흐름</b>: NIST SP 800-61r2 §3.2 Triage + KISA §2.4 초기 대응 점검표 6항목.
          <br />
          단서 → 결정 트리 답변 → 시스템 구성 입력 누적 점수로 사고유형을 추정합니다.
          AI 는 검색·요약·제안만 수행하며 결정은 수사관이 합니다.
        </div>

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
            시작하기 →
          </button>
        </div>
      </div>
    </div>
  );
};

export default DiscoveryIntroModal;
