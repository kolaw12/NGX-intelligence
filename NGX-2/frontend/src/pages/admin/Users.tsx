import { useState } from "react";
import { Search, UserX, UserCheck, ShieldAlert, Pencil, Trash2, Users as UsersIcon } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { TableSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { useAdminUsers, useUpdateAdminUser, useDeleteAdminUser } from "@/hooks/useAdmin";
import type { AdminUser } from "@/types/admin";
import type { UserRole, UserStatus } from "@/types/auth";
import { formatRelative, formatDate } from "@/lib/format";

const ROLE_VARIANT: Record<UserRole, "cyan" | "gold" | "royal" | "default"> = {
  admin: "royal",
  institutional: "cyan",
  professional: "default",
  retail: "default",
};

const STATUS_VARIANT: Record<UserStatus, "success" | "danger" | "warning"> = {
  active: "success",
  suspended: "danger",
  pending: "warning",
};

export default function AdminUsers() {
  const [query, setQuery] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<AdminUser | null>(null);
  const users = useAdminUsers(query);
  const update = useUpdateAdminUser();
  const remove = useDeleteAdminUser();

  function suspend(u: AdminUser) {
    update.mutate(
      { id: u.id, patch: { status: "suspended" } },
      { onSuccess: () => toast.success(`Suspended ${u.name}`) },
    );
  }
  function activate(u: AdminUser) {
    update.mutate(
      { id: u.id, patch: { status: "active" } },
      { onSuccess: () => toast.success(`Re-activated ${u.name}`) },
    );
  }
  function setRole(u: AdminUser, role: UserRole) {
    update.mutate(
      { id: u.id, patch: { role } },
      { onSuccess: () => toast.success(`${u.name} → ${role}`) },
    );
  }
  function deleteUser() {
    if (!confirmDelete) return;
    const u = confirmDelete;
    remove.mutate(u.id, {
      onSuccess: () => {
        toast.success(`Deleted ${u.name}`);
        setConfirmDelete(null);
      },
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin"
        title="Users"
        description="Manage platform users, roles, and account status."
      />

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="relative w-full sm:max-w-sm">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name, email, or organization..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline">{users.data?.length ?? 0} users</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {users.isLoading ? (
            <TableSkeleton rows={8} />
          ) : (users.data?.length ?? 0) === 0 ? (
            <EmptyState icon={UsersIcon} title="No users match" description="Try a different keyword." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Organization</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Logins</TableHead>
                  <TableHead className="text-right">Watchlists</TableHead>
                  <TableHead className="text-right">Alerts</TableHead>
                  <TableHead>Last login</TableHead>
                  <TableHead>Joined</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.data?.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <Avatar className="h-8 w-8 text-[11px]">
                          <AvatarFallback>
                            {u.name
                              .split(" ")
                              .map((p) => p[0])
                              .slice(0, 2)
                              .join("")
                              .toUpperCase()}
                          </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0">
                          <p className="truncate font-semibold text-foreground">{u.name}</p>
                          <p className="truncate text-[11px] text-muted-foreground">{u.email}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{u.organization ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant={ROLE_VARIANT[u.role]} className="capitalize">{u.role}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[u.status]} className="capitalize">{u.status}</Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{u.totalLogins}</TableCell>
                    <TableCell className="text-right tabular-nums">{u.watchlistCount}</TableCell>
                    <TableCell className="text-right tabular-nums">{u.alertCount}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {u.lastLoginAt ? formatRelative(u.lastLoginAt) : "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{formatDate(u.createdAt)}</TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" aria-label="User actions">
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuLabel>Account</DropdownMenuLabel>
                          {u.status === "suspended" ? (
                            <DropdownMenuItem onClick={() => activate(u)}>
                              <UserCheck className="h-3.5 w-3.5" /> Re-activate
                            </DropdownMenuItem>
                          ) : (
                            <DropdownMenuItem onClick={() => suspend(u)}>
                              <UserX className="h-3.5 w-3.5" /> Suspend
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuSeparator />
                          <DropdownMenuLabel>Change role</DropdownMenuLabel>
                          {(["retail", "professional", "institutional", "admin"] as UserRole[]).map((r) => (
                            <DropdownMenuItem
                              key={r}
                              onClick={() => setRole(u, r)}
                              className={u.role === r ? "text-cyan-700" : ""}
                            >
                              <ShieldAlert className="h-3.5 w-3.5" /> {r}
                            </DropdownMenuItem>
                          ))}
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => setConfirmDelete(u)}
                            className="text-danger focus:text-danger"
                          >
                            <Trash2 className="h-3.5 w-3.5" /> Delete user
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={Boolean(confirmDelete)} onOpenChange={(open) => !open && setConfirmDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete user?</DialogTitle>
            <DialogDescription>
              This will permanently remove {confirmDelete?.name} ({confirmDelete?.email}) from the platform. This action
              cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={deleteUser} disabled={remove.isPending}>
              {remove.isPending ? "Deleting…" : "Delete user"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
