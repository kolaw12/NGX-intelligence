import { Link } from "react-router-dom";
import type { Stock } from "@/types/stock";
import { ROUTES } from "@/constants/routes";
import { SparklineChart } from "@/components/charts/SparklineChart";
import { Price, ChangeText } from "@/components/common/NumberFormat";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

interface StockCardProps {
  stock: Stock;
  className?: string;
}

const outlookVariant: Record<Stock["aiOutlook"], "success" | "danger" | "default"> = {
  bullish: "success",
  bearish: "danger",
  neutral: "default",
};

export function StockCard({ stock, className }: StockCardProps) {
  return (
    <Link
      to={ROUTES.stockDetail(stock.symbol)}
      className={cn(
        "group flex flex-col gap-3 rounded-xl border border-border bg-surface/80 p-4 transition-all hover:border-cyan/40 hover:shadow-glow",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold tracking-tight text-foreground">{stock.symbol}</p>
          <p className="truncate text-[11px] text-muted-foreground">{stock.name}</p>
        </div>
        <Badge variant={outlookVariant[stock.aiOutlook]}>{stock.aiOutlook}</Badge>
      </div>

      <div className="flex items-end justify-between">
        <div>
          <Price value={stock.price} size="md" />
          <div className="mt-1">
            <ChangeText value={stock.changePct} size="sm" />
          </div>
        </div>
        <div className="h-10 w-24">
          <SparklineChart data={stock.sparkline} height={40} positive={stock.changePct >= 0} />
        </div>
      </div>

      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        <span>{stock.sector}</span>
        <span className="tabular-nums">Conf {stock.confidence}</span>
      </div>
    </Link>
  );
}
