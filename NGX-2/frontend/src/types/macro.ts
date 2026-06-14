export interface MacroIndicator {
  key: string;
  label: string;
  value: number;
  unit: string;
  changePct: number;
  asOf: string;
  source: string;
}

export interface MacroEvent {
  id: string;
  date: string;
  title: string;
  description: string;
  impact: "low" | "medium" | "high";
  category: "policy" | "fx" | "inflation" | "rates" | "fiscal" | "external";
}

export interface MarketOverview {
  asi: number | null;
  asiChange: number | null;
  asiChangePct: number | null;
  totalMarketCap: number | null;
  totalVolume: number;
  totalValue: number;
  advancing: number;
  declining: number;
  unchanged: number;
  deals: number | null;
  marketStatus: "open" | "closed" | "pre-open";
  lastUpdated?: string;
}
