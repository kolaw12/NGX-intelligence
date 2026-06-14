import { Link } from "react-router-dom";
import { WalletCards } from "lucide-react";
import type { Watchlist } from "@/services/watchlist.service";
import { ROUTES } from "@/constants/routes";
import { cn } from "@/lib/cn";

interface WatchlistCardProps {
  watchlist: Watchlist;
  className?: string;
}

export function WatchlistCard({ watchlist, className }: WatchlistCardProps) {
  return (
    <Link
      to={ROUTES.watchlists}
      className={cn(
        "group flex flex-col gap-3 rounded-xl border border-border bg-surface/80 p-5 transition-all hover:border-cyan/40",
        className,
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan/12 text-cyan-700 ring-1 ring-cyan/30">
            <WalletCards className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">{watchlist.name}</p>
            <p className="text-[11px] text-muted-foreground">{watchlist.symbols.length} symbols</p>
          </div>
        </div>
      </div>
      <p className="line-clamp-2 text-xs text-muted-foreground">{watchlist.description}</p>
      <div className="flex flex-wrap gap-1.5">
        {watchlist.symbols.slice(0, 5).map((sym) => (
          <span key={sym} className="rounded-md bg-surface-elevated px-2 py-0.5 text-[11px] font-medium text-foreground">
            {sym}
          </span>
        ))}
        {watchlist.symbols.length > 5 && (
          <span className="rounded-md bg-surface-elevated px-2 py-0.5 text-[11px] text-muted-foreground">
            +{watchlist.symbols.length - 5}
          </span>
        )}
      </div>
    </Link>
  );
}
