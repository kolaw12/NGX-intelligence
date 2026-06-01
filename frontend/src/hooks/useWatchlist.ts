import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { watchlistService } from "@/services/watchlist.service";
import { qk } from "@/constants/query-keys";

export function useWatchlists() {
  return useQuery({ queryKey: qk.watchlists, queryFn: () => watchlistService.list(), staleTime: 2 * 60_000 });
}

export function useCreateWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, description }: { name: string; description?: string }) =>
      watchlistService.create(name, description),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.watchlists }),
  });
}

export function useAddToWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, symbol }: { id: string; symbol: string }) => watchlistService.addSymbol(id, symbol),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.watchlists }),
  });
}

export function useRemoveFromWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, symbol }: { id: string; symbol: string }) =>
      watchlistService.removeSymbol(id, symbol),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.watchlists }),
  });
}

export function useDeleteWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => watchlistService.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.watchlists }),
  });
}
