import { useNavigate } from "react-router-dom";
import { Search, Menu, Command, Bell, ChevronDown, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
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

interface TopbarProps {
  className?: string;
}

function marketStatus(): { label: string; tone: "open" | "closed" | "pre" } {
  const now = new Date();
  const hour = now.getUTCHours() + 1; // Africa/Lagos is UTC+1
  const day = now.getUTCDay();
  if (day === 0 || day === 6) return { label: "Closed · Weekend", tone: "closed" };
  if (hour >= 10 && hour < 14) return { label: "Open · NGX", tone: "open" };
  if (hour >= 9 && hour < 10) return { label: "Pre-open", tone: "pre" };
  return { label: "Closed · After hours", tone: "closed" };
}

export function Topbar({ className }: TopbarProps) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const openMobileDrawer = useUIStore((s) => s.openMobileDrawer);
  const status = marketStatus();

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

      <div className="hidden flex-1 md:flex">
        <div className="relative w-full max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            placeholder="Search symbols, sectors, insights..."
            className="h-10 w-full rounded-lg border border-border bg-surface-muted pl-9 pr-14 text-sm text-foreground placeholder:text-muted-foreground/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/60"
          />
          <kbd className="absolute right-2 top-1/2 inline-flex h-6 -translate-y-1/2 items-center gap-1 rounded-md border border-border bg-surface px-1.5 text-[10px] text-muted-foreground">
            <Command className="h-3 w-3" />K
          </kbd>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-2 md:gap-3">
        <Badge
          variant={status.tone === "open" ? "success" : status.tone === "pre" ? "warning" : "default"}
          className="hidden sm:inline-flex"
        >
          <Activity className="h-3 w-3" /> {status.label}
        </Badge>

        <Button variant="ghost" size="icon" aria-label="Notifications" onClick={() => navigate(ROUTES.alerts)}>
          <Bell className="h-4 w-4" />
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 rounded-lg border border-transparent px-2 py-1 transition-colors hover:border-border hover:bg-surface-elevated">
              <Avatar>
                <AvatarFallback>
                  {(user?.name ?? "U")
                    .split(" ")
                    .map((p) => p[0])
                    .slice(0, 2)
                    .join("")
                    .toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="hidden text-left sm:block">
                <p className="text-xs font-semibold text-foreground">{user?.name ?? "Guest"}</p>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{user?.role ?? "user"}</p>
              </div>
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>{user?.email ?? "Account"}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate(ROUTES.profile)}>Profile</DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate(ROUTES.settings)}>Settings</DropdownMenuItem>
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
