import type { Sector } from "@/types/sector";
import { http } from "./http.client";

export const sectorsService = {
  list: async (): Promise<Sector[]> => {
    return http.get<Sector[]>("/sectors");
  },

  getBySlug: async (slug: string): Promise<Sector> => {
    return http.get<Sector>(`/sectors/${slug}`);
  },
};
