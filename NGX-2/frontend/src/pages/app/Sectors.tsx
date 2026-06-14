import { useState } from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { useSectors } from "@/hooks/useSectors";
import { SectorCard } from "@/components/market/SectorCard";
import { SectorBarChart } from "@/components/charts/SectorBarChart";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CardSkeleton, ChartSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { Layers, Search } from "lucide-react";
import { Input } from "@/components/ui/input";

export default function Sectors() {
  const [query, setQuery] = useState("");
  const sectors = useSectors();
  const filtered = (sectors.data ?? []).filter((s) => s.name.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Sectors"
        title="Sector analytics & momentum"
        description="AI outlooks, momentum scoring, risk indicators, and constituent intelligence across NGX sectors."
      />

      <Card>
        <CardHeader>
          <CardTitle>Daily sector performance</CardTitle>
          <CardDescription>Ranked by today's move</CardDescription>
        </CardHeader>
        <CardContent>
          {sectors.isLoading ? (
            <ChartSkeleton />
          ) : (
            <SectorBarChart
              data={(sectors.data ?? []).map((s) => ({ name: s.name, value: s.performanceDay }))}
              height={360}
            />
          )}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-foreground">All sectors</h2>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter sectors..."
            className="pl-9 w-56"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      {sectors.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <CardSkeleton key={i} rows={5} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={Layers} title="No sectors match" description="Try a different keyword." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((s) => (
            <SectorCard key={s.slug} sector={s} />
          ))}
        </div>
      )}
    </div>
  );
}
