import type { MarketOverview } from "@/types/macro";
import { cn } from "@/lib/cn";

interface MarketBreadthCardProps {
  data: MarketOverview;
  className?: string;
}

export function MarketBreadthCard({ data, className }: MarketBreadthCardProps) {
  const total = data.advancing + data.declining + data.unchanged;
  const advancing = (data.advancing / total) * 100;
  const declining = (data.declining / total) * 100;
  const unchanged = 100 - advancing - declining;

  return (
    <div className={cn("rounded-xl border border-border bg-surface/80 p-5", className)}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Market breadth</p>
          <p className="mt-1 text-sm font-semibold text-foreground">
            {data.advancing} advancing · {data.declining} declining
          </p>
        </div>
        <p className="text-[11px] text-muted-foreground">
          {data.deals === null ? "Deals unavailable" : `${data.deals.toLocaleString()} deals`}
        </p>
      </div>

      <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-surface-elevated">
        <div className="h-full bg-success" style={{ width: `${advancing}%` }} />
        <div className="h-full bg-muted-foreground/40" style={{ width: `${unchanged}%` }} />
        <div className="h-full bg-danger" style={{ width: `${declining}%` }} />
      </div>

      <div className="mt-3 grid grid-cols-3 text-[11px]">
        <span className="text-success">Advancing {advancing.toFixed(0)}%</span>
        <span className="text-center text-muted-foreground">Unchanged {unchanged.toFixed(0)}%</span>
        <span className="text-right text-danger">Declining {declining.toFixed(0)}%</span>
      </div>
    </div>
  );
}
