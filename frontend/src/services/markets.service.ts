import type { MarketOverview } from "@/types/macro";
import { http } from "./http.client";

export const marketsService = {
  getOverview: async (): Promise<MarketOverview> => {
    return http.get<MarketOverview>("/market/overview");
  },
};
