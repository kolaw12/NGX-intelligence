import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { ROUTES } from "@/constants/routes";
import { ArrowRight, Compass, Layers, ShieldCheck, Sparkles } from "lucide-react";

const principles = [
  {
    icon: Sparkles,
    name: "Intelligence, not signals",
    desc: "We surface decision context. The platform never tells you to buy or sell — it explains what the data is suggesting and why.",
  },
  {
    icon: Compass,
    name: "Explainability first",
    desc: "Every model output is paired with its drivers, confidence, and risk profile. Reasoning is auditable end-to-end.",
  },
  {
    icon: Layers,
    name: "Infrastructure-grade",
    desc: "Engineered to be the financial intelligence backbone for analysts, fintechs, and institutional users across Africa.",
  },
  {
    icon: ShieldCheck,
    name: "Trustworthy by design",
    desc: "We do not facilitate brokerage. We provide intelligence. That separation is intentional — and load-bearing.",
  },
];

export default function About() {
  return (
    <div>
      <section className="bg-radial-light">
        <div className="container py-16 md:py-24">
          <div className="max-w-3xl">
            <Badge variant="cyan">About NGX Intelligence</Badge>
            <h1 className="mt-5 text-display-xl font-semibold tracking-tight text-foreground">
              The financial intelligence infrastructure for Nigeria.
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
              Nigerian markets deserve world-class analytics. We are building the AI-powered intelligence layer that
              transforms raw market data into actionable, explainable, institutional-grade insight.
            </p>
          </div>
        </div>
      </section>

      <section className="container grid gap-12 py-20 lg:grid-cols-[1fr,1.2fr]">
        <div>
          <Badge variant="royal">Mission</Badge>
          <h2 className="mt-4 text-display-lg font-semibold tracking-tight text-foreground">
            Transform raw financial data into intelligent infrastructure
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            Existing tools surface data — charts, prices, news. Few provide context, fewer offer explanation. We are
            engineering the platform where intelligence is the product, not a feature.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {principles.map((p) => (
            <div key={p.name} className="rounded-xl border border-border bg-surface/80 p-5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan/15 text-cyan ring-1 ring-cyan/30">
                <p.icon className="h-4 w-4" />
              </div>
              <p className="mt-3 text-sm font-semibold text-foreground">{p.name}</p>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{p.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-border bg-surface/60">
        <div className="container grid gap-10 py-16 md:grid-cols-3">
          <div>
            <p className="text-3xl font-semibold text-cyan">7</p>
            <p className="mt-1 text-sm font-semibold text-foreground">NGX sectors tracked</p>
            <p className="text-xs text-muted-foreground">Banking, Oil & Gas, Telcos, Industrials, Consumer Goods, Insurance, Agriculture.</p>
          </div>
          <div>
            <p className="text-3xl font-semibold text-cyan">20+</p>
            <p className="mt-1 text-sm font-semibold text-foreground">Tracked instruments</p>
            <p className="text-xs text-muted-foreground">Expanding to full NGX universe at general availability.</p>
          </div>
          <div>
            <p className="text-3xl font-semibold text-cyan">0</p>
            <p className="mt-1 text-sm font-semibold text-foreground">Brokerage exposure</p>
            <p className="text-xs text-muted-foreground">We are an analytics platform. No order routing. No execution.</p>
          </div>
        </div>
      </section>

      <section className="container py-20">
        <div className="rounded-2xl border border-border bg-radial-light p-10 text-center">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Partner with us</h2>
          <p className="mt-2 max-w-xl mx-auto text-sm text-muted-foreground">
            If your team builds for the Nigerian financial ecosystem, we want to hear from you. We work with analysts,
            fintechs, institutions, and developers.
          </p>
          <div className="mt-5 flex justify-center gap-3">
            <Button asChild>
              <Link to={ROUTES.contact}>
                Contact us <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link to={ROUTES.features}>Explore capabilities</Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
