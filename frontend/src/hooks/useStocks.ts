import { useQuery } from "@tanstack/react-query";
import { stocksService } from "@/services/stocks.service";
import { qk } from "@/constants/query-keys";

export function useStocks() {
  return useQuery({
    queryKey: qk.stocks,
    queryFn: () => stocksService.list(),
    staleTime: 5 * 60_000,
  });
}

export function useStocksBySector(slug: string) {
  return useQuery({
    queryKey: qk.stocksBySector(slug),
    queryFn: () => stocksService.getBySector(slug),
    enabled: Boolean(slug),
    staleTime: 5 * 60_000,
  });
}

export function useTopGainers(limit = 5) {
  return useQuery({
    queryKey: [...qk.topMovers, "gainers", limit],
    queryFn: () => stocksService.topGainers(limit),
    staleTime: 60_000,
  });
}

export function useTopLosers(limit = 5) {
  return useQuery({
    queryKey: [...qk.topMovers, "losers", limit],
    queryFn: () => stocksService.topLosers(limit),
    staleTime: 60_000,
  });
}

export function useMostActive(limit = 5) {
  return useQuery({
    queryKey: [...qk.topMovers, "active", limit],
    queryFn: () => stocksService.mostActive(limit),
    staleTime: 60_000,
  });
}
