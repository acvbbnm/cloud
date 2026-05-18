/**
 * 부분 로그 분석 — V-1 Step 2 Discovery Loop ② 부분 로그 분석 (사용자 결정 #2).
 *
 * 단서 시각 ±5분 로그 파일을 업로드해서 OCSF + ATT&CK 기법 매핑 결과를 받음.
 * 백엔드 /api/triage/analyze (multipart) 미구현 시 mock — 파일명 패턴으로
 * 기법 매핑을 시뮬레이션.
 *
 * useTriageStore:
 *   - mappedTechniques 누적
 *   - 백엔드 응답 시 hypothesisScores 도 갱신
 *
 * 학술 근거: AWS Detective scope time + Microsoft Sentinel entity + KISA §2.6
 *           휘발성 정보 수집 (시각 윈도우 좁히기).
 */
import { useState } from 'react';

import Badge from '@/components/Badge';
import DropZone from '@/views/V2_Logs/DropZone';

interface PartialLogAnalysisProps {
  /** 분석 완료된 기법 ID 목록 (누적). */
  mappedTechniques: string[];
  /** 분석 후 호출 — 부모가 useTriageStore.addMappedTechniques 등 처리. */
  onAnalyzed: (techniqueIds: string[], filenames: string[]) => void;
  disabled?: boolean;
}

interface AnalyzedFile {
  name: string;
  size: number;
  techniques: string[];
  analyzed_at: string;
}

// Mock — 파일명 패턴으로 기법 매핑 시뮬레이션 (백엔드 미구현 시)
const mockAnalyze = (file: File): string[] => {
  const name = file.name.toLowerCase();
  const techniques: string[] = [];
  // attack-sim 합성 raw 패턴
  if (name.includes('ncp') && (name.includes('attack') || name.includes('none') || name.includes('collection'))) {
    techniques.push('T1078.004', 'T1098.001');
  }
  if (name.includes('nhn') && (name.includes('attack') || name.includes('none') || name.includes('collection'))) {
    techniques.push('T1078.004', 'T1530', 'T1531');
  }
  if (name.includes('brute') || name.includes('login')) {
    techniques.push('T1110');
  }
  if (name.includes('storage') || name.includes('object')) {
    techniques.push('T1530', 'T1567');
  }
  // 최소 보장
  if (techniques.length === 0) {
    techniques.push('T1078');
  }
  return [...new Set(techniques)];
};

const PartialLogAnalysis = ({
  mappedTechniques,
  onAnalyzed,
  disabled,
}: PartialLogAnalysisProps) => {
  const [files, setFiles] = useState<AnalyzedFile[]>([]);
  const [analyzing, setAnalyzing] = useState(false);

  const handleUpload = async (uploaded: File[]) => {
    if (uploaded.length === 0 || disabled) return;
    setAnalyzing(true);
    try {
      // Mock 처리 — 백엔드 /api/triage/analyze 가 구현되면 그것을 호출
      // multipart/form-data 로 file + caseId + clue 전송, mapped_techniques 응답
      // 현재는 클라이언트 mockAnalyze 로 대체
      const allTechniques: string[] = [];
      const fileMetas: AnalyzedFile[] = [];
      for (const file of uploaded) {
        const techniques = mockAnalyze(file);
        allTechniques.push(...techniques);
        fileMetas.push({
          name: file.name,
          size: file.size,
          techniques,
          analyzed_at: new Date().toISOString(),
        });
        // 약간의 지연 (시각적 피드백)
        await new Promise((r) => setTimeout(r, 200));
      }
      setFiles((prev) => [...prev, ...fileMetas]);
      onAnalyzed(allTechniques, fileMetas.map((f) => f.name));
    } finally {
      setAnalyzing(false);
    }
  };

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
    // 기법 제거는 store 에서 단순화 — 다른 파일이 같은 기법 가지고 있을 수 있으므로
    // 보수적으로 제거 안 함 (사용자 결정 #2: 누적 분석).
  };

  const fmtSize = (n: number) => {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1024 / 1024).toFixed(1)} MB`;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <div className="text-[10.5px] text-ink-400 font-semibold uppercase tracking-wider">
          📊 부분 로그 분석 (선택)
        </div>
        {mappedTechniques.length > 0 && (
          <span className="text-[10.5px] text-brand-teal">
            ● {mappedTechniques.length}개 기법 매핑
          </span>
        )}
      </div>

      <p className="text-[10.5px] text-ink-500 mb-2 leading-5">
        단서 시각 ±5분 로그를 업로드하면 OCSF + ATT&CK 매핑이 우측 가설 점수에 반영됩니다.
        ※ 백엔드 /api/triage/analyze 미구현 시 파일명 패턴으로 mock 동작.
      </p>

      <DropZone onUpload={handleUpload} />

      {analyzing && (
        <div className="mt-2 text-[10.5px] text-amber-300 animate-pulse">
          ⏳ 분석 중…
        </div>
      )}

      {files.length > 0 && (
        <div className="mt-3 space-y-1">
          {files.map((f, i) => (
            <div
              key={`${f.name}-${i}-${f.analyzed_at}`}
              className="bg-ink-900/60 border border-ink-700/70 rounded-lg px-2.5 py-1.5 text-[11px]"
            >
              <div className="flex items-start gap-2">
                <span className="text-[13px]">📄</span>
                <div className="flex-1 min-w-0">
                  <div className="text-ink-100 truncate font-medium">{f.name}</div>
                  <div className="text-[10.5px] text-ink-400">
                    {fmtSize(f.size)} · {f.techniques.length}개 기법 매핑
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {f.techniques.map((t) => (
                      <Badge key={t} tone="purple" size="sm">
                        {t}
                      </Badge>
                    ))}
                  </div>
                </div>
                <button
                  onClick={() => removeFile(i)}
                  className="text-ink-500 hover:text-red-400 text-[14px] leading-none px-1"
                  title="파일 항목 제거 (매핑된 기법은 누적 유지)"
                >
                  ×
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 누적된 기법 요약 */}
      {mappedTechniques.length > 0 && (
        <div className="mt-3 pt-2 border-t border-ink-700/40">
          <div className="text-[10px] text-ink-500 mb-1">누적 매핑 기법:</div>
          <div className="flex flex-wrap gap-1">
            {mappedTechniques.map((t) => (
              <Badge key={t} tone="purple" size="sm">
                {t}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default PartialLogAnalysis;
