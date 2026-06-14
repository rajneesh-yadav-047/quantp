"use client";

import React, { useState, useMemo } from "react";
import dynamic from "next/dynamic";
import {
  TrendingUp, TrendingDown, BarChart3, Shield, Zap, Activity,
  Loader2, Play, PieChart, DollarSign, AlertTriangle
} from "lucide-react";
import { api } from "../lib/api-client";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

interface Props {
  backtestResults: any[];
  theme: "dark" | "light";
  setNotif: (n: { type: "success" | "error" | "info"; msg: string } | null) => void;
}

const Metric = ({
  label,
  value,
  sub,
  color = "text-slate-200",
  icon: Icon,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
  icon?: React.ElementType;
}) => (
  <div className="glass-panel rounded-xl p-4 flex flex-col gap-1 shadow-xs hover:border-slate-600/50 transition-colors">
    <div className="flex items-center justify-between">
      <span className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">{label}</span>
      {Icon && <Icon size={13} className="text-slate-600" />}
    </div>
    <span className={`font-mono text-xl font-bold ${color}`}>{value}</span>
    {sub && <p className="text-[10px] text-slate-500 leading-tight">{sub}</p>}
  </div>
);

export default function PortfolioAnalytics({ backtestResults, theme, setNotif }: Props) {
  const [selectedRunId, setSelectedRunId] = useState("");
  const [mcLoading, setMcLoading] = useState(false);
  const [mcResult, setMcResult] = useState<any>(null);
  const [nSims, setNSims] = useState(500);
  const [activeView, setActiveView] = useState<"overview" | "montecarlo" | "stress">("overview");

  const selectedResult = backtestResults.find((r) => r.id === selectedRunId);

  const isDark = theme === "dark";
  const labelColor = isDark ? "#64748b" : "#475569";
  const gridLineColor = isDark ? "#0f172a" : "#f1f5f9";
  const borderLineColor = isDark ? "#1e293b" : "#cbd5e1";
  const tooltipBgColor = isDark ? "#0b1222" : "#ffffff";
  const tooltipBorderColor = isDark ? "#1e293b" : "#cbd5e1";
  const tooltipTextColor = isDark ? "#e2e8f0" : "#0f172a";

  const runMonteCarlo = async () => {
    if (!selectedRunId) {
      setNotif({ type: "error", msg: "Select a backtest run first" });
      return;
    }
    setMcLoading(true);
    setMcResult(null);
    const res = await api.post("/research/multiasset/monte-carlo", {
      run_id: selectedRunId,
      n_simulations: nSims,
    });
    if (res.ok && res.data) {
      setMcResult(res.data);
      setNotif({ type: "success", msg: "Monte Carlo simulation complete" });
    } else {
      setNotif({ type: "error", msg: res.error || "Monte Carlo failed" });
    }
    setMcLoading(false);
  };

  /* ─── Monte Carlo chart ─── */
  const mcEquityCurveOpt = useMemo(() => {
    if (!mcResult?.monte_carlo?.sample_curves?.length) return null;
    const curves = mcResult.monte_carlo.sample_curves;
    const n = curves[0]?.length || 0;
    const xData = Array.from({ length: n }, (_, i) => i + 1);
    return {
      backgroundColor: "transparent",
      tooltip: { trigger: "axis", backgroundColor: tooltipBgColor, borderColor: tooltipBorderColor, textStyle: { color: tooltipTextColor, fontSize: 10 } },
      grid: { left: 60, right: 15, top: 15, bottom: 35 },
      xAxis: { type: "category", data: xData, axisLabel: { color: labelColor, fontSize: 9 }, axisLine: { lineStyle: { color: borderLineColor } } },
      yAxis: { type: "value", axisLabel: { color: labelColor, fontSize: 9 }, splitLine: { lineStyle: { color: gridLineColor } } },
      series: curves.map((curve: number[], i: number) => ({
        type: "line",
        data: curve,
        showSymbol: false,
        lineStyle: { color: `rgba(139, 92, 246, ${i === 0 ? 0.8 : 0.15})`, width: i === 0 ? 2 : 1 },
      })),
    };
  }, [mcResult, theme]);

  const stressChartOpt = useMemo(() => {
    if (!mcResult?.stress_test) return null;
    const stress = mcResult.stress_test;
    const entries = Object.entries(stress);
    const names = entries.map(([k]) => k.replace("_", " ").toUpperCase());
    const returns = entries.map(([, v]: [string, any]) => v.total_return_pct ?? 0);
    const drawdowns = entries.map(([, v]: [string, any]) => (v.max_drawdown ?? 0) * 100);

    return {
      backgroundColor: "transparent",
      tooltip: { trigger: "axis", backgroundColor: tooltipBgColor, borderColor: tooltipBorderColor, textStyle: { color: tooltipTextColor, fontSize: 10 } },
      grid: { left: 80, right: 15, top: 20, bottom: 60 },
      legend: { bottom: 5, textStyle: { color: labelColor, fontSize: 9 } },
      xAxis: { type: "category", data: names, axisLabel: { color: labelColor, fontSize: 9, rotate: 20 }, axisLine: { lineStyle: { color: borderLineColor } } },
      yAxis: { type: "value", axisLabel: { color: labelColor, fontSize: 9, formatter: "{value}%" }, splitLine: { lineStyle: { color: gridLineColor } } },
      series: [
        {
          name: "Return %",
          type: "bar",
          data: returns.map((v: number) => ({
            value: v,
            itemStyle: { color: v >= 0 ? "#10b981" : "#ef4444", borderRadius: [3, 3, 0, 0] },
          })),
          barWidth: "30%",
        },
        {
          name: "Max Drawdown %",
          type: "bar",
          data: drawdowns.map((v: number) => ({
            value: -v,
            itemStyle: { color: "rgba(244,63,94,0.5)", borderRadius: [0, 0, 3, 3] },
          })),
          barWidth: "30%",
        },
      ],
    };
  }, [mcResult, theme]);

  return (
    <div className="flex flex-col gap-6">
      {/* ─── Header ─── */}
      <div className="glass-panel p-5 rounded-xl">
        <div className="flex items-center gap-3 mb-4 pb-3 border-b border-slate-800/60">
          <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
            <BarChart3 size={18} className="text-emerald-400" />
          </div>
          <div>
            <h3 className="font-bold text-slate-100 text-sm">Portfolio Risk Analytics</h3>
            <p className="text-[10px] text-slate-500">Monte Carlo · Stress Tests · Drawdown Projections · Risk-of-Ruin</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Select Backtest Run</label>
            <select
              value={selectedRunId}
              onChange={(e) => { setSelectedRunId(e.target.value); setMcResult(null); }}
              className="t-input w-full rounded-lg px-3 py-2 text-xs"
              id="portfolio-run-select"
            >
              <option value="">Choose a backtest run…</option>
              {backtestResults.map((r: any) => (
                <option key={r.id} value={r.id}>
                  {r.strategy_name} — {r.symbol} ({r.interval}) — PnL: ₹{r.total_pnl?.toFixed(0)}
                </option>
              ))}
            </select>
          </div>

          <div className="w-28">
            <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Simulations</label>
            <input
              type="number"
              min={100}
              max={5000}
              step={100}
              value={nSims}
              onChange={(e) => setNSims(parseInt(e.target.value))}
              className="t-input w-full rounded-lg px-3 py-2 text-xs font-mono"
            />
          </div>

          <div className="flex items-end">
            <button
              onClick={runMonteCarlo}
              disabled={mcLoading || !selectedRunId}
              className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2.5 rounded-lg text-xs font-bold flex items-center gap-2 transition-all"
              id="run-montecarlo-btn"
            >
              {mcLoading ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
              {mcLoading ? "Simulating…" : "Run Monte Carlo"}
            </button>
          </div>
        </div>
      </div>

      {/* ─── Selected run summary ─── */}
      {selectedResult && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          <Metric label="Total PnL" value={`₹${(selectedResult.total_pnl ?? 0).toFixed(0)}`} color={(selectedResult.total_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"} icon={DollarSign} />
          <Metric label="CAGR" value={`${((selectedResult.cagr ?? 0) * 100).toFixed(2)}%`} color="text-blue-400" icon={TrendingUp} />
          <Metric label="Sharpe" value={(selectedResult.sharpe_ratio ?? 0).toFixed(2)} color="text-violet-400" icon={Activity} />
          <Metric label="Max DD" value={`${((selectedResult.max_drawdown ?? 0) * 100).toFixed(2)}%`} color="text-rose-400" icon={TrendingDown} />
          <Metric label="Win Rate" value={`${((selectedResult.win_rate ?? 0) * 100).toFixed(1)}%`} color="text-amber-400" icon={Shield} />
          <Metric label="Symbol" value={selectedResult.symbol} icon={Zap} />
          <Metric label="Interval" value={selectedResult.interval} />
        </div>
      )}

      {/* ─── Monte Carlo Results ─── */}
      {mcLoading && (
        <div className="glass-panel rounded-xl p-12 text-center">
          <Loader2 size={32} className="text-emerald-400 mx-auto mb-3 animate-spin" />
          <p className="text-slate-400 text-sm">Running {nSims.toLocaleString()} Monte Carlo simulations…</p>
        </div>
      )}

      {mcResult && (
        <div className="flex flex-col gap-5">
          {/* View tabs */}
          <div className="flex gap-2 border-b border-slate-800/60 pb-1">
            {(["overview", "montecarlo", "stress"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setActiveView(v)}
                className={`px-3 py-1.5 rounded-t-lg text-[11px] font-semibold capitalize transition-all ${
                  activeView === v
                    ? "bg-emerald-600/20 border border-emerald-500/30 text-emerald-300"
                    : "text-slate-500 hover:text-slate-300 hover:bg-slate-800/40"
                }`}
              >
                {v.replace("montecarlo", "Monte Carlo")}
              </button>
            ))}
          </div>

          {/* Overview */}
          {activeView === "overview" && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Metric
                label="Risk of Ruin"
                value={`${mcResult.monte_carlo.risk_of_ruin_pct}%`}
                color={mcResult.monte_carlo.risk_of_ruin_pct > 5 ? "text-rose-400" : "text-emerald-400"}
                sub="Probability of losing all capital"
              />
              <Metric
                label="Positive Outcome"
                value={`${mcResult.monte_carlo.positive_outcome_pct}%`}
                color="text-emerald-400"
                sub="Simulations ending above initial capital"
              />
              <Metric
                label="Expected Return"
                value={`${mcResult.monte_carlo.expected_return_pct.mean}%`}
                sub={`95% CI: [${mcResult.monte_carlo.expected_return_pct.ci_95_low}%, ${mcResult.monte_carlo.expected_return_pct.ci_95_high}%]`}
                color="text-blue-400"
              />
              <Metric
                label="Worst-Case DD (p95)"
                value={`${(mcResult.monte_carlo.max_drawdown.p95 * 100).toFixed(1)}%`}
                color="text-rose-400"
                sub={`Mean: ${(mcResult.monte_carlo.max_drawdown.mean * 100).toFixed(1)}%`}
              />
              <Metric label="Median Final Equity" value={`₹${mcResult.monte_carlo.final_equity.median.toLocaleString()}`} color="text-violet-400" />
              <Metric label="Best Case (p95)" value={`₹${mcResult.monte_carlo.final_equity.p95.toLocaleString()}`} color="text-emerald-400" />
              <Metric label="Worst Case (p5)" value={`₹${mcResult.monte_carlo.final_equity.p5.toLocaleString()}`} color="text-rose-400" />
              <Metric label="Total Simulations" value={mcResult.monte_carlo.n_simulations.toLocaleString()} />
            </div>
          )}

          {/* Monte Carlo curves */}
          {activeView === "montecarlo" && mcEquityCurveOpt && (
            <div className="glass-panel rounded-xl p-5">
              <h4 className="text-sm font-bold text-slate-200 mb-3 flex items-center gap-2">
                <Activity size={14} className="text-emerald-400" />
                Monte Carlo Equity Paths (20 samples shown)
              </h4>
              <ReactECharts option={mcEquityCurveOpt} style={{ height: 340 }} />
            </div>
          )}

          {/* Stress test */}
          {activeView === "stress" && stressChartOpt && (
            <div className="glass-panel rounded-xl p-5">
              <h4 className="text-sm font-bold text-slate-200 mb-3 flex items-center gap-2">
                <AlertTriangle size={14} className="text-amber-400" /> Stress Test Results
              </h4>
              <ReactECharts option={stressChartOpt} style={{ height: 300 }} />
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
                {Object.entries(mcResult.stress_test).map(([name, s]: [string, any]) => (
                  <div key={name} className={`p-3 rounded-lg border text-center ${s.ruin ? "border-rose-800/50 bg-rose-900/10" : "border-slate-800/50 bg-slate-900/20"}`}>
                    <p className="text-[10px] font-bold uppercase text-slate-500 mb-1">{name.replace("_", " ")}</p>
                    <p className={`font-mono text-sm font-bold ${s.total_return_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {s.total_return_pct > 0 ? "+" : ""}{s.total_return_pct}%
                    </p>
                    <p className="text-[10px] text-slate-500">DD: {(s.max_drawdown * 100).toFixed(1)}%</p>
                    {s.ruin && <span className="text-[9px] text-rose-400 font-bold">⚠ RUIN</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!selectedResult && !mcResult && (
        <div className="glass-panel rounded-xl p-12 text-center">
          <BarChart3 size={40} className="text-slate-700 mx-auto mb-4" />
          <p className="text-slate-500 text-sm">Select a completed backtest run and click Run Monte Carlo to analyze risk.</p>
        </div>
      )}
    </div>
  );
}
