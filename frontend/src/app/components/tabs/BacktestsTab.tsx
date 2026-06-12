"use client";

import { Play, Pause, SkipForward, SkipBack, AlertTriangle, Layers, PlayCircle } from "lucide-react";
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
}: any) {
  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Run Controls */}
      <div className="glass-panel p-4 rounded-xl">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Strategy</label>
            <select
              value={selectedStrategyId}
              onChange={e => handleSelectStrategy(e.target.value)}
              className="w-56 text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">-- Choose Strategy --</option>
              {strategies.map((s: any) => (
                <option key={s.id} value={s.id}>{s.name} ({(s.symbols || []).join(", ")})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">From</label>
            <input type="date" value={btStartDate} onChange={e => setBtStartDate(e.target.value)} className="text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-slate-200" />
          </div>
          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">To</label>
            <input type="date" value={btEndDate} onChange={e => setBtEndDate(e.target.value)} className="text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-slate-200" />
          </div>
          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Slippage %</label>
            <input type="number" step="0.01" value={btSlippage} onChange={e => setBtSlippage(Number(e.target.value))} className="w-20 text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-slate-200" />
          </div>
          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Trade Type</label>
            <div className="flex gap-1">
              {["INTRADAY", "DELIVERY", "FUTURES"].map(t => (
                <button
                  key={t}
                  onClick={() => setBtTradeType(t)}
                  className={`px-2 py-1 text-[10px] font-bold border rounded transition-all ${btTradeType === t ? "bg-blue-600/15 border-blue-500 text-blue-400" : "border-slate-800 text-slate-400 bg-slate-950/50 hover:bg-slate-900"}`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={handleRunBacktest}
            disabled={!selectedStrategyId}
            className="bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded font-bold text-xs py-2 px-4 transition-all flex items-center gap-2"
          >
            <Play size={14} fill="currentColor" /> Run Backtest
          </button>
        </div>
      </div>

      {/* Results View */}
      {backtestDetail ? (
        <div className="flex flex-col gap-4 flex-1 min-h-0">
          {/* Top Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Return", val: `${(((backtestDetail.final_equity - backtestDetail.initial_capital) / backtestDetail.initial_capital) * 100).toFixed(1)}%`, color: backtestDetail.total_pnl >= 0 ? "text-emerald-400" : "text-rose-400" },
              { label: "Sharpe Ratio", val: backtestDetail.sharpe_ratio?.toFixed(2) ?? "-", color: "text-blue-400" },
              { label: "Max Drawdown", val: `${(backtestDetail.max_drawdown * 100).toFixed(1)}%`, color: "text-rose-400" },
              { label: "Total Trades", val: backtestDetail.metrics?.trade_metrics?.total_trades ?? "-", color: "text-slate-200" },
            ].map((m, i) => (
              <div key={i} className="glass-panel p-4 rounded-xl">
                <span className="text-[10px] uppercase font-bold text-slate-500">{m.label}</span>
                <h3 className={`text-xl font-bold font-mono mt-1 ${m.color}`}>{m.val}</h3>
              </div>
            ))}
          </div>

          {/* Main Chart Area */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">
            {/* Left: Equity Curve + Replay */}
            <div className="lg:col-span-2 flex flex-col gap-3 h-full min-h-0">
              {/* Playback Controls */}
              <div className="glass-panel p-2.5 rounded-xl flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-2">
                  <button onClick={() => setCurrentStep(0)} className="p-1.5 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 rounded"><SkipBack size={12} /></button>
                  <button
                    onClick={() => setIsPlaying(!isPlaying)}
                    className={`p-2 rounded text-white transition-all ${isPlaying ? "bg-amber-600 hover:bg-amber-700" : "bg-emerald-600 hover:bg-emerald-700"}`}
                  >
                    {isPlaying ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" />}
                  </button>
                  <button onClick={() => setCurrentStep((prev: number) => Math.min(replayEvents.length - 1, prev + 1))} className="p-1.5 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 rounded"><SkipForward size={12} /></button>
                </div>
                <div className="flex items-center gap-1">
                  {[1, 2, 5, 10].map(speed => (
                    <button key={speed} onClick={() => setPlaybackSpeed(speed)} className={`px-1.5 py-0.5 rounded text-[9px] font-bold border transition-all ${playbackSpeed === speed ? "bg-blue-600/20 border-blue-500 text-blue-400" : "border-slate-800 text-slate-500 hover:bg-slate-900"}`}>
                      {speed}x
                    </button>
                  ))}
                </div>
                <div className="flex-1 min-w-[150px] flex items-center gap-2">
                  <input
                    type="range"
                    min={0}
                    max={replayEvents.length > 0 ? replayEvents.length - 1 : 0}
                    value={currentStep}
                    onChange={e => setCurrentStep(Number(e.target.value))}
                    className="w-full accent-blue-500 cursor-pointer"
                  />
                  <span className="text-[10px] font-mono text-slate-500 whitespace-nowrap">{currentStep} / {replayEvents.length - 1}</span>
                </div>
                <div className="text-[10px] font-mono text-slate-400">{currentEvent?.timestamp?.split(" ")[1] || "--:--:--"}</div>
              </div>

              {/* Equity Curve Chart */}
              <div className="flex-1 min-h-[300px] flex flex-col">
                <div className="flex items-center gap-2 mb-2 px-1 flex-wrap">
                  <span className="text-[10px] text-slate-500 font-bold uppercase">Indicators:</span>
                  <button onClick={() => setShowEmaFast(!showEmaFast)} className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${showEmaFast ? "bg-blue-600/20 border-blue-500 text-blue-400" : "border-slate-800 text-slate-500 hover:bg-slate-900"}`}>EMA 9</button>
                  <button onClick={() => setShowEmaSlow(!showEmaSlow)} className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${showEmaSlow ? "bg-amber-600/20 border-amber-500 text-amber-400" : "border-slate-800 text-slate-500 hover:bg-slate-900"}`}>EMA 21</button>
                  <span className="text-[10px] text-slate-500 font-bold uppercase ml-2">Trades:</span>
                  <button onClick={() => setShowBuyTrades(!showBuyTrades)} className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${showBuyTrades ? "bg-emerald-600/20 border-emerald-500 text-emerald-400" : "border-slate-800 text-slate-500 hover:bg-slate-900"}`}>BUY</button>
                  <button onClick={() => setShowSellTrades(!showSellTrades)} className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${showSellTrades ? "bg-rose-600/20 border-rose-500 text-rose-400" : "border-slate-800 text-slate-500 hover:bg-slate-900"}`}>SELL</button>
                </div>
                {activeCandles.length > 0 ? (
                  <LightweightChart
                    candles={activeCandles}
                    trades={activeTrades}
                    showEmaFast={showEmaFast}
                    showEmaSlow={showEmaSlow}
                    showBuyTrades={showBuyTrades}
                    showSellTrades={showSellTrades}
                    height={350}
                  />
                ) : (
                  <div className="w-full h-80 bg-slate-950/60 rounded-xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-500">
                    <AlertTriangle size={32} className="text-slate-600 mb-2 animate-bounce" />
                    <span className="text-xs">No active replay data loaded. Run a backtest first.</span>
                  </div>
                )}
              </div>

              {/* Position Exposure */}
              <div className="glass-panel rounded-xl overflow-hidden flex flex-col shrink-0 border border-slate-800/50">
                <div className="px-3 py-1.5 bg-slate-950/80 border-b border-slate-800 text-[10px] font-bold font-mono text-slate-400 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Layers size={12} className="text-blue-400" />
                    <span>Net Position Exposure</span>
                  </div>
                </div>
                <PositionChart data={positionCurveData} height={120} />
              </div>
            </div>

            {/* Right: Metrics, Breakdown, Trades */}
            <div className="space-y-4 h-full overflow-y-auto">
              {/* Portfolio Snapshot */}
              <div className="glass-panel p-4 rounded-xl space-y-3">
                <h5 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Portfolio Snapshot</h5>
                {[
                  { label: "Net Equity", val: `₹${currentPortfolio?.equity?.toLocaleString(undefined, { maximumFractionDigits: 1 }) || backtestDetail.final_equity?.toLocaleString(undefined, { maximumFractionDigits: 1 }) || "0.0"}` },
                  { label: "Cash Balance", val: `₹${currentPortfolio?.cash?.toLocaleString(undefined, { maximumFractionDigits: 1 }) || "0.0"}` },
                  { label: "Total Fees", val: `₹${currentPortfolio?.total_fees?.toLocaleString(undefined, { maximumFractionDigits: 1 }) || backtestDetail.total_fees?.toLocaleString(undefined, { maximumFractionDigits: 1 }) || "0.0"}` },
                  { label: "Total PnL", val: `₹${(currentPortfolio?.total_pnl ?? backtestDetail.total_pnl)?.toLocaleString(undefined, { maximumFractionDigits: 1 }) || "0.0"}` },
                  { label: "Max Pos Limit", val: `${backtestDetail.max_position_size || "Auto"}` },
                ].map((row, i) => (
                  <div key={i} className="flex justify-between items-center text-xs py-1 border-b border-slate-800/40">
                    <span className="text-slate-400">{row.label}</span>
                    <span className="font-semibold text-slate-200 font-mono">{row.val}</span>
                  </div>
                ))}
              </div>

              {/* Symbol Breakdown */}
              <div className="glass-panel p-4 rounded-xl">
                <h5 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2.5">Symbol Breakdown</h5>
                {backtestDetail.symbols && backtestDetail.symbols.length > 1 ? (
                  <div className="space-y-2">
                    {backtestDetail.symbols.map((sym: string) => {
                      const symTrades = backtestDetail.metrics?.trades?.filter((t: any) => t.symbol === sym) || [];
                      const symPnl = symTrades.reduce((acc: number, t: any) => acc + ((t.direction === "SELL" ? 1 : -1) * (t.price || 0) * (t.qty || 0)), 0);
                      return (
                        <div key={sym} className="flex justify-between items-center text-xs border border-slate-800 rounded p-2 bg-slate-950/40">
                          <span className="font-bold text-slate-200">{sym}</span>
                          <span className={`font-mono font-semibold ${symPnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                            ₹{symPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 text-center py-2">Primary: {backtestDetail.symbol}</div>
                )}
              </div>

              {/* Open Positions */}
              <div className="glass-panel p-4 rounded-xl">
                <h5 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2.5">Positions</h5>
                {currentPortfolio?.positions && Object.keys(currentPortfolio.positions).length > 0 ? (
                  Object.values(currentPortfolio.positions).map((pos: any) => (
                    <div key={pos.symbol} className="flex justify-between items-center text-xs border border-slate-800 rounded p-2 bg-slate-950/40 mb-2">
                      <div>
                        <span className="font-bold text-slate-200">{pos.symbol}</span>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          {pos.qty > 0 ? "LONG" : pos.qty < 0 ? "SHORT" : "FLAT"} {Math.abs(pos.qty)} @ {pos.avg_price?.toFixed(1) || "-"}
                        </div>
                      </div>
                      <span className={`font-mono font-semibold ${pos.unrealized_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        ₹{pos.unrealized_pnl?.toFixed(1) || "0.0"}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="text-[10px] text-slate-500 text-center py-4">No open positions.</p>
                )}
              </div>

              {/* Trade Log */}
              <div className="glass-panel p-4 rounded-xl">
                <h5 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2.5">Trade Log</h5>
                <div className="max-h-48 overflow-y-auto space-y-1">
                  {(backtestDetail.metrics?.trades || []).slice(0, 20).map((t: any, idx: number) => (
                    <div key={idx} className="flex justify-between text-[10px] border-b border-slate-800/30 py-1">
                      <span className="text-slate-500">{t.timestamp?.split(" ")[1] || "--:--"}</span>
                      <span className={`font-bold ${t.direction === "BUY" ? "text-emerald-400" : "text-rose-400"}`}>{t.direction}</span>
                      <span className="text-slate-300">{t.symbol}</span>
                      <span className="font-mono text-slate-400">{t.qty} @ ₹{t.price?.toFixed(1)}</span>
                    </div>
                  ))}
                  {(!backtestDetail.metrics?.trades || backtestDetail.metrics.trades.length === 0) && (
                    <p className="text-[10px] text-slate-500 text-center py-2">No trades recorded.</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="glass-panel p-8 text-center text-slate-500 rounded-xl">
          <PlayCircle size={32} className="mx-auto mb-2 text-slate-700 animate-pulse" />
          <span className="text-xs">Select a strategy and run a backtest to view results.</span>
        </div>
      )}
    </div>
  );
}
