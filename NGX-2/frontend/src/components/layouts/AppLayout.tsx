import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { Topbar } from "@/components/dashboard/Topbar";
import { MarketTicker } from "@/components/dashboard/MarketTicker";
import { NewsTicker } from "@/components/dashboard/NewsTicker";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { useUIStore } from "@/store/ui.store";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";

export function AppLayout() {
  const mobileDrawerOpen = useUIStore((s) => s.mobileDrawerOpen);
  const closeMobileDrawer = useUIStore((s) => s.closeMobileDrawer);
  const location = useLocation();

  useEffect(() => {
    closeMobileDrawer();
  }, [location.pathname, closeMobileDrawer]);

  return (
    <div className="flex min-h-screen bg-background">
      <div className="sticky top-0 hidden h-screen shrink-0 lg:flex">
        <Sidebar variant="desktop" />
      </div>

      <Sheet open={mobileDrawerOpen} onOpenChange={(open) => !open && closeMobileDrawer()}>
        <SheetContent side="left" className="w-72 border-r border-border bg-surface p-0">
          <Sidebar variant="mobile" onNavigate={closeMobileDrawer} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <MarketTicker />
        <NewsTicker />
        <main className="flex-1 overflow-x-hidden">
          <ErrorBoundary>
            <div className="mx-auto w-full max-w-[1440px] px-4 py-6 lg:px-8">
              <Outlet />
            </div>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
