import { useQuery } from "@tanstack/react-query";
import { macroService } from "@/services/macro.service";
import { qk } from "@/constants/query-keys";

export function useMacroIndicators() {
  return useQuery({ queryKey: qk.macroIndicators, queryFn: () => macroService.getIndicators(), staleTime: 5 * 60_000 });
}

export function useMacroEvents() {
  return useQuery({ queryKey: qk.macroEvents, queryFn: () => macroService.getEvents(), staleTime: 5 * 60_000 });
}
