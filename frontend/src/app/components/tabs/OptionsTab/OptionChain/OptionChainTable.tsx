"use client";

import { BarChart3 } from "lucide-react";
import type { OptionChainData } from "../types";
import { OptionChainRow } from "./OptionChainRow";
import { findAtmStrike } from "./useOptionChain";

interface OptionChainTableProps {
  chainData: OptionChainData | null;
  onAddLeg: (config: { position: "BUY" | "SELL"; option_type: "CE" | "PE"; strike_criteria: string; strike_value: number; qty: number }) => void;
}

export function OptionChainTable({ chainData, onAddLeg }: OptionChainTableProps) {
  if (!chainData || chainData.strikes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-[#a0a0a0]">
        <BarChart3 size={32} className="mb-3 opacity-50" />
        <p className="text-xs font-bold">No option chain data</p>
        <p className="text-[10px] mt-1">Enter a symbol and click Refresh to load</p>
      </div>
    );
  }

  const atmStrike = findAtmStrike(chainData.ltp, chainData.strikes);

  return (
    <div className="overflow-auto flex-1">
      <table className="w-full text-xs">
        <thead className="sticky top-0">
          <tr className="bg-[#111] border-b border-[var(--ax-border)]">
            <th className="px-2 py-2 text-[10px] font-bold text-[#606060] text-left">Call</th>
            <th className="px-2 py-2 text-[10px] font-bold text-[#606060] text-center">Delta</th>
            <th className="px-2 py-2 text-[10px] font-bold text-[#93b4ff] text-center">Strike</th>
            <th className="px-2 py-2 text-[10px] font-bold text-[#606060] text-center">Delta</th>
            <th className="px-2 py-2 text-[10px] font-bold text-[#606060] text-right">Put</th>
          </tr>
        </thead>
        <tbody>
          {chainData.strikes.map(strike => {
            const ce = chainData.chain[strike]?.CE;
            const pe = chainData.chain[strike]?.PE;
            const isAtm = Math.abs(strike - atmStrike) < 0.01;
            return (
              <OptionChainRow
                key={strike}
                strike={strike}
                ce={ce}
                pe={pe}
                isAtm={isAtm}
                onAddLeg={onAddLeg}
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
