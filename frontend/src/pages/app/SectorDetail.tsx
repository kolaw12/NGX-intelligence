import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Layers, ShieldCheck, TrendingUp } from "lucide-react";
import { useSector } from "@/hooks/useSectors";
import { useStocksBySector } from "@/hooks/useStocks";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StockCard } from "@/components/market/StockCard";
import { ChangeText, Compact } from "@/components/common/NumberFormat";
import { CardSkeleton, ChartSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorFallback } from "@/components/common/ErrorFallback";
import { LineChart } from "@/components/charts/LineChart";
import { ROUTES } from "@/constants/routes";
import { Button } from "@/components/ui/button";

export default function SectorDetail() {
  const { slug = "" } = useParams();
  const sector = useSector(slug);
  const stocks = useStocksBySector(slug);

  if (sector.isError) {
    return <ErrorFallback message="Sector not found." onRetry={sector.refetch} />;
  }

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="w-fit">
        <Link to={ROUTES.sectors}>
          <ArrowLeft className="h-4 w-4" /> Back to sectors
        </Link>
      </Button>

      {sector.isLoading || !sector.data ? (
        <CardSkeleton rows={4} />
      ) : (
        <>
          <PageHeader
            eyebrow="Sector intelligence"
            title={sector.data.name}
            description={sector.data.summary}
            actions={
              <Badge variant={sector.data.aiOutlook === "bullish" ? "success" : sector.data.aiOutlook === "bearish" ? "danger" : "default"}>
                AI · {sector.data.aiOutlook}
              </Badge>
            }
          />

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-border bg-surface/80 p-4">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Day</p>
              <div className="mt-2 text-xl"><ChangeText value={sector.data.performanceDay} variant="percent" /></div>
            </div>
            <div className="rounded-xl border border-border bg-surface/80 p-4">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Week</p>
              <div className="mt-2 text-xl"><ChangeText value={sector.data.performanceWeek} variant="percent" /></div>
            </div>
            <div className="rounded-xl border border-border bg-surface/80 p-4">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Month</p>
              <div className="mt-2 text-xl"><ChangeText value={sector.data.performanceMonth} variant="percent" /></div>
            </div>
            <div className="rounded-xl border border-border bg-surface/80 p-4">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">YTD</p>
              <div className="mt-2 text-xl"><ChangeText value={sector.data.performanceYtd} variant="percent" /></div>
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle>Sector momentum</CardTitle>
                <CardDescription>Indexed sector performance</CardDescription>
              </CardHeader>
              <CardContent>
                {sector.data ? (
                  <LineChart
                    data={sector.data.sparkline.map((v, i) => ({
                      time: new Date(Date.now() - (sector.data!.sparkline.length - i) * 86400000).toISOString(),
                      value: v,
                    }))}
                    height={300}
                  />
                ) : (
                  <ChartSkeleton />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Sector summary</CardTitle>
                <CardDescription>Key dimensions</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground inline-flex items-center gap-2">
                    <Layers className="h-3.5 w-3.5" /> Market cap
                  </span>
                  <Compact value={sector.data.marketCap} prefix="₦" />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground inline-flex items-center gap-2">
                    <TrendingUp className="h-3.5 w-3.5 text-cyan" /> Momentum
                  </span>
                  <span className="tabular-nums font-semibold text-foreground">{sector.data.momentum}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground inline-flex items-center gap-2">
                    <ShieldCheck className="h-3.5 w-3.5 text-gold" /> Risk score
                  </span>
                  <span className="tabular-nums font-semibold text-foreground">{sector.data.riskScore}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Constituents</span>
                  <span className="tabular-nums font-semibold text-foreground">{sector.data.componentCount}</span>
                </div>
              </CardContent>
            </Card>
          </div>

          <div>
            <h2 className="mb-4 text-base font-semibold text-foreground">Constituent instruments</h2>
            {stocks.isLoading ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <CardSkeleton key={i} rows={3} />
                ))}
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {stocks.data?.map((s) => (
                  <StockCard key={s.symbol} stock={s} />
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
