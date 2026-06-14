import { Link, useParams, useSearchParams } from "react-router-dom";
import { useState } from "react";
import { ArrowLeft, BellRing, Plus, Check, Building2, Globe, Users, CalendarDays, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { useStock, useStockOHLC, useStockFundamentals, useStockPeers } from "@/hooks/useStock";
import { useAIInsight, useNews } from "@/hooks/useAIInsights";
import { useCreateAlert } from "@/hooks/useAlerts";
import { useAddToWatchlist, useRemoveFromWatchlist, useWatchlists } from "@/hooks/useWatchlist";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { PredictionBadge } from "@/components/ai/PredictionBadge";
import { ConfidenceMeter } from "@/components/ai/ConfidenceMeter";
import { ExplainabilityPanel } from "@/components/ai/ExplainabilityPanel";
import { RiskScoreCard } from "@/components/ai/RiskScoreCard";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import { Price, ChangeText, Compact } from "@/components/common/NumberFormat";
import { CardSkeleton, ChartSkeleton, TableSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorFallback } from "@/components/common/ErrorFallback";
import { ROUTES } from "@/constants/routes";
import { cn } from "@/lib/cn";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Range } from "@/types/common";
import type { NewsItem } from "@/types/ai";
import { formatRelative } from "@/lib/format";

const RANGES: Range[] = ["1D", "5D", "1M", "3M", "6M", "1Y", "5Y", "MAX"];

export default function StockDetail() {
  const { symbol = "" } = useParams();
  const sym = symbol.toUpperCase();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get("tab") ?? "overview";
  const [range, setRange] = useState<Range>("3M");

  const stock = useStock(sym);
  const ohlc = useStockOHLC(sym, range);
  const insight = useAIInsight(sym);
  const fundamentals = useStockFundamentals(sym);
  const peers = useStockPeers(sym);
  const news = useNews(sym);
  const marketNews = useNews();
  const watchlists = useWatchlists();
  const defaultWatchlist = watchlists.data?.[0];
  const isTracked = Boolean(defaultWatchlist?.symbols.includes(sym));
  const addToWatchlist = useAddToWatchlist();
  const removeFromWatchlist = useRemoveFromWatchlist();
  const createAlert = useCreateAlert();
  const displayedOutlook = insight.data?.outlook ?? stock.data?.aiOutlook;
  const displayedConfidence = insight.data?.confidence ?? stock.data?.confidence;

  function handleWatch() {
    const watchlistId = defaultWatchlist?.id ?? "default";
    if (isTracked) {
      removeFromWatchlist.mutate(
        { id: watchlistId, symbol: sym },
        { onSuccess: () => toast.success(`Removed ${sym} from watchlist`) },
      );
    } else {
      addToWatchlist.mutate(
        { id: watchlistId, symbol: sym },
        { onSuccess: () => toast.success(`Added ${sym} to watchlist`) },
      );
    }
  }

  function handleQuickAlert() {
    if (!stock.data) return;
    const threshold = Number((stock.data.price * 1.05).toFixed(2));
    createAlert.mutate(
      { symbol: sym, condition: "above", threshold },
      { onSuccess: () => toast.success(`Alert set: notify when ${sym} crosses ₦${threshold}`) },
    );
  }

  function setTab(value: string) {
    setSearchParams({ tab: value });
  }

  if (stock.isError) {
    return (
      <div className="space-y-4">
        <Button asChild variant="ghost" size="sm">
          <Link to={ROUTES.stocks}>
            <ArrowLeft className="h-4 w-4" /> Back to stocks
          </Link>
        </Button>
        <ErrorFallback message={`Could not load ${sym}.`} onRetry={stock.refetch} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="w-fit">
        <Link to={ROUTES.stocks}>
          <ArrowLeft className="h-4 w-4" /> Back to stocks
        </Link>
      </Button>

      {/* Sticky header */}
      <div className="sticky top-16 z-20 -mx-4 border-y border-border bg-surface/95 px-4 py-4 backdrop-blur-xl lg:-mx-8 lg:px-8">
        {stock.isLoading || !stock.data ? (
          <CardSkeleton rows={1} />
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-cyan/12 text-cyan-700 ring-1 ring-cyan/30">
                <span className="text-sm font-semibold">{stock.data.symbol.slice(0, 3)}</span>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-semibold tracking-tight text-foreground">{stock.data.symbol}</h1>
                  <Badge variant="royal">{stock.data.sector}</Badge>
                  {displayedOutlook && <PredictionBadge outlook={displayedOutlook} />}
                </div>
                <p className="text-sm text-muted-foreground">{stock.data.name}</p>
              </div>
            </div>
            <div className="flex items-end gap-6">
              <div>
                <Price value={stock.data.price} size="xl" />
                <div className="mt-1 flex items-center gap-3">
                  <ChangeText value={stock.data.changePct} variant="both" />
                  {stock.data.dataAsOf && (
                    <span className="text-[10px] text-muted-foreground">as of {stock.data.dataAsOf}</span>
                  )}
                </div>
              </div>
              <div className="hidden lg:block min-w-[160px]">
                <ConfidenceMeter value={displayedConfidence ?? 0} label="AI confidence" />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  onClick={handleWatch}
                  variant={isTracked ? "outline" : "secondary"}
                  size="sm"
                  disabled={addToWatchlist.isPending || removeFromWatchlist.isPending}
                >
                  {isTracked ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                  {isTracked ? "Tracking" : "Add to watchlist"}
                </Button>
                <Button onClick={handleQuickAlert} variant="primary" size="sm">
                  <BellRing className="h-4 w-4" /> Set alert
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Event severity / regime alert banner */}
      {insight.data && (insight.data.regimeAlert || (insight.data.eventSeverity && insight.data.eventSeverity !== "NORMAL")) && (
        <div
          className={cn(
            "flex items-start gap-3 rounded-lg border px-4 py-3 text-sm",
            insight.data.eventSeverity === "CRITICAL"
              ? "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-400"
              : "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
          )}
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="min-w-0">
            <p className="font-semibold">
              {insight.data.eventSeverity === "CRITICAL"
                ? "Critical market event detected"
                : insight.data.regimeAlert
                  ? "Abnormal volatility regime"
                  : "High-impact news event detected"}
            </p>
            <p className="mt-0.5 text-xs opacity-80">
              {insight.data.eventAlerts?.[0]?.replace(/^'|'$/g, "") ??
                insight.data.regimeReason ??
                "Unusual market conditions detected. Model confidence is reduced until conditions normalise."}
            </p>
            {insight.data.eventSeverity === "CRITICAL" && (
              <p className="mt-1 text-xs font-medium opacity-90">
                All directional signals are suspended. Do not act on BUY or SELL until this event resolves.
              </p>
            )}
          </div>
        </div>
      )}

      <Tabs value={tab} onValueChange={setTab} className="space-y-5">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="ai">AI Analysis</TabsTrigger>
          <TabsTrigger value="fundamentals">Fundamentals</TabsTrigger>
          <TabsTrigger value="sector">Sector</TabsTrigger>
          <TabsTrigger value="news">News</TabsTrigger>
        </TabsList>

        {/* OVERVIEW */}
        <TabsContent value="overview" className="space-y-5">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>Price chart</CardTitle>
                  <CardDescription>Candlestick view with volume sub-pane</CardDescription>
                </div>
                <div className="inline-flex rounded-lg border border-border bg-surface/60 p-0.5">
                  {RANGES.map((r) => (
                    <button
                      key={r}
                      onClick={() => setRange(r)}
                      className={cn(
                        "rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors",
                        range === r ? "bg-navy text-white shadow-card" : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {ohlc.isLoading ? (
                <ChartSkeleton height={420} />
              ) : ohlc.isError ? (
                <ErrorFallback message="Chart data unavailable." onRetry={ohlc.refetch} />
              ) : (
                <CandlestickChart data={ohlc.data ?? []} height={420} />
              )}
            </CardContent>
          </Card>

          <div className="grid gap-5 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Key statistics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5 text-sm">
                {stock.data ? (
                  <>
                    <Stat label="Market cap" value={<Compact value={stock.data.marketCap} prefix="₦" />} />
                    <Stat label="P/E (TTM)" value={formatNullable(stock.data.pe)} />
                    <Stat label="Dividend yield" value={stock.data.dividendYield === null ? "—" : `${stock.data.dividendYield.toFixed(2)}%`} />
                    <Stat label="Beta" value={formatNullable(stock.data.beta)} />
                    <Stat label="52w high" value={`₦${stock.data.high52w.toFixed(2)}`} />
                    <Stat label="52w low" value={`₦${stock.data.low52w.toFixed(2)}`} />
                    <Stat label="Volume" value={<Compact value={stock.data.volume} />} />
                    <Stat label="Sector rank" value={stock.data.sectorRank === null ? "—" : `#${stock.data.sectorRank}`} />
                  </>
                ) : <CardSkeleton rows={6} />}
              </CardContent>
            </Card>

            {insight.data && (
              <Card>
                <CardHeader>
                  <CardTitle>AI outlook</CardTitle>
                  <CardDescription>{insight.data.horizonDays}-day horizon · {insight.data.modelVersion}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <PredictionBadge outlook={insight.data.outlook} />
                  <ConfidenceMeter value={insight.data.confidence} />
                  <ul className="space-y-1.5">
                    {insight.data.drivers.slice(0, 3).map((d) => (
                      <li key={d.label} className="flex items-start gap-2 text-xs text-foreground">
                        <span
                          className={cn(
                            "mt-1 h-1.5 w-1.5 rounded-full",
                            d.direction === "positive" && "bg-success",
                            d.direction === "negative" && "bg-danger",
                            d.direction === "neutral" && "bg-muted-foreground",
                          )}
                        />
                        <span>{d.label}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}

            {insight.data && (
              <RiskScoreCard
                total={insight.data.risks.marketRisk + insight.data.risks.sectorRisk + insight.data.risks.companyRisk}
                decomposition={insight.data.risks}
              />
            )}
          </div>

          {stock.data && (
            <Card>
              <CardHeader>
                <CardTitle>Company profile</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <p className="md:col-span-2 lg:col-span-3 text-sm leading-relaxed text-muted-foreground">
                  {stock.data.description}
                </p>
                <Stat icon={Building2} label="Headquarters" value={stock.data.headquarters ?? "—"} />
                <Stat icon={CalendarDays} label="Founded" value={stock.data.founded ?? "—"} />
                <Stat icon={Users} label="Employees" value={stock.data.employees === null ? "—" : stock.data.employees.toLocaleString()} />
                <Stat label="CEO" value={stock.data.ceo ?? "—"} />
                <Stat label="Industry" value={stock.data.industry} />
                <Stat
                  icon={Globe}
                  label="Website"
                  value={
                    stock.data.website ? (
                      <a href={stock.data.website} className="text-cyan hover:text-cyan-300" target="_blank" rel="noreferrer">
                        {stock.data.website.replace(/^https?:\/\//, "")}
                      </a>
                    ) : "—"
                  }
                />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* AI */}
        <TabsContent value="ai">
          {insight.data ? <ExplainabilityPanel insight={insight.data} /> : <CardSkeleton rows={6} />}
        </TabsContent>

        {/* FUNDAMENTALS */}
        <TabsContent value="fundamentals">
          <Card>
            <CardHeader>
              <CardTitle>Financial fundamentals</CardTitle>
              <CardDescription>
                {stock.data?.fundamentalsSource && stock.data.fundamentalsSource !== "unavailable"
                  ? `Source: ${stock.data.fundamentalsSource}`
                  : "Real fundamentals export unavailable; showing market-data metrics only."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {fundamentals.isLoading ? (
                <TableSkeleton rows={7} />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Metric</TableHead>
                      <TableHead className="text-right">FY 2021</TableHead>
                      <TableHead className="text-right">FY 2022</TableHead>
                      <TableHead className="text-right">FY 2023</TableHead>
                      <TableHead className="text-right">TTM</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {fundamentals.data?.map((row) => (
                      <TableRow key={row.metric}>
                        <TableCell className="font-medium text-foreground">{row.metric}</TableCell>
                        <TableCell className="text-right">{row.fy2021}</TableCell>
                        <TableCell className="text-right">{row.fy2022}</TableCell>
                        <TableCell className="text-right">{row.fy2023}</TableCell>
                        <TableCell className="text-right font-semibold text-foreground">{row.ttm}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* SECTOR */}
        <TabsContent value="sector">
          <Card>
            <CardHeader>
              <CardTitle>Peer comparison</CardTitle>
              <CardDescription>Sector peers ranked by market cap</CardDescription>
            </CardHeader>
            <CardContent>
              {peers.isLoading ? (
                <TableSkeleton rows={5} />
              ) : (peers.data?.length ?? 0) === 0 ? (
                <p className="text-sm text-muted-foreground">No peer instruments tracked.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Symbol</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead className="text-right">Price</TableHead>
                      <TableHead className="text-right">Change</TableHead>
                      <TableHead className="text-right">Market cap</TableHead>
                      <TableHead className="text-right">P/E</TableHead>
                      <TableHead>AI outlook</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {peers.data?.map((p) => (
                      <TableRow key={p.symbol}>
                        <TableCell>
                          <Link to={ROUTES.stockDetail(p.symbol)} className="font-semibold text-foreground hover:text-cyan">
                            {p.symbol}
                          </Link>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{p.name}</TableCell>
                        <TableCell className="text-right">₦{p.price.toFixed(2)}</TableCell>
                        <TableCell className="text-right"><ChangeText value={p.changePct} size="sm" /></TableCell>
                        <TableCell className="text-right"><Compact value={p.marketCap} prefix="₦" /></TableCell>
                        <TableCell className="text-right">{formatNullable(p.pe)}</TableCell>
                        <TableCell><PredictionBadge outlook={p.aiOutlook} withIcon={false} /></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* NEWS */}
        <TabsContent value="news">
          <Card>
            <CardHeader>
              <CardTitle>Recent news</CardTitle>
              <CardDescription>Headlines tagged with sentiment</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {news.isLoading ? (
                <CardSkeleton rows={3} />
              ) : news.isError ? (
                <ErrorFallback message={`Could not load news for ${sym}.`} onRetry={news.refetch} />
              ) : (news.data?.length ?? 0) === 0 ? (
                <>
                  <div className="rounded-lg border border-border bg-surface-elevated/40 p-4">
                    <p className="text-sm font-semibold text-foreground">No ticker-specific news for {sym}.</p>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      Showing latest market headlines instead. These are real backend news items, but they are not tagged directly to this symbol.
                    </p>
                  </div>
                  {marketNews.isLoading ? (
                    <CardSkeleton rows={3} />
                  ) : marketNews.isError ? (
                    <ErrorFallback message="Could not load latest market headlines." onRetry={marketNews.refetch} />
                  ) : (marketNews.data?.length ?? 0) === 0 ? (
                    <p className="text-sm text-muted-foreground">No market news available.</p>
                  ) : (
                    marketNews.data?.slice(0, 8).map((n) => <NewsCard key={n.id} item={n} marketFallback />)
                  )}
                </>
              ) : (
                news.data?.map((n) => (
                  <div key={n.id} className="rounded-lg border border-border bg-surface-elevated/40 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Badge
                        variant={n.sentiment === "positive" ? "success" : n.sentiment === "negative" ? "danger" : "default"}
                      >
                        {n.sentiment}
                      </Badge>
                      <p className="text-[11px] text-muted-foreground">{n.source} · {formatRelative(n.publishedAt)}</p>
                    </div>
                    <p className="mt-2 text-sm font-semibold text-foreground">{n.headline}</p>
                    <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{n.summary}</p>
                    {(n.eventTags?.length ?? 0) > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {n.eventTags?.slice(0, 4).map((tag) => (
                          <Badge key={tag} variant="outline" className="text-[10px]">
                            {tag.replace(/_/g, " ")}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <p className="rounded-lg border border-border/50 bg-surface-elevated/30 px-4 py-3 text-[11px] leading-relaxed text-muted-foreground">
        <span className="font-semibold text-foreground">Disclaimer:</span> This platform provides AI-assisted market analysis for
        educational and decision-support purposes only. It does not constitute financial advice. Investors should conduct their
        own research or consult a licensed financial adviser before making investment decisions. AI signals are probabilistic
        and do not guarantee future performance.
      </p>
    </div>
  );
}

function Stat({ label, value, icon: Icon }: { label: string; value: React.ReactNode; icon?: typeof Building2 }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/60 py-1.5 last:border-0">
      <span className="flex items-center gap-2 text-xs text-muted-foreground">
        {Icon && <Icon className="h-3.5 w-3.5" />}
        {label}
      </span>
      <span className="text-sm font-semibold text-foreground">{value}</span>
    </div>
  );
}

function NewsCard({ item, marketFallback = false }: { item: NewsItem; marketFallback?: boolean }) {
  return (
    <div className="rounded-lg border border-border bg-surface-elevated/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={item.sentiment === "positive" ? "success" : item.sentiment === "negative" ? "danger" : "default"}>
            {item.sentiment}
          </Badge>
          {marketFallback && (
            <Badge variant="outline" className="text-[10px]">
              market-wide
            </Badge>
          )}
        </div>
        <p className="text-[11px] text-muted-foreground">
          {item.source.replace(/_/g, " ")} · {formatRelative(item.publishedAt)}
        </p>
      </div>
      <a href={item.url} target="_blank" rel="noreferrer" className="mt-2 block text-sm font-semibold text-foreground hover:text-cyan">
        {item.headline}
      </a>
      <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{item.summary}</p>
      {(item.eventTags?.length ?? 0) > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {item.eventTags?.slice(0, 4).map((tag) => (
            <Badge key={tag} variant="outline" className="text-[10px]">
              {tag.replace(/_/g, " ")}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

function formatNullable(value: number | null | undefined, fractionDigits = 2): string {
  return value === null || value === undefined ? "—" : value.toFixed(fractionDigits);
}
