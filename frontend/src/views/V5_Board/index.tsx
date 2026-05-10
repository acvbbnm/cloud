import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import PageHeader from '@/components/PageHeader';
import Card from '@/components/Card';
import Badge from '@/components/Badge';
import { useToastStore } from '@/stores/useToastStore';
import { useBoardStore } from '@/stores/useBoardStore';
import type { BoardLog } from '@/stores/useBoardStore';

import LogPanel from './LogPanel';
import BoardCanvas from './BoardCanvas';

interface ChainNodeMeta {
  n: string;
  t: string;
  id: string;
  tm: string;
  ip: string;
  d: string;
}

const nodeMeta: ChainNodeMeta[] = [
  { n: 'consoleSignIn', t: 'Initial Access', id: 'T1078', tm: '02:34:18', ip: '203.0.113.45', d: '해외 IP 심야 비인가 로그인' },
  { n: 'addSubAccountRole', t: 'Persistence', id: 'T1098', tm: '14:33:15', ip: '203.0.113.45', d: 'Sub Account 관리자 역할 추가' },
  { n: 'getObject x142', t: 'Collection', id: 'T1530', tm: '14:38:55', ip: '203.0.113.45', d: 'Object Storage 2.3GB 대량 다운로드' },
  { n: 'putBucketPolicy', t: 'Exfiltration', id: 'T1537', tm: '14:35:42', ip: '203.0.113.45', d: '버킷 정책 변경 외부 접근 허용' },
  { n: 'deleteAccessKey (추정)', t: 'Defense Evasion', id: 'T1070.008', tm: '~14:34', ip: '—', d: 'AI 제안: 접근 키 삭제 흔적 제거' },
];

const V5Board = () => {
  const navigate = useNavigate();
  const showToast = useToastStore((s) => s.show);
  const cards = useBoardStore((s) => s.cards);

  const [pendingLog, setPendingLog] = useState<BoardLog | null>(null);
  const [activeNode, setActiveNode] = useState<ChainNodeMeta | null>(null);
  const [memo, setMemo] = useState('');

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        eyebrow="Layer 3 · M3-1"
        title="수사 보드"
        description="수집된 로그를 드래그해 캔버스에 배치하고, 추천 공격 체인 노드를 검토해 사고 흐름을 재구성합니다."
        actions={
          <>
            <button onClick={() => navigate('/gap')} className="btn-ghost">
              ← 갭 감지
            </button>
            <button
              onClick={() => {
                showToast('→ ATT&CK 매핑 진행');
                navigate('/attack');
              }}
              className="btn-primary"
            >
              ATT&CK 매핑 →
            </button>
          </>
        }
      />

      <div className="max-w-[1280px] mx-auto w-full px-8 lg:px-12 py-6 flex gap-4 flex-1 overflow-hidden min-h-0 animate-fade-up">
        <div className="flex-1 min-w-0 flex flex-col gap-3">
          <BoardCanvas pendingLog={pendingLog} clearPendingLog={() => setPendingLog(null)} />
          <Card title={<>🎯 추천 공격 체인 노드</>} className="flex-shrink-0">
            <div className="flex flex-wrap gap-2">
              {nodeMeta.map((n) => {
                const sel = activeNode?.id === n.id;
                return (
                  <button
                    key={n.id + n.tm}
                    onClick={() => setActiveNode(n)}
                    className={`bg-ink-900/60 border rounded-xl px-3 py-2 text-[12px] flex flex-col gap-0.5 transition-all hover:border-brand-blue/50 ${
                      sel ? 'border-brand-blue/60 ring-1 ring-brand-blue/40 shadow-glow' : 'border-ink-700/70'
                    }`}
                  >
                    <span className="font-semibold">{n.n}</span>
                    <span className="text-ink-400 text-[10.5px]">
                      {n.tm} · <span className="text-brand-purple">{n.id}</span>
                    </span>
                  </button>
                );
              })}
            </div>
            {cards.length > 0 && (
              <p className="mt-3 text-[12px] text-ink-400">
                현재 보드에 <b className="text-brand-blue">{cards.length}</b>개 로그 카드가 배치되어 있습니다. 노드 카드를 클릭해 상세 정보를 우측에서 확인하세요.
              </p>
            )}
          </Card>
        </div>

        <div className="w-[300px] shrink-0 flex flex-col gap-3 overflow-y-auto pr-1">
          <Card title={<>ℹ️ 노드 상세</>}>
            {activeNode ? (
              <div className="text-[12.5px]">
                <div className="font-bold text-[14px] mb-2">{activeNode.n}</div>
                <Row label="전술">{activeNode.t}</Row>
                <Row label="기법">
                  <Badge tone="purple">{activeNode.id}</Badge>
                </Row>
                <Row label="시각">
                  <span className="font-mono">{activeNode.tm}</span>
                </Row>
                <Row label="Source IP">
                  <span className="text-brand-red font-mono">{activeNode.ip}</span>
                </Row>
                <p className="py-2 text-ink-300 text-[11.5px] leading-6">{activeNode.d}</p>
              </div>
            ) : (
              <div className="text-[12px] text-ink-400">공격 체인 노드를 클릭하세요</div>
            )}
          </Card>

          <Card title={<span className="text-brand-purple">🧠 AI 셰르파 브리핑</span>}>
            <div className="bg-ink-950 border border-ink-700/70 rounded-xl p-3 text-[12px] leading-7 text-ink-200">
              <b className="text-brand-teal">컨텍스트 브리핑</b>
              <p className="mt-1">T1078 → T1098 전이는 클라우드 권한 탈취 공격의 전형적 패턴입니다.</p>
              <b className="block mt-3 text-brand-amber">빠진 고리 힌트</b>
              <p className="mt-1">14:32~14:35 사이 deleteAccessKey 호출 가능성 높음 (T1070.008).</p>
              <p className="mt-3 text-[10px] text-ink-400">출처: ATT&CK Cloud v14 / NCP 매핑 테이블</p>
            </div>
          </Card>

          <Card title={<>📝 수사관 메모</>}>
            <textarea
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              placeholder="메모 입력..."
              rows={3}
              className="input resize-y min-h-[72px]"
            />
          </Card>

          <LogPanel onDragStart={setPendingLog} />
        </div>
      </div>
    </div>
  );
};

const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div className="flex justify-between items-center py-1.5 border-b border-ink-700/30">
    <span className="text-ink-400">{label}</span>
    <span>{children}</span>
  </div>
);

export default V5Board;
