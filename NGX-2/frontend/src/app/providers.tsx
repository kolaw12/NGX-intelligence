import { QueryClient, QueryClientProvider, keepPreviousData } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 15 * 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: "always",
      placeholderData: keepPreviousData,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
});

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider delayDuration={200}>
          {children}
          <Toaster
            theme="light"
            position="top-right"
            toastOptions={{
              style: {
                background: "rgba(255,255,255,0.98)",
                color: "#0B1437",
                border: "1px solid rgba(15,20,55,0.12)",
                boxShadow: "0 12px 32px -8px rgba(15,20,55,0.15)",
              },
            }}
          />
        </TooltipProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
}
