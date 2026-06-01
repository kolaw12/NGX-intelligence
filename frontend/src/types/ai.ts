import type { AIOutlook } from "./stock";

export interface AIDriver {
  label: string;
  direction: "positive" | "negative" | "neutral";
  weight: number;
}

export interface AIRiskDecomposition {
  marketRisk: number;
  sectorRisk: number;
  companyRisk: number;
}

export interface AIInsight {
  symbol?: string;
  outlook: AIOutlook;
  confidence: number;
  summary: string;
  drivers: AIDriver[];
  risks: AIRiskDecomposition;
  generatedAt: string;
  horizonDays: number;
  modelVersion: string;
}

export interface MarketSentiment {
  score: number;
  label: "extreme-fear" | "fear" | "neutral" | "greed" | "extreme-greed";
  summary: string;
  drivers: AIDriver[];
  source?: "sentiment_pipeline_json" | "nlp_engine" | "market_breadth_fallback";
  articles?: number;
  tickersCovered?: number;
  latestSummaryDate?: string | null;
  fallbackActive?: boolean;
}

export interface NewsItem {
  id: string;
  symbol?: string;
  mentionedTickers?: string[];
  headline: string;
  source: string;
  publishedAt: string;
  url: string;
  sentiment: "positive" | "negative" | "neutral";
  sentimentScore?: number;
  relevanceScore?: number;
  eventTags?: string[];
  summary: string;
}

export interface SentimentDiagnostics {
  source: "nlp_engine" | "neutral_fallback";
  articlesLoaded: number;
  summaryRows: number;
  tickersCovered: number;
  latestArticleDate: string | null;
  latestSummaryDate: string | null;
  fallbackActive: boolean;
}
