"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import { api } from "@/lib/api-client";
import {
  TrendingUp, TrendingDown, Plus, Trash2, Copy, Play, Save, Download,
  ChevronRight, AlertTriangle, CheckCircle2, XCircle, RefreshCw,
  Target, Layers, ArrowUpRight, ArrowDownRight, BarChart3, Zap,
  Calendar, Clock, Settings, Package, BookOpen, Info,
} from "lucide-react";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

// ── Types ──

interface OptionChainData {
  underlying: string;
  symbol: string;
  ltp: number;
  expiry_dates: string[];
  strikes: number[];
  chain: Record<number, {
    CE?: { ltp: number; open: number; high: number; low: number; close: number; volume: number; open_interest: number; delta: number; gamma: number; theta: number; vega: number; iv: number; symbol: string; token: string };
    PE?: { ltp: number; open: number; high: number; low: number; close: number; volume: number; open_interest: number; delta: number; gamma: number; theta: number; vega: number; iv: number; symbol: string; token: string };
  }>;
  lot_size?: number;
  is_mock?: boolean;
}

interface StrategyLeg {
  id: string;
  leg_index: number;
  position: "BUY" | "SELL";
  option_type: "CE" | "PE";
  qty: number;
  lot_multiplier: number;
  strike_criteria: string;
  strike_value: number;
  strike_type: string;
  sl_enabled: boolean;
  sl_type: string;
  sl_value: number;
  tp_enabled: boolean;
  tp_type: string;
  tp_value: number;
}

interface StrategyTemplate {
  id: string;
  name: string;
  description: string;
  legs_count: number;
  example: string;
}

// ── Helpers ──

const generateId = () => Math.random().toString(36).substring(2, 10);

function findAtmStrike(ltp: number, strikes: number[]): number {
  if (!strikes.length) return ltp;
  return strikes.reduce((closest, strike) =>
    Math.abs(strike - ltp) < Math.abs(closest - ltp) ? strike : closest,
    strikes[0]
  );
}

function resolveStrike(
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
    const sorted = optionType === "CE" ? [...strikes].filter(s => s < ltp).sort((a, b) => b - a) : [...strikes].filter(s => s > ltp).sort((a, b) => a - b);
    return sorted[0] || atm;
  }
  if (strikeCriteria === "OTM") {
    const sorted = optionType === "CE" ? [...strikes].filter(s => s > ltp).sort((a, b) => a - b) : [...strikes].filter(s => s < ltp).sort((a, b) => b - a);
    return sorted[0] || atm;
  }
  // ATM + points / percent
  let offset = strikeType === "PERCENT" ? ltp * (strikeValue / 100) : strikeValue;
  const target = ltp + (strikeValue >= 0 ? offset : -offset);
  return strikes.reduce((closest, strike) =>
    Math.abs(strike - target) < Math.abs(closest - target) ? strike : closest,
    strikes[0]
  );
}

function calculatePayoff(
  legs: StrategyLeg[],
  ltp: number,
  strikes: number[],
  chainData: OptionChainData
): { spotPrices: number[]; payoffs: number[]; maxProfit: number; maxLoss: number; breakevens: number[] } {
  if (!ltp || !strikes.length || !legs.length) {
    return { spotPrices: [], payoffs: [], maxProfit: 0, maxLoss: 0, breakevens: [] };
  }

  const range = ltp * 0.15; // ±15% range
  const minSpot = Math.max(ltp - range, strikes[0] * 0.8);
  const maxSpot = Math.min(ltp + range, strikes[strikes.length - 1] * 1.2);
  const steps = 200;
  const stepSize = (maxSpot - minSpot) / steps;
  const spotPrices: number[] = [];
  const payoffs: number[] = [];

  for (let i = 0; i <= steps; i++) {
    const spot = minSpot + i * stepSize;
    spotPrices.push(spot);
    let totalPnL = 0;

    for (const leg of legs) {
      const strike = resolveStrike(ltp, leg.strike_criteria, leg.strike_value, leg.strike_type, leg.option_type, strikes);
      const ceData = chainData.chain[strike]?.CE;
      const peData = chainData.chain[strike]?.PE;
      const premium = leg.option_type === "CE" ? (ceData?.ltp || 0) : (peData?.ltp || 0);
      const qty = leg.qty * leg.lot_multiplier;

      let legPnL = 0;
      if (leg.option_type === "CE") {
        if (leg.position === "BUY") {
          legPnL = (Math.max(0, spot - strike) - premium) * qty;
        } else {
          legPnL = (premium - Math.max(0, spot - strike)) * qty;
        }
      } else {
        if (leg.position === "BUY") {
          legPnL = (Math.max(0, strike - spot) - premium) * qty;
        } else {
          legPnL = (premium - Math.max(0, strike - spot)) * qty;
        }
      }
      totalPnL += legPnL;
    }
    payoffs.push(totalPnL);
  }

  const maxProfit = Math.max(...payoffs, 0);
  const maxLoss = Math.min(...payoffs, 0);

  // Find breakevens (where payoff crosses zero)
  const breakevens: number[] = [];
  for (let i = 1; i < payoffs.length; i++) {
    if ((payoffs[i - 1] < 0 && payoffs[i] >= 0) || (payoffs[i - 1] > 0 && payoffs[i] <= 0)) {
      // Linear interpolation
      const t = Math.abs(payoffs[i - 1]) / (Math.abs(payoffs[i - 1]) + Math.abs(payoffs[i]));
      breakevens.push(spotPrices[i - 1] + t * (spotPrices[i] - spotPrices[i - 1]));
    }
  }

  return { spotPrices, payoffs, maxProfit, maxLoss, breakevens };
}

function calculateMarginEstimate(legs: StrategyLeg[], ltp: number, strikes: number[], chainData: OptionChainData): number {
  let totalMargin = 0;
  for (const leg of legs) {
    const strike = resolveStrike(ltp, leg.strike_criteria, leg.strike_value, leg.strike_type, leg.option_type, strikes);
    const ceData = chainData.chain[strike]?.CE;
    const peData = chainData.chain[strike]?.PE;
    const premium = leg.option_type === "CE" ? (ceData?.ltp || 0) : (peData?.ltp || 0);
    const qty = leg.qty * leg.lot_multiplier;

    // Short options require SPAN + Exposure margin
    // Rough estimate: ~15% of underlying notional for short options
    if (leg.position === "SELL") {
      const notional = strike * qty;
      totalMargin += notional * 0.15;
    } else {
      // Long options only need premium
      totalMargin += premium * qty;
    }
  }
  return totalMargin;
}

// ── Component ──

export function OptionsTab({ triggerNotif, smartapiConnected, backendOnline }: any) {
  // ── Option Chain State ──
  const [chainSymbol, setChainSymbol] = useState("NSE:NIFTY 50");
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [chainData, setChainData] = useState<OptionChainData | null>(null);
  const [chainLoading, setChainLoading] = useState(false);

  // ── Strategy Builder State ──
  const [strategyName, setStrategyName] = useState("My Option Strategy");
  const [strategyType, setStrategyType] = useState("indicator"); // indicator, time-based
  const [tradeType, setTradeType] = useState("MIS"); // MIS, CNC, BTST
  const [startTime, setStartTime] = useState("09:16");
  const [endTime, setEndTime] = useState("15:15");
  const [expiryType, setExpiryType] = useState("WEEKLY");
  const [initialCapital, setInitialCapital] = useState(1000000);
  const [tradeDays, setTradeDays] = useState({ mon: true, tue: true, wed: true, thu: true, fri: true });

  // ── Legs ──
  const [legs, setLegs] = useState<StrategyLeg[]>([
    {
      id: generateId(), leg_index: 0, position: "SELL", option_type: "CE", qty: 75, lot_multiplier: 1,
      strike_criteria: "ATM", strike_value: 0, strike_type: "POINTS",
      sl_enabled: true, sl_type: "PERCENT", sl_value: 1.0, tp_enabled: false, tp_type: "PERCENT", tp_value: 0,
    },
    {
      id: generateId(), leg_index: 1, position: "SELL", option_type: "PE", qty: 75, lot_multiplier: 1,
      strike_criteria: "ATM", strike_value: 0, strike_type: "POINTS",
      sl_enabled: true, sl_type: "PERCENT", sl_value: 1.0, tp_enabled: false, tp_type: "PERCENT", tp_value: 0,
    },
  ]);

  // ── Templates ──
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);

  // ── Saved Strategies ──
  const [savedStrategies, setSavedStrategies] = useState<any[]>([]);
  const [savedLoading, setSavedLoading] = useState(false);

  // ── Load option chain ──
  const loadChain = useCallback(async () => {
    if (!backendOnline) {
      triggerNotif("error", "Backend is offline.");
      return;
    }
    if (!smartapiConnected) {
      triggerNotif("error", "SmartAPI not connected. Login first.");
      return;
    }
    setChainLoading(true);
    const result = await api.post("/options/chain", { symbol: chainSymbol, expiry_date: selectedExpiry || null });
    if (result.ok && result.data) {
      setChainData(result.data.data);
      if (result.data.data?.expiry_dates?.length && !selectedExpiry) {
        setSelectedExpiry(result.data.data.expiry_dates[0]);
      }
      triggerNotif("success", `Option chain loaded: ${result.data.data?.is_mock ? "Mock" : "Live"}`);
    } else {
      triggerNotif("error", result.error || "Failed to load option chain.");
    }
    setChainLoading(false);
  }, [chainSymbol, selectedExpiry, backendOnline, smartapiConnected, triggerNotif]);

  // ── Load templates ──
  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    const result = await api.get("/options/templates");
    if (result.ok && result.data) {
      setTemplates(result.data.templates || []);
    }
    setTemplatesLoading(false);
  }, []);

  // ── Load saved strategies ──
  const loadSavedStrategies = useCallback(async () => {
    setSavedLoading(true);
    const result = await api.get("/options/strategies");
    if (result.ok && result.data) {
      setSavedStrategies(result.data.strategies || []);
    }
    setSavedLoading(false);
  }, []);

  // ── Initial load ──
  useEffect(() => {
    loadTemplates();
    loadSavedStrategies();
    // Auto-load chain if connected
    if (smartapiConnected && backendOnline) {
      loadChain();
    }
  }, [smartapiConnected, backendOnline]);

  // ── Add / Remove Leg ──
  const addLeg = useCallback(() => {
    setLegs(prev => [
      ...prev,
      {
        id: generateId(),
        leg_index: prev.length,
        position: "SELL",
        option_type: "CE",
        qty: 75,
        lot_multiplier: 1,
        strike_criteria: "ATM",
        strike_value: 0,
        strike_type: "POINTS",
        sl_enabled: false,
        sl_type: "PERCENT",
        sl_value: 0,
        tp_enabled: false,
        tp_type: "PERCENT",
        tp_value: 0,
      },
    ]);
  }, []);

  // ── Add leg with specific configuration ──
  const addConfiguredLeg = useCallback((config: Partial<StrategyLeg>) => {
    setLegs(prev => [
      ...prev,
      {
        id: generateId(),
        leg_index: prev.length,
        position: config.position || "SELL",
        option_type: config.option_type || "CE",
        qty: config.qty || 75,
        lot_multiplier: config.lot_multiplier || 1,
        strike_criteria: config.strike_criteria || "ATM",
        strike_value: config.strike_value || 0,
        strike_type: config.strike_type || "POINTS",
        sl_enabled: config.sl_enabled || false,
        sl_type: config.sl_type || "PERCENT",
        sl_value: config.sl_value || 0,
        tp_enabled: config.tp_enabled || false,
        tp_type: config.tp_type || "PERCENT",
        tp_value: config.tp_value || 0,
      },
    ]);
  }, []);

  const removeLeg = useCallback((id: string) => {
    setLegs(prev => prev.filter(l => l.id !== id).map((l, i) => ({ ...l, leg_index: i })));
  }, []);

  const updateLeg = useCallback((id: string, updates: Partial<StrategyLeg>) => {
    setLegs(prev => prev.map(l => l.id === id ? { ...l, ...updates } : l));
  }, []);

  const duplicateLeg = useCallback((id: string) => {
    const leg = legs.find(l => l.id === id);
    if (!leg) return;
    setLegs(prev => [
      ...prev,
      { ...leg, id: generateId(), leg_index: prev.length },
    ]);
  }, [legs]);

  // ── Create from template ──
  const createFromTemplate = useCallback(async (templateId: string) => {
    if (!backendOnline) {
      triggerNotif("error", "Backend is offline.");
      return;
    }
    const result = await api.post("/options/strategies/template", {
      template_name: templateId,
      underlying_symbol: chainSymbol,
    });
    if (result.ok && result.data) {
      triggerNotif("success", `Strategy created from template: ${result.data.strategy?.name}`);
      loadSavedStrategies();
    } else {
      triggerNotif("error", result.error || "Failed to create from template.");
    }
  }, [chainSymbol, backendOnline, triggerNotif, loadSavedStrategies]);

  // ── Save strategy ──
  const saveStrategy = useCallback(async () => {
    if (!backendOnline) {
      triggerNotif("error", "Backend is offline.");
      return;
    }
    const result = await api.post("/options/strategies", {
      name: strategyName,
      underlying_symbol: chainSymbol,
      trade_type: tradeType,
      start_time: startTime,
      end_time: endTime,
      expiry_type: expiryType,
      strategy_type: strategyType,
      initial_capital: initialCapital,
      trade_mon: tradeDays.mon,
      trade_tue: tradeDays.tue,
      trade_wed: tradeDays.wed,
      trade_thu: tradeDays.thu,
      trade_fri: tradeDays.fri,
      legs: legs.map(l => ({
        position: l.position,
        option_type: l.option_type,
        qty: l.qty,
        lot_multiplier: l.lot_multiplier,
        strike_criteria: l.strike_criteria,
        strike_value: l.strike_value,
        strike_type: l.strike_type,
        sl_enabled: l.sl_enabled,
        sl_type: l.sl_type,
        sl_value: l.sl_value,
        tp_enabled: l.tp_enabled,
        tp_type: l.tp_type,
        tp_value: l.tp_value,
      })),
    });
    if (result.ok && result.data) {
      triggerNotif("success", "Strategy saved successfully.");
      loadSavedStrategies();
    } else {
      triggerNotif("error", result.error || "Failed to save strategy.");
    }
  }, [backendOnline, chainSymbol, tradeType, startTime, endTime, expiryType, strategyType, initialCapital, tradeDays, legs, strategyName, triggerNotif, loadSavedStrategies]);

  // ── Payoff calculation ──
  const payoff = useMemo(() => {
    if (!chainData || !chainData.ltp || !chainData.strikes.length) {
      return { spotPrices: [], payoffs: [], maxProfit: 0, maxLoss: 0, breakevens: [] };
    }
    return calculatePayoff(legs, chainData.ltp, chainData.strikes, chainData);
  }, [legs, chainData]);

  const marginEstimate = useMemo(() => {
    if (!chainData || !chainData.ltp || !chainData.strikes.length) return 0;
    return calculateMarginEstimate(legs, chainData.ltp, chainData.strikes, chainData);
  }, [legs, chainData]);

  const netPremium = useMemo(() => {
    if (!chainData || !chainData.strikes.length) return 0;
    let total = 0;
    for (const leg of legs) {
      const strike = resolveStrike(chainData.ltp, leg.strike_criteria, leg.strike_value, leg.strike_type, leg.option_type, chainData.strikes);
      const ceData = chainData.chain[strike]?.CE;
      const peData = chainData.chain[strike]?.PE;
      const premium = leg.option_type === "CE" ? (ceData?.ltp || 0) : (peData?.ltp || 0);
      const qty = leg.qty * leg.lot_multiplier;
      total += leg.position === "SELL" ? premium * qty : -premium * qty;
    }
    return total;
  }, [legs, chainData]);

  // ── Payoff chart options ──
  const payoffChartOption = useMemo(() => {
    if (!payoff.spotPrices.length) return null;
    const colorAbove = "#22c55e";
    const colorBelow = "#ef4444";
    return {
      grid: { left: 50, right: 30, top: 30, bottom: 50 },
      xAxis: {
        type: "category" as const,
        data: payoff.spotPrices.map(p => p.toFixed(0)),
        name: "Spot Price",
        nameLocation: "middle" as const,
        nameGap: 35,
        axisLine: { lineStyle: { color: "#475569" } },
        axisLabel: { color: "#94a3b8", fontSize: 10, rotate: 45, interval: Math.floor(payoff.spotPrices.length / 10) },
      },
      yAxis: {
        type: "value" as const,
        name: "P&L",
        nameLocation: "middle" as const,
        nameGap: 45,
        axisLine: { lineStyle: { color: "#475569" } },
        axisLabel: { color: "#94a3b8", fontSize: 10 },
        splitLine: { lineStyle: { color: "#334155" } },
      },
      series: [
        {
          name: "Payoff",
          type: "line" as const,
          data: payoff.payoffs,
          smooth: true,
          lineStyle: { width: 2, color: (params: any) => params.value >= 0 ? colorAbove : colorBelow },
          areaStyle: {
            color: (params: any) => {
              return {
                type: "linear" as const,
                x: 0, y: 0, x2: 0, y2: 1,
                colorStops: [
                  { offset: 0, color: "rgba(34, 197, 94, 0.2)" },
                  { offset: 1, color: "rgba(239, 68, 68, 0.2)" },
                ],
              };
            },
          },
          markLine: {
            silent: true,
            data: [
              { yAxis: 0, lineStyle: { color: "#64748b", type: "dashed" } },
              ...payoff.breakevens.map(b => ({
                xAxis: b.toFixed(0),
                lineStyle: { color: "#f59e0b", type: "dashed" },
                label: { formatter: "BE: {c}", color: "#f59e0b", fontSize: 10 },
              })),
            ],
          },
        },
      ],
      tooltip: {
        trigger: "axis" as const,
        formatter: (params: any[]) => {
          const p = params[0];
          return `Spot: ${p.axisValue}<br/>P&L: ₹${p.value.toFixed(2)}`;
        },
      },
    };
  }, [payoff]);

  const ltp = chainData?.ltp || 0;
  const atmStrike = chainData ? findAtmStrike(ltp, chainData.strikes) : 0;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 h-full items-start">
      {/* Left Panel: Option Chain + Config */}
      <div className="xl:col-span-2 space-y-6">
        {/* Symbol & Expiry Selector */}
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-bold text-slate-200 text-sm flex items-center gap-2">
              <Target className="w-4 h-4 text-blue-400" />
              Option Chain
            </h4>
            <div className="flex items-center gap-2">
              {chainData?.is_mock && (
                <span className="text-[10px] bg-amber-950/40 text-amber-400 px-2 py-0.5 rounded border border-amber-800/40">
                  Mock Data
                </span>
              )}
              <button
                onClick={loadChain}
                disabled={chainLoading}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded text-xs font-bold flex items-center gap-1.5 transition-all"
              >
                {chainLoading ? <RefreshCw size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                Refresh
              </button>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Underlying</label>
              <input
                type="text"
                value={chainSymbol}
                onChange={e => setChainSymbol(e.target.value.toUpperCase())}
                className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-mono font-semibold"
                placeholder="NSE:NIFTY 50"
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Expiry</label>
              <select
                value={selectedExpiry}
                onChange={e => setSelectedExpiry(e.target.value)}
                className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-semibold"
              >
                {chainData?.expiry_dates?.map(d => (
                  <option key={d} value={d}>{d}</option>
                )) || <option>--</option>}
              </select>
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">LTP</label>
              <div className="text-xs font-mono font-bold text-slate-200 bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5">
                {ltp ? `₹${ltp.toFixed(2)}` : "--"}
              </div>
            </div>
          </div>
        </div>

        {/* Option Chain Table */}
        <div className="glass-panel rounded-xl overflow-hidden border-slate-800/60">
          {chainData && chainData.strikes.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-950/60 border-b border-slate-800">
                    <th className="px-2 py-2 text-[10px] font-bold text-slate-500 text-left">Call</th>
                    <th className="px-2 py-2 text-[10px] font-bold text-slate-500 text-center">Delta</th>
                    <th className="px-2 py-2 text-[10px] font-bold text-blue-400 text-center">Strike</th>
                    <th className="px-2 py-2 text-[10px] font-bold text-slate-500 text-center">Delta</th>
                    <th className="px-2 py-2 text-[10px] font-bold text-slate-500 text-right">Put</th>
                  </tr>
                </thead>
                <tbody>
                  {chainData.strikes.map(strike => {
                    const ce = chainData.chain[strike]?.CE;
                    const pe = chainData.chain[strike]?.PE;
                    const isAtm = Math.abs(strike - atmStrike) < 0.01;
                    return (
                      <tr
                        key={strike}
                        className={`border-b border-slate-800/40 hover:bg-slate-900/40 transition-colors ${isAtm ? "bg-blue-950/20" : ""}`}
                      >
                        <td className="px-2 py-1.5">
                          <div className="flex items-center gap-1">
                            <button
                              className="px-1.5 py-0.5 bg-emerald-950/50 text-emerald-400 text-[10px] font-bold rounded border border-emerald-800/40 hover:bg-emerald-900/50"
                              onClick={() => addConfiguredLeg({ position: "BUY", option_type: "CE", strike_criteria: "ATM", strike_value: 0, qty: 75 })}
                              title="Buy CE"
                            >
                              B
                            </button>
                            <button
                              className="px-1.5 py-0.5 bg-rose-950/50 text-rose-400 text-[10px] font-bold rounded border border-rose-800/40 hover:bg-rose-900/50"
                              onClick={() => addConfiguredLeg({ position: "SELL", option_type: "CE", strike_criteria: "ATM", strike_value: 0, qty: 75 })}
                              title="Sell CE"
                            >
                              S
                            </button>
                            <span className={`font-mono font-bold ${ce?.ltp ? "text-emerald-400" : "text-slate-600"}`}>
                              {ce?.ltp?.toFixed(2) || "--"}
                            </span>
                          </div>
                          {ce?.volume > 0 && (
                            <div className="text-[9px] text-slate-500 font-mono mt-0.5">
                              OI: {ce?.open_interest?.toLocaleString() || "--"} | Vol: {ce?.volume?.toLocaleString() || "--"}
                            </div>
                          )}
                        </td>
                        <td className="px-2 py-1.5 text-center font-mono text-slate-400">
                          {ce?.delta?.toFixed(2) || "--"}
                        </td>
                        <td className={`px-2 py-1.5 text-center font-mono font-bold ${isAtm ? "text-blue-400" : "text-slate-300"}`}>
                          {strike.toLocaleString()}
                          {isAtm && <span className="text-[9px] text-blue-400 ml-1">ATM</span>}
                        </td>
                        <td className="px-2 py-1.5 text-center font-mono text-slate-400">
                          {pe?.delta?.toFixed(2) || "--"}
                        </td>
                        <td className="px-2 py-1.5 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <span className={`font-mono font-bold ${pe?.ltp ? "text-rose-400" : "text-slate-600"}`}>
                              {pe?.ltp?.toFixed(2) || "--"}
                            </span>
                            <button
                              className="px-1.5 py-0.5 bg-emerald-950/50 text-emerald-400 text-[10px] font-bold rounded border border-emerald-800/40 hover:bg-emerald-900/50"
                              onClick={() => addConfiguredLeg({ position: "BUY", option_type: "PE", strike_criteria: "ATM", strike_value: 0, qty: 75 })}
                              title="Buy PE"
                            >
                              B
                            </button>
                            <button
                              className="px-1.5 py-0.5 bg-rose-950/50 text-rose-400 text-[10px] font-bold rounded border border-rose-800/40 hover:bg-rose-900/50"
                              onClick={() => addConfiguredLeg({ position: "SELL", option_type: "PE", strike_criteria: "ATM", strike_value: 0, qty: 75 })}
                              title="Sell PE"
                            >
                              S
                            </button>
                          </div>
                          {pe?.volume > 0 && (
                            <div className="text-[9px] text-slate-500 font-mono mt-0.5">
                              OI: {pe?.open_interest?.toLocaleString() || "--"} | Vol: {pe?.volume?.toLocaleString() || "--"}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center p-12 text-slate-500">
              <BarChart3 size={32} className="mb-3 opacity-50" />
              <p className="text-xs font-bold">No option chain data</p>
              <p className="text-[10px] mt-1">Enter a symbol and click Refresh to load</p>
            </div>
          )}
        </div>
      </div>

      {/* Right Panel: Strategy Builder + Payoff */}
      <div className="xl:col-span-1 space-y-6">
        {/* Strategy Config */}
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <h4 className="font-bold text-slate-200 text-sm flex items-center gap-2">
            <Layers className="w-4 h-4 text-emerald-400" />
            Strategy Builder
          </h4>

          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Strategy Name</label>
            <input
              type="text"
              value={strategyName}
              onChange={e => setStrategyName(e.target.value)}
              className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-semibold"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Strategy Type</label>
              <select
                value={strategyType}
                onChange={e => setStrategyType(e.target.value)}
                className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-semibold"
              >
                <option value="indicator">Indicator Based</option>
                <option value="time-based">Time Based</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Order Type</label>
              <select
                value={tradeType}
                onChange={e => setTradeType(e.target.value)}
                className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-semibold"
              >
                <option value="MIS">MIS</option>
                <option value="CNC">CNC</option>
                <option value="BTST">BTST</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Start Time</label>
              <input
                type="time"
                value={startTime}
                onChange={e => setStartTime(e.target.value)}
                className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-semibold"
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">End Time</label>
              <input
                type="time"
                value={endTime}
                onChange={e => setEndTime(e.target.value)}
                className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-semibold"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Expiry</label>
              <select
                value={expiryType}
                onChange={e => setExpiryType(e.target.value)}
                className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-semibold"
              >
                <option value="WEEKLY">Weekly</option>
                <option value="MONTHLY">Monthly</option>
                <option value="NEXT_WEEKLY">Next Weekly</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Capital</label>
              <input
                type="number"
                value={initialCapital}
                onChange={e => setInitialCapital(Number(e.target.value))}
                className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-semibold font-mono"
              />
            </div>
          </div>

          {/* Day toggles */}
          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Trade Days</label>
            <div className="flex gap-1">
              {(["mon", "tue", "wed", "thu", "fri"] as const).map(day => (
                <button
                  key={day}
                  onClick={() => setTradeDays(prev => ({ ...prev, [day]: !prev[day] }))}
                  className={`flex-1 py-1 text-[10px] font-bold rounded border transition-all ${
                    tradeDays[day]
                      ? "bg-blue-600/20 border-blue-500 text-blue-400"
                      : "bg-slate-950 border-slate-800 text-slate-500"
                  }`}
                >
                  {day.toUpperCase().slice(0, 3)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Legs */}
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-bold text-slate-200 text-sm flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" />
              Strategy Legs
            </h4>
            <button
              onClick={addLeg}
              className="px-2 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-bold flex items-center gap-1 transition-all"
            >
              <Plus size={12} /> Add Leg
            </button>
          </div>

          {legs.map((leg, index) => (
            <div key={leg.id} className="bg-slate-950/40 border border-slate-800/60 rounded-lg p-3 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-400">Leg {index + 1}</span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => duplicateLeg(leg.id)}
                    className="p-1 text-slate-500 hover:text-slate-300 transition-colors"
                    title="Duplicate"
                  >
                    <Copy size={12} />
                  </button>
                  <button
                    onClick={() => removeLeg(leg.id)}
                    className="p-1 text-slate-500 hover:text-rose-400 transition-colors"
                    title="Remove"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Position</label>
                  <div className="grid grid-cols-2 gap-1">
                    <button
                      onClick={() => updateLeg(leg.id, { position: "BUY" })}
                      className={`py-1 text-[10px] font-bold rounded border transition-all ${
                        leg.position === "BUY" ? "bg-emerald-600/20 border-emerald-500 text-emerald-400" : "bg-slate-950 border-slate-800 text-slate-500"
                      }`}
                    >
                      BUY
                    </button>
                    <button
                      onClick={() => updateLeg(leg.id, { position: "SELL" })}
                      className={`py-1 text-[10px] font-bold rounded border transition-all ${
                        leg.position === "SELL" ? "bg-rose-600/20 border-rose-500 text-rose-400" : "bg-slate-950 border-slate-800 text-slate-500"
                      }`}
                    >
                      SELL
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Type</label>
                  <div className="grid grid-cols-2 gap-1">
                    <button
                      onClick={() => updateLeg(leg.id, { option_type: "CE" })}
                      className={`py-1 text-[10px] font-bold rounded border transition-all ${
                        leg.option_type === "CE" ? "bg-blue-600/20 border-blue-500 text-blue-400" : "bg-slate-950 border-slate-800 text-slate-500"
                      }`}
                    >
                      CE
                    </button>
                    <button
                      onClick={() => updateLeg(leg.id, { option_type: "PE" })}
                      className={`py-1 text-[10px] font-bold rounded border transition-all ${
                        leg.option_type === "PE" ? "bg-violet-600/20 border-violet-500 text-violet-400" : "bg-slate-950 border-slate-800 text-slate-500"
                      }`}
                    >
                      PE
                    </button>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Qty</label>
                  <input
                    type="number"
                    value={leg.qty}
                    onChange={e => updateLeg(leg.id, { qty: Number(e.target.value) })}
                    className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono font-semibold"
                  />
                </div>
                <div>
                  <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Lots</label>
                  <input
                    type="number"
                    value={leg.lot_multiplier}
                    onChange={e => updateLeg(leg.id, { lot_multiplier: Number(e.target.value) })}
                    className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono font-semibold"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Strike</label>
                  <select
                    value={leg.strike_criteria}
                    onChange={e => updateLeg(leg.id, { strike_criteria: e.target.value })}
                    className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-semibold"
                  >
                    <option value="ATM">ATM</option>
                    <option value="ITM">ITM</option>
                    <option value="OTM">OTM</option>
                    <option value="ATM+POINTS">ATM + Points</option>
                    <option value="ATM+PERCENT">ATM + %</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Value</label>
                  <input
                    type="number"
                    value={leg.strike_value}
                    onChange={e => updateLeg(leg.id, { strike_value: Number(e.target.value) })}
                    className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono font-semibold"
                  />
                </div>
              </div>

              {/* SL */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={leg.sl_enabled}
                  onChange={e => updateLeg(leg.id, { sl_enabled: e.target.checked })}
                  className="w-3 h-3"
                />
                <span className="text-[10px] font-bold text-slate-500">SL</span>
                {leg.sl_enabled && (
                  <div className="flex items-center gap-1 flex-1">
                    <input
                      type="number"
                      value={leg.sl_value}
                      onChange={e => updateLeg(leg.id, { sl_value: Number(e.target.value) })}
                      className="w-16 text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono"
                    />
                    <select
                      value={leg.sl_type}
                      onChange={e => updateLeg(leg.id, { sl_type: e.target.value })}
                      className="text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-semibold"
                    >
                      <option value="PERCENT">%</option>
                      <option value="POINTS">pts</option>
                    </select>
                  </div>
                )}
              </div>

              {/* TP */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={leg.tp_enabled}
                  onChange={e => updateLeg(leg.id, { tp_enabled: e.target.checked })}
                  className="w-3 h-3"
                />
                <span className="text-[10px] font-bold text-slate-500">TP</span>
                {leg.tp_enabled && (
                  <div className="flex items-center gap-1 flex-1">
                    <input
                      type="number"
                      value={leg.tp_value}
                      onChange={e => updateLeg(leg.id, { tp_value: Number(e.target.value) })}
                      className="w-16 text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono"
                    />
                    <select
                      value={leg.tp_type}
                      onChange={e => updateLeg(leg.id, { tp_type: e.target.value })}
                      className="text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-semibold"
                    >
                      <option value="PERCENT">%</option>
                      <option value="POINTS">pts</option>
                    </select>
                  </div>
                )}
              </div>
            </div>
          ))}

          <button
            onClick={saveStrategy}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-bold py-2.5 flex items-center justify-center gap-2 transition-all"
          >
            <Save size={13} /> Save Strategy
          </button>
        </div>

        {/* Payoff Metrics */}
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <h4 className="font-bold text-slate-200 text-sm flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-purple-400" />
            Payoff Analysis
          </h4>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-slate-950/40 rounded p-2 border border-slate-800/40">
              <div className="text-[10px] font-bold text-slate-500 uppercase">Net Premium</div>
              <div className={`font-mono font-bold ${netPremium >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                ₹{netPremium.toFixed(2)}
              </div>
            </div>
            <div className="bg-slate-950/40 rounded p-2 border border-slate-800/40">
              <div className="text-[10px] font-bold text-slate-500 uppercase">Est. Margin</div>
              <div className="font-mono font-bold text-amber-400">
                ₹{marginEstimate.toFixed(0)}
              </div>
            </div>
            <div className="bg-slate-950/40 rounded p-2 border border-slate-800/40">
              <div className="text-[10px] font-bold text-slate-500 uppercase">Max Profit</div>
              <div className="font-mono font-bold text-emerald-400">
                ₹{payoff.maxProfit.toFixed(2)}
              </div>
            </div>
            <div className="bg-slate-950/40 rounded p-2 border border-slate-800/40">
              <div className="text-[10px] font-bold text-slate-500 uppercase">Max Loss</div>
              <div className="font-mono font-bold text-rose-400">
                ₹{payoff.maxLoss.toFixed(2)}
              </div>
            </div>
          </div>

          {payoff.breakevens.length > 0 && (
            <div className="bg-slate-950/40 rounded p-2 border border-slate-800/40">
              <div className="text-[10px] font-bold text-slate-500 uppercase mb-1">Breakevens</div>
              <div className="flex flex-wrap gap-1">
                {payoff.breakevens.map((be, i) => (
                  <span key={i} className="text-xs font-mono font-bold text-amber-400 bg-amber-950/30 px-2 py-0.5 rounded">
                    {be.toFixed(0)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Payoff Chart */}
          {payoffChartOption && (
            <div className="h-48">
              <ReactECharts option={payoffChartOption} style={{ height: "100%", width: "100%" }} />
            </div>
          )}
        </div>

        {/* Templates */}
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <h4 className="font-bold text-slate-200 text-sm flex items-center gap-2">
            <Package className="w-4 h-4 text-cyan-400" />
            Strategy Templates
          </h4>
          <div className="space-y-2">
            {templates.map(t => (
              <div key={t.id} className="bg-slate-950/40 border border-slate-800/40 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold text-slate-300">{t.name}</div>
                    <div className="text-[10px] text-slate-500 mt-0.5">{t.description}</div>
                    <div className="text-[10px] text-slate-600 mt-0.5 font-mono">{t.example}</div>
                  </div>
                  <button
                    onClick={() => createFromTemplate(t.id)}
                    className="px-2 py-1 bg-blue-600/20 border border-blue-500/30 text-blue-400 hover:bg-blue-600/30 rounded text-[10px] font-bold transition-all"
                  >
                    Use
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Saved Strategies */}
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <h4 className="font-bold text-slate-200 text-sm flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-pink-400" />
            My Strategies
          </h4>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {savedStrategies.map(s => (
              <div key={s.id} className="bg-slate-950/40 border border-slate-800/40 rounded-lg p-3">
                <div className="text-xs font-bold text-slate-300">{s.name}</div>
                <div className="text-[10px] text-slate-500 mt-0.5">
                  {s.underlying_symbol} | {s.trade_type} | {s.legs_count || 2} legs
                </div>
              </div>
            ))}
            {savedStrategies.length === 0 && (
              <div className="text-center text-slate-500 text-xs py-4">
                No saved strategies yet
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
