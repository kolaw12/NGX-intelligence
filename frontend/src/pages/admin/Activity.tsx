import { useState } from "react";
import { ScrollText, Search } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { TableSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { useAdminActivity } from "@/hooks/useAdmin";
import { formatRelative, formatDateTime } from "@/lib/format";
import type { ActivityEventType } from "@/types/admin";

const EVENT_TYPES: { value: ActivityEventType | "all"; label: string }[] = [
  { value: "all", label: "All events" },
  { value: "login", label: "Logins" },
  { value: "signup", label: "Signups" },
  { value: "alert.create", label: "Alert created" },
  { value: "alert.triggered", label: "Alert triggered" },
  { value: "watchlist.create", label: "Watchlist created" },
  { value: "admin.user.suspend", label: "User suspended" },
  { value: "admin.user.role-change", label: "Role changed" },
];

const TYPE_VARIANT: Record<string, "default" | "cyan" | "gold" | "success" | "danger" | "warning" | "royal"> = {
  login: "cyan",
  logout: "default",
  signup: "success",
  "alert.create": "gold",
  "alert.delete": "default",
  "alert.triggered": "warning",
  "watchlist.create": "cyan",
  "watchlist.update": "default",
  "watchlist.delete": "default",
  "profile.update": "default",
  "password.reset": "warning",
  "admin.user.suspend": "danger",
  "admin.user.activate": "success",
  "admin.user.role-change": "royal",
};

export default function AdminActivity() {
  const [query, setQuery] = useState("");
  const [type, setType] = useState<ActivityEventType | "all">("all");
  const activity = useAdminActivity(type !== "all" ? { type } : undefined);

  const filtered = (activity.data ?? []).filter((e) => {
    if (!query) return true;
    const q = query.toLowerCase();
    return (
      e.userName.toLowerCase().includes(q) ||
      e.userEmail.toLowerCase().includes(q) ||
      e.description.toLowerCase().includes(q) ||
      e.type.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin"
        title="Activity log"
        description="Audit trail of user and administrator events across the platform."
      />

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative w-full sm:max-w-sm">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by user, email, or event..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              {EVENT_TYPES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setType(t.value as ActivityEventType | "all")}
                  className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
                    type === t.value
                      ? "border-cyan/40 bg-cyan/10 text-cyan-700"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <div className="ml-auto text-xs text-muted-foreground">{filtered.length} events</div>
          </div>
        </CardHeader>
        <CardContent>
          {activity.isLoading ? (
            <TableSkeleton rows={10} />
          ) : filtered.length === 0 ? (
            <EmptyState icon={ScrollText} title="No events match" description="Adjust the filter or search." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>IP / Device</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell>
                      <div className="flex items-center gap-2.5">
                        <Avatar className="h-7 w-7 text-[10px]">
                          <AvatarFallback>
                            {e.userName
                              .split(" ")
                              .map((p) => p[0])
                              .slice(0, 2)
                              .join("")
                              .toUpperCase()}
                          </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-foreground">{e.userName}</p>
                          <p className="truncate text-[11px] text-muted-foreground">{e.userEmail}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={TYPE_VARIANT[e.type] ?? "default"}>{e.type}</Badge>
                    </TableCell>
                    <TableCell className="text-foreground">{e.description}</TableCell>
                    <TableCell className="text-muted-foreground">
                      <div className="tabular-nums">{e.ip ?? "—"}</div>
                      <div className="text-[11px]">{e.userAgent ?? ""}</div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      <div title={formatDateTime(e.timestamp)}>{formatRelative(e.timestamp)}</div>
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
