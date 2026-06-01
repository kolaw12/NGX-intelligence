import { Link } from "react-router-dom";
import type { Sector } from "@/types/sector";
import { ROUTES } from "@/constants/routes";
import { SparklineChart } from "@/components/charts/SparklineChart";
import { Badge } from "@/components/ui/badge";
import { ChangeText, Compact } from "@/components/common/NumberFormat";
import { ShieldCheck, TrendingUp } from "lucide-react";
import { cn } from "@/lib/cn";

interface SectorCardProps {
  sector: Sector;
  className?: string;
}

const outlookVariant: Record<Sector["aiOutlook"], "success" | "danger" | "default"> = {
  bullish: "success",
  bearish: "danger",
  neutral: "default",
};

export function SectorCard({ sector, className }: SectorCardProps) {
  return (
    <Link
      to={ROUTES.sectorDetail(sector.slug)}
      className={cn(
        "group relative flex flex-col gap-4 overflow-hidden rounded-xl border border-border bg-surface/80 p-5 transition-all hover:border-cyan/40 hover:shadow-glow",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold tracking-tight text-foreground">{sector.name}</p>
          <p className="text-[11px] text-muted-foreground">{sector.componentCount} constituents</p>
        </div>
        <Badge variant={outlookVariant[sector.aiOutlook]}>AI · {sector.aiOutlook}</Badge>
      </div>

      <div className="grid grid-cols-3 gap-3 text-xs">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Day</p>
          <ChangeText value={sector.performanceDay} size="sm" />
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Week</p>
          <ChangeText value={sector.performanceWeek} size="sm" />
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">YTD</p>
          <ChangeText value={sector.performanceYtd} size="sm" />
        </div>
      </div>

      <div className="h-16">
        <SparklineChart data={sector.sparkline} height={64} positive={sector.performanceDay >= 0} />
      </div>

      <div className="flex items-center justify-between border-t border-border pt-3 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <TrendingUp className="h-3 w-3 text-cyan" /> Momentum {sector.momentum}
        </span>
        <span className="inline-flex items-center gap-1">
          <ShieldCheck className="h-3 w-3 text-gold" /> Risk {sector.riskScore}
        </span>
        <Compact value={sector.marketCap} prefix="₦" className="text-xs" />
      </div>
    </Link>
  );
}
