import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/auth.store";
import { ROUTES } from "@/constants/routes";

export function AdminProtectedRoute() {
  const isHydrated = useAuthStore((s) => s.isHydrated);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated());
  const user = useAuthStore((s) => s.user);
  const location = useLocation();

  if (!isHydrated) return null;
  if (!isAuthenticated) {
    return <Navigate to={ROUTES.login} state={{ from: location }} replace />;
  }
  if (user?.role !== "admin") {
    return <Navigate to={ROUTES.dashboard} replace />;
  }
  return <Outlet />;
}
