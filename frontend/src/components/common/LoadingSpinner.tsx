// Shared loading indicator for query, upload, and prediction processing states.
type LoadingSpinnerProps = {
  label?: string;
};

export const LoadingSpinner = ({ label = "Processing telemetry" }: LoadingSpinnerProps) => (
  <div className="flex items-center gap-3 text-sm text-slate-300">
    <span className="h-5 w-5 animate-spin rounded-full border-2 border-secondary border-t-transparent" />
    <span>{label}</span>
  </div>
);
