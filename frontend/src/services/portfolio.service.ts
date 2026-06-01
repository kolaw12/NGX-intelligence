import type { PortfolioSummary } from "@/types/portfolio";
import { http } from "./http.client";

export const portfolioService = {
  getSummary: async (): Promise<PortfolioSummary> => {
    return http.get<PortfolioSummary>("/portfolio");
  },
};
