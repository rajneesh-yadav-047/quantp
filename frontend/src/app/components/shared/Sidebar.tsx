"use client";

import { Cpu, LayoutDashboard, Database, Code, PlayCircle, Rocket, Radio, FlaskConical, Settings, Trash2, CheckCircle2, AlertCircle, Sun, Moon, Network, BarChart3 } from "lucide-react";
import type { Notif } from "../../hooks/useQuantLab";

interface SidebarProps {
  activeTab: string;
  setActiveTab: (id: string) => void;
  notif: Notif | null;
  backendOnline: boolean;
  smartapiConnected: boolean;
  apiErrors: Record<string, { error: string; retry: () => void }>;
  theme: "dark" | "light";
  setTheme: (theme: "dark" | "light") => void;
}

const navItems = [
  { id: "dashboard",      label: "Dashboard",       icon: LayoutDashboard },
  { id: "datasets",       label: "Datasets",        icon: Database },
  { id: "strategies",     label: "Strategies",      icon: Code },
  { id: "backtests",      label: "Backtests",       icon: PlayCircle },
  { id: "deployments",    label: "Deployments",     icon: Rocket },
  { id: "live",           label: "Live Trading",    icon: Radio, external: "/live" },
  { id: "research",       label: "Research Lab",    icon: FlaskConical },
  { id: "multi-asset",    label: "Multi-Asset",     icon: Network },
  { id: "portfolio-risk", label: "Portfolio Risk",  icon: BarChart3 },
  { id: "optimizer",      label: "Optimizer",       icon: Settings },
  { id: "cleanup",        label: "Cleanup",         icon: Trash2 },
];

export default function Sidebar({
  activeTab,
  setActiveTab,
  notif,
  backendOnline,
  smartapiConnected,
  theme,
  setTheme
}: SidebarProps) {
  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");
  const isDark = theme === "dark";

  return (
    <aside
      className="w-64 flex flex-col justify-between shrink-0 transition-colors duration-200 p-4"
      style={{
        backgroundColor: "var(--sidebar-bg)",
        borderRight: "1px solid var(--sidebar-border)",
      }}
    >
      <div>
        {/* Logo */}
        <div className="flex items-center gap-3 px-2 py-3 mb-6">
          <div className="p-2 bg-blue-600 rounded-lg text-white shadow-sm">
            <Cpu size={18} />
          </div>
          <div>
            <h1 className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
              QuantLab
            </h1>
            <span className="text-[10px] font-mono font-medium" style={{ color: "var(--text-tertiary)" }}>
              v2.0.0-STRAT
            </span>
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
                style={active ? {
                  backgroundColor: isDark ? "rgba(59,130,246,0.12)" : "rgba(37,99,235,0.08)",
                  color: isDark ? "#60a5fa" : "#1d4ed8",
                  borderLeft: "2px solid var(--accent-blue)",
                } : {
                  color: "var(--text-tertiary)",
                  borderLeft: "2px solid transparent",
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-bold uppercase tracking-wide transition-all cursor-pointer`}
                onMouseEnter={e => {
                  if (!active) {
                    (e.currentTarget as HTMLElement).style.backgroundColor = isDark ? "rgba(148,163,184,0.06)" : "rgba(15,23,42,0.05)";
                    (e.currentTarget as HTMLElement).style.color = "var(--text-primary)";
                  }
                }}
                onMouseLeave={e => {
                  if (!active) {
                    (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
                    (e.currentTarget as HTMLElement).style.color = "var(--text-tertiary)";
                  }
                }}
              >
                <Icon size={14} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer: Status + Theme Toggle */}
      <div className="space-y-4 pt-4" style={{ borderTop: "1px solid var(--sidebar-border)" }}>
        {notif && (
          <div
            className={`p-2.5 rounded-lg border text-[11px] flex gap-2 items-center leading-normal font-medium ${
              notif.type === "success"
                ? "bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/50"
                : notif.type === "error"
                  ? "bg-rose-50 dark:bg-rose-950/20 text-rose-700 dark:text-rose-400 border-rose-200 dark:border-rose-800/50"
                  : "bg-blue-50 dark:bg-blue-950/20 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-800/50"
            }`}
          >
            {notif.type === "success" ? <CheckCircle2 size={13} className="shrink-0" /> : <AlertCircle size={13} className="shrink-0" />}
            <p className="line-clamp-2">{notif.msg}</p>
          </div>
        )}

        <div className="space-y-2 text-[11px] font-semibold">
          <div className="flex items-center justify-between px-1">
            <span style={{ color: "var(--text-tertiary)" }}>FastAPI Backend</span>
            <div className="flex items-center gap-1.5 font-mono">
              <div className={`h-2 w-2 rounded-full ${backendOnline ? "bg-emerald-500" : "bg-amber-500"}`} />
              <span style={{ color: "var(--text-secondary)" }}>{backendOnline ? "Online" : "Offline"}</span>
            </div>
          </div>
          <div className="flex items-center justify-between px-1">
            <span style={{ color: "var(--text-tertiary)" }}>SmartAPI Feed</span>
            <div className="flex items-center gap-1.5 font-mono">
              <div className={`h-2 w-2 rounded-full ${smartapiConnected ? "bg-emerald-500" : isDark ? "bg-slate-600" : "bg-slate-400"}`} />
              <span style={{ color: "var(--text-secondary)" }}>{smartapiConnected ? "Connected" : "Disconnected"}</span>
            </div>
          </div>
        </div>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-colors cursor-pointer"
          style={{
            border: "1px solid var(--border-color)",
            backgroundColor: isDark ? "rgba(15,23,42,0.5)" : "#f1f5f9",
            color: "var(--text-secondary)",
          }}
        >
          {isDark ? (
            <>
              <Sun size={13} className="text-amber-500" />
              <span>Light Mode</span>
            </>
          ) : (
            <>
              <Moon size={13} style={{ color: "var(--text-tertiary)" }} />
              <span>Dark Mode</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
