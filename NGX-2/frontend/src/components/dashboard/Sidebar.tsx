import { NavLink } from "react-router-dom";
import { PanelLeftClose, PanelLeftOpen, LogOut } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { BrandLogo } from "@/components/common/BrandLogo";
import { SIDEBAR_NAV, SIDEBAR_FOOTER_NAV } from "@/constants/nav";
import { useUIStore } from "@/store/ui.store";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";

interface SidebarProps {
  variant?: "desktop" | "mobile";
  onNavigate?: () => void;
}

export function Sidebar({ variant = "desktop", onNavigate }: SidebarProps) {
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const { logout } = useAuth();
  const collapsed = variant === "desktop" && sidebarCollapsed;

  const itemClass = (isActive: boolean) =>
    collapsed
      ? cn(
          "flex h-11 w-11 items-center justify-center rounded-lg transition-colors",
          isActive
            ? "bg-cyan/15 text-cyan-700"
            : "text-muted-foreground hover:bg-surface-elevated hover:text-foreground",
        )
      : cn(
          "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
          isActive
            ? "bg-cyan/12 text-foreground"
            : "text-muted-foreground hover:bg-surface-elevated hover:text-foreground",
        );

  const iconClass = collapsed ? "h-5 w-5 shrink-0" : "h-4 w-4 shrink-0";

  return (
    <TooltipProvider delayDuration={150}>
      <aside
        className={cn(
          "flex h-full flex-col border-r border-border bg-surface/95 backdrop-blur-xl",
          variant === "desktop" ? (collapsed ? "w-[72px]" : "w-[248px]") : "w-full",
          "transition-[width] duration-200 ease-out",
        )}
      >
        <div className={cn("flex items-center px-4 py-5", collapsed && "justify-center px-0")}>
          <BrandLogo compact={collapsed} />
        </div>

        <nav
          className={cn(
            "flex flex-1 flex-col overflow-y-auto px-2 py-2",
            collapsed ? "items-center gap-2" : "gap-0.5",
          )}
        >
          {SIDEBAR_NAV.map((item) => {
            const Icon = item.icon;
            const link = (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/app"}
                onClick={onNavigate}
                className={({ isActive }) => itemClass(isActive)}
              >
                <Icon className={iconClass} />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </NavLink>
            );
            return collapsed ? (
              <Tooltip key={item.to}>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            ) : (
              link
            );
          })}
        </nav>

        <div
          className={cn(
            "flex flex-col border-t border-border px-2 py-3",
            collapsed ? "items-center gap-2" : "gap-0.5",
          )}
        >
          {SIDEBAR_FOOTER_NAV.map((item) => {
            const Icon = item.icon;
            const link = (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onNavigate}
                className={({ isActive }) => itemClass(isActive)}
              >
                <Icon className={iconClass} />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            );
            return collapsed ? (
              <Tooltip key={item.to}>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            ) : (
              link
            );
          })}
          <button
            onClick={() => logout.mutate()}
            className={cn(
              collapsed
                ? "flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-danger-soft hover:text-danger"
                : "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-danger-soft hover:text-danger",
            )}
            aria-label="Sign out"
          >
            <LogOut className={iconClass} />
            {!collapsed && <span>Sign out</span>}
          </button>
        </div>

        {variant === "desktop" && (
          <div className={cn("flex border-t border-border p-2", collapsed && "justify-center")}>
            <button
              onClick={toggleSidebar}
              className={cn(
                "flex items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-surface-elevated hover:text-foreground",
                collapsed ? "h-10 w-10" : "h-10 w-full",
              )}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-4 w-4" />}
            </button>
          </div>
        )}
      </aside>
    </TooltipProvider>
  );
}
