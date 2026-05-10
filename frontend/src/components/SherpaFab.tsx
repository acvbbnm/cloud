import { useState } from 'react';

/**
 * AI 셰르파 플로팅 액션 버튼.
 * 클릭 시 채팅 패널 슬라이드 (Phase 3에서 구현).
 */
const SherpaFab = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* FAB 버튼 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-purple-600 hover:bg-purple-500 rounded-full shadow-lg flex items-center justify-center text-2xl transition-transform hover:scale-110 z-50"
        title="AI 셰르파"
      >
        🤖
      </button>

      {/* 채팅 패널 (Phase 3에서 구현) */}
      {isOpen && (
        <div className="fixed bottom-24 right-6 w-96 h-[500px] bg-gray-800 border border-gray-600 rounded-xl shadow-2xl z-40 flex flex-col">
          <div className="p-4 border-b border-gray-700 flex justify-between items-center">
            <h3 className="font-bold text-purple-400">AI 셰르파</h3>
            <button
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-white"
            >
              ✕
            </button>
          </div>
          <div className="flex-1 p-4 flex items-center justify-center text-gray-500 text-sm">
            Phase 3에서 구현 예정
          </div>
        </div>
      )}
    </>
  );
};

export default SherpaFab;
