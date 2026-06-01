const NGN = "NGN ";

export function formatCurrency(value: number | null | undefined, currency: string = NGN, fractionDigits = 2): string {
  if (value === null || value === undefined) return "Unavailable";
  if (!Number.isFinite(value)) return `${currency}-`;
  return `${currency}${value.toLocaleString("en-NG", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })}`;
}

export function formatCompact(value: number | null | undefined, currency = ""): string {
  if (value === null || value === undefined) return "Unavailable";
  if (!Number.isFinite(value)) return "-";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e12) return `${sign}${currency}${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}${currency}${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}${currency}${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}${currency}${(abs / 1e3).toFixed(2)}K`;
  return `${sign}${currency}${abs.toFixed(0)}`;
}

export function formatMarketCap(value: number | null | undefined): string {
  return formatCompact(value, NGN);
}

export function formatNumber(value: number | null | undefined, fractionDigits = 0): string {
  if (value === null || value === undefined) return "Unavailable";
  if (!Number.isFinite(value)) return "-";
  return value.toLocaleString("en-NG", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

export function formatPercent(value: number, fractionDigits = 2, withSign = true): string {
  if (!Number.isFinite(value)) return "-";
  const sign = withSign ? (value > 0 ? "+" : "") : "";
  return `${sign}${value.toFixed(fractionDigits)}%`;
}

export function formatChange(value: number, fractionDigits = 2): string {
  if (!Number.isFinite(value)) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(fractionDigits)}`;
}

export function changeColor(value: number): string {
  if (value > 0) return "text-success";
  if (value < 0) return "text-danger";
  return "text-muted-foreground";
}

export function changeBg(value: number): string {
  if (value > 0) return "bg-success-soft text-success";
  if (value < 0) return "bg-danger-soft text-danger";
  return "bg-muted text-muted-foreground";
}

export function formatDate(input: string | Date, opts?: Intl.DateTimeFormatOptions): string {
  const d = typeof input === "string" ? new Date(input) : input;
  return d.toLocaleDateString("en-NG", opts ?? { year: "numeric", month: "short", day: "numeric" });
}

export function formatDateTime(input: string | Date): string {
  const d = typeof input === "string" ? new Date(input) : input;
  return d.toLocaleString("en-NG", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelative(input: string | Date): string {
  const d = typeof input === "string" ? new Date(input) : input;
  const diff = Date.now() - d.getTime();
  const minutes = Math.round(diff / 60_000);
  if (minutes < 1) return "less than 1m ago";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return formatDate(d);
}

export function abbreviateSymbol(symbol: string, max = 6): string {
  return symbol.length <= max ? symbol : `${symbol.slice(0, max - 1)}...`;
}
