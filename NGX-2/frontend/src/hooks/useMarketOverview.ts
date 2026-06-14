import { useQuery } from "@tanstack/react-query";
import { marketsService } from "@/services/markets.service";
import { qk } from "@/constants/query-keys";

export function useMarketOverview() {
  return useQuery({
    queryKey: qk.marketOverview,
    queryFn: () => marketsService.getOverview(),
    refetchInterval: 60_000,
    staleTime: 45_000,
  });
}
