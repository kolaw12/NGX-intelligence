import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowRight,
  BarChart3,
  BrainCircuit,
  BriefcaseBusiness,
  Landmark,
  ShieldCheck,
  BellRing,
  Layers,
  ChartCandlestick,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ROUTES } from "@/constants/routes";
import { SectorCard } from "@/components/market/SectorCard";
import { StockCard } from "@/components/market/StockCard";
import { ExplainabilityPanel } from "@/components/ai/ExplainabilityPanel";
import { useSectors } from "@/hooks/useSectors";
import { useStocks, useTopGainers } from "@/hooks/useStocks";
import { useAIInsight } from "@/hooks/useAIInsights";
import { SparklineChart } from "@/components/charts/SparklineChart";
import { MetricCard } from "@/components/market/MetricCard";
import { useMacroIndicators } from "@/hooks/useMacroIndicators";

const features = [
  { icon: BrainCircuit, title: "AI Market Intelligence", desc: "Explainable outlooks and confidence scoring across every listed equity." },
  { icon: BarChart3, title: "Sector Analytics", desc: "Sector momentum, risk indicators, and constituent intelligence at a glance." },
  { icon: BriefcaseBusiness, title: "Portfolio Monitoring", desc: "Allocation insight, performance attribution, and diversification scoring." },
  { icon: Landmark, title: "Macroeconomic Insights", desc: "Inflation, FX, MPR, yields, and CBN events with contextual analysis." },
  { icon: ShieldCheck, title: "Risk Intelligence", desc: "Market, sector, and company-level risk decomposition for every position." },
  { icon: BellRing, title: "Real-time Alerts", desc: "Configurable alerts on price, volume, and AI outlook transitions." },
];

export default function Landing() {
  const { data: sectors } = useSectors();
  const { data: stocks } = useStocks();
  const { data: gainers } = useTopGainers(4);
  const { data: insight } = useAIInsight("GTCO");
  const { data: macro } = useMacroIndicators();

  const featured = sectors?.slice(0, 6) ?? [];

  return (
    <div className="overflow-hidden">
      {/* HERO */}
      <section className="relative bg-radial-light">
        <div className="container relative grid gap-12 py-16 lg:grid-cols-[1.05fr,1fr] lg:items-center lg:py-24">
          <div className="space-y-7">
            <Badge variant="cyan">
              <Sparkles className="h-3 w-3" /> AI-powered financial intelligence
            </Badge>
            <h1 className="text-display-2xl font-semibold tracking-tight text-foreground">
              AI-Powered <span className="text-cyan">Nigerian</span> Financial Intelligence
            </h1>
            <p className="max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
              Institutional-grade market intelligence, macroeconomic analytics, sector intelligence, and explainable
              AI-powered NGX insights — purpose-built for analysts, fintechs, and institutions.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <Button asChild size="lg">
                <Link to={ROUTES.signup}>
                  Get started <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline" size="lg">
                <Link to={ROUTES.features}>Explore intelligence</Link>
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 pt-2 text-xs text-muted-foreground">
              <span>Built for Nigerian markets</span>
              <span className="text-border">•</span>
              <span>Explainable AI</span>
              <span className="text-border">•</span>
              <span>API-ready infrastructure</span>
            </div>
          </div>

          {/* Dashboard mockup */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="relative"
          >
            <div className="absolute -inset-6 bg-radial-glow blur-2xl" aria-hidden="true" />
            <div className="relative rounded-2xl border border-border bg-surface/80 p-4 shadow-elevated backdrop-blur-xl">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="h-2.5 w-2.5 rounded-full bg-danger/80" />
                  <span className="h-2.5 w-2.5 rounded-full bg-gold/80" />
                  <span className="h-2.5 w-2.5 rounded-full bg-success/80" />
                  <span className="ml-2">NGX Intelligence · Live</span>
                </div>
                <Badge variant="success">Open · NGX</Badge>
              </div>

              <div className="grid gap-3 pt-3 sm:grid-cols-2">
                <MetricCard
                  label="ASI"
                  value="102,485.62"
                  change={0.53}
                  icon={ChartCandlestick}
                  accent="cyan"
                />
                <MetricCard
                  label="Total Market Cap"
                  value="₦58.24T"
                  change={0.48}
                  icon={Layers}
                  accent="gold"
                  helper="↑ vs prior session"
                />
              </div>

              <div className="mt-3 rounded-xl border border-border bg-surface-elevated/60 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Top movers</p>
                  <span className="text-[11px] text-cyan">Real-time</span>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {(gainers ?? stocks?.slice(0, 4) ?? []).slice(0, 4).map((s) => (
                    <div key={s.symbol} className="flex items-center justify-between gap-3 rounded-md bg-surface/70 px-2.5 py-2">
                      <div>
                        <p className="text-xs font-semibold text-foreground">{s.symbol}</p>
                        <p className="text-[10px] text-muted-foreground">{s.sector}</p>
                      </div>
                      <div className="h-7 w-12">
                        <SparklineChart data={s.sparkline} height={28} positive={s.changePct >= 0} />
                      </div>
                      <div className="text-right">
                        <p className="text-xs font-semibold tabular-nums text-foreground">₦{s.price.toFixed(2)}</p>
                        <p className={s.changePct >= 0 ? "text-[10px] text-success" : "text-[10px] text-danger"}>
                          {s.changePct > 0 ? "+" : ""}
                          {s.changePct.toFixed(2)}%
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-3 grid grid-cols-3 gap-2">
                {(macro ?? []).slice(0, 3).map((m) => (
                  <div key={m.key} className="rounded-md border border-border bg-surface-elevated/60 p-2">
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{m.label}</p>
                    <p className="mt-1 text-sm font-semibold tabular-nums text-foreground">
                      {m.unit === "₦" || m.unit === "$" ? `${m.unit}${m.value.toLocaleString()}` : `${m.value}${m.unit}`}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* FEATURES */}
      <section className="container py-20">
        <div className="mb-12 max-w-2xl">
          <Badge variant="royal">Platform capabilities</Badge>
          <h2 className="mt-4 text-display-lg font-semibold tracking-tight text-foreground">
            Built for serious financial analysis
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">
            Every component is engineered for analytical depth. No hype, no signals — just transparent, explainable,
            institution-quality intelligence.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="rounded-xl border border-border bg-surface/80 p-6 transition-colors hover:border-cyan/40">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan/15 text-cyan ring-1 ring-cyan/30">
                <f.icon className="h-5 w-5" />
              </div>
              <p className="mt-4 text-base font-semibold text-foreground">{f.title}</p>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* SECTOR PREVIEW */}
      <section className="border-y border-border bg-surface/60">
        <div className="container py-20">
          <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
            <div className="max-w-xl">
              <Badge variant="cyan">Sector intelligence</Badge>
              <h2 className="mt-4 text-display-lg font-semibold tracking-tight text-foreground">
                Live sector momentum across NGX
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                AI outlooks, momentum scoring, risk indicators, and constituent intelligence — all updated as market
                conditions evolve.
              </p>
            </div>
            <Button asChild variant="outline">
              <Link to={ROUTES.signup}>
                Open dashboard <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {featured.map((s) => (
              <SectorCard key={s.slug} sector={s} />
            ))}
          </div>
        </div>
      </section>

      {/* AI EXPLAINABILITY */}
      <section className="container py-20">
        <div className="grid gap-10 lg:grid-cols-[1fr,1.1fr] lg:items-center">
          <div className="space-y-5">
            <Badge variant="gold">Explainable AI</Badge>
            <h2 className="text-display-lg font-semibold tracking-tight text-foreground">
              Every outlook tells you <span className="text-cyan">why</span>
            </h2>
            <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
              Confidence scores derived from auditable factor weights. Risk decomposed into market, sector, and
              company-specific components. Drivers labelled and ranked — never opaque.
            </p>
            <ul className="space-y-3 pt-2">
              {[
                { t: "Confidence scoring", d: "Probabilistic conviction for every outlook with model lineage." },
                { t: "Driver attribution", d: "Ranked factors with directional contribution to the call." },
                { t: "Risk decomposition", d: "Separate market, sector and company-specific risk channels." },
                { t: "Model versioning", d: "Every insight is tied to a model version for reproducibility." },
              ].map((li) => (
                <li key={li.t} className="flex items-start gap-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-cyan" />
                  <div>
                    <p className="text-sm font-semibold text-foreground">{li.t}</p>
                    <p className="text-sm text-muted-foreground">{li.d}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <div>{insight && <ExplainabilityPanel insight={insight} />}</div>
        </div>
      </section>

      {/* STOCKS PREVIEW */}
      <section className="border-t border-border bg-surface/60">
        <div className="container py-20">
          <div className="mb-10 max-w-xl">
            <Badge variant="cyan">Equity intelligence</Badge>
            <h2 className="mt-4 text-display-lg font-semibold tracking-tight text-foreground">
              Institutional intelligence for every listed name
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              From bellwether banks to industrial leaders — comprehensive, AI-augmented analytics for the NGX universe.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {(stocks ?? []).slice(0, 4).map((s) => (
              <StockCard key={s.symbol} stock={s} />
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="container py-20">
        <div className="relative overflow-hidden rounded-2xl border border-border bg-radial-light p-10 text-center lg:p-16">
          <div className="absolute inset-0 bg-radial-glow opacity-70" aria-hidden="true" />
          <div className="relative z-10 mx-auto max-w-2xl space-y-5">
            <Badge variant="cyan">Get started</Badge>
            <h2 className="text-display-xl font-semibold tracking-tight text-foreground">
              Bring institutional-grade intelligence into your workflow
            </h2>
            <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
              No credit card. No commitment. Explore the platform with live local market data while we onboard your
              organization to live infrastructure.
            </p>
            <div className="flex flex-wrap justify-center gap-3">
              <Button asChild size="lg">
                <Link to={ROUTES.signup}>
                  Create your account <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline" size="lg">
                <Link to={ROUTES.contact}>Talk to the team</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
