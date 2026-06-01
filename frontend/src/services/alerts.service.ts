import type { Alert } from "@/types/auth";
import { http } from "./http.client";

export const alertsService = {
  list: async (): Promise<Alert[]> => {
    return http.get<Alert[]>("/alerts");
  },

  create: async (input: Omit<Alert, "id" | "createdAt" | "status">): Promise<Alert> => {
    return http.post<Alert>("/alerts", input);
  },

  remove: async (id: string): Promise<void> => {
    return http.delete<void>(`/alerts/${id}`);
  },
};
