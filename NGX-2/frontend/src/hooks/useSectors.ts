import { useQuery } from "@tanstack/react-query";
import { sectorsService } from "@/services/sectors.service";
import { qk } from "@/constants/query-keys";

export function useSectors() {
  return useQuery({ queryKey: qk.sectors, queryFn: () => sectorsService.list(), staleTime: 10 * 60_000 });
}

export function useSector(slug: string) {
  return useQuery({
    queryKey: qk.sector(slug),
    queryFn: () => sectorsService.getBySlug(slug),
    enabled: Boolean(slug),
    staleTime: 10 * 60_000,
  });
}
