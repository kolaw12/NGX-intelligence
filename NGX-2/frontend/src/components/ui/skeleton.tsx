import { cn } from "@/lib/cn";

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-lg bg-gradient-to-r from-surface-elevated via-surface to-surface-elevated bg-[length:200%_100%]",
        className,
      )}
      {...props}
    />
  );
}
