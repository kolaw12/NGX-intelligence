import type { AIInsight, MarketSentiment, NewsItem, SentimentDiagnostics } from "@/types/ai";
import type { Stock } from "@/types/stock";
import { http } from "./http.client";
import stockSnapshot from "@/data/stocks.snapshot.json";

const fallbackStocks = stockSnapshot as Stock[];

function findStock(symbol: string) {
  return fallbackStocks.find((stock) => stock.symbol.toUpperCase() === symbol.toUpperCase());
}

function buildInsight(stock: Stock): AIInsight {
  const confidence = Math.max(12, Math.round(stock.confidence || Math.min(85, Math.abs(stock.changePct) * 6 + 18)));
  const outlook = stock.aiOutlook;
  const riskTotal = Math.round(stock.riskScore || 45);
  const marketRisk = Math.round(Math.min(35, Math.max(12, riskTotal * 0.35)));
  const sectorRisk = Math.round(Math.min(35, Math.max(10, riskTotal * 0.3)));
  const companyRisk = Math.max(8, riskTotal - marketRisk - sectorRisk);

  return {
    symbol: stock.symbol,
    outlook,
    confidence,
    summary:
      outlook === "bullish"
        ? `${stock.symbol} is showing positive momentum in the latest bundled market snapshot, supported by price movement and trading activity.`
        : outlook === "bearish"
          ? `${stock.symbol} is showing weaker short-term momentum in the latest bundled market snapshot, so the model view remains cautious.`
          : `${stock.symbol} has a neutral model view in the latest bundled market snapshot; confidence is not strong enough for a BUY or SELL signal.`,
    drivers: [
      { label: "daily price change", direction: stock.changePct >= 0 ? "positive" : "negative", weight: Math.min(0.35, Math.max(0.08, Math.abs(stock.changePct) / 30)) },
      { label: "trading volume", direction: stock.volume > 0 ? "positive" : "neutral", weight: stock.volume > 0 ? 0.18 : 0.08 },
      { label: "sector context", direction: outlook === "bullish" ? "positive" : outlook === "bearish" ? "negative" : "neutral", weight: 0.16 },
      { label: "risk score", direction: riskTotal > 60 ? "negative" : riskTotal < 35 ? "positive" : "neutral", weight: 0.14 },
      { label: "market snapshot", direction: "neutral", weight: 0.1 },
    ],
    risks: { marketRisk, sectorRisk, companyRisk },
    generatedAt: new Date().toISOString(),
    horizonDays: 30,
    modelVersion: "bundled-snapshot-fallback",
  };
}

function fallbackInsights(limit = 12) {
  return [...fallbackStocks]
    .filter((stock) => stock.volume > 0)
    .sort((a, b) => Math.abs(b.changePct) + b.volume / 1_000_000_000 - (Math.abs(a.changePct) + a.volume / 1_000_000_000))
    .slice(0, limit)
    .map(buildInsight);
}

export const aiService = {
  getInsight: async (symbol: string): Promise<AIInsight> => {
    const stock = findStock(symbol);
    if (!stock) throw new Error(`Ticker not found: ${symbol}`);
    return buildInsight(stock);
  },

  listInsights: async (): Promise<AIInsight[]> => {
    return fallbackInsights();
  },

  getMarketSentiment: async (): Promise<MarketSentiment> => {
    return http.get<MarketSentiment>("/ai/sentiment");
  },

  getNews: async (symbol?: string): Promise<NewsItem[]> => {
    return http.get<NewsItem[]>(symbol ? `/news?symbol=${symbol}` : "/news");
  },

  getSentimentDiagnostics: async (): Promise<SentimentDiagnostics> => {
    return http.get<SentimentDiagnostics>("/news/sentiment-diagnostics");
  },
};
