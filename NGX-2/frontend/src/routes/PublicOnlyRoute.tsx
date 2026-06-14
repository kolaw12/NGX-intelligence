import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "@/store/auth.store";
import { ROUTES } from "@/constants/routes";

export function PublicOnlyRoute() {
  const isHydrated = useAuthStore((s) => s.isHydrated);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated());
  const user = useAuthStore((s) => s.user);

  if (!isHydrated) return null;
  if (isAuthenticated) {
    return <Navigate to={user?.role === "admin" ? ROUTES.admin : ROUTES.dashboard} replace />;
  }
  return <Outlet />;
}
