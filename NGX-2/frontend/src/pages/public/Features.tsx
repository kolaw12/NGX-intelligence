import { Link } from "react-router-dom";
import {
  BrainCircuit,
  BarChart3,
  BriefcaseBusiness,
  Landmark,
  ShieldCheck,
  BellRing,
  Layers,
  ChartCandlestick,
  Activity,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ROUTES } from "@/constants/routes";

const capabilities = [
  {
    icon: BrainCircuit,
    name: "Explainable AI",
    desc: "Auditable model lineage, confidence scoring, ranked driver attribution, and risk decomposition for every outlook.",
    bullets: [
      "Probabilistic confidence per outlook",
      "Ranked driver attribution with weights",
      "Risk channels: market / sector / company",
      "Model versioning for reproducibility",
    ],
  },
  {
    icon: BarChart3,
    name: "Sector Analytics",
    desc: "Momentum scoring, performance windows, AI outlook, and constituent intelligence across every NGX sector.",
    bullets: [
      "Day / week / month / YTD performance",
      "Momentum + risk indicators",
      "Sector-level AI outlook",
      "Constituent-level drill-down",
    ],
  },
  {
    icon: ChartCandlestick,
    name: "Equity Intelligence",
    desc: "Institutional-grade per-stock pages with advanced charts, fundamentals, peer comparison, and explainable AI.",
    bullets: [
      "Candlestick + line charts (1D — MAX)",
      "Fundamental snapshots",
      "Peer comparison tables",
      "AI outlook + risk indicators",
    ],
  },
  {
    icon: Landmark,
    name: "Macroeconomic Intelligence",
    desc: "Inflation, FX, MPR, T-bill yields, oil prices, and CBN events with contextual analytical commentary.",
    bullets: [
      "NBS / CBN / FMDQ indicators",
      "Event categorisation by impact",
      "Official + parallel FX tracking",
      "Yield curve & policy context",
    ],
  },
  {
    icon: BriefcaseBusiness,
    name: "Portfolio Monitoring",
    desc: "Allocation breakdown, performance attribution, risk scoring, and diversification analytics — read-only.",
    bullets: [
      "Sector allocation analysis",
      "Unrealised P&L attribution",
      "Diversification & risk scoring",
      "90-day performance series",
    ],
  },
  {
    icon: ShieldCheck,
    name: "Risk Intelligence",
    desc: "Decomposed risk indicators per asset and portfolio. Understand exactly where exposure originates.",
    bullets: [
      "Beta & volatility metrics",
      "Sector concentration alerts",
      "Macro risk overlays",
      "Risk-adjusted comparisons",
    ],
  },
  {
    icon: BellRing,
    name: "Real-time Alerts",
    desc: "Configurable alerts on price thresholds, volume spikes, and AI outlook transitions.",
    bullets: [
      "Price above / below thresholds",
      "Volume spike detection",
      "AI outlook change events",
      "Status & history tracking",
    ],
  },
  {
    icon: Activity,
    name: "Market Infrastructure",
    desc: "Real-time market overview, breadth analytics, and a live ticker across the broader NGX universe.",
    bullets: [
      "Live ASI + market cap",
      "Advancing / declining breadth",
      "Top gainers / losers / most active",
      "Deal count & volume aggregates",
    ],
  },
  {
    icon: Layers,
    name: "Developer-ready",
    desc: "API-ready service architecture. Components consume hooks, hooks consume services — clean handoff to live infrastructure.",
    bullets: [
      "Service abstraction layer",
      "Mock ↔ live API symmetry",
      "Typed contracts end-to-end",
      "Coming soon: public API",
    ],
  },
];

export default function Features() {
  return (
    <div>
      <section className="bg-radial-light">
        <div className="container py-16 text-center md:py-24">
          <Badge variant="cyan">Platform capabilities</Badge>
          <h1 className="mx-auto mt-5 max-w-3xl text-display-xl font-semibold tracking-tight text-foreground">
            Built for the depth that institutional analysis demands
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
            Every capability is purpose-built for Nigerian financial intelligence. Explainable, transparent, and
            designed for the workflows of real analysts.
          </p>
        </div>
      </section>

      <section className="container py-16">
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {capabilities.map((c) => (
            <div key={c.name} className="rounded-xl border border-border bg-surface/80 p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan/15 text-cyan ring-1 ring-cyan/30">
                <c.icon className="h-5 w-5" />
              </div>
              <p className="mt-4 text-base font-semibold text-foreground">{c.name}</p>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{c.desc}</p>
              <ul className="mt-4 space-y-1.5">
                {c.bullets.map((b) => (
                  <li key={b} className="flex items-start gap-2 text-xs text-foreground">
                    <span className="mt-1 h-1.5 w-1.5 rounded-full bg-cyan" />
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section className="container pb-20">
        <div className="rounded-2xl border border-border bg-surface/60 p-8 text-center">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Ready to explore the platform?</h2>
          <p className="mt-2 text-sm text-muted-foreground">Live local market data available immediately. No commitment.</p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <Button asChild>
              <Link to={ROUTES.signup}>
                Get started <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link to={ROUTES.contact}>Talk to the team</Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
