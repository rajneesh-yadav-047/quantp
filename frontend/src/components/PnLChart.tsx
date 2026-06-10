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

export default function PnLChart({ data, height = 160, title = "PnL Performance" }: PnLChartProps) {
  const svgData = useMemo(() => {
    if (data.length === 0) return null;

    const width = 800;
    const padding = { top: 10, right: 10, bottom: 20, left: 50 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Collect all symbols
    const symbols = Array.from(new Set(data.flatMap(d => Object.keys(d.values))));

    // Collect all values across all symbols for scaling
    const allValues = data.flatMap(d => Object.values(d.values));
    const maxVal = Math.max(...allValues, 0);
    const minVal = Math.min(...allValues, 0);
    const range = maxVal - minVal || 2;

    const xScale = (i: number) => padding.left + (i / (data.length - 1)) * chartWidth;
    const yScale = (v: number) => padding.top + chartHeight - ((v - minVal) / range) * chartHeight;

    // Build a path for each symbol
    const series = symbols.map(sym => {
      const pathD = data
        .map((d, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yScale(d.values[sym] || 0)}`)
        .join(" ");
      const finalPnL = data[data.length - 1].values[sym] || 0;
      return { symbol: sym, pathD, finalPnL, color: finalPnL >= 0 ? "#10B981" : "#EF4444" };
    });

    // Zero line
    const zeroY = yScale(0);

    // Y-axis ticks
    const tickCount = 5;
    const ticks = Array.from({ length: tickCount }, (_, i) => {
      const val = minVal + (range * i) / (tickCount - 1);
      return { val, y: yScale(val) };
    });

    return { width, height, series, zeroY, ticks, maxVal, minVal };
  }, [data, height]);

  if (!svgData) {
    return (
      <div
        className="w-full bg-slate-950/40 rounded border border-slate-800/50 flex items-center justify-center text-slate-500 text-xs"
        style={{ height }}
      >
        No PnL data
      </div>
    );
  }

  const { width, series, zeroY, ticks, maxVal, minVal } = svgData;

  return (
    <div className="w-full relative bg-slate-950/40 rounded border border-slate-800/50 overflow-hidden">
      {/* Header with legend */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-slate-800/50">
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{title}</span>
        <div className="flex items-center gap-3 flex-wrap">
          {series.map(s => (
            <div key={s.symbol} className="flex items-center gap-1">
              <span className="w-2 h-0.5 rounded" style={{ backgroundColor: s.color }} />
              <span className="text-[9px] font-mono text-slate-400">{s.symbol}</span>
              <span className={`text-[9px] font-mono font-bold ${s.finalPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
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
            stroke="rgba(148, 163, 184, 0.1)"
            strokeWidth={0.5}
          />
        ))}

        {/* Zero baseline */}
        <line
          x1={50}
          y1={zeroY}
          x2={width - 10}
          y2={zeroY}
          stroke="rgba(148, 163, 184, 0.3)"
          strokeWidth={1}
          strokeDasharray="4 4"
        />

        {/* One line per symbol */}
        {series.map(s => (
          <path
            key={s.symbol}
            d={s.pathD}
            fill="none"
            stroke={s.color}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}

        {/* Y-axis labels */}
        {ticks.map((t, i) => (
          <text
            key={`label-${i}`}
            x={45}
            y={t.y + 3}
            textAnchor="end"
            fill="#64748B"
            fontSize={9}
            fontFamily="monospace"
          >
            {t.val >= 1000 ? `₹${(t.val / 1000).toFixed(1)}k` : `₹${Math.round(t.val)}`}
          </text>
        ))}
      </svg>
    </div>
  );
}
