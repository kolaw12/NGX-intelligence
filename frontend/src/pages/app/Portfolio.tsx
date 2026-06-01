import { Link } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import { usePortfolio } from "@/hooks/usePortfolio";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MetricCard } from "@/components/market/MetricCard";
import { AllocationDonut } from "@/components/charts/AllocationDonut";
import { LineChart } from "@/components/charts/LineChart";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ChangeText, Compact, Price } from "@/components/common/NumberFormat";
import { PredictionBadge } from "@/components/ai/PredictionBadge";
import { CardSkeleton, ChartSkeleton, TableSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorFallback } from "@/components/common/ErrorFallback";
import { ROUTES } from "@/constants/routes";
import { BriefcaseBusiness, ShieldCheck, Sparkles, TrendingUp, WalletCards } from "lucide-react";

export default function Portfolio() {
  const p = usePortfolio();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Portfolio"
        title="Portfolio intelligence"
        description="Allocation analytics, performance attribution, risk scoring, and diversification metrics — read-only intelligence."
      />

      {p.isLoading ? (
        <CardSkeleton rows={4} />
      ) : p.isError ? (
        <ErrorFallback
          message="Portfolio intelligence could not load. Sign in again if your session expired, then retry."
          onRetry={() => p.refetch()}
        />
      ) : !p.data ? (
        <EmptyState icon={WalletCards} title="Portfolio unavailable" description="No portfolio response was returned by the backend." />
      ) : p.data.holdings.length === 0 ? (
        <EmptyState
          icon={WalletCards}
          title="No portfolio positions yet"
          description="Add portfolio positions through the backend API to generate allocation, performance, and risk intelligence."
        />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Total value"
              value={`₦${(p.data.totalValue / 1000).toFixed(1)}K`}
              change={p.data.dayChangePct}
              icon={BriefcaseBusiness}
              accent="cyan"
            />
            <MetricCard
              label="Unrealised P&L"
              value={`₦${(p.data.unrealizedPnl / 1000).toFixed(1)}K`}
              change={p.data.unrealizedPnlPct}
              icon={TrendingUp}
              accent="gold"
            />
            <MetricCard
              label="Risk score"
              value={String(p.data.riskScore)}
              icon={ShieldCheck}
              helper={p.data.riskScore < 40 ? "Low" : p.data.riskScore < 65 ? "Moderate" : "Elevated"}
            />
            <MetricCard
              label="Diversification"
              value={String(p.data.diversificationScore)}
              icon={Sparkles}
              helper={p.data.diversificationScore > 70 ? "Healthy spread" : "Concentrated"}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle>Performance · 90 days</CardTitle>
                <CardDescription>Marked-to-market portfolio value</CardDescription>
              </CardHeader>
              <CardContent>
                {p.data ? (
                  <LineChart
                    data={p.data.performanceSeries.map((pt) => ({ time: pt.time, value: pt.value }))}
                    height={300}
                  />
                ) : <ChartSkeleton />}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Sector allocation</CardTitle>
                <CardDescription>By market value weight</CardDescription>
              </CardHeader>
              <CardContent>
                <AllocationDonut data={p.data.allocation.map((a) => ({ name: a.sector, value: a.weight }))} height={300} />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Holdings</CardTitle>
              <CardDescription>Position-level intelligence</CardDescription>
            </CardHeader>
            <CardContent>
              {!p.data ? (
                <TableSkeleton rows={5} />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Symbol</TableHead>
                      <TableHead>Sector</TableHead>
                      <TableHead className="text-right">Units</TableHead>
                      <TableHead className="text-right">Avg cost</TableHead>
                      <TableHead className="text-right">Price</TableHead>
                      <TableHead className="text-right">Value</TableHead>
                      <TableHead className="text-right">P&L</TableHead>
                      <TableHead className="text-right">Weight</TableHead>
                      <TableHead>AI</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {p.data.holdings.map((h) => (
                      <TableRow key={h.symbol}>
                        <TableCell>
                          <Link to={ROUTES.stockDetail(h.symbol)} className="font-semibold text-foreground hover:text-cyan">
                            {h.symbol}
                          </Link>
                          <p className="text-[11px] text-muted-foreground">{h.name}</p>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{h.sector}</TableCell>
                        <TableCell className="text-right">{h.units.toLocaleString()}</TableCell>
                        <TableCell className="text-right">₦{h.avgCost.toFixed(2)}</TableCell>
                        <TableCell className="text-right"><Price value={h.currentPrice} size="sm" /></TableCell>
                        <TableCell className="text-right"><Compact value={h.marketValue} prefix="₦" /></TableCell>
                        <TableCell className="text-right">
                          <ChangeText value={h.unrealizedPnlPct} size="sm" />
                        </TableCell>
                        <TableCell className="text-right text-foreground tabular-nums">{h.allocationPct.toFixed(2)}%</TableCell>
                        <TableCell><PredictionBadge outlook={h.aiOutlook} withIcon={false} /></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
