import type { EChartsOption } from "echarts";
import { ChartContainer } from "./ChartContainer";
import { BRAND } from "@/constants/brand";

interface SectorBarChartProps {
  data: { name: string; value: number }[];
  height?: number;
  loading?: boolean;
}

export function SectorBarChart({ data, height = 320, loading }: SectorBarChartProps) {
  const sorted = [...data].sort((a, b) => a.value - b.value);
  const option: EChartsOption = {
    grid: { left: 8, right: 32, top: 8, bottom: 24, containLabel: true },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const arr = params as { name: string; value: number }[];
        const p = arr[0];
        const color = p.value >= 0 ? BRAND.colors.success : BRAND.colors.danger;
        return `<div style="font-size:11px;color:#8B95B7">${p.name}</div>
                <div style="color:${color};font-weight:600">${p.value > 0 ? "+" : ""}${p.value.toFixed(2)}%</div>`;
      },
    },
    xAxis: {
      type: "value",
      axisLabel: { formatter: "{value}%", color: "#8B95B7", fontSize: 10 },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
    },
    yAxis: {
      type: "category",
      data: sorted.map((d) => d.name),
      axisLabel: { color: "#C6CBDD", fontSize: 11 },
    },
    series: [
      {
        type: "bar",
        data: sorted.map((d) => ({
          value: d.value,
          itemStyle: {
            color: d.value >= 0 ? BRAND.colors.success : BRAND.colors.danger,
            borderRadius: 3,
          },
        })),
        barWidth: 14,
        label: {
          show: true,
          position: "right",
          color: "#C6CBDD",
          fontSize: 10,
          formatter: (v) => {
            const n = typeof v.value === "number" ? v.value : 0;
            return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
          },
        },
      },
    ],
  };

  return <ChartContainer option={option} height={height} loading={loading} />;
}
