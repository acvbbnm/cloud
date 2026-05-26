import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import Header from '@/components/Header';
import LogAnalysisFab from '@/components/LogAnalysisFab';
import Sidebar from '@/components/Sidebar';
import SherpaFab from '@/components/SherpaFab';
import Toast from '@/components/Toast';

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
      <div className="h-screen flex flex-col bg-ink-950 text-ink-100 overflow-hidden">
        <Header />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-y-auto bg-ink-950">
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
        </div>
        <SherpaFab />
        <LogAnalysisFab />
        <Toast />
      </div>
    </BrowserRouter>
  );
};

export default App;
