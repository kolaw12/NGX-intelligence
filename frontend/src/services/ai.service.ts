import type { AIInsight, MarketSentiment, NewsItem, SentimentDiagnostics } from "@/types/ai";
import type { Stock } from "@/types/stock";
import { http } from "./http.client";
import stockSnapshot from "@/data/stocks.snapshot.json";
import xgboostSignalSnapshot from "@/data/xgboost-signals.snapshot.json";

const fallbackStocks = stockSnapshot as Stock[];
type XGBoostSignal = {
  public_symbol: string;
  probability: number;
  recommendation: "BUY" | "HOLD" | "SELL" | "AVOID";
  outlook: Stock["aiOutlook"];
  confidence: number;
  risk_score: number;
  model_version: string;
  sentiment_score: number;
  sentiment_label: string;
};
const xgboostSignals = xgboostSignalSnapshot.signals as Record<string, XGBoostSignal>;

function findStock(symbol: string) {
  return fallbackStocks.find((stock) => stock.symbol.toUpperCase() === symbol.toUpperCase());
}

function findSignal(symbol: string) {
  return xgboostSignals[symbol.toUpperCase()];
}

function buildInsight(stock: Stock): AIInsight {
  const signal = findSignal(stock.symbol);
  const confidence = Math.max(0, Math.min(100, Math.round(signal?.confidence ?? stock.confidence ?? 0)));
  const outlook = signal?.outlook ?? stock.aiOutlook;
  const riskTotal = Math.round(signal?.risk_score ?? stock.riskScore ?? 45);
  const marketRisk = Math.round(Math.min(35, Math.max(12, riskTotal * 0.35)));
  const sectorRisk = Math.round(Math.min(35, Math.max(10, riskTotal * 0.3)));
  const companyRisk = Math.max(8, riskTotal - marketRisk - sectorRisk);
  const upProbability = signal ? Math.round(signal.probability * 100) : null;
  const recommendation = signal?.recommendation ?? "HOLD";

  return {
    symbol: stock.symbol,
    outlook,
    confidence,
    summary:
      signal && outlook === "bullish"
        ? `The trained XGBoost model gives ${stock.symbol} a ${upProbability}% upside probability, producing a ${recommendation} signal after risk and sentiment checks.`
        : signal && outlook === "bearish"
          ? `The trained XGBoost model gives ${stock.symbol} a ${upProbability}% upside probability, so the current model signal is ${recommendation}.`
          : signal
            ? `The trained XGBoost model gives ${stock.symbol} a ${upProbability}% upside probability; confidence is not strong enough for a decisive BUY or SELL.`
            : `${stock.symbol} is using the bundled market fallback because no XGBoost signal was exported for this ticker.`,
    drivers: [
      {
        label: signal ? `XGBoost upside probability (${upProbability}%)` : "model signal unavailable",
        direction: signal ? (signal.probability >= 0.6 ? "positive" : signal.probability <= 0.4 ? "negative" : "neutral") : "neutral",
        weight: signal ? Math.min(0.45, Math.max(0.12, Math.abs(signal.probability - 0.5))) : 0.1,
      },
      { label: "daily price change", direction: stock.changePct >= 0 ? "positive" : "negative", weight: Math.min(0.3, Math.max(0.08, Math.abs(stock.changePct) / 30)) },
      { label: "trading volume", direction: stock.volume > 0 ? "positive" : "neutral", weight: stock.volume > 0 ? 0.18 : 0.08 },
      { label: "risk score", direction: riskTotal > 60 ? "negative" : riskTotal < 35 ? "positive" : "neutral", weight: 0.14 },
      {
        label: `sentiment ${signal?.sentiment_label ?? "neutral"}`,
        direction: (signal?.sentiment_score ?? 0) > 0.15 ? "positive" : (signal?.sentiment_score ?? 0) < -0.15 ? "negative" : "neutral",
        weight: 0.1,
      },
    ],
    risks: { marketRisk, sectorRisk, companyRisk },
    generatedAt: xgboostSignalSnapshot.generatedAt,
    horizonDays: 30,
    modelVersion: signal ? `xgboost:${signal.model_version}` : "bundled-snapshot-fallback",
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
