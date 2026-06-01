import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useMarketOverview } from "@/hooks/useMarketOverview";
import { useTopGainers, useTopLosers } from "@/hooks/useStocks";
import { useSectors } from "@/hooks/useSectors";
import { useMacroIndicators } from "@/hooks/useMacroIndicators";
import { useMarketSentiment } from "@/hooks/useAIInsights";
import { useAlerts } from "@/hooks/useAlerts";
import { useWatchlists } from "@/hooks/useWatchlist";

import { PageHeader } from "@/components/common/PageHeader";
import { MetricCard } from "@/components/market/MetricCard";
import { StockRow } from "@/components/market/StockRow";
import { MarketBreadthCard } from "@/components/market/MarketBreadthCard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CardSkeleton, ChartSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorFallback } from "@/components/common/ErrorFallback";
import { EmptyState } from "@/components/common/EmptyState";
import { Compact } from "@/components/common/NumberFormat";
import { useAuth } from "@/hooks/useAuth";
import {
  Activity,
  ChartCandlestick,
  Layers,
  TrendingUp,
  TrendingDown,
  Landmark,
  BellRing,
  BrainCircuit,
  ArrowRight,
  WalletCards,
  RefreshCw,
} from "lucide-react";
import { Link } from "react-router-dom";
import { ROUTES } from "@/constants/routes";
import { Button } from "@/components/ui/button";
import { qk } from "@/constants/query-keys";

const SectorBarChart = lazy(() =>
  import("@/components/charts/SectorBarChart").then((module) => ({ default: module.SectorBarChart })),
);
const GaugeChart = lazy(() =>
  import("@/components/charts/GaugeChart").then((module) => ({ default: module.GaugeChart })),
);

export default function Dashboard() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [loadInsights, setLoadInsights] = useState(false);
  const overview = useMarketOverview();
  const gainers = useTopGainers(5);
  const losers = useTopLosers(5);
  const sectors = useSectors();
  const macro = useMacroIndicators();
  const sentiment = useMarketSentiment({ enabled: loadInsights });
  const alerts = useAlerts();
  const watchlists = useWatchlists();
  const dashboardQueries = useMemo(
    () => [overview, gainers, losers, sectors, macro, sentiment, alerts, watchlists],
    [overview, gainers, losers, sectors, macro, sentiment, alerts, watchlists],
  );
  const isRefreshing = dashboardQueries.some((query) => query.isFetching && !query.isLoading);
  const sectorChartData = useMemo(
    () => (sectors.data ?? []).map((s) => ({ name: s.name, value: s.performanceDay })),
    [sectors.data],
  );
  const lastUpdated = useMemo(() => {
    const latest = Math.max(...dashboardQueries.map((query) => query.dataUpdatedAt).filter(Boolean));
    if (!Number.isFinite(latest) || latest <= 0) return "not updated yet";
    return new Intl.DateTimeFormat("en-NG", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(latest));
  }, [dashboardQueries]);

  useEffect(() => {
    const id = window.setTimeout(() => setLoadInsights(true), 400);
    return () => window.clearTimeout(id);
  }, []);

  const refreshDashboard = () => {
    queryClient.invalidateQueries({ queryKey: qk.marketOverview });
    queryClient.invalidateQueries({ queryKey: qk.topMovers });
    queryClient.invalidateQueries({ queryKey: qk.sectors });
    queryClient.invalidateQueries({ queryKey: qk.macroIndicators });
    queryClient.invalidateQueries({ queryKey: qk.marketSentiment });
    queryClient.invalidateQueries({ queryKey: qk.watchlists });
    queryClient.invalidateQueries({ queryKey: qk.alerts });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Overview"
        title={`Welcome back, ${user?.name?.split(" ")[0] ?? "Analyst"}`}
        description="Real-time NGX market intelligence, sector momentum, and AI outlooks — at a glance."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {isRefreshing ? "Refreshing..." : `Last updated ${lastUpdated}`}
            </span>
            <Button variant="outline" size="sm" onClick={refreshDashboard} disabled={isRefreshing}>
              <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to={ROUTES.markets}>
                View markets <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        }
      />

      {/* Top metrics */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {overview.isLoading ? (
          <>
            <CardSkeleton rows={1} />
            <CardSkeleton rows={1} />
            <CardSkeleton rows={1} />
            <CardSkeleton rows={1} />
          </>
        ) : overview.isError ? (
          <ErrorFallback message="Couldn't load market overview." onRetry={overview.refetch} />
        ) : overview.data ? (
          <>
            <MetricCard
              label="NGX ASI"
              value={overview.data.asi === null ? "Unavailable" : overview.data.asi.toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
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
              helper={overview.data.deals === null ? "Deals unavailable" : `${overview.data.deals.toLocaleString()} deals`}
            />
            <MetricCard
              label="Breadth"
              value={`${overview.data.advancing} / ${overview.data.declining}`}
              icon={TrendingUp}
              helper="Advancing · declining"
              accent="cyan"
            />
          </>
        ) : null}
      </div>

      {/* Main grid */}
      <div className="grid gap-6 xl:grid-cols-3">
        {/* Sector chart */}
        <Card className="xl:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Sector performance</CardTitle>
                <CardDescription>Daily change across NGX sectors</CardDescription>
              </div>
              <Button asChild variant="ghost" size="sm">
                <Link to={ROUTES.sectors}>
                  All sectors <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {sectors.isLoading ? (
              <ChartSkeleton />
            ) : sectors.isError ? (
              <ErrorFallback message="Sector data unavailable." onRetry={sectors.refetch} />
            ) : (
              <Suspense fallback={<ChartSkeleton />}>
                <SectorBarChart
                  data={sectorChartData}
                  height={320}
                />
              </Suspense>
            )}
          </CardContent>
        </Card>

        {/* Sentiment */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BrainCircuit className="h-4 w-4 text-cyan" /> AI market sentiment
            </CardTitle>
            <CardDescription>
              {sentiment.data?.source === "sentiment_pipeline_json" || sentiment.data?.source === "nlp_engine"
                ? "NLP news sentiment from processed articles"
                : "NLP-first sentiment with market fallback"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {sentiment.isLoading ? (
              <ChartSkeleton height={200} />
            ) : sentiment.data ? (
              <>
                <Suspense fallback={<ChartSkeleton height={200} />}>
                  <GaugeChart value={sentiment.data.score} label={sentiment.data.label} height={200} />
                </Suspense>
                <p className="text-xs leading-relaxed text-muted-foreground">{sentiment.data.summary}</p>
              </>
            ) : (
              <ErrorFallback message="Sentiment unavailable." onRetry={sentiment.refetch} />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Movers */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-success" /> Top gainers
            </CardTitle>
            <CardDescription>Largest daily movers</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {gainers.data?.map((s) => (
              <StockRow key={s.symbol} stock={s} />
            )) ?? <CardSkeleton rows={5} />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-danger" /> Top losers
            </CardTitle>
            <CardDescription>Largest daily declines</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {losers.data?.map((s) => (
              <StockRow key={s.symbol} stock={s} />
            )) ?? <CardSkeleton rows={5} />}
          </CardContent>
        </Card>
      </div>

      {/* Macro + breadth */}
      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Landmark className="h-4 w-4 text-gold" /> Macroeconomic indicators
            </CardTitle>
            <CardDescription>CBN · NBS · FMDQ — latest values</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {macro.data?.slice(0, 8).map((m) => (
                <div key={m.key} className="rounded-lg border border-border bg-surface-elevated/60 p-3">
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{m.label}</p>
                  <p className="mt-1 text-base font-semibold tabular-nums text-foreground">
                    {m.unit === "₦" || m.unit === "$" ? `${m.unit}${m.value.toLocaleString()}` : `${m.value}${m.unit}`}
                  </p>
                  <p className={`text-[11px] tabular-nums ${m.changePct >= 0 ? "text-success" : "text-danger"}`}>
                    {m.changePct > 0 ? "+" : ""}
                    {m.changePct.toFixed(2)}%
                  </p>
                </div>
              )) ?? <CardSkeleton rows={4} />}
            </div>
          </CardContent>
        </Card>
        {overview.data && <MarketBreadthCard data={overview.data} />}
      </div>

      {/* Watchlists + Alerts */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <WalletCards className="h-4 w-4 text-cyan" /> Watchlists
              </CardTitle>
              <Button asChild variant="ghost" size="sm">
                <Link to={ROUTES.watchlists}>
                  Manage <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            </div>
            <CardDescription>Quick access to tracked instruments</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {watchlists.data?.slice(0, 3).map((wl) => (
              <div
                key={wl.id}
                className="flex items-center justify-between rounded-lg border border-border bg-surface-elevated/40 px-3 py-2.5"
              >
                <div>
                  <p className="text-sm font-semibold text-foreground">{wl.name}</p>
                  <p className="text-[11px] text-muted-foreground">{wl.symbols.length} symbols</p>
                </div>
                <div className="flex gap-1.5">
                  {wl.symbols.slice(0, 4).map((s) => (
                    <span key={s} className="rounded-md bg-surface px-2 py-0.5 text-[11px] text-foreground">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )) ?? <EmptyState icon={WalletCards} title="No watchlists yet" />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <BellRing className="h-4 w-4 text-gold" /> Recent alerts
              </CardTitle>
              <Button asChild variant="ghost" size="sm">
                <Link to={ROUTES.alerts}>
                  All alerts <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            </div>
            <CardDescription>Triggered & active alerts</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {alerts.data?.slice(0, 4).map((a) => (
              <div
                key={a.id}
                className="flex items-center justify-between rounded-lg border border-border bg-surface-elevated/40 px-3 py-2.5"
              >
                <div>
                  <p className="text-sm font-semibold text-foreground">{a.symbol}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {a.condition.replace("-", " ")} {a.condition === "above" || a.condition === "below" ? `₦${a.threshold}` : ""}
                  </p>
                </div>
                <Badge variant={a.status === "triggered" ? "gold" : "default"}>{a.status}</Badge>
              </div>
            )) ?? <EmptyState icon={BellRing} title="No alerts configured" />}
          </CardContent>
        </Card>
      </div>

      {/* Aggregate footer */}
      {overview.data && (
        <div className="rounded-xl border border-border bg-surface/60 p-5">
          <div className="grid gap-6 sm:grid-cols-4">
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Total value traded</p>
              <Compact value={overview.data.totalValue} prefix="₦" className="text-lg" />
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Deals</p>
              <p className="text-lg font-semibold tabular-nums text-foreground">
                {overview.data.deals === null ? "Unavailable" : overview.data.deals.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Volume</p>
              <Compact value={overview.data.totalVolume} className="text-lg" />
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Status</p>
              <p className="text-lg font-semibold capitalize text-foreground">{overview.data.marketStatus}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
