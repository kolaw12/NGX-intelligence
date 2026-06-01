import { useEffect, useRef } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { registerEchartsTheme, NGX_THEME_NAME } from "@/lib/echarts-theme";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

registerEchartsTheme();

interface ChartContainerProps {
  option: EChartsOption;
  height?: number | string;
  loading?: boolean;
  className?: string;
  notMerge?: boolean;
  onEvents?: Record<string, (...args: unknown[]) => void>;
  ariaLabel?: string;
}

export function ChartContainer({
  option,
  height = 280,
  loading,
  className,
  notMerge = true,
  onEvents,
  ariaLabel,
}: ChartContainerProps) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ReactECharts | null>(null);

  useEffect(() => {
    if (!wrapRef.current) return;
    const observer = new ResizeObserver(() => {
      chartRef.current?.getEchartsInstance().resize();
    });
    observer.observe(wrapRef.current);
    return () => observer.disconnect();
  }, []);

  if (loading) {
    return <Skeleton className={cn("w-full", className)} style={{ height }} aria-label={ariaLabel} />;
  }

  return (
    <div ref={wrapRef} className={cn("w-full", className)} aria-label={ariaLabel}>
      <ReactECharts
        ref={(r) => {
          chartRef.current = r;
        }}
        option={option}
        theme={NGX_THEME_NAME}
        notMerge={notMerge}
        lazyUpdate
        style={{ height: typeof height === "number" ? `${height}px` : height, width: "100%" }}
        opts={{ renderer: "canvas" }}
        onEvents={onEvents}
      />
    </div>
  );
}
