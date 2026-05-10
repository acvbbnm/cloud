import { NavLink } from 'react-router-dom';

const navItems = [
  { path: '/setup', label: 'V-1 사고 접수', icon: '📋' },
  { path: '/logs', label: 'V-2 로그 수집', icon: '📁' },
  { path: '/ocsf', label: 'V-3 OCSF 정규화', icon: '🔄' },
  { path: '/gap', label: 'V-4 갭 감지', icon: '🔍' },
  { path: '/board', label: 'V-5 수사 보드', icon: '🗺️' },
  { path: '/attack', label: 'V-6 ATT&CK', icon: '⚔️' },
  { path: '/report', label: 'V-7 보고서', icon: '📄' },
  { path: '/sherpa', label: 'V-8 AI 셰르파', icon: '🤖' },
];

const Sidebar = () => {
  return (
    <aside className="w-56 bg-gray-800 border-r border-gray-700 flex flex-col">
      {/* 로고 */}
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-lg font-bold text-blue-400">AI Sherpa</h1>
        <p className="text-xs text-gray-400">침해사고 분석 시스템</p>
      </div>

      {/* 네비게이션 */}
      <nav className="flex-1 p-2">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-700'
              }`
            }
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* 하단 정보 */}
      <div className="p-4 border-t border-gray-700 text-xs text-gray-500">
        v0.1.0 · Offline Mode
      </div>
    </aside>
  );
};

export default Sidebar;
