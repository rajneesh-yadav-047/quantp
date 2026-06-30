"use client";

import { useState, useCallback, useEffect } from "react";
import { api } from "@/lib/api-client";
import type { OptionChainData } from "../types";

export function useOptionChain(smartapiConnected: boolean, backendOnline: boolean) {
  const [chainSymbol, setChainSymbol] = useState("NSE:NIFTY 50");
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [chainData, setChainData] = useState<OptionChainData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadChain = useCallback(async () => {
    if (!backendOnline) {
      setError("Backend is offline.");
      return;
    }
    if (!smartapiConnected) {
      setError("SmartAPI not connected. Login first.");
      return;
    }
    setLoading(true);
    setError(null);
    const result = await api.post<{ data: OptionChainData }>("/options/chain", {
      symbol: chainSymbol,
      expiry_date: selectedExpiry || null,
    });
    if (result.ok && result.data) {
      setChainData(result.data.data);
      if (result.data.data?.expiry_dates?.length && !selectedExpiry) {
        setSelectedExpiry(result.data.data.expiry_dates[0]);
      }
    } else {
      setError(result.error || "Failed to load option chain.");
    }
    setLoading(false);
  }, [chainSymbol, selectedExpiry, backendOnline, smartapiConnected]);

  // Auto-load on mount when connected
  useEffect(() => {
    if (smartapiConnected && backendOnline) {
      loadChain();
    }
  }, [smartapiConnected, backendOnline, loadChain]);

  const atmStrike = chainData ? findAtmStrike(chainData.ltp, chainData.strikes) : 0;

  return {
    chainSymbol,
    setChainSymbol,
    selectedExpiry,
    setSelectedExpiry,
    chainData,
    loading,
    error,
    loadChain,
    atmStrike,
    expiryDates: chainData?.expiry_dates || [],
    ltp: chainData?.ltp || 0,
  };
}

export function findAtmStrike(ltp: number, strikes: number[]): number {
  if (!strikes.length) return ltp;
  return strikes.reduce((closest, strike) =>
    Math.abs(strike - ltp) < Math.abs(closest - ltp) ? strike : closest,
    strikes[0]
  );
}

export function resolveStrike(
  ltp: number,
  strikeCriteria: string,
  strikeValue: number,
  strikeType: string,
  optionType: string,
  strikes: number[]
): number {
  const atm = findAtmStrike(ltp, strikes);
  if (strikeCriteria === "ATM") return atm;
  if (strikeCriteria === "ITM") {
    const sorted = optionType === "CE"
      ? [...strikes].filter(s => s < ltp).sort((a, b) => b - a)
      : [...strikes].filter(s => s > ltp).sort((a, b) => a - b);
    return sorted[0] || atm;
  }
  if (strikeCriteria === "OTM") {
    const sorted = optionType === "CE"
      ? [...strikes].filter(s => s > ltp).sort((a, b) => a - b)
      : [...strikes].filter(s => s < ltp).sort((a, b) => b - a);
    return sorted[0] || atm;
  }
  // ATM + points / percent
  const offset = strikeType === "PERCENT" ? ltp * (strikeValue / 100) : strikeValue;
  const target = ltp + (strikeValue >= 0 ? offset : -offset);
  return strikes.reduce((closest, strike) =>
    Math.abs(strike - target) < Math.abs(closest - target) ? strike : closest,
    strikes[0]
  );
}
