"use client";

import { PieChart, BarChart3 } from "lucide-react";

export function OptimizerTab({
  optParamName1, setOptParamName1, optParamVals1, setOptParamVals1,
  optParamName2, setOptParamName2, optParamVals2, setOptParamVals2,
  handleRunOptimization, optimizationGrid,
}: any) {
  return (
    <div className="space-y-6">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 space-y-4">
        <h4 className="font-semibold text-[#f0f0f0] text-sm">Parameter Sweeps Grid Search Config</h4>
        <p className="text-xs text-[#a0a0a0]">
          Run parallel sweeps on strategy attributes to evaluate parameter combos.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
          <div>
            <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-1">Parameter 1 Name</label>
            <input type="text" value={optParamName1} onChange={e => setOptParamName1(e.target.value)} className="w-full text-xs bg-[#111] border border-[#2a2a2a] rounded px-2.5 py-1.5 text-[#c0c0c0]" />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-1">P1 Range Values</label>
            <input type="text" value={optParamVals1} onChange={e => setOptParamVals1(e.target.value)} className="w-full text-xs bg-[#111] border border-[#2a2a2a] rounded px-2.5 py-1.5 text-[#c0c0c0] font-mono" />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-1">Parameter 2 Name</label>
            <input type="text" value={optParamName2} onChange={e => setOptParamName2(e.target.value)} className="w-full text-xs bg-[#111] border border-[#2a2a2a] rounded px-2.5 py-1.5 text-[#c0c0c0]" />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-1">P2 Range Values</label>
            <input type="text" value={optParamVals2} onChange={e => setOptParamVals2(e.target.value)} className="w-full text-xs bg-[#111] border border-[#2a2a2a] rounded px-2.5 py-1.5 text-[#c0c0c0] font-mono" />
          </div>
          <button onClick={handleRunOptimization} className="bg-[#4a7fcc] hover:bg-[#5a8fd0] text-[#f0f0f0] rounded font-bold text-xs py-2 transition-all">
            Execute Grid Sweep
          </button>
        </div>
      </div>

      {optimizationGrid ? (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 space-y-4">
              <h4 className="font-semibold text-[#f0f0f0] text-sm">Optimization Grid Results Matrix</h4>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="bg-[#161616]">
                      <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider text-left">Combo Parameters</th>
                      <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider text-left">CAGR Return</th>
                      <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider text-left">Sharpe Ratio</th>
                      <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider text-left">Max Drawdown</th>
                      <th className="py-2.5 px-3 text-[11px] font-medium text-[#606060] uppercase tracking-wider text-left">Trades Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {optimizationGrid.results.map((row: any, i: number) => (
                      <tr key={i} className="bg-[#1a1a1a] border-b border-[#222] hover:bg-[#1e1e1e]">
                        <td className="py-3 px-3 text-[12px] text-[#c0c0c0] font-mono font-bold text-[#93b4ff]">{JSON.stringify(row.parameters)}</td>
                        <td className="py-3 px-3 text-[12px] text-[#c0c0c0] font-mono">{(row.cagr * 100).toFixed(1)}%</td>
                        <td className="py-3 px-3 text-[12px] text-[#c0c0c0] font-mono font-semibold">{row.sharpe.toFixed(2)}</td>
                        <td className="py-3 px-3 text-[12px] text-[#c0c0c0] font-mono">{(row.max_drawdown * 100).toFixed(1)}%</td>
                        <td className="py-3 px-3 text-[12px] text-[#c0c0c0] font-mono">{row.total_trades ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 col-span-2 flex items-center justify-center">
              <div className="text-center">
                <BarChart3 size={32} className="text-[#505050] mx-auto mb-2" />
                <p className="text-[11px] text-[#505050]">3D Surface Plot — coming soon</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="bg-[#1a1a1a] border border-[#2a2a2a] border-l-[3px] border-l-emerald-500 rounded-r-xl rounded-l-none p-4">
              <span className="text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2 block">Best Parameter Configuration</span>
              {optimizationGrid.best_result ? (
                <div className="space-y-3">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-[#606060] block">Parameters</span>
                    <h4 className="text-sm font-mono font-bold text-emerald-400 mt-0.5">{JSON.stringify(optimizationGrid.best_result.parameters)}</h4>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-[#2a2a2a]">
                    <div>
                      <span className="text-[#606060] block text-[9px] uppercase font-bold">Sharpe</span>
                      <span className="font-bold text-[#c0c0c0] font-mono">{optimizationGrid.best_result.sharpe.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-[#606060] block text-[9px] uppercase font-bold">CAGR</span>
                      <span className="font-bold text-[#c0c0c0] font-mono">{(optimizationGrid.best_result.cagr * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                </div>
              ) : (
                <span className="text-xs text-[#505050]">Grid failed or returned no successes.</span>
              )}
            </div>
            <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
              <span className="text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2 block">Robustness Score</span>
              <p className="text-[22px] font-semibold text-[#f0f0f0] leading-none">N/A</p>
            </div>
            <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
              <span className="text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-2 block">Overfit Detection</span>
              <p className="text-[22px] font-semibold text-[#f0f0f0] leading-none">N/A</p>
            </div>
          </div>

          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
            <h4 className="font-semibold text-[#f0f0f0] text-sm mb-3">Walk-Forward Analysis</h4>
            <div className="h-48 flex items-center justify-center">
              <p className="text-[11px] text-[#505050]">Walk-forward chart — coming soon</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-8 text-center text-[#505050]">
          <PieChart size={32} className="mx-auto mb-2 text-[#a0a0a0] animate-pulse" />
          <span className="text-xs">Configure and execute sweep to display parameter performance surface values.</span>
        </div>
      )}
    </div>
  );
}
