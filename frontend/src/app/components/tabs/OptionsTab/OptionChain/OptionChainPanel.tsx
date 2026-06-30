"use client";

import type { OptionChainData } from "../types";
import { OptionChainToolbar } from "./OptionChainToolbar";
import { OptionChainTable } from "./OptionChainTable";

interface OptionChainPanelProps {
  chainSymbol: string;
  setChainSymbol: (v: string) => void;
  selectedExpiry: string;
  setSelectedExpiry: (v: string) => void;
  expiryDates: string[];
  ltp: number;
  chainData: OptionChainData | null;
  loading: boolean;
  onRefresh: () => void;
  onAddLeg: (config: { position: "BUY" | "SELL"; option_type: "CE" | "PE"; strike_criteria: string; strike_value: number; qty: number }) => void;
}

export function OptionChainPanel({
  chainSymbol,
  setChainSymbol,
  selectedExpiry,
  setSelectedExpiry,
  expiryDates,
  ltp,
  chainData,
  loading,
  onRefresh,
  onAddLeg,
}: OptionChainPanelProps) {
  return (
    <div className="flex flex-col h-full">
      <OptionChainToolbar
        chainSymbol={chainSymbol}
        setChainSymbol={setChainSymbol}
        selectedExpiry={selectedExpiry}
        setSelectedExpiry={setSelectedExpiry}
        expiryDates={expiryDates}
        ltp={ltp}
        loading={loading}
        isMock={chainData?.is_mock || false}
        onRefresh={onRefresh}
      />
      <OptionChainTable chainData={chainData} onAddLeg={onAddLeg} />
    </div>
  );
}
