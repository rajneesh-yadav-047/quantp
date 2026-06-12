"use client";

import { Cpu, LayoutDashboard, Database, Code, PlayCircle, Rocket, Radio, FlaskConical, Settings, Trash2, CheckCircle2, AlertCircle } from "lucide-react";
import type { Notif } from "../../hooks/useQuantLab";

interface SidebarProps {
  activeTab: string;
  setActiveTab: (id: string) => void;
  notif: Notif | null;
  backendOnline: boolean;
  smartapiConnected: boolean;
  ollamaState: string;
  apiErrors: Record<string, { error: string; retry: () => void }>;
}

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "datasets", label: "Datasets", icon: Database },
  { id: "strategies", label: "Strategies", icon: Code },
  { id: "backtests", label: "Backtests", icon: PlayCircle },
  { id: "deployments", label: "Deployments", icon: Rocket },
  { id: "live", label: "Live Trading", icon: Radio, external: "/live" },
  { id: "research", label: "Research Lab", icon: FlaskConical },
  { id: "optimizer", label: "Optimizer", icon: Settings },
  { id: "cleanup", label: "Cleanup", icon: Trash2 },
];

export default function Sidebar({ activeTab, setActiveTab, notif, backendOnline, smartapiConnected, ollamaState, apiErrors }: SidebarProps) {
  return (
    <aside className="w-64 border-r border-slate-800 bg-[#0B0F19]/90 p-4 flex flex-col justify-between shrink-0">
      <div>
        {/* Logo */}
        <div className="flex items-center gap-3 px-2 py-3 mb-6">
          <div className="p-2 bg-blue-600 rounded-lg text-white shadow-[0_0_15px_rgba(59,130,246,0.5)]">
            <Cpu size={20} className="animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-300 bg-clip-text text-transparent">
              QuantLab
            </h1>
            <span className="text-xs text-slate-500 font-mono">v2.0.0-STRAT</span>
          </div>
        </div>

        {/* Nav Items */}
        <nav className="space-y-1">
          {navItems.map(item => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  if (item.external) { window.location.href = item.external; }
                  else { setActiveTab(item.id); }
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  active ? "bg-blue-600/15 text-blue-400 border-l-2 border-blue-500" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                }`}
              >
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Network and Status Indicators */}
      <div className="space-y-4 pt-4 border-t border-slate-800/80">
        {notif && (
          <div className={`p-2.5 rounded-lg border text-xs flex gap-2 items-center ${
            notif.type === "success" ? "bg-emerald-950/40 text-emerald-400 border-emerald-800/50" :
            notif.type === "error" ? "bg-rose-950/40 text-rose-400 border-rose-800/50" :
            "bg-slate-800/60 text-blue-400 border-blue-800/50"
          }`}>
            {notif.type === "success" ? <CheckCircle2 size={14} className="shrink-0" /> : <AlertCircle size={14} className="shrink-0" />}
            <p className="line-clamp-2">{notif.msg}</p>
          </div>
        )}

        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between px-1">
            <span className="text-slate-500">FastAPI Backend</span>
            <div className="flex items-center gap-1.5">
              <div className={`h-2 w-2 rounded-full ${backendOnline ? "bg-emerald-500 shadow-[0_0_8px_#10B981]" : "bg-amber-500 shadow-[0_0_8px_#F59E0B]"}`} />
              <span className="text-slate-300">{backendOnline ? "Online" : "Offline"}</span>
            </div>
          </div>
          <div className="flex items-center justify-between px-1">
            <span className="text-slate-500">SmartAPI Feed</span>
            <div className="flex items-center gap-1.5">
              <div className={`h-2 w-2 rounded-full ${smartapiConnected ? "bg-emerald-500 shadow-[0_0_8px_#10B981]" : "bg-slate-600"}`} />
              <span className="text-slate-300">{smartapiConnected ? "Connected" : "Disconnected"}</span>
            </div>
          </div>
          <div className="flex items-center justify-between px-1">
            <span className="text-slate-500">Ollama AI</span>
            <div className="flex items-center gap-1.5">
              <div className={`h-2 w-2 rounded-full ${
                ollamaState === "online" ? "bg-emerald-500 shadow-[0_0_8px_#10B981]" :
                ollamaState === "error" ? "bg-rose-500 shadow-[0_0_8px_#F43F5E]" : "bg-slate-600"
              }`} />
              <span className="text-slate-300">
                {ollamaState === "online" ? "Online" : ollamaState === "error" ? "Error" : ollamaState === "offline" ? "Offline" : "Checking..."}
              </span>
            </div>
          </div>
          {apiErrors["ollama/status"] && (
            <div className="text-[10px] text-rose-400 px-1 break-words">{apiErrors["ollama/status"].error}</div>
          )}
        </div>
      </div>
    </aside>
  );
}
