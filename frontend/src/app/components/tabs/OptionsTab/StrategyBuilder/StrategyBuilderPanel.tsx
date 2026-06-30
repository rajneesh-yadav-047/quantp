"use client";

import { useState } from "react";
import { Plus, Save, Zap, Copy, Trash2, Download, FileUp, Play, Database, CheckCircle2, AlertTriangle, Calendar, SlidersHorizontal } from "lucide-react";
import type { StrategyLeg, StrategyTemplate, TradeDays } from "../types";
import { StrategyMeta } from "./StrategyMeta";
import { LegList } from "./LegList";
import { TemplateLoader } from "./TemplateLoader";
import { api } from "@/lib/api-client";

interface StrategyBuilderPanelProps {
  // Meta
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

  // Legs
  legs: StrategyLeg[];
  onAddLeg: () => void;
  onUpdateLeg: (id: string, updates: Partial<StrategyLeg>) => void;
  onRemoveLeg: (id: string) => void;
  onDuplicateLeg: (id: string) => void;
  onSaveStrategy: () => void;

  // Templates
  templates: StrategyTemplate[];
  templatesLoading: boolean;
  onSelectTemplate: (templateId: string) => void;

  // Data coverage
  datasets: any[];
  checkDataCoverage: (symbols: string[], interval: string, startDate: string, endDate: string) => { symbol: string; interval: string; reason: string }[];

  // Options download
  optionsDlSymbol: string;
  setOptionsDlSymbol: (v: string) => void;
  optionsDlExpiry: string;
  setOptionsDlExpiry: (v: string) => void;
  optionsDlStrikes: string;
  setOptionsDlStrikes: (v: string) => void;
  optionsDlOptionTypes: string;
  setOptionsDlOptionTypes: (v: string) => void;
  optionsDlFromDate: string;
  setOptionsDlFromDate: (v: string) => void;
  optionsDlToDate: string;
  setOptionsDlToDate: (v: string) => void;
  optionsDlJobId: string | null;
  triggerOptionsDownload: (e: React.FormEvent) => void;

  // Bhavcopy
  bhavcopyFromDate: string;
  setBhavcopyFromDate: (v: string) => void;
  bhavcopyToDate: string;
  setBhavcopyToDate: (v: string) => void;
  bhavcopyJobId: string | null;
  triggerOptionsBhavcopyImport: (e: React.FormEvent) => void;

  // Backtest
  chainSymbol: string;
  selectedExpiry: string;
  btStartDate: string;
  setBtStartDate: (v: string) => void;
  btEndDate: string;
  setBtEndDate: (v: string) => void;
  btSlippage: number;
  setBtSlippage: (v: number) => void;
  handleOptionsBacktest: (strategyId: string, startDate: string, endDate: string) => void;
  handleOptionsBacktestFullFlow: (strategyId: string, startDate: string, endDate: string) => void;
  backendOnline: boolean;
}

export function StrategyBuilderPanel(props: StrategyBuilderPanelProps) {
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [coverageMissing, setCoverageMissing] = useState<{ symbol: string; interval: string; reason: string }[]>([]);
  const [coverageAvailable, setCoverageAvailable] = useState<string[]>([]);
  const [showOptionsDl, setShowOptionsDl] = useState(false);
  const [showBhavcopy, setShowBhavcopy] = useState(false);

  const canonicalize = (s: string): string => {
    const sym = s.trim().toUpperCase();
    if (!sym) return sym;
    if (sym.includes(":")) return sym;
    return `NSE:${sym}-EQ`;
  };

  const checkExists = (sym: string, intv: string) => {
    const base = sym.toUpperCase().trim().replace(/\s+/g, "");
    return props.datasets.some((d: any) => {
      const dsSym = (d.symbol || "").toUpperCase().trim();
      const dsBase = dsSym.includes(":") ? dsSym.split(":")[1].replace(/-EQ$|-BE$/i, "") : dsSym.replace(/-EQ$|-BE$/i, "");
      const checkBase = base.includes(":") ? base.split(":")[1].replace(/-EQ$|-BE$/i, "") : base.replace(/-EQ$|-BE$/i, "");
      return (dsBase === checkBase || dsSym === base) && (d.interval || "").toUpperCase() === intv.toUpperCase();
    });
  };

  const handleRunBacktest = async () => {
    if (!props.backendOnline) {
      alert("Backend is offline.");
      return;
    }
    setBacktestLoading(true);
    setCoverageMissing([]);
    setCoverageAvailable([]);

    // 1. Save strategy
    const saveRes = await api.post("/options/strategies", {
      name: props.strategyName || "Options Backtest Strategy",
      underlying_symbol: props.chainSymbol,
      trade_type: props.tradeType,
      start_time: props.startTime,
      end_time: props.endTime,
      expiry_type: props.expiryType,
      strategy_type: props.strategyType,
      initial_capital: props.initialCapital,
      trade_mon: props.tradeDays.mon,
      trade_tue: props.tradeDays.tue,
      trade_wed: props.tradeDays.wed,
      trade_thu: props.tradeDays.thu,
      trade_fri: props.tradeDays.fri,
      legs: props.legs.map(l => ({
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
        sl_on_price: l.sl_on_price,
        tp_enabled: l.tp_enabled,
        tp_type: l.tp_type,
        tp_value: l.tp_value,
        tp_on_price: l.tp_on_price,
        trail_sl_enabled: l.trail_sl_enabled,
        trail_sl_type: l.trail_sl_type,
        trail_sl_value: l.trail_sl_value,
        trail_sl_step: l.trail_sl_step,
      })),
    });
    if (!saveRes.ok || !saveRes.data?.strategy?.id) {
      setBacktestLoading(false);
      alert(saveRes.error || "Failed to save strategy for backtest.");
      return;
    }

    const strategyId = saveRes.data.strategy.id;
    const underlying = canonicalize(props.chainSymbol);
    const interval = "FIVE_MINUTE";

    // 2. Check equity data coverage for the underlying symbol
    const missing = props.checkDataCoverage([underlying], interval, props.btStartDate, props.btEndDate);
    const available = [underlying].filter(s => !missing.some(m => {
      const mBase = m.symbol.toUpperCase().replace(/^(NSE:|NFO:)/, "").replace(/-EQ$|-BE$/, "");
      const sBase = s.toUpperCase().replace(/^(NSE:|NFO:)/, "").replace(/-EQ$|-BE$/, "");
      return mBase === sBase;
    }));

    setCoverageMissing(missing);
    setCoverageAvailable(available);

    if (missing.length > 0) {
      // Data missing — trigger download + TOTP flow via full handler
      setBacktestLoading(false);
      props.handleOptionsBacktestFullFlow(strategyId, props.btStartDate, props.btEndDate);
      return;
    }

    // 3. Data is present — run backtest directly
    props.handleOptionsBacktest(strategyId, props.btStartDate, props.btEndDate);
    setBacktestLoading(false);
  };

  return (
    <div className="xl:col-span-1 space-y-4">
      <StrategyMeta
        strategyName={props.strategyName}
        setStrategyName={props.setStrategyName}
        strategyType={props.strategyType}
        setStrategyType={props.setStrategyType}
        tradeType={props.tradeType}
        setTradeType={props.setTradeType}
        startTime={props.startTime}
        setStartTime={props.setStartTime}
        endTime={props.endTime}
        setEndTime={props.setEndTime}
        expiryType={props.expiryType}
        setExpiryType={props.setExpiryType}
        initialCapital={props.initialCapital}
        setInitialCapital={props.setInitialCapital}
        tradeDays={props.tradeDays}
        setTradeDays={props.setTradeDays}
        optionsDlStrikes={props.optionsDlStrikes}
        setOptionsDlStrikes={props.setOptionsDlStrikes}
      />

      {/* Data Coverage Banner */}
      {(coverageMissing.length > 0 || coverageAvailable.length > 0) && (
        <div className="p-3 border border-[var(--ax-border)] rounded-xl bg-[var(--ax-surface)] space-y-2">
          <div className="flex items-center gap-2 text-[10px] font-bold uppercase text-[#a0a0a0]">
            <Database className="w-3 h-3" />
            Data Coverage
          </div>
          <div className="flex flex-wrap gap-1.5">
            {coverageAvailable.map(sym => (
              <span key={sym} className="flex items-center gap-1 bg-emerald-950/60 border border-emerald-800/60 text-emerald-400 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full">
                <CheckCircle2 size={10} /> {sym}
              </span>
            ))}
            {coverageMissing.map(m => (
              <span key={m.symbol} className="flex items-center gap-1 bg-red-950/60 border border-red-800/60 text-red-400 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full">
                <AlertTriangle size={10} /> {m.symbol} ({m.interval}) — {m.reason}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Backtest Config — Inline, always visible */}
      <div className="p-4 border border-[var(--ax-border)] rounded-xl bg-[var(--ax-surface)] space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="font-bold text-[#c0c0c0] text-sm flex items-center gap-2">
            <Calendar className="w-4 h-4 text-[#93b4ff]" />
            Backtest Config
          </h4>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">From Date</label>
            <input type="date" value={props.btStartDate} onChange={e => props.setBtStartDate(e.target.value)} className="t-input w-full text-xs rounded px-2.5 py-1.5" />
          </div>
          <div>
            <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">To Date</label>
            <input type="date" value={props.btEndDate} onChange={e => props.setBtEndDate(e.target.value)} className="t-input w-full text-xs rounded px-2.5 py-1.5" />
          </div>
        </div>
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">Slippage %</label>
          <div className="flex items-center gap-2">
            <input type="number" step="0.01" min="0" max="5" value={props.btSlippage} onChange={e => props.setBtSlippage(Number(e.target.value))} className="t-input w-24 text-xs rounded px-2.5 py-1.5" />
            <span className="text-[10px] text-[#606060]">Applied to fill prices</span>
          </div>
        </div>
        <button
          onClick={handleRunBacktest}
          disabled={backtestLoading}
          className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-[#161616] disabled:text-[#606060] text-[#f0f0f0] rounded text-xs font-bold py-2.5 flex items-center justify-center gap-2 transition-all"
        >
          <Play size={13} fill="currentColor" /> {backtestLoading ? "Checking & Running…" : "Run Backtest"}
        </button>
      </div>

      <LegList
        legs={props.legs}
        onAdd={props.onAddLeg}
        onUpdate={props.onUpdateLeg}
        onRemove={props.onRemoveLeg}
        onDuplicate={props.onDuplicateLeg}
        onSave={props.onSaveStrategy}
      />

      {/* Data Tools — Collapsible */}
      <div className="p-4 border border-[var(--ax-border)] rounded-xl bg-[var(--ax-surface)] space-y-3">
        <h4 className="font-bold text-[#c0c0c0] text-sm flex items-center gap-2">
          <SlidersHorizontal className="w-4 h-4 text-[#93b4ff]" />
          Data Tools
        </h4>

        {/* Options Data Download */}
        <div>
          <button
            onClick={() => setShowOptionsDl(!showOptionsDl)}
            className="w-full text-left px-3 py-2 rounded-lg bg-[#111] border border-[var(--ax-border)]/60 hover:bg-[#161616] transition-all text-xs font-bold text-[#c0c0c0] flex items-center justify-between"
          >
            <span className="flex items-center gap-2"><Download size={12} /> Download Options Data</span>
            <span className="text-[10px] text-[#606060]">{showOptionsDl ? "▲" : "▼"}</span>
          </button>
          {showOptionsDl && (
            <form onSubmit={props.triggerOptionsDownload} className="mt-2 space-y-2 p-3 bg-[#111] rounded-lg border border-[var(--ax-border)]/40">
              <div>
                <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">Underlying Symbol</label>
                <input type="text" value={props.optionsDlSymbol} onChange={e => props.setOptionsDlSymbol(e.target.value)} className="t-input w-full text-xs rounded px-2.5 py-1.5" placeholder="NSE:NIFTY 50" />
              </div>
              <div>
                <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">Expiry (YYYY-MM-DD)</label>
                <input type="text" value={props.optionsDlExpiry} onChange={e => props.setOptionsDlExpiry(e.target.value)} className="t-input w-full text-xs rounded px-2.5 py-1.5" placeholder="2024-06-27" />
              </div>
              <div>
                <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">Strikes (comma-separated)</label>
                <input type="text" value={props.optionsDlStrikes} onChange={e => props.setOptionsDlStrikes(e.target.value)} className="t-input w-full text-xs rounded px-2.5 py-1.5" placeholder="22500, 22600, 22700" />
              </div>
              <div>
                <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">Option Types</label>
                <input type="text" value={props.optionsDlOptionTypes} onChange={e => props.setOptionsDlOptionTypes(e.target.value)} className="t-input w-full text-xs rounded px-2.5 py-1.5" placeholder="CE,PE" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">From</label>
                  <input type="date" value={props.optionsDlFromDate} onChange={e => props.setOptionsDlFromDate(e.target.value)} className="t-input w-full text-xs rounded px-2.5 py-1.5" />
                </div>
                <div>
                  <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">To</label>
                  <input type="date" value={props.optionsDlToDate} onChange={e => props.setOptionsDlToDate(e.target.value)} className="t-input w-full text-xs rounded px-2.5 py-1.5" />
                </div>
              </div>
              <button
                type="submit"
                disabled={!!props.optionsDlJobId}
                className="w-full bg-[#4a7fcc] hover:bg-[#5a8fd0] disabled:bg-[#161616] disabled:text-[#606060] text-[#f0f0f0] rounded text-xs font-bold py-2 flex items-center justify-center gap-2 transition-all"
              >
                <Download size={12} /> {props.optionsDlJobId ? "Downloading…" : "Queue Options Download"}
              </button>
            </form>
          )}
        </div>

        {/* Bhavcopy Import */}
        <div>
          <button
            onClick={() => setShowBhavcopy(!showBhavcopy)}
            className="w-full text-left px-3 py-2 rounded-lg bg-[#111] border border-[var(--ax-border)]/60 hover:bg-[#161616] transition-all text-xs font-bold text-[#c0c0c0] flex items-center justify-between"
          >
            <span className="flex items-center gap-2"><FileUp size={12} /> Import NSE Bhavcopy</span>
            <span className="text-[10px] text-[#606060]">{showBhavcopy ? "▲" : "▼"}</span>
          </button>
          {showBhavcopy && (
            <form onSubmit={props.triggerOptionsBhavcopyImport} className="mt-2 space-y-2 p-3 bg-[#111] rounded-lg border border-[var(--ax-border)]/40">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">From Date</label>
                  <input type="date" value={props.bhavcopyFromDate} onChange={e => props.setBhavcopyFromDate(e.target.value)} className="t-input w-full text-xs rounded px-2.5 py-1.5" />
                </div>
                <div>
                  <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">To Date</label>
                  <input type="date" value={props.bhavcopyToDate} onChange={e => props.setBhavcopyToDate(e.target.value)} className="t-input w-full text-xs rounded px-2.5 py-1.5" />
                </div>
              </div>
              <button
                type="submit"
                disabled={!!props.bhavcopyJobId}
                className="w-full bg-[#4a7fcc] hover:bg-[#5a8fd0] disabled:bg-[#161616] disabled:text-[#606060] text-[#f0f0f0] rounded text-xs font-bold py-2 flex items-center justify-center gap-2 transition-all"
              >
                <FileUp size={12} /> {props.bhavcopyJobId ? "Importing…" : "Queue Bhavcopy Import"}
              </button>
            </form>
          )}
        </div>
      </div>

      <TemplateLoader
        templates={props.templates}
        loading={props.templatesLoading}
        onSelect={props.onSelectTemplate}
      />
    </div>
  );
}
