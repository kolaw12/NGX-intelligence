import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminService } from "@/services/admin.service";
import type { UpdateUserRequest } from "@/types/admin";

const ADMIN_KEY = {
  metrics: ["admin", "metrics"] as const,
  users: (q?: string) => ["admin", "users", q ?? ""] as const,
  activity: (filter?: { userId?: string; type?: string }) => ["admin", "activity", filter ?? {}] as const,
};

export function useAdminMetrics() {
  return useQuery({ queryKey: ADMIN_KEY.metrics, queryFn: () => adminService.getMetrics() });
}

export function useAdminUsers(query?: string) {
  return useQuery({
    queryKey: ADMIN_KEY.users(query),
    queryFn: () => adminService.listUsers(query),
  });
}

export function useUpdateAdminUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: UpdateUserRequest }) => adminService.updateUser(id, patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin"] });
    },
  });
}

export function useDeleteAdminUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminService.deleteUser(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin"] });
    },
  });
}

export function useAdminActivity(filter?: { userId?: string; type?: string }) {
  return useQuery({
    queryKey: ADMIN_KEY.activity(filter),
    queryFn: () => adminService.getActivity(filter),
  });
}
