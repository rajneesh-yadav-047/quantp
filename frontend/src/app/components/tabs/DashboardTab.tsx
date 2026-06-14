"use client";

import React, { useState } from "react";
import { Shield, RefreshCw, Trash2, Database, CheckCircle2, XCircle, ServerCrash, RotateCcw, Play, Pause, SkipForward, SkipBack, AlertTriangle, PlayCircle, PieChart, Rocket, Plus, Code, FileText, TrendingUp, TrendingDown, BarChart3, ArrowLeft, Radio, Activity, DollarSign, Wallet, Clock, Bell, ChevronDown, ChevronUp, BarChart, Calendar } from "lucide-react";
import type { Notif, ApiErrorInfo, BacktestDetail, ReplayEvent } from "../../hooks/useQuantLab";
import LightweightChart from "../../../components/LightweightChart";


/* ---------- TotpModal ---------- */
export function TotpModal({
  isOpen, totpInput, setTotpInput, pendingAction, onConfirm, onCancel,
}: {
  isOpen: boolean; totpInput: string; setTotpInput: (v: string) => void;
  pendingAction: string | null; onConfirm: () => void; onCancel: () => void;
}) {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="glass-panel p-6 rounded-2xl w-full max-w-sm border-blue-500/30 shadow-[0_0_50px_rgba(59,130,246,0.15)] animate-in zoom-in-95 duration-200">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2.5 bg-blue-600 rounded-xl text-white"><Shield size={20} /></div>
          <h3 className="text-lg font-bold text-slate-100">Verification Required</h3>
        </div>
        <p className="text-xs text-slate-400 mb-6 leading-relaxed">
          {pendingAction === "AUTH" ? "Authorize SmartAPI session via Angel One TOTP." : "Authorize market data download request."}
        </p>
        <input
          autoFocus type="text" maxLength={6} placeholder="000000"
          className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-4 text-center text-3xl font-mono tracking-[0.4em] text-blue-400 focus:outline-none focus:border-blue-500 shadow-inner"
          value={totpInput}
          onChange={(e) => setTotpInput(e.target.value.replace(/\D/g, ""))}
          onKeyDown={(e) => e.key === "Enter" && onConfirm()}
        />
        <div className="flex gap-3 mt-8">
          <button onClick={onCancel} className="flex-1 px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-bold text-slate-400 hover:bg-slate-800 transition-all">Cancel</button>
          <button onClick={onConfirm} className="flex-1 px-4 py-2.5 rounded-lg bg-blue-600 text-xs font-bold text-white hover:bg-blue-700 transition-all shadow-lg shadow-blue-600/20">Confirm Code</button>
        </div>
      </div>
    </div>
  );
}

/* ---------- ErrorBanners ---------- */
export function ErrorBanners({ apiErrors, clearEndpointError }: {
  apiErrors: Record<string, ApiErrorInfo>; clearEndpointError: (ep: string) => void;
}) {
  const errors = Object.entries(apiErrors).filter(([ep]) => !ep.startsWith("ollama/"));
  if (errors.length === 0) return null;
  return (
    <div className="space-y-2 mb-4">
      {errors.map(([endpoint, info]) => (
        <div key={endpoint} className="flex items-center gap-3 p-3 rounded-lg border border-rose-800/50 bg-rose-950/20 text-rose-400 text-xs">
          <ServerCrash size={16} className="shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="font-semibold">{endpoint}</span>
            <p className="text-rose-300/80 truncate">{info.error}</p>
          </div>
          <button
            onClick={() => { clearEndpointError(endpoint); info.retry(); }}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded bg-rose-900/40 hover:bg-rose-900/60 border border-rose-800/50 text-[10px] font-bold transition-all shrink-0"
          >
            <RotateCcw size={12} /> Retry
          </button>
          <button onClick={() => clearEndpointError(endpoint)} className="p-1.5 rounded hover:bg-rose-900/40 text-rose-400/60 hover:text-rose-400 transition-all shrink-0">×</button>
        </div>
      ))}
    </div>
  );
}

/* ---------- DashboardTab ---------- */
export function DashboardTab({
  smartapiConnected, datasets, strategies, backtestRuns, selectedStrategyId, btStartDate, btEndDate,
  setBtStartDate, setBtEndDate, handleSelectStrategy, handleRunBacktest, triggerAuth, handleSelectRun,
}: any) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { title: "SmartAPI Connection", val: smartapiConnected ? "Connected" : "Disconnected", status: smartapiConnected ? "success" : "info" },
          { title: "Saved Datasets", val: `${datasets.length} Active`, status: "info" },
          { title: "Strategies", val: `${strategies.length} Configured`, status: "info" },
          { title: "Backtest Sessions", val: `${backtestRuns.length} Runs logged`, status: "info" }
        ].map((card, i) => (
          <div key={i} className="glass-panel p-4 rounded-xl relative overflow-hidden">
            <div className="absolute right-0 top-0 h-24 w-24 bg-gradient-to-br from-blue-500/10 to-transparent rounded-bl-full pointer-events-none" />
            <span className="text-xs text-slate-400 font-medium">{card.title}</span>
            <h3 className="text-lg font-bold text-slate-100 mt-1">{card.val}</h3>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="glass-panel p-5 rounded-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h4 className="font-bold text-slate-200 flex items-center gap-2">
                <Shield size={18} className="text-blue-400" />
                SmartAPI Authentication
              </h4>
              {smartapiConnected ? (
                <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800">CONNECTED</span>
              ) : (
                <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded-full bg-slate-900 text-slate-400 border border-slate-800">DISCONNECTED</span>
              )}
            </div>
            <p className="text-xs text-slate-400 mb-4 leading-relaxed">
              Connect to Angel One SmartAPI to download real historical market ticks. Credentials are encrypted and stored in local catalog.
            </p>
            <form onSubmit={triggerAuth}>
              <div className="p-3 bg-slate-900/50 border border-dashed border-slate-800 rounded-lg text-center mb-4">
                <p className="text-[10px] text-slate-500 uppercase font-bold">Authenticated via .env</p>
              </div>
              <button type="submit" className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded font-bold text-xs py-2 transition-all">
                Authenticate SmartAPI
              </button>
            </form>
          </div>
        </div>

        <div className="glass-panel p-5 rounded-xl flex flex-col justify-between col-span-2">
          <div>
            <h4 className="font-bold text-slate-200 mb-4 flex items-center gap-2">
              <PlayCircle size={18} className="text-emerald-400" />
              Quick Backtest Session Launch
            </h4>
            <p className="text-xs text-slate-400 mb-5 leading-relaxed">
              Select a strategy and date range. Strategy config (symbols, interval, capital) is pulled automatically from the strategy definition.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Select Strategy</label>
                <select
                  value={selectedStrategyId}
                  onChange={e => handleSelectStrategy(e.target.value)}
                  className="t-input w-full text-xs rounded px-2.5 py-1.5"
                >
                  <option value="">-- Choose Strategy --</option>
                  {strategies.map((s: any) => (
                    <option key={s.id} value={s.id}>{s.name} (v{s.version})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1 flex items-center gap-1">
                  <Calendar size={10} className="text-blue-400" /> Date Range
                </label>
                <div className="flex gap-2">
                  <input type="date" value={btStartDate} onChange={e => setBtStartDate(e.target.value)} className="t-input flex-1 text-xs rounded px-2 py-1" />
                  <input type="date" value={btEndDate} onChange={e => setBtEndDate(e.target.value)} className="t-input flex-1 text-xs rounded px-2 py-1" />
                </div>
              </div>
              <div className="col-span-2">
                <button
                  onClick={handleRunBacktest}
                  disabled={!selectedStrategyId}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2"
                >
                  <Play size={14} fill="currentColor" /> Execute Backtest Engine
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Past runs */}
      <div className="glass-panel p-5 rounded-xl">
        <h4 className="font-bold text-slate-200 mb-4">Past Backtest Results</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-400 border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-300 font-medium">
                <th className="py-2.5">Run ID</th><th>Strategy</th><th>Symbols</th><th>Interval</th><th>Period</th><th>Net Profit</th><th>Sharpe</th><th>Max DD</th><th className="text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {backtestRuns.map((run: any) => (
                <tr key={run.id} className="hover:bg-slate-900/30">
                  <td className="py-3 font-mono text-blue-400 font-bold">{run.id}</td>
                  <td>{run.strategy_name}</td>
                  <td className="font-bold text-slate-300">{(run.symbols || [run.symbol]).join(", ")}</td>
                  <td>{run.interval}</td>
                  <td className="text-slate-500">{run.start_time?.split(" ")[0] || run.start_time} to {run.end_time?.split(" ")[0] || run.end_time}</td>
                  <td className={run.total_pnl >= 0 ? "text-emerald-400 font-semibold" : "text-rose-400 font-semibold"}>
                    ₹{(run.total_pnl ?? 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                  </td>
                  <td className="font-bold">{run.sharpe_ratio?.toFixed(2) ?? "-"}</td>
                  <td className="font-mono text-slate-500">{(run.max_drawdown * 100)?.toFixed(1) ?? "-"}%</td>
                  <td className="text-right">
                    <button
                      onClick={() => handleSelectRun(run.id)}
                      className="px-2.5 py-1 rounded bg-slate-800 text-[10px] font-bold text-slate-200 hover:bg-slate-700 transition-all"
                    >
                      Load
                    </button>
                  </td>
                </tr>
              ))}
              {backtestRuns.length === 0 && (
                <tr>
                  <td colSpan={9} className="py-6 text-center text-slate-500 font-medium">
                    No simulation runs logged yet. Configure a strategy and run a backtest.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ---------- DatasetsTab ---------- */
export function DatasetsTab({
  dlSymbol, setDlSymbol, dlInterval, setDlInterval, dlFromDate, setDlFromDate, dlToDate, setDlToDate,
  downloading, triggerDownload, datasets, selectedDataset, setSelectedDataset, suggestions, showSuggestions, setShowSuggestions,
  triggerNotif,
  // New props for preview:
  previewData, setPreviewData, previewLoading, previewError, handlePreviewDataset,
}: any) {
  const [previewTab, setPreviewTab] = useState<"chart" | "table">("chart");

  const handleDownloadFile = (symbol: string, interval: string, filePath: string) => {
    const url = `/api/data/download-file/${encodeURIComponent(symbol)}/${encodeURIComponent(interval)}`;
    const a = document.createElement("a");
    a.href = url;
    a.download = `${symbol}_${interval}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    triggerNotif("success", `Downloaded ${symbol} ${interval} dataset.`);
  };

  const formatTimeLabel = (timeVal: any, interval: string) => {
    if (!timeVal) return "-";
    if (typeof timeVal === "number") {
      const date = new Date(timeVal * 1000);
      const year = date.getUTCFullYear();
      const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const month = monthNames[date.getUTCMonth()];
      const day = date.getUTCDate();
      const hours = String(date.getUTCHours()).padStart(2, '0');
      const minutes = String(date.getUTCMinutes()).padStart(2, '0');
      return `${day} ${month} ${year}, ${hours}:${minutes}`;
    }
    return String(timeVal);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="glass-panel p-5 rounded-xl self-start">
        <h4 className="font-bold text-slate-200 mb-4 flex items-center gap-2">
          <Database size={18} className="text-blue-400" />
          SmartAPI Downloader
        </h4>
        <p className="text-xs text-slate-400 mb-4 leading-relaxed">
          Submit symbol requests. Files are indexed in standard CSV and Excel formats under <code className="text-slate-300">/datasets/csv/</code>.
        </p>
        <form onSubmit={triggerDownload} className="space-y-4">
          <div className="relative">
            <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Asset Symbol</label>
            <input
              type="text" value={dlSymbol}
              onChange={e => { setDlSymbol(e.target.value.toUpperCase()); setShowSuggestions(true); }}
              onFocus={() => setShowSuggestions(true)}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
              className="t-input w-full text-xs rounded px-2.5 py-1.5 font-semibold"
              placeholder="e.g. SBIN, RELIANCE, NIFTY"
            />
            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute z-50 w-full mt-1 max-h-60 overflow-y-auto rounded shadow-2xl divide-y custom-scrollbar" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
                {suggestions.map((s: any) => (
                  <div
                    key={s.token}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      const bare = s.bare_symbol || s.symbol;
                      setDlSymbol(bare);
                      setShowSuggestions(false);
                    }}
                    className="px-3 py-2 text-xs cursor-pointer flex justify-between items-center transition-colors duration-150"
                    style={{ borderColor: 'var(--border-color)' }}
                    onMouseEnter={e => (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--bg-panel-inner)'}
                    onMouseLeave={e => (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'}
                  >
                    <div className="flex flex-col">
                      <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{s.bare_symbol || s.symbol}</span>
                      <span className="text-[9px] truncate max-w-[160px]" style={{ color: 'var(--text-tertiary)' }}>{s.name}</span>
                    </div>
                    <span className="text-[9px] font-mono rounded px-1.5 py-0.5" style={{ backgroundColor: 'var(--bg-panel-inner)', border: '1px solid var(--border-color)', color: 'var(--text-tertiary)' }}>{s.token}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Timeframe Interval</label>
            <select value={dlInterval} onChange={e => setDlInterval(e.target.value)} className="t-input w-full text-xs rounded px-2.5 py-1.5">
              <option value="ONE_MINUTE">1 Minute (Intraday)</option>
              <option value="FIVE_MINUTE">5 Minute (Intraday)</option>
              <option value="FIFTEEN_MINUTE">15 Minute (Intraday)</option>
              <option value="ONE_HOUR">1 Hour</option>
              <option value="ONE_DAY">Daily</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1 flex items-center gap-1">
                <Calendar size={10} className="text-white" /> From Date
              </label>
              <input type="date" value={dlFromDate} onChange={e => setDlFromDate(e.target.value)} className="t-input w-full text-xs rounded px-2 py-1" />
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1 flex items-center gap-1">
                <Calendar size={10} className="text-white" /> To Date
              </label>
              <input type="date" value={dlToDate} onChange={e => setDlToDate(e.target.value)} className="t-input w-full text-xs rounded px-2 py-1" />
            </div>
          </div>
          <button type="submit" disabled={downloading} className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2">
            {downloading ? <><RefreshCw size={14} className="animate-spin" /> Fetching...</> : <><Database size={14} /> Fetch & Write CSV</>}
          </button>
        </form>
      </div>

      <div className="glass-panel p-5 rounded-xl col-span-2 flex flex-col gap-4">
        <h4 className="font-bold text-slate-200">Metadata Catalog (CSV / Excel Storage)</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-400 border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-300 font-medium">
                <th className="py-2.5">Symbol</th><th>Interval</th><th>Record Range</th><th>Bars Count</th><th>CSV Path</th><th className="text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {datasets.map((d: any) => (
                <tr key={`${d.symbol}_${d.interval}`} className="hover:bg-slate-900/30">
                  <td className="py-3 font-bold text-slate-200">
                    <div className="flex items-center gap-2">
                      <span>{d.symbol}</span>
                      {d.is_mock ? (
                        <span className="px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded">Mock</span>
                      ) : (
                        <span className="px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded">Real</span>
                      )}
                    </div>
                  </td>
                  <td>{d.interval}</td>
                  <td className="text-slate-500 font-mono text-[10px]">{d.start_date || "-"} - {d.end_date || "-"}</td>
                  <td className="font-semibold text-blue-400 font-mono">{d.records_count ?? "-"}</td>
                  <td className="text-slate-600 truncate max-w-xs text-[10px]" title={d.file_path || ""}>{d.file_path || "-"}</td>
                  <td className="text-right whitespace-nowrap">
                    <button
                      onClick={() => handlePreviewDataset(d.symbol, d.interval)}
                      className="px-2.5 py-1 rounded text-[10px] font-bold bg-slate-800 text-slate-200 border border-slate-700 hover:bg-slate-700 transition-all mr-2"
                    >
                      Preview
                    </button>
                    <button
                      onClick={() => { setSelectedDataset(`${d.symbol}_${d.interval}`); triggerNotif("success", `Dataset ${d.symbol} selected as active simulation feed.`); }}
                      className={`px-2.5 py-1 rounded text-[10px] font-bold transition-all mr-2 ${selectedDataset === `${d.symbol}_${d.interval}` ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-slate-800 text-slate-200 hover:bg-slate-700"}`}
                    >
                      {selectedDataset === `${d.symbol}_${d.interval}` ? "Active" : "Select"}
                    </button>
                    <button
                      onClick={() => handleDownloadFile(d.symbol, d.interval, d.file_path)}
                      className="px-2.5 py-1 rounded text-[10px] font-bold bg-blue-600/20 text-blue-400 border border-blue-800 hover:bg-blue-600/30 transition-all"
                    >
                      Download
                    </button>
                  </td>
                </tr>
              ))}
              {datasets.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-500 font-medium">
                    No CSV datasets found. Download candles using SmartAPI.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Dataset Preview section (when loading) */}
      {previewLoading && (
        <div className="glass-panel p-6 rounded-xl col-span-3 flex flex-col items-center justify-center min-h-[300px] border border-blue-500/20">
          <RefreshCw size={24} className="animate-spin text-blue-400 mb-2" />
          <span className="text-sm font-semibold text-slate-300">Loading dataset preview...</span>
        </div>
      )}

      {/* Dataset Preview section (when error) */}
      {previewError && (
        <div className="glass-panel p-6 rounded-xl col-span-3 flex flex-col items-center justify-center min-h-[200px] border border-rose-500/20 text-rose-400">
          <AlertTriangle size={24} className="mb-2 text-rose-500" />
          <span className="text-sm font-semibold">Failed to load preview</span>
          <p className="text-xs text-rose-300/80 mt-1">{previewError}</p>
          <button onClick={() => setPreviewData(null)} className="mt-4 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded text-xs text-slate-200 font-bold border border-slate-700">Dismiss</button>
        </div>
      )}

      {/* Dataset Preview Panel */}
      {previewData && (
        <div className="glass-panel p-6 rounded-xl col-span-3 flex flex-col gap-5 border border-slate-800/80 shadow-2xl relative animate-in fade-in slide-in-from-bottom-2 duration-200">
          {/* Header */}
          <div className="flex justify-between items-center pb-4 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-blue-600/10 border border-blue-500/20 rounded-xl text-blue-400">
                <Database size={20} />
              </div>
              <div>
                <h4 className="font-bold text-slate-100 text-base flex items-center gap-2">
                  Dataset Preview: {previewData.symbol}
                  {previewData.is_mock ? (
                    <span className="px-2 py-0.5 text-[10px] font-extrabold uppercase bg-amber-500/10 text-amber-400 border border-amber-500/30 rounded-full">Mock Data</span>
                  ) : (
                    <span className="px-2 py-0.5 text-[10px] font-extrabold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded-full">Real Data (Verified)</span>
                  )}
                </h4>
                <p className="text-xs text-slate-400 mt-0.5">Timeframe: <span className="font-mono text-blue-400 font-semibold">{previewData.interval}</span> • Total Records: <span className="font-semibold text-slate-200">{previewData.total_records} candles</span></p>
              </div>
            </div>
            
            {/* Actions & Close */}
            <div className="flex items-center gap-3">
              {/* Chart/Table Toggle */}
              <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800">
                <button
                  onClick={() => setPreviewTab("chart")}
                  className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                    previewTab === "chart"
                      ? "bg-slate-800 text-blue-400 shadow-sm font-semibold"
                      : "text-slate-400 hover:text-slate-200 font-medium"
                  }`}
                >
                  Chart View
                </button>
                <button
                  onClick={() => setPreviewTab("table")}
                  className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                    previewTab === "table"
                      ? "bg-slate-800 text-blue-400 shadow-sm font-semibold"
                      : "text-slate-400 hover:text-slate-200 font-medium"
                  }`}
                >
                  Spreadsheet View
                </button>
              </div>
              
              {/* Close button */}
              <button
                onClick={() => setPreviewData(null)}
                className="p-1.5 rounded-lg border border-slate-850 bg-slate-900/50 hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-all font-bold text-sm w-8 h-8 flex items-center justify-center"
              >
                ×
              </button>
            </div>
          </div>
          
          {/* Stats Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-slate-950/40 p-4 rounded-xl border border-slate-800/60">
            {[
              { label: "Date Range Covered", value: previewData.candles.length > 0 ? `${formatTimeLabel(previewData.candles[0].time, previewData.interval)} to ${formatTimeLabel(previewData.candles[previewData.candles.length - 1].time, previewData.interval)}` : "N/A" },
              { label: "Suggested Max Pos Size", value: previewData.suggested_max_position ? `₹${previewData.suggested_max_position.toLocaleString(undefined, {maximumFractionDigits: 0})}` : "Auto" },
              { label: "Average Close Price", value: previewData.candles.length > 0 ? `₹${(previewData.candles.reduce((acc: number, c: any) => acc + c.close, 0) / previewData.candles.length).toFixed(2)}` : "N/A" },
              { label: "Price Range (Min - Max)", value: previewData.candles.length > 0 ? `₹${Math.min(...previewData.candles.map((c: any) => c.close)).toFixed(1)} - ₹${Math.max(...previewData.candles.map((c: any) => c.close)).toFixed(1)}` : "N/A" }
            ].map((stat, i) => (
              <div key={i} className="flex flex-col">
                <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider">{stat.label}</span>
                <span className="text-xs font-semibold text-slate-300 mt-1 font-mono">{stat.value}</span>
              </div>
            ))}
          </div>

          {/* Main Preview Tab Content */}
          <div className="flex-1 min-h-[400px]">
            {previewTab === "chart" ? (
              <div className="h-[400px] w-full rounded-xl overflow-hidden bg-slate-950">
                <LightweightChart candles={previewData.candles} height={400} showEmaFast={false} showEmaSlow={false} />
              </div>
            ) : (
              <div className="max-h-[400px] overflow-auto rounded-xl border border-slate-800/80 bg-slate-950/20 custom-scrollbar">
                <table className="w-full text-left text-xs text-slate-400 border-collapse">
                  <thead>
                    <tr className="sticky top-0 bg-slate-900 border-b border-slate-800 text-slate-300 font-semibold shadow-[0_1px_0_rgba(255,255,255,0.05)]">
                      <th className="p-3">Time / Date</th>
                      <th className="p-3 text-right">Open (₹)</th>
                      <th className="p-3 text-right">High (₹)</th>
                      <th className="p-3 text-right">Low (₹)</th>
                      <th className="p-3 text-right">Close (₹)</th>
                      <th className="p-3 text-right">Volume</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/40 font-mono">
                    {previewData.candles.slice(0, 50).map((c: any, index: number) => (
                      <tr key={index} className="hover:bg-slate-900/30">
                        <td className="p-3 text-slate-300">{formatTimeLabel(c.time, previewData.interval)}</td>
                        <td className="p-3 text-right">₹{Number(c.open).toFixed(2)}</td>
                        <td className="p-3 text-right text-emerald-400">₹{Number(c.high).toFixed(2)}</td>
                        <td className="p-3 text-right text-rose-400">₹{Number(c.low).toFixed(2)}</td>
                        <td className="p-3 text-right text-slate-200">₹{Number(c.close).toFixed(2)}</td>
                        <td className="p-3 text-right text-slate-400">{Number(c.volume || 0).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {previewData.candles.length > 50 && (
                  <div className="p-3 text-center text-[10px] text-slate-500 bg-slate-950/20 border-t border-slate-800/30">
                    Showing first 50 rows of {previewData.candles.length} total candles.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
