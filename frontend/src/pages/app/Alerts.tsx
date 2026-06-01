import { useState } from "react";
import { BellRing, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common/PageHeader";
import { useAlerts, useCreateAlert, useDeleteAlert } from "@/hooks/useAlerts";
import { useStocks } from "@/hooks/useStocks";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CardSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { FormField } from "@/components/forms/FormField";
import { Label } from "@/components/ui/label";
import { formatRelative } from "@/lib/format";
import type { Alert } from "@/types/auth";

const CONDITIONS: { value: Alert["condition"]; label: string }[] = [
  { value: "above", label: "Price above threshold" },
  { value: "below", label: "Price below threshold" },
  { value: "ai-outlook-change", label: "AI outlook change" },
  { value: "volume-spike", label: "Volume spike (% of 20d avg)" },
];

export default function Alerts() {
  const alerts = useAlerts();
  const stocks = useStocks();
  const create = useCreateAlert();
  const remove = useDeleteAlert();

  const [open, setOpen] = useState(false);
  const [symbol, setSymbol] = useState("");
  const [condition, setCondition] = useState<Alert["condition"]>("above");
  const [threshold, setThreshold] = useState("50");

  function handleCreate() {
    if (!symbol) return;
    create.mutate(
      { symbol, condition, threshold: Number(threshold) || 0 },
      {
        onSuccess: () => {
          toast.success(`Alert for ${symbol} created`);
          setOpen(false);
          setSymbol("");
          setThreshold("50");
          setCondition("above");
        },
      },
    );
  }

  const active = alerts.data?.filter((a) => a.status === "active") ?? [];
  const triggered = alerts.data?.filter((a) => a.status === "triggered") ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Alerts"
        title="Configurable alerts"
        description="Receive notifications when price thresholds, volume conditions, or AI outlook transitions are met."
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="h-4 w-4" /> New alert
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create alert</DialogTitle>
                <DialogDescription>Set the symbol, condition, and threshold.</DialogDescription>
              </DialogHeader>
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label>Symbol</Label>
                  <select
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    className="h-11 w-full rounded-lg border border-border bg-surface-muted px-3 text-sm text-foreground"
                  >
                    <option value="">Select symbol…</option>
                    {stocks.data?.map((s) => (
                      <option key={s.symbol} value={s.symbol}>
                        {s.symbol} · {s.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label>Condition</Label>
                  <select
                    value={condition}
                    onChange={(e) => setCondition(e.target.value as Alert["condition"])}
                    className="h-11 w-full rounded-lg border border-border bg-surface-muted px-3 text-sm text-foreground"
                  >
                    {CONDITIONS.map((c) => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>
                <FormField
                  label="Threshold"
                  type="number"
                  value={threshold}
                  onChange={(e) => setThreshold(e.target.value)}
                  helperText={
                    condition === "ai-outlook-change"
                      ? "Threshold ignored — alerts fire on any AI outlook change."
                      : condition === "volume-spike"
                        ? "Volume threshold as % of 20-day average (e.g. 200)"
                        : "Price threshold in ₦"
                  }
                />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                <Button onClick={handleCreate} disabled={!symbol || create.isPending}>Create alert</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Triggered</CardTitle>
          <CardDescription>Most recent firings</CardDescription>
        </CardHeader>
        <CardContent>
          {alerts.isLoading ? (
            <CardSkeleton rows={3} />
          ) : triggered.length === 0 ? (
            <EmptyState icon={BellRing} title="Nothing triggered" description="Active alerts will appear here when conditions are met." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Condition</TableHead>
                  <TableHead>Message</TableHead>
                  <TableHead>Triggered</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {triggered.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="font-semibold text-foreground">{a.symbol}</TableCell>
                    <TableCell>
                      <Badge variant="gold">{a.condition.replace(/-/g, " ")}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{a.message ?? "—"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {a.triggeredAt ? formatRelative(a.triggeredAt) : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Active</CardTitle>
          <CardDescription>Listening for trigger conditions</CardDescription>
        </CardHeader>
        <CardContent>
          {alerts.isLoading ? (
            <CardSkeleton rows={4} />
          ) : active.length === 0 ? (
            <EmptyState icon={BellRing} title="No active alerts" description="Create an alert to start receiving notifications." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Condition</TableHead>
                  <TableHead className="text-right">Threshold</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {active.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="font-semibold text-foreground">{a.symbol}</TableCell>
                    <TableCell>{a.condition.replace(/-/g, " ")}</TableCell>
                    <TableCell className="text-right">
                      {a.condition === "ai-outlook-change" ? "—" : a.condition === "volume-spike" ? `${a.threshold}%` : `₦${a.threshold}`}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{formatRelative(a.createdAt)}</TableCell>
                    <TableCell className="text-right">
                      <button
                        onClick={() => remove.mutate(a.id, { onSuccess: () => toast.success(`Alert removed`) })}
                        className="rounded-md p-1.5 text-muted-foreground hover:bg-danger-soft hover:text-danger"
                        aria-label="Delete alert"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
