// Formatting helpers for dates, percentages, and mission-facing numbers.
export const formatDate = (value: string) =>
  new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));

export const formatPercent = (value: number) => `${value.toFixed(1)}%`;

export const formatNumber = (value: number) => new Intl.NumberFormat("en").format(value);
