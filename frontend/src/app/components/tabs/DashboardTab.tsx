"use client";

import React, { useState } from "react";
import { Shield, RefreshCw, Trash2, Database, CheckCircle2, XCircle, ServerCrash, RotateCcw, Play, Pause, SkipForward, SkipBack, AlertTriangle, PlayCircle, PieChart, Rocket, Plus, Code, FileText, TrendingUp, TrendingDown, BarChart3, ArrowLeft, Radio, Activity, DollarSign, Wallet, Clock, Bell, ChevronDown, ChevronUp, BarChart, Calendar } from "lucide-react";
import type { Notif, ApiErrorInfo, BacktestDetail, ReplayEvent } from "../../hooks/useAxon";
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
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-6 rounded-2xl w-full max-w-sm border-[#4a7fcc]/30 shadow-[0_0_50px_rgba(74,127,204,0.15)] animate-in zoom-in-95 duration-200">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2.5 bg-[#4a7fcc] rounded-xl text-[#f0f0f0]"><Shield size={20} /></div>
          <h3 className="text-lg font-bold text-[#e8e8e8]">Verification Required</h3>
        </div>
        <p className="text-xs text-[#a0a0a0] mb-6 leading-relaxed">
          {pendingAction === "AUTH"
            ? "Authorize SmartAPI session via Angel One TOTP."
            : pendingAction === "DOWNLOAD"
            ? "Authorize market data download request."
            : "Authorize request."}
        </p>
        <input
          autoFocus type="text" maxLength={6} placeholder="000000"
          className="w-full bg-[#111] border border-[var(--ax-border)] rounded-xl px-4 py-4 text-center text-3xl font-mono tracking-[0.4em] text-[#93b4ff] focus:outline-none focus:border-[#4a7fcc] shadow-inner"
          value={totpInput}
          onChange={(e) => setTotpInput(e.target.value.replace(/\D/g, ""))}
          onKeyDown={(e) => e.key === "Enter" && onConfirm()}
        />
        <div className="flex gap-3 mt-8">
          <button onClick={onCancel} className="flex-1 px-4 py-2.5 rounded-lg bg-[#161616] border border-[var(--ax-border)] text-xs font-bold text-[#a0a0a0] hover:bg-[#222] transition-all">Cancel</button>
          <button onClick={onConfirm} className="flex-1 px-4 py-2.5 rounded-lg bg-[#4a7fcc] text-xs font-bold text-[#f0f0f0] hover:bg-[#5a8fd0] transition-all shadow-lg shadow-[#4a7fcc]/20">Confirm Code</button>
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
        <div key={endpoint} className="bg-[#1a0d0d] border border-[#3a1515] rounded-lg px-4 py-3 flex items-start gap-3 text-[12px] text-[#c0c0c0]">
          <ServerCrash size={16} className="shrink-0 mt-0.5 text-red-400" />
          <div className="flex-1 min-w-0">
            <span className="font-semibold text-[#e0e0e0]">{endpoint}</span>
            <p className="text-[#a0a0a0] truncate">{info.error}</p>
          </div>
          <button
            onClick={() => { clearEndpointError(endpoint); info.retry(); }}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded bg-[#2a1515] hover:bg-[#3a2020] border border-[#3a1515] text-[10px] font-bold transition-all shrink-0 text-[#c0c0c0]"
          >
            <RotateCcw size={12} /> Retry
          </button>
          <button onClick={() => clearEndpointError(endpoint)} className="p-1.5 rounded hover:bg-[#2a1515] text-[#a0a0a0] hover:text-[#e0e0e0] transition-all shrink-0">×</button>
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
      <div className="grid grid-cols-4 gap-3">
        {[
          { title: "SmartAPI Connection", val: smartapiConnected ? "Connected" : "Disconnected", sub: smartapiConnected ? "Session active" : "Session inactive", subColor: smartapiConnected ? "text-emerald-400" : "text-red-400" },
          { title: "Saved Datasets", val: `${datasets.length} Active`, sub: "Available for backtesting", subColor: "text-[#93b4ff]" },
          { title: "Strategies", val: `${strategies.length} Configured`, sub: "Active configurations", subColor: "text-[#93b4ff]" },
          { title: "Backtest Sessions", val: `${backtestRuns.length} Runs logged`, sub: "Completed sessions", subColor: "text-[#93b4ff]" }
        ].map((card, i) => (
          <div key={i} className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
            <div className="text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">{card.title}</div>
            <div className="text-[22px] font-semibold text-[#f0f0f0] leading-none">{card.val}</div>
            <div className={`text-[11px] mt-1.5 ${card.subColor}`}>{card.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] border-l-[3px] border-l-[#4a7fcc] rounded-r-xl rounded-l-none p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h4 className="font-bold text-[#c0c0c0] flex items-center gap-2">
                <Shield size={18} className="text-[#93b4ff]" />
                SmartAPI Authentication
              </h4>
              {smartapiConnected ? (
                <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800">CONNECTED</span>
              ) : (
                <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded-full bg-[#161616] text-[#a0a0a0] border border-[var(--ax-border)]">DISCONNECTED</span>
              )}
            </div>
            <p className="text-xs text-[#a0a0a0] mb-4 leading-relaxed">
              Connect to Angel One SmartAPI to download real historical market ticks. Credentials are encrypted and stored in local catalog.
            </p>
            <form onSubmit={triggerAuth}>
              <div className="p-3 bg-[#161616]/50 border border-dashed border-[var(--ax-border)] rounded-lg text-center mb-4">
                <p className="text-[10px] text-[#606060] uppercase font-bold">Authenticated via .env</p>
              </div>
              <button type="submit" className="w-full bg-[#4a7fcc] hover:bg-[#5a8fd0] text-[#f0f0f0] rounded font-bold text-xs py-2 transition-all">
                Authenticate SmartAPI
              </button>
            </form>
          </div>
        </div>

        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 flex flex-col justify-between col-span-2">
          <div>
            <h4 className="font-bold text-[#c0c0c0] mb-4 flex items-center gap-2">
              <PlayCircle size={18} className="text-emerald-400" />
              Quick Backtest Session Launch
            </h4>
            <p className="text-xs text-[#a0a0a0] mb-5 leading-relaxed">
              Select a strategy and date range. Strategy config (symbols, interval, capital) is pulled automatically from the strategy definition.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">Select Strategy</label>
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
                <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1 flex items-center gap-1">
                  <Calendar size={10} className="text-[#93b4ff]" /> Date Range
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
                  className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-[#161616] disabled:text-[#606060] text-[#f0f0f0] rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2"
                >
                  <Play size={14} fill="currentColor" /> Execute Backtest Engine
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Past runs */}
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
        <h4 className="font-bold text-[#c0c0c0] mb-4">Past Backtest Results</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#161616]">
                <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider">Run ID</th>
                <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider">Strategy</th>
                <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider">Symbols</th>
                <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider">Interval</th>
                <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider">Period</th>
                <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider">Net Profit</th>
                <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider">Sharpe</th>
                <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider">Max DD</th>
                <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {backtestRuns.map((run: any) => (
                <tr key={run.id} className="bg-[#1a1a1a] border-b border-[#222] hover:bg-[#1e1e1e]">
                  <td className="py-3 px-3 text-[12px] text-[#c0c0c0] font-mono text-[#93b4ff] font-bold">{run.id}</td>
                  <td className="py-3 px-3 text-[12px] text-[#c0c0c0]">{run.strategy_name}</td>
                  <td className="py-3 px-3 text-[12px] text-[#c0c0c0] font-bold text-[#888]">{(run.symbols || [run.symbol]).join(", ")}</td>
                  <td className="py-3 px-3 text-[12px] text-[#c0c0c0]">{run.interval}</td>
                  <td className="py-3 px-3 text-[12px] text-[#c0c0c0]">{run.start_time?.split(" ")[0] || run.start_time} to {run.end_time?.split(" ")[0] || run.end_time}</td>
                  <td className={run.total_pnl >= 0 ? "py-3 px-3 text-[12px] font-semibold text-emerald-400" : "py-3 px-3 text-[12px] font-semibold text-red-400"}>
                    ₹{(run.total_pnl ?? 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                  </td>
                  <td className="py-3 px-3 text-[12px] text-[#c0c0c0] font-bold">{run.sharpe_ratio?.toFixed(2) ?? "-"}</td>
                  <td className="py-3 px-3 text-[12px] text-[#c0c0c0] font-mono">{(run.max_drawdown * 100)?.toFixed(1) ?? "-"}%</td>
                  <td className="py-3 px-3 text-[12px] text-[#c0c0c0] text-right">
                    <button
                      onClick={() => handleSelectRun(run.id)}
                      className="px-2.5 py-1 rounded bg-[#161616] text-[10px] font-bold text-[#c0c0c0] hover:bg-[#222] transition-all"
                    >
                      Load
                    </button>
                  </td>
                </tr>
              ))}
              {backtestRuns.length === 0 && (
                <tr className="bg-[#1a1a1a]">
                  <td colSpan={9} className="py-6 px-3 text-center text-[12px] text-[#c0c0c0] font-medium">
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
  downloading, dlJobId, dlJobProgress, triggerDownload, datasets, selectedDataset, setSelectedDataset, suggestions, showSuggestions, setShowSuggestions,
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
    <div className="space-y-4">
      <form onSubmit={triggerDownload} className="flex gap-3 items-end">
        <div className="relative flex-1 min-w-0">
          <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">Asset Symbol</label>
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
        <div className="min-w-[140px]">
          <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">Interval</label>
          <select value={dlInterval} onChange={e => setDlInterval(e.target.value)} className="t-input w-full text-xs rounded px-2.5 py-1.5">
            <option value="ONE_MINUTE">1 Minute (Intraday)</option>
            <option value="FIVE_MINUTE">5 Minute (Intraday)</option>
            <option value="FIFTEEN_MINUTE">15 Minute (Intraday)</option>
            <option value="ONE_HOUR">1 Hour</option>
            <option value="ONE_DAY">Daily</option>
          </select>
        </div>
        <div className="min-w-[130px]">
          <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1 flex items-center gap-1">
            <Calendar size={10} className="text-[#f0f0f0]" /> From Date
          </label>
          <input type="date" value={dlFromDate} onChange={e => setDlFromDate(e.target.value)} className="t-input w-full text-xs rounded px-2 py-1" />
        </div>
        <div className="min-w-[130px]">
          <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1 flex items-center gap-1">
            <Calendar size={10} className="text-[#f0f0f0]" /> To Date
          </label>
          <input type="date" value={dlToDate} onChange={e => setDlToDate(e.target.value)} className="t-input w-full text-xs rounded px-2 py-1" />
        </div>
        <button type="submit" disabled={downloading || !!dlJobId} className="bg-[#4a7fcc] hover:bg-[#5a8fd0] text-[#f0f0f0] rounded font-bold text-xs py-2 px-4 transition-all flex items-center justify-center gap-2 shrink-0">
          {downloading ? <><RefreshCw size={14} className="animate-spin" /> Fetching…</> : dlJobId ? <><RefreshCw size={14} className="animate-spin" /> Downloading…</> : <><Database size={14} /> Fetch & Write CSV</>}
        </button>
      </form>

      {dlJobId && (
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-[#a0a0a0] font-medium">Background download in progress</span>
            <span className="text-[10px] text-[#93b4ff] font-bold">{dlJobProgress}%</span>
          </div>
          <div className="w-full bg-[#161616] rounded-full h-1.5 overflow-hidden">
            <div className="bg-[#4a7fcc] h-1.5 rounded-full transition-all duration-500" style={{ width: `${dlJobProgress}%` }} />
          </div>
          <p className="text-[9px] text-[#606060] mt-1">You can navigate away. The download continues in the background.</p>
        </div>
      )}

      <div className="flex flex-col gap-2">
        {datasets.map((d: any) => (
          <div key={`${d.symbol}_${d.interval}`} className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-4 py-3 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#222] flex items-center justify-center text-[#93b4ff] shrink-0">
              <Database size={16} />
            </div>
            <div className="min-w-0">
              <div className="text-[13px] font-medium text-[#d0d0d0] flex items-center gap-2">
                {d.symbol}
                {d.is_mock ? (
                  <span className="px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded">Mock</span>
                ) : (
                  <span className="px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded">Real</span>
                )}
              </div>
              <div className="text-[11px] text-[#505050]">
                {d.interval} • {d.start_date || "-"} - {d.end_date || "-"} • {d.records_count ?? "-"} records
              </div>
            </div>
            <div className="ml-auto text-right flex items-center gap-2 shrink-0">
              <button
                onClick={() => handlePreviewDataset(d.symbol, d.interval)}
                className="px-2.5 py-1 rounded text-[10px] font-bold bg-[#161616] text-[#c0c0c0] border border-[var(--ax-border)] hover:bg-[#222] transition-all"
              >
                Preview
              </button>
              <button
                onClick={() => { setSelectedDataset(`${d.symbol}_${d.interval}`); triggerNotif("success", `Dataset ${d.symbol} selected as active simulation feed.`); }}
                className={`px-2.5 py-1 rounded text-[10px] font-bold transition-all ${selectedDataset === `${d.symbol}_${d.interval}` ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-[#161616] text-[#c0c0c0] hover:bg-[#222]"}`}
              >
                {selectedDataset === `${d.symbol}_${d.interval}` ? "Active" : "Select"}
              </button>
              <button
                onClick={() => handleDownloadFile(d.symbol, d.interval, d.file_path)}
                className="px-2.5 py-1 rounded text-[10px] font-bold bg-[#1c2030] text-[#93b4ff] border border-[#2a3a5a] hover:bg-[#4a7fcc]/30 transition-all"
              >
                Download
              </button>
            </div>
          </div>
        ))}
        {datasets.length === 0 && (
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-4 py-3 text-center text-[12px] text-[#c0c0c0]">
            No CSV datasets found. Download candles using SmartAPI.
          </div>
        )}
      </div>

      {/* Dataset Preview section (when loading) */}
      {previewLoading && (
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 flex flex-col items-center justify-center min-h-[300px]">
          <RefreshCw size={24} className="animate-spin text-[#93b4ff] mb-2" />
          <span className="text-sm font-semibold text-[#888]">Loading dataset preview...</span>
        </div>
      )}

      {/* Dataset Preview section (when error) */}
      {previewError && (
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 flex flex-col items-center justify-center min-h-[200px] text-rose-400">
          <AlertTriangle size={24} className="mb-2 text-rose-500" />
          <span className="text-sm font-semibold">Failed to load preview</span>
          <p className="text-xs text-rose-300/80 mt-1">{previewError}</p>
          <button onClick={() => setPreviewData(null)} className="mt-4 px-4 py-2 bg-[#161616] hover:bg-[#222] rounded text-xs text-[#c0c0c0] font-bold border border-[var(--ax-border)]">Dismiss</button>
        </div>
      )}

      {/* Dataset Preview Panel */}
      {previewData && (
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 flex flex-col gap-5 relative animate-in fade-in slide-in-from-bottom-2 duration-200">
          {/* Header */}
          <div className="flex justify-between items-center pb-4 border-b border-[var(--ax-border)]">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-[#1c2030] border border-[#4a7fcc]/20 rounded-xl text-[#93b4ff]">
                <Database size={20} />
              </div>
              <div>
                <h4 className="font-bold text-[#e8e8e8] text-base flex items-center gap-2">
                  Dataset Preview: {previewData.symbol}
                  {previewData.is_mock ? (
                    <span className="px-2 py-0.5 text-[10px] font-extrabold uppercase bg-amber-500/10 text-amber-400 border border-amber-500/30 rounded-full">Mock Data</span>
                  ) : (
                    <span className="px-2 py-0.5 text-[10px] font-extrabold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded-full">Real Data (Verified)</span>
                  )}
                </h4>
                <p className="text-xs text-[#a0a0a0] mt-0.5">Timeframe: <span className="font-mono text-[#93b4ff] font-semibold">{previewData.interval}</span> • Total Records: <span className="font-semibold text-[#c0c0c0]">{previewData.total_records} candles</span></p>
              </div>
            </div>
            
            {/* Actions & Close */}
            <div className="flex items-center gap-3">
              {/* Chart/Table Toggle */}
              <div className="flex bg-[#111] p-1 rounded-lg border border-[var(--ax-border)]">
                <button
                  onClick={() => setPreviewTab("chart")}
                  className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                    previewTab === "chart"
                      ? "bg-[#161616] text-[#93b4ff] shadow-sm font-semibold"
                      : "text-[#a0a0a0] hover:text-[#c0c0c0] font-medium"
                  }`}
                >
                  Chart View
                </button>
                <button
                  onClick={() => setPreviewTab("table")}
                  className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                    previewTab === "table"
                      ? "bg-[#161616] text-[#93b4ff] shadow-sm font-semibold"
                      : "text-[#a0a0a0] hover:text-[#c0c0c0] font-medium"
                  }`}
                >
                  Spreadsheet View
                </button>
              </div>
              
              {/* Close button */}
              <button
                onClick={() => setPreviewData(null)}
                className="p-1.5 rounded-lg border border-[var(--ax-border)] bg-[#161616]/50 hover:bg-[#222] text-[#a0a0a0] hover:text-[#e8e8e8] transition-all font-bold text-sm w-8 h-8 flex items-center justify-center"
              >
                ×
              </button>
            </div>
          </div>
          
          {/* Stats Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-[#111]/40 p-4 rounded-xl border border-[var(--ax-border)]/60">
            {[
              { label: "Date Range Covered", value: previewData.candles.length > 0 ? `${formatTimeLabel(previewData.candles[0].time, previewData.interval)} to ${formatTimeLabel(previewData.candles[previewData.candles.length - 1].time, previewData.interval)}` : "N/A" },
              { label: "Suggested Max Pos Size", value: previewData.suggested_max_position ? `₹${previewData.suggested_max_position.toLocaleString(undefined, {maximumFractionDigits: 0})}` : "Auto" },
              { label: "Average Close Price", value: previewData.candles.length > 0 ? `₹${(previewData.candles.reduce((acc: number, c: any) => acc + c.close, 0) / previewData.candles.length).toFixed(2)}` : "N/A" },
              { label: "Price Range (Min - Max)", value: previewData.candles.length > 0 ? `₹${Math.min(...previewData.candles.map((c: any) => c.close)).toFixed(1)} - ₹${Math.max(...previewData.candles.map((c: any) => c.close)).toFixed(1)}` : "N/A" }
            ].map((stat, i) => (
              <div key={i} className="flex flex-col">
                <span className="text-[10px] text-[#606060] uppercase font-bold tracking-wider">{stat.label}</span>
                <span className="text-xs font-semibold text-[#888] mt-1 font-mono">{stat.value}</span>
              </div>
            ))}
          </div>

          {/* Main Preview Tab Content */}
          <div className="flex-1 min-h-[400px]">
            {previewTab === "chart" ? (
              <div className="h-[400px] w-full rounded-xl overflow-hidden bg-[#111]">
                <LightweightChart candles={previewData.candles} height={400} showEmaFast={false} showEmaSlow={false} />
              </div>
            ) : (
              <div className="max-h-[400px] overflow-auto rounded-xl border border-[var(--ax-border)]/80 bg-[#111]/20 custom-scrollbar">
                <table className="w-full text-left text-xs text-[#a0a0a0] border-collapse">
                  <thead>
                    <tr className="sticky top-0 bg-[#161616] border-b border-[var(--ax-border)] text-[#888] font-semibold shadow-[0_1px_0_rgba(255,255,255,0.05)]">
                      <th className="p-3">Time / Date</th>
                      <th className="p-3 text-right">Open (₹)</th>
                      <th className="p-3 text-right">High (₹)</th>
                      <th className="p-3 text-right">Low (₹)</th>
                      <th className="p-3 text-right">Close (₹)</th>
                      <th className="p-3 text-right">Volume</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--ax-border)]/40 font-mono">
                    {previewData.candles.slice(0, 50).map((c: any, index: number) => (
                      <tr key={index} className="hover:bg-[#161616]/30">
                        <td className="p-3 text-[#888]">{formatTimeLabel(c.time, previewData.interval)}</td>
                        <td className="p-3 text-right">₹{Number(c.open).toFixed(2)}</td>
                        <td className="p-3 text-right text-emerald-400">₹{Number(c.high).toFixed(2)}</td>
                        <td className="p-3 text-right text-rose-400">₹{Number(c.low).toFixed(2)}</td>
                        <td className="p-3 text-right text-[#c0c0c0]">₹{Number(c.close).toFixed(2)}</td>
                        <td className="p-3 text-right text-[#a0a0a0]">{Number(c.volume || 0).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {previewData.candles.length > 50 && (
                  <div className="p-3 text-center text-[10px] text-[#606060] bg-[#111]/20 border-t border-[var(--ax-border)]/30">
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
