import { AppRoutes } from "@/routes";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";

export function App() {
  return (
    <ErrorBoundary>
      <AppRoutes />
    </ErrorBoundary>
  );
}
