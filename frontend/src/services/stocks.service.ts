import type { Stock, StockDetail, FundamentalsRow, PeerStock } from "@/types/stock";
import type { OHLC, Range, SeriesPoint } from "@/types/common";
import { http } from "./http.client";

export const stocksService = {
  list: async (): Promise<Stock[]> => {
    return http.get<Stock[]>("/stocks");
  },

  getBySymbol: async (symbol: string): Promise<StockDetail> => {
    return http.get<StockDetail>(`/stocks/${symbol}`);
  },

  getBySector: async (slug: string): Promise<Stock[]> => {
    return http.get<Stock[]>(`/stocks?sector=${slug}`);
  },

  getOHLC: async (symbol: string, range: Range): Promise<OHLC[]> => {
    return http.get<OHLC[]>(`/stocks/${symbol}/ohlc?range=${range}`).catch(() => []);
  },

  getLine: async (symbol: string, range: Range): Promise<SeriesPoint[]> => {
    return http.get<SeriesPoint[]>(`/stocks/${symbol}/line?range=${range}`).catch(() => []);
  },

  getFundamentals: async (symbol: string): Promise<FundamentalsRow[]> => {
    return http.get<FundamentalsRow[]>(`/stocks/${symbol}/fundamentals`).catch(() => []);
  },

  getPeers: async (symbol: string): Promise<PeerStock[]> => {
    return http.get<PeerStock[]>(`/stocks/${symbol}/peers`).catch(() => []);
  },

  topGainers: async (limit = 5): Promise<Stock[]> => {
    return http.get<Stock[]>(`/stocks/top-gainers?limit=${limit}`);
  },

  topLosers: async (limit = 5): Promise<Stock[]> => {
    return http.get<Stock[]>(`/stocks/top-losers?limit=${limit}`);
  },

  mostActive: async (limit = 5): Promise<Stock[]> => {
    return http.get<Stock[]>(`/stocks/most-active?limit=${limit}`);
  },
};
