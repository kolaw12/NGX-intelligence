import type { MarketOverview } from "@/types/macro";
import marketOverviewSnapshot from "@/data/market-overview.snapshot.json";
import { http } from "./http.client";

const fallbackMarketOverview = marketOverviewSnapshot as MarketOverview;

export const marketsService = {
  getOverview: async (): Promise<MarketOverview> => {
    return http.get<MarketOverview>("/market/overview").catch(() => fallbackMarketOverview);
  },
};
