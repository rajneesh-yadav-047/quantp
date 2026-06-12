"use client";

import { Rocket, Plus, Code, Trash2 } from "lucide-react";

export function DeploymentsTab({
  deploymentFormOpen, setDeploymentFormOpen,
  depStrategyId, setDepStrategyId, depName, setDepName, depSymbol, setDepSymbol, depMode, setDepMode,
  handleCreateDeployment, handleDeleteDeployment, strategies, deployments,
}: any) {
  return (
    <div className="space-y-6">
      <div className="glass-panel p-5 rounded-xl">
        <div className="flex items-center justify-between mb-4">
          <h4 className="font-bold text-slate-200 flex items-center gap-2">
            <Rocket size={18} className="text-blue-400" />
            Deployments
          </h4>
          <button
            onClick={() => setDeploymentFormOpen(!deploymentFormOpen)}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-bold transition-all flex items-center gap-1"
          >
            <Plus size={14} /> New Deployment
          </button>
        </div>

        {deploymentFormOpen && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4 p-4 bg-slate-950/40 rounded-lg border border-slate-800">
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Strategy</label>
              <select value={depStrategyId} onChange={e => setDepStrategyId(e.target.value)} className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200">
                <option value="">-- Select --</option>
                {strategies.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Name</label>
              <input type="text" value={depName} onChange={e => setDepName(e.target.value)} placeholder="Deployment #1" className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200" />
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Symbol (optional)</label>
              <input type="text" value={depSymbol} onChange={e => setDepSymbol(e.target.value.toUpperCase())} placeholder="All symbols" className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200" />
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Mode</label>
              <div className="flex gap-1">
                {["paper", "live"].map(m => (
                  <button
                    key={m}
                    onClick={() => setDepMode(m)}
                    className={`flex-1 text-[10px] font-bold border rounded py-1.5 transition-all ${depMode === m ? "bg-blue-600/15 border-blue-500 text-blue-400" : "border-slate-800 text-slate-400 bg-slate-950/50"}`}
                  >
                    {m.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            <div className="md:col-span-4 flex justify-end">
              <button onClick={handleCreateDeployment} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs font-bold transition-all">
                Create Deployment
              </button>
            </div>
          </div>
        )}

        <div className="space-y-4">
          {strategies.map((strategy: any) => {
            const strategyDeployments = deployments.filter((d: any) => d.strategy_id === strategy.id);
            if (strategyDeployments.length === 0) return null;
            return (
              <div key={strategy.id} className="border border-slate-800 rounded-lg overflow-hidden">
                <div className="px-4 py-2 bg-slate-950/60 border-b border-slate-800 flex items-center gap-2">
                  <Code size={14} className="text-blue-400" />
                  <span className="text-xs font-bold text-slate-200">{strategy.name}</span>
                  <span className="text-[10px] text-slate-500">({strategy.interval})</span>
                </div>
                <div className="divide-y divide-slate-800/50">
                  {strategyDeployments.map((dep: any) => (
                    <div key={dep.id} className="px-4 py-3 flex items-center justify-between hover:bg-slate-900/30">
                      <div className="flex items-center gap-3">
                        <div className={`h-2 w-2 rounded-full ${dep.status === "active" ? "bg-emerald-500" : dep.status === "paused" ? "bg-amber-500" : "bg-rose-500"}`} />
                        <div>
                          <div className="text-xs font-bold text-slate-200">{dep.name}</div>
                          <div className="text-[10px] text-slate-500">
                            {dep.symbol || "All symbols"} • {dep.mode.toUpperCase()} • {dep.status}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => handleDeleteDeployment(dep.id)} className="p-1.5 text-rose-400 hover:bg-rose-950/30 rounded transition-all" title="Delete">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
          {deployments.length === 0 && (
            <div className="text-center py-8 text-slate-500">
              <Rocket size={32} className="mx-auto mb-2 text-slate-700" />
              <p className="text-xs">No deployments yet. Create one to deploy a strategy.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
