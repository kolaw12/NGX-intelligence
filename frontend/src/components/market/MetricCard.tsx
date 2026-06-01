import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { ChangeText } from "@/components/common/NumberFormat";

interface MetricCardProps {
  label: string;
  value: string;
  change?: number;
  icon?: LucideIcon;
  helper?: string;
  className?: string;
  accent?: "default" | "cyan" | "gold";
}

export function MetricCard({ label, value, change, icon: Icon, helper, className, accent = "default" }: MetricCardProps) {
  const accentMap = {
    default: "text-muted-foreground",
    cyan: "text-cyan",
    gold: "text-gold",
  };
  return (
    <div className={cn("rounded-xl border border-border bg-surface/80 p-4", className)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-foreground tabular-nums">{value}</p>
        </div>
        {Icon && (
          <div className={cn("flex h-9 w-9 items-center justify-center rounded-lg bg-surface-elevated", accentMap[accent])}>
            <Icon className="h-4 w-4" />
          </div>
        )}
      </div>
      {(change !== undefined || helper) && (
        <div className="mt-3 flex items-center justify-between">
          {change !== undefined && <ChangeText value={change} size="sm" />}
          {helper && <p className="text-[11px] text-muted-foreground">{helper}</p>}
        </div>
      )}
    </div>
  );
}
