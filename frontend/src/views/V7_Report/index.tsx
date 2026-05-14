import { useState } from 'react';

import PageHeader from '@/components/PageHeader';
import PageBody from '@/components/PageBody';
import Card from '@/components/Card';
import { useToastStore } from '@/stores/useToastStore';

interface Section {
  key: string;
  title: string;
  initial: string;
  rows: number;
  emoji: string;
}

const sections: Section[] = [
  {
    key: 'overview',
    title: '사고 개요',
    emoji: '📌',
    rows: 3,
    initial:
      '2026-03-25 02:34 KST, 해외 IP(203.0.113.45)에서 admin-user 계정으로 비인가 로그인. Sub Account 권한 상승 후 Object Storage에서 2.3GB 대량 다운로드.',
  },
  {
    key: 'timeline',
    title: '타임라인',
    emoji: '⏱',
    rows: 5,
    initial:
      '02:34 — consoleSignIn (해외 IP)\n14:32 — changeSubAccountLoginId\n14:33 — addSubAccountRole (권한 상승)\n14:35 — putBucketPolicy (외부 공유)\n14:38 — getObject x142 (2.3GB)',
  },
  {
    key: 'impact',
    title: '영향 분석',
    emoji: '💥',
    rows: 3,
    initial:
      '계정: admin-user, svc-backup, svc-admin-prod\n리소스: bucket-finance-2026 / 유출: ~2.3GB',
  },
  {
    key: 'attack_analysis',
    title: 'ATT&CK 결과',
    emoji: '🎯',
    rows: 4,
    initial:
      'T1078 → T1098 → T1078.004 → T1530 → T1537\n총 7개 기법, 4개 전술 탐지\n규칙 기반 JSON 매핑 (환각 없음)',
  },
  {
    key: 'response',
    title: '대응 조치',
    emoji: '🛡',
    rows: 4,
    initial:
      '15:08 계정 잠금\n15:12 외부 공유 제거\n15:20 해외 IP 블록\n15:30 비밀번호 초기화',
  },
  {
    key: 'recommendation',
    title: '권고사항',
    emoji: '💡',
    rows: 3,
    initial:
      '수집 갭: VPC Flow Log 확보 필요\n권고: MFA 확대, IP 기반 접근 제어 강화',
  },
];

const V7Report = () => {
  const showToast = useToastStore((s) => s.show);
  const [content, setContent] = useState<Record<string, string>>(() =>
    Object.fromEntries(sections.map((s) => [s.key, s.initial])),
  );

  const handleAiDraft = () => {
    showToast('AI 초안 생성 중...');
  };

  const handleExport = (fmt: string) => {
    showToast(`${fmt.toUpperCase()} 내보내기 완료`);
  };

  return (
    <div>
      <PageHeader
        eyebrow="Layer 4 · M4-1"
        title={
          <>
            보고서 <span className="grad-text">생성</span>
          </>
        }
        description="KISA 양식 6 섹션을 편집하고 AI 초안을 활용해 사고 보고서를 완성합니다. PDF · DOCX 내보내기 지원."
        actions={
          <>
            <button onClick={handleAiDraft} className="btn-ghost">
              🧠 AI 초안
            </button>
            <button onClick={() => handleExport('docx')} className="btn-ghost">
              📝 DOCX
            </button>
            <button onClick={() => handleExport('pdf')} className="btn-primary">
              📄 PDF 내보내기
            </button>
          </>
        }
      />

      <PageBody className="animate-fade-up">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {sections.map((s, i) => (
            <Card
              key={s.key}
              title={
                <>
                  <span className="w-6 h-6 rounded-lg bg-cta-gradient text-white text-[11px] font-bold flex items-center justify-center">
                    {i + 1}
                  </span>
                  <span>
                    {s.emoji} {s.title}
                  </span>
                </>
              }
              action={
                <span className="chip text-[10px]">
                  {content[s.key].length} chars
                </span>
              }
            >
              <textarea
                value={content[s.key]}
                onChange={(e) => setContent((prev) => ({ ...prev, [s.key]: e.target.value }))}
                rows={s.rows}
                className="input resize-y font-mono leading-7"
              />
            </Card>
          ))}
        </div>
      </PageBody>
    </div>
  );
};

export default V7Report;
