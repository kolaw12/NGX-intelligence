import type { OHLC, SeriesPoint } from "./common";

export type AIOutlook = "bullish" | "neutral" | "bearish";

export interface Stock {
  symbol: string;
  name: string;
  sector: string;
  sectorSlug: string;
  price: number;
  change: number;
  changePct: number;
  marketCap: number | null;
  pe: number | null;
  dividendYield: number | null;
  volume: number;
  aiOutlook: AIOutlook;
  confidence: number;
  riskScore: number;
  sectorRank: number | null;
  high52w: number;
  low52w: number;
  beta: number | null;
  sparkline: number[];
}

export interface StockDetail extends Stock {
  description: string;
  founded: number | null;
  headquarters: string | null;
  employees: number | null;
  website: string | null;
  ceo: string | null;
  industry: string;
  exchange: string;
  fundamentalsSource?: string;
  ohlc?: OHLC[];
  intradayLine?: SeriesPoint[];
}

export interface PeerStock {
  symbol: string;
  name: string;
  price: number;
  changePct: number;
  marketCap: number | null;
  pe: number | null;
  aiOutlook: AIOutlook;
}

export interface FundamentalsRow {
  metric: string;
  fy2021: number | string;
  fy2022: number | string;
  fy2023: number | string;
  ttm: number | string;
}
