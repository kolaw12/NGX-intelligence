import type { ActivityEvent, AdminMetrics, AdminUser, UpdateUserRequest } from "@/types/admin";
import { http } from "./http.client";

export const adminService = {
  getMetrics: async (): Promise<AdminMetrics> => {
    return http.get<AdminMetrics>("/admin/metrics");
  },

  listUsers: async (query?: string): Promise<AdminUser[]> => {
    return http.get<AdminUser[]>(`/admin/users${query ? `?q=${encodeURIComponent(query)}` : ""}`);
  },

  updateUser: async (id: string, patch: UpdateUserRequest): Promise<AdminUser> => {
    return http.put<AdminUser>(`/admin/users/${id}`, patch);
  },

  deleteUser: async (id: string): Promise<void> => {
    return http.delete<void>(`/admin/users/${id}`);
  },

  getActivity: async (filter?: { userId?: string; type?: string; limit?: number }): Promise<ActivityEvent[]> => {
    const params = new URLSearchParams();
    if (filter?.limit) params.set("limit", String(filter.limit));
    return http.get<ActivityEvent[]>(`/admin/activity${params.toString() ? `?${params.toString()}` : ""}`);
  },
};
