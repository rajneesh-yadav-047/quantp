"use client";

import React, { useMemo, useState } from "react";

interface EquityPoint {
  time: string;
  equity: number;
}

interface DailyPnL {
  date: string;
  pnl: number;
  equityStart: number;
  equityEnd: number;
}

interface DailyPnLHeatmapProps {
  equityCurve?: EquityPoint[];
  startDate?: string;
  endDate?: string;
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function parseDateKey(ts: string): string {
  const d = new Date(ts.replace(" ", "T"));
  if (isNaN(d.getTime())) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function getDayOfWeek(dateKey: string): number {
  const d = new Date(dateKey + "T00:00:00");
  return d.getDay(); // 0=Sun, 1=Mon ... 6=Sat
}

function addDays(dateKey: string, days: number): string {
  const d = new Date(dateKey + "T00:00:00");
  d.setDate(d.getDate() + days);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function monthKey(dateKey: string): string {
  return dateKey.slice(0, 7); // "YYYY-MM"
}

function monthLabel(dateKey: string): string {
  const d = new Date(dateKey + "-01T00:00:00");
  return d.toLocaleString("en-US", { month: "long", year: "numeric" });
}

function formatLabel(dateKey: string): string {
  const d = new Date(dateKey + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" });
}

interface MonthData {
  label: string;
  yearMonth: string;
  weeks: (string | null)[][]; // each week is 7 days (Sun-Sat), null = empty cell
}

export function DailyPnLHeatmap({ equityCurve, startDate, endDate }: DailyPnLHeatmapProps) {
  const [hovered, setHovered] = useState<DailyPnL | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const { months, dailyPnLMap, maxAbsPnL } = useMemo(() => {
    if (!equityCurve || equityCurve.length === 0) {
      return { months: [] as MonthData[], dailyPnLMap: new Map<string, DailyPnL>(), maxAbsPnL: 0 };
    }

    // 1. Sort equity curve chronologically
    const sortedCurve = [...equityCurve].sort((a, b) => {
      const ta = new Date(a.time.replace(" ", "T")).getTime();
      const tb = new Date(b.time.replace(" ", "T")).getTime();
      return ta - tb;
    });

    // 2. Group by date and compute daily PnL
    const dailyMap = new Map<string, { first: number; last: number }>();
    for (const pt of sortedCurve) {
      const equity = typeof pt.equity === "number" ? pt.equity : parseFloat(String(pt.equity));
      if (isNaN(equity)) continue;
      const dk = parseDateKey(pt.time);
      if (!dk) continue;
      const existing = dailyMap.get(dk);
      if (existing) {
        existing.last = equity;
      } else {
        dailyMap.set(dk, { first: equity, last: equity });
      }
    }

    const dailyPnL = new Map<string, DailyPnL>();
    let maxAbs = 0;
    for (const [date, vals] of dailyMap.entries()) {
      const pnl = vals.last - vals.first;
      dailyPnL.set(date, { date, pnl, equityStart: vals.first, equityEnd: vals.last });
      maxAbs = Math.max(maxAbs, Math.abs(pnl));
    }

    // 3. Determine full date range
    const sortedDates = Array.from(dailyMap.keys()).sort();
    const firstDate = startDate || sortedDates[0];
    const lastDate = endDate || sortedDates[sortedDates.length - 1];

    // 4. Build months
    const monthMap = new Map<string, MonthData>();

    // Start from first of the month containing firstDate
    let cursor = firstDate.slice(0, 7) + "-01";
    const endMonth = lastDate.slice(0, 7) + "-01";

    while (cursor <= endMonth || cursor.slice(0, 7) === endMonth.slice(0, 7)) {
      const ym = monthKey(cursor);
      const label = monthLabel(cursor);

      const weeks: (string | null)[][] = [];
      let currentWeek: (string | null)[] = new Array(7).fill(null);

      const firstDayOfMonth = cursor;
      const daysInMonth = new Date(
        parseInt(cursor.slice(0, 4)),
        parseInt(cursor.slice(5, 7)),
        0
      ).getDate();

      for (let day = 1; day <= daysInMonth; day++) {
        const dateKey = `${ym}-${String(day).padStart(2, "0")}`;
        const dow = getDayOfWeek(dateKey);
        currentWeek[dow] = dateKey;
        if (dow === 6) {
          weeks.push(currentWeek);
          currentWeek = new Array(7).fill(null);
        }
      }
      if (currentWeek.some((d) => d !== null)) {
        weeks.push(currentWeek);
      }

      monthMap.set(ym, { label, yearMonth: ym, weeks });

      // Move to next month
      const nextMonth = new Date(parseInt(cursor.slice(0, 4)), parseInt(cursor.slice(5, 7)), 1);
      const y = nextMonth.getFullYear();
      const m = String(nextMonth.getMonth() + 1).padStart(2, "0");
      cursor = `${y}-${m}-01`;
      if (cursor > lastDate && cursor.slice(0, 7) !== endMonth.slice(0, 7)) break;
    }

    return { months: Array.from(monthMap.values()), dailyPnLMap: dailyPnL, maxAbsPnL: maxAbs };
  }, [equityCurve, startDate, endDate]);

  if (!equityCurve || equityCurve.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-xs text-slate-500">
        No equity data available for calendar view.
      </div>
    );
  }

  const getColor = (pnl: number) => {
    if (pnl > 0) {
      const intensity = maxAbsPnL > 0 ? Math.max(0.35, Math.min(1.0, Math.abs(pnl) / maxAbsPnL)) : 0.5;
      return `rgba(34, 197, 94, ${intensity})`;
    }
    if (pnl < 0) {
      const intensity = maxAbsPnL > 0 ? Math.max(0.35, Math.min(1.0, Math.abs(pnl) / maxAbsPnL)) : 0.5;
      return `rgba(244, 63, 94, ${intensity})`;
    }
    return "rgba(51, 65, 85, 0.5)";
  };

  const handleMouseEnter = (e: React.MouseEvent, dateKey: string) => {
    const data = dailyPnLMap.get(dateKey);
    if (data) {
      setHovered(data);
      setTooltipPos({ x: e.clientX, y: e.clientY });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    setTooltipPos({ x: e.clientX, y: e.clientY });
  };

  const handleMouseLeave = () => {
    setHovered(null);
  };

  return (
    <div className="relative w-full">
      {/* Months grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {months.map((month) => (
          <div key={month.yearMonth} className="border border-slate-800 rounded-lg p-3 bg-slate-950/40">
            {/* Month header */}
            <div className="text-xs font-bold text-slate-300 mb-2 text-center">
              {month.label}
            </div>

            {/* Day-of-week headers */}
            <div className="grid grid-cols-7 gap-1 mb-1">
              {WEEKDAYS.map((d, i) => (
                <div key={`wd-${i}`} className="text-[9px] text-slate-500 text-center font-medium">
                  {d}
                </div>
              ))}
            </div>

            {/* Calendar grid */}
            <div className="grid grid-cols-7 gap-1">
              {month.weeks.flat().map((dateKey, idx) => {
                if (!dateKey) {
                  return <div key={idx} className="aspect-square" />;
                }
                const pnlData = dailyPnLMap.get(dateKey);
                const pnl = pnlData ? pnlData.pnl : 0;
                const hasData = pnlData !== undefined;
                const dayNum = parseInt(dateKey.slice(8, 10));

                return (
                  <div
                    key={idx}
                    onMouseEnter={(e) => handleMouseEnter(e, dateKey)}
                    onMouseMove={handleMouseMove}
                    onMouseLeave={handleMouseLeave}
                    className="aspect-square rounded-sm flex items-center justify-center cursor-pointer transition-transform hover:scale-110 hover:ring-1 hover:ring-slate-400"
                    style={{
                      backgroundColor: hasData ? getColor(pnl) : "rgba(51, 65, 85, 0.25)",
                      fontSize: "10px",
                    }}
                  >
                    <span className={`font-medium ${hasData ? "text-slate-900" : "text-slate-500"}`}>
                      {dayNum}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-4 mt-5 text-[10px] text-slate-400">
        <span>Loss</span>
        <div className="flex gap-1">
          <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: "rgba(244, 63, 94, 0.85)" }} />
          <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: "rgba(244, 63, 94, 0.5)" }} />
          <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: "rgba(244, 63, 94, 0.35)" }} />
        </div>
        <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: "rgba(51, 65, 85, 0.35)" }} />
        <div className="flex gap-1">
          <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: "rgba(34, 197, 94, 0.35)" }} />
          <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: "rgba(34, 197, 94, 0.5)" }} />
          <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: "rgba(34, 197, 94, 0.85)" }} />
        </div>
        <span>Profit</span>
      </div>

      {/* Tooltip */}
      {hovered && (
        <div
          className="fixed z-50 pointer-events-none bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 shadow-2xl text-xs"
          style={{
            left: tooltipPos.x + 16,
            top: tooltipPos.y - 12,
          }}
        >
          <div className="font-bold text-slate-200 mb-1">{formatLabel(hovered.date)}</div>
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Daily PnL:</span>
            <span className={`font-mono font-bold ${hovered.pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {hovered.pnl >= 0 ? "+" : ""}₹{hovered.pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </span>
          </div>
          <div className="text-[10px] text-slate-500 mt-1">
            Start: ₹{hovered.equityStart.toLocaleString(undefined, { maximumFractionDigits: 0 })} → End: ₹{hovered.equityEnd.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            Change: {((hovered.pnl / hovered.equityStart) * 100).toFixed(2)}%
          </div>
        </div>
      )}
    </div>
  );
}

export default DailyPnLHeatmap;
