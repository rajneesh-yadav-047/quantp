"use client";

import { RefreshCw, Target } from "lucide-react";

interface OptionChainToolbarProps {
  chainSymbol: string;
  setChainSymbol: (v: string) => void;
  selectedExpiry: string;
  setSelectedExpiry: (v: string) => void;
  expiryDates: string[];
  ltp: number;
  loading: boolean;
  isMock: boolean;
  onRefresh: () => void;
}

export function OptionChainToolbar({
  chainSymbol,
  setChainSymbol,
  selectedExpiry,
  setSelectedExpiry,
  expiryDates,
  ltp,
  loading,
  isMock,
  onRefresh,
}: OptionChainToolbarProps) {
  return (
    <div className="p-4 border-b border-[var(--ax-border)] space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="font-bold text-[#c0c0c0] text-sm flex items-center gap-2">
          <Target className="w-4 h-4 text-[#93b4ff]" />
          Option Chain
        </h4>
        <div className="flex items-center gap-2">
          {isMock && (
            <span className="text-[10px] bg-[#1a150d] text-amber-400 px-2 py-0.5 rounded border border-amber-800/40">
              Mock Data
            </span>
          )}
          <button
            onClick={onRefresh}
            disabled={loading}
            className="px-3 py-1.5 bg-[#4a7fcc] hover:bg-[#5a8fd0] disabled:opacity-50 text-[#f0f0f0] rounded text-xs font-bold flex items-center gap-1.5 transition-all"
          >
            {loading ? <RefreshCw size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Underlying</label>
          <input
            type="text"
            value={chainSymbol}
            onChange={e => setChainSymbol(e.target.value.toUpperCase())}
            className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0] font-mono font-semibold"
            placeholder="NSE:NIFTY 50"
          />
        </div>
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Expiry</label>
          <select
            value={selectedExpiry}
            onChange={e => setSelectedExpiry(e.target.value)}
            className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0] font-semibold"
          >
            {expiryDates.map(d => (
              <option key={d} value={d}>{d}</option>
            ))}
            {expiryDates.length === 0 && <option>--</option>}
          </select>
        </div>
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">LTP</label>
          <div className="text-xs font-mono font-bold text-[#c0c0c0] bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5">
            {ltp ? `₹${ltp.toFixed(2)}` : "--"}
          </div>
        </div>
      </div>
    </div>
  );
}
