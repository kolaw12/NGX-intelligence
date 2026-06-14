import type { AIInsight, MarketSentiment, NewsItem, SentimentDiagnostics } from "@/types/ai";
import { http } from "./http.client";

export const aiService = {
  getInsight: async (symbol: string): Promise<AIInsight> => {
    return http.get<AIInsight>(`/ai/insights/${symbol}`);
  },

  listInsights: async (): Promise<AIInsight[]> => {
    return http.get<AIInsight[]>("/ai/insights");
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
