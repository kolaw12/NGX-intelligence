import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { alertsService } from "@/services/alerts.service";
import { qk } from "@/constants/query-keys";
import type { Alert } from "@/types/auth";

export function useAlerts() {
  return useQuery({ queryKey: qk.alerts, queryFn: () => alertsService.list(), staleTime: 60_000 });
}

export function useCreateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: Omit<Alert, "id" | "createdAt" | "status">) => alertsService.create(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.alerts }),
  });
}

export function useDeleteAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => alertsService.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.alerts }),
  });
}
