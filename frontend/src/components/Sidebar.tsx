/**
 * 단말기 사이드바 — 2026-05-22 블룸버그 스타일 + 4그룹 접이식 (재개정).
 *
 * 그룹: INTAKE / 로그분석 / REPORT / AI
 *   각 그룹 클릭 → 하위 메뉴 토글 표시.
 *   현재 라우트가 속한 그룹은 자동 펼침.
 *   레이어 코드(L0/L1/...) · V-번호(V1/V2/...) 표기 제거 — 미니멀.
 */
import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

interface NavItem {
  path: string;
  label: string;
}

interface NavGroup {
  key: string;
  label: string;
  items: NavItem[];
}

const groups: NavGroup[] = [
  {
    key: 'intake',
    label: 'INTAKE',
    items: [{ path: '/setup', label: 'NEW CASE' }],
  },
  {
    key: 'logs',
    label: 'LOG ANALYSIS',
    items: [
      { path: '/logs',   label: 'COLLECT' },
      { path: '/ocsf',   label: 'NORMALIZE' },
      { path: '/gap',    label: 'GAP DETECT' },
    ],
  },
  {
    key: 'report',
    label: 'REPORT',
    items: [
      { path: '/board',  label: 'BOARD' },
      { path: '/attack', label: 'ATT&CK' },
      { path: '/report', label: 'REPORT' },
    ],
  },
  {
    key: 'ai',
    label: 'AI',
    items: [{ path: '/sherpa', label: 'SHERPA' }],
  },
];

const Sidebar = () => {
  const { pathname } = useLocation();

  // 현재 라우트가 속한 그룹을 기본 펼침. 그 외는 접힘.
  // 단, INTAKE 는 메인 진입이라 항상 기본 펼침으로 시작.
  const initialOpen = (): Record<string, boolean> => {
    const out: Record<string, boolean> = { intake: true };
    for (const g of groups) {
      if (g.items.some((i) => pathname.startsWith(i.path))) {
        out[g.key] = true;
      }
    }
    return out;
  };

  const [open, setOpen] = useState<Record<string, boolean>>(initialOpen);

  const toggle = (key: string) =>
    setOpen((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <aside className="w-[180px] shrink-0 bg-ink-950 border-r border-ink-700 flex flex-col overflow-y-auto font-mono text-[11px]">
      {groups.map((g) => {
        const isOpen = !!open[g.key];
        const hasActive = g.items.some((i) => pathname.startsWith(i.path));
        return (
          <div key={g.key} className="border-b border-ink-700">
            <button
              onClick={() => toggle(g.key)}
              className={`w-full flex items-center justify-between px-3 py-2 uppercase tracking-[0.16em] transition-colors ${
                hasActive
                  ? 'bg-ink-900 text-brand-amber'
                  : 'bg-ink-900 text-ink-300 hover:text-brand-amber'
              }`}
            >
              <span className="font-bold">{g.label}</span>
              <span className="text-ink-500 text-[10px]">{isOpen ? '−' : '+'}</span>
            </button>
            {isOpen &&
              g.items.map((it) => (
                <NavLink
                  key={it.path}
                  to={it.path}
                  className={({ isActive }) =>
                    `block px-3 py-1.5 transition-colors ${
                      isActive
                        ? 'bg-brand-amber/10 text-ink-50 border-l-2 border-brand-amber'
                        : 'text-ink-300 hover:bg-ink-850 hover:text-ink-100 border-l-2 border-transparent'
                    }`
                  }
                >
                  {it.label}
                </NavLink>
              ))}
          </div>
        );
      })}
      <div className="mt-auto px-3 py-2 text-[10px] text-ink-500 uppercase tracking-[0.12em] border-t border-ink-700">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 bg-brand-teal" />
          sLLM · LLAMA 3.1
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
