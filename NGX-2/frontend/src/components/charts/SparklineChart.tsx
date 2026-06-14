import type { EChartsOption } from "echarts";
import { ChartContainer } from "./ChartContainer";
import { BRAND } from "@/constants/brand";

interface SparklineChartProps {
  data: number[];
  height?: number;
  color?: string;
  positive?: boolean;
  className?: string;
}

export function SparklineChart({ data, height = 36, color, positive, className }: SparklineChartProps) {
  const resolved =
    color ?? (positive === undefined ? BRAND.colors.cyan : positive ? BRAND.colors.success : BRAND.colors.danger);

  const option: EChartsOption = {
    grid: { left: 0, right: 0, top: 2, bottom: 2 },
    xAxis: { type: "category", show: false, data: data.map((_, i) => i) },
    yAxis: { type: "value", show: false, scale: true },
    tooltip: { show: false },
    series: [
      {
        type: "line",
        data,
        smooth: true,
        symbol: "none",
        lineStyle: { color: resolved, width: 1.6 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: `${resolved}55` },
              { offset: 1, color: `${resolved}00` },
            ],
          },
        },
      },
    ],
  };

  return <ChartContainer option={option} height={height} className={className} />;
}
