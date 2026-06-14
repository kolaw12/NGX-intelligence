import { Link } from "react-router-dom";
import {
  Users,
  ShieldCheck,
  UserPlus,
  Activity,
  BellRing,
  Gauge,
  TriangleAlert,
  WalletCards,
  ArrowRight,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { MetricCard } from "@/components/market/MetricCard";
import { LineChart } from "@/components/charts/LineChart";
import { AllocationDonut } from "@/components/charts/AllocationDonut";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardSkeleton, ChartSkeleton } from "@/components/common/LoadingSkeleton";
import { useAdminMetrics, useAdminActivity } from "@/hooks/useAdmin";
import { ROUTES } from "@/constants/routes";
import { formatRelative } from "@/lib/format";

export default function AdminOverview() {
  const metrics = useAdminMetrics();
  const activity = useAdminActivity();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin"
        title="Platform overview"
        description="Real-time platform health, growth, and operational signals."
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to={ROUTES.adminUsers}>
              Manage users <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        }
      />

      {metrics.isLoading || !metrics.data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} rows={1} />)}
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Total users"
              value={metrics.data.totalUsers.toLocaleString()}
              icon={Users}
              helper={`${metrics.data.activeUsers} active`}
              accent="cyan"
            />
            <MetricCard
              label="Signups (7d)"
              value={metrics.data.newSignups7d.toLocaleString()}
              icon={UserPlus}
              helper={`${metrics.data.newSignupsToday} today`}
              accent="gold"
            />
            <MetricCard
              label="DAU / MAU"
              value={`${metrics.data.dau} / ${metrics.data.mau}`}
              icon={Activity}
              helper={`${((metrics.data.dau / Math.max(metrics.data.mau, 1)) * 100).toFixed(0)}% stickiness`}
            />
            <MetricCard
              label="Suspended"
              value={metrics.data.suspendedUsers.toLocaleString()}
              icon={ShieldCheck}
              helper={metrics.data.suspendedUsers > 0 ? "Review required" : "All clear"}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle>Daily active users · 30d</CardTitle>
                <CardDescription>Authenticated sessions per day</CardDescription>
              </CardHeader>
              <CardContent>
                <LineChart
                  data={metrics.data.dauSeries.map((p) => ({ time: p.date, value: p.count }))}
                  height={260}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>User roles</CardTitle>
                <CardDescription>Distribution across the user base</CardDescription>
              </CardHeader>
              <CardContent>
                <AllocationDonut
                  data={metrics.data.roleBreakdown.map((r) => ({ name: r.role, value: r.count }))}
                  height={260}
                />
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>New signups · 30d</CardTitle>
                <CardDescription>Trend of account creations</CardDescription>
              </CardHeader>
              <CardContent>
                <LineChart
                  data={metrics.data.signupsSeries.map((p) => ({ time: p.date, value: p.count }))}
                  height={220}
                  color="#E89A35"
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Platform health</CardTitle>
                <CardDescription>Last 24 hours</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <HealthRow
                  icon={Gauge}
                  label="API requests (24h)"
                  value={metrics.data.apiRequests24h.toLocaleString()}
                  tone="default"
                />
                <HealthRow
                  icon={TriangleAlert}
                  label="API error rate (24h)"
                  value={`${metrics.data.apiErrorRate24h.toFixed(2)}%`}
                  tone={metrics.data.apiErrorRate24h > 1 ? "danger" : metrics.data.apiErrorRate24h > 0.5 ? "warning" : "success"}
                />
                <HealthRow
                  icon={BellRing}
                  label="Active alerts"
                  value={metrics.data.activeAlerts.toLocaleString()}
                  tone="default"
                />
                <HealthRow
                  icon={BellRing}
                  label="Alerts triggered (today)"
                  value={metrics.data.triggeredAlertsToday.toLocaleString()}
                  tone="default"
                />
                <HealthRow
                  icon={WalletCards}
                  label="Total watchlists"
                  value={metrics.data.totalWatchlists.toLocaleString()}
                  tone="default"
                />
              </CardContent>
            </Card>
          </div>
        </>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Recent activity</CardTitle>
              <CardDescription>Latest user events across the platform</CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link to={ROUTES.adminActivity}>
                View all <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {activity.isLoading ? (
            <ChartSkeleton height={200} />
          ) : (
            <div className="space-y-1.5">
              {activity.data?.slice(0, 8).map((e) => (
                <div
                  key={e.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface-elevated/40 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-foreground">{e.userName}</p>
                    <p className="truncate text-[11px] text-muted-foreground">{e.description} · {e.userEmail}</p>
                  </div>
                  <p className="shrink-0 text-[11px] text-muted-foreground">{formatRelative(e.timestamp)}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function HealthRow({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Gauge;
  label: string;
  value: string;
  tone: "default" | "success" | "warning" | "danger";
}) {
  const toneVariant: Record<typeof tone, "default" | "success" | "warning" | "danger"> = {
    default: "default",
    success: "success",
    warning: "warning",
    danger: "danger",
  };
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/60 py-2 last:border-0">
      <span className="flex items-center gap-2 text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </span>
      <Badge variant={toneVariant[tone]}>{value}</Badge>
    </div>
  );
}
