import { useState, useCallback, useRef } from 'react';

interface DropZoneProps {
  onUpload: (files: File[]) => void;
}

const DropZone = ({ onUpload }: DropZoneProps) => {
  const [active, setActive] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setActive(true);
  }, []);
  const handleDragLeave = useCallback(() => setActive(false), []);
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setActive(false);
      const files = Array.from(e.dataTransfer.files);
      if (files.length) onUpload(files);
    },
    [onUpload],
  );

  const handleClick = () => inputRef.current?.click();
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length) onUpload(files);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div
      onClick={handleClick}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`panel cursor-pointer text-center py-10 px-6 select-none transition-all border-2 border-dashed flex flex-col items-center justify-center gap-2 ${
        active
          ? 'border-brand-blue bg-brand-blue/[0.08] shadow-glow'
          : 'border-ink-700 hover:border-brand-blue/60 hover:bg-ink-900/40'
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".json,.csv,.jsonl"
        onChange={handleFileSelect}
        className="hidden"
      />
      <div
        className={`w-14 h-14 rounded-2xl bg-cta-gradient flex items-center justify-center text-[28px] transition-transform ${
          active ? 'scale-110' : ''
        }`}
      >
        
      </div>
      <div className="font-bold text-[14px]">CSP 로그 파일 업로드</div>
      <div className="text-[12px] text-ink-400">
        JSON · CSV · JSONL 지원 · 드래그 앤 드롭 또는 클릭
      </div>
    </div>
  );
};

export default DropZone;
