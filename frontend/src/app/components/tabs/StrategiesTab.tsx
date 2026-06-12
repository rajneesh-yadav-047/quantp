"use client";

import { Plus, FileText, Code, PlayCircle } from "lucide-react";

export function StrategiesTab({
  strategies, selectedStrategyId, handleSelectStrategy, handleNewStrategy, handleSaveStrategy, handleFileUpload,
  code, setCode, fileInputRef, uploadedFileName, setUploadedFileName,
  strategyName, setStrategyName, strategySymbols, setStrategySymbols, strategyInterval, setStrategyInterval,
  strategyCapital, setStrategyCapital, strategyMaxPos, setStrategyMaxPos,
  strategyRuntimeType, setStrategyRuntimeType, strategyEntrypoint, setStrategyEntrypoint,
  strategyParams, setStrategyParams, strategyRisk, setStrategyRisk,
  strategySuggestions, showStrategySuggestions, setShowStrategySuggestions, setActiveTab, triggerNotif,
}: any) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 h-full min-h-[500px]">
      {/* Strategy catalog sidebar */}
      <div className="glass-panel p-4 rounded-xl flex flex-col justify-between">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-bold text-slate-200 text-sm">Strategies</h4>
            <button onClick={handleNewStrategy} className="p-1 bg-slate-800 hover:bg-slate-700 text-blue-400 rounded transition-all" title="New Strategy">
              <Plus size={14} />
            </button>
          </div>
          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {strategies.map((s: any) => (
              <div
                key={s.id}
                onClick={() => handleSelectStrategy(s.id)}
                className={`p-2.5 rounded-lg border text-left cursor-pointer transition-all ${
                  selectedStrategyId === s.id ? "bg-blue-600/10 border-blue-500/50" : "border-slate-800/80 bg-slate-950/20 hover:bg-slate-900/50"
                }`}
              >
                <h5 className="font-semibold text-slate-200 text-xs">{s.name}</h5>
                <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                  {(s.symbols || []).join(", ")} • {s.interval} • v{s.version}
                </p>
              </div>
            ))}
            {strategies.length === 0 && (
              <p className="text-[10px] text-slate-500 text-center py-4">No strategies stored yet.</p>
            )}
          </div>
        </div>
        <div className="space-y-3 pt-4 border-t border-slate-800">
          <button
            onClick={handleSaveStrategy}
            disabled={!code || !strategyName}
            className="w-full bg-slate-800 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-600 text-slate-200 border border-slate-700 rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2"
          >
            <FileText size={14} /> Save to Database
          </button>
          <button
            onClick={() => { if (selectedStrategyId) { setActiveTab("backtests"); } else { triggerNotif("info", "Select or save a strategy first."); } }}
            disabled={!selectedStrategyId}
            className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2"
          >
            <PlayCircle size={14} /> Run Backtest
          </button>
        </div>
      </div>

      {/* Strategy Editor */}
      <div className="glass-panel rounded-xl col-span-3 flex flex-col overflow-hidden relative border border-slate-800">
        {/* Config Panel */}
        <div className="p-5 border-b border-slate-800 bg-slate-950/60">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Strategy Name</label>
              <input
                type="text" value={strategyName} onChange={e => setStrategyName(e.target.value)}
                placeholder="Mean Reversion"
                className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500 font-semibold"
              />
            </div>
            <div className="relative">
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Symbols (comma-separated)</label>
              <input
                type="text" value={strategySymbols}
                onChange={e => { setStrategySymbols(e.target.value.toUpperCase()); setShowStrategySuggestions(true); }}
                onFocus={() => setShowStrategySuggestions(true)}
                onBlur={() => setTimeout(() => setShowStrategySuggestions(false), 200)}
                placeholder="SBIN, AFC, IDE"
                className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500 font-semibold"
              />
              {showStrategySuggestions && strategySuggestions.length > 0 && (
                <div className="absolute z-50 w-full mt-1 max-h-60 overflow-y-auto bg-slate-950 border border-slate-800 rounded shadow-2xl divide-y divide-slate-800/60 custom-scrollbar">
                  {strategySuggestions.map((s: any) => (
                    <div
                      key={s.token}
                      onClick={() => {
                        const parts = strategySymbols.split(",").map((p: string) => p.trim()).filter(Boolean);
                        parts.pop();
                        parts.push(s.symbol);
                        setStrategySymbols(parts.join(", "));
                        setShowStrategySuggestions(false);
                      }}
                      className="px-3 py-2 text-xs hover:bg-slate-900 cursor-pointer flex justify-between items-center transition-colors duration-150"
                    >
                      <div className="flex flex-col">
                        <span className="font-semibold text-slate-200">{s.symbol}</span>
                        <span className="text-[9px] text-slate-500 truncate max-w-[160px]">{s.name}</span>
                      </div>
                      <span className="text-[9px] font-mono bg-slate-900 border border-slate-800/80 rounded px-1.5 py-0.5 text-slate-400">{s.token}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Interval</label>
              <select value={strategyInterval} onChange={e => setStrategyInterval(e.target.value)} className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500">
                <option value="ONE_MINUTE">1 Minute</option>
                <option value="FIVE_MINUTE">5 Minute</option>
                <option value="FIFTEEN_MINUTE">15 Minute</option>
                <option value="ONE_HOUR">1 Hour</option>
                <option value="ONE_DAY">Daily</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Initial Capital (₹)</label>
              <input type="number" value={strategyCapital} onChange={e => setStrategyCapital(Number(e.target.value))} className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none" />
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Max Position Size</label>
              <input type="number" value={strategyMaxPos} onChange={e => setStrategyMaxPos(Number(e.target.value))} placeholder="Auto = 0" className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none" />
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Runtime Type</label>
              <select value={strategyRuntimeType} onChange={e => setStrategyRuntimeType(e.target.value)} className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500">
                <option value="legacy_on_bar">Legacy On-Bar</option>
                <option value="prosperity_trader">Prosperity Trader</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Entrypoint</label>
              <input type="text" value={strategyEntrypoint || ""} onChange={e => setStrategyEntrypoint(e.target.value || null)} placeholder="e.g., trader.py:Trader" className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Parameters (JSON)</label>
              <input type="text" value={strategyParams} onChange={e => setStrategyParams(e.target.value)} placeholder='{"ema_fast": 9}' className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none font-mono" />
            </div>
          </div>
        </div>

        {/* Upload area */}
        <div className="p-4 border-b border-slate-800 bg-slate-950/40">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-bold text-slate-200 text-sm flex items-center gap-2">
              <Code size={16} className="text-blue-400" /> Strategy Code
            </h4>
            {uploadedFileName && (
              <span className="text-xs font-mono text-emerald-400 bg-emerald-950/30 px-2 py-1 rounded border border-emerald-800">{uploadedFileName}</span>
            )}
          </div>
          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-slate-700 hover:border-blue-500 rounded-xl p-4 text-center cursor-pointer transition-colors bg-slate-950/30"
          >
            <input ref={fileInputRef} type="file" accept=".py" onChange={handleFileUpload} className="hidden" />
            <div className="flex flex-col items-center gap-1">
              <div className="p-2 bg-slate-800 rounded-full"><FileText size={20} className="text-slate-400" /></div>
              <p className="text-sm font-medium text-slate-300">Click to upload a <span className="text-blue-400 font-bold">.py</span> strategy file</p>
              <p className="text-[10px] text-slate-500">Or drag and drop. Max file size ~1 MB.</p>
            </div>
          </div>
        </div>

        {/* Code preview */}
        <div className="flex-1 min-h-0 bg-[#1e1e1e] overflow-auto">
          {code ? (
            <pre className="p-4 text-xs font-mono text-slate-300 leading-relaxed whitespace-pre-wrap">{code}</pre>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-600">
              <div className="text-center">
                <Code size={32} className="mx-auto mb-2 text-slate-700" />
                <p className="text-sm">Upload a .py file or paste code to preview</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
