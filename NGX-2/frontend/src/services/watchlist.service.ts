import { http } from "./http.client";

export interface Watchlist {
  id: string;
  name: string;
  description?: string | null;
  symbols: string[];
  createdAt: string;
}

export const watchlistService = {
  list: async (): Promise<Watchlist[]> => {
    return http.get<Watchlist[]>("/watchlists");
  },

  create: async (name: string, description = ""): Promise<Watchlist> => {
    return http.post<Watchlist>("/watchlists", { name, description });
  },

  addSymbol: async (id: string, symbol: string): Promise<Watchlist> => {
    return http.post<Watchlist>(`/watchlists/${id}/symbols`, { symbol });
  },

  removeSymbol: async (id: string, symbol: string): Promise<Watchlist> => {
    return http.delete<Watchlist>(`/watchlists/${id}/symbols/${symbol}`);
  },

  remove: async (id: string): Promise<void> => {
    return http.delete<void>(`/watchlists/${id}`);
  },
};
