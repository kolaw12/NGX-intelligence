import { Link, Outlet } from "react-router-dom";
import { BrandLogo } from "@/components/common/BrandLogo";
import { ROUTES } from "@/constants/routes";

export function AuthLayout() {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between border-r border-border bg-radial-light p-10 lg:flex">
        <Link to={ROUTES.home}>
          <BrandLogo />
        </Link>
        <div className="relative z-10 max-w-md space-y-6">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-cyan-700">Financial Intelligence</p>
          <h2 className="text-3xl font-semibold leading-tight tracking-tight text-foreground">
            Institutional-grade intelligence for the Nigerian Exchange.
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            AI-powered market analytics, macroeconomic intelligence, sector momentum, and explainable insights — built for
            analysts, fintechs, and institutions.
          </p>
          <div className="grid grid-cols-2 gap-3 pt-2">
            {[
              { v: "20+", l: "Tracked instruments" },
              { v: "7", l: "Sectors monitored" },
              { v: "90d", l: "AI horizon" },
              { v: "0", l: "Brokerage involvement" },
            ].map((s) => (
              <div key={s.l} className="rounded-lg border border-border bg-surface/60 p-3">
                <p className="text-2xl font-semibold tabular-nums text-foreground">{s.v}</p>
                <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{s.l}</p>
              </div>
            ))}
          </div>
        </div>
        <p className="relative z-10 text-xs text-muted-foreground">
          © {new Date().getFullYear()} NGX Intelligence. Analytics platform — not a brokerage.
        </p>
      </div>

      <div className="flex flex-col">
        <div className="flex h-16 items-center px-6 lg:hidden">
          <Link to={ROUTES.home}>
            <BrandLogo />
          </Link>
        </div>
        <div className="flex flex-1 items-center justify-center px-6 py-10">
          <div className="w-full max-w-md">
            <Outlet />
          </div>
        </div>
      </div>
    </div>
  );
}
