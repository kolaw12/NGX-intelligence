import type { AIOutlook } from "./stock";

export interface PortfolioHolding {
  symbol: string;
  name: string;
  sector: string;
  units: number;
  avgCost: number;
  currentPrice: number;
  marketValue: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  allocationPct: number;
  aiOutlook: AIOutlook;
}

export interface PortfolioSummary {
  totalValue: number;
  totalCost: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  dayChange: number;
  dayChangePct: number;
  holdings: PortfolioHolding[];
  allocation: { sector: string; weight: number }[];
  performanceSeries: { time: string; value: number }[];
  riskScore: number;
  diversificationScore: number;
}
