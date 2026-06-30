"use client";

import { useMemo } from "react";
import {
  LayoutDashboard, Database, Code, PlayCircle, Rocket, Radio,
  FlaskConical, Network, BarChart3, TrendingUp, Settings, Trash2,
  Sun, Moon, CheckCircle2, AlertCircle
} from "lucide-react";
import type { Notif } from "../../hooks/useAxon";

interface AxonSidebarProps {
  activeTab: string;
  setActiveTab: (id: string) => void;
  notif: Notif | null;
  backendOnline: boolean;
  smartapiConnected: boolean;
  theme: "dark" | "light";
  setTheme: (theme: "dark" | "light") => void;
}

/* ── Top-level sections ── */
const topSections = [
  { id: "overview", label: "Overview", tab: "dashboard" },
  { id: "data",     label: "Data",     tab: "datasets" },
  { id: "strategies", label: "Strategies", tab: "strategies" },
  { id: "trading",  label: "Trading",  tab: "backtests" },
  { id: "research", label: "Research", tab: "research" },
];

/* ── Sidebar nav groups per section ── */
const sidebarGroups: Record<string, { label: string; items: { id: string; label: string }[] }[]> = {
  overview: [
    { label: "Dashboard", items: [{ id: "dashboard", label: "Overview" }] },
  ],
  data: [
    { label: "Data", items: [{ id: "datasets", label: "Datasets & Downloader" }] },
  ],
  strategies: [
    { label: "Strategies", items: [
      { id: "strategies", label: "Strategy Workspace" },
      { id: "backtests", label: "Backtests" },
      { id: "optimizer", label: "Optimizer" },
    ]},
  ],
  trading: [
    { label: "Trading", items: [
      { id: "backtests", label: "Backtests" },
      { id: "deployments", label: "Deployments" },
      { id: "live", label: "Live Trading" },
      { id: "options", label: "Options" },
      { id: "optimizer", label: "Optimizer" },
      { id: "cleanup", label: "Cleanup" },
    ]},
    { label: "Tools", items: [
      { id: "portfolio-risk", label: "Portfolio Risk" },
    ]},
  ],
  research: [
    { label: "Research", items: [
      { id: "research", label: "Research Lab" },
      { id: "multi-asset", label: "Multi-Asset" },
      { id: "portfolio-risk", label: "Portfolio Risk" },
    ]},
  ],
};

export default function AxonSidebar({
  activeTab,
  setActiveTab,
  notif,
  backendOnline,
  smartapiConnected,
  theme,
  setTheme,
}: AxonSidebarProps) {
  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");

  /* Determine which top-level section is active */
  const currentSection = useMemo(() => {
    for (const s of topSections) {
      if (s.tab === activeTab) return s.id;
    }
    // Check sidebar items for indirect match
    for (const [section, groups] of Object.entries(sidebarGroups)) {
      for (const g of groups) {
        if (g.items.some((i) => i.id === activeTab)) return section;
      }
    }
    return "overview";
  }, [activeTab]);

  const groups = sidebarGroups[currentSection] || sidebarGroups.overview;

  return (
    <aside
      className="w-36 bg-[var(--ax-sidebar-bg)] border-r border-[var(--ax-border)] py-2.5 shrink-0 overflow-y-auto flex flex-col justify-between"
    >
      <div>
        {groups.map((group, gi) => (
          <div key={gi} className="mb-3">
            <div className="text-[10px] font-medium text-[#606060] uppercase tracking-widest px-3 pb-1">
              {group.label}
            </div>
            {group.items.map((item) => {
              const isActive = activeTab === item.id;
              const isAccent = isActive && item.id === "options";
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center gap-2 px-3 py-1.5 text-xs w-full text-left border-l-2 transition-colors ${
                    isAccent
                      ? "text-[#93b4ff] bg-[#0f1520] border-l-[#4a7fcc]"
                      : isActive
                      ? "text-[#c0c0c0] bg-[#161616] border-l-[#444]"
                      : "text-[#a0a0a0] border-transparent hover:text-[#888]"
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* Footer: Status + Theme Toggle */}
      <div className="px-3 pt-2 border-t border-[var(--ax-border)] space-y-3">
        {notif && (
          <div
            className={`p-2 rounded border text-[10px] flex gap-2 items-center leading-normal font-medium ${
              notif.type === "success"
                ? "bg-emerald-950/20 text-emerald-400 border-emerald-800/50"
                : notif.type === "error"
                  ? "bg-rose-950/20 text-rose-400 border-rose-800/50"
                  : "bg-[var(--ax-atm)] text-[#93b4ff] border-[#2a3a5a]/50"
            }`}
          >
            {notif.type === "success" ? <CheckCircle2 size={13} className="shrink-0" /> : <AlertCircle size={13} className="shrink-0" />}
            <p className="line-clamp-2">{notif.msg}</p>
          </div>
        )}

        <div className="space-y-2 text-[9px] font-semibold">
          <div className="flex items-center justify-between">
            <span className="text-[#606060]">FastAPI</span>
            <div className="flex items-center gap-1 font-mono">
              <div className={`h-1.5 w-1.5 rounded-full ${backendOnline ? "bg-emerald-500" : "bg-amber-500"}`} />
              <span className="text-[#a0a0a0]">{backendOnline ? "Online" : "Offline"}</span>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[#606060]">SmartAPI</span>
            <div className="flex items-center gap-1 font-mono">
              <div className={`h-1.5 w-1.5 rounded-full ${smartapiConnected ? "bg-emerald-500" : "bg-[#383838]"}`} />
              <span className="text-[#a0a0a0]">{smartapiConnected ? "Connected" : "Disconnected"}</span>
            </div>
          </div>
        </div>

        <button
          onClick={toggleTheme}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded text-[10px] font-bold uppercase tracking-wider transition-colors cursor-pointer border border-[var(--ax-border)] bg-[#111] text-[#555] hover:text-[#888]"
        >
          {theme === "dark" ? (
            <>
              <Sun size={13} className="text-amber-500" />
              <span>Light</span>
            </>
          ) : (
            <>
              <Moon size={13} />
              <span>Dark</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
