import { useQuery } from "@tanstack/react-query";
import { engineService } from "@/services/engine.service";

export function useModelStatus() {
  return useQuery({
    queryKey: ["engine", "model-status"],
    queryFn: engineService.modelStatus,
    staleTime: 60_000,
  });
}

export function useEngineHealth() {
  return useQuery({
    queryKey: ["engine", "health"],
    queryFn: engineService.engineHealth,
    staleTime: 30_000,
  });
}
