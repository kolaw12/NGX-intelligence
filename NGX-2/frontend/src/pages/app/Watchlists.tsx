import { useState } from "react";
import { Plus, WalletCards, X } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common/PageHeader";
import { useStocks } from "@/hooks/useStocks";
import {
  useWatchlists,
  useCreateWatchlist,
  useAddToWatchlist,
  useRemoveFromWatchlist,
  useDeleteWatchlist,
} from "@/hooks/useWatchlist";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { FormField } from "@/components/forms/FormField";
import { Label } from "@/components/ui/label";
import { CardSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { StockRow } from "@/components/market/StockRow";

export default function Watchlists() {
  const watchlists = useWatchlists();
  const stocks = useStocks();
  const create = useCreateWatchlist();
  const addSymbol = useAddToWatchlist();
  const removeSymbol = useRemoveFromWatchlist();
  const deleteWl = useDeleteWatchlist();

  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  function handleCreate() {
    if (!name.trim()) return;
    create.mutate(
      { name, description },
      {
        onSuccess: () => {
          toast.success(`Watchlist "${name}" created`);
          setName("");
          setDescription("");
          setOpen(false);
        },
      },
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Watchlists"
        title="Tracked instruments"
        description="Curated lists for targeted observation. Organize by sector, conviction, theme, or risk band."
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="h-4 w-4" /> New watchlist
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create watchlist</DialogTitle>
                <DialogDescription>Name and optional description.</DialogDescription>
              </DialogHeader>
              <div className="space-y-3">
                <FormField label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Tier-1 Banks" />
                <div className="space-y-1.5">
                  <Label>Description</Label>
                  <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional" />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                <Button onClick={handleCreate} disabled={!name.trim() || create.isPending}>Create</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      {watchlists.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          <CardSkeleton rows={4} />
          <CardSkeleton rows={4} />
        </div>
      ) : (watchlists.data?.length ?? 0) === 0 ? (
        <EmptyState icon={WalletCards} title="No watchlists" description="Create your first watchlist to start tracking instruments." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {watchlists.data?.map((wl) => {
            const rows = (stocks.data ?? []).filter((s) => wl.symbols.includes(s.symbol));
            return (
              <Card key={wl.id}>
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <CardTitle>{wl.name}</CardTitle>
                      <CardDescription>{wl.description || `${wl.symbols.length} symbols tracked`}</CardDescription>
                    </div>
                    <button
                      onClick={() => {
                        if (confirm(`Delete watchlist "${wl.name}"?`)) {
                          deleteWl.mutate(wl.id, { onSuccess: () => toast.success(`Deleted "${wl.name}"`) });
                        }
                      }}
                      className="text-muted-foreground hover:text-danger"
                      aria-label="Delete watchlist"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-1.5">
                  {rows.length === 0 ? (
                    <EmptyState icon={WalletCards} title="Empty list" description="Add a symbol to begin tracking." />
                  ) : (
                    rows.map((s) => (
                      <div key={s.symbol} className="flex items-center gap-2">
                        <div className="flex-1">
                          <StockRow stock={s} showSparkline={false} />
                        </div>
                        <button
                          onClick={() =>
                            removeSymbol.mutate(
                              { id: wl.id, symbol: s.symbol },
                              { onSuccess: () => toast.success(`Removed ${s.symbol}`) },
                            )
                          }
                          className="rounded-md p-1 text-muted-foreground hover:text-danger"
                          aria-label={`Remove ${s.symbol}`}
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))
                  )}
                  <AddSymbolForm
                    onAdd={(symbol) => addSymbol.mutate({ id: wl.id, symbol }, { onSuccess: () => toast.success(`Added ${symbol}`) })}
                    options={(stocks.data ?? []).map((s) => s.symbol).filter((s) => !wl.symbols.includes(s))}
                  />
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AddSymbolForm({ onAdd, options }: { onAdd: (symbol: string) => void; options: string[] }) {
  const [value, setValue] = useState("");
  return (
    <div className="flex items-center gap-2 border-t border-border pt-3">
      <select
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="flex-1 rounded-md border border-border bg-surface-muted px-2.5 py-1.5 text-xs text-foreground"
      >
        <option value="">Add symbol…</option>
        {options.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
      <Button
        size="sm"
        variant="outline"
        disabled={!value}
        onClick={() => {
          if (value) {
            onAdd(value);
            setValue("");
          }
        }}
      >
        <Plus className="h-3.5 w-3.5" /> Add
      </Button>
    </div>
  );
}
