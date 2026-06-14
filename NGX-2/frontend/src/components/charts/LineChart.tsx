import type { EChartsOption } from "echarts";
import type { SeriesPoint } from "@/types/common";
import { ChartContainer } from "./ChartContainer";
import { BRAND } from "@/constants/brand";

interface LineChartProps {
  data: SeriesPoint[];
  height?: number;
  color?: string;
  loading?: boolean;
  showArea?: boolean;
  className?: string;
  ariaLabel?: string;
}

export function LineChart({
  data,
  height = 280,
  color = BRAND.colors.cyan,
  loading,
  showArea = true,
  className,
  ariaLabel,
}: LineChartProps) {
  const option: EChartsOption = {
    grid: { left: 8, right: 8, top: 16, bottom: 24, containLabel: true },
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const arr = params as { axisValueLabel: string; data: [string, number] }[];
        const first = arr[0];
        return `<div style="font-size:11px;color:#8B95B7">${first.axisValueLabel}</div>
                <div style="font-weight:600;color:#E6E8F0">${first.data[1].toLocaleString("en-NG", {
                  maximumFractionDigits: 2,
                })}</div>`;
      },
    },
    xAxis: {
      type: "time",
      axisLabel: { color: "#8B95B7", fontSize: 10 },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { color: "#8B95B7", fontSize: 10 },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
    },
    series: [
      {
        type: "line",
        data: data.map((p) => [p.time, p.value]),
        smooth: true,
        symbol: "none",
        lineStyle: { color, width: 2 },
        areaStyle: showArea
          ? {
              color: {
                type: "linear",
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: `${color}44` },
                  { offset: 1, color: `${color}00` },
                ],
              },
            }
          : undefined,
      },
    ],
  };

  return <ChartContainer option={option} height={height} loading={loading} className={className} ariaLabel={ariaLabel} />;
}
