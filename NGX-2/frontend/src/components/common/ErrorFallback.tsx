import { AlertTriangle, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

interface ErrorFallbackProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorFallback({ message = "We couldn't load this data.", onRetry, className }: ErrorFallbackProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-danger/30 bg-danger-soft p-6 text-center",
        className,
      )}
    >
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-danger/20 text-danger">
        <AlertTriangle className="h-4 w-4" />
      </div>
      <p className="text-sm text-foreground">{message}</p>
      {onRetry && (
        <Button size="sm" variant="secondary" onClick={onRetry}>
          <RefreshCcw className="h-4 w-4" /> Retry
        </Button>
      )}
    </div>
  );
}
