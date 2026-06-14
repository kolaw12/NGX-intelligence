import { useState } from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { useStocks, useTopGainers, useTopLosers, useMostActive } from "@/hooks/useStocks";
import { useMarketOverview } from "@/hooks/useMarketOverview";
import { useSectors } from "@/hooks/useSectors";
import { StockRow } from "@/components/market/StockRow";
import { HeatmapChart } from "@/components/charts/HeatmapChart";
import { SectorBarChart } from "@/components/charts/SectorBarChart";
import { MetricCard } from "@/components/market/MetricCard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Activity, ChartCandlestick, Layers, Search, TrendingDown, TrendingUp, Zap } from "lucide-react";
import { CardSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";

export default function Markets() {
  const [query, setQuery] = useState("");
  const overview = useMarketOverview();
  const stocks = useStocks();
  const gainers = useTopGainers(8);
  const losers = useTopLosers(8);
  const active = useMostActive(8);
  const sectors = useSectors();

  const filtered = (stocks.data ?? []).filter(
    (s) => s.symbol.toLowerCase().includes(query.toLowerCase()) || s.name.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Markets"
        title="NGX market intelligence"
        description="Aggregate market overview, heatmaps, sector momentum, and top movers across the Nigerian Exchange."
      />

      {overview.data && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="ASI"
            value={overview.data.asi === null ? "Unavailable" : overview.data.asi.toLocaleString("en-NG", { maximumFractionDigits: 2 })}
            change={overview.data.asiChangePct ?? undefined}
            icon={ChartCandlestick}
            accent="cyan"
          />
          <MetricCard
            label="Market Cap"
            value={overview.data.totalMarketCap === null ? "Unavailable" : `NGN ${(overview.data.totalMarketCap / 1e12).toFixed(2)}T`}
            change={overview.data.asiChangePct ?? undefined}
            icon={Layers}
            accent="gold"
          />
          <MetricCard
            label="Volume"
            value={`${(overview.data.totalVolume / 1e6).toFixed(1)}M`}
            icon={Activity}
            helper={`₦${(overview.data.totalValue / 1e9).toFixed(2)}B traded`}
          />
          <MetricCard
            label="Deals"
            value={overview.data.deals === null ? "Unavailable" : overview.data.deals.toLocaleString()}
            icon={Zap}
            helper={`${overview.data.advancing} up / ${overview.data.declining} down`}
          />
        </div>
      )}

      <Tabs defaultValue="heatmap" className="space-y-4">
        <TabsList>
          <TabsTrigger value="heatmap">Heatmap</TabsTrigger>
          <TabsTrigger value="sectors">Sector momentum</TabsTrigger>
          <TabsTrigger value="movers">Movers</TabsTrigger>
          <TabsTrigger value="all">All equities</TabsTrigger>
        </TabsList>

        <TabsContent value="heatmap">
          <Card>
            <CardHeader>
              <CardTitle>Market heatmap</CardTitle>
              <CardDescription>Daily performance across sectors and constituents</CardDescription>
            </CardHeader>
            <CardContent>
              {stocks.data ? <HeatmapChart stocks={stocks.data} /> : <CardSkeleton rows={6} />}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="sectors">
          <Card>
            <CardHeader>
              <CardTitle>Sector daily performance</CardTitle>
              <CardDescription>Color-coded by direction; ranked by daily move</CardDescription>
            </CardHeader>
            <CardContent>
              <SectorBarChart
                data={(sectors.data ?? []).map((s) => ({ name: s.name, value: s.performanceDay }))}
                height={420}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="movers" className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-success" /> Top gainers
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              {gainers.data?.map((s) => <StockRow key={s.symbol} stock={s} />) ?? <CardSkeleton rows={6} />}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingDown className="h-4 w-4 text-danger" /> Top losers
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              {losers.data?.map((s) => <StockRow key={s.symbol} stock={s} />) ?? <CardSkeleton rows={6} />}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-cyan" /> Most active
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              {active.data?.map((s) => <StockRow key={s.symbol} stock={s} />) ?? <CardSkeleton rows={6} />}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="all">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>All equities</CardTitle>
                  <CardDescription>{filtered.length} instruments</CardDescription>
                </div>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Search symbol or company..."
                    className="pl-9 w-72"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {filtered.length === 0 ? (
                <EmptyState icon={Search} title="No matches" description="Try a different symbol or company name." />
              ) : (
                <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
                  {filtered.map((s) => (
                    <StockRow key={s.symbol} stock={s} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
