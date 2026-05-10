import { useNavigate } from 'react-router-dom';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import Card from '@/components/Card';
import Badge from '@/components/Badge';
import { useToastStore } from '@/stores/useToastStore';

import CompletenessKpi from './CompletenessKpi';
import EvidenceItemList from './EvidenceItemList';
import type { EvidenceItem } from './EvidenceItemList';

const evidence: EvidenceItem[] = [
  { name: 'Activity Tracer', role: 'REQUIRED', collected: true, techniques: ['T1078', 'T1098'] },
  { name: 'Sub Account 변경 이력', role: 'REQUIRED', collected: true, techniques: ['T1098', 'T1136'] },
  { name: 'Object Storage 로그', role: 'REQUIRED', collected: true, techniques: ['T1530', 'T1537'] },
  { name: 'VPC Flow Log', role: 'REQUIRED', collected: false, techniques: ['T1071'] },
  { name: '로그인 기록', role: 'CORROBORATING', collected: true, techniques: ['T1078'] },
  { name: 'Cloud Advisor', role: 'CORROBORATING', collected: false, techniques: ['T1562'] },
];

const V4Gap = () => {
  const navigate = useNavigate();
  const showToast = useToastStore((s) => s.show);

  const requiredMissing = evidence.filter((e) => e.role === 'REQUIRED' && !e.collected);
  const corMissing = evidence.filter((e) => e.role === 'CORROBORATING' && !e.collected);
  const totalCovered = evidence.filter((e) => e.collected).length;
  const rate = Math.round((totalCovered / evidence.length) * 100);

  return (
    <div>
      <PageHeader
        eyebrow="Layer 2 · M2-2"
        title="갭 감지"
        description="OCSF 정규화 결과를 기반으로 증거 역할 기준 필수 증거 누락 여부를 판정합니다."
        actions={
          <>
            <button
              onClick={() => {
                showToast('Layer 0 복귀: VPC Flow Log 수집 필요');
                navigate('/setup');
              }}
              className="btn-ghost"
            >
              ↩ Layer 0 복귀
            </button>
            <button
              onClick={() => {
                showToast('갭 인지 후 수사 보드 진행');
                navigate('/board');
              }}
              className="btn-primary"
            >
              수사 보드 →
            </button>
          </>
        }
      />

      <PageBody className="flex flex-col gap-6 animate-fade-up">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <CompletenessKpi
            rate={rate}
            label={rate === 100 ? '완전 수집' : rate >= 60 ? '수집 갭 감지' : '필수 증거 부족'}
          />

          <div className="lg:col-span-2 flex flex-col gap-3">
            <Card borderColor="#FF4D6D">
              <div className="flex justify-between items-center gap-3">
                <div>
                  <b className="text-brand-red text-[14px]">⛔ 수집 갭 — {requiredMissing.length}건</b>
                  <p className="text-[12px] text-ink-300 mt-1 leading-6">
                    {requiredMissing.length
                      ? `${requiredMissing.map((e) => e.name).join(', ')} 미수집: 네트워크 공격 경로 추적 불가`
                      : '필수 증거가 모두 확보되었습니다.'}
                  </p>
                </div>
                <button
                  onClick={() => {
                    showToast('Layer 0 복귀');
                    navigate('/setup');
                  }}
                  className="btn-danger whitespace-nowrap"
                >
                  ↩ Layer 0 복귀
                </button>
              </div>
            </Card>

            <Card borderColor="#FBB13B">
              <b className="text-brand-amber text-[14px]">⚠ 증거 갭 — {corMissing.length}건</b>
              <p className="text-[12px] text-ink-300 mt-1 leading-6">
                {corMissing.length
                  ? `${corMissing.map((e) => e.name).join(', ')} 보강 증거 부족`
                  : '보강 증거가 모두 확보되었습니다.'}
              </p>
              <div className="mt-2">
                <Badge tone="amber">수사관 판단 위임</Badge>
              </div>
            </Card>

            <Card borderColor="#14D9B0">
              <b className="text-brand-teal text-[14px]">✅ 해석 갭 — 0건</b>
              <p className="text-[12px] text-ink-300 mt-1 leading-6">
                모든 매핑 결과에 대한 ATT&CK 문서 참조 가능
              </p>
            </Card>
          </div>
        </div>

        <EvidenceItemList items={evidence} />
      </PageBody>
    </div>
  );
};

export default V4Gap;
