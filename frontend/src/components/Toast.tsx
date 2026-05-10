import { useToastStore } from '@/stores/useToastStore';

const Toast = () => {
  const message = useToastStore((s) => s.message);

  return (
    <div
      className={`fixed top-6 left-1/2 -translate-x-1/2 z-[9999] panel px-4 py-2.5 text-[12px] font-medium flex items-center gap-2 transition-all duration-300 ${
        message ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-2 pointer-events-none'
      }`}
    >
      <span className="w-5 h-5 rounded-full bg-brand-teal/20 text-brand-teal flex items-center justify-center text-[10px]">
        ✓
      </span>
      <span>{message ?? ''}</span>
    </div>
  );
};

export default Toast;
