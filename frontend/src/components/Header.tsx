/**
 * 단말기 상단 바 — 미니멀 (2026-05-22 재개정).
 * 워드마크 + 오프라인·시각만. CSP 토글·CASE 표시 제거 (V-1 내부에서 설정).
 */
import { useEffect, useState } from 'react';

const Header = () => {
  const [ts, setTs] = useState(() => {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  });

  useEffect(() => {
    const id = window.setInterval(() => {
      const d = new Date();
      setTs(`${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`);
    }, 30_000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <header className="h-9 bg-ink-975 border-b border-ink-700 flex items-stretch shrink-0 z-20 font-mono text-[11px]">
      <div className="px-3 flex items-center border-r border-ink-700">
        <span className="text-brand-amber font-bold tracking-[0.18em]">AI · SHERPA</span>
      </div>
      <div className="ml-auto flex items-stretch">
        <div className="px-3 flex items-center gap-1.5 border-l border-ink-700">
          <span className="w-1.5 h-1.5 bg-brand-teal" />
          <span className="text-ink-400 uppercase tracking-[0.12em]">OFFLINE</span>
        </div>
        <div className="px-3 flex items-center text-ink-300 border-l border-ink-700">{ts}</div>
      </div>
    </header>
  );
};

export default Header;
