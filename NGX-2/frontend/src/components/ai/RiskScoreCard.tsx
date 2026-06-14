import type { AIRiskDecomposition } from "@/types/ai";
import { ShieldCheck, ShieldAlert, Shield } from "lucide-react";
import { cn } from "@/lib/cn";

interface RiskScoreCardProps {
  total: number;
  decomposition?: AIRiskDecomposition;
  className?: string;
}

function bucket(total: number) {
  if (total <= 35) return { label: "Low risk", Icon: ShieldCheck, color: "text-success" };
  if (total <= 60) return { label: "Moderate risk", Icon: Shield, color: "text-gold" };
  return { label: "Elevated risk", Icon: ShieldAlert, color: "text-danger" };
}

export function RiskScoreCard({ total, decomposition, className }: RiskScoreCardProps) {
  const { label, Icon, color } = bucket(total);
  const rows = decomposition
    ? [
        { name: "Market", value: decomposition.marketRisk },
        { name: "Sector", value: decomposition.sectorRisk },
        { name: "Company", value: decomposition.companyRisk },
      ]
    : [];
  return (
    <div className={cn("rounded-xl border border-border bg-surface/80 p-5", className)}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div className={cn("flex h-9 w-9 items-center justify-center rounded-lg bg-surface-elevated", color)}>
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Risk indicator</p>
            <p className={cn("text-sm font-semibold", color)}>{label}</p>
          </div>
        </div>
        <p className="text-2xl font-semibold tabular-nums text-foreground">{total}</p>
      </div>
      {rows.length > 0 && (
        <div className="mt-4 space-y-2.5">
          {rows.map((r) => (
            <div key={r.name}>
              <div className="mb-1 flex items-center justify-between text-[11px] text-muted-foreground">
                <span>{r.name}</span>
                <span className="tabular-nums">{r.value}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-surface-elevated">
                <div
                  className="h-full bg-gradient-to-r from-cyan via-gold to-danger"
                  style={{ width: `${Math.min(r.value * 2, 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
