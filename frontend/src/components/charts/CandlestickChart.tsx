import type { EChartsOption } from "echarts";
import type { OHLC } from "@/types/common";
import { ChartContainer } from "./ChartContainer";
import { BRAND } from "@/constants/brand";

interface CandlestickChartProps {
  data: OHLC[];
  height?: number;
  loading?: boolean;
  showVolume?: boolean;
  className?: string;
}

export function CandlestickChart({
  data,
  height = 420,
  loading,
  showVolume = true,
  className,
}: CandlestickChartProps) {
  const dates = data.map((d) => d.time);
  const ohlc = data.map((d) => [d.open, d.close, d.low, d.high]);
  const volumes = data.map((d, i) => ({
    value: d.volume,
    itemStyle: { color: d.close >= d.open ? `${BRAND.colors.success}66` : `${BRAND.colors.danger}66` },
    index: i,
  }));

  const option: EChartsOption = {
    animation: false,
    grid: showVolume
      ? [
          { left: 60, right: 16, top: 16, height: "65%" },
          { left: 60, right: 16, top: "78%", height: "16%" },
        ]
      : [{ left: 60, right: 16, top: 16, bottom: 32 }],
    axisPointer: {
      link: [{ xAxisIndex: "all" }],
      label: { backgroundColor: "#2D3B84" },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      backgroundColor: "rgba(13,22,55,0.96)",
      borderColor: "rgba(255,255,255,0.10)",
      textStyle: { color: "#E6E8F0", fontSize: 12 },
      formatter: (params: unknown) => {
        const arr = params as Array<{ seriesType: string; data: number[] | { value: number }; axisValueLabel: string }>;
        const candle = arr.find((p) => p.seriesType === "candlestick");
        if (!candle) return "";
        const [o, c, l, h] = candle.data as number[];
        const positive = c >= o;
        return `
          <div style="font-size:11px;color:#8B95B7;margin-bottom:4px">${candle.axisValueLabel}</div>
          <div style="display:grid;grid-template-columns:auto auto;gap:6px 16px;font-size:12px">
            <span style="color:#8B95B7">Open</span><span style="color:#E6E8F0;text-align:right">${o.toFixed(2)}</span>
            <span style="color:#8B95B7">High</span><span style="color:#E6E8F0;text-align:right">${h.toFixed(2)}</span>
            <span style="color:#8B95B7">Low</span><span style="color:#E6E8F0;text-align:right">${l.toFixed(2)}</span>
            <span style="color:#8B95B7">Close</span><span style="color:${positive ? BRAND.colors.success : BRAND.colors.danger};text-align:right;font-weight:600">${c.toFixed(2)}</span>
          </div>`;
      },
    },
    xAxis: [
      {
        type: "category",
        data: dates,
        boundaryGap: true,
        axisLabel: {
          formatter: (v: string) => {
            const d = new Date(v);
            return `${d.getMonth() + 1}/${d.getDate()}`;
          },
          color: "#8B95B7",
          fontSize: 10,
        },
        axisLine: { lineStyle: { color: "rgba(255,255,255,0.08)" } },
      },
      ...(showVolume
        ? [
            {
              type: "category" as const,
              gridIndex: 1,
              data: dates,
              boundaryGap: true,
              axisLabel: { show: false },
              axisLine: { lineStyle: { color: "rgba(255,255,255,0.08)" } },
              axisTick: { show: false },
            },
          ]
        : []),
    ],
    yAxis: [
      {
        type: "value",
        scale: true,
        position: "right",
        axisLabel: { color: "#8B95B7", fontSize: 10 },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
      },
      ...(showVolume
        ? [
            {
              type: "value" as const,
              gridIndex: 1,
              position: "right" as const,
              axisLabel: {
                color: "#8B95B7",
                fontSize: 10,
                formatter: (v: number) => (v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(0)}K` : `${v}`),
              },
              splitLine: { lineStyle: { color: "rgba(255,255,255,0.04)" } },
            },
          ]
        : []),
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: showVolume ? [0, 1] : [0], start: 0, end: 100 },
    ],
    series: [
      {
        type: "candlestick",
        data: ohlc,
        itemStyle: {
          color: BRAND.colors.success,
          color0: BRAND.colors.danger,
          borderColor: BRAND.colors.success,
          borderColor0: BRAND.colors.danger,
        },
      },
      ...(showVolume
        ? [
            {
              type: "bar" as const,
              xAxisIndex: 1,
              yAxisIndex: 1,
              data: volumes,
              barWidth: "60%",
            },
          ]
        : []),
    ],
  };

  return <ChartContainer option={option} height={height} loading={loading} className={className} />;
}
