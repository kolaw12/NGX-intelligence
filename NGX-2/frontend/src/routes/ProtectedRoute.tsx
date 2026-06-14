import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/auth.store";
import { ROUTES } from "@/constants/routes";

export function ProtectedRoute() {
  const isHydrated = useAuthStore((s) => s.isHydrated);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated());
  const location = useLocation();

  if (!isHydrated) return null;
  if (!isAuthenticated) {
    return <Navigate to={ROUTES.login} state={{ from: location }} replace />;
  }
  return <Outlet />;
}
