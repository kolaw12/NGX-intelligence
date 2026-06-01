import { ExternalLink } from "lucide-react";
import { useNews } from "@/hooks/useAIInsights";
import { cn } from "@/lib/cn";

function formatSource(source: string) {
  return source.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function NewsTicker({ className }: { className?: string }) {
  const { data: news, isError, isLoading } = useNews();
  const items = (news ?? []).slice(0, 8);

  if (isLoading) {
    return (
      <div className={cn("h-8 border-b border-border bg-surface-elevated/80", className)}>
        <div className="flex h-full items-center pl-20 text-xs text-muted-foreground">Loading market news...</div>
      </div>
    );
  }

  if (isError || items.length === 0) {
    return (
      <div className={cn("h-8 border-b border-border bg-surface-elevated/80", className)}>
        <div className="flex h-full items-center pl-20 text-xs text-muted-foreground">News unavailable</div>
      </div>
    );
  }

  const renderItems = (hidden = false) =>
    items.map((item) => (
      <a
        key={`${hidden ? "copy" : "main"}-${item.id}`}
        href={item.url}
        target="_blank"
        rel="noreferrer"
        className="flex min-w-[320px] max-w-[520px] shrink-0 items-center gap-2 text-xs text-muted-foreground transition-colors hover:text-foreground"
        title={item.headline}
      >
        <span
          className={cn(
            "h-1.5 w-1.5 shrink-0 rounded-full",
            item.sentiment === "positive" && "bg-success",
            item.sentiment === "negative" && "bg-danger",
            item.sentiment === "neutral" && "bg-muted-foreground",
          )}
        />
        <span className="truncate font-medium text-foreground">{item.headline}</span>
        <span className="shrink-0 text-[11px] uppercase tracking-wide text-muted-foreground">
          {formatSource(item.source)}
        </span>
        <ExternalLink className="h-3 w-3 shrink-0" />
      </a>
    ));

  return (
    <div className={cn("relative h-8 overflow-hidden border-b border-border bg-surface-elevated/80", className)}>
      <div className="absolute inset-y-0 left-0 z-10 flex w-16 items-center justify-center bg-gradient-to-r from-surface-elevated via-surface-elevated/90 to-transparent text-[11px] font-semibold uppercase tracking-widest text-gold-600">
        News
      </div>
      <div className="flex h-full w-max animate-ticker-scroll items-center whitespace-nowrap pl-20 will-change-transform [&:hover]:[animation-play-state:paused]">
        <div className="flex shrink-0 items-center gap-12 pr-12">{renderItems()}</div>
        <div className="flex shrink-0 items-center gap-12 pr-12" aria-hidden="true">
          {renderItems(true)}
        </div>
      </div>
    </div>
  );
}
