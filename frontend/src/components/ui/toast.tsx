// Small toast component powered by the ToastContext provider.
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/useToast";

export const ToastViewport = () => {
  const { toasts, dismissToast } = useToast();

  return (
    <div className="fixed bottom-4 right-4 z-50 flex w-[min(92vw,360px)] flex-col gap-3">
      {toasts.map((toast) => (
        <div key={toast.id} className="glass-card rounded-xl p-4 shadow-glow">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">{toast.title}</p>
              {toast.description ? (
                <p className="mt-1 text-sm text-slate-400">{toast.description}</p>
              ) : null}
            </div>
            <Button size="icon" variant="ghost" onClick={() => dismissToast(toast.id)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
};
