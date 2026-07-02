// Hook for consuming toast notifications from the application provider.
import { useContext } from "react";
import { ToastContext } from "@/contexts/toast-context";

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
};
