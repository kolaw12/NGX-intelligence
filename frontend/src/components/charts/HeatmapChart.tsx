import type { Stock } from "@/types/stock";
import { changeBg } from "@/lib/format";
import { cn } from "@/lib/cn";

interface HeatmapChartProps {
  stocks: Stock[];
  className?: string;
}

export function HeatmapChart({ stocks, className }: HeatmapChartProps) {
  // group by sector
  const grouped = stocks.reduce<Record<string, Stock[]>>((acc, s) => {
    (acc[s.sector] ??= []).push(s);
    return acc;
  }, {});

  return (
    <div className={cn("grid gap-3 sm:grid-cols-2 xl:grid-cols-3", className)}>
      {Object.entries(grouped).map(([sector, group]) => (
        <div key={sector} className="rounded-xl border border-border bg-surface/60 p-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{sector}</p>
            <p className="text-[10px] text-muted-foreground">{group.length} names</p>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {group.map((s) => {
              const intensity = Math.min(Math.abs(s.changePct) / 5, 1);
              const isPositive = s.changePct >= 0;
              return (
                <div
                  key={s.symbol}
                  className="rounded-md p-2 transition-transform hover:scale-[1.02]"
                  style={{
                    background: isPositive
                      ? `rgba(34,197,94,${0.1 + intensity * 0.45})`
                      : `rgba(239,68,68,${0.1 + intensity * 0.45})`,
                  }}
                  title={`${s.symbol} ${s.changePct.toFixed(2)}%`}
                >
                  <p className="text-xs font-semibold text-foreground">{s.symbol}</p>
                  <p className={cn("mt-1 text-[11px] tabular-nums", changeBg(s.changePct).replace(/bg-[^ ]+/, ""))}>
                    {s.changePct > 0 ? "+" : ""}
                    {s.changePct.toFixed(2)}%
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
