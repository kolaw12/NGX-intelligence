import * as echarts from "echarts/core";
import { BRAND } from "@/constants/brand";

export const NGX_THEME_NAME = "ngx-intelligence";

let registered = false;

export function registerEchartsTheme(): void {
  if (registered) return;
  echarts.registerTheme(NGX_THEME_NAME, {
    color: [
      BRAND.colors.cyan,
      BRAND.colors.gold,
      "#5B6BFF",
      BRAND.colors.success,
      BRAND.colors.danger,
      "#A855F7",
      "#3B82F6",
      "#84CC16",
    ],
    backgroundColor: "transparent",
    textStyle: {
      fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      color: "#475569",
    },
    title: {
      textStyle: { color: "#0B1437", fontWeight: 600 },
      subtextStyle: { color: "#64748B" },
    },
    grid: {
      left: 8,
      right: 8,
      top: 24,
      bottom: 24,
      containLabel: true,
    },
    categoryAxis: {
      axisLine: { lineStyle: { color: "rgba(15,20,55,0.10)" } },
      axisTick: { show: false },
      axisLabel: { color: "#64748B", fontSize: 11 },
      splitLine: { show: false },
    },
    valueAxis: {
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: "#64748B", fontSize: 11 },
      splitLine: { lineStyle: { color: "rgba(15,20,55,0.06)" } },
    },
    legend: {
      textStyle: { color: "#475569" },
      icon: "roundRect",
    },
    tooltip: {
      backgroundColor: "rgba(255,255,255,0.98)",
      borderColor: "rgba(15,20,55,0.12)",
      borderWidth: 1,
      textStyle: { color: "#0B1437", fontSize: 12 },
      extraCssText:
        "backdrop-filter: blur(8px); border-radius: 10px; padding: 10px 12px; box-shadow: 0 12px 32px -8px rgba(15,20,55,0.15);",
      axisPointer: {
        type: "cross",
        lineStyle: { color: "rgba(0,180,180,0.5)", type: "dashed" },
        crossStyle: { color: "rgba(0,180,180,0.5)" },
        label: { backgroundColor: "#2D3B84", color: "#FFFFFF" },
      },
    },
    candlestick: {
      itemStyle: {
        color: BRAND.colors.success,
        color0: BRAND.colors.danger,
        borderColor: BRAND.colors.success,
        borderColor0: BRAND.colors.danger,
      },
    },
    line: {
      smooth: true,
      symbol: "none",
      lineStyle: { width: 2 },
    },
    bar: {
      itemStyle: { borderRadius: [4, 4, 0, 0] },
    },
  });
  registered = true;
}
