import type { EChartsOption } from "echarts";
import { ChartContainer } from "./ChartContainer";

interface AllocationDonutProps {
  data: { name: string; value: number }[];
  height?: number;
  loading?: boolean;
}

const PALETTE = ["#00DCDC", "#E89A35", "#7F7BFF", "#22C55E", "#60A5FA", "#F472B6", "#A3E635"];

export function AllocationDonut({ data, height = 280, loading }: AllocationDonutProps) {
  const option: EChartsOption = {
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const p = params as { name: string; value: number; percent: number };
        return `<div style="font-size:11px;color:#8B95B7">${p.name}</div>
                <div style="color:#E6E8F0;font-weight:600">${p.value.toFixed(2)}% allocation</div>`;
      },
    },
    legend: {
      orient: "vertical",
      right: 0,
      top: "center",
      icon: "circle",
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: "#C6CBDD", fontSize: 11 },
    },
    series: [
      {
        type: "pie",
        radius: ["58%", "78%"],
        center: ["32%", "50%"],
        avoidLabelOverlap: false,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: { borderColor: "#0A1233", borderWidth: 2 },
        data: data.map((d, i) => ({ name: d.name, value: d.value, itemStyle: { color: PALETTE[i % PALETTE.length] } })),
      },
    ],
  };

  return <ChartContainer option={option} height={height} loading={loading} />;
}
