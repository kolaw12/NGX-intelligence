import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[NGX] ErrorBoundary caught", error, info);
  }

  reset = () => {
    this.setState({ hasError: false, error: undefined });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-danger-soft text-danger">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <div className="space-y-1">
            <p className="text-base font-semibold text-foreground">Something went wrong</p>
            <p className="max-w-md text-sm text-muted-foreground">
              An unexpected error occurred while rendering this section. Reload to try again, or contact support if the
              issue persists.
            </p>
          </div>
          <div className="flex gap-2">
            <Button onClick={this.reset} variant="secondary" size="sm">
              <RefreshCcw className="h-4 w-4" /> Try again
            </Button>
            <Button onClick={() => window.location.reload()} variant="outline" size="sm">
              Reload page
            </Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
