"use client";

import { PieChart, Settings } from "lucide-react";

export function OptimizerTab({
  optParamName1, setOptParamName1, optParamVals1, setOptParamVals1,
  optParamName2, setOptParamName2, optParamVals2, setOptParamVals2,
  handleRunOptimization, optimizationGrid,
}: any) {
  return (
    <div className="space-y-6">
      <div className="glass-panel p-5 rounded-xl space-y-4">
        <h4 className="font-bold text-slate-200 text-sm">Parameter Sweeps Grid Search Config</h4>
        <p className="text-xs text-slate-400">
          Run parallel sweeps on strategy attributes to evaluate parameter combos.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Parameter 1 Name</label>
            <input type="text" value={optParamName1} onChange={e => setOptParamName1(e.target.value)} className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200" />
          </div>
          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">P1 Range Values</label>
            <input type="text" value={optParamVals1} onChange={e => setOptParamVals1(e.target.value)} className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-mono" />
          </div>
          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Parameter 2 Name</label>
            <input type="text" value={optParamName2} onChange={e => setOptParamName2(e.target.value)} className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200" />
          </div>
          <div>
            <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">P2 Range Values</label>
            <input type="text" value={optParamVals2} onChange={e => setOptParamVals2(e.target.value)} className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 font-mono" />
          </div>
          <button onClick={handleRunOptimization} className="bg-blue-600 hover:bg-blue-700 text-white rounded font-bold text-xs py-2 transition-all">
            Execute Grid Sweep
          </button>
        </div>
      </div>

      {optimizationGrid ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="glass-panel p-5 rounded-xl col-span-2 space-y-4">
            <h4 className="font-bold text-slate-200 text-sm">Optimization Grid Results Matrix</h4>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-400 border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-300 font-medium">
                    <th className="py-2.5">Combo Parameters</th>
                    <th>CAGR Return</th>
                    <th>Sharpe Ratio</th>
                    <th>Max Drawdown</th>
                    <th>Trades Count</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {optimizationGrid.results.map((row: any, i: number) => (
                    <tr key={i} className="hover:bg-slate-900/30">
                      <td className="py-3 font-mono font-bold text-blue-400">{JSON.stringify(row.parameters)}</td>
                      <td className="font-mono">{(row.cagr * 100).toFixed(1)}%</td>
                      <td className="font-mono font-semibold text-slate-200">{row.sharpe.toFixed(2)}</td>
                      <td className="font-mono">{(row.max_drawdown * 100).toFixed(1)}%</td>
                      <td className="font-mono text-slate-500">{row.total_trades ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="glass-panel p-5 rounded-xl space-y-4 self-start">
            <h4 className="font-bold text-slate-200 text-sm">Best Parameter Configuration</h4>
            {optimizationGrid.best_result ? (
              <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-3">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-500">Parameters</span>
                  <h4 className="text-sm font-mono font-bold text-emerald-400 mt-0.5">{JSON.stringify(optimizationGrid.best_result.parameters)}</h4>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-slate-800">
                  <div>
                    <span className="text-slate-500 block text-[9px] uppercase font-bold">Sharpe</span>
                    <span className="font-bold text-slate-200 font-mono">{optimizationGrid.best_result.sharpe.toFixed(2)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[9px] uppercase font-bold">CAGR</span>
                    <span className="font-bold text-slate-200 font-mono">{(optimizationGrid.best_result.cagr * 100).toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            ) : (
              <span className="text-xs text-slate-500">Grid failed or returned no successes.</span>
            )}
          </div>
        </div>
      ) : (
        <div className="glass-panel p-8 text-center text-slate-500 rounded-xl">
          <PieChart size={32} className="mx-auto mb-2 text-slate-700 animate-pulse" />
          <span className="text-xs">Configure and execute sweep to display parameter performance surface values.</span>
        </div>
      )}
    </div>
  );
}
