"use client";

import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import dynamic from "next/dynamic";
import {
  BarChart2, Play, Terminal, TrendingUp, TrendingDown, Activity,
  ArrowUpRight, ArrowDownRight, Clock, Calendar, Zap, Shield,
  Target, Layers, ChevronDown, ChevronUp, Loader2, Database,
  AlertTriangle, CheckCircle2, XCircle, BarChart3, PieChart,
} from "lucide-react";
import { api } from "../lib/api-client";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

/* ─── Standalone sub-components (outside ResearchLab so React never remounts them) ─── */

const Stat = ({ label, value, color = "text-slate-200", suffix = "" }: any) => (
  <div className="bg-slate-950/50 border border-slate-800/50 rounded-lg p-3">
    <div className="text-[10px] uppercase font-bold text-slate-500 mb-1">{label}</div>
    <div className={`text-lg font-mono font-bold ${color}`}>
      {value}{suffix}
    </div>
  </div>
);

interface CardProps {
  title: string;
  icon: any;
  cardKey: string;
  isExpanded: boolean;
  onToggle: (key: string) => void;
  children: React.ReactNode;
  className?: string;
}

const Card = React.memo(function Card({
  title,
  icon: Icon,
  cardKey,
  isExpanded,
  onToggle,
  children,
  className = "",
}: CardProps) {
  return (
    <div className={`glass-panel rounded-xl overflow-hidden ${className}`}>
      <button
        onClick={() => onToggle(cardKey)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-800/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon size={16} className="text-blue-400" />
          <span className="font-bold text-sm text-slate-200">{title}</span>
        </div>
        {isExpanded ? (
          <ChevronUp size={16} className="text-slate-500" />
        ) : (
          <ChevronDown size={16} className="text-slate-500" />
        )}
      </button>
      {isExpanded && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
});

/* ─── Main component ─── */

interface ResearchLabProps {
  datasets: any[];
  apiErrors: Record<string, { error: string; retry: () => void }>;
  setEndpointError: (endpoint: string, error: string | null, retry?: () => void) => void;
  clearEndpointError: (endpoint: string) => void;
  setNotif: (notif: { type: "success" | "error" | "info"; msg: string } | null) => void;
}

export default function ResearchLab({
  datasets,
  apiErrors,
  setEndpointError,
  clearEndpointError,
  setNotif,
}: ResearchLabProps) {
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({
    overview: true,
    returns: true,
    volatility: true,
    trend: true,
    drawdown: true,
    levels: true,
    volume: true,
    regimes: true,
    seasonality: true,
    patterns: true,
    autocorr: true,
    suitability: true,
    "tuning-summary": true,
  });
  const logsEndRef = useRef<HTMLDivElement>(null);

  const datasetOptions = useMemo(() => {
    return datasets.map((val: any) => {
      const key = val.symbol && val.interval ? `${val.symbol}_${val.interval}` : String(val.id || val.key || "");
      return {
        key,
        label: `${val.symbol || key.split("_")[0]} (${val.interval || key.split("_")[1]}) — ${val.records || val.total_records || "?"} bars`,
      };
    });
  }, [datasets]);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollTop = logsEndRef.current.scrollHeight;
    }
  }, [analysisResult?.logs]);

  const runAnalysis = async () => {
    if (!selectedDataset) {
      setNotif({ type: "error", msg: "Select a dataset first" });
      return;
    }
    const firstUnderscore = selectedDataset.indexOf("_");
    const symbol = selectedDataset.substring(0, firstUnderscore);
    const interval = selectedDataset.substring(firstUnderscore + 1);
    if (!symbol || !interval) {
      setNotif({ type: "error", msg: "Invalid dataset key" });
      return;
    }

    setAnalysisLoading(true);
    setAnalysisResult(null);
    clearEndpointError("research/analyze");

    const res = await api.post("/research/analyze", { symbol, interval });

    if (res.ok && res.data) {
      setAnalysisResult(res.data);
      clearEndpointError("research/analyze");
      setNotif({ type: "success", msg: `Analysis complete for ${symbol}` });
    } else {
      setEndpointError(
        "research/analyze",
        res.error || "Analysis failed",
        () => runAnalysis()
      );
      setNotif({ type: "error", msg: res.error || "Analysis failed" });
    }

    setAnalysisLoading(false);
  };

  const toggleCard = useCallback((key: string) => {
    setExpandedCards((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  /* ─── Chart options — memoized so echarts never re-initialises ─── */

  const priceChartOpt = useMemo(() => {
    if (!analysisResult?.plot_series) return {};
    const ps = analysisResult.plot_series;
    return {
      tooltip: { trigger: "axis" },
      grid: { left: 50, right: 20, top: 30, bottom: 50 },
      xAxis: { type: "category", data: ps.time, axisLabel: { color: "#64748b", fontSize: 10 } },
      yAxis: [
        { type: "value", axisLabel: { color: "#64748b", fontSize: 10 }, splitLine: { lineStyle: { color: "#1e293b" } } },
        { type: "value", show: false },
      ],
      dataZoom: [{ type: "inside" }, { type: "slider", bottom: 0, height: 20 }],
      series: [
        { name: "Close", type: "line", data: ps.close, smooth: false, lineStyle: { color: "#3b82f6", width: 1.5 }, itemStyle: { color: "#3b82f6" }, showSymbol: false },
        { name: "EMA 20", type: "line", data: ps.ema_fast, smooth: false, lineStyle: { color: "#f59e0b", width: 1 }, showSymbol: false },
        { name: "EMA 50", type: "line", data: ps.ema_slow, smooth: false, lineStyle: { color: "#8b5cf6", width: 1 }, showSymbol: false },
        { name: "Volume", type: "bar", yAxisIndex: 1, data: ps.volume, itemStyle: { color: "rgba(100,116,139,0.3)" } },
      ],
    };
  }, [analysisResult?.plot_series]);

  const returnsDistChartOpt = useMemo(() => {
    if (!analysisResult?.returns) return {};
    const returns = analysisResult.plot_series?.returns || [];
    const min = Math.min(...returns);
    const max = Math.max(...returns);
    const bins = 30;
    const step = (max - min) / bins || 1;
    const counts = new Array(bins).fill(0);
    returns.forEach((r: number) => {
      const idx = Math.min(Math.floor((r - min) / step), bins - 1);
      counts[idx]++;
    });
    const labels = counts.map((_, i) => (min + i * step).toFixed(3));
    return {
      tooltip: { trigger: "axis" },
      grid: { left: 50, right: 20, top: 20, bottom: 40 },
      xAxis: { type: "category", data: labels, axisLabel: { color: "#64748b", fontSize: 9, rotate: 45 } },
      yAxis: { type: "value", axisLabel: { color: "#64748b", fontSize: 10 }, splitLine: { lineStyle: { color: "#1e293b" } } },
      series: [{ type: "bar", data: counts, itemStyle: { color: "#3b82f6" }, barWidth: "90%" }],
    };
  }, [analysisResult?.returns, analysisResult?.plot_series?.returns]);

  const drawdownChartOpt = useMemo(() => {
    if (!analysisResult?.plot_series?.drawdown) return {};
    return {
      tooltip: { trigger: "axis" },
      grid: { left: 50, right: 20, top: 20, bottom: 40 },
      xAxis: { type: "category", data: analysisResult.plot_series.time, axisLabel: { color: "#64748b", fontSize: 10 } },
      yAxis: { type: "value", axisLabel: { color: "#64748b", fontSize: 10 }, splitLine: { lineStyle: { color: "#1e293b" } } },
      series: [{ type: "line", data: analysisResult.plot_series.drawdown, areaStyle: { color: "rgba(244,63,94,0.2)" }, lineStyle: { color: "#f43f5e", width: 1 }, showSymbol: false }],
    };
  }, [analysisResult?.plot_series?.drawdown, analysisResult?.plot_series?.time]);

  const volChartOpt = useMemo(() => {
    if (!analysisResult?.plot_series?.rolling_vol_20) return {};
    return {
      tooltip: { trigger: "axis" },
      grid: { left: 50, right: 20, top: 20, bottom: 40 },
      xAxis: { type: "category", data: analysisResult.plot_series.time, axisLabel: { color: "#64748b", fontSize: 10 } },
      yAxis: { type: "value", axisLabel: { color: "#64748b", fontSize: 10 }, splitLine: { lineStyle: { color: "#1e293b" } } },
      series: [{ type: "line", data: analysisResult.plot_series.rolling_vol_20, areaStyle: { color: "rgba(245,158,11,0.15)" }, lineStyle: { color: "#f59e0b", width: 1.5 }, showSymbol: false }],
    };
  }, [analysisResult?.plot_series?.rolling_vol_20, analysisResult?.plot_series?.time]);

  const regimeChartOpt = useMemo(() => {
    if (!analysisResult?.regimes) return {};
    const regimes = analysisResult.regimes;
    const colors: Record<string, string> = {
      TRENDING_BULLISH: "#10b981",
      TRENDING_BEARISH: "#f43f5e",
      VOLATILE_RANGING: "#f59e0b",
      QUIET_RANGING: "#64748b",
      GAP_DAY: "#8b5cf6",
    };
    const data = Object.entries(regimes).map(([name, pct]: [string, any]) => ({
      name: name.replace(/_/g, " "),
      value: pct,
      itemStyle: { color: colors[name] || "#3b82f6" },
    }));
    return {
      tooltip: { trigger: "item", formatter: "{b}: {c}%" },
      series: [{ type: "pie", radius: ["40%", "70%"], avoidLabelOverlap: true, label: { color: "#94a3b8", fontSize: 10 }, data }],
    };
  }, [analysisResult?.regimes]);

  const seasonalityChartOpt = useMemo(() => {
    if (!analysisResult?.seasonality?.dow?.dow_data) return {};
    const dowData = analysisResult.seasonality.dow.dow_data;
    return {
      tooltip: { trigger: "axis" },
      grid: { left: 40, right: 20, top: 20, bottom: 30 },
      xAxis: { type: "category", data: dowData.map((d: any) => d.day), axisLabel: { color: "#64748b", fontSize: 10 } },
      yAxis: { type: "value", axisLabel: { color: "#64748b", fontSize: 10, formatter: "{value}%" }, splitLine: { lineStyle: { color: "#1e293b" } } },
      series: [{ type: "bar", data: dowData.map((d: any) => d.mean_return_pct), itemStyle: { color: (params: any) => params.value >= 0 ? "#10b981" : "#f43f5e" }, barWidth: "50%" }],
    };
  }, [analysisResult?.seasonality?.dow?.dow_data]);

  const suitabilityChartOpt = useMemo(() => {
    if (!analysisResult?.suitability?.scores) return {};
    const scores = analysisResult.suitability.scores;
    const data = Object.entries(scores).map(([name, score]: [string, any]) => ({
      name: name.replace(/_/g, " ").toUpperCase(),
      value: score,
      color: score > 60 ? "#10b981" : score > 40 ? "#f59e0b" : "#f43f5e",
    }));
    return {
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 120, right: 30, top: 10, bottom: 20 },
      xAxis: { type: "value", max: 100, axisLabel: { color: "#64748b", fontSize: 10 }, splitLine: { lineStyle: { color: "#1e293b" } } },
      yAxis: { type: "category", data: data.map((d: any) => d.name), axisLabel: { color: "#94a3b8", fontSize: 10 } },
      series: [{ type: "bar", data: data.map((d: any) => ({ value: d.value, itemStyle: { color: d.color } })), barWidth: "60%", label: { show: true, position: "right", color: "#e2e8f0", fontSize: 10, formatter: "{c}" } }],
    };
  }, [analysisResult?.suitability?.scores]);

  return (
    <div className="space-y-6">
      {/* Header + Controls */}
      <div className="glass-panel p-5 rounded-xl space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-bold text-slate-200 text-base flex items-center gap-2">
              <BarChart2 size={18} className="text-blue-400" />
              Dataset Deep Analysis
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Independent statistical analysis of raw market data to determine strategy suitability.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1.5">Dataset</label>
            <select
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
              value={selectedDataset}
              onChange={(e) => setSelectedDataset(e.target.value)}
            >
              <option value="">Select a dataset...</option>
              {datasetOptions.map((opt) => (
                <option key={opt.key} value={opt.key}>{opt.label}</option>
              ))}
            </select>
          </div>
          <button
            onClick={runAnalysis}
            disabled={analysisLoading || !selectedDataset}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 text-white px-5 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-colors"
          >
            {analysisLoading ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            {analysisLoading ? "Analyzing..." : "Run Deep Analysis"}
          </button>
        </div>

        {apiErrors["research/analyze"] && (
          <div className="bg-rose-950/30 border border-rose-800/50 rounded-lg p-3 flex items-center justify-between">
            <span className="text-xs text-rose-400">{apiErrors["research/analyze"].error}</span>
            <button
              onClick={apiErrors["research/analyze"].retry}
              className="text-xs text-rose-300 hover:text-rose-200 underline"
            >
              Retry
            </button>
          </div>
        )}
      </div>

      {/* Results */}
      {analysisResult && analysisResult.valid && (
        <div className="space-y-4">
          {/* Terminal Logs */}
          <div className="glass-panel rounded-xl overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800/50 bg-slate-950/50">
              <Terminal size={14} className="text-emerald-400" />
              <span className="text-xs font-bold text-slate-400 uppercase">Analysis Terminal</span>
              <span className="text-[10px] text-slate-600 ml-auto font-mono">
                {analysisResult.symbol} @ {analysisResult.interval} | {analysisResult.bars} bars
              </span>
            </div>
            <div
              ref={logsEndRef}
              className="h-48 overflow-y-auto p-4 space-y-1 font-mono text-[11px] bg-slate-950/80"
            >
              {analysisResult.logs?.map((log: string, i: number) => {
                const isError = log.includes("[ERROR]");
                const isWarn = log.includes("[WARN]") || log.includes("WARNING");
                const isRec = log.includes("RECOMMENDED");
                return (
                  <div
                    key={i}
                    className={`${
                      isError ? "text-rose-400" :
                      isWarn ? "text-amber-400" :
                      isRec ? "text-emerald-400 font-bold" :
                      "text-slate-400"
                    }`}
                  >
                    {log}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Overview Stats */}
          <Card title="Overview" icon={Activity} cardKey="overview" isExpanded={expandedCards.overview} onToggle={toggleCard}>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Stat label="Bars" value={analysisResult.bars} />
              <Stat label="Date Range" value={`${analysisResult.date_range.start?.split(" ")[0]} → ${analysisResult.date_range.end?.split(" ")[0]}`} />
              <Stat label="Avg Close" value={`₹${analysisResult.price_stats?.close_mean}`} />
              <Stat label="Close Std" value={`₹${analysisResult.price_stats?.close_std}`} />
              <Stat label="Avg Range" value={`₹${analysisResult.price_stats?.avg_range}`} />
              <Stat label="Body/Range" value={analysisResult.price_stats?.body_to_range_ratio} />
              <Stat label="Max High" value={`₹${analysisResult.price_stats?.high_max}`} />
              <Stat label="Min Low" value={`₹${analysisResult.price_stats?.low_min}`} />
            </div>
            <div className="mt-4 h-64">
              <ReactECharts option={priceChartOpt} style={{ height: "100%" }} />
            </div>
          </Card>

          {/* Returns */}
          <Card title="Returns Analysis" icon={TrendingUp} cardKey="returns" isExpanded={expandedCards.returns} onToggle={toggleCard}>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <Stat label="Mean Return" value={analysisResult.returns?.mean_return_pct} suffix="%" />
              <Stat label="Std Return" value={analysisResult.returns?.std_return_pct} suffix="%" />
              <Stat label="Ann. Return" value={analysisResult.returns?.annualized_return_pct || "—"} suffix="%" />
              <Stat label="Ann. Vol" value={analysisResult.returns?.annualized_vol_pct} suffix="%" />
              <Stat label="Sharpe (approx)" value={analysisResult.returns?.sharpe_approx} />
              <Stat label="Skewness" value={analysisResult.returns?.skewness} color={analysisResult.returns?.skewness < 0 ? "text-rose-400" : "text-slate-200"} />
              <Stat label="Kurtosis" value={analysisResult.returns?.kurtosis} />
              <Stat label="Normal?" value={analysisResult.returns?.is_normal ? "Yes" : "No"} color={analysisResult.returns?.is_normal ? "text-emerald-400" : "text-amber-400"} />
              <Stat label="VaR (95%)" value={analysisResult.returns?.var_95_pct} suffix="%" color="text-rose-400" />
              <Stat label="CVaR (95%)" value={analysisResult.returns?.cvar_95_pct} suffix="%" color="text-rose-400" />
              <Stat label="Max Gain" value={analysisResult.returns?.max_single_gain_pct} suffix="%" color="text-emerald-400" />
              <Stat label="Max Loss" value={analysisResult.returns?.max_single_loss_pct} suffix="%" color="text-rose-400" />
            </div>
            <div className="h-48">
              <ReactECharts option={returnsDistChartOpt} style={{ height: "100%" }} />
            </div>
          </Card>

          {/* Volatility */}
          <Card title="Volatility Analysis" icon={Zap} cardKey="volatility" isExpanded={expandedCards.volatility} onToggle={toggleCard}>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <Stat label="Realized Vol" value={analysisResult.volatility?.realized_vol_annual_pct} suffix="%" />
              <Stat label="EWMA Vol" value={analysisResult.volatility?.ewma_vol_annual_pct} suffix="%" />
              <Stat label="Vol of Vol" value={analysisResult.volatility?.vol_of_vol} />
              <Stat label="Current Regime" value={analysisResult.volatility?.current_vol_regime} color={
                analysisResult.volatility?.current_vol_regime === "HIGH" ? "text-rose-400" :
                analysisResult.volatility?.current_vol_regime === "LOW" ? "text-emerald-400" : "text-amber-400"
              } />
              <Stat label="Current Vol" value={analysisResult.volatility?.current_vol_pct} suffix="%" />
              <Stat label="Vol Median" value={analysisResult.volatility?.vol_median_pct} suffix="%" />
              <Stat label="Vol Max" value={analysisResult.volatility?.vol_max_pct} suffix="%" />
              <Stat label="Vol Min" value={analysisResult.volatility?.vol_min_pct} suffix="%" />
            </div>
            <div className="h-48">
              <ReactECharts option={volChartOpt} style={{ height: "100%" }} />
            </div>
          </Card>

          {/* Trend */}
          <Card title="Trend & Momentum" icon={Target} cardKey="trend" isExpanded={expandedCards.trend} onToggle={toggleCard}>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Stat label="Direction" value={analysisResult.trend?.trend_direction} color={
                analysisResult.trend?.trend_direction === "BULLISH" ? "text-emerald-400" :
                analysisResult.trend?.trend_direction === "BEARISH" ? "text-rose-400" : "text-slate-400"
              } />
              <Stat label="R²" value={analysisResult.trend?.r_squared} />
              <Stat label="Linear Slope" value={analysisResult.trend?.linear_slope} />
              <Stat label="Is Trending?" value={analysisResult.trend?.is_trending ? "Yes" : "No"} color={analysisResult.trend?.is_trending ? "text-emerald-400" : "text-slate-400"} />
              <Stat label="EMA 20" value={`₹${analysisResult.trend?.ema20}`} />
              <Stat label="EMA 50" value={`₹${analysisResult.trend?.ema50}`} />
              <Stat label="vs EMA20" value={`${analysisResult.trend?.price_vs_ema20_pct}%`} color={analysisResult.trend?.price_vs_ema20_pct >= 0 ? "text-emerald-400" : "text-rose-400"} />
              <Stat label="ADX Proxy" value={analysisResult.trend?.adx_proxy} />
            </div>
          </Card>

          {/* Drawdown */}
          <Card title="Drawdown Analysis" icon={ArrowDownRight} cardKey="drawdown" isExpanded={expandedCards.drawdown} onToggle={toggleCard}>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <Stat label="Max DD" value={`${analysisResult.drawdown?.max_drawdown_pct}%`} color="text-rose-400" />
              <Stat label="Max DD Date" value={analysisResult.drawdown?.max_dd_date?.split(" ")[0] || "—"} />
              <Stat label="Avg DD Duration" value={`${analysisResult.drawdown?.avg_drawdown_duration_bars} bars`} />
              <Stat label="Max DD Duration" value={`${analysisResult.drawdown?.max_drawdown_duration_bars} bars`} />
              <Stat label="Current DD" value={`${analysisResult.drawdown?.current_drawdown_pct}%`} color={analysisResult.drawdown?.current_drawdown_pct < -5 ? "text-rose-400" : "text-slate-200"} />
              <Stat label="Time Underwater" value={`${analysisResult.drawdown?.underwater_pct}%`} />
            </div>
            <div className="h-48">
              <ReactECharts option={drawdownChartOpt} style={{ height: "100%" }} />
            </div>
          </Card>

          {/* Levels */}
          <Card title="Support & Resistance" icon={Layers} cardKey="levels" isExpanded={expandedCards.levels} onToggle={toggleCard}>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
              <Stat label="Rolling High" value={`₹${analysisResult.levels?.rolling_high}`} />
              <Stat label="Rolling Low" value={`₹${analysisResult.levels?.rolling_low}`} />
              <Stat label="Nearest Res." value={analysisResult.levels?.nearest_resistance ? `₹${analysisResult.levels.nearest_resistance.price}` : "—"} />
              <Stat label="Nearest Sup." value={analysisResult.levels?.nearest_support ? `₹${analysisResult.levels.nearest_support.price}` : "—"} />
            </div>
            {analysisResult.levels?.pivots?.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[11px] text-slate-400">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-300">
                      <th className="py-2">Type</th>
                      <th>Price</th>
                      <th>Strength</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/50">
                    {analysisResult.levels.pivots.map((p: any, i: number) => (
                      <tr key={i} className="hover:bg-slate-900/30">
                        <td className={`py-2 font-bold ${p.type === "support" ? "text-emerald-400" : "text-rose-400"}`}>
                          {p.type.toUpperCase()}
                        </td>
                        <td className="font-mono">₹{p.price.toFixed(2)}</td>
                        <td className="font-mono">{p.strength}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {/* Volume */}
          {analysisResult.volume?.available && (
            <Card title="Volume Analysis" icon={BarChart3} cardKey="volume" isExpanded={expandedCards.volume} onToggle={toggleCard}>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Stat label="Avg Volume" value={analysisResult.volume?.avg_volume?.toLocaleString()} />
                <Stat label="Rel. Volume" value={`${analysisResult.volume?.relative_volume}x`} />
                <Stat label="Vol-Price Corr" value={analysisResult.volume?.volume_price_corr} />
                <Stat label="Vol Trend" value={analysisResult.volume?.volume_trend} color={analysisResult.volume?.volume_trend === "RISING" ? "text-emerald-400" : "text-rose-400"} />
              </div>
            </Card>
          )}

          {/* Regimes */}
          <Card title="Market Regimes" icon={PieChart} cardKey="regimes" isExpanded={expandedCards.regimes} onToggle={toggleCard}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="h-56">
                <ReactECharts option={regimeChartOpt} style={{ height: "100%" }} />
              </div>
              <div className="space-y-2">
                {Object.entries(analysisResult.regimes || {}).map(([regime, pct]: [string, any]) => (
                  <div key={regime} className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">{regime.replace(/_/g, " ")}</span>
                    <span className="font-mono font-bold text-slate-200">{pct}%</span>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          {/* Seasonality */}
          {analysisResult.seasonality && Object.keys(analysisResult.seasonality).length > 0 && (
            <Card title="Seasonality" icon={Calendar} cardKey="seasonality" isExpanded={expandedCards.seasonality} onToggle={toggleCard}>
              <div className="h-48">
                <ReactECharts option={seasonalityChartOpt} style={{ height: "100%" }} />
              </div>
              {analysisResult.seasonality?.hourly && (
                <div className="mt-3 text-xs text-slate-400">
                  Best hour: {analysisResult.seasonality.hourly.best_hour}:00 ({analysisResult.seasonality.hourly.best_hour_return_pct}%)<br/>
                  Worst hour: {analysisResult.seasonality.hourly.worst_hour}:00 ({analysisResult.seasonality.hourly.worst_hour_return_pct}%)
                </div>
              )}
            </Card>
          )}

          {/* Patterns */}
          <Card title="Candlestick Patterns" icon={AlertTriangle} cardKey="patterns" isExpanded={expandedCards.patterns} onToggle={toggleCard}>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <Stat label="Doji" value={`${analysisResult.patterns?.doji_count} (${analysisResult.patterns?.doji_pct}%)`} />
              <Stat label="Hammer" value={analysisResult.patterns?.hammer_count} />
              <Stat label="Shooting Star" value={analysisResult.patterns?.shooting_star_count} />
              <Stat label="Bull Engulf" value={analysisResult.patterns?.bullish_engulfing_count} />
              <Stat label="Bear Engulf" value={analysisResult.patterns?.bearish_engulfing_count} />
            </div>
          </Card>

          {/* Autocorrelation */}
          <Card title="Autocorrelation" icon={Clock} cardKey="autocorr" isExpanded={expandedCards.autocorr} onToggle={toggleCard}>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {analysisResult.autocorrelation?.lags?.map((lag: any) => (
                <Stat
                  key={lag.lag}
                  label={`Lag-${lag.lag}`}
                  value={lag.autocorr}
                  color={lag.autocorr > 0.1 ? "text-emerald-400" : lag.autocorr < -0.1 ? "text-rose-400" : "text-slate-400"}
                />
              ))}
            </div>
          </Card>

          {/* Strategy Tuning Summary — actionable digest at the bottom */}
          <Card title="Strategy Tuning Summary" icon={Zap} cardKey="tuning-summary" isExpanded={expandedCards["tuning-summary"] ?? true} onToggle={toggleCard}>
            <div className="space-y-4">
              {/* Top-line verdict */}
              <div className="bg-slate-950 border border-slate-800 rounded-lg p-4">
                <div className="text-[10px] uppercase font-bold text-slate-500 mb-2">Verdict</div>
                <div className="text-sm text-slate-300 leading-relaxed">
                  {(() => {
                    const rec = analysisResult.suitability?.recommended?.replace(/_/g, " ") || "unknown";
                    const score = analysisResult.suitability?.recommended_score || 0;
                    const trend = analysisResult.trend?.trend_direction;
                    const vol = analysisResult.volatility?.current_vol_regime;
                    const skew = analysisResult.returns?.skewness;
                    const ac1 = analysisResult.autocorrelation?.lags?.[0]?.autocorr;
                    const posPct = analysisResult.returns?.positive_bars_pct;
                    return (
                      <span>
                        <span className="font-bold text-emerald-400">{rec.toUpperCase()}</span> is the best-fit strategy family (score {score}/100). 
                        Market is <span className={`font-bold ${trend === "BULLISH" ? "text-emerald-400" : trend === "BEARISH" ? "text-rose-400" : "text-amber-400"}`}>{trend}</span> with 
                        <span className={`font-bold ${vol === "HIGH" ? "text-rose-400" : vol === "LOW" ? "text-emerald-400" : "text-amber-400"}`}>{vol}</span> volatility. 
                        {skew < -0.5 ? "Negative skew — tighten stops. " : skew > 0.5 ? "Positive skew — wider targets may work. " : ""}
                        {ac1 > 0.1 ? "Momentum persistence detected — ride the trend. " : ac1 < -0.1 ? "Mean-reversion signal — fade moves. " : ""}
                        {posPct > 55 ? "Up-bar bias — lean long. " : posPct < 45 ? "Down-bar bias — lean short or stay flat. " : ""}
                      </span>
                    );
                  })()}
                </div>
              </div>

              {/* Parameter tuning table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[11px]">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-500">
                      <th className="py-2 pr-4">Parameter</th>
                      <th className="py-2 pr-4">Value</th>
                      <th className="py-2">Tuning Guidance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/50 text-slate-300">
                    <tr>
                      <td className="py-2 pr-4 font-mono text-slate-400">avg_range</td>
                      <td className="py-2 pr-4 font-mono">₹{analysisResult.price_stats?.avg_range}</td>
                      <td className="py-2">Scale stop-loss & profit targets to this range. ATR-based stops should use ~1.5–2× this value.</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 font-mono text-slate-400">body_to_range</td>
                      <td className="py-2 pr-4 font-mono">{analysisResult.price_stats?.body_to_range_ratio}</td>
                      <td className="py-2">{analysisResult.price_stats?.body_to_range_ratio > 0.6 ? "Strong directional candles — trend strategies favored." : analysisResult.price_stats?.body_to_range_ratio < 0.3 ? "Weak bodies, long wicks — ranging/mean-reversion environment." : "Mixed — use confirmation filters."}</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 font-mono text-slate-400">annualized_vol</td>
                      <td className="py-2 pr-4 font-mono">{analysisResult.returns?.annualized_vol_pct}%</td>
                      <td className="py-2">{analysisResult.returns?.annualized_vol_pct > 40 ? "High vol — reduce position size, widen stops." : analysisResult.returns?.annualized_vol_pct < 15 ? "Low vol — tighter stops, watch for breakout compression." : "Moderate vol — standard sizing."}</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 font-mono text-slate-400">sharpe_approx</td>
                      <td className="py-2 pr-4 font-mono">{analysisResult.returns?.sharpe_approx}</td>
                      <td className="py-2">{analysisResult.returns?.sharpe_approx > 1 ? "Good risk-adjusted drift — directional bias pays." : "Weak drift — need edge from timing, not buy-and-hold."}</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 font-mono text-slate-400">max_drawdown</td>
                      <td className="py-2 pr-4 font-mono">{analysisResult.drawdown?.max_drawdown_pct}%</td>
                      <td className="py-2">Cap strategy risk so live drawdown does not exceed this historical worst case.</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 font-mono text-slate-400">var_95 / cvar_95</td>
                      <td className="py-2 pr-4 font-mono">{analysisResult.returns?.var_95_pct}% / {analysisResult.returns?.cvar_95_pct}%</td>
                      <td className="py-2">Size positions so a 1-day tail event does not exceed your max loss budget.</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 font-mono text-slate-400">autocorr_lag1</td>
                      <td className="py-2 pr-4 font-mono">{analysisResult.autocorrelation?.lags?.[0]?.autocorr}</td>
                      <td className="py-2">{analysisResult.autocorrelation?.lags?.[0]?.autocorr > 0.1 ? "Positive serial correlation — momentum filters (e.g. EMA cross) should help." : analysisResult.autocorrelation?.lags?.[0]?.autocorr < -0.1 ? "Negative serial correlation — mean-reversion (RSI, Bollinger) should help." : "No clear serial correlation — need stronger signal filters."}</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 font-mono text-slate-400">win_rate_bias</td>
                      <td className="py-2 pr-4 font-mono">{analysisResult.returns?.positive_bars_pct}%</td>
                      <td className="py-2">{analysisResult.returns?.positive_bars_pct > 55 ? "Up-bar bias — long-only or long-biased strategies have tailwind." : analysisResult.returns?.positive_bars_pct < 45 ? "Down-bar bias — short-biased or market-neutral may outperform." : "Balanced — direction-agnostic strategies work best."}</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 font-mono text-slate-400">adx_proxy</td>
                      <td className="py-2 pr-4 font-mono">{analysisResult.trend?.adx_proxy}</td>
                      <td className="py-2">{analysisResult.trend?.adx_proxy > 25 ? "Strong trend strength — trend-following with wide stops." : "Weak trend — avoid pure trend strategies; use range or hybrid."}</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 font-mono text-slate-400">r_squared</td>
                      <td className="py-2 pr-4 font-mono">{analysisResult.trend?.r_squared}</td>
                      <td className="py-2">{analysisResult.trend?.r_squared > 0.3 ? "Significant linear trend — EMA/slope-based entries are valid." : "Noisy price action — avoid linear trend signals."}</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 font-mono text-slate-400">nearest_support</td>
                      <td className="py-2 pr-4 font-mono">₹{analysisResult.levels?.nearest_support?.price || "—"}</td>
                      <td className="py-2">Use as stop-loss anchor for long positions. Trail below this level.</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 font-mono text-slate-400">nearest_resistance</td>
                      <td className="py-2 pr-4 font-mono">₹{analysisResult.levels?.nearest_resistance?.price || "—"}</td>
                      <td className="py-2">Use as profit target for long positions. Short entries near this level.</td>
                    </tr>
                    {analysisResult.seasonality?.hourly && (
                      <tr>
                        <td className="py-2 pr-4 font-mono text-slate-400">best_hour</td>
                        <td className="py-2 pr-4 font-mono">{analysisResult.seasonality.hourly.best_hour}:00</td>
                        <td className="py-2">Concentrate entries during this hour for best edge. Avoid the worst hour.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Copy-friendly raw JSON */}
              <div className="bg-slate-950 border border-slate-800 rounded-lg overflow-hidden">
                <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800 bg-slate-950/50">
                  <span className="text-[10px] font-bold text-slate-500 uppercase">Raw Tuning JSON</span>
                  <button
                    onClick={() => {
                      const tuning = {
                        symbol: analysisResult.symbol,
                        interval: analysisResult.interval,
                        bars: analysisResult.bars,
                        recommended_strategy: analysisResult.suitability?.recommended,
                        recommended_score: analysisResult.suitability?.recommended_score,
                        trend_direction: analysisResult.trend?.trend_direction,
                        vol_regime: analysisResult.volatility?.current_vol_regime,
                        avg_range: analysisResult.price_stats?.avg_range,
                        body_to_range_ratio: analysisResult.price_stats?.body_to_range_ratio,
                        annualized_vol_pct: analysisResult.returns?.annualized_vol_pct,
                        sharpe_approx: analysisResult.returns?.sharpe_approx,
                        skewness: analysisResult.returns?.skewness,
                        max_drawdown_pct: analysisResult.drawdown?.max_drawdown_pct,
                        var_95_pct: analysisResult.returns?.var_95_pct,
                        cvar_95_pct: analysisResult.returns?.cvar_95_pct,
                        autocorr_lag1: analysisResult.autocorrelation?.lags?.[0]?.autocorr,
                        positive_bars_pct: analysisResult.returns?.positive_bars_pct,
                        adx_proxy: analysisResult.trend?.adx_proxy,
                        r_squared: analysisResult.trend?.r_squared,
                        nearest_support: analysisResult.levels?.nearest_support?.price,
                        nearest_resistance: analysisResult.levels?.nearest_resistance?.price,
                        best_hour: analysisResult.seasonality?.hourly?.best_hour,
                        regime_distribution: analysisResult.regimes,
                      };
                      navigator.clipboard.writeText(JSON.stringify(tuning, null, 2));
                      setNotif({ type: "info", msg: "Tuning JSON copied to clipboard" });
                    }}
                    className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    Copy JSON
                  </button>
                </div>
                <pre className="p-3 overflow-x-auto text-[10px] font-mono text-slate-400 leading-relaxed max-h-40">
{(() => {
  const tuning = {
    symbol: analysisResult.symbol,
    interval: analysisResult.interval,
    bars: analysisResult.bars,
    recommended_strategy: analysisResult.suitability?.recommended,
    recommended_score: analysisResult.suitability?.recommended_score,
    trend_direction: analysisResult.trend?.trend_direction,
    vol_regime: analysisResult.volatility?.current_vol_regime,
    avg_range: analysisResult.price_stats?.avg_range,
    body_to_range_ratio: analysisResult.price_stats?.body_to_range_ratio,
    annualized_vol_pct: analysisResult.returns?.annualized_vol_pct,
    sharpe_approx: analysisResult.returns?.sharpe_approx,
    skewness: analysisResult.returns?.skewness,
    max_drawdown_pct: analysisResult.drawdown?.max_drawdown_pct,
    var_95_pct: analysisResult.returns?.var_95_pct,
    cvar_95_pct: analysisResult.returns?.cvar_95_pct,
    autocorr_lag1: analysisResult.autocorrelation?.lags?.[0]?.autocorr,
    positive_bars_pct: analysisResult.returns?.positive_bars_pct,
    adx_proxy: analysisResult.trend?.adx_proxy,
    r_squared: analysisResult.trend?.r_squared,
    nearest_support: analysisResult.levels?.nearest_support?.price,
    nearest_resistance: analysisResult.levels?.nearest_resistance?.price,
    best_hour: analysisResult.seasonality?.hourly?.best_hour,
    regime_distribution: analysisResult.regimes,
  };
  return JSON.stringify(tuning, null, 2);
})()}
                </pre>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Empty state */}
      {!analysisResult && !analysisLoading && (
        <div className="glass-panel p-12 text-center text-slate-500 rounded-xl">
          <BarChart2 size={40} className="mx-auto mb-3 text-slate-700" />
          <p className="text-sm font-medium">Select a dataset and run deep analysis</p>
          <p className="text-xs mt-1">Statistical profiling, regime detection, and strategy suitability scoring</p>
        </div>
      )}
    </div>
  );
}
