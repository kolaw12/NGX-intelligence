import { useQuery } from "@tanstack/react-query";
import { portfolioService } from "@/services/portfolio.service";
import { qk } from "@/constants/query-keys";

export function usePortfolio() {
  return useQuery({ queryKey: qk.portfolio, queryFn: () => portfolioService.getSummary(), staleTime: 60_000 });
}
