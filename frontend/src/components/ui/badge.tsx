// Badge primitive for compact model and prediction status labels.
import type { HTMLAttributes } from "react";
import { cn } from "@/utils/cn";

export const Badge = ({ className, ...props }: HTMLAttributes<HTMLSpanElement>) => (
  <span
    className={cn(
      "inline-flex items-center rounded-full border border-space-border bg-white/5 px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-slate-200",
      className,
    )}
    {...props}
  />
);
