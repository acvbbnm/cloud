import { useCaseStore } from '@/stores/useCaseStore';
import { useToastStore } from '@/stores/useToastStore';

const cspTabs = [
  { id: 'naver', label: 'Naver Cloud' },
  { id: 'nhn', label: 'NHN Cloud' },
  { id: 'all', label: '통합 뷰' },
];

const Header = () => {
  const csp = useCaseStore((s) => s.csp);
  const setCsp = useCaseStore((s) => s.setCsp);
  const caseId = useCaseStore((s) => s.caseId);
  const showToast = useToastStore((s) => s.show);

  const handleSwitch = (id: string) => {
    setCsp(id);
    const meta = cspTabs.find((c) => c.id === id);
    showToast(`CSP 전환: ${meta?.label ?? id}`);
  };

  return (
    <header className="h-14 bg-ink-900/80 backdrop-blur border-b border-ink-700/70 flex items-center justify-between px-6 shrink-0 z-20">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2.5">
          <span className="w-7 h-7 rounded-lg bg-sherpa-gradient flex items-center justify-center text-[14px] shadow-glow">
            🛡
          </span>
          <div className="leading-tight">
            <b className="text-[15px] tracking-tight">AI 셰르파</b>
            <span className="text-[10px] text-ink-400 ml-2">v3.1</span>
          </div>
        </div>
        <div className="hidden md:flex items-center gap-1 p-1 bg-ink-850 border border-ink-700/70 rounded-full">
          {cspTabs.map((tab) => {
            const active = csp === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => handleSwitch(tab.id)}
                className={`text-[12px] px-3.5 py-1.5 rounded-full transition-all ${
                  active
                    ? 'bg-cta-gradient text-white shadow-soft'
                    : 'text-ink-300 hover:text-ink-100'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>
      <div className="flex items-center gap-4">
        <span className="hidden sm:inline-flex chip">
          <span className="w-1.5 h-1.5 rounded-full bg-brand-teal" />
          {caseId ? caseId : 'CASE-NEW'}
        </span>
        <div className="w-8 h-8 rounded-full bg-ink-800 border border-ink-700 flex items-center justify-center text-[13px]">
          👤
        </div>
      </div>
    </header>
  );
};

export default Header;
