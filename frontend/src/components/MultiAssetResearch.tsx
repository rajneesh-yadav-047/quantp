"use client";

import React, { useState, useMemo, useCallback, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import {
  Network, Search, TrendingUp, BarChart2, Activity, Loader2, Play,
  ChevronDown, ChevronUp, ArrowRightLeft, Zap, Layers, AlignJustify,
  AlertTriangle, CheckCircle2, GitBranch, Shuffle, RefreshCw
} from "lucide-react";
import { api } from "../lib/api-client";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

/* ─── Types ─── */
interface Props {
  datasets: any[];
  theme: "dark" | "light";
  setNotif: (n: { type: "success" | "error" | "info"; msg: string } | null) => void;
  backendOnline?: boolean;
  dlSymbol?: string;
  setDlSymbol?: (v: string) => void;
  dlInterval?: string;
  setDlInterval?: (v: string) => void;
  dlFromDate?: string;
  setDlFromDate?: (v: string) => void;
  dlToDate?: string;
  setDlToDate?: (v: string) => void;
  pendingMultiAsset?: any;
  setPendingMultiAsset?: (v: any) => void;
  multiAssetRetrySignal?: number;
  setIsTotpModalOpen?: (v: boolean) => void;
  setPendingAction?: (v: any) => void;
  setDownloadQueue?: (symbols: string[]) => void;
}

type AnalysisTab =
  | "correlation"
  | "pairs"
  | "cointegration"
  | "spread"
  | "leadlag"
  | "breadth"
  | "ranking";

const TABS: { id: AnalysisTab; label: string; icon: React.ElementType }[] = [
  { id: "correlation", label: "Correlation Matrix", icon: BarChart2 },
  { id: "pairs", label: "Pair Discovery", icon: GitBranch },
  { id: "cointegration", label: "Cointegration", icon: ArrowRightLeft },
  { id: "spread", label: "Spread & Z-Score", icon: Activity },
  { id: "leadlag", label: "Lead-Lag", icon: TrendingUp },
  { id: "breadth", label: "Sector Breadth", icon: Layers },
  { id: "ranking", label: "Factor Ranking", icon: AlignJustify },
];

const PRESET_GROUPS: Record<string, string[]> = {
  BANKING: ["SBIN", "HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK"],
  IT: ["INFY", "TCS", "WIPRO", "TECHM", "HCLTECH"],
  PHARMA: ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "BIOCON"],
  AUTO: ["TATAMOTORS", "MARUTI", "M&M", "BAJAJ-AUTO", "HEROMOTOCO"],
  FMCG: ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR"],
  METALS: ["TATASTEEL", "HINDALCO", "JSWSTEEL", "VEDL"],
  NIFTY_TOP: ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"],
};

/* ─── Symbol Autocomplete Input ─── */
const SymbolAutocomplete = ({
  value,
  onChange,
  onSelect,
  placeholder = "Search symbol…",
  disabled = false,
}: {
  value: string;
  onChange: (v: string) => void;
  onSelect?: (bare: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) => {
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [show, setShow] = useState(false);
  const timerRef = useRef<any>(null);

  useEffect(() => {
    if (!value || value.length < 2) { setSuggestions([]); return; }
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      api.get(`/data/symbols/search?q=${encodeURIComponent(value)}`)
        .then(r => { if (r.ok && r.data) setSuggestions(r.data); else setSuggestions([]); })
        .catch(() => setSuggestions([]));
    }, 250);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [value]);

  return (
    <div className="relative">
      <input
        value={value}
        onChange={(e) => { onChange(e.target.value.toUpperCase()); setShow(true); }}
        onFocus={() => setShow(true)}
        onBlur={() => setTimeout(() => setShow(false), 200)}
        placeholder={placeholder}
        disabled={disabled}
        className="t-input w-full rounded-lg px-3 py-2 text-xs font-mono"
      />
      {show && suggestions.length > 0 && (
        <div className="absolute z-50 w-full mt-1 max-h-52 overflow-y-auto rounded shadow-2xl divide-y custom-scrollbar"
          style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
          {suggestions.map((s: any) => {
            const bare = s.bare_symbol || s.symbol;
            return (
              <div
                key={s.token}
                onMouseDown={(e) => {
                  e.preventDefault();
                  onChange(bare);
                  setShow(false);
                  onSelect?.(bare);
                }}
                className="px-3 py-2 text-xs cursor-pointer flex justify-between items-center transition-colors duration-150"
                style={{ borderColor: 'var(--border-color)' }}
                onMouseEnter={e => (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--bg-panel-inner)'}
                onMouseLeave={e => (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'}
              >
                <div className="flex flex-col">
                  <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{bare}</span>
                  <span className="text-[9px] truncate max-w-[160px]" style={{ color: 'var(--text-tertiary)' }}>{s.name}</span>
                </div>
                <span className="text-[9px] font-mono rounded px-1.5 py-0.5" style={{ backgroundColor: 'var(--bg-panel-inner)', border: '1px solid var(--border-color)', color: 'var(--text-tertiary)' }}>{s.token}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

/* ─── Tag Input with Autocomplete ─── */
const TagInput = ({
  value,
  onChange,
}: {
  value: string[];
  onChange: (v: string[]) => void;
}) => {
  const [input, setInput] = useState("");
  const add = (v?: string) => {
    const raw = (v || input).trim().toUpperCase().replace(/\s+/g, "");
    if (raw && !value.includes(raw)) onChange([...value, raw]);
    setInput("");
  };
  return (
    <div className="flex flex-wrap gap-1.5 p-2 rounded-lg border border-slate-700/60 bg-slate-900/40 min-h-[40px]">
      {value.map((sym) => (
        <span
          key={sym}
          className="flex items-center gap-1 bg-blue-600/20 border border-blue-500/30 text-blue-300 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full"
        >
          {sym}
          <button
            onClick={() => onChange(value.filter((s) => s !== sym))}
            className="text-blue-400 hover:text-red-400 transition-colors ml-0.5 leading-none"
          >
            ×
          </button>
        </span>
      ))}
      <div className="flex-1 min-w-[120px]">
        <SymbolAutocomplete
          value={input}
          onChange={setInput}
          onSelect={(bare) => add(bare)}
          placeholder="Add symbol…"
        />
      </div>
    </div>
  );
};

const MetricBadge = ({ label, value, color = "text-slate-200" }: { label: string; value: string | number; color?: string }) => (
  <div className="flex flex-col gap-0.5">
    <span className="text-[9px] text-slate-500 uppercase tracking-wider font-bold">{label}</span>
    <span className={`font-mono text-sm font-bold ${color}`}>{value}</span>
  </div>
);

/* ─── Main Component ─── */
export default function MultiAssetResearch({
  datasets,
  theme,
  setNotif,
  backendOnline = false,
  dlSymbol,
  setDlSymbol,
  dlInterval,
  setDlInterval,
  dlFromDate,
  setDlFromDate,
  dlToDate,
  setDlToDate,
  pendingMultiAsset,
  setPendingMultiAsset,
  multiAssetRetrySignal = 0,
  setIsTotpModalOpen,
  setPendingAction,
  setDownloadQueue,
}: Props) {
  const [activeTab, setActiveTab] = useState<AnalysisTab>("correlation");
  const [symbols, setSymbols] = useState<string[]>(PRESET_GROUPS.BANKING);
  const [interval, setInterval] = useState("ONE_DAY");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  // Coverage banner states
  const [coverageMissing, setCoverageMissing] = useState<string[]>([]);
  const [coverageAvailable, setCoverageAvailable] = useState<string[]>([]);

  // Pair/cointegration/spread specific
  const [sym1, setSym1] = useState("SBIN");
  const [sym2, setSym2] = useState("HDFCBANK");
  const [hedgeRatio, setHedgeRatio] = useState(1.0);
  const [factor, setFactor] = useState("momentum");

  const isDark = theme === "dark";
  const labelColor = isDark ? "#64748b" : "#475569";
  const gridLineColor = isDark ? "#0f172a" : "#f1f5f9";
  const borderLineColor = isDark ? "#1e293b" : "#cbd5e1";
  const tooltipBgColor = isDark ? "#0b1222" : "#ffffff";
  const tooltipBorderColor = isDark ? "#1e293b" : "#cbd5e1";
  const tooltipTextColor = isDark ? "#e2e8f0" : "#0f172a";

  /* Check if dataset exists for a symbol+interval */
  const checkExists = useCallback((sym: string, intv: string) => {
    const base = sym.toUpperCase().trim().replace(/\s+/g, "");
    return datasets.some((d: any) => {
      const dsSym = (d.symbol || "").toUpperCase().trim();
      const dsBase = dsSym.includes(":") ? dsSym.split(":")[1].replace(/-EQ$|-BE$/i, "") : dsSym.replace(/-EQ$|-BE$/i, "");
      return (dsBase === base || dsSym === base) && (d.interval || "").toUpperCase() === intv.toUpperCase();
    });
  }, [datasets]);

  const getMissing = useCallback((syms: string[], intv: string) => {
    return syms.filter(s => !checkExists(s, intv));
  }, [checkExists]);

  /* Auto-retry after download */
  const retryRef = useRef<{ symbols: string[]; interval: string; activeTab: string; params: any } | null>(null);
  useEffect(() => {
    if (!multiAssetRetrySignal || !retryRef.current) return;
    const r = retryRef.current;
    const stillMissing = getMissing(r.symbols, r.interval);
    if (stillMissing.length === 0) {
      setNotif({ type: "info", msg: "All datasets downloaded. Re-running analysis…" });
      runWithParams(r.activeTab, r.symbols, r.interval, r.params);
    }
    retryRef.current = null;
  }, [multiAssetRetrySignal]);

  const runWithParams = async (
    tab: AnalysisTab,
    syms: string[],
    intv: string,
    extraParams?: any
  ) => {
    setLoading(true);
    setResult(null);
    setCoverageMissing([]);
    setCoverageAvailable([]);
    let res: any = null;

    try {
      if (tab === "correlation") {
        res = await api.post("/research/multiasset/correlation", {
          symbols: syms, interval: intv, window: 60, log_returns: true,
        });
      } else if (tab === "pairs") {
        res = await api.post("/research/multiasset/pair-discovery", {
          symbols: syms, interval: intv, top_n: 15, min_corr: 0.5,
        });
      } else if (tab === "cointegration") {
        res = await api.post("/research/multiasset/cointegration", {
          sym1: extraParams?.sym1 || sym1, sym2: extraParams?.sym2 || sym2, interval: intv,
        });
      } else if (tab === "spread") {
        res = await api.post("/research/multiasset/spread-analysis", {
          sym1: extraParams?.sym1 || sym1, sym2: extraParams?.sym2 || sym2, interval: intv,
          hedge_ratio: extraParams?.hedgeRatio ?? hedgeRatio, zscore_window: 20,
        });
      } else if (tab === "leadlag") {
        res = await api.post("/research/multiasset/lead-lag", {
          symbols: syms, interval: intv, max_lag: 5,
        });
      } else if (tab === "breadth") {
        res = await api.post("/research/multiasset/breadth", {
          symbols: syms, interval: intv, window: 20, log_returns: false,
        });
      } else if (tab === "ranking") {
        res = await api.post("/research/multiasset/ranking", {
          symbols: syms, interval: intv, factor: extraParams?.factor || factor, lookback: 20,
        });
      }

      if (res?.ok && res?.data) {
        setResult(res.data);
        setNotif({ type: "success", msg: `Analysis complete` });
      } else {
        const errMsg = res?.error || "Analysis failed";
        // Fallback: if backend says missing data
        if (errMsg.includes("No data found") || errMsg.includes("not found") || errMsg.includes("datasets not found")) {
          const missing = getMissing(syms, intv);
          const available = (needsPair ? [sym1, sym2] : syms).filter(s => !missing.includes(s));
          if (missing.length > 0) {
            setCoverageMissing(missing);
            setCoverageAvailable(available);
            setNotif({ type: "error", msg: `Missing data for ${missing.join(", ")}. Will auto-download.` });
            const first = missing[0];
            const today = new Date().toISOString().slice(0, 10);
            const past = new Date(); past.setDate(past.getDate() - 60);
            setDlSymbol?.(first);
            setDlInterval?.(intv);
            setDlFromDate?.(past.toISOString().slice(0, 10));
            setDlToDate?.(today);
            setDownloadQueue?.(missing);
            setPendingMultiAsset?.({ symbols: syms, interval: intv, activeTab: tab, params: extraParams });
            setPendingAction?.("DOWNLOAD");
            setIsTotpModalOpen?.(true);
            retryRef.current = { symbols: syms, interval: intv, activeTab: tab, params: extraParams };
            setLoading(false);
            return;
          }
        }
        setNotif({ type: "error", msg: errMsg });
      }
    } catch (e: any) {
      setNotif({ type: "error", msg: e.message || "Unexpected error" });
    } finally {
      setLoading(false);
    }
  };

  const run = () => {
    const syms = needsPair ? [sym1, sym2] : symbols;
    const extraParams = needsPair ? { sym1, sym2, hedgeRatio, factor } : { factor };
    const checkSyms = needsPair ? [sym1, sym2] : symbols;

    const missing = getMissing(checkSyms, interval);
    const available = checkSyms.filter(s => !missing.includes(s));

    setCoverageMissing(missing);
    setCoverageAvailable(available);

    if (missing.length > 0) {
      setDownloadQueue?.(missing);
      const today = new Date().toISOString().slice(0, 10);
      const past = new Date(); past.setDate(past.getDate() - 60);
      setDlSymbol?.(missing[0]);
      setDlInterval?.(interval);
      setDlFromDate?.(past.toISOString().slice(0, 10));
      setDlToDate?.(today);
      setPendingMultiAsset?.({ symbols: syms, interval, activeTab, params: extraParams });
      setPendingAction?.("DOWNLOAD");
      setIsTotpModalOpen?.(true);
      retryRef.current = { symbols: syms, interval, activeTab, params: extraParams };
      setNotif({ type: "error", msg: `Missing data for ${missing.join(", ")}. Enter TOTP to auto-download all.` });
      return;
    }

    runWithParams(activeTab, syms, interval, extraParams);
  };

  /* ─── Chart options ─── */
  const correlationHeatmapOpt = useMemo(() => {
    if (!result?.correlation_matrix) return null;
    const syms = result.symbols || [];
    const matrix = result.correlation_matrix;

    const data: [number, number, number][] = [];
    syms.forEach((s1: string, i: number) => {
      syms.forEach((s2: string, j: number) => {
        const val = matrix[s1]?.[s2] ?? 0;
        data.push([i, j, parseFloat(val.toFixed(3))]);
      });
    });

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        backgroundColor: tooltipBgColor,
        borderColor: tooltipBorderColor,
        textStyle: { color: tooltipTextColor, fontSize: 11 },
        formatter: (p: any) =>
          `${syms[p.data[0]]} / ${syms[p.data[1]]}: <b>${p.data[2]}</b>`,
      },
      grid: { left: 80, right: 20, top: 20, bottom: 80 },
      xAxis: {
        type: "category",
        data: syms,
        axisLabel: { color: labelColor, fontSize: 10, rotate: 45 },
        axisLine: { lineStyle: { color: borderLineColor } },
        splitLine: { show: false },
      },
      yAxis: {
        type: "category",
        data: syms,
        axisLabel: { color: labelColor, fontSize: 10 },
        axisLine: { lineStyle: { color: borderLineColor } },
        splitLine: { show: false },
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 0,
        inRange: {
          color: ["#ef4444", "#f59e0b", "#10b981"],
        },
        textStyle: { color: labelColor, fontSize: 10 },
      },
      series: [
        {
          name: "Correlation",
          type: "heatmap",
          data,
          label: {
            show: syms.length <= 8,
            fontSize: 9,
            color: "#fff",
            formatter: (p: any) => p.data[2].toFixed(2),
          },
          emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.5)" } },
          itemStyle: { borderRadius: 2, borderWidth: 1, borderColor: isDark ? "#0f172a" : "#fff" },
        },
      ],
    };
  }, [result, theme]);

  const spreadChartOpt = useMemo(() => {
    if (!result?.spread_series || !result?.zscore_series) return null;
    const n = result.spread_series.length;
    const xData = Array.from({ length: n }, (_, i) => i + 1);
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: tooltipBgColor,
        borderColor: tooltipBorderColor,
        textStyle: { color: tooltipTextColor, fontSize: 11 },
      },
      grid: [
        { left: 60, right: 15, top: "5%", height: "42%" },
        { left: 60, right: 15, top: "55%", height: "38%" },
      ],
      xAxis: [
        { type: "category", data: xData, axisLabel: { show: false }, axisLine: { lineStyle: { color: borderLineColor } }, gridIndex: 0 },
        { type: "category", data: xData, axisLabel: { color: labelColor, fontSize: 9 }, axisLine: { lineStyle: { color: borderLineColor } }, gridIndex: 1 },
      ],
      yAxis: [
        { scale: true, axisLabel: { color: labelColor, fontSize: 9 }, splitLine: { lineStyle: { color: gridLineColor } }, gridIndex: 0 },
        { scale: true, axisLabel: { color: labelColor, fontSize: 9 }, splitLine: { lineStyle: { color: gridLineColor } }, gridIndex: 1 },
      ],
      series: [
        {
          name: "Spread",
          type: "line",
          data: result.spread_series,
          xAxisIndex: 0,
          yAxisIndex: 0,
          showSymbol: false,
          lineStyle: { color: "#3b82f6", width: 1.5 },
          areaStyle: { color: "rgba(59,130,246,0.08)" },
        },
        {
          name: "Z-Score",
          type: "line",
          data: result.zscore_series,
          xAxisIndex: 1,
          yAxisIndex: 1,
          showSymbol: false,
          lineStyle: { color: "#f59e0b", width: 1.5 },
          markLine: {
            silent: true,
            lineStyle: { color: "#ef4444", type: "dashed", width: 1 },
            data: [{ yAxis: 2 }, { yAxis: -2 }],
          },
        },
      ],
    };
  }, [result, theme]);

  const rankingChartOpt = useMemo(() => {
    if (!result?.rankings) return null;
    const sorted = [...result.rankings].reverse();
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: tooltipBgColor,
        borderColor: tooltipBorderColor,
        textStyle: { color: tooltipTextColor, fontSize: 11 },
      },
      grid: { left: 70, right: 20, top: 15, bottom: 30 },
      xAxis: {
        type: "value",
        axisLabel: { color: labelColor, fontSize: 9 },
        splitLine: { lineStyle: { color: gridLineColor } },
      },
      yAxis: {
        type: "category",
        data: sorted.map((r: any) => r.symbol),
        axisLabel: { color: labelColor, fontSize: 10 },
        axisLine: { lineStyle: { color: borderLineColor } },
      },
      series: [
        {
          type: "bar",
          data: sorted.map((r: any) => ({
            value: r.raw_score,
            itemStyle: {
              color: r.raw_score >= 0 ? "#10b981" : "#ef4444",
              borderRadius: [0, 4, 4, 0],
            },
          })),
          barWidth: "55%",
        },
      ],
    };
  }, [result, theme]);

  const needsPair = activeTab === "cointegration" || activeTab === "spread";
  const needsSymbols = !needsPair;

  return (
    <div className="flex flex-col gap-6">
      {/* ─── Header ─── */}
      <div className="glass-panel p-5 rounded-xl shadow-xl">
        <div className="flex items-center gap-3 mb-4 pb-3 border-b border-slate-800/60">
          <div className="p-2 bg-violet-500/10 border border-violet-500/20 rounded-lg">
            <Network size={18} className="text-violet-400" />
          </div>
          <div>
            <h3 className="font-bold text-slate-100 text-sm">Multi-Asset Research Lab</h3>
            <p className="text-[10px] text-slate-500 mt-0.5">Correlations · Pair Trading · Sector Analysis · Factor Ranking</p>
          </div>
        </div>

        {/* Configuration */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Symbol/Pair input */}
          <div>
            {needsPair ? (
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Symbol 1</label>
                  <SymbolAutocomplete value={sym1} onChange={setSym1} placeholder="e.g. SBIN" />
                </div>
                <div className="flex-1">
                  <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Symbol 2</label>
                  <SymbolAutocomplete value={sym2} onChange={setSym2} placeholder="e.g. HDFCBANK" />
                </div>
                {activeTab === "spread" && (
                  <div className="w-24">
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Hedge Ratio</label>
                    <input
                      type="number"
                      step="0.01"
                      value={hedgeRatio}
                      onChange={(e) => setHedgeRatio(parseFloat(e.target.value))}
                      className="t-input w-full rounded-lg px-3 py-2 text-xs font-mono"
                    />
                  </div>
                )}
              </div>
            ) : (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-[10px] uppercase font-bold text-slate-500">Symbol Universe</label>
                  <div className="flex gap-1">
                    {Object.keys(PRESET_GROUPS).map((g) => (
                      <button
                        key={g}
                        onClick={() => setSymbols(PRESET_GROUPS[g])}
                        className="text-[9px] px-2 py-0.5 rounded font-bold bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200 transition-colors"
                      >
                        {g}
                      </button>
                    ))}
                  </div>
                </div>
                <TagInput value={symbols} onChange={setSymbols} />
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3">
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Interval</label>
                <select
                  value={interval}
                  onChange={(e) => setInterval(e.target.value)}
                  className="t-input w-full rounded-lg px-3 py-2 text-xs"
                >
                  <option value="ONE_DAY">Daily</option>
                  <option value="ONE_WEEK">Weekly</option>
                  <option value="FIVE_MINUTE">5 Min</option>
                  <option value="FIFTEEN_MINUTE">15 Min</option>
                  <option value="ONE_HOUR">1 Hour</option>
                </select>
              </div>
              {activeTab === "ranking" && (
                <div className="flex-1">
                  <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Factor</label>
                  <select
                    value={factor}
                    onChange={(e) => setFactor(e.target.value)}
                    className="t-input w-full rounded-lg px-3 py-2 text-xs"
                  >
                    <option value="momentum">Momentum</option>
                    <option value="volatility">Volatility (inverse)</option>
                    <option value="sharpe">Sharpe</option>
                  </select>
                </div>
              )}
            </div>

            <button
              onClick={run}
              disabled={loading}
              className="w-full bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white py-2.5 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-all"
              id="multiasset-run-btn"
            >
              {loading ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
              {loading ? "Analyzing…" : "Run Analysis"}
            </button>
          </div>
        </div>
      </div>

      {/* ─── Data Coverage Banner ─── */}
      {(coverageAvailable.length > 0 || coverageMissing.length > 0) && (
        <div className="glass-panel p-3 rounded-xl flex flex-col gap-2">
          {coverageAvailable.length > 0 && (
            <div className="flex items-center gap-2 text-[11px]">
              <span className="font-bold text-emerald-400 uppercase tracking-wider">Available:</span>
              <span className="text-slate-300 font-mono">{coverageAvailable.join(", ")}</span>
            </div>
          )}
          {coverageMissing.length > 0 && (
            <div className="flex items-center gap-2 text-[11px]">
              <span className="font-bold text-rose-400 uppercase tracking-wider">Missing:</span>
              <span className="text-slate-300 font-mono">{coverageMissing.join(", ")}</span>
              <span className="text-slate-500 italic ml-1">Will auto-download after TOTP</span>
            </div>
          )}
        </div>
      )}

      {/* ─── Tabs ─── */}
      <div className="flex items-center gap-1 overflow-x-auto pb-1 border-b border-slate-800/60">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => { setActiveTab(tab.id); setResult(null); }}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-t-lg text-[11px] font-semibold whitespace-nowrap transition-all ${
                active
                  ? "bg-violet-600/20 border border-violet-500/30 text-violet-300"
                  : "text-slate-500 hover:text-slate-300 hover:bg-slate-800/40"
              }`}
            >
              <Icon size={12} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ─── Results ─── */}
      {!result && !loading && (
        <div className="glass-panel rounded-xl p-12 text-center">
          <Network size={40} className="text-slate-700 mx-auto mb-4" />
          <p className="text-slate-500 text-sm">Configure your symbols and run analysis to see results.</p>
        </div>
      )}

      {loading && (
        <div className="glass-panel rounded-xl p-12 text-center">
          <Loader2 size={32} className="text-violet-400 mx-auto mb-4 animate-spin" />
          <p className="text-slate-400 text-sm">Running multi-asset analysis…</p>
        </div>
      )}

      {result && (
        <div className="flex flex-col gap-6">
          {/* Correlation heatmap */}
          {activeTab === "correlation" && correlationHeatmapOpt && (
            <div className="glass-panel rounded-xl p-5">
              <h4 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
                <BarChart2 size={14} className="text-violet-400" /> Correlation Matrix
                <span className="text-[10px] text-slate-500 font-normal ml-1">({result.n_bars_used} bars)</span>
              </h4>
              <ReactECharts option={correlationHeatmapOpt} style={{ height: 380 }} />
            </div>
          )}

          {/* Pair discovery */}
          {activeTab === "pairs" && result.pairs && (
            <div className="glass-panel rounded-xl p-5">
              <h4 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
                <GitBranch size={14} className="text-violet-400" /> Discovered Pairs
                <span className="text-[10px] text-slate-500 font-normal ml-1">({result.pairs.length} pairs)</span>
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-800">
                      {["Rank", "Symbol 1", "Symbol 2", "Correlation", "Type"].map((h) => (
                        <th key={h} className="text-left py-2 px-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.pairs.map((p: any, i: number) => (
                      <tr key={i} className="border-b border-slate-800/40 hover:bg-slate-800/20 transition-colors">
                        <td className="py-2 px-3 font-mono text-slate-500">#{i + 1}</td>
                        <td className="py-2 px-3 font-mono font-bold text-blue-300">{p.sym1}</td>
                        <td className="py-2 px-3 font-mono font-bold text-blue-300">{p.sym2}</td>
                        <td className="py-2 px-3 font-mono font-bold">
                          <span className={p.correlation > 0 ? "text-emerald-400" : "text-rose-400"}>
                            {p.correlation > 0 ? "+" : ""}{p.correlation}
                          </span>
                        </td>
                        <td className="py-2 px-3">
                          <span className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase ${
                            p.pair_type === "correlated"
                              ? "bg-emerald-900/30 text-emerald-400 border border-emerald-800/40"
                              : "bg-rose-900/30 text-rose-400 border border-rose-800/40"
                          }`}>
                            {p.pair_type?.replace("_", " ")}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Cointegration */}
          {activeTab === "cointegration" && (
            <div className="glass-panel rounded-xl p-5">
              <h4 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
                <ArrowRightLeft size={14} className="text-violet-400" />
                Cointegration Test: {result.sym1} / {result.sym2}
              </h4>
              <div className="flex items-center gap-4 mb-6">
                {result.cointegrated ? (
                  <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-4 py-3">
                    <CheckCircle2 size={18} className="text-emerald-400" />
                    <div>
                      <p className="text-emerald-300 font-bold text-sm">Cointegrated</p>
                      <p className="text-[10px] text-emerald-500">Suitable for statistical arbitrage</p>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 bg-rose-500/10 border border-rose-500/20 rounded-lg px-4 py-3">
                    <AlertTriangle size={18} className="text-rose-400" />
                    <div>
                      <p className="text-rose-300 font-bold text-sm">Not Cointegrated</p>
                      <p className="text-[10px] text-rose-500">Proceed with caution</p>
                    </div>
                  </div>
                )}
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricBadge label="P-Value" value={result.pvalue} color={result.pvalue < 0.05 ? "text-emerald-400" : "text-rose-400"} />
                <MetricBadge label="ADF Stat" value={result.adf_stat} />
                <MetricBadge label="Hedge Ratio" value={result.hedge_ratio} color="text-blue-300" />
                <MetricBadge label="Intercept" value={result.intercept} />
              </div>
            </div>
          )}

          {/* Spread & Z-Score */}
          {activeTab === "spread" && spreadChartOpt && (
            <div className="glass-panel rounded-xl p-5">
              <h4 className="text-sm font-bold text-slate-200 mb-2 flex items-center gap-2">
                <Activity size={14} className="text-violet-400" />
                Spread & Z-Score: {result.sym1} / {result.sym2}
              </h4>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <MetricBadge label="Half-Life (bars)" value={result.half_life_bars ?? "∞"} color="text-amber-300" />
                <MetricBadge
                  label="Current Z-Score"
                  value={result.current_zscore ?? "N/A"}
                  color={
                    Math.abs(result.current_zscore) > 2
                      ? "text-rose-400"
                      : Math.abs(result.current_zscore) > 1
                      ? "text-amber-400"
                      : "text-emerald-400"
                  }
                />
                <MetricBadge label="Hedge Ratio" value={result.hedge_ratio} color="text-blue-300" />
              </div>
              <ReactECharts option={spreadChartOpt} style={{ height: 360 }} />
            </div>
          )}

          {/* Lead-Lag */}
          {activeTab === "leadlag" && result.relationships && (
            <div className="glass-panel rounded-xl p-5">
              <h4 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
                <TrendingUp size={14} className="text-violet-400" /> Lead-Lag Relationships
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {Object.values(result.relationships).map((r: any, i: number) => (
                  <div key={i} className="p-3 rounded-lg border border-slate-800/60 bg-slate-900/30">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs font-bold text-slate-300">
                        {r.sym1} / {r.sym2}
                      </span>
                      <span className={`text-[10px] font-mono font-bold ${r.best_lag === 0 ? "text-slate-400" : r.best_lag > 0 ? "text-blue-400" : "text-amber-400"}`}>
                        lag={r.best_lag} (xcorr={r.max_xcorr})
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-500">{r.relationship}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Breadth */}
          {activeTab === "breadth" && (
            <div className="glass-panel rounded-xl p-5">
              <h4 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
                <Layers size={14} className="text-violet-400" /> Sector Breadth
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <MetricBadge
                  label="Breadth %"
                  value={`${result.breadth_pct}%`}
                  color={result.breadth_pct > 60 ? "text-emerald-400" : result.breadth_pct > 40 ? "text-amber-400" : "text-rose-400"}
                />
                <MetricBadge label="Advancing" value={result.advancing} color="text-emerald-400" />
                <MetricBadge label="Declining" value={result.declining} color="text-rose-400" />
                <MetricBadge label="A/D Ratio" value={Number.isFinite(result.ad_ratio) ? result.ad_ratio : "∞"} />
              </div>
              <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
                {Object.entries(result.per_symbol || {}).map(([sym, above]: [string, any]) => (
                  <div
                    key={sym}
                    className={`p-2 rounded-lg border text-center ${
                      above
                        ? "bg-emerald-900/20 border-emerald-800/40"
                        : "bg-rose-900/20 border-rose-800/40"
                    }`}
                  >
                    <span className="font-mono text-xs font-bold text-slate-300 block">{sym}</span>
                    <span className={`text-[10px] font-bold ${above ? "text-emerald-400" : "text-rose-400"}`}>
                      {above ? "▲ Above" : "▼ Below"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Factor Ranking */}
          {activeTab === "ranking" && rankingChartOpt && (
            <div className="glass-panel rounded-xl p-5">
              <h4 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
                <AlignJustify size={14} className="text-violet-400" />
                Cross-Sectional Ranking ({result.factor} / {result.lookback}d lookback)
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <ReactECharts option={rankingChartOpt} style={{ height: 300 }} />
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-slate-800">
                        {["Rank", "Symbol", "Score", "Percentile"].map((h) => (
                          <th key={h} className="text-left py-2 px-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.rankings.map((r: any) => (
                        <tr key={r.symbol} className="border-b border-slate-800/40 hover:bg-slate-800/20">
                          <td className="py-2 px-3 font-mono text-slate-500">#{r.rank}</td>
                          <td className="py-2 px-3 font-mono font-bold text-slate-200">{r.symbol}</td>
                          <td className={`py-2 px-3 font-mono font-bold ${r.raw_score >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                            {r.raw_score > 0 ? "+" : ""}{r.raw_score}
                          </td>
                          <td className="py-2 px-3 font-mono text-slate-400">{r.percentile}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
