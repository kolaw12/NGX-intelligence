import { Skeleton } from "@/components/ui/skeleton";

export function CardSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3 rounded-xl border border-border bg-surface/60 p-5">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-7 w-40" />
      <div className="space-y-2 pt-2">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-3 w-full" />
        ))}
      </div>
    </div>
  );
}

export function ChartSkeleton({ height = 280 }: { height?: number }) {
  return (
    <div className="rounded-xl border border-border bg-surface/60 p-4">
      <Skeleton className="mb-3 h-4 w-32" />
      <Skeleton className="w-full" style={{ height }} />
    </div>
  );
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2 rounded-xl border border-border bg-surface/60 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="grid grid-cols-5 gap-3">
          <Skeleton className="h-4 col-span-1" />
          <Skeleton className="h-4 col-span-1" />
          <Skeleton className="h-4 col-span-1" />
          <Skeleton className="h-4 col-span-1" />
          <Skeleton className="h-4 col-span-1" />
        </div>
      ))}
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-6 p-6">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-4 w-96" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
      <ChartSkeleton />
    </div>
  );
}
