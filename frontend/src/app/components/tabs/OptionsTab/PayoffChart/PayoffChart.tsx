"use client";

import dynamic from "next/dynamic";
import type { PayoffResult } from "../types";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

interface PayoffChartProps {
  payoff: PayoffResult;
}

export function PayoffChart({ payoff }: PayoffChartProps) {
  if (!payoff.spotPrices.length) return null;

  const option = {
    grid: { left: 50, right: 30, top: 30, bottom: 50 },
    xAxis: {
      type: "category" as const,
      data: payoff.spotPrices.map(p => p.toFixed(0)),
      name: "Spot Price",
      nameLocation: "middle" as const,
      nameGap: 35,
      axisLine: { lineStyle: { color: "#1f1f1f" } },
      axisLabel: { color: "#484848", fontSize: 10, rotate: 45, interval: Math.floor(payoff.spotPrices.length / 10) },
    },
    yAxis: {
      type: "value" as const,
      name: "P&L",
      nameLocation: "middle" as const,
      nameGap: 45,
      axisLine: { lineStyle: { color: "#1f1f1f" } },
      axisLabel: { color: "#484848", fontSize: 10 },
      splitLine: { lineStyle: { color: "#1f1f1f" } },
    },
    series: [
      {
        name: "Payoff",
        type: "line" as const,
        data: payoff.payoffs,
        smooth: true,
        lineStyle: { width: 2 },
        itemStyle: {
          color: (params: any) => (params.value >= 0 ? "#22c55e" : "#ef4444"),
        },
        areaStyle: {
          color: {
            type: "linear" as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(34, 197, 94, 0.2)" },
              { offset: 1, color: "rgba(239, 68, 68, 0.2)" },
            ],
          },
        },
        markLine: {
          silent: true,
          data: [
            { yAxis: 0, lineStyle: { color: "#484848", type: "dashed" } },
            ...payoff.breakevens.map(b => ({
              xAxis: b.toFixed(0),
              lineStyle: { color: "#f59e0b", type: "dashed" },
              label: { formatter: "BE: {c}", color: "#f59e0b", fontSize: 10 },
            })),
          ],
        },
      },
    ],
    tooltip: {
      trigger: "axis" as const,
      formatter: (params: any[]) => {
        const p = params[0];
        return `Spot: ${p.axisValue}<br/>P&L: ₹${p.value.toFixed(2)}`;
      },
    },
  };

  return <ReactECharts option={option} style={{ height: 300, width: "100%" }} />;
}
