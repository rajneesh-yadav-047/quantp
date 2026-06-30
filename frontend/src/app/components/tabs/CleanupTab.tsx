"use client";

import { Trash2, RefreshCw, Database, FileText } from "lucide-react";

export function CleanupTab({
  cleanupStatus, cleanupLoading, cleanupDryRun, setCleanupDryRun,
  cleanupTarget, setCleanupTarget, cleanupSymbol, setCleanupSymbol,
  cleanupInterval, setCleanupInterval, cleanupOlderThan, setCleanupOlderThan,
  cleanupStrategyId, setCleanupStrategyId, cleanupResult,
  fetchCleanupStatus, handleRunCleanup, handleVacuumDB,
}: any) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 rounded-xl">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-[#a0a0a0] font-medium">CSV Datasets</span>
            <Database size={16} className="text-[#93b4ff]" />
          </div>
          <h3 className="text-lg font-bold text-[#e8e8e8]">{cleanupStatus?.datasets_csv?.size_human || "--"}</h3>
        </div>
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 rounded-xl">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-[#a0a0a0] font-medium">Backtest Logs</span>
            <FileText size={16} className="text-amber-400" />
          </div>
          <h3 className="text-lg font-bold text-[#e8e8e8]">{cleanupStatus?.logs?.size_human || "--"}</h3>
        </div>
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 rounded-xl">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-[#a0a0a0] font-medium">SQLite Database</span>
            <Database size={16} className="text-emerald-400" />
          </div>
          <h3 className="text-lg font-bold text-[#e8e8e8]">{cleanupStatus?.database?.size_human || "--"}</h3>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5 rounded-xl space-y-4">
          <h4 className="font-bold text-[#c0c0c0] flex items-center gap-2">
            <Trash2 size={18} className="text-rose-400" />
            Cleanup Controls
          </h4>
          <div>
            <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">Target</label>
            <select value={cleanupTarget} onChange={e => setCleanupTarget(e.target.value)} className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0]">
              <option value="logs">Backtest Logs Only</option>
              <option value="csv">CSV Datasets Only</option>
              <option value="strategies">Strategy Files Only</option>
              <option value="all">Logs + CSV + Strategies (ALL)</option>
              <option value="db_orphans">DB Orphan Records Only</option>
            </select>
          </div>
          {(cleanupTarget === "csv" || cleanupTarget === "all") && (
            <>
              <div>
                <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">Symbol Filter (optional)</label>
                <input type="text" value={cleanupSymbol} onChange={e => setCleanupSymbol(e.target.value.toUpperCase())} placeholder="e.g. SBIN" className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0]" />
              </div>
              <div>
                <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">Interval Filter (optional)</label>
                <select value={cleanupInterval} onChange={e => setCleanupInterval(e.target.value)} className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0]">
                  <option value="">-- Any Interval --</option>
                  <option value="ONE_MINUTE">1 Minute</option>
                  <option value="FIVE_MINUTE">5 Minute</option>
                  <option value="FIFTEEN_MINUTE">15 Minute</option>
                  <option value="ONE_HOUR">1 Hour</option>
                  <option value="ONE_DAY">Daily</option>
                </select>
              </div>
            </>
          )}
          {(cleanupTarget === "strategies" || cleanupTarget === "all") && (
            <div>
              <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">Strategy ID Filter (optional)</label>
              <input type="text" value={cleanupStrategyId} onChange={e => setCleanupStrategyId(e.target.value.trim())} placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000" className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0]" />
            </div>
          )}
          <div>
            <label className="block text-[10px] uppercase font-bold text-[#a0a0a0] mb-1">Older Than (days, optional)</label>
            <input type="number" min="1" value={cleanupOlderThan} onChange={e => setCleanupOlderThan(e.target.value ? Number(e.target.value) : "")} placeholder="e.g. 7" className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2.5 py-1.5 text-[#c0c0c0]" />
          </div>
          <div className="flex items-center gap-3 p-3 bg-[#111]/50 rounded border border-[var(--ax-border)]">
            <input id="dryRun" type="checkbox" checked={cleanupDryRun} onChange={e => setCleanupDryRun(e.target.checked)} className="h-4 w-4 accent-blue-500" />
            <label htmlFor="dryRun" className="text-xs text-[#888] cursor-pointer select-none">
              <span className="font-bold">Dry-Run Mode</span> — Preview deletions without actually deleting
            </label>
          </div>
          <div className="space-y-2 pt-2">
            <button onClick={handleRunCleanup} disabled={cleanupLoading} className={`w-full rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2 ${cleanupDryRun ? "bg-[#161616] hover:bg-[#222] text-[#c0c0c0] border border-[var(--ax-border)]" : "bg-rose-600 hover:bg-rose-700 text-[#f0f0f0]"}`}>
              {cleanupLoading ? <RefreshCw size={14} className="animate-spin" /> : cleanupDryRun ? <><RefreshCw size={14} /> Preview Cleanup</> : <><Trash2 size={14} /> Execute Cleanup</>}
            </button>
            <button onClick={handleVacuumDB} disabled={cleanupLoading} className="w-full bg-[#161616] hover:bg-[#222] text-[#c0c0c0] border border-[var(--ax-border)] rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2">
              {cleanupLoading ? <RefreshCw size={14} className="animate-spin" /> : <><Database size={14} /> {cleanupDryRun ? "Preview Vacuum DB" : "Vacuum Database"}</>}
            </button>
            <button onClick={fetchCleanupStatus} disabled={cleanupLoading} className="w-full bg-[#1c2030] hover:bg-[#232a40] text-[#93b4ff] border border-[#2a3a5a] rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2">
              <RefreshCw size={14} /> Refresh Status
            </button>
          </div>
        </div>

        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5 rounded-xl col-span-2 space-y-4">
          <h4 className="font-bold text-[#c0c0c0] text-sm">Cleanup Results</h4>
          {!cleanupResult && !cleanupStatus && (
            <div className="p-8 text-center text-[#606060]">
              <Trash2 size={32} className="mx-auto mb-2 text-[#a0a0a0]" />
              <span className="text-xs">Click "Refresh Status" to load disk usage, or run a cleanup preview.</span>
            </div>
          )}
          {cleanupStatus && (
            <div className="space-y-3">
              <div className="p-3 bg-[#111]/60 rounded border border-[var(--ax-border)]">
                <span className="text-[10px] uppercase font-bold text-[#606060]">Total Disk Usage</span>
                <h3 className="text-xl font-bold text-[#c0c0c0] font-mono mt-0.5">{cleanupStatus.total_human}</h3>
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs">
                {["datasets_csv", "logs", "strategies", "database", "backend_log", "backend_restart_log"].map(key => (
                  <div key={key} className="p-2 bg-[#111] rounded border border-[var(--ax-border)]">
                    <span className="text-[#606060] block text-[9px] uppercase font-bold">{key.replace(/_/g, " ")}</span>
                    <span className="font-mono text-[#888]">{cleanupStatus[key]?.size_human || "--"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {cleanupResult && (
            <div className="space-y-3">
              <div className={`p-3 rounded border ${cleanupResult.dry_run ? "bg-[var(--ax-atm)]/30 border-[#2a3a5a]" : "bg-emerald-950/30 border-emerald-800"}`}>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-[#a0a0a0]">{cleanupResult.dry_run ? "Dry-Run Preview" : "Cleanup Executed"}</span>
                  <span className="text-xs font-bold font-mono text-[#c0c0c0]">{cleanupResult.bytes_freed_human} freed</span>
                </div>
                <div className="text-xs text-[#888] mt-1">Files deleted: <span className="font-mono font-bold">{cleanupResult.files_deleted}</span></div>
              </div>
              {cleanupResult.details && cleanupResult.details.length > 0 && (
                <div className="max-h-64 overflow-y-auto space-y-1 p-2 bg-[#111] rounded border border-[var(--ax-border)]">
                  {cleanupResult.details.map((detail: string, i: number) => (
                    <div key={i} className="text-[11px] font-mono text-[#a0a0a0] py-0.5 border-b border-[var(--ax-border)]/30 last:border-0">{detail}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
