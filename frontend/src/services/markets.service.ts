import type { MarketOverview } from "@/types/macro";
import marketOverviewSnapshot from "@/data/market-overview.snapshot.json";

const fallbackMarketOverview = marketOverviewSnapshot as MarketOverview;

export const marketsService = {
  getOverview: async (): Promise<MarketOverview> => {
    return fallbackMarketOverview;
  },
};
