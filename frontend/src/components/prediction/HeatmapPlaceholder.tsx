// Explainable AI placeholder for future saliency or Grad-CAM overlays.
export const HeatmapPlaceholder = () => (
  <div className="relative min-h-64 overflow-hidden rounded-xl border border-space-border bg-space-background mission-grid">
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_36%_42%,rgba(0,194,255,0.32),transparent_18%),radial-gradient(circle_at_66%_58%,rgba(124,58,237,0.28),transparent_22%),radial-gradient(circle_at_48%_70%,rgba(37,99,235,0.3),transparent_16%)]" />
    <div className="absolute inset-x-4 bottom-4 rounded-lg border border-space-border bg-black/35 p-3 backdrop-blur">
      <p className="text-sm font-medium text-white">Explainable AI heatmap placeholder</p>
      <p className="mt-1 text-xs text-slate-400">Future overlay will highlight spectral regions that influenced mineral classification.</p>
    </div>
  </div>
);
