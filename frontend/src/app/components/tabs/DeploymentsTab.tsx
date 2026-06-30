"use client";

import { Rocket, Plus, Code, Trash2, Activity } from "lucide-react";

export function DeploymentsTab({
  deploymentFormOpen, setDeploymentFormOpen,
  depStrategyId, setDepStrategyId, depName, setDepName, depSymbol, setDepSymbol, depMode, setDepMode,
  handleCreateDeployment, handleDeleteDeployment, strategies, deployments,
}: any) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h4 className="font-bold text-[#f0f0f0] flex items-center gap-2">
          <Rocket size={18} className="text-[#93b4ff]" />
          Deployments
        </h4>
        <button
          onClick={() => setDeploymentFormOpen(!deploymentFormOpen)}
          className="px-3 py-1.5 bg-[#4a7fcc] hover:bg-[#5a8fd0] text-[#f0f0f0] rounded text-xs font-bold transition-all flex items-center gap-1"
        >
          <Plus size={14} /> New Deployment
        </button>
      </div>

      {deploymentFormOpen && (
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-1">Strategy</label>
              <select value={depStrategyId} onChange={e => setDepStrategyId(e.target.value)} className="w-full text-xs bg-[#111] border border-[#2a2a2a] rounded px-2.5 py-1.5 text-[#c0c0c0]">
                <option value="">-- Select --</option>
                {strategies.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-1">Name</label>
              <input type="text" value={depName} onChange={e => setDepName(e.target.value)} placeholder="Deployment #1" className="w-full text-xs bg-[#111] border border-[#2a2a2a] rounded px-2.5 py-1.5 text-[#c0c0c0]" />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-1">Symbol (optional)</label>
              <input type="text" value={depSymbol} onChange={e => setDepSymbol(e.target.value.toUpperCase())} placeholder="All symbols" className="w-full text-xs bg-[#111] border border-[#2a2a2a] rounded px-2.5 py-1.5 text-[#c0c0c0]" />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-[#606060] uppercase tracking-wider mb-1">Mode</label>
              <div className="flex gap-1">
                {["paper", "live"].map(m => (
                  <button
                    key={m}
                    onClick={() => setDepMode(m)}
                    className={`flex-1 text-[10px] font-bold border rounded py-1.5 transition-all ${depMode === m ? "bg-[#1c2030] border-[#4a7fcc] text-[#93b4ff]" : "border-[#2a2a2a] text-[#a0a0a0] bg-[#111]/50"}`}
                  >
                    {m.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            <div className="md:col-span-4 flex justify-end">
              <button onClick={handleCreateDeployment} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-[#f0f0f0] rounded text-xs font-bold transition-all">
                Create Deployment
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
        <div className="space-y-4">
          {strategies.map((strategy: any) => {
            const strategyDeployments = deployments.filter((d: any) => d.strategy_id === strategy.id);
            if (strategyDeployments.length === 0) return null;
            return (
              <div key={strategy.id} className="rounded-lg border border-[#2a2a2a] overflow-hidden">
                <div className="px-4 py-2 bg-[#161616] border-b border-[#222] flex items-center gap-2">
                  <Code size={14} className="text-[#93b4ff]" />
                  <span className="text-xs font-bold text-[#d0d0d0]">{strategy.name}</span>
                  <span className="text-[10px] text-[#505050]">({strategy.interval})</span>
                </div>
                <div>
                  {strategyDeployments.map((dep: any) => (
                    <div key={dep.id} className="bg-[#1a1a1a] border-b border-[#222] px-4 py-3 flex items-center gap-3 hover:bg-[#1e1e1e]">
                      <div className="w-8 h-8 rounded-lg bg-[#222] flex items-center justify-center text-[#93b4ff] shrink-0">
                        {dep.status === "active" ? <Activity size={14} /> : <Rocket size={14} />}
                      </div>
                      <div>
                        <div className="text-[13px] font-medium text-[#d0d0d0]">{dep.name}</div>
                        <div className="text-[11px] text-[#505050]">
                          {dep.symbol || "All symbols"} · {dep.mode.toUpperCase()} · {dep.status}
                        </div>
                      </div>
                      <div className="ml-auto flex items-center gap-2">
                        <div className={`h-2 w-2 rounded-full ${dep.status === "active" ? "bg-emerald-500" : dep.status === "paused" ? "bg-amber-500" : "bg-rose-500"}`} />
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
            <div className="text-center py-8 text-[#505050]">
              <Rocket size={32} className="mx-auto mb-2 text-[#a0a0a0]" />
              <p className="text-xs">No deployments yet. Create one to deploy a strategy.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
