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
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between px-1">
          <h4 className="text-[11px] font-medium text-[#606060] uppercase tracking-wider">Strategies</h4>
          <button onClick={handleNewStrategy} className="w-8 h-8 rounded-lg bg-[#222] hover:bg-[#2a2a2a] text-[#93b4ff] flex items-center justify-center transition-all" title="New Strategy">
            <Plus size={14} />
          </button>
        </div>
        <div className="space-y-2 max-h-96 overflow-y-auto pr-1 custom-scrollbar">
          {strategies.map((s: any) => (
            <div
              key={s.id}
              onClick={() => handleSelectStrategy(s.id)}
              className={`bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-4 py-3 flex items-center gap-3 cursor-pointer transition-all ${
                selectedStrategyId === s.id ? "border-l-[3px] border-l-[#4a7fcc] rounded-l-none" : "hover:bg-[#1e1e1e]"
              }`}
            >
              <div className="w-8 h-8 rounded-lg bg-[#222] flex items-center justify-center text-[#93b4ff] shrink-0">
                <Code size={16} />
              </div>
              <div className="min-w-0">
                <div className="text-[13px] font-medium text-[#d0d0d0]">{s.name}</div>
                <div className="text-[11px] text-[#505050]">
                  {(s.symbols || []).join(", ")} · {s.interval} · v{s.version}
                </div>
              </div>
            </div>
          ))}
          {strategies.length === 0 && (
            <p className="text-[11px] text-[#505050] text-center py-4">No strategies stored yet.</p>
          )}
        </div>
        <div className="mt-auto pt-4 border-t border-[#2a2a2a] space-y-3">
          <button
            onClick={() => { if (selectedStrategyId) { setActiveTab("backtests"); } else { triggerNotif("info", "Select or save a strategy first."); } }}
            disabled={!selectedStrategyId}
            className="w-full bg-[#1a1a1a] hover:bg-[#1e1e1e] disabled:bg-[#161616] disabled:text-[#606060] text-[#c0c0c0] border border-[#2a2a2a] rounded-xl font-medium text-[12px] py-2.5 transition-all flex items-center justify-center gap-2"
          >
            <PlayCircle size={14} /> Run Backtest
          </button>
        </div>
      </div>

      {/* Main area: Editor + Config */}
      <div className="col-span-3 flex gap-4 h-full min-h-0">
        {/* Editor area */}
        <div className="flex-[3] bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl flex flex-col overflow-hidden min-h-0">
          {/* Upload area */}
          <div className="p-4 border-b border-[#2a2a2a]">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-[12px] font-medium text-[#c0c0c0] flex items-center gap-2">
                <Code size={16} className="text-[#93b4ff]" /> Strategy Code
              </h4>
              {uploadedFileName && (
                <span className="text-[11px] font-mono text-emerald-400 bg-[#0d1a10] border border-[#1a3a20] px-2 py-1 rounded">{uploadedFileName}</span>
              )}
            </div>
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-[#2a2a2a] hover:border-[#4a7fcc] rounded-xl p-4 text-center cursor-pointer transition-colors bg-[#161616]/50"
            >
              <input ref={fileInputRef} type="file" accept=".py" onChange={handleFileUpload} className="hidden" />
              <div className="flex flex-col items-center gap-1">
                <div className="p-2 bg-[#222] rounded-full"><FileText size={20} className="text-[#606060]" /></div>
                <p className="text-[13px] font-medium text-[#888]">Click to upload a <span className="text-[#93b4ff] font-bold">.py</span> strategy file</p>
                <p className="text-[11px] text-[#505050]">Or drag and drop. Max file size ~1 MB.</p>
              </div>
            </div>
          </div>

          {/* Code preview */}
          <div className="flex-1 min-h-0 bg-[#1e1e1e] overflow-auto">
            {code ? (
              <pre className="p-4 text-xs font-mono text-[#888] leading-relaxed whitespace-pre-wrap">{code}</pre>
            ) : (
              <div className="h-full flex items-center justify-center text-[#505050]">
                <div className="text-center">
                  <Code size={32} className="mx-auto mb-2 text-[#606060]" />
                  <p className="text-[13px]">Upload a .py file or paste code to preview</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Config panel */}
        <div className="flex-[1] flex flex-col gap-3 min-h-0 overflow-y-auto custom-scrollbar">
          {/* Strategy Name */}
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
            <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Strategy Name</label>
            <input
              type="text" value={strategyName} onChange={e => setStrategyName(e.target.value)}
              placeholder="Mean Reversion"
              className="w-full text-[12px] bg-[#161616] border border-[#2a2a2a] rounded-lg px-3 py-2 text-[#c0c0c0] focus:outline-none focus:border-[#4a7fcc] font-medium"
            />
          </div>

          {/* Symbol / Interval */}
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 space-y-3">
            <div className="relative">
              <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Symbols</label>
              <input
                type="text" value={strategySymbols}
                onChange={e => { setStrategySymbols(e.target.value.toUpperCase()); setShowStrategySuggestions(true); }}
                onFocus={() => setShowStrategySuggestions(true)}
                onBlur={() => setTimeout(() => setShowStrategySuggestions(false), 200)}
                placeholder="SBIN, AFC, IDE"
                className="w-full text-[12px] bg-[#161616] border border-[#2a2a2a] rounded-lg px-3 py-2 text-[#c0c0c0] focus:outline-none focus:border-[#4a7fcc] font-medium"
              />
              {showStrategySuggestions && strategySuggestions.length > 0 && (
                <div className="absolute z-50 w-full mt-1 max-h-60 overflow-y-auto bg-[#161616] border border-[#2a2a2a] rounded-lg shadow-2xl divide-y divide-[#2a2a2a] custom-scrollbar">
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
                      className="px-3 py-2 text-[12px] hover:bg-[#1e1e1e] cursor-pointer flex justify-between items-center transition-colors duration-150"
                    >
                      <div className="flex flex-col">
                        <span className="font-medium text-[#c0c0c0]">{s.symbol}</span>
                        <span className="text-[10px] text-[#505050] truncate max-w-[160px]">{s.name}</span>
                      </div>
                      <span className="text-[10px] font-mono bg-[#222] border border-[#2a2a2a] rounded px-1.5 py-0.5 text-[#a0a0a0]">{s.token}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Interval</label>
              <select value={strategyInterval} onChange={e => setStrategyInterval(e.target.value)} className="w-full text-[12px] bg-[#161616] border border-[#2a2a2a] rounded-lg px-3 py-2 text-[#c0c0c0] focus:outline-none focus:border-[#4a7fcc]">
                <option value="ONE_MINUTE">1 Minute</option>
                <option value="FIVE_MINUTE">5 Minute</option>
                <option value="FIFTEEN_MINUTE">15 Minute</option>
                <option value="ONE_HOUR">1 Hour</option>
                <option value="ONE_DAY">Daily</option>
              </select>
            </div>
          </div>

          {/* Capital / Risk */}
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 space-y-3">
            <div>
              <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Initial Capital (₹)</label>
              <input type="number" value={strategyCapital} onChange={e => setStrategyCapital(Number(e.target.value))} className="w-full text-[12px] bg-[#161616] border border-[#2a2a2a] rounded-lg px-3 py-2 text-[#c0c0c0] focus:outline-none" />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Max Position Size</label>
              <input type="number" value={strategyMaxPos} onChange={e => setStrategyMaxPos(Number(e.target.value))} placeholder="Auto = 0" className="w-full text-[12px] bg-[#161616] border border-[#2a2a2a] rounded-lg px-3 py-2 text-[#c0c0c0] focus:outline-none" />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Runtime Type</label>
              <select value={strategyRuntimeType} onChange={e => setStrategyRuntimeType(e.target.value)} className="w-full text-[12px] bg-[#161616] border border-[#2a2a2a] rounded-lg px-3 py-2 text-[#c0c0c0] focus:outline-none focus:border-[#4a7fcc]">
                <option value="legacy_on_bar">Legacy On-Bar</option>
                <option value="prosperity_trader">Prosperity Trader</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Entrypoint</label>
              <input type="text" value={strategyEntrypoint || ""} onChange={e => setStrategyEntrypoint(e.target.value || null)} placeholder="e.g., trader.py:Trader" className="w-full text-[12px] bg-[#161616] border border-[#2a2a2a] rounded-lg px-3 py-2 text-[#c0c0c0] focus:outline-none focus:border-[#4a7fcc]" />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2">Parameters (JSON)</label>
              <input type="text" value={strategyParams} onChange={e => setStrategyParams(e.target.value)} placeholder='{"ema_fast": 9}' className="w-full text-[12px] bg-[#161616] border border-[#2a2a2a] rounded-lg px-3 py-2 text-[#c0c0c0] focus:outline-none font-mono" />
            </div>
          </div>

          <button
            onClick={handleSaveStrategy}
            disabled={!code || !strategyName}
            className="w-full bg-[#1c2030] hover:bg-[#222d40] disabled:bg-[#161616] disabled:text-[#606060] text-[#93b4ff] border border-[#2a3a5a] rounded-xl font-medium text-[12px] py-2.5 transition-all flex items-center justify-center gap-2"
          >
            <FileText size={14} /> Save to Database
          </button>
        </div>
      </div>
    </div>
  );
}
