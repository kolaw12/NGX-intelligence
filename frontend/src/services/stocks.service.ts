import type { Stock, StockDetail, FundamentalsRow, PeerStock } from "@/types/stock";
import type { OHLC, Range, SeriesPoint } from "@/types/common";
import { http } from "./http.client";
import stockSnapshot from "@/data/stocks.snapshot.json";

const fallbackStocks = stockSnapshot as Stock[];

function bySymbol(symbol: string) {
  return fallbackStocks.find((stock) => stock.symbol.toUpperCase() === symbol.toUpperCase());
}

function sortedFallback(sorter: (a: Stock, b: Stock) => number, limit: number) {
  return [...fallbackStocks].sort(sorter).slice(0, limit);
}

export const stocksService = {
  list: async (): Promise<Stock[]> => {
    return fallbackStocks;
  },

  getBySymbol: async (symbol: string): Promise<StockDetail> => {
    const stock = bySymbol(symbol);
    if (!stock) throw new Error(`Ticker not found: ${symbol}`);
    return {
      ...stock,
      description: `${stock.name} is listed on the Nigerian Exchange and tracked from the bundled NGX Intelligence market snapshot.`,
      founded: null,
      headquarters: null,
      employees: null,
      website: null,
      ceo: null,
      industry: stock.sector,
      exchange: "NGX",
      fundamentalsSource: "bundled snapshot",
      ohlc: [],
      intradayLine: [],
    };
  },

  getBySector: async (slug: string): Promise<Stock[]> => {
    return fallbackStocks.filter((stock) => stock.sectorSlug === slug);
  },

  getOHLC: async (symbol: string, range: Range): Promise<OHLC[]> => {
    return http.get<OHLC[]>(`/stocks/${symbol}/ohlc?range=${range}`).catch(() => []);
  },

  getLine: async (symbol: string, range: Range): Promise<SeriesPoint[]> => {
    return http.get<SeriesPoint[]>(`/stocks/${symbol}/line?range=${range}`).catch(() => []);
  },

  getFundamentals: async (symbol: string): Promise<FundamentalsRow[]> => {
    const stock = bySymbol(symbol);
    if (!stock) return [];
    return [
      { metric: "Latest close (market snapshot)", fy2021: "Unavailable", fy2022: "Unavailable", fy2023: "Unavailable", ttm: stock.price },
      { metric: "Latest daily change", fy2021: "Unavailable", fy2022: "Unavailable", fy2023: "Unavailable", ttm: `${stock.changePct.toFixed(2)}%` },
      { metric: "Latest volume", fy2021: "Unavailable", fy2022: "Unavailable", fy2023: "Unavailable", ttm: stock.volume.toLocaleString() },
      { metric: "52-week high", fy2021: "Unavailable", fy2022: "Unavailable", fy2023: "Unavailable", ttm: stock.high52w },
      { metric: "52-week low", fy2021: "Unavailable", fy2022: "Unavailable", fy2023: "Unavailable", ttm: stock.low52w },
      { metric: "Risk score", fy2021: "Unavailable", fy2022: "Unavailable", fy2023: "Unavailable", ttm: stock.riskScore },
    ];
  },

  getPeers: async (symbol: string): Promise<PeerStock[]> => {
    const stock = bySymbol(symbol);
    if (!stock) return [];
    return fallbackStocks
      .filter((peer) => peer.sectorSlug === stock.sectorSlug && peer.symbol !== stock.symbol)
      .sort((a, b) => b.volume - a.volume)
      .slice(0, 12)
      .map((peer) => ({
        symbol: peer.symbol,
        name: peer.name,
        price: peer.price,
        changePct: peer.changePct,
        marketCap: peer.marketCap,
        pe: peer.pe,
        aiOutlook: peer.aiOutlook,
      }));
  },

  topGainers: async (limit = 5): Promise<Stock[]> => {
    return sortedFallback((a, b) => b.changePct - a.changePct, limit);
  },

  topLosers: async (limit = 5): Promise<Stock[]> => {
    return sortedFallback((a, b) => a.changePct - b.changePct, limit);
  },

  mostActive: async (limit = 5): Promise<Stock[]> => {
    return sortedFallback((a, b) => b.volume - a.volume, limit);
  },
};
