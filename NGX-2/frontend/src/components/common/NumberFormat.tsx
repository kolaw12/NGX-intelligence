import { formatChange, formatCurrency, formatNumber, formatPercent, changeColor } from "@/lib/format";
import { cn } from "@/lib/cn";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

interface ChangeProps {
  value: number;
  variant?: "absolute" | "percent" | "both";
  withIcon?: boolean;
  className?: string;
  size?: "sm" | "md";
}

export function ChangeText({ value, variant = "percent", withIcon = true, className, size = "md" }: ChangeProps) {
  const Icon = value > 0 ? ArrowUpRight : value < 0 ? ArrowDownRight : Minus;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 font-medium tabular-nums",
        changeColor(value),
        size === "sm" ? "text-xs" : "text-sm",
        className,
      )}
    >
      {withIcon && <Icon className={cn(size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5")} />}
      {variant === "absolute" && formatChange(value)}
      {variant === "percent" && formatPercent(value)}
      {variant === "both" && `${formatChange(value)} (${formatPercent(value)})`}
    </span>
  );
}

interface PriceProps {
  value: number | null | undefined;
  fractionDigits?: number;
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
}

export function Price({ value, fractionDigits = 2, className, size = "md" }: PriceProps) {
  const sizes = {
    sm: "text-sm",
    md: "text-base",
    lg: "text-xl",
    xl: "text-3xl",
  };
  return (
    <span className={cn("font-semibold tabular-nums tracking-tight text-foreground", sizes[size], className)}>
      {formatCurrency(value, "₦", fractionDigits)}
    </span>
  );
}

interface CompactProps {
  value: number | null | undefined;
  prefix?: string;
  className?: string;
}

export function Compact({ value, prefix = "", className }: CompactProps) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return <span className={cn("font-semibold tabular-nums text-muted-foreground", className)}>Unavailable</span>;
  }
  const abs = Math.abs(value);
  let suffix = "";
  let v = abs;
  if (abs >= 1e12) {
    v = abs / 1e12;
    suffix = "T";
  } else if (abs >= 1e9) {
    v = abs / 1e9;
    suffix = "B";
  } else if (abs >= 1e6) {
    v = abs / 1e6;
    suffix = "M";
  } else if (abs >= 1e3) {
    v = abs / 1e3;
    suffix = "K";
  }
  return (
    <span className={cn("font-semibold tabular-nums text-foreground", className)}>
      {value < 0 ? "-" : ""}
      {prefix}
      {v.toFixed(2)}
      {suffix}
    </span>
  );
}

interface NumProps {
  value: number | null | undefined;
  fractionDigits?: number;
  className?: string;
}

export function Num({ value, fractionDigits = 0, className }: NumProps) {
  return (
    <span className={cn("tabular-nums text-foreground", className)}>{formatNumber(value, fractionDigits)}</span>
  );
}
