// Compact confidence gauge displayed on prediction and dashboard cards.
import { Gauge } from "lucide-react";
import { formatPercent } from "@/utils/formatters";

type ConfidenceGaugeProps = {
  value: number;
};

export const ConfidenceGauge = ({ value }: ConfidenceGaugeProps) => (
  <div className="rounded-xl border border-space-border bg-white/[0.04] p-4">
    <div className="mb-3 flex items-center justify-between">
      <span className="flex items-center gap-2 text-sm font-medium text-slate-300">
        <Gauge className="h-4 w-4 text-secondary" />
        Confidence
      </span>
      <span className="text-xl font-bold text-white">{formatPercent(value)}</span>
    </div>
    <div className="h-2 overflow-hidden rounded-full bg-slate-800">
      <div
        className="h-full rounded-full bg-gradient-to-r from-primary via-secondary to-accent transition-all duration-500"
        style={{ width: `${Math.min(value, 100)}%` }}
      />
    </div>
  </div>
);
