import { Link } from "react-router-dom";
import type { Stock } from "@/types/stock";
import { ROUTES } from "@/constants/routes";
import { ChangeText, Price } from "@/components/common/NumberFormat";
import { SparklineChart } from "@/components/charts/SparklineChart";
import { cn } from "@/lib/cn";

interface StockRowProps {
  stock: Stock;
  showSparkline?: boolean;
  className?: string;
}

export function StockRow({ stock, showSparkline = true, className }: StockRowProps) {
  return (
    <Link
      to={ROUTES.stockDetail(stock.symbol)}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-surface-elevated/60",
        className,
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-foreground">{stock.symbol}</p>
        <p className="truncate text-[11px] text-muted-foreground">{stock.name}</p>
      </div>
      {showSparkline && (
        <div className="hidden h-8 w-16 sm:block">
          <SparklineChart data={stock.sparkline} height={32} positive={stock.changePct >= 0} />
        </div>
      )}
      <div className="text-right">
        <Price value={stock.price} size="sm" />
        <div className="mt-0.5">
          <ChangeText value={stock.changePct} size="sm" withIcon={false} />
        </div>
      </div>
    </Link>
  );
}
