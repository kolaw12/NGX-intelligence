import { useQuery } from "@tanstack/react-query";
import { aiService } from "@/services/ai.service";
import { qk } from "@/constants/query-keys";

export function useAIInsight(symbol: string) {
  return useQuery({
    queryKey: qk.aiInsight(symbol),
    queryFn: () => aiService.getInsight(symbol),
    enabled: Boolean(symbol),
    staleTime: 10 * 60_000,
  });
}

export function useAIInsights() {
  return useQuery({ queryKey: qk.aiInsights, queryFn: () => aiService.listInsights(), staleTime: 10 * 60_000 });
}

export function useMarketSentiment(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: qk.marketSentiment,
    queryFn: () => aiService.getMarketSentiment(),
    staleTime: 60_000,
    ...options,
  });
}

export function useNews(symbol?: string) {
  return useQuery({ queryKey: qk.news(symbol), queryFn: () => aiService.getNews(symbol), staleTime: 5 * 60_000 });
}

export function useSentimentDiagnostics() {
  return useQuery({
    queryKey: ["news", "sentiment-diagnostics"],
    queryFn: aiService.getSentimentDiagnostics,
    staleTime: 5 * 60_000,
  });
}
