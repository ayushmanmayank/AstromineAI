// Text input primitive with dark NASA-inspired styling.
import type { InputHTMLAttributes } from "react";
import { cn } from "@/utils/cn";

export const Input = ({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) => (
  <input
    className={cn(
      "h-11 w-full rounded-lg border border-space-border bg-white/5 px-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-secondary focus:ring-2 focus:ring-secondary/20",
      className,
    )}
    {...props}
  />
);
