import { ArrowUpRight, ArrowDownRight, Circle, BrainCircuit } from "lucide-react";
import type { AIInsight } from "@/types/ai";
import { PredictionBadge } from "./PredictionBadge";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { RiskScoreCard } from "./RiskScoreCard";
import { cn } from "@/lib/cn";

interface ExplainabilityPanelProps {
  insight: AIInsight;
  className?: string;
}

export function ExplainabilityPanel({ insight, className }: ExplainabilityPanelProps) {
  const totalRisk = insight.risks.marketRisk + insight.risks.sectorRisk + insight.risks.companyRisk;
  return (
    <div className={cn("space-y-5 rounded-xl border border-border bg-surface/80 p-6", className)}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan/15 text-cyan ring-1 ring-cyan/30">
            <BrainCircuit className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-cyan/80">Explainable AI</p>
            <p className="text-sm font-semibold text-foreground">
              Outlook for {insight.symbol ?? "the market"} · {insight.horizonDays}-day horizon
            </p>
            <p className="text-[11px] text-muted-foreground">Model {insight.modelVersion}</p>
          </div>
        </div>
        <PredictionBadge outlook={insight.outlook} />
      </header>

      <p className="text-sm leading-relaxed text-foreground">{insight.summary}</p>

      <ConfidenceMeter value={insight.confidence} />

      <div>
        <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Driver breakdown</p>
        <ul className="space-y-2">
          {insight.drivers.map((d) => {
            const Icon = d.direction === "positive" ? ArrowUpRight : d.direction === "negative" ? ArrowDownRight : Circle;
            const color =
              d.direction === "positive" ? "text-success" : d.direction === "negative" ? "text-danger" : "text-muted-foreground";
            return (
              <li key={d.label} className="flex items-center gap-3 rounded-lg border border-border/60 bg-surface-elevated/60 p-3">
                <Icon className={cn("h-4 w-4 shrink-0", color)} />
                <p className="flex-1 text-sm text-foreground">{d.label}</p>
                <div className="hidden w-24 sm:block">
                  <div className="h-1.5 overflow-hidden rounded-full bg-surface">
                    <div
                      className={cn(
                        "h-full",
                        d.direction === "positive" && "bg-success",
                        d.direction === "negative" && "bg-danger",
                        d.direction === "neutral" && "bg-muted-foreground/60",
                      )}
                      style={{ width: `${Math.round(d.weight * 100)}%` }}
                    />
                  </div>
                </div>
                <span className="w-10 text-right text-xs tabular-nums text-muted-foreground">
                  {Math.round(d.weight * 100)}%
                </span>
              </li>
            );
          })}
        </ul>
      </div>

      <RiskScoreCard total={totalRisk} decomposition={insight.risks} />
    </div>
  );
}
