"use client";

import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import dynamic from "next/dynamic";
import {
  BarChart2, Play, Terminal, TrendingUp, TrendingDown, Activity,
  ArrowUpRight, ArrowDownRight, Clock, Calendar, Zap, Shield,
  Target, Layers, Loader2, Database, AlertTriangle, CheckCircle2,
  XCircle, BarChart3, PieChart, Copy, Check, ChevronRight, Info, HelpCircle
} from "lucide-react";
import { api } from "../lib/api-client";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

/* ─── Premium Sub-Components ─── */

interface StatCardProps {
  label: string;
  value: string | number;
  suffix?: string;
  desc?: string;
  color?: string;
  badge?: string;
  badgeColor?: string;
}

const StatCard = ({ label, value, suffix = "", desc, color = "text-slate-850 dark:text-slate-100", badge, badgeColor = "bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-100 dark:border-blue-900/30" }: StatCardProps) => (
  <div className="glass-panel rounded-xl p-4 flex flex-col justify-between shadow-xs hover:border-slate-350 dark:hover:border-slate-700/60 transition-all duration-300">
    <div className="flex items-start justify-between mb-2">
      <span className="text-[10px] tracking-wider uppercase font-bold text-slate-500">{label}</span>
      {badge && (
        <span className={`text-[9px] px-2 py-0.5 rounded font-mono font-bold uppercase tracking-wider ${badgeColor}`}>
          {badge}
        </span>
      )}
    </div>
    <div>
      <div className={`text-xl font-mono font-bold tracking-tight ${color}`}>
        {value}{suffix}
      </div>
      {desc && <p className="text-[10px] text-slate-500 mt-1 leading-normal">{desc}</p>}
    </div>
  </div>
);

interface PatternBadgeProps {
  name: string;
  count: number;
  pct?: number;
  type?: "bullish" | "bearish" | "neutral";
}

const PatternBadge = ({ name, count, pct, type = "neutral" }: PatternBadgeProps) => {
  const colorMap = {
    bullish: "border-emerald-200 dark:border-emerald-800/50 bg-emerald-50 dark:bg-emerald-950/20 text-emerald-600 dark:text-emerald-450 hover:bg-emerald-100 dark:hover:bg-emerald-950/30",
    bearish: "border-rose-200 dark:border-rose-805/50 bg-rose-50 dark:bg-rose-955/20 text-rose-600 dark:text-rose-450 hover:bg-rose-100 dark:hover:bg-rose-955/30",
    neutral: "border-slate-200 dark:border-slate-800/50 bg-slate-50 dark:bg-slate-950/30 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-950/40"
  };

  return (
    <div className={`flex items-center justify-between border rounded-lg px-3 py-2.5 transition-colors duration-200 ${colorMap[type]}`}>
      <span className="text-xs font-semibold">{name}</span>
      <div className="flex items-center gap-2 font-mono text-xs font-bold">
        <span className="opacity-90">{count}</span>
        {pct !== undefined && (
          <span className="text-[10px] opacity-60">({pct}%)</span>
        )}
      </div>
    </div>
  );
};

interface RegimeProgressProps {
  name: string;
  pct: number;
  color: string;
  desc: string;
}

const RegimeProgress = ({ name, pct, color, desc }: RegimeProgressProps) => (
  <div className="space-y-1.5 p-3 rounded-lg border border-slate-200 dark:border-slate-800/40 bg-slate-50 dark:bg-slate-950/25">
    <div className="flex items-center justify-between text-xs font-medium">
      <div className="flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
        <span className="text-slate-750 dark:text-slate-300 font-bold">{name.replace(/_/g, " ")}</span>
      </div>
      <span className="font-mono text-slate-800 dark:text-slate-200 font-bold">{pct}%</span>
    </div>
    <div className="w-full bg-slate-200 dark:bg-slate-900 rounded-full h-1.5 overflow-hidden">
      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
    </div>
    <p className="text-[10px] text-slate-500 leading-normal">{desc}</p>
  </div>
);

interface SuitabilityProgressProps {
  name: string;
  score: number;
  isRecommended: boolean;
}

const SuitabilityProgress = ({ name, score, isRecommended }: SuitabilityProgressProps) => {
  const getSuitabilityColor = (val: number) => {
    if (val >= 65) return { bar: "bg-emerald-500", glow: "dark:shadow-[0_0_12px_rgba(16,185,129,0.4)]", text: "text-emerald-600 dark:text-emerald-400" };
    if (val >= 40) return { bar: "bg-amber-500", glow: "dark:shadow-[0_0_12px_rgba(245,158,11,0.4)]", text: "text-amber-600 dark:text-amber-400" };
    return { bar: "bg-rose-500", glow: "dark:shadow-[0_0_12px_rgba(244,63,94,0.4)]", text: "text-rose-600 dark:text-rose-455" };
  };

  const style = getSuitabilityColor(score);

  return (
    <div className={`p-4 rounded-xl border transition-all duration-300 ${
      isRecommended 
        ? "border-emerald-300 dark:border-emerald-800 bg-emerald-500/5 dark:bg-emerald-950/10 shadow-sm" 
        : "border-slate-200 dark:border-slate-800/60 bg-slate-100/30 dark:bg-slate-900/30"
    }`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold ${isRecommended ? "text-emerald-600 dark:text-emerald-400" : "text-slate-500 dark:text-slate-350"}`}>
            {name.replace(/_/g, " ").toUpperCase()}
          </span>
          {isRecommended && (
            <span className="text-[9px] bg-emerald-100 dark:bg-emerald-950/60 text-emerald-750 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-850 px-2 py-0.5 rounded font-bold uppercase tracking-wider animate-pulse">
              Best Fit
            </span>
          )}
        </div>
        <span className={`text-sm font-mono font-black ${style.text}`}>{score}/100</span>
      </div>
      <div className="w-full bg-slate-200 dark:bg-slate-955/60 border border-slate-300/40 dark:border-slate-800/40 rounded-full h-2.5 overflow-hidden">
        <div 
          className={`h-full rounded-full transition-all duration-1000 ${style.bar} ${style.glow}`}
          style={{ width: `${score}%` }} 
        />
      </div>
    </div>
  );
};

/* ─── Main Component ─── */

interface ResearchLabProps {
  datasets: any[];
  apiErrors: Record<string, { error: string; retry: () => void }>;
  setEndpointError: (endpoint: string, error: string | null, retry?: () => void) => void;
  clearEndpointError: (endpoint: string) => void;
  setNotif: (notif: { type: "success" | "error" | "info"; msg: string } | null) => void;
  theme: "dark" | "light";
}

type TabType = "overview" | "returns" | "volatility" | "trend" | "seasonality" | "verdict";

export default function ResearchLab({
  datasets,
  apiErrors,
  setEndpointError,
  clearEndpointError,
  setNotif,
  theme,
}: ResearchLabProps) {
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [logSearch, setLogSearch] = useState<string>("");
  const [logFilter, setLogFilter] = useState<"all" | "info" | "warn" | "recommend">("all");
  const [copied, setCopied] = useState(false);

  const logsEndRef = useRef<HTMLDivElement>(null);

  const datasetOptions = useMemo(() => {
    return datasets.map((val: any) => {
      const key = val.symbol && val.interval ? `${val.symbol}_${val.interval}` : String(val.id || val.key || "");
      return {
        key,
        label: `${val.symbol || key.split("_")[0]} (${val.interval || key.split("_")[1]})`,
        bars: val.records || val.total_records || "?",
      };
    });
  }, [datasets]);

  // Autoscroll logs terminal
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollTop = logsEndRef.current.scrollHeight;
    }
  }, [analysisResult?.logs, analysisLoading]);

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

  const handleCopyJSON = () => {
    if (!analysisResult) return;
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
    setCopied(true);
    setNotif({ type: "success", msg: "Tuning JSON copied to clipboard" });
    setTimeout(() => setCopied(false), 2000);
  };

  // Filter logs inside terminal
  const filteredLogs = useMemo(() => {
    if (!analysisResult?.logs) return [];
    return analysisResult.logs.filter((log: string) => {
      const matchSearch = log.toLowerCase().includes(logSearch.toLowerCase());
      if (!matchSearch) return false;

      if (logFilter === "all") return true;
      if (logFilter === "info") return log.includes("[INFO]") || log.includes("[PRICE]") || log.includes("[LEVELS]") || log.includes("[VOLUME]");
      if (logFilter === "warn") return log.includes("[WARN]") || log.includes("WARNING") || log.includes("[ERROR]");
      if (logFilter === "recommend") return log.includes("RECOMMENDED") || log.includes("[SUITABILITY]") || log.includes("[REGIME]") || log.includes("[AUTOCORR]");
      return true;
    });
  }, [analysisResult?.logs, logSearch, logFilter]);

  const isDark = theme === "dark";
  const labelColor = isDark ? "#64748b" : "#475569";
  const gridLineColor = isDark ? "#0f172a" : "#f1f5f9";
  const borderLineColor = isDark ? "#1e293b" : "#cbd5e1";
  const tooltipBgColor = isDark ? "#0b1222" : "#ffffff";
  const tooltipBorderColor = isDark ? "#1e293b" : "#cbd5e1";
  const tooltipTextColor = isDark ? "#e2e8f0" : "#0f172a";

  /* ─── Custom Premium ECharts Configuration Options ─── */

  const priceChartOpt = useMemo(() => {
    if (!analysisResult?.plot_series) return {};
    const ps = analysisResult.plot_series;
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: tooltipBgColor,
        borderColor: tooltipBorderColor,
        textStyle: { color: tooltipTextColor, fontSize: 11 },
        axisPointer: { type: "cross", lineStyle: { color: "#3b82f6", width: 1, type: "dashed" } }
      },
      grid: [
        { left: 55, right: 15, top: "8%", height: "62%" },
        { left: 55, right: 15, top: "75%", height: "20%" }
      ],
      xAxis: [
        {
          type: "category",
          data: ps.time,
          boundaryGap: true,
          axisLine: { lineStyle: { color: borderLineColor } },
          axisLabel: { color: labelColor, fontSize: 10 },
          splitLine: { show: false }
        },
        {
          type: "category",
          gridIndex: 1,
          data: ps.time,
          boundaryGap: true,
          axisLine: { lineStyle: { color: borderLineColor } },
          axisLabel: { show: false },
          splitLine: { show: false }
        }
      ],
      yAxis: [
        {
          scale: true,
          axisLine: { lineStyle: { color: borderLineColor } },
          axisLabel: { color: labelColor, fontSize: 10 },
          splitLine: { lineStyle: { color: gridLineColor } }
        },
        {
          gridIndex: 1,
          scale: true,
          axisLabel: { show: false },
          axisLine: { show: false },
          splitLine: { show: false }
        }
      ],
      dataZoom: [
        { type: "inside", xAxisIndex: [0, 1] },
        { type: "slider", xAxisIndex: [0, 1], bottom: 0, height: 18, textStyle: { color: labelColor } }
      ],
      series: [
        {
          name: "OHLC Price",
          type: "candlestick",
          data: ps.open.map((o: number, idx: number) => [o, ps.close[idx], ps.low[idx], ps.high[idx]]),
          itemStyle: {
            color: "#10b981",
            color0: "#ef4444",
            borderColor: "#10b981",
            borderColor0: "#ef4444"
          }
        },
        {
          name: "EMA 20",
          type: "line",
          data: ps.ema_fast,
          showSymbol: false,
          lineStyle: { color: "#f59e0b", width: 1.2, opacity: 0.85 }
        },
        {
          name: "EMA 50",
          type: "line",
          data: ps.ema_slow,
          showSymbol: false,
          lineStyle: { color: "#8b5cf6", width: 1.2, opacity: 0.85 }
        },
        {
          name: "Volume",
          type: "bar",
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: ps.volume,
          itemStyle: { color: "rgba(100, 116, 139, 0.2)" }
        }
      ]
    };
  }, [analysisResult?.plot_series, theme]);

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
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: tooltipBgColor,
        borderColor: tooltipBorderColor,
        textStyle: { color: tooltipTextColor, fontSize: 11 }
      },
      grid: { left: 45, right: 15, top: 15, bottom: 45 },
      xAxis: {
        type: "category",
        data: labels,
        axisLine: { lineStyle: { color: borderLineColor } },
        axisLabel: { color: labelColor, fontSize: 9, rotate: 45 }
      },
      yAxis: {
        type: "value",
        axisLine: { lineStyle: { color: borderLineColor } },
        axisLabel: { color: labelColor, fontSize: 10 },
        splitLine: { lineStyle: { color: gridLineColor } }
      },
      series: [
        {
          type: "bar",
          data: counts,
          itemStyle: {
            color: {
              type: "linear",
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: "#3b82f6" },
                { offset: 1, color: "#1d4ed8" }
              ]
            },
            borderRadius: [3, 3, 0, 0]
          },
          barWidth: "85%"
        }
      ]
    };
  }, [analysisResult?.plot_series?.returns, theme]);

  const drawdownChartOpt = useMemo(() => {
    if (!analysisResult?.plot_series?.drawdown) return {};
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: tooltipBgColor,
        borderColor: tooltipBorderColor,
        textStyle: { color: tooltipTextColor, fontSize: 11 }
      },
      grid: { left: 45, right: 15, top: 15, bottom: 35 },
      xAxis: {
        type: "category",
        data: analysisResult.plot_series.time,
        axisLine: { lineStyle: { color: borderLineColor } },
        axisLabel: { color: labelColor, fontSize: 9 }
      },
      yAxis: {
        type: "value",
        axisLine: { lineStyle: { color: borderLineColor } },
        axisLabel: { color: labelColor, fontSize: 10 },
        splitLine: { lineStyle: { color: gridLineColor } }
      },
      series: [
        {
          type: "line",
          data: analysisResult.plot_series.drawdown,
          showSymbol: false,
          lineStyle: { color: "#f43f5e", width: 1.2 },
          areaStyle: {
            color: {
              type: "linear",
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(244, 63, 94, 0.25)" },
                { offset: 1, color: "rgba(244, 63, 94, 0.00)" }
              ]
            }
          }
        }
      ]
    };
  }, [analysisResult?.plot_series?.drawdown, analysisResult?.plot_series?.time, theme]);

  const volChartOpt = useMemo(() => {
    if (!analysisResult?.plot_series?.rolling_vol_20) return {};
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: tooltipBgColor,
        borderColor: tooltipBorderColor,
        textStyle: { color: tooltipTextColor, fontSize: 11 }
      },
      grid: { left: 45, right: 15, top: 15, bottom: 35 },
      xAxis: {
        type: "category",
        data: analysisResult.plot_series.time,
        axisLine: { lineStyle: { color: borderLineColor } },
        axisLabel: { color: labelColor, fontSize: 9 }
      },
      yAxis: {
        type: "value",
        axisLine: { lineStyle: { color: borderLineColor } },
        axisLabel: { color: labelColor, fontSize: 10 },
        splitLine: { lineStyle: { color: gridLineColor } }
      },
      series: [
        {
          type: "line",
          data: analysisResult.plot_series.rolling_vol_20,
          showSymbol: false,
          lineStyle: { color: "#f59e0b", width: 1.2 },
          areaStyle: {
            color: {
              type: "linear",
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(245, 158, 11, 0.15)" },
                { offset: 1, color: "rgba(245, 158, 11, 0.00)" }
              ]
            }
          }
        }
      ]
    };
  }, [analysisResult?.plot_series?.rolling_vol_20, analysisResult?.plot_series?.time, theme]);

  const regimeChartOpt = useMemo(() => {
    if (!analysisResult?.regimes) return {};
    const regimes = analysisResult.regimes;
    const colors: Record<string, string> = {
      TRENDING_BULLISH: "#10b981",
      TRENDING_BEARISH: "#f43f5e",
      VOLATILE_RANGING: "#f59e0b",
      QUIET_RANGING: "#64748b",
      GAP_DAY: "#a855f7",
    };
    const data = Object.entries(regimes).map(([name, pct]: [string, any]) => ({
      name: name.replace(/_/g, " "),
      value: pct,
      itemStyle: { color: colors[name] || "#3b82f6" },
    }));
    return {
      backgroundColor: "transparent",
      tooltip: { trigger: "item", formatter: "{b}: {c}%" },
      series: [
        {
          type: "pie",
          radius: ["45%", "75%"],
          avoidLabelOverlap: true,
          itemStyle: {
            borderRadius: 5,
            borderColor: isDark ? "#060913" : "#ffffff",
            borderWidth: 2
          },
          label: { show: false, position: "center" },
          emphasis: {
            label: {
              show: true,
              fontSize: 12,
              fontWeight: "bold",
              color: tooltipTextColor,
              formatter: "{b}\n{c}%"
            }
          },
          data
        }
      ]
    };
  }, [analysisResult?.regimes, theme]);

  const seasonalityChartOpt = useMemo(() => {
    if (!analysisResult?.seasonality?.dow?.dow_data) return {};
    const dowData = analysisResult.seasonality.dow.dow_data;
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: tooltipBgColor,
        borderColor: tooltipBorderColor,
        textStyle: { color: tooltipTextColor, fontSize: 11 }
      },
      grid: { left: 45, right: 15, top: 15, bottom: 35 },
      xAxis: {
        type: "category",
        data: dowData.map((d: any) => d.day),
        axisLine: { lineStyle: { color: borderLineColor } },
        axisLabel: { color: labelColor, fontSize: 10 }
      },
      yAxis: {
        type: "value",
        axisLine: { lineStyle: { color: borderLineColor } },
        axisLabel: { color: labelColor, fontSize: 10, formatter: "{value}%" },
        splitLine: { lineStyle: { color: gridLineColor } }
      },
      series: [
        {
          type: "bar",
          data: dowData.map((d: any) => d.mean_return_pct),
          itemStyle: {
            color: (params: any) => params.value >= 0 ? "#10b981" : "#f43f5e",
            borderRadius: [3, 3, 0, 0]
          },
          barWidth: "45%"
        }
      ]
    };
  }, [analysisResult?.seasonality?.dow?.dow_data, theme]);

  return (
    <div className="flex flex-col lg:flex-row gap-6 items-stretch">
      {/* ─── Left Sidebar Controls + Logs Terminal ─── */}
      <div className="w-full lg:w-80 flex-shrink-0 flex flex-col gap-6">
        
        {/* Controls Card */}
        <div className="glass-panel p-5 rounded-xl shadow-xl space-y-4" style={{ borderColor: 'var(--border-color)' }}>
          <div className="pb-3 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border-color)' }}>
            <BarChart2 size={16} className="text-blue-400" />
            <h4 className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>Target Dataset</h4>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-[10px] uppercase font-bold mb-1.5" style={{ color: 'var(--text-tertiary)' }}>Select File</label>
              <select
                className="t-input w-full rounded-lg px-3 py-2 text-xs font-medium transition-colors"
                value={selectedDataset}
                onChange={(e) => setSelectedDataset(e.target.value)}
              >
                <option value="">Choose a dataset...</option>
                {datasetOptions.map((opt) => (
                  <option key={opt.key} value={opt.key}>
                    {opt.label} [{opt.bars} bars]
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={runAnalysis}
              disabled={analysisLoading || !selectedDataset}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed border border-transparent text-white py-2.5 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-all"
            >
              {analysisLoading ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
              {analysisLoading ? "Running Diagnostics..." : "Analyze Dataset"}
            </button>
          </div>

          {apiErrors["research/analyze"] && (
            <div className="bg-rose-950/20 border border-rose-800/40 rounded-lg p-3 flex flex-col gap-1.5">
              <span className="text-[10px] text-rose-400 leading-normal">{apiErrors["research/analyze"].error}</span>
              <button
                onClick={apiErrors["research/analyze"].retry}
                className="text-[10px] text-rose-400 hover:text-rose-200 underline font-bold w-fit"
              >
                Retry Request
              </button>
            </div>
          )}
        </div>

        {/* Glowing Logs Terminal Console */}
        <div className="glass-panel rounded-xl overflow-hidden border-slate-800/60 shadow-xl flex-1 flex flex-col min-h-[300px]">
          <div className="px-4 py-3 border-b border-slate-800/80 bg-slate-950/40 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal size={13} className="text-emerald-450" />
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Lab Console</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-ping" />
              <span className="text-[9px] font-mono text-slate-500">online</span>
            </div>
          </div>

          {/* Terminal Search and Filter */}
          <div className="p-2 border-b border-slate-800/60 bg-slate-950/20 flex flex-col gap-1.5">
            <input
              type="text"
              placeholder="Search logs..."
              className="bg-slate-950/80 border border-slate-700/60 rounded px-2.5 py-1 text-[10px] text-slate-300 focus:outline-none focus:border-slate-500 placeholder:text-slate-600"
              value={logSearch}
              onChange={(e) => setLogSearch(e.target.value)}
            />
            <div className="flex gap-1">
              {(["all", "info", "warn", "recommend"] as const).map((filter) => (
                <button
                  key={filter}
                  onClick={() => setLogFilter(filter)}
                  className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase transition-colors ${
                    logFilter === filter
                      ? "bg-slate-800 text-slate-200"
                      : "text-slate-500 hover:text-slate-400 hover:bg-slate-900/30"
                  }`}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          {/* Terminal output */}
          <div
            ref={logsEndRef}
            className="flex-1 overflow-y-auto p-4 space-y-1.5 font-mono text-[10px] bg-slate-950/60 leading-normal"
          >
            {analysisLoading && (
              <div className="text-blue-400 flex items-center gap-2 py-2">
                <Loader2 size={10} className="animate-spin" />
                <span>Initializing quantitative profiling engine...</span>
              </div>
            )}

            {!analysisResult && !analysisLoading && (
              <div className="text-slate-600 italic py-4 text-center">
                Console idle. Awaiting dataset diagnostics execution.
              </div>
            )}

            {analysisResult && filteredLogs.length === 0 && (
              <div className="text-slate-600 italic py-2">
                No logs matching filter constraints.
              </div>
            )}

            {analysisResult && filteredLogs.map((log: string, i: number) => {
              const isError = log.includes("[ERROR]");
              const isWarn = log.includes("[WARN]") || log.includes("WARNING");
              const isRec = log.includes("RECOMMENDED") || log.includes("[SUITABILITY]");
              
              let textColor = "text-slate-450";
              if (isError) textColor = "text-rose-400 font-semibold";
              else if (isWarn) textColor = "text-amber-400";
              else if (isRec) textColor = "text-emerald-400 font-bold";

              return (
                <div key={i} className={`whitespace-pre-wrap border-l-2 pl-1.5 border-transparent ${textColor}`}>
                  {log}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ─── Right Analytics Workspace ─── */}
      <div className="flex-1 min-w-0 flex flex-col gap-6">
        
        {/* If Active Result - Top Ribbon Metadata Header */}
        {analysisResult && analysisResult.valid && (
          <div className="glass-panel p-4 rounded-xl border-slate-800/60 shadow-lg flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="bg-blue-500/10 border border-blue-800/30 rounded-lg p-2 flex items-center justify-center">
                <Activity size={18} className="text-blue-400" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-slate-100 text-sm leading-tight uppercase font-mono">
                    {analysisResult.symbol}
                  </h3>
                  <span className="text-[10px] bg-slate-800 border border-slate-700/50 rounded-full px-2 py-0.5 font-bold font-mono text-slate-300">
                    {analysisResult.interval}
                  </span>
                </div>
                <p className="text-[10px] text-slate-500 mt-0.5">
                  Range: <span className="font-mono text-slate-400">{analysisResult.date_range.start?.split(" ")[0]}</span> to <span className="font-mono text-slate-400">{analysisResult.date_range.end?.split(" ")[0]}</span>
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-6">
              <div className="text-right">
                <span className="text-[9px] uppercase font-bold text-slate-500 block">Bars Analyzed</span>
                <span className="font-mono text-xs font-bold text-slate-300">{analysisResult.bars}</span>
              </div>
              <div className="text-right">
                <span className="text-[9px] uppercase font-bold text-slate-500 block">Volatility Regime</span>
                <span className={`text-xs font-bold tracking-wide uppercase ${
                  analysisResult.volatility?.current_vol_regime === "HIGH" ? "text-rose-400" :
                  analysisResult.volatility?.current_vol_regime === "LOW" ? "text-emerald-400" : "text-amber-400"
                }`}>
                  {analysisResult.volatility?.current_vol_regime}
                </span>
              </div>
              <div className="text-right border-l border-slate-800 pl-6">
                <span className="text-[9px] uppercase font-bold text-slate-500 block">Recommended Strategy</span>
                <span className="text-xs font-bold text-emerald-400 uppercase tracking-wide">
                  {analysisResult.suitability?.recommended?.replace(/_/g, " ")}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Tab System & Workspace Viewer */}
        {analysisResult && analysisResult.valid ? (
          <div className="flex flex-col gap-6 flex-1">
            
            {/* Custom Glowing Tabs List */}
            <div className="flex items-center gap-1.5 overflow-x-auto border-b border-slate-800/80 pb-px">
              {(
                [
                  { id: "overview", label: "Overview", icon: BarChart2 },
                  { id: "returns", label: "Returns & Risk", icon: TrendingUp },
                  { id: "volatility", label: "Volatility & Regimes", icon: Zap },
                  { id: "trend", label: "Trend & Levels", icon: Target },
                  { id: "seasonality", label: "Seasonality & Volume", icon: Calendar },
                  { id: "verdict", label: "Verdict & Tuning", icon: Shield }
                ] as const
              ).map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center gap-2 px-4 py-2.5 border-b-2 text-xs font-bold tracking-wide uppercase transition-all whitespace-nowrap cursor-pointer ${
                      isActive
                        ? "border-blue-500 text-blue-400 bg-blue-500/5"
                        : "border-transparent text-slate-500 hover:text-slate-350 hover:border-slate-800/80"
                    }`}
                  >
                    <Icon size={12} className={isActive ? "text-blue-400" : "text-slate-500"} />
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* TAB CONTAINER CONTENT */}
            <div className="flex-1">
              
              {/* ─── TAB 1: CHART & CANDLESTICK PROFILE ─── */}
              {activeTab === "overview" && (
                <div className="space-y-6">
                  {/* Candlestick ECharts */}
                  <div className="glass-panel p-5 rounded-xl border-slate-800/60 shadow-lg">
                    <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
                      <div>
                        <h4 className="text-xs font-bold text-slate-250 uppercase flex items-center gap-1.5">
                          <Activity size={12} className="text-blue-400" />
                          OHLCV Price Series
                        </h4>
                        <p className="text-[10px] text-slate-500 mt-0.5">Zoom and drag to review raw market candle structures with EMA 20 & 50.</p>
                      </div>
                    </div>
                    <div className="h-88">
                      <ReactECharts option={priceChartOpt} style={{ height: "100%" }} />
                    </div>
                  </div>

                  {/* Descriptive Stats Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <StatCard 
                      label="Average Close" 
                      value={`₹${analysisResult.price_stats?.close_mean}`} 
                      desc="Mean price across the complete dataset range." 
                    />
                    <StatCard 
                      label="Close Volatility" 
                      value={`₹${analysisResult.price_stats?.close_std}`} 
                      desc="Standard deviation of closes (nominal spread)." 
                    />
                    <StatCard 
                      label="Average Candle Range" 
                      value={`₹${analysisResult.price_stats?.avg_range}`} 
                      desc="Typical high-to-low spread per candle." 
                    />
                    <StatCard 
                      label="Candle Body/Range" 
                      value={analysisResult.price_stats?.body_to_range_ratio} 
                      desc="Ratio of real body to range (>0.6 implies strong conviction)."
                      badge={analysisResult.price_stats?.body_to_range_ratio > 0.6 ? "Strong bodies" : "High wicks"}
                      badgeColor={analysisResult.price_stats?.body_to_range_ratio > 0.6 ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"}
                    />
                    <StatCard label="Highest Candle High" value={`₹${analysisResult.price_stats?.high_max}`} color="text-emerald-400" />
                    <StatCard label="Lowest Candle Low" value={`₹${analysisResult.price_stats?.low_min}`} color="text-rose-450" />
                    <StatCard label="Average Upper Wick" value={`₹${analysisResult.price_stats?.avg_upper_wick}`} desc="Average length of candle upper shadow." />
                    <StatCard label="Average Lower Wick" value={`₹${analysisResult.price_stats?.avg_lower_wick}`} desc="Average length of candle lower shadow." />
                  </div>

                  {/* Candlestick Patterns */}
                  <div className="glass-panel p-5 rounded-xl border-slate-800/60 shadow-lg space-y-4">
                    <div className="border-b border-slate-800 pb-3">
                      <h4 className="text-xs font-bold text-slate-250 uppercase flex items-center gap-1.5">
                        <AlertTriangle size={12} className="text-blue-450" />
                        Detected Candlestick Patterns
                      </h4>
                      <p className="text-[10px] text-slate-500 mt-0.5">Absolute occurrence counts and frequencies inside the target dataset.</p>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                      <PatternBadge name="Doji" count={analysisResult.patterns?.doji_count} pct={analysisResult.patterns?.doji_pct} />
                      <PatternBadge name="Hammer" count={analysisResult.patterns?.hammer_count} type="bullish" />
                      <PatternBadge name="Shooting Star" count={analysisResult.patterns?.shooting_star_count} type="bearish" />
                      <PatternBadge name="Bullish Engulfing" count={analysisResult.patterns?.bullish_engulfing_count} type="bullish" />
                      <PatternBadge name="Bearish Engulfing" count={analysisResult.patterns?.bearish_engulfing_count} type="bearish" />
                    </div>
                  </div>
                </div>
              )}

              {/* ─── TAB 2: RETURNS & RISK STUDIO ─── */}
              {activeTab === "returns" && (
                <div className="space-y-6">
                  {/* returns stats row */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <StatCard label="Mean Return per bar" value={analysisResult.returns?.mean_return_pct} suffix="%" />
                    <StatCard label="Volatility per bar" value={analysisResult.returns?.std_return_pct} suffix="%" />
                    <StatCard label="Sharpe (Approx)" value={analysisResult.returns?.sharpe_approx} badge="Annualized" badgeColor="bg-slate-800 text-slate-300" />
                    <StatCard 
                      label="Normal Distribution?" 
                      value={analysisResult.returns?.is_normal ? "Passed" : "Failed"} 
                      color={analysisResult.returns?.is_normal ? "text-emerald-450" : "text-amber-450"} 
                      desc="Jarque-Bera normalcy statistical hypothesis test." 
                    />
                    <StatCard label="Annualized Return" value={analysisResult.returns?.annualized_return_pct ?? "—"} suffix="%" />
                    <StatCard label="Annualized Volatility" value={analysisResult.returns?.annualized_vol_pct} suffix="%" />
                    <StatCard 
                      label="Skewness" 
                      value={analysisResult.returns?.skewness} 
                      color={analysisResult.returns?.skewness < -0.5 ? "text-rose-450" : "text-slate-100"} 
                      desc="Symmetry of returns. Negative values imply downside tails."
                    />
                    <StatCard label="Kurtosis" value={analysisResult.returns?.kurtosis} desc="Fat tails measurement. Values >3 are leptokurtic." />
                  </div>

                  {/* Histogram and Tail Risk row */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Returns Dist EChart */}
                    <div className="glass-panel p-5 rounded-xl border-slate-800/60 shadow-lg md:col-span-2">
                      <h4 className="text-xs font-bold text-slate-250 uppercase mb-4 border-b border-slate-800 pb-3 flex items-center gap-1.5">
                        <BarChart3 size={12} className="text-blue-400" />
                        Returns Distribution Frequency
                      </h4>
                      <div className="h-56">
                        <ReactECharts option={returnsDistChartOpt} style={{ height: "100%" }} />
                      </div>
                    </div>

                    {/* Tail Risk Card */}
                    <div className="glass-panel p-5 rounded-xl border-rose-900/20 bg-rose-955/5 shadow-lg flex flex-col justify-between">
                      <div className="space-y-4">
                        <div className="border-b border-rose-900/30 pb-3">
                          <h4 className="text-xs font-bold text-rose-400 uppercase flex items-center gap-1.5">
                            <Shield size={12} className="text-rose-400" />
                            Tail Risk Diagnostics
                          </h4>
                          <p className="text-[10px] text-slate-500 mt-0.5">Loss potential in extreme adverse statistical environments.</p>
                        </div>
                        <div className="space-y-3">
                          <div>
                            <span className="text-[9px] uppercase font-bold text-slate-500 block mb-1">Value-at-Risk (VaR 95%)</span>
                            <span className="font-mono text-lg font-bold text-rose-400">-{Math.abs(analysisResult.returns?.var_95_pct)}%</span>
                            <p className="text-[9px] text-slate-500 mt-0.5">With 95% confidence, loss will not exceed this value per bar.</p>
                          </div>
                          <div>
                            <span className="text-[9px] uppercase font-bold text-slate-500 block mb-1">Conditional VaR (CVaR 95%)</span>
                            <span className="font-mono text-lg font-bold text-rose-400">-{Math.abs(analysisResult.returns?.cvar_95_pct)}%</span>
                            <p className="text-[9px] text-slate-500 mt-0.5">Average loss in the worst 5% of all occurrences.</p>
                          </div>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3 border-t border-rose-900/20 pt-4 mt-4 text-xs font-mono">
                        <div>
                          <span className="text-[9px] uppercase text-slate-550 block">Max Gain Bar</span>
                          <span className="text-emerald-450 font-bold">+{analysisResult.returns?.max_single_gain_pct}%</span>
                        </div>
                        <div>
                          <span className="text-[9px] uppercase text-slate-550 block">Max Loss Bar</span>
                          <span className="text-rose-455 font-bold">-{Math.abs(analysisResult.returns?.max_single_loss_pct)}%</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Drawdown Curve & Metrics */}
                  <div className="glass-panel p-5 rounded-xl border-slate-800/60 shadow-lg">
                    <div className="flex flex-wrap items-center justify-between border-b border-slate-800 pb-3 mb-5 gap-3">
                      <div>
                        <h4 className="text-xs font-bold text-slate-250 uppercase flex items-center gap-1.5">
                          <ArrowDownRight size={12} className="text-rose-450" />
                          Peak-to-Trough Drawdown
                        </h4>
                        <p className="text-[10px] text-slate-500 mt-0.5">Historical equity erosion depth curve.</p>
                      </div>
                      <div className="flex items-center gap-6 text-xs font-mono">
                        <div>
                          <span className="text-[9px] uppercase text-slate-500 block">Max Drawdown</span>
                          <span className="text-rose-455 font-bold">{analysisResult.drawdown?.max_drawdown_pct}%</span>
                        </div>
                        <div>
                          <span className="text-[9px] uppercase text-slate-500 block">Time Underwater</span>
                          <span className="text-slate-300 font-bold">{analysisResult.drawdown?.underwater_pct}%</span>
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                      <div className="md:col-span-3 h-56">
                        <ReactECharts option={drawdownChartOpt} style={{ height: "100%" }} />
                      </div>
                      <div className="space-y-4 justify-center flex flex-col border-t md:border-t-0 md:border-l border-slate-800/80 pt-4 md:pt-0 md:pl-6">
                        <div>
                          <span className="text-[9px] uppercase font-bold text-slate-500 block">Max Drawdown Date</span>
                          <span className="font-mono text-xs text-slate-300 font-semibold">{analysisResult.drawdown?.max_dd_date?.slice(0, 10) || "—"}</span>
                        </div>
                        <div>
                          <span className="text-[9px] uppercase font-bold text-slate-500 block">Avg DD Recovery Duration</span>
                          <span className="font-mono text-xs text-slate-300 font-semibold">{analysisResult.drawdown?.avg_drawdown_duration_bars} bars</span>
                        </div>
                        <div>
                          <span className="text-[9px] uppercase font-bold text-slate-500 block">Max DD Recovery Duration</span>
                          <span className="font-mono text-xs text-slate-300 font-semibold">{analysisResult.drawdown?.max_drawdown_duration_bars} bars</span>
                        </div>
                        <div>
                          <span className="text-[9px] uppercase font-bold text-slate-500 block">Current Drawdown</span>
                          <span className={`font-mono text-xs font-bold ${analysisResult.drawdown?.current_drawdown_pct < -2 ? "text-rose-450" : "text-slate-300"}`}>
                            {analysisResult.drawdown?.current_drawdown_pct}%
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ─── TAB 3: VOLATILITY & REGIMES ─── */}
              {activeTab === "volatility" && (
                <div className="space-y-6">
                  {/* Volatility stats */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <StatCard label="Realized Volatility" value={analysisResult.volatility?.realized_vol_annual_pct} suffix="%" desc="Annualized returns dispersion deviation." />
                    <StatCard label="EWMA Volatility (GARCH approx)" value={analysisResult.volatility?.ewma_vol_annual_pct} suffix="%" desc="Exponentially Weighted Moving Average volatility." />
                    <StatCard label="Volatility of Volatility" value={analysisResult.volatility?.vol_of_vol} desc="Standard deviation of the rolling volatility series." />
                    <StatCard 
                      label="Current Vol Regime" 
                      value={analysisResult.volatility?.current_vol_regime} 
                      color={
                        analysisResult.volatility?.current_vol_regime === "HIGH" ? "text-rose-450" :
                        analysisResult.volatility?.current_vol_regime === "LOW" ? "text-emerald-450" : "text-amber-450"
                      }
                      desc="Comparing current 20-period volatility to history."
                    />
                    <StatCard label="Current 20-bar Vol" value={analysisResult.volatility?.current_vol_pct} suffix="%" />
                    <StatCard label="Median Volatility" value={analysisResult.volatility?.vol_median_pct} suffix="%" />
                    <StatCard label="Maximum Volatility" value={analysisResult.volatility?.vol_max_pct} suffix="%" color="text-rose-450" />
                    <StatCard label="Minimum Volatility" value={analysisResult.volatility?.vol_min_pct} suffix="%" color="text-emerald-450" />
                  </div>

                  {/* Vol Chart and Regimes Row */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Vol Curve */}
                    <div className="glass-panel p-5 rounded-xl border-slate-800/60 shadow-lg md:col-span-2 space-y-4">
                      <h4 className="text-xs font-bold text-slate-250 uppercase border-b border-slate-800 pb-3 flex items-center gap-1.5">
                        <Zap size={12} className="text-amber-450" />
                        Rolling 20-Period Volatility
                      </h4>
                      <div className="h-56">
                        <ReactECharts option={volChartOpt} style={{ height: "100%" }} />
                      </div>
                    </div>

                    {/* Regimes Doughnut */}
                    <div className="glass-panel p-5 rounded-xl border-slate-800/60 shadow-lg flex flex-col justify-between">
                      <h4 className="text-xs font-bold text-slate-250 uppercase border-b border-slate-800 pb-3 flex items-center gap-1.5">
                        <PieChart size={12} className="text-blue-400" />
                        Market Regime Allocation
                      </h4>
                      <div className="h-40 flex items-center justify-center relative">
                        <ReactECharts option={regimeChartOpt} style={{ height: "100%", width: "100%" }} />
                      </div>
                      <div className="border-t border-slate-800/80 pt-3 text-[10px] text-slate-500 leading-normal flex items-center gap-1.5">
                        <Info size={11} className="text-slate-400 flex-shrink-0" />
                        Hover segments to analyze specific distribution allocations.
                      </div>
                    </div>
                  </div>

                  {/* Regime breakdown rows */}
                  <div className="glass-panel p-5 rounded-xl border-slate-800/60 shadow-lg space-y-4">
                    <h4 className="text-xs font-bold text-slate-250 uppercase border-b border-slate-800 pb-3 flex items-center gap-1.5">
                      <Layers size={12} className="text-blue-400" />
                      Regime Characteristic Explanations
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-4">
                      <RegimeProgress 
                        name="TRENDING_BULLISH" 
                        pct={analysisResult.regimes?.TRENDING_BULLISH || 0} 
                        color="#10b981" 
                        desc="Consistent upward drift with clean positive candles." 
                      />
                      <RegimeProgress 
                        name="TRENDING_BEARISH" 
                        pct={analysisResult.regimes?.TRENDING_BEARISH || 0} 
                        color="#f43f5e" 
                        desc="Consistent downward drift with clean negative candles." 
                      />
                      <RegimeProgress 
                        name="VOLATILE_RANGING" 
                        pct={analysisResult.regimes?.VOLATILE_RANGING || 0} 
                        color="#f59e0b" 
                        desc="Wide high-to-low sideways whipsaws, challenging for stops." 
                      />
                      <RegimeProgress 
                        name="QUIET_RANGING" 
                        pct={analysisResult.regimes?.QUIET_RANGING || 0} 
                        color="#64748b" 
                        desc="Low volume, sideways compression with short candles." 
                      />
                      <RegimeProgress 
                        name="GAP_DAY" 
                        pct={analysisResult.regimes?.GAP_DAY || 0} 
                        color="#a855f7" 
                        desc="Sudden price steps/disconnects (e.g. overnight gaps)." 
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* ─── TAB 4: TREND & LEVELS ─── */}
              {activeTab === "trend" && (
                <div className="space-y-6">
                  {/* Trend diagnostic stats */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <StatCard 
                      label="Trend Direction" 
                      value={analysisResult.trend?.trend_direction} 
                      color={
                        analysisResult.trend?.trend_direction === "BULLISH" ? "text-emerald-450" :
                        analysisResult.trend?.trend_direction === "BEARISH" ? "text-rose-455" : "text-slate-450"
                      }
                      badge={analysisResult.trend?.is_trending ? "Trending" : "Ranging"}
                      badgeColor={analysisResult.trend?.is_trending ? "bg-emerald-500/10 text-emerald-450" : "bg-slate-800 text-slate-400"}
                    />
                    <StatCard 
                      label="Linear R-Squared" 
                      value={analysisResult.trend?.r_squared} 
                      desc="Goodness of linear drift fit. (>0.3 is significant)." 
                    />
                    <StatCard label="Linear Slope Coefficient" value={analysisResult.trend?.linear_slope} desc="Expected nominal rate of change per candle." />
                    <StatCard 
                      label="ADX Proxy Strength" 
                      value={analysisResult.trend?.adx_proxy} 
                      desc="Directional movement index proxy. (>25 is strong trend)."
                      badge={analysisResult.trend?.strong_trend ? "Strong ADX" : "Weak ADX"}
                      badgeColor={analysisResult.trend?.strong_trend ? "bg-emerald-500/10 text-emerald-450" : "bg-slate-800 text-slate-400"}
                    />
                    <StatCard label="EMA 20" value={`₹${analysisResult.trend?.ema20}`} />
                    <StatCard label="EMA 50" value={`₹${analysisResult.trend?.ema50}`} />
                    <StatCard 
                      label="Close vs. EMA 20" 
                      value={analysisResult.trend?.price_vs_ema20_pct} 
                      suffix="%" 
                      color={analysisResult.trend?.price_vs_ema20_pct >= 0 ? "text-emerald-450" : "text-rose-455"} 
                    />
                    <StatCard 
                      label="Close vs. EMA 50" 
                      value={analysisResult.trend?.price_vs_ema50_pct} 
                      suffix="%" 
                      color={analysisResult.trend?.price_vs_ema50_pct >= 0 ? "text-emerald-450" : "text-rose-455"} 
                    />
                  </div>

                  {/* S&R Pivots Card */}
                  <div className="glass-panel p-5 rounded-xl border-slate-800/60 shadow-lg">
                    <div className="border-b border-slate-800 pb-3 mb-4 flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <h4 className="text-xs font-bold text-slate-250 uppercase flex items-center gap-1.5">
                          <Layers size={12} className="text-blue-400" />
                          Support & Resistance Levels (Pivots)
                        </h4>
                        <p className="text-[10px] text-slate-500 mt-0.5">Clustered local extrema pivot zones indicating target boundaries.</p>
                      </div>
                      <div className="flex gap-4 text-xs font-mono">
                        <div>
                          <span className="text-[9px] uppercase text-slate-50 block">Rolling High</span>
                          <span className="text-slate-350 font-bold">₹{analysisResult.levels?.rolling_high}</span>
                        </div>
                        <div>
                          <span className="text-[9px] uppercase text-slate-50 block">Rolling Low</span>
                          <span className="text-slate-350 font-bold">₹{analysisResult.levels?.rolling_low}</span>
                        </div>
                      </div>
                    </div>

                    {/* Proximity gauge indicator */}
                    {analysisResult.levels?.nearest_support && analysisResult.levels?.nearest_resistance && (
                      <div className="mb-6 bg-slate-950/40 p-4 rounded-xl border border-slate-800/30">
                        <div className="flex justify-between text-[10px] font-mono font-bold text-slate-550 mb-1">
                          <span>Support (₹{analysisResult.levels.nearest_support.price.toFixed(2)})</span>
                          <span>Resistance (₹{analysisResult.levels.nearest_resistance.price.toFixed(2)})</span>
                        </div>
                        {(() => {
                          const sup = analysisResult.levels.nearest_support.price;
                          const res = analysisResult.levels.nearest_resistance.price;
                          const cur = analysisResult.price_stats?.close_mean || (sup + res)/2;
                          const pct = Math.min(Math.max(((cur - sup) / (res - sup)) * 100, 0), 100);
                          return (
                            <div className="relative">
                              <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden flex">
                                <div className="h-full bg-slate-850" style={{ width: `${pct}%` }} />
                                <div className="h-full bg-slate-950 flex-1" />
                              </div>
                              <div 
                                className="absolute -top-1 w-4 h-4 bg-blue-500 border-2 border-slate-950 rounded-full shadow-[0_0_8px_rgba(59,130,246,0.8)] transition-all duration-300"
                                style={{ left: `calc(${pct}% - 8px)` }}
                              />
                            </div>
                          );
                        })()}
                        <div className="flex justify-between text-[9px] text-slate-500 mt-2 font-mono">
                          <span>Dist: {analysisResult.levels.distance_to_support_pct}% below close</span>
                          <span>Dist: {analysisResult.levels.distance_to_resistance_pct}% above close</span>
                        </div>
                      </div>
                    )}

                    {/* Pivots Table */}
                    {analysisResult.levels?.pivots?.length > 0 ? (
                      <div className="overflow-hidden border border-slate-800/50 rounded-lg">
                        <table className="w-full text-left text-xs text-slate-400">
                          <thead>
                            <tr className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-bold">
                              <th className="py-2.5 px-4">Type</th>
                              <th className="py-2.5 px-4">Target Pivot Price</th>
                              <th className="py-2.5 px-4">Detected Cluster Strength</th>
                              <th className="py-2.5 px-4">Distance from current Close</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/50 bg-slate-950/10">
                            {analysisResult.levels.pivots.map((p: any, i: number) => {
                              const curClose = analysisResult.plot_series?.close?.[analysisResult.plot_series.close.length - 1] || p.price;
                              const dist = ((p.price - curClose) / curClose) * 100;
                              return (
                                <tr key={i} className="hover:bg-slate-900/20 transition-colors">
                                  <td className="py-2.5 px-4">
                                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                      p.type === "support" 
                                        ? "bg-emerald-950/40 text-emerald-450 border border-emerald-900/30" 
                                        : "bg-rose-955/20 text-rose-455 border border-rose-900/30"
                                    }`}>
                                      {p.type}
                                    </span>
                                  </td>
                                  <td className="py-2.5 px-4 font-mono font-bold text-slate-200">₹{p.price.toFixed(2)}</td>
                                  <td className="py-2.5 px-4 font-mono text-slate-350">{p.strength} hits</td>
                                  <td className="py-2.5 px-4 font-mono font-bold">
                                    <span className={dist >= 0 ? "text-emerald-450" : "text-rose-455"}>
                                      {dist >= 0 ? "+" : ""}{dist.toFixed(2)}%
                                    </span>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="text-center text-xs text-slate-500 py-6">
                        No support or resistance pivots detected in current window parameters.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* ─── TAB 5: SEASONALITY & VOLUME ─── */}
              {activeTab === "seasonality" && (
                <div className="space-y-6">
                  {/* Volume row */}
                  {analysisResult.volume?.available ? (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                      <StatCard label="Average Bar Volume" value={analysisResult.volume?.avg_volume?.toLocaleString()} />
                      <StatCard label="Relative Volume Ratio" value={`${analysisResult.volume?.relative_volume}x`} desc="Current volume vs 20-bar average." />
                      <StatCard 
                        label="Volume-Price Correlation" 
                        value={analysisResult.volume?.volume_price_corr} 
                        desc="Correlation between returns absolute magnitude and volume." 
                      />
                      <StatCard 
                        label="Volume Trend" 
                        value={analysisResult.volume?.volume_trend} 
                        color={analysisResult.volume?.volume_trend === "RISING" ? "text-emerald-450" : "text-rose-455"} 
                      />
                    </div>
                  ) : (
                    <div className="glass-panel p-5 rounded-xl border-slate-800/40 text-center text-xs text-slate-500">
                      No Volume metrics available for current instrument catalog schema.
                    </div>
                  )}

                  {/* Seasonality Chart and Hourly Statistics */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Seasonality DOW Chart */}
                    {analysisResult.seasonality?.dow?.dow_data ? (
                      <div className="glass-panel p-5 rounded-xl border-slate-800/60 shadow-lg md:col-span-2 space-y-4">
                        <h4 className="text-xs font-bold text-slate-250 uppercase border-b border-slate-800 pb-3 flex items-center gap-1.5">
                          <Calendar size={12} className="text-blue-400" />
                          Seasonality: Day of Week returns
                        </h4>
                        <div className="h-56">
                          <ReactECharts option={seasonalityChartOpt} style={{ height: "100%" }} />
                        </div>
                      </div>
                    ) : (
                      <div className="glass-panel p-5 rounded-xl border-slate-800/40 text-center text-xs text-slate-500 md:col-span-2">
                        No day-of-week seasonality dataset parsed.
                      </div>
                    )}

                    {/* Hourly Statistics Cards */}
                    <div className="glass-panel p-5 rounded-xl border-slate-800/60 shadow-lg flex flex-col justify-between">
                      <div className="space-y-4">
                        <div className="border-b border-slate-800 pb-3">
                          <h4 className="text-xs font-bold text-slate-250 uppercase flex items-center gap-1.5">
                            <Clock size={12} className="text-blue-400" />
                            Hourly Windows
                          </h4>
                          <p className="text-[10px] text-slate-500 mt-0.5">Top performing intraday execution schedules.</p>
                        </div>
                        
                        {analysisResult.seasonality?.hourly ? (
                          <div className="space-y-4">
                            <div>
                              <span className="text-[9px] uppercase font-bold text-slate-500 block mb-1">Golden Hour (Best)</span>
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-base font-bold text-emerald-450">
                                  {analysisResult.seasonality.hourly.best_hour}:00
                                </span>
                                <span className="text-xs text-emerald-400 font-mono">
                                  ({analysisResult.seasonality.hourly.best_hour_return_pct}%)
                                </span>
                              </div>
                              <p className="text-[9px] text-slate-500 mt-0.5">Best window to execute long-biased parameters.</p>
                            </div>
                            <div>
                              <span className="text-[9px] uppercase font-bold text-slate-500 block mb-1">Risk Window (Worst)</span>
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-base font-bold text-rose-455">
                                  {analysisResult.seasonality.hourly.worst_hour}:00
                                </span>
                                <span className="text-xs text-rose-455 font-mono">
                                  ({analysisResult.seasonality.hourly.worst_hour_return_pct}%)
                                </span>
                              </div>
                              <p className="text-[9px] text-slate-500 mt-0.5">Avoid active long scaling during this timezone.</p>
                            </div>
                          </div>
                        ) : (
                          <div className="text-xs text-slate-500 italic py-6">
                            Intraday hourly parameters unavailable (asset interval is daily+).
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ─── TAB 6: VERDICT & TUNING ─── */}
              {activeTab === "verdict" && (
                <div className="space-y-6">
                  {/* Verdict header box */}
                  <div className="glass-panel p-5 rounded-xl border-emerald-900/30 bg-emerald-955/5 shadow-lg space-y-4">
                    <div className="flex items-center gap-2 border-b border-emerald-900/20 pb-3">
                      <Shield size={14} className="text-emerald-400" />
                      <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wide">Lab Expert Verdict recommendation</h4>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed font-medium">
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
                            Statistical profiling recommends deploying a{" "}
                            <span className="font-bold text-emerald-400 uppercase tracking-wide underline">{rec}</span> strategy structure (Score {score}/100) 
                            for this instrument. This is primarily influenced by the current{" "}
                            <span className={`font-bold ${trend === "BULLISH" ? "text-emerald-400" : trend === "BEARISH" ? "text-rose-455" : "text-slate-400"}`}>{trend}</span> macro 
                            trend drift and <span className={`font-bold ${vol === "HIGH" ? "text-rose-450" : vol === "LOW" ? "text-emerald-450" : "text-amber-450"}`}>{vol}</span> volatility environment. 
                            {skew < -0.5 && " Heavy negative skew is detected; you should enforce strict stop-loss caps."}
                            {skew > 0.5 && " Returns possess positive skew; trail profit targets for breakout continuation."}
                            {ac1 > 0.1 && " Momentum persistence is evident (Lag-1 >0.1); prioritize trend-riding indicators."}
                            {ac1 < -0.1 && " Mean-reversion tendency detected (Lag-1 <-0.1); favor fading oscillators."}
                            {posPct > 55 && " Positive bar bias exists (>55%); long scaling holds higher statistical edge."}
                            {posPct < 45 && " Negative bar bias exists (<45%); avoid excessive long-only strategies."}
                          </span>
                        );
                      })()}
                    </p>
                  </div>

                  {/* Strategy Suite Scores */}
                  <div className="glass-panel p-5 rounded-xl border-slate-800/60 shadow-lg space-y-4">
                    <div className="border-b border-slate-800 pb-3">
                      <h4 className="text-xs font-bold text-slate-250 uppercase flex items-center gap-1.5">
                        <Activity size={12} className="text-blue-400" />
                        Strategy Suite Suitability scores
                      </h4>
                      <p className="text-[10px] text-slate-500 mt-0.5">Comparative scoring (0-100) of strategy categories based on statistical metrics.</p>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {Object.entries(analysisResult.suitability?.scores || {}).map(([name, score]: [string, any]) => (
                        <SuitabilityProgress 
                          key={name} 
                          name={name} 
                          score={score} 
                          isRecommended={analysisResult.suitability?.recommended === name} 
                        />
                      ))}
                    </div>
                  </div>

                  {/* Tuning Parameters Guidance */}
                  <div className="glass-panel p-5 rounded-xl border-slate-800/60 shadow-lg space-y-4">
                    <div className="border-b border-slate-800 pb-3">
                      <h4 className="text-xs font-bold text-slate-250 uppercase flex items-center gap-1.5">
                        <Zap size={12} className="text-amber-450" />
                        Tuning Parameter reference & metrics
                      </h4>
                      <p className="text-[10px] text-slate-500 mt-0.5">Calculated limits and statistical guidelines to manually optimize your strategies.</p>
                    </div>
                    <div className="overflow-x-auto border border-slate-800/60 rounded-lg">
                      <table className="w-full text-left text-xs text-slate-400">
                        <thead>
                          <tr className="bg-slate-950/80 border-b border-slate-800 font-bold text-slate-400">
                            <th className="py-2.5 px-4 w-48">Parameter</th>
                            <th className="py-2.5 px-4 w-32">Metric Value</th>
                            <th className="py-2.5 px-4">Tuning Guidance</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/50 bg-slate-950/10 font-medium">
                          <tr>
                            <td className="py-2.5 px-4 font-mono font-bold text-slate-300">avg_range</td>
                            <td className="py-2.5 px-4 font-mono">₹{analysisResult.price_stats?.avg_range}</td>
                            <td className="py-2.5 px-4 leading-normal text-slate-350">Scale stops and targets here. Enforce ATR filters ~1.5x to 2.5x this value.</td>
                          </tr>
                          <tr>
                            <td className="py-2.5 px-4 font-mono font-bold text-slate-300">body_to_range</td>
                            <td className="py-2.5 px-4 font-mono">{analysisResult.price_stats?.body_to_range_ratio}</td>
                            <td className="py-2.5 px-4 leading-normal text-slate-350">
                              {analysisResult.price_stats?.body_to_range_ratio > 0.6 
                                ? "High directional candles: ride standard trend lines directly." 
                                : "High wick values: expect fake-outs, use wider confirmation filters."}
                            </td>
                          </tr>
                          <tr>
                            <td className="py-2.5 px-4 font-mono font-bold text-slate-300">annualized_vol</td>
                            <td className="py-2.5 px-4 font-mono">{analysisResult.returns?.annualized_vol_pct}%</td>
                            <td className="py-2.5 px-4 leading-normal text-slate-350">
                              {analysisResult.returns?.annualized_vol_pct > 35 
                                ? "Elevated vol: reduce position sizing scaling weights, widen targets." 
                                : "Compressed vol: tighter stops, prepare for compression breakout."}
                            </td>
                          </tr>
                          <tr>
                            <td className="py-2.5 px-4 font-mono font-bold text-slate-300">autocorr_lag1</td>
                            <td className="py-2.5 px-4 font-mono">
                              {analysisResult.autocorrelation?.lags?.[0]?.autocorr ?? "—"}
                            </td>
                            <td className="py-2.5 px-4 leading-normal text-slate-350">
                              {analysisResult.autocorrelation?.lags?.[0]?.autocorr > 0.1 
                                ? "Positive autocorrelation: ride the trend. Prioritize moving averages." 
                                : "Negative autocorrelation: mean reverting. Prioritize oscillators."}
                            </td>
                          </tr>
                          <tr>
                            <td className="py-2.5 px-4 font-mono font-bold text-slate-300">adx_proxy</td>
                            <td className="py-2.5 px-4 font-mono">{analysisResult.trend?.adx_proxy}</td>
                            <td className="py-2.5 px-4 leading-normal text-slate-350">
                              {analysisResult.trend?.adx_proxy > 25 
                                ? "Strong trend. Wide stops are ideal." 
                                : "Low trend. Tighten stops or adopt swing setups."}
                            </td>
                          </tr>
                          <tr>
                            <td className="py-2.5 px-4 font-mono font-bold text-slate-300">nearest_support</td>
                            <td className="py-2.5 px-4 font-mono text-emerald-450">₹{analysisResult.levels?.nearest_support?.price || "—"}</td>
                            <td className="py-2.5 px-4 leading-normal text-slate-350">Use as stop-loss buffer zone for long positions.</td>
                          </tr>
                          <tr>
                            <td className="py-2.5 px-4 font-mono font-bold text-slate-300">nearest_resistance</td>
                            <td className="py-2.5 px-4 font-mono text-rose-455">₹{analysisResult.levels?.nearest_resistance?.price || "—"}</td>
                            <td className="py-2.5 px-4 leading-normal text-slate-350">Use as profit target target zone for long configurations.</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Raw JSON Tuning Config */}
                  <div className="glass-panel rounded-xl overflow-hidden border-slate-800/60 shadow-lg">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-950/40">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <Database size={12} className="text-slate-400" />
                        Tuning configuration JSON
                      </span>
                      <button
                        onClick={handleCopyJSON}
                        className="text-[10px] bg-slate-950 hover:bg-slate-900 border border-slate-850 px-3 py-1 rounded text-slate-300 hover:text-slate-100 flex items-center gap-1.5 transition-colors font-bold shadow-md cursor-pointer"
                      >
                        {copied ? <Check size={11} className="text-emerald-400 animate-scale" /> : <Copy size={11} />}
                        {copied ? "Copied" : "Copy JSON"}
                      </button>
                    </div>
                    <pre className="p-4 overflow-x-auto text-[10px] font-mono text-slate-400 bg-slate-950/80 leading-relaxed max-h-56">
                      {JSON.stringify(
                        {
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
                        },
                        null,
                        2
                      )}
                    </pre>
                  </div>
                </div>
              )}

            </div>
          </div>
        ) : (
          <div className="flex-1 min-h-[400px] flex flex-col items-center justify-center text-center p-8 bg-slate-900/15 border border-slate-800/40 rounded-2xl glass-panel shadow-inner">
            <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-6 mb-4 shadow-lg text-blue-500/20">
              <BarChart2 size={42} className="mx-auto text-blue-400/80 animate-pulse" />
            </div>
            <h4 className="font-bold text-slate-300 text-sm">Target Dataset Diagnostics Required</h4>
            <p className="text-xs text-slate-500 mt-1 max-w-sm leading-normal">
              Select an instrument dataset CSV and run deep statistical diagnostics to compute suitability profiling, tail risk, and regimes.
            </p>
          </div>
        )}

      </div>
    </div>
  );
}
