import { useMemo, useState } from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { useStocks } from "@/hooks/useStocks";
import { useSectors } from "@/hooks/useSectors";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StockCard } from "@/components/market/StockCard";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Search } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { CardSkeleton } from "@/components/common/LoadingSkeleton";

type SortKey = "symbol" | "price" | "change" | "marketCap" | "confidence";

export default function Stocks() {
  const stocks = useStocks();
  const sectors = useSectors();
  const [query, setQuery] = useState("");
  const [sector, setSector] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("marketCap");

  const filtered = useMemo(() => {
    const list = (stocks.data ?? []).filter((s) => {
      if (sector && s.sectorSlug !== sector) return false;
      if (query && !`${s.symbol} ${s.name}`.toLowerCase().includes(query.toLowerCase())) return false;
      return true;
    });
    list.sort((a, b) => {
      switch (sortKey) {
        case "symbol":
          return a.symbol.localeCompare(b.symbol);
        case "price":
          return b.price - a.price;
        case "change":
          return b.changePct - a.changePct;
        case "confidence":
          return b.confidence - a.confidence;
        case "marketCap":
        default:
          return (b.marketCap ?? -1) - (a.marketCap ?? -1);
      }
    });
    return list;
  }, [stocks.data, query, sector, sortKey]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Equities"
        title="NGX-listed instruments"
        description="Browse, filter, and drill into intelligence on every tracked instrument."
      />

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search symbol or company..."
                className="pl-9 w-72"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                onClick={() => setSector(null)}
                className={`rounded-md border px-2.5 py-1 text-xs ${sector === null ? "border-cyan/40 bg-cyan/10 text-cyan" : "border-border text-muted-foreground hover:text-foreground"}`}
              >
                All
              </button>
              {sectors.data?.map((s) => (
                <button
                  key={s.slug}
                  onClick={() => setSector(s.slug)}
                  className={`rounded-md border px-2.5 py-1 text-xs ${sector === s.slug ? "border-cyan/40 bg-cyan/10 text-cyan" : "border-border text-muted-foreground hover:text-foreground"}`}
                >
                  {s.name}
                </button>
              ))}
            </div>
            <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
              <span>Sort by</span>
              <select
                value={sortKey}
                onChange={(e) => setSortKey(e.target.value as SortKey)}
                className="rounded-md border border-border bg-surface-muted px-2 py-1 text-foreground"
              >
                <option value="marketCap">Market cap</option>
                <option value="confidence">AI confidence</option>
                <option value="change">Daily change</option>
                <option value="price">Price</option>
                <option value="symbol">Symbol</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="mb-3 flex items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="outline">{filtered.length} results</Badge>
            {sector && <Badge variant="cyan">{sectors.data?.find((s) => s.slug === sector)?.name}</Badge>}
          </div>
          {stocks.isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => <CardSkeleton key={i} rows={3} />)}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState icon={Search} title="No matches" description="Adjust your filters or try a different keyword." />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {filtered.map((s) => <StockCard key={s.symbol} stock={s} />)}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
