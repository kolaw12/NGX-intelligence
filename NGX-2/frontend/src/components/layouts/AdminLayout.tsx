import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { AdminTopbar } from "@/components/admin/AdminTopbar";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { useUIStore } from "@/store/ui.store";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";

export function AdminLayout() {
  const mobileDrawerOpen = useUIStore((s) => s.mobileDrawerOpen);
  const closeMobileDrawer = useUIStore((s) => s.closeMobileDrawer);
  const location = useLocation();

  useEffect(() => {
    closeMobileDrawer();
  }, [location.pathname, closeMobileDrawer]);

  return (
    <div className="flex min-h-screen bg-background">
      <div className="sticky top-0 hidden h-screen shrink-0 lg:flex">
        <AdminSidebar variant="desktop" />
      </div>

      <Sheet open={mobileDrawerOpen} onOpenChange={(open) => !open && closeMobileDrawer()}>
        <SheetContent side="left" className="w-72 border-r border-border bg-surface p-0">
          <AdminSidebar variant="mobile" onNavigate={closeMobileDrawer} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <AdminTopbar />
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
