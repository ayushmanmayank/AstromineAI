// Toast context value and React context shared by the provider and hook.
import { createContext } from "react";

export type Toast = {
  id: string;
  title: string;
  description?: string;
};

export type ToastContextValue = {
  toasts: Toast[];
  showToast: (toast: Omit<Toast, "id">) => void;
  dismissToast: (id: string) => void;
};

export const ToastContext = createContext<ToastContextValue | undefined>(undefined);
