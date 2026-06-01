import type { EChartsOption } from "echarts";
import { ChartContainer } from "./ChartContainer";
import { BRAND } from "@/constants/brand";

interface GaugeChartProps {
  value: number;
  label?: string;
  height?: number;
  loading?: boolean;
}

export function GaugeChart({ value, label, height = 200, loading }: GaugeChartProps) {
  const option: EChartsOption = {
    series: [
      {
        type: "gauge",
        startAngle: 200,
        endAngle: -20,
        min: 0,
        max: 100,
        radius: "100%",
        center: ["50%", "62%"],
        progress: { show: true, width: 12, itemStyle: { color: BRAND.colors.cyan } },
        axisLine: {
          lineStyle: {
            width: 12,
            color: [
              [0.3, BRAND.colors.danger],
              [0.7, BRAND.colors.gold],
              [1, BRAND.colors.success],
            ],
          },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        anchor: { show: false },
        title: {
          offsetCenter: [0, "32%"],
          color: "#8B95B7",
          fontSize: 11,
        },
        detail: {
          valueAnimation: true,
          formatter: (v) => `${Math.round(v as number)}`,
          color: "#E6E8F0",
          fontSize: 28,
          fontWeight: 600,
          offsetCenter: [0, "0%"],
        },
        data: [{ value, name: label ?? "" }],
      },
    ],
  };

  return <ChartContainer option={option} height={height} loading={loading} />;
}
