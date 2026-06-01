import { NavLink, Link } from "react-router-dom";
import { ShieldCheck, ExternalLink, LogOut } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { BrandLogo } from "@/components/common/BrandLogo";
import { Badge } from "@/components/ui/badge";
import { ADMIN_NAV } from "@/constants/admin-nav";
import { ROUTES } from "@/constants/routes";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";

interface AdminSidebarProps {
  variant?: "desktop" | "mobile";
  onNavigate?: () => void;
}

export function AdminSidebar({ variant = "desktop", onNavigate }: AdminSidebarProps) {
  const { logout } = useAuth();

  return (
    <TooltipProvider delayDuration={150}>
      <aside
        className={cn(
          "flex h-full flex-col border-r border-border bg-surface/95 backdrop-blur-xl",
          variant === "desktop" ? "w-[248px]" : "w-full",
        )}
      >
        <div className="flex items-center justify-between px-4 py-5">
          <BrandLogo />
        </div>
        <div className="px-4 pb-3">
          <Badge variant="royal" className="text-[10px]">
            <ShieldCheck className="h-3 w-3" /> Admin portal
          </Badge>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-2">
          {ADMIN_NAV.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === ROUTES.adminOverview}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-cyan/12 text-foreground"
                      : "text-muted-foreground hover:bg-surface-elevated hover:text-foreground",
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="truncate">{item.label}</p>
                  {item.description && (
                    <p className="truncate text-[10px] text-muted-foreground/80">{item.description}</p>
                  )}
                </div>
              </NavLink>
            );
          })}
        </nav>

        <div className="space-y-0.5 border-t border-border px-2 py-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Link
                to={ROUTES.dashboard}
                onClick={onNavigate}
                className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-surface-elevated hover:text-foreground"
              >
                <ExternalLink className="h-4 w-4 shrink-0" />
                <span>User dashboard</span>
              </Link>
            </TooltipTrigger>
            <TooltipContent side="right">Switch to the user experience</TooltipContent>
          </Tooltip>
          <button
            onClick={() => logout.mutate()}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-danger-soft hover:text-danger"
          >
            <LogOut className="h-4 w-4 shrink-0" /> Sign out
          </button>
        </div>
      </aside>
    </TooltipProvider>
  );
}
