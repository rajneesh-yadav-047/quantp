"use client";

import type { OptionChainStrike } from "../types";

interface OptionChainRowProps {
  strike: number;
  ce?: OptionChainStrike;
  pe?: OptionChainStrike;
  isAtm: boolean;
  onAddLeg: (config: { position: "BUY" | "SELL"; option_type: "CE" | "PE"; strike_criteria: string; strike_value: number; qty: number }) => void;
}

export function OptionChainRow({ strike, ce, pe, isAtm, onAddLeg }: OptionChainRowProps) {
  return (
    <tr
      className={`border-b border-[var(--ax-border)]/40 hover:bg-[#161616]/40 transition-colors ${isAtm ? "bg-[var(--ax-atm)]" : ""}`}
    >
      {/* CE Side */}
      <td className="px-2 py-1.5">
        <div className="flex items-center gap-1">
          <button
            className="px-1.5 py-0.5 bg-[#0d1a10] text-emerald-400 text-[10px] font-bold rounded border border-emerald-800/40 hover:bg-[#132a1a]"
            onClick={() => onAddLeg({ position: "BUY", option_type: "CE", strike_criteria: "ATM", strike_value: 0, qty: 75 })}
            title="Buy CE"
          >
            B
          </button>
          <button
            className="px-1.5 py-0.5 bg-[#1a0d0d] text-rose-400 text-[10px] font-bold rounded border border-rose-800/40 hover:bg-[#2a1515]"
            onClick={() => onAddLeg({ position: "SELL", option_type: "CE", strike_criteria: "ATM", strike_value: 0, qty: 75 })}
            title="Sell CE"
          >
            S
          </button>
          <span className={`font-mono font-bold ${ce?.ltp ? "text-emerald-400" : "text-[#606060]"}`}>
            {ce?.ltp?.toFixed(2) || "--"}
          </span>
        </div>
        {(ce?.volume ?? 0) > 0 && (
          <div className="text-[9px] text-[#a0a0a0] font-mono mt-0.5">
            OI: {ce?.open_interest?.toLocaleString() || "--"} | Vol: {ce?.volume?.toLocaleString() || "--"}
          </div>
        )}
      </td>
      <td className="px-2 py-1.5 text-center font-mono text-[#a0a0a0]">
        {ce?.delta?.toFixed(2) || "--"}
      </td>

      {/* Strike */}
      <td className={`px-2 py-1.5 text-center font-mono font-bold ${isAtm ? "text-[#93b4ff]" : "text-[#c0c0c0]"}`}>
        {strike.toLocaleString()}
        {isAtm && <span className="text-[9px] text-[#93b4ff] ml-1">ATM</span>}
      </td>

      {/* PE Side */}
      <td className="px-2 py-1.5 text-center font-mono text-[#a0a0a0]">
        {pe?.delta?.toFixed(2) || "--"}
      </td>
      <td className="px-2 py-1.5 text-right">
        <div className="flex items-center justify-end gap-1">
          <span className={`font-mono font-bold ${pe?.ltp ? "text-rose-400" : "text-[#606060]"}`}>
            {pe?.ltp?.toFixed(2) || "--"}
          </span>
          <button
            className="px-1.5 py-0.5 bg-[#0d1a10] text-emerald-400 text-[10px] font-bold rounded border border-emerald-800/40 hover:bg-[#132a1a]"
            onClick={() => onAddLeg({ position: "BUY", option_type: "PE", strike_criteria: "ATM", strike_value: 0, qty: 75 })}
            title="Buy PE"
          >
            B
          </button>
          <button
            className="px-1.5 py-0.5 bg-[#1a0d0d] text-rose-400 text-[10px] font-bold rounded border border-rose-800/40 hover:bg-[#2a1515]"
            onClick={() => onAddLeg({ position: "SELL", option_type: "PE", strike_criteria: "ATM", strike_value: 0, qty: 75 })}
            title="Sell PE"
          >
            S
          </button>
        </div>
        {(pe?.volume ?? 0) > 0 && (
          <div className="text-[9px] text-[#a0a0a0] font-mono mt-0.5">
            OI: {pe?.open_interest?.toLocaleString() || "--"} | Vol: {pe?.volume?.toLocaleString() || "--"}
          </div>
        )}
      </td>
    </tr>
  );
}
