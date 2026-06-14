"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { api, formatApiError, type ApiResult } from "../../lib/api-client";

export type NotifType = "success" | "error" | "info";
export interface Notif { type: NotifType; msg: string }
export interface ApiErrorInfo { error: string; retry: () => void }

export interface BacktestDetail {
  id: string;
  strategy_name: string;
  symbol: string;
  symbols: string[];
  interval: string;
  start_time: string;
  end_time: string;
  initial_capital: number;
  final_equity: number;
  total_pnl: number;
  cagr: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  win_rate: number;
  max_position_size: number;
  profit_factor: number;
  total_fees: number;
  metrics?: any;
}

export interface ReplayEvent {
  step: number;
  timestamp: string;
  candle: Record<string, any>;
  orders_submitted: any[];
  orders_filled: any[];
  portfolio: any;
  log_messages: string[];
}

export function useQuantLab() {
  // ── Navigation ──
  const [activeTab, setActiveTab] = useState<string>("dashboard");

  // ── Server & SmartAPI Status ──
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [smartapiConfigured, setSmartapiConfigured] = useState<boolean>(false);
  const [smartapiConnected, setSmartapiConnected] = useState<boolean>(false);

  // ── Ollama Status ──
  const [ollamaState, setOllamaState] = useState<"unknown" | "online" | "offline" | "error">("unknown");
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [ollamaLastError, setOllamaLastError] = useState<string | null>(null);
  const ollamaFailCountRef = useRef(0);
  const ollamaOnlineRef = useRef(false);

  // ── TOTP Popup ──
  const [isTotpModalOpen, setIsTotpModalOpen] = useState<boolean>(false);
  const [totpInput, setTotpInput] = useState<string>("");
  const [pendingAction, setPendingAction] = useState<"AUTH" | "DOWNLOAD" | null>(null);

  // ── Data Collections ──
  const [datasets, setDatasets] = useState<any[]>([]);
  const [strategies, setStrategies] = useState<any[]>([]);
  const [backtestRuns, setBacktestRuns] = useState<any[]>([]);
  const [deployments, setDeployments] = useState<any[]>([]);

  // ── Selected Objects ──
  const [selectedStrategyId, setSelectedStrategyId] = useState<string>("");
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [selectedRunId, setSelectedRunId] = useState<string>("");

  // ── Strategy Editor ──
  const [code, setCode] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string>("");
  const [strategyName, setStrategyName] = useState<string>("");
  const [strategySymbols, setStrategySymbols] = useState<string>("SBIN");
  const [strategyInterval, setStrategyInterval] = useState<string>("FIVE_MINUTE");
  const [strategyCapital, setStrategyCapital] = useState<number>(100000);
  const [strategyMaxPos, setStrategyMaxPos] = useState<number>(0);
  const [strategyRuntimeType, setStrategyRuntimeType] = useState<string>("legacy_on_bar");
  const [strategyEntrypoint, setStrategyEntrypoint] = useState<string | null>(null);
  const [strategyParams, setStrategyParams] = useState<string>("");
  const [strategyRisk, setStrategyRisk] = useState<string>("");

  // ── Backtest Inputs ──
  const [btStartDate, setBtStartDate] = useState<string>(() => {
    const d = new Date(); d.setDate(d.getDate() - 7); return d.toISOString().slice(0, 10);
  });
  const [btEndDate, setBtEndDate] = useState<string>(() => new Date().toISOString().slice(0, 10));
  const [btSlippage, setBtSlippage] = useState<number>(0.05);
  const [btTradeType, setBtTradeType] = useState<string>("INTRADAY");
  const [btIsAutoMaxPos, setBtIsAutoMaxPos] = useState<boolean>(true);
  const [btAutoMaxPosValue, setBtAutoMaxPosValue] = useState<number>(0);
  const [btMaxPositionSize, setBtMaxPositionSize] = useState<number>(0);

  // ── Replay State ──
  const [backtestDetail, setBacktestDetail] = useState<BacktestDetail | null>(null);
  const [replayEvents, setReplayEvents] = useState<ReplayEvent[]>([]);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(2);

  // ── Chart Toggles ──
  const [showEmaFast, setShowEmaFast] = useState<boolean>(true);
  const [showEmaSlow, setShowEmaSlow] = useState<boolean>(true);
  const [showBuyTrades, setShowBuyTrades] = useState<boolean>(true);
  const [showSellTrades, setShowSellTrades] = useState<boolean>(true);

  // ── Research / Capital / Optimization ──
  const [researchData, setResearchData] = useState<any>(null);
  const [capitalData, setCapitalData] = useState<any>(null);
  const [optimizationGrid, setOptimizationGrid] = useState<any>(null);

  // ── Optimization Inputs ──
  const [optParamName1, setOptParamName1] = useState<string>("ema_fast");
  const [optParamVals1, setOptParamVals1] = useState<string>("5, 9, 15");
  const [optParamName2, setOptParamName2] = useState<string>("ema_slow");
  const [optParamVals2, setOptParamVals2] = useState<string>("20, 30, 50");

  // ── Deployment ──
  const [deploymentFormOpen, setDeploymentFormOpen] = useState<boolean>(false);
  const [depStrategyId, setDepStrategyId] = useState<string>("");
  const [depName, setDepName] = useState<string>("");
  const [depSymbol, setDepSymbol] = useState<string>("");
  const [depMode, setDepMode] = useState<string>("paper");

  // ── Cleanup ──
  const [cleanupStatus, setCleanupStatus] = useState<any>(null);
  const [cleanupLoading, setCleanupLoading] = useState<boolean>(false);
  const [cleanupDryRun, setCleanupDryRun] = useState<boolean>(true);
  const [cleanupTarget, setCleanupTarget] = useState<string>("logs");
  const [cleanupSymbol, setCleanupSymbol] = useState<string>("");
  const [cleanupInterval, setCleanupInterval] = useState<string>("");
  const [cleanupOlderThan, setCleanupOlderThan] = useState<number | "">("");
  const [cleanupStrategyId, setCleanupStrategyId] = useState<string>("");
  const [cleanupResult, setCleanupResult] = useState<any>(null);

  // ── Dataset download ──
  const [dlSymbol, setDlSymbol] = useState<string>("SBIN");
  const [dlInterval, setDlInterval] = useState<string>("ONE_MINUTE");
  const [dlFromDate, setDlFromDate] = useState<string>(() => {
    const d = new Date(); d.setDate(d.getDate() - 7); return d.toISOString().slice(0, 10);
  });
  const [dlToDate, setDlToDate] = useState<string>(() => new Date().toISOString().slice(0, 10));
  const [downloading, setDownloading] = useState<boolean>(false);

  // ── Dataset preview ──
  const [previewData, setPreviewData] = useState<any>(null);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // ── Pending backtest auto-download ──
  const [pendingBacktest, setPendingBacktest] = useState<{
    strategyId: string;
    symbols: string[];
    interval: string;
    startDate: string;
    endDate: string;
  } | null>(null);

  // ── Pending multi-asset auto-download ──
  const [pendingMultiAsset, setPendingMultiAsset] = useState<{
    symbols: string[];
    interval: string;
    activeTab: string;
    params: any;
  } | null>(null);

  // ── Multi-asset retry signal ──
  const [multiAssetRetrySignal, setMultiAssetRetrySignal] = useState<number>(0);

  // ── Batch download queue (mutable ref, used for sequential auto-downloads) ──
  const downloadQueueRef = useRef<string[]>([]);
  const batchDownloadCountRef = useRef(0);
  const setDownloadQueue = useCallback((symbols: string[]) => {
    downloadQueueRef.current = symbols;
    batchDownloadCountRef.current = 0;
  }, []);

  // ── Autocomplete ──
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState<boolean>(false);
  const [strategySuggestions, setStrategySuggestions] = useState<any[]>([]);
  const [showStrategySuggestions, setShowStrategySuggestions] = useState<boolean>(false);

  // ── Notifications & Errors ──
  const [notif, setNotif] = useState<Notif | null>(null);
  const [apiErrors, setApiErrors] = useState<Record<string, ApiErrorInfo>>({});

  const triggerNotif = useCallback((type: NotifType, msg: string) => {
    setNotif({ type, msg });
    setTimeout(() => setNotif(null), 5000);
  }, []);

  const setEndpointError = useCallback((endpoint: string, error: string | null, retry?: () => void) => {
    setApiErrors(prev => {
      const next = { ...prev };
      if (error === null) { delete next[endpoint]; }
      else { next[endpoint] = { error, retry: retry || (() => {}) }; }
      return next;
    });
  }, []);

  const clearEndpointError = useCallback((endpoint: string) => {
    setApiErrors(prev => {
      const next = { ...prev };
      delete next[endpoint];
      return next;
    });
  }, []);

  // ── Refs for latest state (prevents stale closures) ──
  const stateRef = useRef({
    strategies, datasets, backtestRuns, deployments,
    backendOnline, selectedStrategyId, dlSymbol, dlInterval,
    dlFromDate, dlToDate, strategyCapital, strategyName,
    btStartDate, btEndDate, btSlippage, btTradeType,
    btIsAutoMaxPos, btAutoMaxPosValue, btMaxPositionSize,
    pendingBacktest, pendingMultiAsset, backendOnlineRef: false,
  });
  stateRef.current = {
    strategies, datasets, backtestRuns, deployments,
    backendOnline, selectedStrategyId, dlSymbol, dlInterval,
    dlFromDate, dlToDate, strategyCapital, strategyName,
    btStartDate, btEndDate, btSlippage, btTradeType,
    btIsAutoMaxPos, btAutoMaxPosValue, btMaxPositionSize,
    pendingBacktest, pendingMultiAsset, backendOnlineRef: backendOnline,
  };

  // ── CONNECTIVITY ──

  const checkBackendHealth = useCallback(async () => {
    const result = await api.get("/strategies", { timeout: 5000 });
    if (result.ok) {
      setBackendOnline(true);
      clearEndpointError("health");
    } else {
      setBackendOnline(false);
      if (result.isNetworkError) {
        setEndpointError("health", "Backend is offline. Start the FastAPI server.", checkBackendHealth);
      }
    }
  }, [clearEndpointError, setEndpointError]);

  const checkOllamaHealth = useCallback(async () => {
    if (!stateRef.current.backendOnline) { setOllamaState("offline"); ollamaOnlineRef.current = false; return; }
    const result = await api.get("/forge/status", { timeout: 5000 });
    if (result.ok && result.data) {
      const { state, models, last_error } = result.data;
      setOllamaModels(models || []);
      setOllamaLastError(last_error || null);
      if (state === "online") {
        ollamaFailCountRef.current = 0;
        ollamaOnlineRef.current = true;
        setOllamaState("online");
        clearEndpointError("ollama/status");
      } else {
        ollamaFailCountRef.current += 1;
        if (ollamaFailCountRef.current >= 2) {
          ollamaOnlineRef.current = false;
          setOllamaState(state === "error" ? "error" : "offline");
          setEndpointError("ollama/status", last_error || "Ollama is unreachable. Start it with: ollama serve", checkOllamaHealth);
        }
      }
    } else {
      ollamaFailCountRef.current += 1;
      if (ollamaFailCountRef.current >= 2) {
        ollamaOnlineRef.current = false;
        setOllamaState("offline");
        setEndpointError("ollama/status", result.error || "Ollama status check failed.", checkOllamaHealth);
      }
    }
  }, [clearEndpointError, setEndpointError]);

  // ── CORE DATA FETCHING ──
  // Fetches all core data from backend. Uses refs to avoid stale closures.

  const fetchCoreData = useCallback(async () => {
    if (!stateRef.current.backendOnline) return;

    const [stratRes, catRes, runsRes, depRes, sapiRes] = await Promise.all([
      api.get("/strategies"),
      api.get("/data/datasets"),
      api.get("/backtest/results"),
      api.get("/deployments"),
      api.get("/auth/smartapi/status"),
    ]);

    if (stratRes.ok && stratRes.data) {
      clearEndpointError("strategies");
      setStrategies(stratRes.data);
    } else if (!stratRes.ok) {
      setEndpointError("strategies", formatApiError(stratRes, "Strategies"), fetchCoreData);
      triggerNotif("error", formatApiError(stratRes, "Strategies"));
    }

    if (catRes.ok && catRes.data) {
      clearEndpointError("datasets");
      const catalogData = Object.values(catRes.data || {});
      setDatasets(catalogData);
    } else if (!catRes.ok) {
      setEndpointError("datasets", formatApiError(catRes, "Datasets"), fetchCoreData);
      triggerNotif("error", formatApiError(catRes, "Datasets"));
    }

    if (runsRes.ok && runsRes.data) {
      clearEndpointError("backtest/results");
      setBacktestRuns(runsRes.data || []);
    } else if (!runsRes.ok) {
      setEndpointError("backtest/results", formatApiError(runsRes, "Backtest runs"), fetchCoreData);
      triggerNotif("error", formatApiError(runsRes, "Backtest runs"));
    }

    if (depRes.ok && depRes.data) {
      clearEndpointError("deployments");
      setDeployments(depRes.data || []);
    } else if (!depRes.ok) {
      setEndpointError("deployments", formatApiError(depRes, "Deployments"), fetchCoreData);
      triggerNotif("error", formatApiError(depRes, "Deployments"));
    }

    if (sapiRes.ok && sapiRes.data) {
      clearEndpointError("smartapi/status");
      setSmartapiConfigured(sapiRes.data.configured);
      setSmartapiConnected(sapiRes.data.connected);
    } else if (!sapiRes.ok) {
      setEndpointError("smartapi/status", formatApiError(sapiRes, "SmartAPI status"), fetchCoreData);
    }
  }, [clearEndpointError, setEndpointError, triggerNotif]);

  useEffect(() => {
    checkBackendHealth();
    const interval = setInterval(() => {
      checkBackendHealth();
    }, 5000);
    return () => clearInterval(interval);
  }, [checkBackendHealth]);

  useEffect(() => {
    if (backendOnline) fetchCoreData();
  }, [backendOnline, fetchCoreData]);

  // ── AUTOCOMPLETE DEBOUNCE ──

  useEffect(() => {
    if (!dlSymbol || dlSymbol.length < 2) { setSuggestions([]); return; }
    if (!backendOnline) return;
    const delay = setTimeout(() => {
      api.get(`/data/symbols/search?q=${encodeURIComponent(dlSymbol)}`)
        .then(r => { if (r.ok && r.data) setSuggestions(r.data); else setSuggestions([]); })
        .catch(() => setSuggestions([]));
    }, 250);
    return () => clearTimeout(delay);
  }, [dlSymbol, backendOnline]);

  useEffect(() => {
    const lastToken = strategySymbols.split(",").pop()?.trim() || "";
    if (!lastToken || lastToken.length < 2) { setStrategySuggestions([]); return; }
    if (!backendOnline) return;
    const delay = setTimeout(() => {
      api.get(`/data/symbols/search?q=${encodeURIComponent(lastToken)}`)
        .then(r => { if (r.ok && r.data) setStrategySuggestions(r.data); else setStrategySuggestions([]); })
        .catch(() => setStrategySuggestions([]));
    }, 250);
    return () => clearTimeout(delay);
  }, [strategySymbols, backendOnline]);

  // ── FILE UPLOAD ──

  const handleFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.endsWith(".py")) { triggerNotif("error", "Only .py files are allowed."); return; }
    const reader = new FileReader();
    reader.onload = (ev) => {
      const content = String(ev.target?.result || "");
      setCode(content);
      setUploadedFileName(file.name);
      setSelectedStrategyId("");
      triggerNotif("success", `Loaded ${file.name} (${content.length} chars)`);
    };
    reader.readAsText(file);
  }, [triggerNotif]);

  // ── STRATEGY HANDLERS ──

  const handleSelectStrategy = useCallback(async (id: string) => {
    setSelectedStrategyId(id);
    if (!stateRef.current.backendOnline) { triggerNotif("info", "Loaded strategy template in memory."); return; }
    const result = await api.get(`/strategies/${id}`);
    if (result.ok && result.data) {
      const s = result.data;
      setCode(s.code || "");
      setStrategyName(s.name || "");
      setStrategySymbols((s.symbols || ["SBIN"]).join(", "));
      setStrategyInterval(s.interval || "FIVE_MINUTE");
      setStrategyCapital(s.initial_capital || 100000);
      setStrategyMaxPos(s.max_position_size || 0);
      setStrategyRuntimeType(s.runtime_type || "legacy_on_bar");
      setStrategyEntrypoint(s.entrypoint || null);
      setStrategyParams(s.parameters_json || "");
      setStrategyRisk(s.risk_settings_json || "");
      setUploadedFileName(`${s.name}.py`);
      triggerNotif("success", `Loaded strategy: ${s.name}`);
      clearEndpointError(`strategies/${id}`);
    } else {
      setEndpointError(`strategies/${id}`, result.error || "Failed to load strategy", () => handleSelectStrategy(id));
      triggerNotif("error", `Failed to fetch strategy: ${result.error}`);
    }
  }, [triggerNotif, clearEndpointError, setEndpointError]);

  const handleSaveStrategy = useCallback(async () => {
    if (!strategyName.trim()) { triggerNotif("error", "Strategy name is required."); return; }
    if (!code.trim()) { triggerNotif("error", "Strategy code is required."); return; }
    const payload = {
      name: strategyName,
      description: "Strategy created in QuantLab",
      code,
      symbols: strategySymbols.split(",").map(s => s.trim().toUpperCase()).filter(Boolean),
      interval: strategyInterval,
      initial_capital: strategyCapital,
      max_position_size: strategyMaxPos || null,
      parameters_json: strategyParams || null,
      risk_settings_json: strategyRisk || null,
      runtime_type: strategyRuntimeType,
      entrypoint: strategyEntrypoint,
    };
    if (!selectedStrategyId) {
      if (!stateRef.current.backendOnline) {
        const mockId = `S-MOCK-${Math.floor(Math.random()*90000)+10000}`;
        setStrategies(prev => [...prev, { id: mockId, ...payload, version: 1, updated_at: new Date() }]);
        setSelectedStrategyId(mockId);
        triggerNotif("success", "Strategy template saved to memory!");
        return;
      }
      const result = await api.post("/strategies", payload);
      if (result.ok && result.data) {
        triggerNotif("success", "Strategy created in DB!");
        fetchCoreData();
        setSelectedStrategyId(result.data.id);
      } else {
        triggerNotif("error", `Failed to save strategy: ${result.error || "Unknown error"}`);
      }
    } else {
      if (!stateRef.current.backendOnline) { triggerNotif("success", "Local strategy updated!"); return; }
      const result = await api.put(`/strategies/${selectedStrategyId}`, payload);
      if (result.ok) { triggerNotif("success", "Strategy updated successfully!"); fetchCoreData(); }
      else { triggerNotif("error", `Failed to update strategy: ${result.error || "Unknown error"}`); }
    }
  }, [strategyName, code, strategySymbols, strategyInterval, strategyCapital, strategyMaxPos, strategyParams, strategyRisk, strategyRuntimeType, strategyEntrypoint, selectedStrategyId, triggerNotif, fetchCoreData]);

  const handleNewStrategy = useCallback(() => {
    setSelectedStrategyId("");
    setStrategyName("");
    setStrategySymbols("SBIN");
    setStrategyInterval("FIVE_MINUTE");
    setStrategyCapital(100000);
    setStrategyMaxPos(0);
    setCode("");
    setUploadedFileName("");
    setStrategyParams("");
    setStrategyRisk("");
    triggerNotif("info", "Cleared. Configure a new strategy.");
  }, [triggerNotif]);

  // ── BACKTEST HANDLERS ──

  const runFrontendSimulation = useCallback(() => {
    triggerNotif("info", "Backend offline. Executing client-side simulated backtest...");
    const numBars = 100;
    const mockCandles: any[] = [];
    let price = 500.0;
    const baseDate = new Date();
    for (let i = 0; i < numBars; i++) {
      const barTime = new Date(baseDate.getTime() + i * 60000);
      const ret = (Math.random() - 0.48) * 4.0;
      const o = price;
      const c = price + ret;
      const h = Math.max(o, c) + Math.random() * 1.5;
      const l = Math.min(o, c) - Math.random() * 1.5;
      mockCandles.push({
        time: barTime.toISOString().replace("T", " ").slice(0, 19),
        open: Number(o.toFixed(2)), high: Number(h.toFixed(2)), low: Number(l.toFixed(2)), close: Number(c.toFixed(2)),
        volume: Math.floor(Math.random() * 5000) + 100
      });
      price = c;
    }

    const trades: any[] = [];
    const equityCurve: any[] = [];
    const events: ReplayEvent[] = [];
    let cash = strategyCapital;
    let positionQty = 0;
    let avgPrice = 0.0;
    let unrealized = 0.0;
    let realized = 0.0;
    let fees = 0.0;

    for (let idx = 0; idx < numBars; idx++) {
      const currentCandle = mockCandles[idx];
      const slice = mockCandles.slice(0, idx + 1);
      const closes = slice.map((x: any) => x.close);
      const ema9 = calculateSimpleEMA(closes, 9);
      const ema21 = calculateSimpleEMA(closes, 21);
      const prevEma9 = idx > 0 ? calculateSimpleEMA(closes.slice(0, -1), 9) : ema9;
      const prevEma21 = idx > 0 ? calculateSimpleEMA(closes.slice(0, -1), 21) : ema21;
      const symbol = "MOCK-SBIN";
      const ts = currentCandle.time;
      const orderRequests: any[] = [];
      const filledTrades: any[] = [];

      if (idx >= 21) {
        if (prevEma9 <= prevEma21 && ema9 > ema21 && positionQty <= 0) {
          const orderQty = positionQty < 0 ? 20 : 10;
          const buyPrice = currentCandle.close * (1 + btSlippage / 100);
          const fee = 20.0 + (buyPrice * orderQty * 0.0003);
          fees += fee; cash -= fee;
          if (positionQty < 0) { const profit = (avgPrice - buyPrice) * 10; realized += profit; cash += (avgPrice * 10) + profit; }
          positionQty += orderQty; avgPrice = buyPrice;
          const newTrade = { id: `T-MOCK-${Math.floor(Math.random()*90000)+10000}`, order_id: `O-MOCK-${idx}`, timestamp: ts, symbol, direction: "BUY", price: buyPrice, qty: orderQty, total_charges: fee };
          trades.push(newTrade); filledTrades.push(newTrade); orderRequests.push({ symbol, direction: "BUY", type: "MARKET", price: 0.0, qty: orderQty });
        } else if (prevEma9 >= prevEma21 && ema9 < ema21 && positionQty >= 0) {
          const orderQty = positionQty > 0 ? 20 : 10;
          const sellPrice = currentCandle.close * (1 - btSlippage / 100);
          const fee = 20.0 + (sellPrice * orderQty * 0.0003);
          fees += fee; cash -= fee;
          if (positionQty > 0) { const profit = (sellPrice - avgPrice) * 10; realized += profit; cash += (avgPrice * 10) + profit; }
          positionQty -= orderQty; avgPrice = sellPrice;
          const newTrade = { id: `T-MOCK-${Math.floor(Math.random()*90000)+10000}`, order_id: `O-MOCK-${idx}`, timestamp: ts, symbol, direction: "SELL", price: sellPrice, qty: orderQty, total_charges: fee };
          trades.push(newTrade); filledTrades.push(newTrade); orderRequests.push({ symbol, direction: "SELL", type: "MARKET", price: 0.0, qty: orderQty });
        }
      }

      unrealized = positionQty * (currentCandle.close - avgPrice);
      const equity = cash + unrealized;
      const marginUsed = Math.abs(positionQty) * currentCandle.close * 0.20;
      equityCurve.push({ time: ts, equity, cash, unrealized_pnl: unrealized, margin_used: marginUsed, fees });
      events.push({
        step: idx, timestamp: ts,
        candle: { [symbol]: currentCandle },
        orders_submitted: orderRequests, orders_filled: filledTrades,
        portfolio: { cash, margin_used: marginUsed, margin_free: equity - marginUsed, equity, unrealized_pnl: unrealized, total_fees: fees, total_pnl: realized + unrealized, positions: { [symbol]: { symbol, qty: positionQty, avg_price: avgPrice, unrealized_pnl: unrealized } } },
        log_messages: orderRequests.length > 0 ? ["[Sim Engine] Technical EMA Crossover triggered trade order!"] : []
      });
    }

    const mockId = `B-MOCK-${Math.floor(Math.random()*90000)+10000}`;
    const resultObj = { run_id: mockId, trades, equity_curve: equityCurve, final_portfolio: equityCurve[equityCurve.length - 1], log_file_path: "" };

    setBacktestDetail({
      id: mockId,
      strategy_name: strategyName || "EMA Crossover Template (Simulated)",
      symbol: "MOCK-SBIN", symbols: ["MOCK-SBIN"], interval: "ONE_MINUTE",
      start_time: mockCandles[0].time, end_time: mockCandles[mockCandles.length - 1].time,
      initial_capital: strategyCapital, final_equity: resultObj.final_portfolio.equity,
      total_pnl: resultObj.final_portfolio.equity - strategyCapital,
      cagr: 0.154, sharpe_ratio: 1.84, sortino_ratio: 2.12, max_drawdown: 0.042, win_rate: 0.60,
      max_position_size: btMaxPositionSize, profit_factor: 1.74, total_fees: fees,
      metrics: {
        cost_breakdown: { brokerage: fees * 0.4, stt: fees * 0.3, exchange_charges: fees * 0.1, gst: fees * 0.1, sebi_charges: fees * 0.05, stamp_duty: fees * 0.05, total_fees: fees },
        trade_metrics: { total_trades: trades.length, win_trades: Math.floor(trades.length * 0.6), loss_trades: trades.length - Math.floor(trades.length * 0.6), avg_win: 450.0, avg_loss: -250.0, gross_profit: 450.0 * Math.floor(trades.length * 0.6), gross_loss: 250.0 * (trades.length - Math.floor(trades.length * 0.6)) }
      }
    });

    setReplayEvents(events);
    setCurrentStep(0);
    setBacktestRuns(prev => [{
      id: mockId, strategy_name: strategyName || "EMA Crossover (Simulated)", symbol: "MOCK-SBIN", symbols: ["MOCK-SBIN"], interval: "ONE_MINUTE",
      start_time: mockCandles[0].time, end_time: mockCandles[mockCandles.length - 1].time,
      total_pnl: resultObj.final_portfolio.equity - strategyCapital,
      cagr: 0.154, sharpe_ratio: 1.84, max_position_size: btMaxPositionSize, max_drawdown: 0.042,
      created_at: new Date().toISOString()
    }, ...prev]);
    setSelectedRunId(mockId);

    setResearchData({
      regime_attribution: { TRENDING_BULLISH: { trade_count: 5, total_pnl: 1200.0, avg_pnl: 240.0, win_rate: 0.8 }, TRENDING_BEARISH: { trade_count: 3, total_pnl: 450.0, avg_pnl: 150.0, win_rate: 0.66 }, VOLATILE_RANGING: { trade_count: 4, total_pnl: -300.0, avg_pnl: -75.0, win_rate: 0.25 }, QUIET_RANGING: { trade_count: 2, total_pnl: 100.0, avg_pnl: 50.0, win_rate: 0.5 }, GAP_DAY: { trade_count: 1, total_pnl: -50.0, avg_pnl: -50.0, win_rate: 0.0 } },
      market_regime_distribution: { TRENDING_BULLISH: 0.35, TRENDING_BEARISH: 0.20, VOLATILE_RANGING: 0.15, QUIET_RANGING: 0.25, GAP_DAY: 0.05 }
    });

    setCapitalData({
      minimum_viable_capital: 35000.0, optimal_capital_allocation: 50000.0,
      scaling_curve: [
        { capital: 25000, cagr: 0.18, sharpe: 1.6, margin_call: true },
        { capital: 50000, cagr: 0.16, sharpe: 1.9, margin_call: false },
        { capital: 100000, cagr: 0.15, sharpe: 1.8, margin_call: false },
        { capital: 250000, cagr: 0.12, sharpe: 1.5, margin_call: false },
        { capital: 500000, cagr: 0.08, sharpe: 1.1, margin_call: false },
        { capital: 1000000, cagr: 0.04, sharpe: 0.6, margin_call: false }
      ]
    });

    setOptimizationGrid({
      results: [
        { parameters: { ema_fast: 5, ema_slow: 20 }, cagr: 0.12, sharpe: 1.3, max_drawdown: 0.08, status: "SUCCESS" },
        { parameters: { ema_fast: 9, ema_slow: 21 }, cagr: 0.15, sharpe: 1.8, max_drawdown: 0.04, status: "SUCCESS" },
        { parameters: { ema_fast: 15, ema_slow: 30 }, cagr: 0.09, sharpe: 1.1, max_drawdown: 0.06, status: "SUCCESS" },
        { parameters: { ema_fast: 9, ema_slow: 50 }, cagr: 0.05, sharpe: 0.7, max_drawdown: 0.05, status: "SUCCESS" }
      ],
      best_result: { parameters: { ema_fast: 9, ema_slow: 21 }, cagr: 0.15, sharpe: 1.8, max_drawdown: 0.04 },
      parameter_names: ["ema_fast", "ema_slow"], total_runs: 4
    });

    setActiveTab("backtests");
    triggerNotif("success", "Client simulated run generated! Loaded in Backtests.");
  }, [strategyCapital, strategyName, btSlippage, btMaxPositionSize, triggerNotif]);

  const loadBacktestReplay = useCallback(async (runId: string) => {
    if (!stateRef.current.backendOnline) return;
    const detRes = await api.get(`/backtest/results/${runId}`);
    if (detRes.ok && detRes.data) { setBacktestDetail(detRes.data); clearEndpointError(`backtest/results/${runId}`); }
    else { setEndpointError(`backtest/results/${runId}`, detRes.error || "Failed to load backtest details", () => loadBacktestReplay(runId)); triggerNotif("error", `Replay details unavailable: ${detRes.error}`); }

    const logsRes = await api.get(`/backtest/logs/${runId}`);
    if (logsRes.ok && logsRes.data) { setReplayEvents(logsRes.data); setCurrentStep(0); setIsPlaying(false); clearEndpointError(`backtest/logs/${runId}`); }
    else { setEndpointError(`backtest/logs/${runId}`, logsRes.error || "Failed to load replay logs", () => loadBacktestReplay(runId)); triggerNotif("error", `Replay logs unavailable: ${logsRes.error}`); }

    const regRes = await api.get(`/research/regimes/${runId}`);
    if (regRes.ok && regRes.data) { setResearchData(regRes.data); clearEndpointError(`research/regimes/${runId}`); }
    else if (regRes.status === 404) { setResearchData(null); }
    else { setEndpointError(`research/regimes/${runId}`, regRes.error || "Research data unavailable", () => loadBacktestReplay(runId)); }

    const capRes = await api.get(`/capital/analysis/${runId}`);
    if (capRes.ok && capRes.data) { setCapitalData(capRes.data); clearEndpointError(`capital/analysis/${runId}`); }
    else if (capRes.status === 404) { setCapitalData(null); }
    else { setEndpointError(`capital/analysis/${runId}`, capRes.error || "Capital analysis unavailable", () => loadBacktestReplay(runId)); }
  }, [clearEndpointError, setEndpointError, triggerNotif]);

  const checkDataCoverage = useCallback((symbols: string[], interval: string, startDate: string, endDate: string) => {
    const missing: { symbol: string; interval: string; reason: string }[] = [];
    for (const sym of symbols) {
      const symBase = sym.toUpperCase().trim();
      const ds = datasets.find((d: any) => {
        const dsSym = (d.symbol || "").toUpperCase().trim();
        // Match either bare "SBIN" or canonical "NSE:SBIN-EQ" by extracting the base symbol
        const dsBase = dsSym.includes(":") ? dsSym.split(":")[1].replace(/-EQ$|-BE$/i, "") : dsSym.replace(/-EQ$|-BE$/i, "");
        return dsBase === symBase && (d.interval || "").toUpperCase() === interval.toUpperCase();
      });
      if (!ds) {
        missing.push({ symbol: sym, interval, reason: "No dataset found." });
        continue;
      }
      const dsStart = ds.start_date ? ds.start_date.slice(0, 10) : null;
      const dsEnd = ds.end_date ? ds.end_date.slice(0, 10) : null;
      if (!dsStart || !dsEnd) {
        missing.push({ symbol: sym, interval, reason: "Dataset has no date range metadata." });
        continue;
      }
      if (startDate < dsStart || endDate > dsEnd) {
        missing.push({ symbol: sym, interval, reason: `Dataset only covers ${dsStart} to ${dsEnd}.` });
      }
    }
    return missing;
  }, [datasets]);

  const handleRunBacktest = useCallback(async () => {
    const ref = stateRef.current;
    if (!ref.selectedStrategyId) { triggerNotif("info", "Please select a strategy first."); return; }
    const selectedStrategy = ref.strategies.find((s: any) => s.id === ref.selectedStrategyId);
    if (!selectedStrategy) { triggerNotif("error", "Selected strategy not found."); return; }
    if (!ref.backendOnline) { runFrontendSimulation(); return; }
    const symbols = selectedStrategy.symbols || [selectedStrategy.symbol || "SBIN"];
    const interval = selectedStrategy.interval || "FIVE_MINUTE";

    const missing = checkDataCoverage(symbols, interval, ref.btStartDate, ref.btEndDate);
    if (missing.length > 0) {
      const first = missing[0];
      downloadQueueRef.current = []; // clear any stale batch queue
      batchDownloadCountRef.current = 0;
      triggerNotif("error", `Missing data for ${first.symbol} (${first.interval}): ${first.reason}`);
      setPendingBacktest({ strategyId: ref.selectedStrategyId, symbols, interval, startDate: ref.btStartDate, endDate: ref.btEndDate });
      setDlSymbol(first.symbol);
      setDlInterval(interval);
      setDlFromDate(ref.btStartDate);
      setDlToDate(ref.btEndDate);
      setPendingAction("DOWNLOAD");
      setIsTotpModalOpen(true);
      return;
    }

    triggerNotif("info", `Initiating backtest on ${symbols.join(", ")}...`);
    const result = await api.post("/backtest/run", {
      strategy_id: ref.selectedStrategyId, start_date: ref.btStartDate, end_date: ref.btEndDate,
      slippage_pct: ref.btSlippage / 100.0, trade_type: ref.btTradeType,
      max_position_size: ref.btIsAutoMaxPos ? ref.btAutoMaxPosValue : ref.btMaxPositionSize, auto_download: true,
    });
    if (result.ok && result.data) {
      triggerNotif("success", "Backtest run completed successfully!");
      setSelectedRunId(result.data.run_id);
      fetchCoreData();
      loadBacktestReplay(result.data.run_id);
      setActiveTab("backtests");
    } else {
      triggerNotif("error", `Backtest failed: ${result.error || "Engine error"}`);
    }
  }, [triggerNotif, runFrontendSimulation, checkDataCoverage, fetchCoreData, loadBacktestReplay]);

  const handleSelectRun = useCallback((runId: string) => {
    setSelectedRunId(runId);
    loadBacktestReplay(runId);
    triggerNotif("success", `Loaded run ${runId} metadata.`);
  }, [loadBacktestReplay, triggerNotif]);

  // ── REPLAY CONTROLS ──

  useEffect(() => {
    if (!isPlaying || replayEvents.length === 0) return;
    const intervalVal = setInterval(() => {
      setCurrentStep(prev => {
        if (prev >= replayEvents.length - 1) { setIsPlaying(false); return prev; }
        return prev + 1;
      });
    }, 1000 / playbackSpeed);
    return () => clearInterval(intervalVal);
  }, [isPlaying, playbackSpeed, replayEvents]);

  const currentEvent = replayEvents[currentStep] || null;
  const currentCandleMap = currentEvent?.candle || {};
  const currentSymbol = Object.keys(currentCandleMap)[0] || "";
  const currentPortfolio = currentEvent?.portfolio || null;

  const activeCandles = useMemo(() => {
    if (replayEvents.length === 0) return [];
    return replayEvents.slice(0, currentStep + 1).map((ev: any) => {
      const c = ev.candle?.[currentSymbol];
      return c ? { time: ev.timestamp, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume } : null;
    }).filter(Boolean) as any[];
  }, [replayEvents, currentStep, currentSymbol]);

  const activeTrades = useMemo(() => {
    if (replayEvents.length === 0) return [];
    const trades: any[] = [];
    replayEvents.slice(0, currentStep + 1).forEach((ev: any) => {
      if (ev.orders_filled && ev.orders_filled.length > 0) {
        ev.orders_filled.forEach((t: any) => trades.push({ time: ev.timestamp, direction: t.direction, price: t.price, qty: t.qty }));
      }
    });
    return trades;
  }, [replayEvents, currentStep]);

  const positionCurveData = useMemo(() => {
    if (replayEvents.length === 0) return [];
    return replayEvents.slice(0, currentStep + 1).map((ev: any) => ({
      time: ev.timestamp,
      value: ev.portfolio?.positions ? Object.values(ev.portfolio.positions).reduce((acc: number, p: any) => acc + p.qty, 0) : 0
    }));
  }, [replayEvents, currentStep]);

  // ── AUTH & DOWNLOAD ──

  const triggerAuth = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!stateRef.current.backendOnline) { triggerNotif("error", "Backend is offline. Start the server to authenticate SmartAPI."); return; }
    setPendingAction("AUTH");
    setIsTotpModalOpen(true);
  }, [triggerNotif]);

  const finalizeAuth = useCallback(async (code: string) => {
    const result = await api.post("/auth/smartapi/connect", { totp: code });
    if (result.ok && result.data?.connection_success) {
      setSmartapiConfigured(true); setSmartapiConnected(true);
      triggerNotif("success", "SmartAPI Authenticated & Connected!");
      fetchCoreData();
    } else {
      triggerNotif("error", `SmartAPI connection failed: ${result.error || result.data?.message || "Bad keys"}`);
    }
  }, [triggerNotif, fetchCoreData]);

  const triggerDownload = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    downloadQueueRef.current = []; // clear any stale batch queue
    batchDownloadCountRef.current = 0;
    setPendingAction("DOWNLOAD");
    setIsTotpModalOpen(true);
  }, []);

  const finalizeDownload = useCallback(async (code: string) => {
    const ref = stateRef.current;
    const sym = ref.dlSymbol;
    setDownloading(true);
    triggerNotif("info", `Downloading ${sym}…`);
    if (!ref.backendOnline) {
      setDownloading(false);
      triggerNotif("error", "Backend is offline. Cannot download data.");
      return;
    }
    // Append market hours to dates so SmartAPI receives YYYY-MM-DD HH:MM format
    const fromDate = `${ref.dlFromDate} 09:15`;
    const toDate = `${ref.dlToDate} 15:30`;
    // First download in a batch uses TOTP; chained downloads reuse the already-authenticated SmartAPI session
    batchDownloadCountRef.current += 1;
    const isFirst = batchDownloadCountRef.current === 1;
    const result = await api.post("/data/download", { symbol: sym, interval: ref.dlInterval, from_date: fromDate, to_date: toDate, totp: isFirst ? code : undefined });
    setDownloading(false);
    if (result.ok && result.data) {
      triggerNotif("success", `Downloaded ${sym} successfully!`);
      fetchCoreData();
      // ── Batch queue chaining ──
      // Remove the just-downloaded symbol from the queue
      downloadQueueRef.current = downloadQueueRef.current.filter(s => s.toUpperCase() !== sym.toUpperCase());
      if (downloadQueueRef.current.length > 0) {
        const next = downloadQueueRef.current[0];
        setDlSymbol(next);
        triggerNotif("info", `Next: downloading ${next}…`);
        setTimeout(() => finalizeDownload(code), 600);
        return;
      }
      // ── Queue exhausted: reset counter ──
      batchDownloadCountRef.current = 0;
      // ── Single backtest auto-resume ──
      if (ref.pendingBacktest) {
        const pb = ref.pendingBacktest;
        const covers = pb.symbols.some(s => s.toUpperCase() === sym.toUpperCase()) && pb.interval.toUpperCase() === ref.dlInterval.toUpperCase();
        if (covers) {
          setTimeout(() => {
            setPendingBacktest(null);
            handleRunBacktest();
          }, 500);
        }
      }
      // ── Multi-asset auto-resume ──
      if (ref.pendingMultiAsset) {
        setTimeout(() => {
          setPendingMultiAsset(null);
          setMultiAssetRetrySignal(Date.now());
        }, 500);
      }
    } else {
      triggerNotif("error", result.error || `Download failed for ${sym}. Check the symbol spelling and try again.`);
    }
  }, [triggerNotif, fetchCoreData, handleRunBacktest]);

  const handlePreviewDataset = useCallback(async (symbol: string, interval: string) => {
    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewData(null);
    const result = await api.get(`/data/datasets/${encodeURIComponent(symbol)}/${encodeURIComponent(interval)}`);
    setPreviewLoading(false);
    if (result.ok && result.data) {
      setPreviewData(result.data);
      triggerNotif("success", `Loaded preview for ${symbol} (${interval})`);
    } else {
      setPreviewError(result.error || "Failed to load dataset preview.");
      triggerNotif("error", result.error || "Failed to load dataset preview.");
    }
  }, [triggerNotif]);

  const handleTotpConfirm = useCallback(() => {
    if (totpInput.length !== 6) { triggerNotif("error", "Invalid code. Please enter 6 digits."); return; }
    const code = totpInput;
    setIsTotpModalOpen(false); setTotpInput("");
    if (pendingAction === "AUTH") finalizeAuth(code);
    else if (pendingAction === "DOWNLOAD") finalizeDownload(code);
    setPendingAction(null);
  }, [totpInput, pendingAction, triggerNotif, finalizeAuth, finalizeDownload]);

  // ── OPTIMIZATION ──

  const handleRunOptimization = useCallback(async () => {
    const ref = stateRef.current;
    if (!ref.selectedStrategyId) { triggerNotif("info", "Select a strategy first."); return; }
    triggerNotif("info", "Starting Optimization sweep parameter sweep grid...");
    if (!ref.backendOnline) { triggerNotif("success", "Simulated parameter sweep complete!"); return; }
    const selectedStrategy = ref.strategies.find((s: any) => s.id === ref.selectedStrategyId);
    const symbol = selectedStrategy?.symbols?.[0] || "SBIN";
    const interval = selectedStrategy?.interval || "FIVE_MINUTE";
    const parseVals = (str: string) => str.split(",").map(s => Number(s.trim()));
    const gridObj = { [optParamName1]: parseVals(optParamVals1), [optParamName2]: parseVals(optParamVals2) };
    const result = await api.post("/backtest/optimize", {
      strategy_id: ref.selectedStrategyId, symbol, interval, start_date: ref.btStartDate, end_date: ref.btEndDate,
      param_grid_json: JSON.stringify(gridObj), initial_capital: ref.strategyCapital, trade_type: ref.btTradeType
    });
    if (result.ok && result.data) { setOptimizationGrid(result.data); triggerNotif("success", "Optimization grid calculation finished!"); }
    else { triggerNotif("error", `Optimization error: ${result.error || "Unknown error"}`); }
  }, [optParamName1, optParamVals1, optParamName2, optParamVals2, triggerNotif]);

  // ── DEPLOYMENT HANDLERS ──

  const handleCreateDeployment = useCallback(async () => {
    if (!depStrategyId || !depName.trim()) { triggerNotif("error", "Strategy and deployment name are required."); return; }
    if (!stateRef.current.backendOnline) {
      const mockId = `D-MOCK-${Math.floor(Math.random()*90000)+10000}`;
      setDeployments(prev => [...prev, { id: mockId, strategy_id: depStrategyId, name: depName, symbol: depSymbol || null, mode: depMode, status: "active", created_at: new Date().toISOString() }]);
      setDeploymentFormOpen(false); setDepName(""); setDepSymbol("");
      triggerNotif("success", "Deployment created (local mock).");
      return;
    }
    const result = await api.post("/deployments", { strategy_id: depStrategyId, name: depName, symbol: depSymbol || null, mode: depMode });
    if (result.ok && result.data) { triggerNotif("success", "Deployment created!"); fetchCoreData(); setDeploymentFormOpen(false); setDepName(""); setDepSymbol(""); }
    else { triggerNotif("error", `Failed to create deployment: ${result.error || "Unknown error"}`); }
  }, [depStrategyId, depName, depSymbol, depMode, triggerNotif, fetchCoreData]);

  const handleDeleteDeployment = useCallback(async (id: string) => {
    if (!stateRef.current.backendOnline) { setDeployments(prev => prev.filter(d => d.id !== id)); triggerNotif("success", "Deployment deleted (local)."); return; }
    const result = await api.delete(`/deployments/${id}`);
    if (result.ok) { triggerNotif("success", "Deployment deleted."); fetchCoreData(); }
    else { triggerNotif("error", `Failed to delete deployment: ${result.error || "Unknown error"}`); }
  }, [triggerNotif, fetchCoreData]);

  // ── CLEANUP HANDLERS ──

  const fetchCleanupStatus = useCallback(async () => {
    if (!stateRef.current.backendOnline) { triggerNotif("error", "Backend is offline. Cannot fetch cleanup status."); return; }
    const result = await api.get("/cleanup/status");
    if (result.ok && result.data) { setCleanupStatus(result.data); clearEndpointError("cleanup/status"); }
    else { setEndpointError("cleanup/status", result.error || "Failed to fetch cleanup status", fetchCleanupStatus); triggerNotif("error", `Cleanup status failed: ${result.error}`); }
  }, [triggerNotif, clearEndpointError, setEndpointError]);

  const handleRunCleanup = useCallback(async () => {
    if (!stateRef.current.backendOnline) { triggerNotif("error", "Backend is offline. Cannot run cleanup."); return; }
    setCleanupLoading(true); setCleanupResult(null);
    const result = await api.post("/cleanup/run", {
      target: cleanupTarget, symbol: cleanupSymbol || null, interval: cleanupInterval || null, run_id: null,
      strategy_id: cleanupStrategyId || null, older_than_days: cleanupOlderThan ? Number(cleanupOlderThan) : null, dry_run: cleanupDryRun,
    });
    if (result.ok && result.data) {
      setCleanupResult(result.data);
      if (cleanupDryRun) { triggerNotif("info", `Dry-run complete. Would free ${result.data.bytes_freed_human}.`); }
      else { triggerNotif("success", `Cleanup complete! Freed ${result.data.bytes_freed_human}.`); fetchCleanupStatus(); fetchCoreData(); }
      clearEndpointError("cleanup/run");
    } else {
      setEndpointError("cleanup/run", result.error || "Cleanup failed", handleRunCleanup);
      triggerNotif("error", `Cleanup failed: ${result.error || "Unknown error"}`);
    }
    setCleanupLoading(false);
  }, [cleanupTarget, cleanupSymbol, cleanupInterval, cleanupStrategyId, cleanupOlderThan, cleanupDryRun, triggerNotif, clearEndpointError, setEndpointError, fetchCleanupStatus, fetchCoreData]);

  const handleVacuumDB = useCallback(async () => {
    if (!stateRef.current.backendOnline) { triggerNotif("error", "Backend is offline. Cannot vacuum database."); return; }
    setCleanupLoading(true);
    const result = await api.post(`/cleanup/vacuum?dry_run=${cleanupDryRun}`, {});
    if (result.ok && result.data) {
      if (cleanupDryRun) { triggerNotif("info", `Dry-run: Would vacuum DB (${result.data.size_before_human}).`); }
      else { triggerNotif("success", `Vacuumed DB! Freed ${result.data.freed_human || "0 B"}.`); fetchCleanupStatus(); }
      clearEndpointError("cleanup/vacuum");
    } else {
      setEndpointError("cleanup/vacuum", result.error || "Vacuum failed", handleVacuumDB);
      triggerNotif("error", `Vacuum failed: ${result.error || "Unknown error"}`);
    }
    setCleanupLoading(false);
  }, [cleanupDryRun, triggerNotif, clearEndpointError, setEndpointError, fetchCleanupStatus]);

  return {
    // Navigation
    activeTab, setActiveTab,
    // Status
    backendOnline, smartapiConfigured, smartapiConnected,
    // TOTP
    isTotpModalOpen, setIsTotpModalOpen, totpInput, setTotpInput, pendingAction, setPendingAction, handleTotpConfirm,
    // Data
    datasets, strategies, backtestRuns, deployments,
    // Selected
    selectedStrategyId, setSelectedStrategyId, selectedDataset, setSelectedDataset, selectedRunId, setSelectedRunId,
    // Strategy Editor
    code, setCode, fileInputRef, uploadedFileName, setUploadedFileName,
    strategyName, setStrategyName, strategySymbols, setStrategySymbols, strategyInterval, setStrategyInterval,
    strategyCapital, setStrategyCapital, strategyMaxPos, setStrategyMaxPos,
    strategyRuntimeType, setStrategyRuntimeType, strategyEntrypoint, setStrategyEntrypoint,
    strategyParams, setStrategyParams, strategyRisk, setStrategyRisk,
    // Backtest Inputs
    btStartDate, setBtStartDate, btEndDate, setBtEndDate, btSlippage, setBtSlippage,
    btTradeType, setBtTradeType, btIsAutoMaxPos, setBtIsAutoMaxPos,
    btAutoMaxPosValue, setBtAutoMaxPosValue, btMaxPositionSize, setBtMaxPositionSize,
    // Replay
    backtestDetail, setBacktestDetail, replayEvents, setReplayEvents,
    currentStep, setCurrentStep, isPlaying, setIsPlaying, playbackSpeed, setPlaybackSpeed,
    // Chart toggles
    showEmaFast, setShowEmaFast, showEmaSlow, setShowEmaSlow, showBuyTrades, setShowBuyTrades, showSellTrades, setShowSellTrades,
    // Research / Capital / Optimization
    researchData, setResearchData, capitalData, setCapitalData, optimizationGrid, setOptimizationGrid,
    // Optimization inputs
    optParamName1, setOptParamName1, optParamVals1, setOptParamVals1,
    optParamName2, setOptParamName2, optParamVals2, setOptParamVals2,
    // Deployment
    deploymentFormOpen, setDeploymentFormOpen, depStrategyId, setDepStrategyId, depName, setDepName,
    depSymbol, setDepSymbol, depMode, setDepMode,
    // Cleanup
    cleanupStatus, setCleanupStatus, cleanupLoading, setCleanupLoading, cleanupDryRun, setCleanupDryRun,
    cleanupTarget, setCleanupTarget, cleanupSymbol, setCleanupSymbol, cleanupInterval, setCleanupInterval,
    cleanupOlderThan, setCleanupOlderThan, cleanupStrategyId, setCleanupStrategyId, cleanupResult, setCleanupResult,
    // Dataset download
    dlSymbol, setDlSymbol, dlInterval, setDlInterval, dlFromDate, setDlFromDate, dlToDate, setDlToDate, downloading, setDownloading,
    // Dataset preview
    previewData, setPreviewData, previewLoading, previewError, handlePreviewDataset,
    // Data coverage
    checkDataCoverage, pendingBacktest, setPendingBacktest,
    pendingMultiAsset, setPendingMultiAsset, multiAssetRetrySignal, setMultiAssetRetrySignal,
    setDownloadQueue,
    // Autocomplete
    suggestions, setSuggestions, showSuggestions, setShowSuggestions,
    strategySuggestions, setStrategySuggestions, showStrategySuggestions, setShowStrategySuggestions,
    // Notifications & errors
    notif, setNotif, apiErrors, setApiErrors, triggerNotif, setEndpointError, clearEndpointError,
    // Handlers
    handleFileUpload, handleSelectStrategy, handleSaveStrategy, handleNewStrategy,
    handleRunBacktest, handleSelectRun, loadBacktestReplay,
    triggerAuth, triggerDownload, finalizeAuth, finalizeDownload,
    handleRunOptimization, handleCreateDeployment, handleDeleteDeployment,
    fetchCleanupStatus, handleRunCleanup, handleVacuumDB,
    // Replay computed
    currentEvent, currentCandleMap, currentSymbol, currentPortfolio,
    activeCandles, activeTrades, positionCurveData,
    // Refetch
    fetchCoreData, checkBackendHealth, checkOllamaHealth,
  };
}

function calculateSimpleEMA(closes: number[], period: number): number {
  if (closes.length === 0) return 0;
  const k = 2 / (period + 1);
  let ema = closes[0];
  for (let i = 1; i < closes.length; i++) { ema = closes[i] * k + ema * (1 - k); }
  return ema;
}
