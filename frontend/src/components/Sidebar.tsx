import { NavLink } from 'react-router-dom';

interface NavItem {
  path: string;
  label: string;
  icon: string;
  num: string;
}

const sections: { layer: string; items: NavItem[] }[] = [
  {
    layer: 'Layer 0 — 준비',
    items: [{ path: '/setup', label: '사고 접수', icon: '📋', num: 'V1' }],
  },
  {
    layer: 'Layer 1 — 수집',
    items: [{ path: '/logs', label: '로그 수집', icon: '💾', num: 'V2' }],
  },
  {
    layer: 'Layer 2 — 분석',
    items: [
      { path: '/ocsf', label: 'OCSF 정규화', icon: '🔄', num: 'V3' },
      { path: '/gap', label: '갭 감지', icon: '🔍', num: 'V4' },
      { path: '/attack', label: 'ATT&CK 매핑', icon: '🎯', num: 'V6' },
    ],
  },
  {
    layer: 'Layer 3 — AI 셰르파',
    items: [{ path: '/sherpa', label: 'AI 셰르파', icon: '🤖', num: 'V8' }],
  },
  {
    layer: 'Layer 4 — 보드/보고서',
    items: [
      { path: '/board', label: '수사 보드', icon: '🕸', num: 'V5' },
      { path: '/report', label: '보고서', icon: '📄', num: 'V7' },
    ],
  },
];

const Sidebar = () => {
  return (
    <aside className="w-[244px] shrink-0 bg-ink-900/60 backdrop-blur border-r border-ink-700/70 flex flex-col overflow-y-auto">
      <div className="px-5 py-4 border-b border-ink-700/60">
        <div className="eyebrow text-[10px]">Investigation</div>
        <div className="mt-1 text-[13px] font-bold flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-brand-red animate-pulse" />
          진행 중
        </div>
        <div className="mt-1 text-[11px] text-ink-400">5계층 파이프라인 워크플로</div>
      </div>
      <nav className="flex-1 py-3">
        {sections.map((sec) => (
          <div key={sec.layer} className="mb-2">
            <div className="px-5 pt-2 pb-1.5 text-[10px] uppercase tracking-[0.12em] text-ink-400/70 font-semibold">
              {sec.layer}
            </div>
            {sec.items.map((it) => (
              <NavLink
                key={it.path}
                to={it.path}
                className={({ isActive }) =>
                  `mx-2 flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] transition-all relative ${
                    isActive
                      ? 'bg-brand-blue/10 text-ink-100 font-semibold ring-1 ring-inset ring-brand-blue/30'
                      : 'text-ink-300 hover:text-ink-100 hover:bg-ink-800/60'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full bg-cta-gradient" />
                    )}
                    <span className="w-5 text-center text-[15px]">{it.icon}</span>
                    <span className="flex-1">{it.label}</span>
                    <span className="text-[9px] font-mono text-ink-400">{it.num}</span>
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      <div className="p-4 border-t border-ink-700/60">
        <div className="bg-ink-850 border border-ink-700/70 rounded-xl px-3 py-2.5 flex items-center gap-2.5">
          <span className="w-2 h-2 rounded-full bg-brand-teal" />
          <div className="leading-tight">
            <div className="text-[12px] font-semibold">오프라인 모드</div>
            <div className="text-[10px] text-ink-400">sLLM Llama 3.1 활성</div>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
