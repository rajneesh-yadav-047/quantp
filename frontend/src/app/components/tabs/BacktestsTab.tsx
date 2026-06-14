"use client";

import React, { useState, useMemo } from "react";
import {
  Play, Pause, SkipForward, SkipBack, AlertTriangle, Layers,
  PlayCircle, Calendar, Database, CheckCircle2, XCircle,
  TrendingUp, BarChart3, Clock, Wallet, DollarSign, Award,
  Sliders, ChevronRight, ListCollapse
} from "lucide-react";
import dynamic from "next/dynamic";

const LightweightChart = dynamic(() => import("../../../components/LightweightChart"), { ssr: false });
const PositionChart = dynamic(() => import("../../../components/PositionChart"), { ssr: false });

export function BacktestsTab({
  strategies, selectedStrategyId, handleSelectStrategy,
  btStartDate, setBtStartDate, btEndDate, setBtEndDate, btSlippage, setBtSlippage,
  btTradeType, setBtTradeType, btIsAutoMaxPos, setBtIsAutoMaxPos,
  btAutoMaxPosValue, setBtAutoMaxPosValue, btMaxPositionSize, setBtMaxPositionSize,
  handleRunBacktest, backtestDetail, backtestRuns, handleSelectRun,
  showEmaFast, setShowEmaFast, showEmaSlow, setShowEmaSlow,
  showBuyTrades, setShowBuyTrades, showSellTrades, setShowSellTrades,
  isPlaying, setIsPlaying, playbackSpeed, setPlaybackSpeed,
  currentStep, setCurrentStep, replayEvents, currentEvent, currentPortfolio,
  activeCandles, activeTrades, positionCurveData,
  datasets, checkDataCoverage, pendingBacktest, setPendingBacktest,
}: any) {
  const [activeResultsTab, setActiveResultsTab] = useState<"replay" | "trades" | "metrics">("replay");

  const selectedStrategy = strategies.find((s: any) => s.id === selectedStrategyId);
  const symbols = selectedStrategy?.symbols || [selectedStrategy?.symbol || "SBIN"];
  const interval = selectedStrategy?.interval || "FIVE_MINUTE";

  const coverage = useMemo(() => {
    if (!selectedStrategyId) return { missing: [], available: [] as any[] };
    return {
      missing: checkDataCoverage(symbols, interval, btStartDate, btEndDate),
      available: symbols.map((sym: string) => {
        const symBase = sym.toUpperCase().trim();
        const ds = datasets.find((d: any) => {
          const dsSym = (d.symbol || "").toUpperCase().trim();
          const dsBase = dsSym.includes(":") ? dsSym.split(":")[1].replace(/-EQ$|-BE$/i, "") : dsSym.replace(/-EQ$|-BE$/i, "");
          return dsBase === symBase && (d.interval || "").toUpperCase() === interval.toUpperCase();
        });
        return ds ? { symbol: sym, interval, start: ds.start_date?.slice(0, 10), end: ds.end_date?.slice(0, 10) } : null;
      }).filter(Boolean),
    };
  }, [selectedStrategyId, symbols, interval, btStartDate, btEndDate, checkDataCoverage, datasets]);

  const isDateRangeValid = coverage.missing.length === 0;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 h-full items-start">
      {/* Sidebar Controls Panel */}
      <div className="xl:col-span-1 glass-panel p-5 rounded-xl space-y-5 flex flex-col justify-between self-start shadow-xl">
        <div className="space-y-4">
          <h4 className="font-bold text-slate-200 text-sm flex items-center gap-2 border-b border-slate-800 pb-3">
            <Sliders className="w-4 h-4 text-blue-400" />
            Backtest Configurations
          </h4>

          {/* Strategy Select */}
          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-450 mb-1.5">Target Strategy</label>
            <select
              value={selectedStrategyId}
              onChange={e => handleSelectStrategy(e.target.value)}
              className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500 font-semibold"
            >
              <option value="">-- Select Strategy --</option>
              {strategies.map((s: any) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          {/* Date Picker Range */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-450 mb-1.5 flex items-center gap-1">
                <Calendar size={10} className="text-blue-400" /> From Date
              </label>
              <input
                type="date"
                value={btStartDate}
                onChange={e => setBtStartDate(e.target.value)}
                className={`text-xs bg-slate-950 border rounded px-2 py-1.5 text-slate-200 w-full focus:outline-none ${
                  !isDateRangeValid && coverage.missing.some((m: any) => btStartDate < m.startDate)
                    ? 'border-rose-700 focus:border-rose-500'
                    : 'border-slate-800 focus:border-blue-500'
                }`}
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-450 mb-1.5 flex items-center gap-1">
                <Calendar size={10} className="text-blue-400" /> To Date
              </label>
              <input
                type="date"
                value={btEndDate}
                onChange={e => setBtEndDate(e.target.value)}
                className={`text-xs bg-slate-950 border rounded px-2 py-1.5 text-slate-200 w-full focus:outline-none ${
                  !isDateRangeValid && coverage.missing.some((m: any) => btEndDate > m.endDate)
                    ? 'border-rose-700 focus:border-rose-500'
                    : 'border-slate-800 focus:border-blue-500'
                }`}
              />
            </div>
          </div>

          {/* Slippage & Position Limits */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-450 mb-1.5">Slippage %</label>
              <input
                type="number"
                step="0.01"
                value={btSlippage}
                onChange={e => setBtSlippage(Number(e.target.value))}
                className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-semibold font-mono"
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-450 mb-1.5">Max Position Size</label>
              <input
                type="number"
                value={btMaxPositionSize || ""}
                onChange={e => setBtMaxPositionSize(e.target.value ? parseInt(e.target.value) : null)}
                placeholder="Auto"
                className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-semibold font-mono"
              />
            </div>
          </div>

          {/* Trade Type Selection */}
          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-450 mb-1.5">Trade Execution Mode</label>
            <div className="grid grid-cols-3 gap-1">
              {["INTRADAY", "DELIVERY", "FUTURES"].map(t => (
                <button
                  key={t}
                  onClick={() => setBtTradeType(t)}
                  className={`px-1 py-1.5 text-[9px] font-bold border rounded transition-all ${
                    btTradeType === t
                      ? "bg-blue-600/15 border-blue-500 text-blue-400 shadow-sm"
                      : "border-slate-850 text-slate-450 bg-slate-950/50 hover:bg-slate-900"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Data Validation Notification Cards */}
        {selectedStrategyId && (
          <div className="space-y-2 pt-2">
            {coverage.missing.length > 0 && (
              <div className="flex items-start gap-2 p-2.5 rounded-lg border border-rose-800/40 bg-rose-950/20 text-rose-400 text-[10px] leading-relaxed">
                <XCircle size={14} className="shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-bold mb-1">Missing Coverage Period:</p>
                  {coverage.missing.map((m: any, i: number) => (
                    <p key={i} className="text-rose-300/80">{m.symbol}: {m.reason}</p>
                  ))}
                  <p className="text-[9px] text-rose-300/50 mt-1.5 italic">Will auto-download from SmartAPI on backtest run.</p>
                </div>
              </div>
            )}
            {coverage.available.length > 0 && coverage.missing.length === 0 && (
              <div className="flex items-start gap-2 p-2 rounded-lg border border-emerald-800/40 bg-emerald-950/20 text-emerald-400 text-[10px]">
                <CheckCircle2 size={13} className="shrink-0 mt-0.5" />
                <span>Historical data cached and verified locally for backtest parameters.</span>
              </div>
            )}
            {coverage.available.length === 0 && coverage.missing.length === 0 && (
              <div className="flex items-start gap-2 p-2 rounded-lg border border-slate-850 bg-slate-950/40 text-slate-500 text-[10px]">
                <Database size={13} className="shrink-0 mt-0.5" />
                <span>No local cache folders found for {symbols.join(", ")}. Missing candles will be downloaded.</span>
              </div>
            )}
          </div>
        )}

        <button
          onClick={handleRunBacktest}
          disabled={!selectedStrategyId}
          className="w-full mt-4 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded font-bold text-xs py-2 px-4 transition-all flex items-center justify-center gap-2"
        >
          <PlayCircle size={14} fill="currentColor" /> Run Simulation Engine
        </button>
      </div>

      {/* Main Results View */}
      <div className="xl:col-span-3 h-full flex flex-col gap-6">
        {backtestDetail ? (
          <>
            {/* Top Stat Ribbon */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Simulator Return", val: `${(((backtestDetail.final_equity - backtestDetail.initial_capital) / backtestDetail.initial_capital) * 100).toFixed(1)}%`, color: backtestDetail.total_pnl >= 0 ? "text-emerald-400" : "text-rose-400", icon: TrendingUp },
                { label: "Sharpe Ratio", val: backtestDetail.sharpe_ratio?.toFixed(2) ?? "-", color: "text-purple-400", icon: Award },
                { label: "Max Drawdown", val: `${(backtestDetail.max_drawdown * 100).toFixed(1)}%`, color: "text-rose-400", icon: AlertTriangle },
                { label: "Trade Fills Count", val: backtestDetail.metrics?.trade_metrics?.total_trades ?? "-", color: "text-blue-400", icon: Clock },
              ].map((m, i) => (
                <div key={i} className="glass-panel p-4 rounded-xl shadow flex items-center justify-between">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-slate-500">{m.label}</span>
                    <h3 className={`text-xl font-bold font-mono mt-1 ${m.color}`}>{m.val}</h3>
                  </div>
                  <m.icon className="w-5 h-5 text-slate-600/70" />
                </div>
              ))}
            </div>

            {/* Results Studio Card */}
            <div className="glass-panel rounded-xl overflow-hidden shadow-2xl flex flex-col border border-slate-800/80 bg-[#0B0F19]/40">
              {/* Tabs selector */}
              <div className="px-5 py-3 border-b border-slate-800 bg-slate-950/20 flex flex-wrap items-center justify-between gap-3">
                <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-850">
                  <button
                    onClick={() => setActiveResultsTab("replay")}
                    className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                      activeResultsTab === "replay"
                        ? "bg-slate-850 text-blue-400 shadow-sm"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Replay Studio
                  </button>
                  <button
                    onClick={() => setActiveResultsTab("trades")}
                    className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                      activeResultsTab === "trades"
                        ? "bg-slate-850 text-blue-400 shadow-sm"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Trade Log ({backtestDetail.metrics?.trades?.length || 0})
                  </button>
                  <button
                    onClick={() => setActiveResultsTab("metrics")}
                    className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                      activeResultsTab === "metrics"
                        ? "bg-slate-850 text-blue-400 shadow-sm"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Analysis Summary
                  </button>
                </div>

                <div className="text-[10px] text-slate-500 font-bold uppercase font-mono">
                  Strategy: {backtestDetail.strategy_name}
                </div>
              </div>

              {/* Tab: Replay Studio */}
              {activeResultsTab === "replay" && (
                <div className="p-5 space-y-5">
                  {/* Playback HUD Bar */}
                  <div className="flex flex-wrap items-center justify-between gap-4 p-3 bg-slate-950/80 border border-slate-850 rounded-xl">
                    <div className="flex items-center gap-1.5">
                      <button onClick={() => setCurrentStep(0)} className="p-1.5 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 rounded transition-colors"><SkipBack size={12} /></button>
                      <button
                        onClick={() => setIsPlaying(!isPlaying)}
                        className={`p-2 rounded text-white transition-all ${isPlaying ? "bg-amber-600 hover:bg-amber-700" : "bg-emerald-600 hover:bg-emerald-700"}`}
                      >
                        {isPlaying ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" />}
                      </button>
                      <button onClick={() => setCurrentStep((prev: number) => Math.min(replayEvents.length - 1, prev + 1))} className="p-1.5 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 rounded transition-colors"><SkipForward size={12} /></button>
                    </div>

                    <div className="flex items-center gap-1">
                      {[1, 2, 5, 10].map(speed => (
                        <button key={speed} onClick={() => setPlaybackSpeed(speed)} className={`px-2 py-0.5 rounded text-[9px] font-bold border transition-all ${playbackSpeed === speed ? "bg-blue-600/20 border-blue-500 text-blue-400" : "border-slate-850 text-slate-500 hover:bg-slate-900"}`}>
                          {speed}x
                        </button>
                      ))}
                    </div>

                    {/* Timeline slider */}
                    <div className="flex-1 min-w-[200px] flex items-center gap-3">
                      <input
                        type="range"
                        min={0}
                        max={replayEvents.length > 0 ? replayEvents.length - 1 : 0}
                        value={currentStep}
                        onChange={e => setCurrentStep(Number(e.target.value))}
                        className="w-full accent-blue-500 cursor-pointer"
                      />
                      <span className="text-[10px] font-mono text-slate-400 whitespace-nowrap bg-slate-900 px-2 py-0.5 rounded border border-slate-800">{currentStep} / {replayEvents.length - 1}</span>
                    </div>

                    {/* Active timestamp info */}
                    <div className="text-[10px] font-mono text-slate-350 bg-blue-950/30 border border-blue-900/50 px-2 py-1 rounded">
                      Time: {currentEvent?.timestamp?.split(" ")[1] || "--:--:--"}
                    </div>
                  </div>

                  {/* Chart controls & Lightweight Candlestick Chart */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between px-1 flex-wrap gap-2 border-b border-slate-850/60 pb-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] text-slate-500 font-bold uppercase">EMA Channels:</span>
                        <button onClick={() => setShowEmaFast(!showEmaFast)} className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${showEmaFast ? "bg-blue-600/10 border-blue-500 text-blue-400" : "border-slate-850 text-slate-500 hover:bg-slate-900"}`}>EMA Fast (9)</button>
                        <button onClick={() => setShowEmaSlow(!showEmaSlow)} className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${showEmaSlow ? "bg-amber-600/10 border-amber-500 text-amber-400" : "border-slate-850 text-slate-500 hover:bg-slate-900"}`}>EMA Slow (21)</button>
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] text-slate-500 font-bold uppercase">Trades:</span>
                        <button onClick={() => setShowBuyTrades(!showBuyTrades)} className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${showBuyTrades ? "bg-emerald-600/10 border-emerald-500 text-emerald-400" : "border-slate-850 text-slate-500 hover:bg-slate-900"}`}>BUY Markers</button>
                        <button onClick={() => setShowSellTrades(!showSellTrades)} className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${showSellTrades ? "bg-rose-600/10 border-rose-500 text-rose-400" : "border-slate-850 text-slate-500 hover:bg-slate-900"}`}>SELL Markers</button>
                      </div>
                    </div>

                    <div className="relative">
                      {activeCandles.length > 0 ? (
                        <LightweightChart
                          candles={activeCandles}
                          trades={activeTrades}
                          showEmaFast={showEmaFast}
                          showEmaSlow={showEmaSlow}
                          showBuyTrades={showBuyTrades}
                          showSellTrades={showSellTrades}
                          height={360}
                        />
                      ) : (
                        <div className="w-full h-80 bg-slate-950/60 rounded-xl border border-slate-800 flex flex-col items-center justify-center text-slate-500">
                          <AlertTriangle size={32} className="text-slate-600 mb-2 animate-bounce" />
                          <span className="text-xs">No active replay data loaded.</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Exposure Curve and Positions HUD */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                    {/* Exposure Chart */}
                    <div className="lg:col-span-2 border border-slate-800/80 rounded-xl overflow-hidden bg-slate-950/20">
                      <div className="px-4 py-2 bg-slate-950/60 border-b border-slate-850 text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between">
                        <span>Net Position Exposure</span>
                        <span className="font-mono text-blue-400">{currentPortfolio?.positions ? Object.keys(currentPortfolio.positions).length : 0} Assets</span>
                      </div>
                      <PositionChart data={positionCurveData} height={130} />
                    </div>

                    {/* Positions Details List */}
                    <div className="border border-slate-800/80 rounded-xl overflow-hidden bg-slate-950/20 flex flex-col">
                      <div className="px-4 py-2 bg-slate-950/60 border-b border-slate-850 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        Open Positions HUD
                      </div>
                      <div className="flex-1 p-3 overflow-y-auto space-y-2 max-h-[130px] custom-scrollbar">
                        {currentPortfolio?.positions && Object.keys(currentPortfolio.positions).length > 0 ? (
                          Object.values(currentPortfolio.positions).map((pos: any) => (
                            <div key={pos.symbol} className="flex justify-between items-center text-[11px] border border-slate-850 rounded-lg p-2 bg-slate-950/60">
                              <div>
                                <span className="font-bold text-slate-200">{pos.symbol}</span>
                                <div className="text-[9px] text-slate-500 mt-0.5">
                                  {pos.qty > 0 ? "LONG" : pos.qty < 0 ? "SHORT" : "FLAT"} {Math.abs(pos.qty)} @ ₹{pos.avg_price?.toFixed(1) || "-"}
                                </div>
                              </div>
                              <span className={`font-mono font-bold ${pos.unrealized_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                                PnL: ₹{pos.unrealized_pnl?.toFixed(1) || "0.0"}
                              </span>
                            </div>
                          ))
                        ) : (
                          <div className="text-[10px] text-slate-500 text-center py-8 font-medium">No open positions at this step.</div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab: Trade Log */}
              {activeResultsTab === "trades" && (
                <div className="p-5">
                  <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/20 max-h-[480px] custom-scrollbar">
                    <table className="w-full text-xs text-left">
                      <thead>
                        <tr className="bg-slate-900 border-b border-slate-800 text-slate-300 font-semibold sticky top-0 shadow">
                          <th className="p-3">Timestamp</th>
                          <th className="p-3">Symbol</th>
                          <th className="p-3">Direction</th>
                          <th className="p-3 text-right">Quantity</th>
                          <th className="p-3 text-right">Execution Price (₹)</th>
                          <th className="p-3 text-right">Value (₹)</th>
                          <th className="p-3 text-right">Commission & Taxes (₹)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/40 font-mono">
                        {(!backtestDetail.metrics?.trades || backtestDetail.metrics.trades.length === 0) ? (
                          <tr>
                            <td colSpan={7} className="p-8 text-center text-slate-500 font-medium">No trades recorded.</td>
                          </tr>
                        ) : (
                          backtestDetail.metrics.trades.map((t: any, i: number) => (
                            <tr key={i} className="hover:bg-slate-900/30">
                              <td className="p-3 text-slate-500">{t.timestamp}</td>
                              <td className="p-3 font-bold text-slate-200">{t.symbol}</td>
                              <td className="p-3">
                                <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                                  t.direction === "BUY" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-950" : "bg-red-500/10 text-red-400 border border-red-950"
                                }`}>
                                  {t.direction}
                                </span>
                              </td>
                              <td className="p-3 text-right">{t.qty}</td>
                              <td className="p-3 text-right">₹{Number(t.price).toFixed(2)}</td>
                              <td className="p-3 text-right text-slate-350">₹{Number(t.qty * t.price).toFixed(2)}</td>
                              <td className="p-3 text-right text-amber-500 font-bold">₹{Number(t.total_charges || 0).toFixed(2)}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Tab: Metrics summary */}
              {activeResultsTab === "metrics" && (
                <div className="p-5 grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* Performance Indicators */}
                  <div className="glass-panel p-4 rounded-xl space-y-3 bg-slate-950/20">
                    <h5 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <TrendingUp className="w-4 h-4 text-emerald-400" />
                      Key Performance Ratios
                    </h5>
                    {[
                      { label: "CAGR / Annual Return", val: `${(backtestDetail.cagr * 100).toFixed(2)}%`, desc: "Compounded annualized growth rate" },
                      { label: "Sharpe Ratio", val: backtestDetail.sharpe_ratio?.toFixed(2) ?? "-", desc: "Risk-adjusted return vs volatility" },
                      { label: "Sortino Ratio", val: backtestDetail.sortino_ratio?.toFixed(2) ?? "-", desc: "Risk-adjusted return vs downside risk" },
                      { label: "Max Drawdown", val: `${(backtestDetail.max_drawdown * 100).toFixed(2)}%`, desc: "Peak-to-trough decline limit" },
                    ].map((row, i) => (
                      <div key={i} className="py-2 border-b border-slate-800/40 last:border-0">
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-slate-400">{row.label}</span>
                          <span className="font-bold text-slate-200 font-mono">{row.val}</span>
                        </div>
                        <p className="text-[9px] text-slate-500 mt-0.5">{row.desc}</p>
                      </div>
                    ))}
                  </div>

                  {/* Trade Analysis Statistics */}
                  <div className="glass-panel p-4 rounded-xl space-y-3 bg-slate-950/20">
                    <h5 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <Clock className="w-4 h-4 text-blue-400" />
                      Trade Execution Summary
                    </h5>
                    {[
                      { label: "Win Rate", val: `${(backtestDetail.win_rate * 100).toFixed(1)}%`, desc: "Percentage of profitable trades" },
                      { label: "Profit Factor", val: backtestDetail.profit_factor?.toFixed(2) ?? "-", desc: "Gross profits divided by gross losses" },
                      { label: "Initial Capital", val: `₹${backtestDetail.initial_capital?.toLocaleString()}`, desc: "Starting simulation pool" },
                      { label: "Final Equity Value", val: `₹${backtestDetail.final_equity?.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, desc: "Resulting account valuation" },
                    ].map((row, i) => (
                      <div key={i} className="py-2 border-b border-slate-800/40 last:border-0">
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-slate-400">{row.label}</span>
                          <span className="font-bold text-slate-200 font-mono">{row.val}</span>
                        </div>
                        <p className="text-[9px] text-slate-500 mt-0.5">{row.desc}</p>
                      </div>
                    ))}
                  </div>

                  {/* Portfolio Drag & Expenses */}
                  <div className="glass-panel p-4 rounded-xl space-y-3 bg-slate-950/20">
                    <h5 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <DollarSign className="w-4 h-4 text-amber-500" />
                      Frictional Drag Breakdown
                    </h5>
                    {[
                      { label: "Total Simulation Fees", val: `₹${backtestDetail.total_fees?.toFixed(2)}`, desc: "Combined brokerage, taxes & stamp duty" },
                      { label: "Calculated PnL (Net)", val: `₹${backtestDetail.total_pnl?.toFixed(2)}`, desc: "Final absolute gains after expenses" },
                      { label: "Max Position Limit", val: `${backtestDetail.max_position_size || "No limit specified"}`, desc: "Risk boundaries applied on execution" },
                      { label: "Slippage Applied", val: `${btSlippage}%`, desc: "Simulated market slippage percentage" },
                    ].map((row, i) => (
                      <div key={i} className="py-2 border-b border-slate-800/40 last:border-0">
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-slate-400">{row.label}</span>
                          <span className="font-bold text-slate-200 font-mono">{row.val}</span>
                        </div>
                        <p className="text-[9px] text-slate-500 mt-0.5">{row.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="glass-panel p-16 text-center text-slate-500 rounded-xl flex-1 flex flex-col items-center justify-center border border-slate-850">
            <PlayCircle size={40} className="mb-3 text-slate-700 animate-pulse" />
            <span className="text-sm font-semibold">Ready for Backtest Simulation</span>
            <p className="text-xs text-slate-450 mt-1 max-w-sm">Select a strategy from the sidebar, configure dates/execution type, and hit run to display historical results.</p>
          </div>
        )}
      </div>
    </div>
  );
}
