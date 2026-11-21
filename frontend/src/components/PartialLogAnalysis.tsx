/**
 * 부분 로그 분석 — V-1 Step 2 Discovery Loop  부분 로그 분석 (사용자 결정 #2).
 *
 * dev3 B-2 (2026-05-19): 백엔드 /api/triage/analyze-logs (multipart) 실 호출.
 *   - LogIngestor.ingest → OCSFNormalizer.normalize_case → AttackMapper.map_case
 *   - clue_time ±window_minutes 윈도우 내 attack_events 필터 → technique_ids 누적
 *   - 응답: hypothesis_scores (갱신본) + mapped_events
 *
 * 부모(Step2_Discovery)가 응답의 hypothesis_scores 로 useTriageStore.setHypothesisScores
 * 호출 + addMappedTechniques 로 기법 누적.
 *
 * 학술 근거: AWS Detective scope time + Microsoft Sentinel entity + KISA §2.6
 *           휘발성 정보 수집 (시각 윈도우 좁히기).
 */
import { useState } from 'react';

import Badge from '@/components/Badge';
import DropZone from '@/views/V2_Logs/DropZone';

import { analyzeLogs } from '@/api/triage';
import { useToastStore } from '@/stores/useToastStore';

import type { HypothesisScores } from '@/types';

interface PartialLogAnalysisProps {
  /** 케이스 ID — 백엔드 호출 필수. */
  caseId: string | null;
  /** 현재 누적 가설 점수 — 백엔드 stateless 정책으로 매 호출 전달. */
  currentScores: HypothesisScores;
  /** 분석 완료된 기법 ID 목록 (누적, 표시용). */
  mappedTechniques: string[];
  /** 단서 시각 ISO8601 (선택) — ±window_minutes 윈도우 필터. */
  clueTime?: string | null;
  /**
   * 분석 후 호출 — 부모가 useTriageStore.setHypothesisScores +
   * addMappedTechniques 등 처리.
   */
  onAnalyzed: (
    techniqueIds: string[],
    filenames: string[],
    newScores: HypothesisScores,
  ) => void;
  disabled?: boolean;
}

interface AnalyzedFile {
  name: string;
  size: number;
  techniques: string[];
  analyzed_at: string;
}

const PartialLogAnalysis = ({
  caseId,
  currentScores,
  mappedTechniques,
  clueTime,
  onAnalyzed,
  disabled,
}: PartialLogAnalysisProps) => {
  const showToast = useToastStore((s) => s.show);
  const [files, setFiles] = useState<AnalyzedFile[]>([]);
  const [analyzing, setAnalyzing] = useState(false);

  const handleUpload = async (uploaded: File[]) => {
    if (uploaded.length === 0 || disabled) return;
    if (!caseId) {
      showToast('caseId 누락 — Step 1 으로 돌아가 케이스를 생성하세요.');
      return;
    }
    setAnalyzing(true);
    try {
      let scores: HypothesisScores = currentScores;
      const allTechniques: string[] = [];
      const fileMetas: AnalyzedFile[] = [];
      for (const file of uploaded) {
        // 백엔드 /api/triage/analyze-logs (multipart) 실 호출 — 순차 처리하여
        // 가설 점수가 파일 누적순으로 갱신되게.
        const res = await analyzeLogs(caseId, file, scores, clueTime, 5);
        // mapped_events 에서 distinct technique_id 추출
        const tids = [
          ...new Set((res.mapped_events ?? []).map((e) => e.technique_id).filter(Boolean)),
        ];
        scores = res.hypothesis_scores;
        allTechniques.push(...tids);
        fileMetas.push({
          name: file.name,
          size: file.size,
          techniques: tids,
          analyzed_at: new Date().toISOString(),
        });
      }
      setFiles((prev) => [...prev, ...fileMetas]);
      onAnalyzed(allTechniques, fileMetas.map((f) => f.name), scores);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(`부분 로그 분석 실패: ${msg}`);
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
           부분 로그 분석 (선택)
        </div>
        {mappedTechniques.length > 0 && (
          <span className="text-[10.5px] text-brand-teal">
             {mappedTechniques.length}개 기법 매핑
          </span>
        )}
      </div>

      <p className="text-[10.5px] text-ink-500 mb-2 leading-5">
        단서 시각 ±5분 로그를 업로드하면 OCSF + ATT&CK 매핑이 우측 가설 점수에 반영됩니다.
      </p>

      <DropZone onUpload={handleUpload} />

      {analyzing && (
        <div className="mt-2 text-[10.5px] text-amber-300 animate-pulse">
           분석 중…
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
                <span className="text-[13px]"></span>
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
