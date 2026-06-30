"use client";

import React, { useMemo } from "react";

interface PnLSeriesPoint {
  time: string;
  values: Record<string, number>;
}

interface PnLChartProps {
  data: PnLSeriesPoint[];
  height?: number;
  title?: string;
}

const SYMBOL_COLORS = [
  "#3B82F6", // blue
  "#F59E0B", // amber
  "#10B981", // emerald
  "#EC4899", // pink
  "#8B5CF6", // violet
  "#06B6D4", // cyan
  "#F97316", // orange
  "#84CC16", // lime
  "#EF4444", // red
  "#14B8A6", // teal
];

function formatTimeLabel(ts: string): string {
  const parts = ts.split(" ");
  if (parts.length === 2) {
    const date = parts[0];
    const time = parts[1].slice(0, 5); // HH:MM
    const day = date.slice(5); // MM-DD
    return `${day} ${time}`;
  }
  return ts.slice(11, 16); // fallback HH:MM
}

export default function PnLChart({ data, height = 180, title = "PnL Performance" }: PnLChartProps) {
  const svgData = useMemo(() => {
    if (data.length === 0) return null;

    const width = 800;
    const padding = { top: 10, right: 10, bottom: 30, left: 50 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const singlePoint = data.length === 1;

    // Collect all symbols
    const symbols = Array.from(new Set(data.flatMap(d => Object.keys(d.values))));

    // Collect all values across all symbols for scaling
    const allValues = data.flatMap(d => Object.values(d.values));
    const maxVal = Math.max(...allValues, 0);
    const minVal = Math.min(...allValues, 0);
    const range = maxVal - minVal || 2;

    const xScale = (i: number) => {
      if (singlePoint) return padding.left + chartWidth / 2;
      return padding.left + (i / (data.length - 1)) * chartWidth;
    };
    const yScale = (v: number) => padding.top + chartHeight - ((v - minVal) / range) * chartHeight;

    // Build a path for each symbol
    const series = symbols.map((sym, idx) => {
      let pathD = "";
      let dotPoints: { x: number; y: number }[] = [];
      if (singlePoint) {
        const x = xScale(0);
        const y = yScale(data[0].values[sym] || 0);
        pathD = `M ${x} ${y}`;
        dotPoints = [{ x, y }];
      } else {
        pathD = data
          .map((d, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yScale(d.values[sym] || 0)}`)
          .join(" ");
      }
      const finalPnL = data[data.length - 1].values[sym] || 0;
      const lineColor = SYMBOL_COLORS[idx % SYMBOL_COLORS.length];
      return { symbol: sym, pathD, finalPnL, lineColor, dotPoints };
    });

    // Zero line
    const zeroY = yScale(0);

    // Y-axis ticks
    const tickCount = 5;
    const ticks = Array.from({ length: tickCount }, (_, i) => {
      const val = minVal + (range * i) / (tickCount - 1);
      return { val, y: yScale(val) };
    });

    // X-axis time labels (start, middle, end) — deduplicate for single point
    const timeLabels = singlePoint
      ? [{ label: formatTimeLabel(data[0].time), x: xScale(0) }]
      : [
          { label: formatTimeLabel(data[0].time), x: xScale(0) },
          { label: formatTimeLabel(data[Math.floor(data.length / 2)].time), x: xScale(Math.floor(data.length / 2)) },
          { label: formatTimeLabel(data[data.length - 1].time), x: xScale(data.length - 1) },
        ];

    return { width, height, series, zeroY, ticks, timeLabels, maxVal, minVal };
  }, [data, height]);

  if (!svgData) {
    return (
      <div
        className="w-full bg-[#fafafa] bg-[#111]/40 rounded-xl border border-[var(--ax-border)] border-[var(--ax-border)]/50 flex items-center justify-center text-[#606060] dark:text-[#a0a0a0] text-xs"
        style={{ height }}
      >
        No PnL data
      </div>
    );
  }

  const { width, series, zeroY, ticks, timeLabels, maxVal, minVal } = svgData;

  return (
    <div className="w-full relative bg-[#fafafa] bg-[#111]/40 rounded-xl border border-[var(--ax-border)] border-[var(--ax-border)]/50 overflow-hidden transition-colors duration-200">
      {/* Header with legend */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--ax-border)] border-[var(--ax-border)]/50 bg-[#f4f4f5]/50 bg-[#111]/40">
        <span className="text-[10px] font-bold text-[#606060] text-[#a0a0a0] uppercase tracking-wider">{title}</span>
        <div className="flex items-center gap-3 flex-wrap">
          {series.map(s => (
            <div key={s.symbol} className="flex items-center gap-1">
              <span className="w-2 h-0.5 rounded" style={{ backgroundColor: s.lineColor }} />
              <span className="text-[9px] font-mono text-[#606060] text-[#a0a0a0]">{s.symbol}</span>
              <span className={`text-[9px] font-mono font-bold ${s.finalPnL > 0 ? "text-emerald-500 text-emerald-400" : s.finalPnL < 0 ? "text-rose-500 text-rose-400" : "text-orange-400 dark:text-orange-300"}`}>
                ₹{s.finalPnL.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </span>
            </div>
          ))}
        </div>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ height }}
        preserveAspectRatio="none"
      >
        {/* Grid lines */}
        {ticks.map((t, i) => (
          <line
            key={i}
            x1={50}
            y1={t.y}
            x2={width - 10}
            y2={t.y}
            stroke="currentColor"
            className="text-slate-250 dark:text-[#c0c0c0]"
            strokeWidth={0.5}
            opacity={0.6}
          />
        ))}

        {/* Zero baseline */}
        <line
          x1={50}
          y1={zeroY}
          x2={width - 10}
          y2={zeroY}
          stroke="currentColor"
          className="text-[#a0a0a0] dark:text-slate-650"
          strokeWidth={1}
          strokeDasharray="4 4"
          opacity={0.7}
        />

        {/* One line per symbol */}
        {series.map(s => (
          <g key={s.symbol}>
            <path
              d={s.pathD}
              fill="none"
              stroke={s.lineColor}
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {/* Dot markers for single-point data */}
            {s.dotPoints?.map((pt, di) => (
              <circle
                key={di}
                cx={pt.x}
                cy={pt.y}
                r={2.5}
                fill={s.lineColor}
              />
            ))}
          </g>
        ))}

        {/* Y-axis labels */}
        {ticks.map((t, i) => (
          <text
            key={`label-${i}`}
            x={45}
            y={t.y + 3}
            textAnchor="end"
            fill="currentColor"
            className="text-[#606060] dark:text-[#a0a0a0] font-mono text-[9px]"
          >
            {t.val >= 1000 ? `₹${(t.val / 1000).toFixed(1)}k` : `₹${Math.round(t.val)}`}
          </text>
        ))}

        {/* X-axis time labels */}
        {timeLabels.map((t, i) => (
          <text
            key={`time-${i}`}
            x={t.x}
            y={height - 6}
            textAnchor={timeLabels.length === 1 ? "middle" : i === 0 ? "start" : i === timeLabels.length - 1 ? "end" : "middle"}
            fill="currentColor"
            className="text-[#606060] dark:text-[#a0a0a0] font-mono text-[8px]"
          >
            {t.label}
          </text>
        ))}
      </svg>
    </div>
  );
}
