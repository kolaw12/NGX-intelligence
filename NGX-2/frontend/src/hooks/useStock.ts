import { useQuery } from "@tanstack/react-query";
import { stocksService } from "@/services/stocks.service";
import { qk } from "@/constants/query-keys";
import type { Range } from "@/types/common";

export function useStock(symbol: string) {
  return useQuery({
    queryKey: qk.stock(symbol),
    queryFn: () => stocksService.getBySymbol(symbol),
    enabled: Boolean(symbol),
  });
}

export function useStockOHLC(symbol: string, range: Range) {
  return useQuery({
    queryKey: qk.stockChart(symbol, range),
    queryFn: () => stocksService.getOHLC(symbol, range),
    enabled: Boolean(symbol),
  });
}

export function useStockLine(symbol: string, range: Range) {
  return useQuery({
    queryKey: [...qk.stockChart(symbol, range), "line"],
    queryFn: () => stocksService.getLine(symbol, range),
    enabled: Boolean(symbol),
  });
}

export function useStockFundamentals(symbol: string) {
  return useQuery({
    queryKey: [...qk.stock(symbol), "fundamentals"],
    queryFn: () => stocksService.getFundamentals(symbol),
    enabled: Boolean(symbol),
  });
}

export function useStockPeers(symbol: string) {
  return useQuery({
    queryKey: [...qk.stock(symbol), "peers"],
    queryFn: () => stocksService.getPeers(symbol),
    enabled: Boolean(symbol),
  });
}
