import { BrainCircuit, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import type { AIInsight } from "@/types/ai";
import { PredictionBadge } from "./PredictionBadge";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { ROUTES } from "@/constants/routes";
import { cn } from "@/lib/cn";

interface AIInsightCardProps {
  insight: AIInsight;
  className?: string;
  compact?: boolean;
}

export function AIInsightCard({ insight, className, compact = false }: AIInsightCardProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 rounded-xl border border-border bg-gradient-to-br from-surface to-cyan/[0.06] p-5 shadow-card",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan/15 text-cyan ring-1 ring-cyan/30">
            <BrainCircuit className="h-4 w-4" />
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">AI outlook</p>
            <p className="text-sm font-semibold text-foreground">{insight.symbol ?? "Market"}</p>
          </div>
        </div>
        <PredictionBadge outlook={insight.outlook} />
      </div>

      {!compact && <p className="text-sm leading-relaxed text-muted-foreground">{insight.summary}</p>}

      <ConfidenceMeter value={insight.confidence} />

      {!compact && insight.drivers.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Key drivers</p>
          <ul className="space-y-1">
            {insight.drivers.slice(0, 3).map((d) => (
              <li key={d.label} className="flex items-start gap-2 text-xs text-foreground">
                <span
                  className={cn(
                    "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
                    d.direction === "positive" && "bg-success",
                    d.direction === "negative" && "bg-danger",
                    d.direction === "neutral" && "bg-muted-foreground",
                  )}
                />
                <span>{d.label}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {insight.symbol && (
        <Link
          to={ROUTES.stockDetail(insight.symbol)}
          className="inline-flex items-center gap-1 text-xs font-medium text-cyan hover:text-cyan-300"
        >
          View full analysis <ArrowRight className="h-3 w-3" />
        </Link>
      )}
    </div>
  );
}
