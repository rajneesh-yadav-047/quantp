"use client";

import React, { useMemo } from "react";

interface PositionPoint {
  time: string;
  value: number;
}

interface PositionChartProps {
  data: PositionPoint[];
  height?: number;
}

export default function PositionChart({ data, height = 120 }: PositionChartProps) {
  const svgData = useMemo(() => {
    if (data.length === 0) return null;

    const width = 800;
    const padding = { top: 10, right: 10, bottom: 20, left: 40 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const values = data.map((d) => d.value);
    const maxVal = Math.max(...values, 1);
    const minVal = Math.min(...values, -1);
    const range = maxVal - minVal || 2;

    const xScale = (i: number) => padding.left + (i / (data.length - 1)) * chartWidth;
    const yScale = (v: number) => padding.top + chartHeight - ((v - minVal) / range) * chartHeight;

    // Build path
    const pathD = data
      .map((d, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yScale(d.value)}`)
      .join(" ");

    // Zero line
    const zeroY = yScale(0);

    // Area fill (above zero = green, below = red)
    const areaPathD =
      pathD +
      ` L ${xScale(data.length - 1)} ${zeroY} L ${xScale(0)} ${zeroY} Z`;

    // Y-axis ticks
    const tickCount = 5;
    const ticks = Array.from({ length: tickCount }, (_, i) => {
      const val = minVal + (range * i) / (tickCount - 1);
      return { val, y: yScale(val) };
    });

    return {
      width,
      height,
      pathD,
      areaPathD,
      zeroY,
      ticks,
      maxVal,
      minVal,
      xScale,
      yScale,
    };
  }, [data, height]);

  if (!svgData) {
    return (
      <div
        className="w-full bg-slate-950/40 rounded border border-slate-800/50 flex items-center justify-center text-slate-500 text-xs"
        style={{ height }}
      >
        No position data
      </div>
    );
  }

  const { width, pathD, areaPathD, zeroY, ticks, maxVal, minVal } = svgData;

  return (
    <div className="w-full relative bg-slate-950/40 rounded border border-slate-800/50 overflow-hidden">
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
            x1={40}
            y1={t.y}
            x2={width - 10}
            y2={t.y}
            stroke="rgba(148, 163, 184, 0.1)"
            strokeWidth={0.5}
          />
        ))}

        {/* Zero baseline */}
        <line
          x1={40}
          y1={zeroY}
          x2={width - 10}
          y2={zeroY}
          stroke="rgba(148, 163, 184, 0.3)"
          strokeWidth={1}
          strokeDasharray="4 4"
        />

        {/* Area fill */}
        <path d={areaPathD} fill="rgba(59, 130, 246, 0.08)" />

        {/* Line */}
        <path
          d={pathD}
          fill="none"
          stroke="#3B82F6"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Y-axis labels */}
        {ticks.map((t, i) => (
          <text
            key={`label-${i}`}
            x={35}
            y={t.y + 3}
            textAnchor="end"
            fill="#64748B"
            fontSize={9}
            fontFamily="monospace"
          >
            {Math.round(t.val)}
          </text>
        ))}
      </svg>

      {/* Current value badge */}
      {data.length > 0 && (
        <div className="absolute top-2 right-2 px-2 py-0.5 bg-slate-900/80 border border-slate-800 rounded text-[10px] font-mono font-bold">
          <span
            className={
              data[data.length - 1].value >= 0
                ? "text-emerald-400"
                : "text-rose-400"
            }
          >
            {data[data.length - 1].value >= 0 ? "LONG " : "SHORT "}
            {Math.abs(data[data.length - 1].value)} Qty
          </span>
        </div>
      )}
    </div>
  );
}
