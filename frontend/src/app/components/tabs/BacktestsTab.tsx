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
const PnLChart = dynamic(() => import("../../../components/PnLChart"), { ssr: false });
const DailyPnLHeatmap = dynamic(() => import("../DailyPnLHeatmap"), { ssr: false });

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
  activeCandles, activeTrades, positionCurveData, pnlCurveData,
  datasets, checkDataCoverage, pendingBacktest, setPendingBacktest,
}: any) {
  const [activeResultsTab, setActiveResultsTab] = useState<"replay" | "trades" | "metrics" | "calendar">("replay");

  const selectedStrategy = strategies.find((s: any) => s.id === selectedStrategyId);
  const symbols = selectedStrategy?.symbols || [selectedStrategy?.symbol || "NSE:SBIN-EQ"];
  const interval = selectedStrategy?.interval || "FIVE_MINUTE";

  const coverage = useMemo(() => {
    if (!selectedStrategyId) return { missing: [], available: [] as any[] };
    return {
      missing: checkDataCoverage(symbols, interval, btStartDate, btEndDate),
      available: symbols.map((sym: string) => {
        const symBase = sym.toUpperCase().trim().includes(":") ? sym.toUpperCase().trim().split(":")[1].replace(/-EQ$|-BE$/i, "") : sym.toUpperCase().trim().replace(/-EQ$|-BE$/i, "");
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
      <div className="xl:col-span-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5 space-y-5 flex flex-col justify-between self-start">
        <div className="space-y-4">
          <h4 className="text-[11px] font-medium text-[#606060] uppercase tracking-wider flex items-center gap-2 border-b border-[#2a2a2a] pb-3">
            <Sliders className="w-4 h-4 text-[#93b4ff]" />
            Backtest Configurations
          </h4>

          {/* Run Config Card */}
          <div className="bg-[#161616] border border-[#2a2a2a] rounded-xl p-4 space-y-3">
            <div>
              <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Target Strategy</label>
              <select
                value={selectedStrategyId}
                onChange={e => handleSelectStrategy(e.target.value)}
                className="w-full text-[12px] bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-3 py-2 text-[#c0c0c0] focus:outline-none focus:border-[#4a7fcc] font-medium"
              >
                <option value="">-- Select Strategy --</option>
                {strategies.map((s: any) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2 flex items-center gap-1">
                  <Calendar size={10} className="text-[#93b4ff]" /> From
                </label>
                <input
                  type="date"
                  value={btStartDate}
                  onChange={e => setBtStartDate(e.target.value)}
                  className={`text-[12px] bg-[#1a1a1a] border rounded-lg px-3 py-2 text-[#c0c0c0] w-full focus:outline-none ${
                    !isDateRangeValid && coverage.missing.some((m: any) => btStartDate < m.startDate)
                      ? 'border-red-700 focus:border-red-500'
                      : 'border-[#2a2a2a] focus:border-[#4a7fcc]'
                  }`}
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2 flex items-center gap-1">
                  <Calendar size={10} className="text-[#93b4ff]" /> To
                </label>
                <input
                  type="date"
                  value={btEndDate}
                  onChange={e => setBtEndDate(e.target.value)}
                  className={`text-[12px] bg-[#1a1a1a] border rounded-lg px-3 py-2 text-[#c0c0c0] w-full focus:outline-none ${
                    !isDateRangeValid && coverage.missing.some((m: any) => btEndDate > m.endDate)
                      ? 'border-red-700 focus:border-red-500'
                      : 'border-[#2a2a2a] focus:border-[#4a7fcc]'
                  }`}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Slippage %</label>
                <input
                  type="number"
                  step="0.01"
                  value={btSlippage}
                  onChange={e => setBtSlippage(Number(e.target.value))}
                  className="w-full text-[12px] bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-3 py-2 text-[#c0c0c0] font-medium font-mono focus:outline-none focus:border-[#4a7fcc]"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Max Position</label>
                <input
                  type="number"
                  value={btMaxPositionSize || ""}
                  onChange={e => setBtMaxPositionSize(e.target.value ? parseInt(e.target.value) : null)}
                  placeholder="Auto"
                  className="w-full text-[12px] bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-3 py-2 text-[#c0c0c0] font-medium font-mono focus:outline-none focus:border-[#4a7fcc]"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Trade Mode</label>
              <div className="grid grid-cols-2 gap-1.5">
                {["INTRADAY", "DELIVERY", "FUTURES", "OPTIONS"].map(t => (
                  <button
                    key={t}
                    onClick={() => setBtTradeType(t)}
                    className={`px-1 py-1.5 text-[10px] font-medium border rounded-lg transition-all ${
                      btTradeType === t
                        ? "bg-[#1c2030] border-[#4a7fcc] text-[#93b4ff]"
                        : "border-[#2a2a2a] text-[#a0a0a0] bg-[#1a1a1a] hover:bg-[#1e1e1e]"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Data Validation Notification Cards */}
        {selectedStrategyId && (
          <div className="space-y-2 pt-2">
            {coverage.missing.length > 0 && (
              <div className="bg-[#1a0d0d] border border-[#3a1515] rounded-lg px-4 py-3 flex items-start gap-3 text-[12px] text-[#c0c0c0]">
                <XCircle size={14} className="shrink-0 mt-0.5 text-red-400" />
                <div className="flex-1">
                  <p className="font-medium mb-1 text-red-400">Missing Coverage Period:</p>
                  {coverage.missing.map((m: any, i: number) => (
                    <p key={i} className="text-red-300/80">{m.symbol}: {m.reason}</p>
                  ))}
                  <p className="text-[11px] text-red-300/50 mt-1.5 italic">Will auto-download from SmartAPI on backtest run.</p>
                </div>
              </div>
            )}
            {coverage.available.length > 0 && coverage.missing.length === 0 && (
              <div className="bg-[#0d1a10] border border-[#1a3a20] rounded-lg px-4 py-3 flex items-start gap-3 text-[12px] text-[#c0c0c0]">
                <CheckCircle2 size={13} className="shrink-0 mt-0.5 text-emerald-400" />
                <span className="text-emerald-300/80">Historical data cached and verified locally for backtest parameters.</span>
              </div>
            )}
            {coverage.available.length === 0 && coverage.missing.length === 0 && (
              <div className="bg-[#0f1520] border border-[#1e2d4a] rounded-lg px-4 py-3 flex items-start gap-3 text-[12px] text-[#c0c0c0]">
                <Database size={13} className="shrink-0 mt-0.5 text-[#93b4ff]" />
                <span className="text-[#93b4ff]/80">No local cache folders found for {symbols.join(", ")}. Missing candles will be downloaded.</span>
              </div>
            )}
          </div>
        )}

        <button
          onClick={handleRunBacktest}
          disabled={!selectedStrategyId}
          className="w-full mt-2 bg-[#1c2030] hover:bg-[#222d40] disabled:bg-[#161616] disabled:text-[#606060] text-[#93b4ff] border border-[#2a3a5a] rounded-xl font-medium text-[12px] py-2.5 transition-all flex items-center justify-center gap-2"
        >
          <PlayCircle size={14} fill="currentColor" /> Run Simulation Engine
        </button>
      </div>

      {/* Main Results View */}
      <div className="xl:col-span-3 h-full flex flex-col gap-6">
        {backtestDetail ? (
          <>
            {/* Metrics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {/* Net Profit */}
              <div className="bg-[#1a1a1a] border border-[#2a2a2a] border-l-[3px] border-l-emerald-500 rounded-r-xl rounded-l-none p-4 flex flex-col justify-between">
                <div>
                  <div className="text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Net Profit</div>
                  <div className={`text-[22px] font-semibold text-[#f0f0f0] leading-none ${backtestDetail.total_pnl > 0 ? "text-emerald-400" : backtestDetail.total_pnl < 0 ? "text-red-400" : ""}`}>
                    ₹{backtestDetail.total_pnl?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? "0"}
                  </div>
                </div>
                {pnlCurveData.length > 0 && (() => {
                  const finalValues = pnlCurveData[pnlCurveData.length - 1].values;
                  const symbols = Object.keys(finalValues);
                  if (symbols.length <= 1) return null;
                  return (
                    <div className="mt-2 pt-2 border-t border-[#2a2a2a]/50 space-y-1">
                      {symbols.map((sym) => {
                        const val = finalValues[sym] || 0;
                        const hasTrade = val !== 0 || backtestDetail.trades?.some((t: any) => t.symbol === sym);
                        return (
                          <div key={sym} className="flex items-center justify-between text-[10px] font-mono">
                            <span className="text-[#a0a0a0]">{sym}</span>
                            <span className={val > 0 ? "text-emerald-400" : val < 0 ? "text-red-400" : !hasTrade ? "text-orange-400" : "text-[#505050]"}>
                              ₹{val.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}
                <div className={`text-[11px] mt-1.5 ${backtestDetail.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  Return: {(((backtestDetail.final_equity - backtestDetail.initial_capital) / backtestDetail.initial_capital) * 100).toFixed(1)}%
                </div>
              </div>

              {/* Sharpe */}
              <div className="bg-[#1a1a1a] border border-[#2a2a2a] border-l-[3px] border-l-[#4a7fcc] rounded-r-xl rounded-l-none p-4">
                <div className="text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Sharpe Ratio</div>
                <div className="text-[22px] font-semibold text-[#f0f0f0] leading-none">{backtestDetail.sharpe_ratio?.toFixed(2) ?? "-"}</div>
                <div className="text-[11px] mt-1.5 text-[#93b4ff]">Risk-adjusted return</div>
              </div>

              {/* Max Drawdown */}
              <div className="bg-[#1a1a1a] border border-[#2a2a2a] border-l-[3px] border-l-red-500 rounded-r-xl rounded-l-none p-4">
                <div className="text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Max Drawdown</div>
                <div className="text-[22px] font-semibold text-[#f0f0f0] leading-none text-red-400">{(backtestDetail.max_drawdown * 100).toFixed(1)}%</div>
                <div className="text-[11px] mt-1.5 text-red-400">Peak-to-trough decline</div>
              </div>

              {/* Win Rate */}
              <div className="bg-[#1a1a1a] border border-[#2a2a2a] border-l-[3px] border-l-[#4a7fcc] rounded-r-xl rounded-l-none p-4">
                <div className="text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Win Rate</div>
                <div className="text-[22px] font-semibold text-[#f0f0f0] leading-none">{(backtestDetail.win_rate * 100).toFixed(1)}%</div>
                <div className="text-[11px] mt-1.5 text-[#93b4ff]">Profitable trades</div>
              </div>
            </div>

            {/* Results Studio Card */}
            <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl overflow-hidden flex flex-col">
              {/* Tabs selector */}
              <div className="px-5 py-3 border-b border-[#2a2a2a] bg-[#161616] flex flex-wrap items-center justify-between gap-3">
                <div className="flex bg-[#1a1a1a] p-1 rounded-lg border border-[#2a2a2a]">
                  <button
                    onClick={() => setActiveResultsTab("replay")}
                    className={`px-3 py-1.5 rounded-md text-[12px] font-medium transition-all ${
                      activeResultsTab === "replay"
                        ? "bg-[#222] text-[#93b4ff]"
                        : "text-[#a0a0a0] hover:text-[#c0c0c0]"
                    }`}
                  >
                    Replay Studio
                  </button>
                  <button
                    onClick={() => setActiveResultsTab("trades")}
                    className={`px-3 py-1.5 rounded-md text-[12px] font-medium transition-all ${
                      activeResultsTab === "trades"
                        ? "bg-[#222] text-[#93b4ff]"
                        : "text-[#a0a0a0] hover:text-[#c0c0c0]"
                    }`}
                  >
                    Trade Log ({backtestDetail.metrics?.trades?.length || 0})
                  </button>
                  <button
                    onClick={() => setActiveResultsTab("metrics")}
                    className={`px-3 py-1.5 rounded-md text-[12px] font-medium transition-all ${
                      activeResultsTab === "metrics"
                        ? "bg-[#222] text-[#93b4ff]"
                        : "text-[#a0a0a0] hover:text-[#c0c0c0]"
                    }`}
                  >
                    Analysis Summary
                  </button>
                  <button
                    onClick={() => setActiveResultsTab("calendar")}
                    className={`px-3 py-1.5 rounded-md text-[12px] font-medium transition-all ${
                      activeResultsTab === "calendar"
                        ? "bg-[#222] text-[#93b4ff]"
                        : "text-[#a0a0a0] hover:text-[#c0c0c0]"
                    }`}
                  >
                    Calendar
                  </button>
                </div>

                <div className="text-[10px] text-[#606060] font-medium uppercase font-mono">
                  Strategy: {backtestDetail.strategy_name}
                </div>
              </div>

              {/* Tab: Replay Studio */}
              {activeResultsTab === "replay" && (
                <div className="p-5 space-y-5">
                  {/* Playback HUD Bar */}
                  <div className="flex flex-wrap items-center justify-between gap-4 p-3 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl">
                    <div className="flex items-center gap-1.5">
                      <button onClick={() => setCurrentStep(0)} className="p-1.5 bg-[#222] border border-[#2a2a2a] hover:bg-[#2a2a2a] text-[#a0a0a0] rounded-lg transition-colors"><SkipBack size={12} /></button>
                      <button
                        onClick={() => setIsPlaying(!isPlaying)}
                        className={`p-2 rounded-lg text-[#f0f0f0] transition-all ${isPlaying ? "bg-amber-600 hover:bg-amber-700" : "bg-emerald-600 hover:bg-emerald-700"}`}
                      >
                        {isPlaying ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" />}
                      </button>
                      <button onClick={() => setCurrentStep((prev: number) => Math.min(replayEvents.length - 1, prev + 1))} className="p-1.5 bg-[#222] border border-[#2a2a2a] hover:bg-[#2a2a2a] text-[#a0a0a0] rounded-lg transition-colors"><SkipForward size={12} /></button>
                    </div>

                    <div className="flex items-center gap-1">
                      {[1, 2, 5, 10].map(speed => (
                        <button key={speed} onClick={() => setPlaybackSpeed(speed)} className={`px-2 py-0.5 rounded text-[10px] font-medium border transition-all ${playbackSpeed === speed ? "bg-[#1c2030] border-[#4a7fcc] text-[#93b4ff]" : "border-[#2a2a2a] text-[#505050] hover:bg-[#222]"}`}>
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
                      <span className="text-[10px] font-mono text-[#a0a0a0] whitespace-nowrap bg-[#222] px-2 py-0.5 rounded border border-[#2a2a2a]">{currentStep} / {replayEvents.length - 1}</span>
                    </div>

                    {/* Active timestamp info */}
                    <div className="text-[10px] font-mono text-[#888] bg-[#1a1a1a] border border-[#2a3a5a]/50 px-2 py-1 rounded-lg">
                      Time: {currentEvent?.timestamp?.split(" ")[1] || "--:--:--"}
                    </div>
                  </div>

                  {/* Chart controls & Lightweight Candlestick Chart */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between px-1 flex-wrap gap-2 border-b border-[#2a2a2a]/60 pb-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] text-[#505050] font-medium uppercase">EMA Channels:</span>
                        <button onClick={() => setShowEmaFast(!showEmaFast)} className={`px-2 py-0.5 rounded text-[10px] font-medium border transition-all ${showEmaFast ? "bg-[#1c2030] border-[#4a7fcc] text-[#93b4ff]" : "border-[#2a2a2a] text-[#505050] hover:bg-[#222]"}`}>EMA Fast (9)</button>
                        <button onClick={() => setShowEmaSlow(!showEmaSlow)} className={`px-2 py-0.5 rounded text-[10px] font-medium border transition-all ${showEmaSlow ? "bg-amber-600/10 border-amber-500 text-amber-400" : "border-[#2a2a2a] text-[#505050] hover:bg-[#222]"}`}>EMA Slow (21)</button>
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] text-[#505050] font-medium uppercase">Trades:</span>
                        <button onClick={() => setShowBuyTrades(!showBuyTrades)} className={`px-2 py-0.5 rounded text-[10px] font-medium border transition-all ${showBuyTrades ? "bg-emerald-600/10 border-emerald-500 text-emerald-400" : "border-[#2a2a2a] text-[#505050] hover:bg-[#222]"}`}>BUY Markers</button>
                        <button onClick={() => setShowSellTrades(!showSellTrades)} className={`px-2 py-0.5 rounded text-[10px] font-medium border transition-all ${showSellTrades ? "bg-red-500/10 border-red-500 text-red-400" : "border-[#2a2a2a] text-[#505050] hover:bg-[#222]"}`}>SELL Markers</button>
                      </div>
                    </div>

                    <div className="relative bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
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
                        <div className="w-full h-80 bg-[#161616] rounded-xl border border-[#2a2a2a] flex flex-col items-center justify-center text-[#505050]">
                          <AlertTriangle size={32} className="text-[#505050] mb-2 animate-bounce" />
                          <span className="text-[13px]">No active replay data loaded.</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Exposure Curve and Positions HUD */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                    {/* Exposure Chart */}
                    <div className="lg:col-span-2 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl overflow-hidden">
                      <div className="px-4 py-2 bg-[#161616] border-b border-[#2a2a2a] text-[10px] font-medium uppercase tracking-wider text-[#606060] flex items-center justify-between">
                        <span>Net Position Exposure</span>
                        <span className="font-mono text-[#93b4ff]">{currentPortfolio?.positions ? Object.keys(currentPortfolio.positions).length : 0} Assets</span>
                      </div>
                      <PositionChart data={positionCurveData} height={130} />
                    </div>

                    {/* Positions Details List */}
                    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl overflow-hidden flex flex-col">
                      <div className="px-4 py-2 bg-[#161616] border-b border-[#2a2a2a] text-[10px] font-medium uppercase tracking-wider text-[#606060]">
                        Open Positions HUD
                      </div>
                      <div className="flex-1 p-3 overflow-y-auto space-y-2 max-h-[130px] custom-scrollbar">
                        {currentPortfolio?.positions && Object.keys(currentPortfolio.positions).length > 0 ? (
                          Object.values(currentPortfolio.positions).map((pos: any) => (
                            <div key={pos.symbol} className="flex justify-between items-center text-[11px] border border-[#2a2a2a] rounded-lg p-2 bg-[#161616]">
                              <div>
                                <span className="font-medium text-[#d0d0d0]">{pos.symbol}</span>
                                <div className="text-[10px] text-[#505050] mt-0.5">
                                  {pos.qty > 0 ? "LONG" : pos.qty < 0 ? "SHORT" : "FLAT"} {Math.abs(pos.qty)} @ ₹{pos.avg_price?.toFixed(1) || "-"}
                                </div>
                              </div>
                              <span className={`font-mono font-medium ${pos.unrealized_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                                PnL: ₹{pos.unrealized_pnl?.toFixed(1) || "0.0"}
                              </span>
                            </div>
                          ))
                        ) : (
                          <div className="text-[11px] text-[#505050] text-center py-8 font-medium">No open positions at this step.</div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Per-Symbol PnL Chart */}
                  <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl overflow-hidden">
                    <div className="px-4 py-2 bg-[#161616] border-b border-[#2a2a2a] text-[10px] font-medium uppercase tracking-wider text-[#606060] flex items-center justify-between">
                      <span>Per-Symbol PnL Curve</span>
                      <span className="font-mono text-[#505050]">Realized + Unrealized</span>
                    </div>
                    <PnLChart data={pnlCurveData} height={180} title="" />
                  </div>
                </div>
              )}

              {/* Tab: Trade Log */}
              {activeResultsTab === "trades" && (
                <div className="p-5">
                  <div className="overflow-x-auto rounded-xl border border-[#2a2a2a] bg-[#1a1a1a] max-h-[480px] custom-scrollbar">
                    <table className="w-full text-left">
                      <thead>
                        <tr className="bg-[#161616] border-b border-[#222]">
                          <th className="p-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider">Timestamp</th>
                          <th className="p-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider">Symbol</th>
                          <th className="p-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider">Direction</th>
                          <th className="p-3 text-right text-[11px] font-medium text-[#606060] uppercase tracking-wider">Quantity</th>
                          <th className="p-3 text-right text-[11px] font-medium text-[#606060] uppercase tracking-wider">Price (₹)</th>
                          <th className="p-3 text-right text-[11px] font-medium text-[#606060] uppercase tracking-wider">Value (₹)</th>
                          <th className="p-3 text-right text-[11px] font-medium text-[#606060] uppercase tracking-wider">Fees (₹)</th>
                        </tr>
                      </thead>
                      <tbody className="font-mono">
                        {(!backtestDetail.metrics?.trades || backtestDetail.metrics.trades.length === 0) ? (
                          <tr className="bg-[#1a1a1a]">
                            <td colSpan={7} className="p-8 text-center text-[12px] text-[#505050] font-medium">No trades recorded.</td>
                          </tr>
                        ) : (
                          backtestDetail.metrics.trades.map((t: any, i: number) => (
                            <tr key={i} className="bg-[#1a1a1a] border-b border-[#222] hover:bg-[#1e1e1e]">
                              <td className="p-3 text-[12px] text-[#c0c0c0]">{t.timestamp}</td>
                              <td className="p-3 text-[12px] font-medium text-[#d0d0d0]">{t.symbol}</td>
                              <td className="p-3">
                                <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium uppercase ${
                                  t.direction === "BUY" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-900" : "bg-red-500/10 text-red-400 border border-red-900"
                                }`}>
                                  {t.direction}
                                </span>
                              </td>
                              <td className="p-3 text-right text-[12px] text-[#c0c0c0]">{t.qty}</td>
                              <td className="p-3 text-right text-[12px] text-[#c0c0c0]">₹{Number(t.price).toFixed(2)}</td>
                              <td className="p-3 text-right text-[12px] text-[#c0c0c0]">₹{Number(t.qty * t.price).toFixed(2)}</td>
                              <td className="p-3 text-right text-[12px] text-amber-400 font-medium">₹{Number(t.total_charges || 0).toFixed(2)}</td>
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
                  <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 space-y-3">
                    <h5 className="text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <TrendingUp className="w-4 h-4 text-emerald-400" />
                      Key Performance Ratios
                    </h5>
                    {[
                      { label: "CAGR / Annual Return", val: `${(backtestDetail.cagr * 100).toFixed(2)}%`, desc: "Compounded annualized growth rate" },
                      { label: "Sharpe Ratio", val: backtestDetail.sharpe_ratio?.toFixed(2) ?? "-", desc: "Risk-adjusted return vs volatility" },
                      { label: "Sortino Ratio", val: backtestDetail.sortino_ratio?.toFixed(2) ?? "-", desc: "Risk-adjusted return vs downside risk" },
                      { label: "Max Drawdown", val: `${(backtestDetail.max_drawdown * 100).toFixed(2)}%`, desc: "Peak-to-trough decline limit" },
                    ].map((row, i) => (
                      <div key={i} className="py-2 border-b border-[#2a2a2a]/40 last:border-0">
                        <div className="flex justify-between items-center text-[12px]">
                          <span className="text-[#a0a0a0]">{row.label}</span>
                          <span className="font-medium text-[#d0d0d0] font-mono">{row.val}</span>
                        </div>
                        <p className="text-[10px] text-[#505050] mt-0.5">{row.desc}</p>
                      </div>
                    ))}
                  </div>

                  {/* Trade Analysis Statistics */}
                  <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 space-y-3">
                    <h5 className="text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <Clock className="w-4 h-4 text-[#93b4ff]" />
                      Trade Execution Summary
                    </h5>
                    {[
                      { label: "Win Rate", val: `${(backtestDetail.win_rate * 100).toFixed(1)}%`, desc: "Percentage of profitable trades" },
                      { label: "Profit Factor", val: backtestDetail.profit_factor?.toFixed(2) ?? "-", desc: "Gross profits divided by gross losses" },
                      { label: "Initial Capital", val: `₹${backtestDetail.initial_capital?.toLocaleString()}`, desc: "Starting simulation pool" },
                      { label: "Final Equity Value", val: `₹${backtestDetail.final_equity?.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, desc: "Resulting account valuation" },
                    ].map((row, i) => (
                      <div key={i} className="py-2 border-b border-[#2a2a2a]/40 last:border-0">
                        <div className="flex justify-between items-center text-[12px]">
                          <span className="text-[#a0a0a0]">{row.label}</span>
                          <span className="font-medium text-[#d0d0d0] font-mono">{row.val}</span>
                        </div>
                        <p className="text-[10px] text-[#505050] mt-0.5">{row.desc}</p>
                      </div>
                    ))}
                  </div>

                  {/* Portfolio Drag & Expenses */}
                  <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 space-y-3">
                    <h5 className="text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <DollarSign className="w-4 h-4 text-amber-500" />
                      Frictional Drag Breakdown
                    </h5>
                    {[
                      { label: "Total Simulation Fees", val: `₹${backtestDetail.total_fees?.toFixed(2)}`, desc: "Combined brokerage, taxes & stamp duty" },
                      { label: "Calculated PnL (Net)", val: `₹${backtestDetail.total_pnl?.toFixed(2)}`, desc: "Final absolute gains after expenses" },
                      { label: "Max Position Limit", val: `${backtestDetail.max_position_size || "No limit specified"}`, desc: "Risk boundaries applied on execution" },
                      { label: "Slippage Applied", val: `${btSlippage}%`, desc: "Simulated market slippage percentage" },
                    ].map((row, i) => (
                      <div key={i} className="py-2 border-b border-[#2a2a2a]/40 last:border-0">
                        <div className="flex justify-between items-center text-[12px]">
                          <span className="text-[#a0a0a0]">{row.label}</span>
                          <span className="font-medium text-[#d0d0d0] font-mono">{row.val}</span>
                        </div>
                        <p className="text-[10px] text-[#505050] mt-0.5">{row.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {/* Tab: Calendar Heatmap */}
              {activeResultsTab === "calendar" && (
                <div className="p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h5 className="text-[11px] font-medium text-[#606060] uppercase tracking-wider flex items-center gap-1.5">
                      <Calendar className="w-4 h-4 text-[#93b4ff]" />
                      Daily PnL Heatmap
                    </h5>
                    <span className="text-[10px] text-[#505050]">
                      {backtestDetail.start_time?.slice(0, 10)} → {backtestDetail.end_time?.slice(0, 10)}
                    </span>
                  </div>
                  <DailyPnLHeatmap
                    equityCurve={backtestDetail.metrics?.equity_curve}
                    startDate={backtestDetail.start_time?.slice(0, 10)}
                    endDate={backtestDetail.end_time?.slice(0, 10)}
                  />
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-16 text-center text-[#505050] flex-1 flex flex-col items-center justify-center">
            <PlayCircle size={40} className="mb-3 text-[#606060] animate-pulse" />
            <span className="text-[13px] font-medium text-[#d0d0d0]">Ready for Backtest Simulation</span>
            <p className="text-[11px] text-[#a0a0a0] mt-1 max-w-sm">Select a strategy from the sidebar, configure dates/execution type, and hit run to display historical results.</p>
          </div>
        )}
      </div>
    </div>
  );
}
