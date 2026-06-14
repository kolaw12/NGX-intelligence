import { useStocks } from "@/hooks/useStocks";
import { ChangeText, Price } from "@/components/common/NumberFormat";
import { Link } from "react-router-dom";
import { ROUTES } from "@/constants/routes";
import { cn } from "@/lib/cn";

export function MarketTicker({ className }: { className?: string }) {
  const { data: stocks } = useStocks();
  if (!stocks?.length) {
    return <div className={cn("h-9 border-b border-border bg-surface/80", className)} />;
  }
  const items = [...stocks, ...stocks];
  return (
    <div className={cn("relative h-9 overflow-hidden border-b border-border bg-surface/80", className)}>
      <div className="absolute inset-y-0 left-0 z-10 flex w-16 items-center justify-center bg-gradient-to-r from-surface via-surface/90 to-transparent text-[11px] font-semibold uppercase tracking-widest text-cyan-600">
        NGX
      </div>
      <div className="flex h-full animate-ticker-scroll items-center gap-8 whitespace-nowrap pl-20 will-change-transform [&:hover]:[animation-play-state:paused]">
        {items.map((s, i) => (
          <Link
            key={`${s.symbol}-${i}`}
            to={ROUTES.stockDetail(s.symbol)}
            className="flex items-center gap-2 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <span className="font-semibold text-foreground">{s.symbol}</span>
            <Price value={s.price} size="sm" className="font-medium" />
            <ChangeText value={s.changePct} size="sm" withIcon={false} />
          </Link>
        ))}
      </div>
    </div>
  );
}
