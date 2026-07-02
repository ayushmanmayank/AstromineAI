// Select primitive used for filtering and upload metadata.
import type { SelectHTMLAttributes } from "react";
import { cn } from "@/utils/cn";

export const Select = ({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) => (
  <select
    className={cn(
      "h-11 w-full rounded-lg border border-space-border bg-[#111722] px-3 text-sm text-white outline-none transition focus:border-secondary focus:ring-2 focus:ring-secondary/20",
      className,
    )}
    {...props}
  />
);
