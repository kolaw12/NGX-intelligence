import type { MacroIndicator, MacroEvent } from "@/types/macro";
import { http } from "./http.client";

export const macroService = {
  getIndicators: async (): Promise<MacroIndicator[]> => {
    return http.get<MacroIndicator[]>("/macro/indicators");
  },

  getEvents: async (): Promise<MacroEvent[]> => {
    return http.get<MacroEvent[]>("/macro/events");
  },
};
