import { Link, NavLink, Outlet } from "react-router-dom";
import { BrandLogo } from "@/components/common/BrandLogo";
import { Button } from "@/components/ui/button";
import { ROUTES } from "@/constants/routes";
import { PUBLIC_NAV as NAV } from "@/constants/nav";
import { ArrowRight, Menu } from "lucide-react";
import { useState } from "react";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { cn } from "@/lib/cn";

export function PublicLayout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative flex min-h-screen flex-col bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border bg-surface/80 backdrop-blur-xl">
        <div className="container flex h-16 items-center justify-between">
          <Link to={ROUTES.home}>
            <BrandLogo />
          </Link>
          <nav className="hidden items-center gap-1 md:flex">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    isActive
                      ? "text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="hidden items-center gap-2 md:flex">
            <Button asChild variant="ghost" size="sm">
              <Link to={ROUTES.login}>Sign in</Link>
            </Button>
            <Button asChild size="sm">
              <Link to={ROUTES.signup}>
                Get started <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
          <button
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-border md:hidden"
            onClick={() => setOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="h-4 w-4" />
          </button>
        </div>

        <Sheet open={open} onOpenChange={setOpen}>
          <SheetContent side="right" className="w-72 p-0">
            <div className="flex h-full flex-col">
              <div className="px-6 py-5">
                <BrandLogo />
              </div>
              <nav className="flex flex-col gap-1 px-3">
                {NAV.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    onClick={() => setOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        "rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                        isActive
                          ? "bg-cyan/12 text-foreground"
                          : "text-muted-foreground hover:bg-surface-elevated hover:text-foreground",
                      )
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>
              <div className="mt-auto space-y-2 border-t border-border p-4">
                <Button asChild variant="outline" className="w-full">
                  <Link to={ROUTES.login}>Sign in</Link>
                </Button>
                <Button asChild className="w-full">
                  <Link to={ROUTES.signup}>Get started</Link>
                </Button>
              </div>
            </div>
          </SheetContent>
        </Sheet>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-border bg-surface/80">
        <div className="container grid gap-8 py-12 md:grid-cols-4">
          <div className="md:col-span-2">
            <BrandLogo />
            <p className="mt-4 max-w-md text-sm text-muted-foreground">
              Institutional-grade financial intelligence for the Nigerian Exchange. NGX Intelligence is an analytics
              platform and does not facilitate trading or brokerage services.
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Product</p>
            <ul className="mt-3 space-y-2 text-sm text-foreground">
              <li><Link to={ROUTES.features} className="hover:text-cyan">Features</Link></li>
              <li><Link to={ROUTES.about} className="hover:text-cyan">About</Link></li>
              <li><Link to={ROUTES.contact} className="hover:text-cyan">Contact</Link></li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Account</p>
            <ul className="mt-3 space-y-2 text-sm text-foreground">
              <li><Link to={ROUTES.login} className="hover:text-cyan">Sign in</Link></li>
              <li><Link to={ROUTES.signup} className="hover:text-cyan">Create account</Link></li>
            </ul>
          </div>
        </div>
        <div className="border-t border-border">
          <div className="container flex flex-col items-start justify-between gap-2 py-5 text-xs text-muted-foreground md:flex-row md:items-center">
            <p>© {new Date().getFullYear()} NGX Intelligence. All rights reserved.</p>
            <p>Information presented for analytical purposes only. Not investment advice.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

