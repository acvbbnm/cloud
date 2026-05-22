import { useToastStore } from '@/stores/useToastStore';

const Toast = () => {
  const items = useToastStore((s) => s.items);
  const dismiss = useToastStore((s) => s.dismiss);

  return (
    <div className="fixed top-6 left-1/2 -translate-x-1/2 z-[9999] flex flex-col items-center gap-2 pointer-events-none">
      {items.map((t) => (
        <button
          key={t.id}
          onClick={() => dismiss(t.id)}
          className="panel px-4 py-2.5 text-[12px] font-medium flex items-center gap-2 pointer-events-auto animate-fade-up cursor-pointer hover:brightness-110 max-w-[480px]"
        >
          <span className="w-5 h-5 rounded-full bg-brand-teal/20 text-brand-teal flex items-center justify-center text-[10px] shrink-0">
            ✓
          </span>
          <span className="text-left">{t.message}</span>
        </button>
      ))}
    </div>
  );
};

export default Toast;
