"use client";

import type { TradeDays } from "../types";

interface StrategyMetaProps {
  strategyName: string;
  setStrategyName: (v: string) => void;
  strategyType: string;
  setStrategyType: (v: string) => void;
  tradeType: string;
  setTradeType: (v: string) => void;
  startTime: string;
  setStartTime: (v: string) => void;
  endTime: string;
  setEndTime: (v: string) => void;
  expiryType: string;
  setExpiryType: (v: string) => void;
  initialCapital: number;
  setInitialCapital: (v: number) => void;
  tradeDays: TradeDays;
  setTradeDays: (v: TradeDays) => void;
  // Download strikes
  optionsDlStrikes?: string;
  setOptionsDlStrikes?: (v: string) => void;
}

export function StrategyMeta({
  strategyName, setStrategyName,
  strategyType, setStrategyType,
  tradeType, setTradeType,
  startTime, setStartTime,
  endTime, setEndTime,
  expiryType, setExpiryType,
  initialCapital, setInitialCapital,
  tradeDays, setTradeDays,
  optionsDlStrikes, setOptionsDlStrikes,
}: StrategyMetaProps) {
  const dayKeys = ["mon", "tue", "wed", "thu", "fri"] as const;

  return (
    <div className="p-4 border border-[var(--ax-border)] rounded-xl bg-[var(--ax-surface)] space-y-4">
      <div>
        <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Strategy Name</label>
        <input
          type="text"
          value={strategyName}
          onChange={e => setStrategyName(e.target.value)}
          className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0] font-semibold"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Strategy Type</label>
          <select
            value={strategyType}
            onChange={e => setStrategyType(e.target.value)}
            className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0] font-semibold"
          >
            <option value="indicator">Indicator Based</option>
            <option value="time-based">Time Based</option>
          </select>
        </div>
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Order Type</label>
          <select
            value={tradeType}
            onChange={e => setTradeType(e.target.value)}
            className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0] font-semibold"
          >
            <option value="MIS">MIS</option>
            <option value="CNC">CNC</option>
            <option value="BTST">BTST</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Start Time</label>
          <input
            type="time"
            value={startTime}
            onChange={e => setStartTime(e.target.value)}
            className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0] font-semibold"
          />
        </div>
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">End Time</label>
          <input
            type="time"
            value={endTime}
            onChange={e => setEndTime(e.target.value)}
            className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0] font-semibold"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Expiry</label>
          <select
            value={expiryType}
            onChange={e => setExpiryType(e.target.value)}
            className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0] font-semibold"
          >
            <option value="WEEKLY">Weekly</option>
            <option value="MONTHLY">Monthly</option>
            <option value="NEXT_WEEKLY">Next Weekly</option>
          </select>
        </div>
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Capital</label>
          <input
            type="number"
            value={initialCapital}
            onChange={e => setInitialCapital(Number(e.target.value))}
            className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0] font-semibold font-mono"
          />
        </div>
      </div>

      {setOptionsDlStrikes && (
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Download Strikes (comma-separated)</label>
          <input
            type="text"
            value={optionsDlStrikes || ""}
            onChange={e => setOptionsDlStrikes(e.target.value)}
            className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0] font-semibold font-mono"
            placeholder="e.g. 22500, 22600, 22700"
          />
        </div>
      )}

      <div>
        <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Trade Days</label>
        <div className="flex gap-1">
          {dayKeys.map(day => (
            <button
              key={day}
              onClick={() => setTradeDays({ ...tradeDays, [day]: !tradeDays[day] })}
              className={`flex-1 py-1 text-[10px] font-bold rounded border transition-all ${
                tradeDays[day]
                  ? "bg-[#1c2030] border-[#4a7fcc] text-[#93b4ff]"
                  : "bg-[#111] border-[var(--ax-border)] text-[#a0a0a0]"
              }`}
            >
              {day.toUpperCase().slice(0, 3)}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
