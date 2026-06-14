import {
  LayoutDashboard,
  Activity,
  Layers,
  ChartCandlestick,
  BrainCircuit,
  BriefcaseBusiness,
  WalletCards,
  BellRing,
  Settings,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { ROUTES } from "./routes";

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  description?: string;
}

export const SIDEBAR_NAV: NavItem[] = [
  { label: "Dashboard", to: ROUTES.dashboard, icon: LayoutDashboard, description: "Market overview & widgets" },
  { label: "Markets", to: ROUTES.markets, icon: Activity, description: "Real-time market intelligence" },
  { label: "Sectors", to: ROUTES.sectors, icon: Layers, description: "Sector analytics & momentum" },
  { label: "Stocks", to: ROUTES.stocks, icon: ChartCandlestick, description: "NGX listed equities" },
  { label: "AI Insights", to: ROUTES.aiInsights, icon: BrainCircuit, description: "Explainable intelligence" },
  { label: "Portfolio", to: ROUTES.portfolio, icon: BriefcaseBusiness, description: "Portfolio monitoring" },
  { label: "Watchlists", to: ROUTES.watchlists, icon: WalletCards, description: "Tracked instruments" },
  { label: "Alerts", to: ROUTES.alerts, icon: BellRing, description: "Triggered & active alerts" },
];

export const SIDEBAR_FOOTER_NAV: NavItem[] = [
  { label: "Settings", to: ROUTES.settings, icon: Settings },
  { label: "Profile", to: ROUTES.profile, icon: UserRound },
];

export const PUBLIC_NAV = [
  { label: "Product", to: ROUTES.features },
  { label: "About", to: ROUTES.about },
  { label: "Contact", to: ROUTES.contact },
] as const;
