import { useNavigate } from "react-router-dom";
import { ChevronDown, Menu, ShieldCheck } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/hooks/useAuth";
import { useUIStore } from "@/store/ui.store";
import { ROUTES } from "@/constants/routes";
import { cn } from "@/lib/cn";

export function AdminTopbar({ className }: { className?: string }) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const openMobileDrawer = useUIStore((s) => s.openMobileDrawer);

  return (
    <header
      className={cn(
        "sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-surface/95 px-4 backdrop-blur-xl lg:px-6",
        className,
      )}
    >
      <button
        onClick={openMobileDrawer}
        className="flex h-9 w-9 items-center justify-center rounded-lg border border-border lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="h-4 w-4" />
      </button>

      <div className="hidden md:flex md:items-center md:gap-2">
        <Badge variant="royal">
          <ShieldCheck className="h-3 w-3" /> Administrator
        </Badge>
        <p className="text-xs text-muted-foreground">Internal operations console</p>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 rounded-lg border border-transparent px-2 py-1 transition-colors hover:border-border hover:bg-surface-elevated">
              <Avatar>
                <AvatarFallback>
                  {(user?.name ?? "A")
                    .split(" ")
                    .map((p) => p[0])
                    .slice(0, 2)
                    .join("")
                    .toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="hidden text-left sm:block">
                <p className="text-xs font-semibold text-foreground">{user?.name ?? "Admin"}</p>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{user?.role ?? "admin"}</p>
              </div>
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>{user?.email ?? "Admin"}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate(ROUTES.dashboard)}>Switch to user view</DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate(ROUTES.profile)}>My profile</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => logout.mutate()} className="text-danger focus:text-danger">
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
