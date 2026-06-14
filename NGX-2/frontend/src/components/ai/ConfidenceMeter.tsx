import { cn } from "@/lib/cn";

interface ConfidenceMeterProps {
  value: number;
  label?: string;
  size?: "sm" | "md";
  className?: string;
}

export function ConfidenceMeter({ value, label = "Confidence", size = "md", className }: ConfidenceMeterProps) {
  const color = value >= 75 ? "bg-success" : value >= 55 ? "bg-cyan" : value >= 35 ? "bg-gold" : "bg-danger";
  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</span>
        <span className={cn("font-semibold tabular-nums text-foreground", size === "sm" ? "text-xs" : "text-sm")}>
          {value}%
        </span>
      </div>
      <div className={cn("w-full overflow-hidden rounded-full bg-surface-elevated", size === "sm" ? "h-1.5" : "h-2")}>
        <div className={cn("h-full transition-all", color)} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
    </div>
  );
}
