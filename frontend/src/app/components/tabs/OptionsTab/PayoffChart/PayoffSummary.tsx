"use client";

import { BarChart3 } from "lucide-react";
import type { PayoffResult } from "../types";

interface PayoffSummaryProps {
  payoff: PayoffResult;
  netPremium: number;
  marginEstimate: number;
}

export function PayoffSummary({ payoff, netPremium, marginEstimate }: PayoffSummaryProps) {
  return (
    <div className="p-4 border border-[var(--ax-border)] rounded-xl bg-[var(--ax-surface)] space-y-4">
      <h4 className="font-bold text-[#c0c0c0] text-sm flex items-center gap-2">
        <BarChart3 className="w-4 h-4 text-[#93b4ff]" />
        Payoff Analysis
      </h4>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="bg-[#111] rounded p-2 border border-[var(--ax-border)]">
          <div className="text-[10px] font-bold text-[#606060] uppercase">Net Premium</div>
          <div className={`font-mono font-bold ${netPremium >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            ₹{netPremium.toFixed(2)}
          </div>
        </div>
        <div className="bg-[#111] rounded p-2 border border-[var(--ax-border)]">
          <div className="text-[10px] font-bold text-[#606060] uppercase">Est. Margin</div>
          <div className="font-mono font-bold text-amber-400">
            ₹{marginEstimate.toFixed(0)}
          </div>
        </div>
        <div className="bg-[#111] rounded p-2 border border-[var(--ax-border)]">
          <div className="text-[10px] font-bold text-[#606060] uppercase">Max Profit</div>
          <div className="font-mono font-bold text-emerald-400">
            ₹{payoff.maxProfit.toFixed(2)}
          </div>
        </div>
        <div className="bg-[#111] rounded p-2 border border-[var(--ax-border)]">
          <div className="text-[10px] font-bold text-[#606060] uppercase">Max Loss</div>
          <div className="font-mono font-bold text-rose-400">
            ₹{payoff.maxLoss.toFixed(2)}
          </div>
        </div>
      </div>

      {payoff.breakevens.length > 0 && (
        <div className="bg-[#111] rounded p-2 border border-[var(--ax-border)]">
          <div className="text-[10px] font-bold text-[#606060] uppercase mb-1">Breakevens</div>
          <div className="flex flex-wrap gap-1">
            {payoff.breakevens.map((b, i) => (
              <span key={i} className="text-xs font-mono font-bold text-amber-400">
                ₹{b.toFixed(2)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
