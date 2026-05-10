import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import Sidebar from '@/components/Sidebar';
import SherpaFab from '@/components/SherpaFab';

// ── 뷰 import (구현 완료 시 실제 컴포넌트로 교체) ──
import V1Setup from '@/views/V1_Setup';
import V2Logs from '@/views/V2_Logs';
import V3OCSF from '@/views/V3_OCSF';
import V4Gap from '@/views/V4_Gap';
import V5Board from '@/views/V5_Board';
import V6Attack from '@/views/V6_Attack';
import V7Report from '@/views/V7_Report';
import V8Sherpa from '@/views/V8_Sherpa';

const App = () => {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-900 text-white">
        {/* 좌측 사이드바 */}
        <Sidebar />

        {/* 메인 콘텐츠 */}
        <main className="flex-1 overflow-auto p-6">
          <Routes>
            <Route path="/" element={<Navigate to="/setup" replace />} />
            <Route path="/setup" element={<V1Setup />} />
            <Route path="/logs" element={<V2Logs />} />
            <Route path="/ocsf" element={<V3OCSF />} />
            <Route path="/gap" element={<V4Gap />} />
            <Route path="/board" element={<V5Board />} />
            <Route path="/attack" element={<V6Attack />} />
            <Route path="/report" element={<V7Report />} />
            <Route path="/sherpa" element={<V8Sherpa />} />
          </Routes>
        </main>

        {/* AI 셰르파 플로팅 버튼 */}
        <SherpaFab />
      </div>
    </BrowserRouter>
  );
};

export default App;
