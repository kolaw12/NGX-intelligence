import type { Sector } from "@/types/sector";
import sectorSnapshot from "@/data/sectors.snapshot.json";

const fallbackSectors = sectorSnapshot as Sector[];

export const sectorsService = {
  list: async (): Promise<Sector[]> => {
    return fallbackSectors;
  },

  getBySlug: async (slug: string): Promise<Sector> => {
    const sector = fallbackSectors.find((item) => item.slug === slug);
    if (!sector) throw new Error(`Sector not found: ${slug}`);
    return sector;
  },
};
