"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import dynamic from "next/dynamic";
import {
  LineChart, Play, Pause, SkipForward, SkipBack, Cpu, FileText, BarChart2,
  PieChart, Database, Code, Shield,
  Plus, PlayCircle, RefreshCw, Layers, CheckCircle2, AlertTriangle, AlertCircle,
  TrendingUp, Trash2, WifiOff, ServerCrash, RotateCcw,
} from "lucide-react";
import { api, apiFetch, formatApiError, type ApiResult } from "../lib/api-client";

// Dynamically import client-only libraries to prevent NextJS hydration / SSR errors
const LightweightChart = dynamic(() => import("../components/LightweightChart"), { ssr: false });
const PositionChart = dynamic(() => import("../components/PositionChart"), { ssr: false });
const PnLChart = dynamic(() => import("../components/PnLChart"), { ssr: false });
const ResearchLab = dynamic(() => import("../components/ResearchLab"), { ssr: false });

export default function Home() {
  // Navigation State
  const [activeTab, setActiveTab] = useState<string>("dashboard");

  // Server & SmartAPI Status
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [smartapiConfigured, setSmartapiConfigured] = useState<boolean>(false);
  const [smartapiConnected, setSmartapiConnected] = useState<boolean>(false);

  // Ollama Status — redesigned with grace period & cached checks
  const [ollamaState, setOllamaState] = useState<"unknown" | "online" | "offline" | "error">("unknown");
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [ollamaLastError, setOllamaLastError] = useState<string | null>(null);
  const ollamaFailCountRef = useRef(0);   // grace period counter
  const ollamaOnlineRef = useRef(false);  // mirror for grace logic

  // TOTP Popup State
  const [isTotpModalOpen, setIsTotpModalOpen] = useState<boolean>(false);
  const [totpInput, setTotpInput] = useState<string>("");
  const [pendingAction, setPendingAction] = useState<"AUTH" | "DOWNLOAD" | null>(null);

  // Data Collections
  const [datasets, setDatasets] = useState<any[]>([]);
  const [strategies, setStrategies] = useState<any[]>([]);
  const [backtestRuns, setBacktestRuns] = useState<any[]>([]);
  
  // Selected Objects
  const [selectedStrategyId, setSelectedStrategyId] = useState<string>("");
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [selectedRunId, setSelectedRunId] = useState<string>("");

  // Editor Code State
  const [code, setCode] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string>("");
  const [strategyRuntimeType, setStrategyRuntimeType] = useState<string>("legacy_on_bar");
  const [strategyEntrypoint, setStrategyEntrypoint] = useState<string | null>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.endsWith(".py")) {
      triggerNotif("error", "Only .py files are allowed.");
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      const content = String(ev.target?.result || "");
      setCode(content);
      setUploadedFileName(file.name);
      setSelectedStrategyId(""); // treat as unsaved/new
      triggerNotif("success", `Loaded ${file.name} (${content.length} chars)`);
    };
    reader.readAsText(file);
  };

  // Selected Backtest Details (Replay State)
  const [backtestDetail, setBacktestDetail] = useState<any>(null);
  const [replayEvents, setReplayEvents] = useState<any[]>([]);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(2); // speeds: 1, 2, 5, 10
  
  // Backtest Input Parameters
  const [initialCapital, setInitialCapital] = useState<number>(100000);
  const [slippagePct, setSlippagePct] = useState<number>(0.05);
  const [tradeType, setTradeType] = useState<string>("INTRADAY");
  const [isAutoMaxPos, setIsAutoMaxPos] = useState<boolean>(true);
  const [autoMaxPosValue, setAutoMaxPosValue] = useState<number>(0);
  const [maxPositionSize, setMaxPositionSize] = useState<number>(0);

  // Research, Capital, and Optimization Dashboards States
  const [researchData, setResearchData] = useState<any>(null);
  const [capitalData, setCapitalData] = useState<any>(null);
  const [optimizationGrid, setOptimizationGrid] = useState<any>(null);
  
  // Chart indicator toggles
  const [showEmaFast, setShowEmaFast] = useState<boolean>(true);
  const [showEmaSlow, setShowEmaSlow] = useState<boolean>(true);
  const [showBuyTrades, setShowBuyTrades] = useState<boolean>(true);
  const [showSellTrades, setShowSellTrades] = useState<boolean>(true);
  
  // Multi-Asset Backtest State
  const [multiSymbols, setMultiSymbols] = useState<string>("SBIN");
  const [multiInterval, setMultiInterval] = useState<string>("ONE_MINUTE");
  const [multiFromDate, setMultiFromDate] = useState<string>("2026-06-01");
  const [multiToDate, setMultiToDate] = useState<string>("2026-06-07");
  const [multiStrategyId, setMultiStrategyId] = useState<string>("");
  const [isBacktestModalOpen, setIsBacktestModalOpen] = useState<boolean>(false);
  const [modalCapital, setModalCapital] = useState<number>(100000);
  const [modalSlippage, setModalSlippage] = useState<number>(0.05);
  const [modalTradeType, setModalTradeType] = useState<string>("INTRADAY");
  const [modalMaxPos, setModalMaxPos] = useState<number>(0);
  const [modalAutoMaxPos, setModalAutoMaxPos] = useState<boolean>(true);
  
  // Multi-Asset Replay State (Prosperity-style)
  const [multiReplayEvents, setMultiReplayEvents] = useState<any[]>([]);
  const [multiCurrentStep, setMultiCurrentStep] = useState<number>(0);
  const [multiIsPlaying, setMultiIsPlaying] = useState<boolean>(false);
  const [multiPlaybackSpeed, setMultiPlaybackSpeed] = useState<number>(2);
  const [multiSelectedSymbol, setMultiSelectedSymbol] = useState<string>("");
  const [multiBacktestDetail, setMultiBacktestDetail] = useState<any>(null);
  const [multiRunId, setMultiRunId] = useState<string>("");
  
  // Optimization Inputs
  const [optParamName1, setOptParamName1] = useState<string>("ema_fast");
  const [optParamVals1, setOptParamVals1] = useState<string>("5, 9, 15");
  const [optParamName2, setOptParamName2] = useState<string>("ema_slow");
  const [optParamVals2, setOptParamVals2] = useState<string>("20, 30, 50");

  // Cleanup State
  const [cleanupStatus, setCleanupStatus] = useState<any>(null);
  const [cleanupLoading, setCleanupLoading] = useState<boolean>(false);
  const [cleanupDryRun, setCleanupDryRun] = useState<boolean>(true);
  const [cleanupTarget, setCleanupTarget] = useState<string>("logs");
  const [cleanupSymbol, setCleanupSymbol] = useState<string>("");
  const [cleanupInterval, setCleanupInterval] = useState<string>("");
  const [cleanupOlderThan, setCleanupOlderThan] = useState<number | "">("");
  const [cleanupStrategyId, setCleanupStrategyId] = useState<string>("");
  const [cleanupResult, setCleanupResult] = useState<any>(null);
  const [dlSymbol, setDlSymbol] = useState<string>("SBIN");
  const [dlInterval, setDlInterval] = useState<string>("ONE_MINUTE");
  const [dlFromDate, setDlFromDate] = useState<string>("2026-06-01");
  const [dlToDate, setDlToDate] = useState<string>("2026-06-07");
  const [downloading, setDownloading] = useState<boolean>(false);

  // Autocomplete suggestions
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState<boolean>(false);


  // Status Alerts
  const [notif, setNotif] = useState<{ type: "success" | "error" | "info"; msg: string } | null>(null);

  // Per-endpoint error tracking for retry UI
  const [apiErrors, setApiErrors] = useState<Record<string, { error: string; retry: () => void }>>({});

  const setEndpointError = (endpoint: string, error: string | null, retry?: () => void) => {
    setApiErrors(prev => {
      const next = { ...prev };
      if (error === null) {
        delete next[endpoint];
      } else {
        next[endpoint] = { error, retry: retry || (() => {}) };
      }
      return next;
    });
  };

  const clearEndpointError = (endpoint: string) => {
    setEndpointError(endpoint, null);
  };

  const handleApiResult = <T,>(
    endpoint: string,
    result: ApiResult<T>,
    onSuccess: (data: T) => void,
    retryFn: () => void,
    context?: string
  ) => {
    if (result.ok && result.data) {
      clearEndpointError(endpoint);
      onSuccess(result.data);
    } else if (!result.ok) {
      const msg = formatApiError(result, context);
      setEndpointError(endpoint, msg, retryFn);
      triggerNotif("error", msg);
    }
  };

  // --- CONNECTIVITY & FETCHERS ---

  useEffect(() => {
    checkBackendHealth();
    // Periodically check health
    const interval = setInterval(() => {
      checkBackendHealth();
      checkOllamaHealth();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Fetch symbol suggestions with debounce
  useEffect(() => {
    if (!dlSymbol || dlSymbol.length < 2) {
      setSuggestions([]);
      return;
    }
    if (!backendOnline) return;

    const delayDebounceFn = setTimeout(() => {
      api.get(`/data/symbols/search?q=${encodeURIComponent(dlSymbol)}`)
        .then(result => {
          if (result.ok && result.data) {
            setSuggestions(result.data);
          } else {
            setSuggestions([]);
          }
        })
        .catch(() => setSuggestions([]));
    }, 250);

    return () => clearTimeout(delayDebounceFn);
  }, [dlSymbol, backendOnline]);

  const triggerNotif = (type: "success" | "error" | "info", msg: string) => {
    setNotif({ type, msg });
    setTimeout(() => setNotif(null), 5000);
  };

  const checkBackendHealth = async () => {
    const result = await api.get("/strategies", { timeout: 5000 });
    if (result.ok) {
      setBackendOnline(true);
      clearEndpointError("health");
      fetchCoreData();
    } else {
      setBackendOnline(false);
      if (result.isNetworkError) {
        setEndpointError("health", "Backend is offline. Start the FastAPI server.", checkBackendHealth);
      }
    }
  };

  const checkOllamaHealth = async () => {
    if (!backendOnline) {
      setOllamaState("offline");
      ollamaOnlineRef.current = false;
      return;
    }
    // Use /forge/status — fast cached endpoint, never blocks on network I/O
    const result = await api.get("/forge/status", { timeout: 5000 });
    if (result.ok && result.data) {
      const { state, models, last_error, stale } = result.data;
      setOllamaModels(models || []);
      setOllamaLastError(last_error || null);

      if (state === "online") {
        ollamaFailCountRef.current = 0;
        ollamaOnlineRef.current = true;
        setOllamaState("online");
        clearEndpointError("ollama/status");
      } else {
        // Grace period: require 2 consecutive failures before marking offline
        ollamaFailCountRef.current += 1;
        if (ollamaFailCountRef.current >= 2) {
          ollamaOnlineRef.current = false;
          setOllamaState(state === "error" ? "error" : "offline");
          setEndpointError(
            "ollama/status",
            last_error || "Ollama is unreachable. Start it with: ollama serve",
            checkOllamaHealth
          );
        }
        // If only 1 failure, keep previous state (don't flicker)
      }
    } else {
      ollamaFailCountRef.current += 1;
      if (ollamaFailCountRef.current >= 2) {
        ollamaOnlineRef.current = false;
        setOllamaState("offline");
        setEndpointError("ollama/status", result.error || "Ollama status check failed.", checkOllamaHealth);
      }
    }
  };

  const setIfChanged = <T,>(setter: React.Dispatch<React.SetStateAction<T>>, current: T, next: T) => {
    if (JSON.stringify(current) !== JSON.stringify(next)) {
      setter(next);
    }
  };

  const fetchCoreData = async () => {
    // Fetch all core data in parallel with safe error handling
    const [stratRes, catRes, runsRes, sapiRes] = await Promise.all([
      api.get("/strategies"),
      api.get("/data/datasets"),
      api.get("/backtest/results"),
      api.get("/auth/smartapi/status"),
    ]);

    handleApiResult("strategies", stratRes, (data) => setIfChanged(setStrategies, strategies, data), fetchCoreData, "Strategies");
    handleApiResult("datasets", catRes, (data) => setIfChanged(setDatasets, datasets, Object.values(data || {})), fetchCoreData, "Datasets");
    handleApiResult("backtest/results", runsRes, (data) => setIfChanged(setBacktestRuns, backtestRuns, data || []), fetchCoreData, "Backtest runs");
    
    if (sapiRes.ok && sapiRes.data) {
      clearEndpointError("smartapi/status");
      setSmartapiConfigured(sapiRes.data.configured);
      setSmartapiConnected(sapiRes.data.connected);
    } else if (!sapiRes.ok) {
      setEndpointError("smartapi/status", formatApiError(sapiRes, "SmartAPI status"), fetchCoreData);
    }
  };

  // --- LOCAL FALLBACK ENGINE (IF BACKEND OFFLINE) ---

  const runFrontendSimulation = () => {
    triggerNotif("info", "Backend offline. Executing client-side simulated backtest...");
    
    // 1. Generate local dummy candle dataset
    const numBars = 100;
    const mockCandles: any[] = [];
    let price = 500.0;
    const baseDate = new Date();
    
    for (let i = 0; i < numBars; i++) {
      const barTime = new Date(baseDate.getTime() + i * 60000);
      const ret = (Math.random() - 0.48) * 4.0; // slight bullish bias
      const o = price;
      const c = price + ret;
      const h = Math.max(o, c) + Math.random() * 1.5;
      const l = Math.min(o, c) - Math.random() * 1.5;
      mockCandles.push({
        time: barTime.toISOString().replace("T", " ").slice(0, 19),
        open: Number(o.toFixed(2)),
        high: Number(h.toFixed(2)),
        low: Number(l.toFixed(2)),
        close: Number(c.toFixed(2)),
        volume: Math.floor(Math.random() * 5000) + 100
      });
      price = c;
    }

    // 2. Run simulation logic
    const trades: any[] = [];
    const equityCurve: any[] = [];
    const events: any[] = [];
    
    let cash = initialCapital;
    let positionQty = 0;
    let avgPrice = 0.0;
    let unrealized = 0.0;
    let realized = 0.0;
    let fees = 0.0;
    
    // Sliding window for EMAs
    for (let idx = 0; idx < numBars; idx++) {
      const currentCandle = mockCandles[idx];
      const slice = mockCandles.slice(0, idx + 1);
      
      // Calculate EMA values
      const closes = slice.map(x => x.close);
      const ema9 = calculateSimpleEMA(closes, 9);
      const ema21 = calculateSimpleEMA(closes, 21);
      
      const prevEma9 = idx > 0 ? calculateSimpleEMA(closes.slice(0, -1), 9) : ema9;
      const prevEma21 = idx > 0 ? calculateSimpleEMA(closes.slice(0, -1), 21) : ema21;

      const symbol = "MOCK-SBIN";
      const ts = currentCandle.time;

      const orderRequests: any[] = [];
      const filledTrades: any[] = [];

      // Trade execution matching
      if (idx >= 21) {
        if (prevEma9 <= prevEma21 && ema9 > ema21 && positionQty <= 0) {
          // BUY Signal
          const orderQty = positionQty < 0 ? 20 : 10;
          const buyPrice = currentCandle.close * (1 + slippagePct / 100);
          const fee = 20.0 + (buyPrice * orderQty * 0.0003); // brokerage + tax approx
          
          fees += fee;
          cash -= fee;
          
          if (positionQty < 0) {
            // Covering short
            const profit = (avgPrice - buyPrice) * 10;
            realized += profit;
            cash += (avgPrice * 10) + profit; // restore margin + profit
          }
          
          positionQty += orderQty;
          avgPrice = buyPrice;
          
          const tradeId = `T-MOCK-${Math.floor(Math.random()*90000)+10000}`;
          const newTrade = {
            id: tradeId,
            order_id: `O-MOCK-${idx}`,
            timestamp: ts,
            symbol,
            direction: "BUY",
            price: buyPrice,
            qty: orderQty,
            total_charges: fee
          };
          
          trades.push(newTrade);
          filledTrades.push(newTrade);
          orderRequests.push({ symbol, direction: "BUY", type: "MARKET", price: 0.0, qty: orderQty });
        } else if (prevEma9 >= prevEma21 && ema9 < ema21 && positionQty >= 0) {
          // SELL Signal
          const orderQty = positionQty > 0 ? 20 : 10;
          const sellPrice = currentCandle.close * (1 - slippagePct / 100);
          const fee = 20.0 + (sellPrice * orderQty * 0.0003);
          
          fees += fee;
          cash -= fee;
          
          if (positionQty > 0) {
            // Exiting long
            const profit = (sellPrice - avgPrice) * 10;
            realized += profit;
            cash += (avgPrice * 10) + profit;
          }
          
          positionQty -= orderQty;
          avgPrice = sellPrice;

          const tradeId = `T-MOCK-${Math.floor(Math.random()*90000)+10000}`;
          const newTrade = {
            id: tradeId,
            order_id: `O-MOCK-${idx}`,
            timestamp: ts,
            symbol,
            direction: "SELL",
            price: sellPrice,
            qty: orderQty,
            total_charges: fee
          };
          
          trades.push(newTrade);
          filledTrades.push(newTrade);
          orderRequests.push({ symbol, direction: "SELL", type: "MARKET", price: 0.0, qty: orderQty });
        }
      }

      unrealized = positionQty * (currentCandle.close - avgPrice);
      const equity = cash + unrealized;
      const marginUsed = Math.abs(positionQty) * currentCandle.close * 0.20; // 5x leverage
      
      equityCurve.push({
        time: ts,
        equity,
        cash,
        unrealized_pnl: unrealized,
        margin_used: marginUsed,
        fees
      });

      events.push({
        step: idx,
        timestamp: ts,
        candle: { [symbol]: currentCandle },
        orders_submitted: orderRequests,
        orders_filled: filledTrades,
        portfolio: {
          cash,
          margin_used: marginUsed,
          margin_free: equity - marginUsed,
          equity,
          unrealized_pnl: unrealized,
          total_fees: fees,
          total_pnl: realized + unrealized
        },
        log_messages: orderRequests.length > 0 ? [`[Sim Engine] Technical EMA Crossover triggered trade order!`] : []
      });
    }

    // Assemble final output
    const mockId = `B-MOCK-${Math.floor(Math.random()*90000)+10000}`;
    const resultObj = {
      run_id: mockId,
      trades,
      equity_curve: equityCurve,
      final_portfolio: equityCurve[equityCurve.length - 1],
      log_file_path: ""
    };

    setBacktestDetail({
      id: mockId,
      strategy_name: "EMA Crossover Template (Simulated)",
      symbol: "MOCK-SBIN",
      interval: "ONE_MINUTE",
      start_time: mockCandles[0].time,
      end_time: mockCandles[mockCandles.length - 1].time,
      initial_capital: initialCapital,
      final_equity: resultObj.final_portfolio.equity,
      total_pnl: resultObj.final_portfolio.equity - initialCapital,
      cagr: 0.154,
      sharpe_ratio: 1.84,
      sortino_ratio: 2.12,
      max_drawdown: 0.042,
      win_rate: 0.60,
      max_position_size: maxPositionSize,
      profit_factor: 1.74,
      total_fees: fees,
      metrics: {
        cost_breakdown: {
          brokerage: fees * 0.4,
          stt: fees * 0.3,
          exchange_charges: fees * 0.1,
          gst: fees * 0.1,
          sebi_charges: fees * 0.05,
          stamp_duty: fees * 0.05,
          total_fees: fees
        },
        trade_metrics: {
          total_trades: trades.length,
          win_trades: Math.floor(trades.length * 0.6),
          loss_trades: trades.length - Math.floor(trades.length * 0.6),
          avg_win: 450.0,
          avg_loss: -250.0,
          gross_profit: 450.0 * Math.floor(trades.length * 0.6),
          gross_loss: 250.0 * (trades.length - Math.floor(trades.length * 0.6))
        }
      }
    });

    setReplayEvents(events);
    setCurrentStep(0);
    setBacktestRuns(prev => [
      {
        id: mockId,
        strategy_name: "EMA Crossover (Simulated)",
        symbol: "MOCK-SBIN",
        interval: "ONE_MINUTE",
        start_time: mockCandles[0].time,
        end_time: mockCandles[mockCandles.length - 1].time,
        total_pnl: resultObj.final_portfolio.equity - initialCapital,
        cagr: 0.154,
        sharpe_ratio: 1.84,
        max_position_size: maxPositionSize,
        max_drawdown: 0.042,
        created_at: new Date().toISOString()
      },
      ...prev
    ]);
    setSelectedRunId(mockId);
    
    // Set research regimes mock
    setResearchData({
      regime_attribution: {
        TRENDING_BULLISH: { trade_count: 5, total_pnl: 1200.0, avg_pnl: 240.0, win_rate: 0.8 },
        TRENDING_BEARISH: { trade_count: 3, total_pnl: 450.0, avg_pnl: 150.0, win_rate: 0.66 },
        VOLATILE_RANGING: { trade_count: 4, total_pnl: -300.0, avg_pnl: -75.0, win_rate: 0.25 },
        QUIET_RANGING: { trade_count: 2, total_pnl: 100.0, avg_pnl: 50.0, win_rate: 0.5 },
        GAP_DAY: { trade_count: 1, total_pnl: -50.0, avg_pnl: -50.0, win_rate: 0.0 }
      },
      market_regime_distribution: {
        TRENDING_BULLISH: 0.35,
        TRENDING_BEARISH: 0.20,
        VOLATILE_RANGING: 0.15,
        QUIET_RANGING: 0.25,
        GAP_DAY: 0.05
      }
    });

    // Set capital scaling mock
    setCapitalData({
      minimum_viable_capital: 35000.0,
      optimal_capital_allocation: 50000.0,
      scaling_curve: [
        { capital: 25000, cagr: 0.18, sharpe: 1.6, margin_call: true },
        { capital: 50000, cagr: 0.16, sharpe: 1.9, margin_call: false },
        { capital: 100000, cagr: 0.15, sharpe: 1.8, margin_call: false },
        { capital: 250000, cagr: 0.12, sharpe: 1.5, margin_call: false },
        { capital: 500000, cagr: 0.08, sharpe: 1.1, margin_call: false },
        { capital: 1000000, cagr: 0.04, sharpe: 0.6, margin_call: false }
      ]
    });

    // Set parameter search grid mock
    setOptimizationGrid({
      results: [
        { parameters: { ema_fast: 5, ema_slow: 20 }, cagr: 0.12, sharpe: 1.3, max_drawdown: 0.08, status: "SUCCESS" },
        { parameters: { ema_fast: 9, ema_slow: 21 }, cagr: 0.15, sharpe: 1.8, max_drawdown: 0.04, status: "SUCCESS" },
        { parameters: { ema_fast: 15, ema_slow: 30 }, cagr: 0.09, sharpe: 1.1, max_drawdown: 0.06, status: "SUCCESS" },
        { parameters: { ema_fast: 9, ema_slow: 50 }, cagr: 0.05, sharpe: 0.7, max_drawdown: 0.05, status: "SUCCESS" }
      ],
      best_result: { parameters: { ema_fast: 9, ema_slow: 21 }, cagr: 0.15, sharpe: 1.8, max_drawdown: 0.04 },
      parameter_names: ["ema_fast", "ema_slow"],
      total_runs: 4
    });

    setActiveTab("studio");
    triggerNotif("success", "Client simulated run generated! Loaded in Replay Studio.");
  };

  const calculateSimpleEMA = (closes: number[], period: number): number => {
    if (closes.length === 0) return 0;
    const k = 2 / (period + 1);
    let ema = closes[0];
    for (let i = 1; i < closes.length; i++) {
      ema = closes[i] * k + ema * (1 - k);
    }
    return ema;
  };

  // --- API ROUTE DISPATCHERS (IF ONLINE) ---

  const triggerAuth = (e: React.FormEvent) => {
    e.preventDefault();
    if (!backendOnline) {
      triggerNotif("error", "Backend is offline. Start the server to authenticate SmartAPI.");
      return;
    }
    setPendingAction("AUTH");
    setIsTotpModalOpen(true);
  };

  const finalizeAuth = async (code: string) => {
    const result = await api.post("/auth/smartapi/connect", { totp: code });
    if (result.ok && result.data?.connection_success) {
      setSmartapiConfigured(true);
      setSmartapiConnected(true);
      triggerNotif("success", "SmartAPI Authenticated & Connected!");
      fetchCoreData();
    } else {
      triggerNotif("error", `SmartAPI connection failed: ${result.error || result.data?.message || "Bad keys"}`);
    }
  };

  const triggerDownload = (e: React.FormEvent) => {
    e.preventDefault();
    setPendingAction("DOWNLOAD");
    setIsTotpModalOpen(true);
  };

  const finalizeDownload = async (code: string) => {
    setDownloading(true);
    triggerNotif("info", `Downloading historical candles for ${dlSymbol}...`);

    if (!backendOnline) {
      // Local mock generate
      setTimeout(() => {
        setDownloading(false);
        const mockCatalogItem = {
          symbol: dlSymbol.toUpperCase(),
          interval: dlInterval.toUpperCase(),
          start_date: dlFromDate + " 09:15:00",
          end_date: dlToDate + " 15:30:00",
          records_count: 2250,
          updated_at: new Date().toISOString()
        };
        setDatasets(prev => [mockCatalogItem, ...prev]);
        setSelectedDataset(`${dlSymbol.toUpperCase()}_${dlInterval.toUpperCase()}`);
        triggerNotif("success", `Dataset for ${dlSymbol} generated locally!`);
      }, 2000);
      return;
    }

    const result = await api.post("/data/download", {
      symbol: dlSymbol,
      interval: dlInterval,
      from_date: dlFromDate + " 09:15",
      to_date: dlToDate + " 15:30",
      totp: code
    });

    setDownloading(false);
    if (result.ok) {
      triggerNotif("success", "Dataset downloaded and cataloged in Parquet!");
      fetchCoreData();
    } else {
      triggerNotif("error", `Download failed: ${result.error || "Server error"}`);
    }
  };

  const handleTotpConfirm = () => {
    if (totpInput.length !== 6) {
      triggerNotif("error", "Invalid code. Please enter 6 digits.");
      return;
    }
    const code = totpInput;
    setIsTotpModalOpen(false);
    setTotpInput("");
    
    if (pendingAction === "AUTH") finalizeAuth(code);
    else if (pendingAction === "DOWNLOAD") finalizeDownload(code);
    setPendingAction(null);
  };

  const handleSaveStrategy = async () => {
    const liveCode = code;
    
    if (!selectedStrategyId) {
      // Create new
      const name = prompt("Enter Strategy Name:", "My Trading Strategy");
      if (!name) return;
      
      if (!backendOnline) {
        const mockId = `S-MOCK-${Math.floor(Math.random()*90000)+10000}`;
        setStrategies(prev => [...prev, { id: mockId, name, description: "Local template", version: 1, updated_at: new Date() }]);
        setSelectedStrategyId(mockId);
        triggerNotif("success", "Strategy template saved to memory!");
        return;
      }
      
      const result = await api.post("/strategies", { 
        name, 
        description: "Editor strategy", 
        code: liveCode,
        runtime_type: strategyRuntimeType,
        entrypoint: strategyEntrypoint
      });
      if (result.ok && result.data) {
        triggerNotif("success", "Strategy created in DB!");
        fetchCoreData();
        setSelectedStrategyId(result.data.id);
      } else {
        triggerNotif("error", `Failed to save strategy: ${result.error || "Unknown error"}`);
      }
    } else {
      // Update existing
      if (!backendOnline) {
        triggerNotif("success", "Local strategy updated!");
        return;
      }

      // Find existing metadata
      const stratMeta = strategies.find(s => s.id === selectedStrategyId);
      const result = await api.put(`/strategies/${selectedStrategyId}`, {
        name: stratMeta?.name || "Strategy",
        runtime_type: strategyRuntimeType,
        entrypoint: strategyEntrypoint,
        description: stratMeta?.description || "",
        code: liveCode
      });
      if (result.ok) {
        triggerNotif("success", "Strategy code updated successfully!");
        fetchCoreData();
      } else {
        triggerNotif("error", `Failed to update strategy: ${result.error || "Unknown error"}`);
      }
    }
  };

  const handleRunBacktest = async () => {
    if (!selectedStrategyId) {
      triggerNotif("info", "Please select or save a strategy first.");
      return;
    }
    if (!selectedDataset) {
      triggerNotif("info", "Please select a Parquet dataset first.");
      return;
    }
    
    // Get the selected strategy object to retrieve its runtime_type
    const selectedStrategy = strategies.find(s => s.id === selectedStrategyId);
    if (!selectedStrategy) {
      triggerNotif("error", "Selected strategy not found.");
      return;
    }

    if (!backendOnline) {
      runFrontendSimulation();
      return;
    }

    const parts = selectedDataset.split("_");
    const symbol = parts[0];
    const interval = parts.slice(1).join("_");
    triggerNotif("info", `Initiating backtest on ${symbol}...`);

    // Find start and end date of dataset to use full range
    const catalogItem = datasets.find(d => `${d.symbol}_${d.interval}` === selectedDataset);
    const extractDate = (dt: string) => {
      if (!dt) return "2026-06-01";
      // Handle both "2026-06-01 09:15:00" and "2026-06-01T09:15:00+05:30"
      return dt.split("T")[0].split(" ")[0];
    };
    const start_date = catalogItem ? extractDate(catalogItem.start_date) : "2026-06-01";
    const end_date = catalogItem ? extractDate(catalogItem.end_date) : "2026-06-07";

    const result = await api.post("/backtest/run", {
      strategy_id: selectedStrategyId,
      symbols: [symbol],
      interval,
      start_date,
      end_date,
      initial_capital: initialCapital,
      slippage_pct: slippagePct / 100.0,
      trade_type: tradeType,
      max_position_size: isAutoMaxPos ? autoMaxPosValue : maxPositionSize,
      runtime_type: selectedStrategy.runtime_type || "legacy_on_bar",
      auto_download: true
    });

    if (result.ok && result.data) {
      triggerNotif("success", "Backtest run completed successfully!");
      setSelectedRunId(result.data.run_id);
      fetchCoreData();
      loadBacktestReplay(result.data.run_id);
      setActiveTab("studio");
    } else {
      triggerNotif("error", `Backtest failed: ${result.error || "Engine error"}`);
    }
  };

  const loadMultiAssetReplay = async (runId: string) => {
    if (!backendOnline) return;

    const detRes = await api.get(`/backtest/results/${runId}`);
    if (detRes.ok && detRes.data) {
      setMultiBacktestDetail(detRes.data);
      clearEndpointError(`backtest/results/${runId}`);
    } else {
      setEndpointError(`backtest/results/${runId}`, detRes.error || "Failed to load backtest details", () => loadMultiAssetReplay(runId));
      triggerNotif("error", `Replay details unavailable: ${detRes.error}`);
    }

    const logsRes = await api.get(`/backtest/logs/${runId}`);
    if (logsRes.ok && logsRes.data) {
      setMultiReplayEvents(logsRes.data);
      setMultiCurrentStep(0);
      setMultiIsPlaying(false);
      setMultiSelectedSymbol("");
      clearEndpointError(`backtest/logs/${runId}`);
    } else {
      setEndpointError(`backtest/logs/${runId}`, logsRes.error || "Failed to load replay logs", () => loadMultiAssetReplay(runId));
      triggerNotif("error", `Replay logs unavailable: ${logsRes.error}`);
    }
  };

  const loadBacktestReplay = async (runId: string) => {
    if (!backendOnline) return;

    // 1. Fetch Result Details
    const detRes = await api.get(`/backtest/results/${runId}`);
    if (detRes.ok && detRes.data) {
      setBacktestDetail(detRes.data);
      clearEndpointError(`backtest/results/${runId}`);
    } else {
      setEndpointError(`backtest/results/${runId}`, detRes.error || "Failed to load backtest details", () => loadBacktestReplay(runId));
      triggerNotif("error", `Replay details unavailable: ${detRes.error}`);
    }

    // 2. Fetch Replay Logs
    const logsRes = await api.get(`/backtest/logs/${runId}`);
    if (logsRes.ok && logsRes.data) {
      setReplayEvents(logsRes.data);
      setCurrentStep(0);
      clearEndpointError(`backtest/logs/${runId}`);
    } else {
      setEndpointError(`backtest/logs/${runId}`, logsRes.error || "Failed to load replay logs", () => loadBacktestReplay(runId));
      triggerNotif("error", `Replay logs unavailable: ${logsRes.error}`);
    }

    // 3. Fetch Research Lab regimes
    const regRes = await api.get(`/research/regimes/${runId}`);
    if (regRes.ok && regRes.data) {
      setResearchData(regRes.data);
      clearEndpointError(`research/regimes/${runId}`);
    } else if (regRes.status === 404) {
      // Missing parquet is expected if data was deleted — don't spam errors
      setResearchData(null);
    } else {
      setEndpointError(`research/regimes/${runId}`, regRes.error || "Research data unavailable", () => loadBacktestReplay(runId));
    }

    // 4. Fetch Capital requirements scaling
    const capRes = await api.get(`/capital/analysis/${runId}`);
    if (capRes.ok && capRes.data) {
      setCapitalData(capRes.data);
      clearEndpointError(`capital/analysis/${runId}`);
    } else if (capRes.status === 404) {
      // Missing parquet is expected if data was deleted
      setCapitalData(null);
    } else {
      setEndpointError(`capital/analysis/${runId}`, capRes.error || "Capital analysis unavailable", () => loadBacktestReplay(runId));
    }
  };

  const handleRunOptimization = async () => {
    if (!selectedStrategyId || !selectedDataset) {
      triggerNotif("info", "Select strategy and dataset first.");
      return;
    }

    triggerNotif("info", "Starting Optimization sweep parameter sweep grid...");

    if (!backendOnline) {
      triggerNotif("success", "Simulated parameter sweep complete!");
      return;
    }

    const parts = selectedDataset.split("_");
    const symbol = parts[0];
    const interval = parts.slice(1).join("_");
    const catalogItem = datasets.find(d => `${d.symbol}_${d.interval}` === selectedDataset);
    const start_date = catalogItem ? catalogItem.start_date.split(" ")[0] : "2026-06-01";
    const end_date = catalogItem ? catalogItem.end_date.split(" ")[0] : "2026-06-07";

    const parseVals = (str: string) => str.split(",").map(s => Number(s.trim()));
    const gridObj = {
      [optParamName1]: parseVals(optParamVals1),
      [optParamName2]: parseVals(optParamVals2)
    };

    const result = await api.post("/backtest/optimize", {
      strategy_id: selectedStrategyId,
      symbol,
      interval,
      start_date,
      end_date,
      param_grid_json: JSON.stringify(gridObj),
      initial_capital: initialCapital,
      trade_type: tradeType
    });

    if (result.ok && result.data) {
      setOptimizationGrid(result.data);
      triggerNotif("success", "Optimization grid calculation finished!");
    } else {
      triggerNotif("error", `Optimization error: ${result.error || "Unknown error"}`);
    }
  };

  // --- CLEANUP API HANDLERS ---

  const fetchCleanupStatus = async () => {
    if (!backendOnline) {
      triggerNotif("error", "Backend is offline. Cannot fetch cleanup status.");
      return;
    }
    const result = await api.get("/cleanup/status");
    if (result.ok && result.data) {
      setCleanupStatus(result.data);
      clearEndpointError("cleanup/status");
    } else {
      setEndpointError("cleanup/status", result.error || "Failed to fetch cleanup status", fetchCleanupStatus);
      triggerNotif("error", `Cleanup status failed: ${result.error}`);
    }
  };

  const handleRunCleanup = async () => {
    if (!backendOnline) {
      triggerNotif("error", "Backend is offline. Cannot run cleanup.");
      return;
    }
    setCleanupLoading(true);
    setCleanupResult(null);
    const result = await api.post("/cleanup/run", {
      target: cleanupTarget,
      symbol: cleanupSymbol || null,
      interval: cleanupInterval || null,
      run_id: null,
      strategy_id: cleanupStrategyId || null,
      older_than_days: cleanupOlderThan ? Number(cleanupOlderThan) : null,
      dry_run: cleanupDryRun,
    });
    if (result.ok && result.data) {
      setCleanupResult(result.data);
      if (cleanupDryRun) {
        triggerNotif("info", `Dry-run complete. Would free ${result.data.bytes_freed_human}.`);
      } else {
        triggerNotif("success", `Cleanup complete! Freed ${result.data.bytes_freed_human}.`);
        fetchCleanupStatus();
        fetchCoreData();
      }
      clearEndpointError("cleanup/run");
    } else {
      setEndpointError("cleanup/run", result.error || "Cleanup failed", handleRunCleanup);
      triggerNotif("error", `Cleanup failed: ${result.error || "Unknown error"}`);
    }
    setCleanupLoading(false);
  };

  const handleVacuumDB = async () => {
    if (!backendOnline) {
      triggerNotif("error", "Backend is offline. Cannot vacuum database.");
      return;
    }
    setCleanupLoading(true);
    const result = await api.post(`/cleanup/vacuum?dry_run=${cleanupDryRun}`, {});
    if (result.ok && result.data) {
      if (cleanupDryRun) {
        triggerNotif("info", `Dry-run: Would vacuum DB (${result.data.size_before_human}).`);
      } else {
        triggerNotif("success", `Vacuumed DB! Freed ${result.data.freed_human || "0 B"}.`);
        fetchCleanupStatus();
      }
      clearEndpointError("cleanup/vacuum");
    } else {
      setEndpointError("cleanup/vacuum", result.error || "Vacuum failed", handleVacuumDB);
      triggerNotif("error", `Vacuum failed: ${result.error || "Unknown error"}`);
    }
    setCleanupLoading(false);
  };

  // Select a past backtest run from the lists
  const handleSelectRun = (runId: string) => {
    setSelectedRunId(runId);
    loadBacktestReplay(runId);
    triggerNotif("success", `Loaded run ${runId} metadata.`);
  };

  // Select a strategy from list to load into editor
  const handleSelectStrategy = async (id: string) => {
    setSelectedStrategyId(id);
    if (!backendOnline) {
      triggerNotif("info", "Loaded strategy template in memory.");
      return;
    }

    const result = await api.get(`/strategies/${id}`);
    if (result.ok && result.data) {
      const newCode = result.data.code || "";
      setCode(newCode);
      setUploadedFileName(`${result.data.name}.py`);
      setStrategyRuntimeType(result.data.runtime_type || "legacy_on_bar");
      setStrategyEntrypoint(result.data.entrypoint || null);
      triggerNotif("success", `Loaded strategy: ${result.data.name}`);
      clearEndpointError(`strategies/${id}`);
    } else {
      setEndpointError(`strategies/${id}`, result.error || "Failed to load strategy", () => handleSelectStrategy(id));
      triggerNotif("error", `Failed to fetch strategy: ${result.error}`);
    }
  };

  // Sync maxPositionSize when Auto toggle changes or auto value updates
  useEffect(() => {
    if (isAutoMaxPos && autoMaxPosValue > 0) {
      setMaxPositionSize(autoMaxPosValue);
    }
  }, [isAutoMaxPos, autoMaxPosValue]);

  // --- REPLAY CONTROLS ---

  useEffect(() => {
    if (!isPlaying || replayEvents.length === 0) return;

    const intervalVal = setInterval(() => {
      setCurrentStep(prev => {
        if (prev >= replayEvents.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 1000 / playbackSpeed);

    return () => clearInterval(intervalVal);
  }, [isPlaying, playbackSpeed, replayEvents]);

  // Derived timeline snapshot variables
  const currentEvent = replayEvents[currentStep] || null;
  const currentCandleMap = currentEvent?.candle || {};
  const currentSymbol = Object.keys(currentCandleMap)[0] || "";
  const currentPortfolio = currentEvent?.portfolio || null;
  
  // Format candles list up to active step
  const activeCandles = useMemo(() => {
    if (replayEvents.length === 0) return [];
    // Extract candles for currentSymbol up to currentStep
    return replayEvents.slice(0, currentStep + 1).map(ev => {
      const c = ev.candle?.[currentSymbol];
      return c ? {
        time: ev.timestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume
      } : null;
    }).filter(Boolean) as any[];
  }, [replayEvents, currentStep, currentSymbol]);

  // Format trade markers up to currentStep
  const activeTrades = useMemo(() => {
    if (replayEvents.length === 0) return [];
    const trades: any[] = [];
    replayEvents.slice(0, currentStep + 1).forEach(ev => {
      if (ev.orders_filled && ev.orders_filled.length > 0) {
        ev.orders_filled.forEach((t: any) => {
          trades.push({
            time: ev.timestamp,
            direction: t.direction,
            price: t.price,
            qty: t.qty
          });
        });
      }
    });
    return trades;
  }, [replayEvents, currentStep]);

  // Calculate Position Exposure Curve (Total Quantity held over time)
  const positionCurveData = useMemo(() => {
    if (replayEvents.length === 0) return [];
    return replayEvents.slice(0, currentStep + 1).map(ev => ({
      time: ev.timestamp,
      value: ev.portfolio?.positions
        ? Object.values(ev.portfolio.positions).reduce((acc: number, p: any) => acc + p.qty, 0)
        : 0
    }));
  }, [replayEvents, currentStep]);

  // --- MULTI-ASSET REPLAY CONTROLS ---

  useEffect(() => {
    if (!multiIsPlaying || multiReplayEvents.length === 0) return;

    const intervalVal = setInterval(() => {
      setMultiCurrentStep(prev => {
        if (prev >= multiReplayEvents.length - 1) {
          setMultiIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 1000 / multiPlaybackSpeed);

    return () => clearInterval(intervalVal);
  }, [multiIsPlaying, multiPlaybackSpeed, multiReplayEvents]);

  // Multi-asset derived values
  const multiCurrentEvent = multiReplayEvents[multiCurrentStep] || null;
  const multiCandleMap = multiCurrentEvent?.candle || {};
  const multiSymbolsList = useMemo(() => {
    if (multiReplayEvents.length === 0) return [];
    const symbols = new Set<string>();
    multiReplayEvents.forEach(ev => {
      if (ev.candle) Object.keys(ev.candle).forEach(s => symbols.add(s));
    });
    return Array.from(symbols);
  }, [multiReplayEvents]);

  // Auto-select first symbol when replay loads
  useEffect(() => {
    if (multiSymbolsList.length > 0 && !multiSelectedSymbol) {
      setMultiSelectedSymbol(multiSymbolsList[0]);
    }
  }, [multiSymbolsList, multiSelectedSymbol]);

  const multiActiveCandles = useMemo(() => {
    if (multiReplayEvents.length === 0 || !multiSelectedSymbol) return [];
    return multiReplayEvents.slice(0, multiCurrentStep + 1).map(ev => {
      const c = ev.candle?.[multiSelectedSymbol];
      return c ? {
        time: ev.timestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume
      } : null;
    }).filter(Boolean) as any[];
  }, [multiReplayEvents, multiCurrentStep, multiSelectedSymbol]);

  const multiActiveTrades = useMemo(() => {
    if (multiReplayEvents.length === 0) return [];
    const trades: any[] = [];
    multiReplayEvents.slice(0, multiCurrentStep + 1).forEach(ev => {
      if (ev.orders_filled && ev.orders_filled.length > 0) {
        ev.orders_filled.forEach((t: any) => {
          if (!multiSelectedSymbol || t.symbol === multiSelectedSymbol) {
            trades.push({ time: ev.timestamp, direction: t.direction, price: t.price, qty: t.qty });
          }
        });
      }
    });
    return trades;
  }, [multiReplayEvents, multiCurrentStep, multiSelectedSymbol]);

  const multiPnLCurveData = useMemo(() => {
    if (multiReplayEvents.length === 0) return [];
    // Build per-asset realized PnL curves from trade fills
    const symbolPnLs: Record<string, number[]> = {};
    const timestamps: string[] = [];
    // Track running PnL per symbol using FIFO matching
    const symbolPositions: Record<string, { qty: number; avgPrice: number; realizedPnL: number }> = {};
    multiReplayEvents.slice(0, multiCurrentStep + 1).forEach(ev => {
      timestamps.push(ev.timestamp);
      // Process fills to update realized PnL
      if (ev.orders_filled) {
        ev.orders_filled.forEach((t: any) => {
          const sym = t.symbol;
          if (!symbolPositions[sym]) symbolPositions[sym] = { qty: 0, avgPrice: 0, realizedPnL: 0 };
          const pos = symbolPositions[sym];
          const dir = t.direction === "BUY" ? 1 : -1;
          const tradeQty = t.qty * dir;
          if ((pos.qty >= 0 && tradeQty > 0) || (pos.qty <= 0 && tradeQty < 0)) {
            // Adding to position
            const totalCost = pos.qty * pos.avgPrice + tradeQty * t.price;
            pos.qty += tradeQty;
            pos.avgPrice = pos.qty !== 0 ? totalCost / pos.qty : 0;
          } else {
            // Closing/reducing
            const matchedQty = Math.min(Math.abs(pos.qty), Math.abs(tradeQty));
            const pnl = (t.price - pos.avgPrice) * matchedQty * (pos.qty > 0 ? 1 : -1);
            pos.realizedPnL += pnl;
            pos.qty += tradeQty;
            if (pos.qty !== 0) pos.avgPrice = t.price;
          }
        });
      }
      // Snapshot current realized PnL for each known symbol
      Object.keys(symbolPositions).forEach(sym => {
        if (!symbolPnLs[sym]) symbolPnLs[sym] = new Array(timestamps.length - 1).fill(0);
        symbolPnLs[sym].push(symbolPositions[sym].realizedPnL);
      });
    });
    // Pad any series that started late with zeros
    Object.keys(symbolPnLs).forEach(sym => {
      while (symbolPnLs[sym].length < timestamps.length) {
        symbolPnLs[sym].unshift(0);
      }
    });
    // Return array of { time, values: { symbol: pnl } }
    return timestamps.map((time, i) => ({
      time,
      values: Object.fromEntries(Object.keys(symbolPnLs).map(sym => [sym, symbolPnLs[sym][i]]))
    }));
  }, [multiReplayEvents, multiCurrentStep]);

  const multiPositionCurveData = useMemo(() => {
    if (multiReplayEvents.length === 0 || !multiSelectedSymbol) return [];
    return multiReplayEvents.slice(0, multiCurrentStep + 1).map(ev => ({
      time: ev.timestamp,
      value: ev.portfolio?.positions?.[multiSelectedSymbol]?.qty || 0
    }));
  }, [multiReplayEvents, multiCurrentStep, multiSelectedSymbol]);

  const multiCurrentOrderDepths = multiCurrentEvent?.order_depths || {};
  const multiCurrentPortfolio = multiCurrentEvent?.portfolio || null;
  const multiCurrentSubmitted = multiCurrentEvent?.orders_submitted || [];
  const multiCurrentFilled = multiCurrentEvent?.orders_filled || [];

  // Order book for selected symbol
  const multiOrderBook = multiCurrentOrderDepths[multiSelectedSymbol] || null;
  const multiMidPrice = multiOrderBook
    ? (multiOrderBook.bid_prices?.[0] + multiOrderBook.ask_prices?.[0]) / 2
    : (multiCandleMap[multiSelectedSymbol]?.close || 0);
  const multiSpread = multiOrderBook
    ? (multiOrderBook.ask_prices?.[0] || 0) - (multiOrderBook.bid_prices?.[0] || 0)
    : 0;

  // Market pressure: bid volume vs ask volume
  const multiMarketPressure = useMemo(() => {
    if (!multiOrderBook) return 0;
    const bidVol = multiOrderBook.bid_volumes?.reduce((a: number, b: number) => a + b, 0) || 0;
    const askVol = multiOrderBook.ask_volumes?.reduce((a: number, b: number) => a + b, 0) || 0;
    const total = bidVol + askVol;
    if (total === 0) return 0;
    return (bidVol / total) * 100; // 0 = all ask, 100 = all bid, 50 = neutral
  }, [multiOrderBook]);

  const handleDatasetChange = async (val: string) => {
    setSelectedDataset(val);
    if (!val) {
      setAutoMaxPosValue(0);
      setMaxPositionSize(0);
      return;
    }

    if (backendOnline) {
      const parts = val.split("_");
      const symbol = parts[0];
      const interval = parts.slice(1).join("_");
      const result = await api.get(`/data/datasets/${symbol}/${interval}`);
      if (result.ok && result.data) {
        const suggested = result.data.suggested_max_position || 0;
        setAutoMaxPosValue(suggested);
        if (isAutoMaxPos) {
          setMaxPositionSize(suggested);
        }
        clearEndpointError(`data/datasets/${symbol}/${interval}`);
      } else {
        // Silently fail - dataset metadata is optional
        setAutoMaxPosValue(0);
      }
    } else {
      const fallback = Math.floor(initialCapital / 500);
      setAutoMaxPosValue(fallback);
      if (isAutoMaxPos) {
        setMaxPositionSize(fallback);
      }
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#050811] text-[#E2E8F0]">
      {/* Sidebar Navigation */}
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
              <span className="text-xs text-slate-500 font-mono">v1.0.0-PRO</span>
            </div>
          </div>

          {/* Nav Items */}
          <nav className="space-y-1">
            {[
              { id: "dashboard", label: "Dashboard", icon: LineChart },
              { id: "multiasset", label: "Multi-Asset", icon: TrendingUp },
              { id: "datasets", label: "Datasets", icon: Database },
              { id: "ide", label: "Strategy IDE", icon: Code },
              { id: "studio", label: "Replay Studio", icon: PlayCircle },
              { id: "research", label: "Research Lab", icon: BarChart2 },
              { id: "capital", label: "Capital Studio", icon: Layers },
              { id: "optimizer", label: "Optimizer", icon: PieChart },
              { id: "cleanup", label: "Cleanup", icon: Trash2 },
            ].map(item => {
              const Icon = item.icon;
              const active = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    active
                      ? "bg-blue-600/15 text-blue-400 border-l-2 border-blue-500"
                      : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
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
          {/* Notification Alert (Toast placeholder) */}
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

          {/* API Connections */}
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
                  ollamaState === "online"
                    ? "bg-emerald-500 shadow-[0_0_8px_#10B981]"
                    : ollamaState === "error"
                    ? "bg-rose-500 shadow-[0_0_8px_#F43F5E]"
                    : "bg-slate-600"
                }`} />
                <span className="text-slate-300">
                  {ollamaState === "online" ? "Online" : ollamaState === "error" ? "Error" : ollamaState === "offline" ? "Offline" : "Checking..."}
                </span>
              </div>
            </div>

            {/* Load Ollama Button — REMOVED: now handled inside Strategy Forge page */}

            {apiErrors["ollama/status"] && (
              <div className="text-[10px] text-rose-400 px-1 break-words">
                {apiErrors["ollama/status"].error}
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Main Workspace Frame */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto bg-[#070B16] p-6">
        {/* Workspace Header */}
        <header className="flex justify-between items-center pb-5 mb-5 border-b border-slate-800/70 shrink-0">
          <div>
            <h2 className="text-2xl font-bold capitalize text-slate-100 font-sans tracking-tight">
              {activeTab === "ide" ? "Strategy Workspace (IDE)" : activeTab.replace("-", " ")}
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              {activeTab === "dashboard" && "Configure market data feed, select strategies, and run simulations."}
              {activeTab === "datasets" && "Manage historical candle data directories saved in Parquet formats."}
              {activeTab === "ide" && "Write, edit, and compile sandboxed python trader.py execution programs."}
              {activeTab === "studio" && "Prosperity-inspired visualizer. Scrub step-by-step and inspect signals."}
              {activeTab === "research" && "Deep statistical analysis of any dataset — returns, volatility, regimes, seasonality, and strategy suitability scoring."}
              {activeTab === "capital" && "Explore margin requirements, drawdown risks, and scaling limits."}
              {activeTab === "optimizer" && "Execute grid-search sweeps to find mathematically optimal strategy weights."}
              {activeTab === "cleanup" && "Manage disk space by deleting old backtest logs and downloaded parquet datasets."}
            </p>
          </div>

          {/* Quick Select Panel */}
          <div className="flex items-center gap-3">
            {selectedDataset && (
              <div className="px-3 py-1 bg-slate-900 border border-slate-800 text-xs rounded-full text-blue-400 font-mono">
                Dataset: {selectedDataset}
              </div>
            )}
            {selectedRunId && (
              <div className="px-3 py-1 bg-slate-900 border border-slate-800 text-xs rounded-full text-emerald-400 font-mono">
                Run ID: {selectedRunId}
              </div>
            )}
          </div>
        </header>

        {/* Global Error Banners */}
        {Object.entries(apiErrors).filter(([ep]) => !ep.startsWith("ollama/")).length > 0 && (
          <div className="space-y-2 mb-4">
            {Object.entries(apiErrors)
              .filter(([ep]) => !ep.startsWith("ollama/"))
              .map(([endpoint, info]) => (
              <div
                key={endpoint}
                className="flex items-center gap-3 p-3 rounded-lg border border-rose-800/50 bg-rose-950/20 text-rose-400 text-xs"
              >
                <ServerCrash size={16} className="shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="font-semibold">{endpoint}</span>
                  <p className="text-rose-300/80 truncate">{info.error}</p>
                </div>
                <button
                  onClick={() => { clearEndpointError(endpoint); info.retry(); }}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded bg-rose-900/40 hover:bg-rose-900/60 border border-rose-800/50 text-[10px] font-bold transition-all shrink-0"
                >
                  <RotateCcw size={12} />
                  Retry
                </button>
                <button
                  onClick={() => clearEndpointError(endpoint)}
                  className="p-1.5 rounded hover:bg-rose-900/40 text-rose-400/60 hover:text-rose-400 transition-all shrink-0"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Tab content area */}
        <div className="flex-1 min-h-0">
          {/* TAB 1: OPERATIONAL DASHBOARD */}
          {activeTab === "dashboard" && (
            <div className="space-y-6">
              {/* Top summary row */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                  { title: "SmartAPI Connection", val: smartapiConnected ? "Connected" : "Disconnected", status: smartapiConnected ? "success" : "info" },
                  { title: "Saved Datasets", val: `${datasets.length} Active`, status: "info" },
                  { title: "Python Strategies", val: `${strategies.length} Compiled`, status: "info" },
                  { title: "Backtest Sessions", val: `${backtestRuns.length} Runs logged`, status: "info" }
                ].map((card, i) => (
                  <div key={i} className="glass-panel p-4 rounded-xl relative overflow-hidden">
                    <div className="absolute right-0 top-0 h-24 w-24 bg-gradient-to-br from-blue-500/10 to-transparent rounded-bl-full pointer-events-none" />
                    <span className="text-xs text-slate-400 font-medium">{card.title}</span>
                    <h3 className="text-lg font-bold text-slate-100 mt-1">{card.val}</h3>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* SmartAPI Connection Module */}
                <div className="glass-panel p-5 rounded-xl flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <h4 className="font-bold text-slate-200 flex items-center gap-2">
                        <Shield size={18} className="text-blue-400" />
                        SmartAPI Authentication
                      </h4>
                      {smartapiConnected ? (
                        <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800">CONNECTED</span>
                      ) : (
                        <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded-full bg-slate-900 text-slate-400 border border-slate-800">DISCONNECTED</span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mb-4 leading-relaxed">
                      Connect to Angel One SmartAPI to download real historical market ticks. Credentials are encrypted and stored in local catalog.
                    </p>
                    
                    <form onSubmit={triggerAuth}>
                      <div className="p-3 bg-slate-900/50 border border-dashed border-slate-800 rounded-lg text-center mb-4">
                        <p className="text-[10px] text-slate-500 uppercase font-bold">Authenticated via .env</p>
                      </div>
                      <button
                        type="submit"
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded font-bold text-xs py-2 transition-all"
                      >
                        Authenticate SmartAPI
                      </button>
                    </form>
                  </div>
                </div>

                {/* Quick Simulation Setup */}
                <div className="glass-panel p-5 rounded-xl flex flex-col justify-between col-span-2">
                  <div>
                    <h4 className="font-bold text-slate-200 mb-4 flex items-center gap-2">
                      <PlayCircle size={18} className="text-emerald-400" />
                      Quick Backtest Session Launch
                    </h4>
                    <p className="text-xs text-slate-400 mb-5 leading-relaxed">
                      Select strategy and market inputs, configure leverage profiles and slippage modeling parameters.
                    </p>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Select Strategy</label>
                        <select
                          value={selectedStrategyId}
                          onChange={e => handleSelectStrategy(e.target.value)}
                          className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                        >
                          <option value="">-- Choose Strategy --</option>
                          {strategies.map(s => (
                            <option key={s.id} value={s.id}>{s.name} (v{s.version})</option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Select Dataset (Parquet)</label>
                        <select
                          value={selectedDataset}
                          onChange={e => handleDatasetChange(e.target.value)}
                          className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                        >
                          <option value="">-- Choose Dataset --</option>
                          {datasets.map(d => (
                            <option key={`${d.symbol}_${d.interval}`} value={`${d.symbol}_${d.interval}`}>
                              {d.symbol} ({d.interval}) - {d.records_count} bars
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Initial Capital (INR)</label>
                        <input
                          type="number"
                          value={initialCapital}
                          onChange={e => setInitialCapital(Number(e.target.value))}
                          className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none"
                        />
                      </div>

                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Slippage Percentage</label>
                        <input
                          type="number"
                          step="0.01"
                          value={slippagePct}
                          onChange={e => setSlippagePct(Number(e.target.value))}
                          className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none"
                        />
                      </div>

                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Trade/Leverage Type</label>
                        <div className="flex gap-2 mt-1">
                          {["INTRADAY", "DELIVERY", "FUTURES"].map(t => (
                            <button
                              key={t}
                              type="button"
                              onClick={() => setTradeType(t)}
                              className={`flex-1 text-[10px] font-bold border rounded py-1 transition-all ${
                                tradeType === t
                                  ? "bg-blue-600/15 border-blue-500 text-blue-400"
                                  : "border-slate-800 text-slate-400 bg-slate-950/50 hover:bg-slate-900"
                              }`}
                            >
                              {t}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="col-span-2">
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1 flex justify-between">
                          <span>Max Position Limit</span>
                          <span className="text-blue-400 font-mono">
                            {isAutoMaxPos ? `${autoMaxPosValue} Qty (Auto)` : `${maxPositionSize} Qty (Custom)`}
                          </span>
                        </label>
                        <div className="flex items-center gap-3">
                          {/* Toggle: Auto / Custom */}
                          <div className="flex bg-slate-950 rounded border border-slate-800 overflow-hidden">
                            <button
                              type="button"
                              onClick={() => setIsAutoMaxPos(true)}
                              className={`px-3 py-1.5 text-[10px] font-bold transition-all ${
                                isAutoMaxPos
                                  ? "bg-blue-600 text-white"
                                  : "text-slate-400 hover:text-slate-200"
                              }`}
                            >
                              Auto
                            </button>
                            <button
                              type="button"
                              onClick={() => setIsAutoMaxPos(false)}
                              className={`px-3 py-1.5 text-[10px] font-bold transition-all ${
                                !isAutoMaxPos
                                  ? "bg-blue-600 text-white"
                                  : "text-slate-400 hover:text-slate-200"
                              }`}
                            >
                              Custom
                            </button>
                          </div>

                          {/* Custom input (only shown when Custom mode) */}
                          {!isAutoMaxPos && (
                            <input
                              type="number"
                              min="1"
                              max="999999"
                              value={maxPositionSize}
                              onChange={e => setMaxPositionSize(Math.max(1, Number(e.target.value)))}
                              className="flex-1 text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
                              placeholder="Enter qty..."
                            />
                          )}

                          {isAutoMaxPos && (
                            <span className="flex-1 text-xs text-slate-500 italic">
                              Risk-based sizing: 2% capital / volatility stop
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="flex items-end">
                        <button
                          onClick={handleRunBacktest}
                          className="w-full bg-emerald-600 hover:bg-emerald-700 text-white rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2"
                        >
                          <Play size={14} fill="currentColor" />
                          Execute Backtest Engine
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Past runs logs */}
              <div className="glass-panel p-5 rounded-xl">
                <h4 className="font-bold text-slate-200 mb-4">Past Backtest Results Logs</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-slate-400 border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-300 font-medium">
                        <th className="py-2.5">Run ID</th>
                        <th>Strategy Name</th>
                        <th>Asset Symbol</th>
                        <th>Timeframe</th>
                        <th>Period Dates</th>
                        <th>Net Profit</th>
                        <th>Sharpe Ratio</th>
                        <th>Max Qty</th>
                        <th className="text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {backtestRuns.map(run => (
                        <tr key={run.id} className="hover:bg-slate-900/30">
                          <td className="py-3 font-mono text-blue-400 font-bold">{run.id}</td>
                          <td>{run.strategy_name}</td>
                          <td className="font-bold text-slate-300">{run.symbol}</td>
                          <td>{run.interval}</td>
                          <td className="text-slate-500">{run.start_time?.split(" ")[0] || run.start_time} to {run.end_time?.split(" ")[0] || run.end_time}</td>
                          <td className={run.total_pnl >= 0 ? "text-emerald-400 font-semibold" : "text-rose-400 font-semibold"}>
                            ₹{(run.total_pnl ?? 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                          </td>
                          <td className="font-bold">{run.sharpe_ratio?.toFixed(2) ?? "-"}</td>
                          <td className="font-mono text-slate-500">{run.max_position_size || "Auto"}</td>
                          <td className="text-right">
                            <button
                              onClick={() => handleSelectRun(run.id)}
                              className="px-2.5 py-1 rounded bg-slate-800 text-[10px] font-bold text-slate-200 hover:bg-slate-700 transition-all"
                            >
                              Load Replay
                            </button>
                          </td>
                        </tr>
                      ))}
                      {backtestRuns.length === 0 && (
                        <tr>
                          <td colSpan={8} className="py-6 text-center text-slate-500 font-medium">
                            No simulation runs logged yet. Configure data and strategy to trigger backtests.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: DATASET EXPLORER */}
          {activeTab === "datasets" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* SmartAPI Candle Downloader Form */}
              <div className="glass-panel p-5 rounded-xl self-start">
                <h4 className="font-bold text-slate-200 mb-4 flex items-center gap-2">
                  <Database size={18} className="text-blue-400" />
                  SmartAPI Downloader
                </h4>
                <p className="text-xs text-slate-400 mb-4 leading-relaxed">
                  Submit symbol requests. Files are indexed in standard Parquet formats under `/datasets/parquet/`.
                </p>

                <form onSubmit={triggerDownload} className="space-y-4">
                  <div className="relative">
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Asset Symbol</label>
                    <input
                      type="text"
                      value={dlSymbol}
                      onChange={e => {
                        setDlSymbol(e.target.value.toUpperCase());
                        setShowSuggestions(true);
                      }}
                      onFocus={() => setShowSuggestions(true)}
                      onBlur={() => {
                        // Delay closing to allow onClick to fire
                        setTimeout(() => setShowSuggestions(false), 200);
                      }}
                      className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500 font-semibold"
                      placeholder="e.g. SBIN, RELIANCE, NIFTY"
                    />
                    
                    {showSuggestions && suggestions.length > 0 && (
                      <div className="absolute z-50 w-full mt-1 max-h-60 overflow-y-auto bg-slate-950 border border-slate-800 rounded shadow-2xl divide-y divide-slate-800/60 custom-scrollbar">
                        {suggestions.map(s => (
                          <div
                            key={s.token}
                            onClick={() => {
                              setDlSymbol(s.symbol);
                              setShowSuggestions(false);
                            }}
                            className="px-3 py-2 text-xs hover:bg-slate-900 cursor-pointer flex justify-between items-center transition-colors duration-150"
                          >
                            <div className="flex flex-col">
                              <span className="font-semibold text-slate-200">{s.symbol}</span>
                              <span className="text-[9px] text-slate-500 truncate max-w-[160px]">{s.name}</span>
                            </div>
                            <span className="text-[9px] font-mono bg-slate-900 border border-slate-800/80 rounded px-1.5 py-0.5 text-slate-400">{s.token}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Timeframe Interval</label>
                    <select
                      value={dlInterval}
                      onChange={e => setDlInterval(e.target.value)}
                      className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                    >
                      <option value="ONE_MINUTE">1 Minute (Intraday)</option>
                      <option value="FIVE_MINUTE">5 Minute (Intraday)</option>
                      <option value="FIFTEEN_MINUTE">15 Minute (Intraday)</option>
                      <option value="ONE_HOUR">1 Hour</option>
                      <option value="ONE_DAY">Daily</option>
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">From Date</label>
                      <input
                        type="date"
                        value={dlFromDate}
                        onChange={e => setDlFromDate(e.target.value)}
                        className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">To Date</label>
                      <input
                        type="date"
                        value={dlToDate}
                        onChange={e => setDlToDate(e.target.value)}
                        className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 focus:outline-none"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={downloading}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2"
                  >
                    {downloading ? (
                      <>
                        <RefreshCw size={14} className="animate-spin" />
                        Fetching Candle Ranges...
                      </>
                    ) : (
                      <>
                        <Database size={14} />
                        Fetch & Write Parquet Sheet
                      </>
                    )}
                  </button>
                </form>
              </div>

              {/* Indexed Parquet Files Metadata Catalog */}
              <div className="glass-panel p-5 rounded-xl col-span-2">
                <h4 className="font-bold text-slate-200 mb-4">Metadata Catalog (Parquet Storage)</h4>
                
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-slate-400 border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-300 font-medium">
                        <th className="py-2.5">Symbol</th>
                        <th>Interval</th>
                        <th>Record Range</th>
                        <th>Bars Count</th>
                        <th>Parquet Path</th>
                        <th className="text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {datasets.map(d => (
                        <tr key={`${d.symbol}_${d.interval}`} className="hover:bg-slate-900/30">
                          <td className="py-3 font-bold text-slate-200">{d.symbol}</td>
                          <td>{d.interval}</td>
                          <td className="text-slate-500 font-mono text-[10px]">{d.start_date || "-"} - {d.end_date || "-"}</td>
                          <td className="font-semibold text-blue-400 font-mono">{d.records_count ?? "-"}</td>
                          <td className="text-slate-600 truncate max-w-xs text-[10px]" title={d.file_path || ""}>
                            {d.file_path || "-"}
                          </td>
                          <td className="text-right">
                            <button
                              onClick={() => {
                                setSelectedDataset(`${d.symbol}_${d.interval}`);
                                triggerNotif("success", `Dataset ${d.symbol} selected as active simulation feed.`);
                              }}
                              className={`px-2.5 py-1 rounded text-[10px] font-bold transition-all ${
                                selectedDataset === `${d.symbol}_${d.interval}`
                                  ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                                  : "bg-slate-800 text-slate-200 hover:bg-slate-700"
                              }`}
                            >
                              {selectedDataset === `${d.symbol}_${d.interval}` ? "Active Feed" : "Select Feed"}
                            </button>
                          </td>
                        </tr>
                      ))}
                      {datasets.length === 0 && (
                        <tr>
                          <td colSpan={6} className="py-6 text-center text-slate-500 font-medium">
                            No Parquet datasets found on disk. Download candles using SmartAPI.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: STRATEGY UPLOAD */}
          {activeTab === "ide" && (
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 h-full min-h-[500px]">
              {/* Strategy catalog sidebar */}
              <div className="glass-panel p-4 rounded-xl flex flex-col justify-between">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-slate-200 text-sm">Strategies Catalog</h4>
                    <button
                      onClick={() => {
                        setSelectedStrategyId("");
                        setCode("");
                        setUploadedFileName("");
                        if (fileInputRef.current) fileInputRef.current.value = "";
                        triggerNotif("info", "Cleared. Upload a .py file to begin.");
                      }}
                      className="p-1 bg-slate-800 hover:bg-slate-700 text-blue-400 rounded transition-all"
                      title="Clear"
                    >
                      <Plus size={14} />
                    </button>
                  </div>

                  <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                    {strategies.map(s => (
                      <div
                        key={s.id}
                        onClick={() => handleSelectStrategy(s.id)}
                        className={`p-2.5 rounded-lg border text-left cursor-pointer transition-all ${
                          selectedStrategyId === s.id
                            ? "bg-blue-600/10 border-blue-500/50"
                            : "border-slate-800/80 bg-slate-950/20 hover:bg-slate-900/50"
                        }`}
                      >
                        <h5 className="font-semibold text-slate-200 text-xs">{s.name} {s.runtime_type ? `(${s.runtime_type})` : ""}</h5>
                        <p className="text-[10px] text-slate-500 font-mono mt-1">v{s.version} • {new Date(s.updated_at).toLocaleDateString()}</p>
                      </div>
                    ))}
                    {strategies.length === 0 && (
                      <p className="text-[10px] text-slate-500 text-center py-4">No strategies stored yet.</p>
                    )}
                  </div>
                </div>

                {/* Runtime config */}
                <div className="space-y-3 pt-4 border-t border-slate-800">
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Runtime Type</label>
                    <select
                      value={strategyRuntimeType}
                      onChange={e => setStrategyRuntimeType(e.target.value)}
                      className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                    >
                      <option value="legacy_on_bar">Legacy On-Bar</option>
                      <option value="prosperity_trader">Prosperity Trader</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Entrypoint</label>
                    <input
                      type="text"
                      value={strategyEntrypoint || ""}
                      onChange={e => setStrategyEntrypoint(e.target.value || null)}
                      placeholder="e.g., trader.py:Trader"
                      className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>

                {/* Action buttons */}
                <div className="space-y-3 pt-4 border-t border-slate-800">
                  <button
                    onClick={handleSaveStrategy}
                    disabled={!code}
                    className="w-full bg-slate-800 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-600 text-slate-200 border border-slate-700 rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2"
                  >
                    <FileText size={14} />
                    Save to Database
                  </button>
                  <button
                    onClick={handleRunBacktest}
                    disabled={!selectedStrategyId}
                    className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2"
                  >
                    <PlayCircle size={14} />
                    Execute Backtest
                  </button>
                </div>
              </div>

              {/* Upload + Preview panel */}
              <div className="glass-panel rounded-xl col-span-3 flex flex-col overflow-hidden relative border border-slate-800">
                {/* Upload area */}
                <div className="p-6 border-b border-slate-800 bg-slate-950/60">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-bold text-slate-200 text-sm flex items-center gap-2">
                      <Code size={16} className="text-blue-400" />
                      Strategy Upload
                    </h4>
                    {uploadedFileName && (
                      <span className="text-xs font-mono text-emerald-400 bg-emerald-950/30 px-2 py-1 rounded border border-emerald-800">
                        {uploadedFileName}
                      </span>
                    )}
                  </div>
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="border-2 border-dashed border-slate-700 hover:border-blue-500 rounded-xl p-8 text-center cursor-pointer transition-colors bg-slate-950/30"
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".py"
                      onChange={handleFileUpload}
                      className="hidden"
                    />
                    <div className="flex flex-col items-center gap-2">
                      <div className="p-3 bg-slate-800 rounded-full">
                        <FileText size={24} className="text-slate-400" />
                      </div>
                      <p className="text-sm font-medium text-slate-300">
                        Click to upload a <span className="text-blue-400 font-bold">.py</span> strategy file
                      </p>
                      <p className="text-[10px] text-slate-500">
                        Or drag and drop. Max file size ~1 MB.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Code preview */}
                <div className="flex-1 min-h-0 bg-[#1e1e1e] overflow-auto">
                  {code ? (
                    <pre className="p-4 text-xs font-mono text-slate-300 leading-relaxed whitespace-pre-wrap">
                      {code}
                    </pre>
                  ) : (
                    <div className="h-full flex items-center justify-center text-slate-600">
                      <div className="text-center">
                        <Code size={32} className="mx-auto mb-2 text-slate-700" />
                        <p className="text-sm">Upload a .py file to preview code</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: REPLAY STUDIO */}
          {activeTab === "studio" && (
            <div className="flex flex-col gap-4 h-full">
              {/* Playback Control Bar */}
              <div className="glass-panel p-3.5 rounded-xl flex flex-wrap items-center justify-between gap-4">
                {/* Simulation Step Counter */}
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-400">Step:</span>
                  <span className="px-2.5 py-1 bg-slate-950 text-blue-400 border border-slate-800 font-mono text-xs rounded font-bold">
                    {currentStep} / {replayEvents.length > 0 ? replayEvents.length - 1 : 0}
                  </span>
                </div>

                {/* Playback Controls */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCurrentStep(prev => Math.max(0, prev - 1))}
                    disabled={currentStep === 0}
                    className="p-2 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-200 rounded disabled:opacity-30 transition-all"
                  >
                    <SkipBack size={14} fill="currentColor" />
                  </button>

                  <button
                    onClick={() => setIsPlaying(!isPlaying)}
                    disabled={replayEvents.length === 0}
                    className={`p-2 rounded text-white shadow-lg transition-all ${
                      isPlaying
                        ? "bg-amber-600 hover:bg-amber-700 shadow-amber-600/10"
                        : "bg-emerald-600 hover:bg-emerald-700 shadow-emerald-600/10"
                    }`}
                  >
                    {isPlaying ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" />}
                  </button>

                  <button
                    onClick={() => setCurrentStep(prev => Math.min(replayEvents.length - 1, prev + 1))}
                    disabled={replayEvents.length === 0 || currentStep === replayEvents.length - 1}
                    className="p-2 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-200 rounded disabled:opacity-30 transition-all"
                  >
                    <SkipForward size={14} fill="currentColor" />
                  </button>
                </div>

                {/* Speed Multiplier */}
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-slate-400 mr-1.5">Speed:</span>
                  {[1, 2, 5, 10].map(speed => (
                    <button
                      key={speed}
                      onClick={() => setPlaybackSpeed(speed)}
                      className={`px-2 py-0.5 border rounded text-[10px] font-bold transition-all ${
                        playbackSpeed === speed
                          ? "bg-blue-600/20 border-blue-500 text-blue-400"
                          : "border-slate-800 text-slate-500 hover:bg-slate-900"
                      }`}
                    >
                      {speed}x
                    </button>
                  ))}
                </div>

                {/* Timeline Slider Scrubber */}
                <div className="flex-1 min-w-[200px] flex items-center gap-3">
                  <input
                    type="range"
                    min={0}
                    max={replayEvents.length > 0 ? replayEvents.length - 1 : 0}
                    value={currentStep}
                    onChange={e => setCurrentStep(Number(e.target.value))}
                    disabled={replayEvents.length === 0}
                    className="w-full accent-blue-500 cursor-pointer disabled:opacity-30"
                  />
                  <span className="text-[10px] font-mono text-slate-500 whitespace-nowrap">
                    {currentEvent?.timestamp || "00:00:00"}
                  </span>
                </div>
              </div>

              {/* Main Replay Workspace split */}
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 flex-1 min-h-0">
                {/* Left 3 Columns: Charts & Logs */}
                <div className="lg:col-span-3 flex flex-col gap-4 h-full min-h-0">
                  {/* Candlestick Interactive Chart */}
                  <div className="flex-1 min-h-[300px] flex flex-col justify-between">
                    {/* Chart Controls */}
                    <div className="flex items-center gap-2 mb-2 px-1 flex-wrap">
                      <span className="text-[10px] text-slate-500 font-bold uppercase">Indicators:</span>
                      <button
                        onClick={() => setShowEmaFast(!showEmaFast)}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${
                          showEmaFast
                            ? "bg-blue-600/20 border-blue-500 text-blue-400"
                            : "border-slate-800 text-slate-500 hover:bg-slate-900"
                        }`}
                      >
                        EMA 9
                      </button>
                      <button
                        onClick={() => setShowEmaSlow(!showEmaSlow)}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${
                          showEmaSlow
                            ? "bg-amber-600/20 border-amber-500 text-amber-400"
                            : "border-slate-800 text-slate-500 hover:bg-slate-900"
                        }`}
                      >
                        EMA 21
                      </button>
                      <span className="text-[10px] text-slate-500 font-bold uppercase ml-2">Trades:</span>
                      <button
                        onClick={() => setShowBuyTrades(!showBuyTrades)}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${
                          showBuyTrades
                            ? "bg-emerald-600/20 border-emerald-500 text-emerald-400"
                            : "border-slate-800 text-slate-500 hover:bg-slate-900"
                        }`}
                      >
                        BUY
                      </button>
                      <button
                        onClick={() => setShowSellTrades(!showSellTrades)}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${
                          showSellTrades
                            ? "bg-rose-600/20 border-rose-500 text-rose-400"
                            : "border-slate-800 text-slate-500 hover:bg-slate-900"
                        }`}
                      >
                        SELL
                      </button>
                    </div>
                    {activeCandles.length > 0 ? (
                      <LightweightChart
                        candles={activeCandles}
                        trades={activeTrades}
                        showEmaFast={showEmaFast}
                        showEmaSlow={showEmaSlow}
                        showBuyTrades={showBuyTrades}
                        showSellTrades={showSellTrades}
                        height={350}
                      />
                    ) : (
                      <div className="w-full h-80 bg-slate-950/60 rounded-xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-500">
                        <AlertTriangle size={32} className="text-slate-600 mb-2 animate-bounce" />
                        <span className="text-xs">No active replay data loaded. Run a backtest or load a past run.</span>
                      </div>
                    )}
                  </div>

                  {/* Position Exposure Line Chart */}
                  <div className="glass-panel rounded-xl overflow-hidden flex flex-col shrink-0 border border-slate-800/50">
                    <div className="px-3 py-1.5 bg-slate-950/80 border-b border-slate-800 text-[10px] font-bold font-mono text-slate-400 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Layers size={12} className="text-blue-400" />
                        <span>Net Position Exposure (Inventory)</span>
                      </div>
                    </div>
                    <PositionChart data={positionCurveData} height={120} />
                  </div>

                  {/* Sandbox Print Logs Output */}
                  <div className="glass-panel rounded-xl overflow-hidden h-36 flex flex-col shrink-0">
                    <div className="px-3 py-1.5 bg-slate-950 border-b border-slate-800 text-[10px] font-bold font-mono text-slate-400 flex items-center justify-between">
                      <span>Strategy print Terminal logs</span>
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 pulse-dot" />
                    </div>
                    <div className="flex-1 p-3 bg-slate-950/90 font-mono text-[11px] text-[#10B981] overflow-y-auto space-y-1.5">
                      {currentEvent?.log_messages?.map((msg: string, idx: number) => (
                        <div key={idx} className="flex gap-2">
                          <span className="text-slate-600">[{currentStep}]</span>
                          <span>{msg}</span>
                        </div>
                      ))}
                      {(!currentEvent?.log_messages || currentEvent.log_messages.length === 0) && (
                        <span className="text-slate-600 text-[10px]">No logs generated at this step.</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right 1 Column: Portfolio snapshot and Active Trades */}
                <div className="space-y-4 h-full overflow-y-auto">
                  {/* Portfolio Snapshot Cards */}
                  <div className="glass-panel p-4 rounded-xl space-y-3">
                    <h5 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Portfolio Snap</h5>
                    
                    {[
                      { label: "Net Equity", val: `₹${currentPortfolio?.equity?.toLocaleString(undefined, { maximumFractionDigits: 1 }) || "0.0"}` },
                      { label: "Cash Balance", val: `₹${currentPortfolio?.cash?.toLocaleString(undefined, { maximumFractionDigits: 1 }) || "0.0"}` },
                      { label: "Margin Used", val: `₹${currentPortfolio?.margin_used?.toLocaleString(undefined, { maximumFractionDigits: 1 }) || "0.0"}` },
                      { label: "Margin Free", val: `₹${currentPortfolio?.margin_free?.toLocaleString(undefined, { maximumFractionDigits: 1 }) || "0.0"}` },
                      { label: "Total Fees Paid", val: `₹${currentPortfolio?.total_fees?.toLocaleString(undefined, { maximumFractionDigits: 1 }) || "0.0"}` },
                      { label: "Max Pos Limit", val: `${backtestDetail?.max_position_size || "Auto"}` },
                    ].map((row, i) => (
                      <div key={i} className="flex justify-between items-center text-xs py-1 border-b border-slate-800/40">
                        <span className="text-slate-400">{row.label}</span>
                        <span className="font-semibold text-slate-200 font-mono">{row.val}</span>
                      </div>
                    ))}
                  </div>

                  {/* Active Positions */}
                  <div className="glass-panel p-4 rounded-xl">
                    <h5 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2.5">Open Positions</h5>
                    {currentPortfolio?.positions && Object.keys(currentPortfolio.positions).length > 0 ? (
                      Object.values(currentPortfolio.positions).map((pos: any) => (
                        <div key={pos.symbol} className="flex justify-between items-center text-xs border border-slate-800 rounded p-2 bg-slate-950/40">
                          <div>
                            <span className="font-bold text-slate-200">{pos.symbol}</span>
                            <div className="text-[10px] text-slate-500 mt-0.5">
                              {pos.qty > 0 ? "LONG" : "SHORT"} {Math.abs(pos.qty)} @ {pos.avg_price.toFixed(1)}
                            </div>
                          </div>
                          <span className={`font-mono font-semibold ${pos.unrealized_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                            ₹{pos.unrealized_pnl.toFixed(1)}
                          </span>
                        </div>
                      ))
                    ) : (
                      <p className="text-[10px] text-slate-500 text-center py-4">No open positions.</p>
                    )}
                  </div>

                  {/* Step Trade matching */}
                  <div className="glass-panel p-4 rounded-xl">
                    <h5 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2.5">Fills at this Step</h5>
                    {currentEvent?.orders_filled && currentEvent.orders_filled.length > 0 ? (
                      currentEvent.orders_filled.map((t: any, idx: number) => (
                        <div key={idx} className="text-xs border border-slate-800 rounded p-2 bg-slate-950/40 space-y-1">
                          <div className="flex justify-between font-bold">
                            <span className={t.direction === "BUY" ? "text-emerald-400" : "text-rose-400"}>
                              {t.direction} {t.qty}
                            </span>
                            <span className="text-slate-200 font-mono">₹{(t.price ?? 0).toFixed(1)}</span>
                          </div>
                          <div className="flex justify-between text-[10px] text-slate-500">
                            <span>Fees: ₹{(t.total_charges ?? 0).toFixed(1)}</span>
                            <span>{t.id}</span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="text-[10px] text-slate-500 text-center py-4">No trade fills this step.</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: RESEARCH LAB */}
          {activeTab === "research" && (
            <ResearchLab
              datasets={datasets}
              apiErrors={apiErrors}
              setEndpointError={setEndpointError}
              clearEndpointError={clearEndpointError}
              setNotif={setNotif}
            />
          )}

          {/* TAB 6: CAPITAL STUDIO */}
          {activeTab === "capital" && (
            <div className="space-y-6">
              {capitalData ? (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Capital requirements metrics card */}
                  <div className="glass-panel p-5 rounded-xl space-y-4 self-start">
                    <h4 className="font-bold text-slate-200 text-sm">Capital Requirements & Allocation</h4>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Simulations analyze the strategy drawdown risks to calculate survival thresholds.
                    </p>

                    <div className="space-y-3 pt-2">
                      <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                        <span className="text-[10px] uppercase font-bold text-slate-500">Minimum Viable Capital (MVC)</span>
                        <h3 className="text-xl font-bold text-rose-400 font-mono mt-0.5">
                          ₹{capitalData.minimum_viable_capital?.toLocaleString()}
                        </h3>
                        <p className="text-[10px] text-slate-500 mt-1">Below this limit, risk of margin liquidation is extreme.</p>
                      </div>

                      <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                        <span className="text-[10px] uppercase font-bold text-slate-500">Optimal Capital Buffer</span>
                        <h3 className="text-xl font-bold text-emerald-400 font-mono mt-0.5">
                          ₹{capitalData.optimal_capital_allocation?.toLocaleString()}
                        </h3>
                        <p className="text-[10px] text-slate-500 mt-1">Recommended account sizing for balanced drawdowns.</p>
                      </div>
                    </div>
                  </div>

                  {/* Scaling curves table list */}
                  <div className="glass-panel p-5 rounded-xl col-span-2 space-y-4">
                    <h4 className="font-bold text-slate-200 text-sm">Capital Sizing & Slippage Degradation Table</h4>
                    <p className="text-xs text-slate-400">
                      Shows how return profiles degrade as size scales (larger orders face higher slippage/market impact).
                    </p>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs text-slate-400 border-collapse">
                        <thead>
                          <tr className="border-b border-slate-800 text-slate-300 font-medium">
                            <th className="py-2.5">Initial Capital</th>
                            <th>CAGR Return</th>
                            <th>Sharpe Ratio</th>
                            <th>Margin Call risk</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/50">
                          {capitalData.scaling_curve.map((row: any) => (
                            <tr key={row.capital} className="hover:bg-slate-900/30">
                              <td className="py-3 font-mono font-bold text-slate-200">
                                ₹{row.capital.toLocaleString()}
                              </td>
                              <td className="font-mono">{(row.cagr * 100).toFixed(1)}%</td>
                              <td className="font-mono">{row.sharpe.toFixed(2)}</td>
                              <td>
                                {row.margin_call ? (
                                  <span className="text-rose-400 text-[10px] font-bold uppercase">HIGH RISK (Margin Call)</span>
                                ) : (
                                  <span className="text-emerald-400 text-[10px] font-bold uppercase">SAFE</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="glass-panel p-8 text-center text-slate-500 rounded-xl">
                  <Layers size={32} className="mx-auto mb-2 text-slate-700 animate-pulse" />
                  <span className="text-xs">Load a backtest run first to calculate capital survival diagnostics.</span>
                </div>
              )}
            </div>
          )}

          {/* TAB 7: OPTIMIZATION LAB */}
          {activeTab === "optimizer" && (
            <div className="space-y-6">
              {/* Optimization run inputs panel */}
              <div className="glass-panel p-5 rounded-xl space-y-4">
                <h4 className="font-bold text-slate-200 text-sm">Parameter Sweeps Grid Search Config</h4>
                <p className="text-xs text-slate-400">
                  Run parallel sweeps on strategy attributes to evaluate parameters combos.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Parameter 1 Name</label>
                    <input
                      type="text"
                      value={optParamName1}
                      onChange={e => setOptParamName1(e.target.value)}
                      className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">P1 Range Values</label>
                    <input
                      type="text"
                      value={optParamVals1}
                      onChange={e => setOptParamVals1(e.target.value)}
                      className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Parameter 2 Name</label>
                    <input
                      type="text"
                      value={optParamName2}
                      onChange={e => setOptParamName2(e.target.value)}
                      className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">P2 Range Values</label>
                    <input
                      type="text"
                      value={optParamVals2}
                      onChange={e => setOptParamVals2(e.target.value)}
                      className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none font-mono"
                    />
                  </div>

                  <button
                    onClick={handleRunOptimization}
                    className="bg-blue-600 hover:bg-blue-700 text-white rounded font-bold text-xs py-2 transition-all"
                  >
                    Execute Grid Sweep
                  </button>
                </div>
              </div>

              {optimizationGrid ? (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Grid details listing */}
                  <div className="glass-panel p-5 rounded-xl col-span-2 space-y-4">
                    <h4 className="font-bold text-slate-200 text-sm">Optimization Grid Results Matrix</h4>
                    
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs text-slate-400 border-collapse">
                        <thead>
                          <tr className="border-b border-slate-800 text-slate-300 font-medium">
                            <th className="py-2.5">Combo Parameters</th>
                            <th>CAGR Return</th>
                            <th>Sharpe Ratio</th>
                            <th>Max Drawdown</th>
                            <th>Trades Count</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/50">
                          {optimizationGrid.results.map((row: any, i: number) => (
                            <tr key={i} className="hover:bg-slate-900/30">
                              <td className="py-3 font-mono font-bold text-blue-400">
                                {JSON.stringify(row.parameters)}
                              </td>
                              <td className="font-mono">{(row.cagr * 100).toFixed(1)}%</td>
                              <td className="font-mono font-semibold text-slate-200">{row.sharpe.toFixed(2)}</td>
                              <td className="font-mono">{(row.max_drawdown * 100).toFixed(1)}%</td>
                              <td className="font-mono text-slate-500">{row.total_trades ?? "-"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Best Combo panel */}
                  <div className="glass-panel p-5 rounded-xl space-y-4 self-start">
                    <h4 className="font-bold text-slate-200 text-sm">Best Parameter Configuration</h4>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Automatically calculated from highest Sharpe Ratio index.
                    </p>

                    {optimizationGrid.best_result ? (
                      <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-3">
                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-500">Parameters</span>
                          <h4 className="text-sm font-mono font-bold text-emerald-400 mt-0.5">
                            {JSON.stringify(optimizationGrid.best_result.parameters)}
                          </h4>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-slate-800">
                          <div>
                            <span className="text-slate-500 block text-[9px] uppercase font-bold">Sharpe</span>
                            <span className="font-bold text-slate-200 font-mono">{optimizationGrid.best_result.sharpe.toFixed(2)}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block text-[9px] uppercase font-bold">CAGR</span>
                            <span className="font-bold text-slate-200 font-mono">{(optimizationGrid.best_result.cagr * 100).toFixed(1)}%</span>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-500">Grid failed or returned no successes.</span>
                    )}
                  </div>
                </div>
              ) : (
                <div className="glass-panel p-8 text-center text-slate-500 rounded-xl">
                  <PieChart size={32} className="mx-auto mb-2 text-slate-700 animate-pulse" />
                  <span className="text-xs">Configure and execute sweep to display parameter performance surface values.</span>
                </div>
              )}
            </div>
          )}

          {/* TAB 8: MULTI-ASSET BACKTEST & REPLAY */}
          {activeTab === "multiasset" && (
            <div className="flex flex-col gap-4 h-full">
              {/* If no replay loaded, show config form */}
              {multiReplayEvents.length === 0 ? (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Multi-Asset Config Panel */}
                    <div className="glass-panel p-5 rounded-xl space-y-4">
                      <h4 className="font-bold text-slate-200 flex items-center gap-2">
                        <TrendingUp size={18} className="text-blue-400" />
                        Multi-Asset Backtest
                      </h4>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        Enter one or more symbols. Data auto-downloads if missing. Supports pairs, spreads, and options multi-leg strategies.
                      </p>

                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Symbols (comma-separated)</label>
                        <input
                          type="text"
                          value={multiSymbols}
                          onChange={e => setMultiSymbols(e.target.value.toUpperCase())}
                          className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500 font-semibold"
                          placeholder="e.g. SBIN, RELIANCE, NIFTY"
                        />
                      </div>

                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Timeframe</label>
                        <select
                          value={multiInterval}
                          onChange={e => setMultiInterval(e.target.value)}
                          className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                        >
                          <option value="ONE_MINUTE">1 Minute</option>
                          <option value="FIVE_MINUTE">5 Minute</option>
                          <option value="FIFTEEN_MINUTE">15 Minute</option>
                          <option value="ONE_HOUR">1 Hour</option>
                          <option value="ONE_DAY">Daily</option>
                        </select>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">From Date</label>
                          <input
                            type="date"
                            value={multiFromDate}
                            onChange={e => setMultiFromDate(e.target.value)}
                            className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">To Date</label>
                          <input
                            type="date"
                            value={multiToDate}
                            onChange={e => setMultiToDate(e.target.value)}
                            className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 focus:outline-none"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Select Strategy</label>
                        <select
                          value={multiStrategyId}
                          onChange={e => setMultiStrategyId(e.target.value)}
                          className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                        >
                          <option value="">-- Choose Strategy --</option>
                          {strategies.map(s => (
                            <option key={s.id} value={s.id}>{s.name} ({s.runtime_type})</option>
                          ))}
                        </select>
                      </div>

                      <button
                        onClick={() => {
                          if (!multiStrategyId) { triggerNotif("error", "Select a strategy first."); return; }
                          if (!multiSymbols.trim()) { triggerNotif("error", "Enter at least one symbol."); return; }
                          setIsBacktestModalOpen(true);
                        }}
                        className="w-full bg-emerald-600 hover:bg-emerald-700 text-white rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2"
                      >
                        <Play size={14} fill="currentColor" />
                        Configure & Run Backtest
                      </button>
                    </div>

                    {/* Info / Help Panel */}
                    <div className="glass-panel p-5 rounded-xl col-span-2 space-y-4">
                      <h4 className="font-bold text-slate-200 text-sm">How Multi-Asset Backtesting Works</h4>
                      <div className="space-y-3 text-xs text-slate-400">
                        <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                          <span className="text-[10px] uppercase font-bold text-blue-400 block mb-1">Auto-Download</span>
                          If data is missing, the backend automatically downloads it via SmartAPI or generates mock candles. No manual dataset management needed.
                        </div>
                        <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                          <span className="text-[10px] uppercase font-bold text-emerald-400 block mb-1">Multiple Symbols</span>
                          Enter <code className="text-slate-200">SBIN, RELIANCE</code> for pairs trading, or <code className="text-slate-200">NIFTY24500CE, NIFTY24600CE, NIFTY24700CE</code> for options spreads.
                        </div>
                        <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                          <span className="text-[10px] uppercase font-bold text-amber-400 block mb-1">Strategy Access</span>
                          In your Prosperity strategy, <code className="text-slate-200">state.order_depths</code> contains ALL symbols simultaneously. Loop through them to trade multi-leg.
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                /* REPLAY MODE: Prosperity-style UI */
                <>
                  {/* Top: Symbol Filter Chips */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] uppercase font-bold text-slate-500 mr-2">Symbols:</span>
                    {multiSymbolsList.map(sym => (
                      <button
                        key={sym}
                        onClick={() => setMultiSelectedSymbol(sym)}
                        className={`px-3 py-1 rounded-full text-[10px] font-bold border transition-all ${
                          multiSelectedSymbol === sym
                            ? "bg-slate-800 border-slate-600 text-white"
                            : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-600"
                        }`}
                      >
                        {sym}
                      </button>
                    ))}
                    <button
                      onClick={() => { setMultiReplayEvents([]); setMultiBacktestDetail(null); setMultiRunId(""); }}
                      className="px-3 py-1 rounded-full text-[10px] font-bold border border-rose-800 text-rose-400 hover:bg-rose-950/30 transition-all ml-auto"
                    >
                      Close Replay
                    </button>
                  </div>

                  {/* Main Layout: Chart Left + Sidebar Right */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">
                    {/* LEFT: Charts & Playback */}
                    <div className="lg:col-span-2 flex flex-col gap-3 h-full min-h-0 overflow-y-auto">
                      {/* Playback Control Bar */}
                      <div className="glass-panel p-2.5 rounded-xl flex flex-wrap items-center gap-3">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setMultiCurrentStep(0)}
                            className="p-1.5 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 rounded text-[10px]"
                            title="Reset"
                          >
                            <SkipBack size={12} />
                          </button>
                          <button
                            onClick={() => setMultiIsPlaying(!multiIsPlaying)}
                            className={`p-2 rounded text-white transition-all ${multiIsPlaying ? "bg-amber-600 hover:bg-amber-700" : "bg-emerald-600 hover:bg-emerald-700"}`}
                          >
                            {multiIsPlaying ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" />}
                          </button>
                          <button
                            onClick={() => setMultiCurrentStep(prev => Math.min(multiReplayEvents.length - 1, prev + 1))}
                            className="p-1.5 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 rounded"
                          >
                            <SkipForward size={12} />
                          </button>
                        </div>

                        <div className="flex items-center gap-1">
                          {[1, 2, 5, 10, 20].map(speed => (
                            <button
                              key={speed}
                              onClick={() => setMultiPlaybackSpeed(speed)}
                              className={`px-1.5 py-0.5 rounded text-[9px] font-bold border transition-all ${
                                multiPlaybackSpeed === speed
                                  ? "bg-blue-600/20 border-blue-500 text-blue-400"
                                  : "border-slate-800 text-slate-500 hover:bg-slate-900"
                              }`}
                            >
                              {speed}x
                            </button>
                          ))}
                        </div>

                        <div className="flex-1 min-w-[150px] flex items-center gap-2">
                          <input
                            type="range"
                            min={0}
                            max={multiReplayEvents.length - 1}
                            value={multiCurrentStep}
                            onChange={e => setMultiCurrentStep(Number(e.target.value))}
                            className="w-full accent-blue-500 cursor-pointer"
                          />
                          <span className="text-[10px] font-mono text-slate-500 whitespace-nowrap">
                            {multiCurrentStep} / {multiReplayEvents.length - 1}
                          </span>
                        </div>

                        <div className="text-[10px] font-mono text-slate-400">
                          {multiCurrentEvent?.timestamp?.split(" ")[1] || "--:--:--"}
                        </div>
                      </div>

                      {/* Price Chart */}
                      <div className="flex-1 min-h-[280px]">
                        {multiActiveCandles.length > 0 ? (
                          <LightweightChart
                            candles={multiActiveCandles}
                            trades={multiActiveTrades}
                            showEmaFast={false}
                            showEmaSlow={false}
                            showBuyTrades={true}
                            showSellTrades={true}
                            height={300}
                          />
                        ) : (
                          <div className="w-full h-[300px] bg-slate-950/60 rounded-xl border border-slate-800/80 flex items-center justify-center text-slate-500 text-xs">
                            No chart data for {multiSelectedSymbol}
                          </div>
                        )}
                      </div>

                      {/* PnL Chart */}
                      <PnLChart data={multiPnLCurveData} height={120} title="PnL Performance" />

                      {/* Position Chart */}
                      <div className="glass-panel rounded-xl overflow-hidden flex flex-col shrink-0 border border-slate-800/50">
                        <div className="px-3 py-1.5 bg-slate-950/80 border-b border-slate-800 text-[10px] font-bold font-mono text-slate-400 flex items-center justify-between">
                          <span>Position: {multiSelectedSymbol}</span>
                          <span className="text-slate-500">{multiCurrentPortfolio?.positions?.[multiSelectedSymbol]?.qty || 0} qty</span>
                        </div>
                        <PositionChart data={multiPositionCurveData} height={100} />
                      </div>

                    </div>

                    {/* RIGHT: Sidebar Panels */}
                    <div className="space-y-3 h-full overflow-y-auto">
                      {/* Strategy Management */}
                      <div className="glass-panel p-3 rounded-xl">
                        <div className="text-[10px] uppercase font-bold text-slate-500 mb-2">Strategy Management</div>
                        <div className="p-2 bg-slate-950 rounded border border-slate-800">
                          <div className="text-[10px] text-slate-400">{multiBacktestDetail?.strategy_name || "Unknown Strategy"}</div>
                          <div className="text-[10px] font-mono text-slate-500 mt-1">Run: {multiRunId}</div>
                        </div>
                      </div>

                      {/* Order Book */}
                      <div className="glass-panel p-3 rounded-xl">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[10px] uppercase font-bold text-slate-500">Order Book</span>
                          <span className="text-[9px] font-mono text-slate-500">Spread: {multiSpread.toFixed(2)}</span>
                        </div>
                        {multiOrderBook ? (
                          <div className="space-y-1">
                            {/* Asks (red) - reverse to show worst first */}
                            {[...multiOrderBook.ask_prices].reverse().map((price: number, i: number) => {
                              const idx = multiOrderBook.ask_prices.length - 1 - i;
                              const vol = multiOrderBook.ask_volumes[idx];
                              return (
                                <div key={`ask-${i}`} className="flex items-center justify-between text-[10px]">
                                  <span className="font-mono text-rose-400">{price?.toFixed(2)}</span>
                                  <div className="flex-1 mx-2 h-1.5 bg-slate-900 rounded overflow-hidden">
                                    <div className="h-full bg-rose-500/30 rounded" style={{ width: `${Math.min(100, (vol / 100) * 100)}%` }} />
                                  </div>
                                  <span className="font-mono text-slate-400">{vol}</span>
                                </div>
                              );
                            })}
                            {/* Mid price */}
                            <div className="py-1 border-y border-slate-800 text-center">
                              <span className="text-[10px] font-mono text-slate-300">MID: {multiMidPrice.toFixed(2)}</span>
                            </div>
                            {/* Bids (green) */}
                            {multiOrderBook.bid_prices.map((price: number, i: number) => {
                              const vol = multiOrderBook.bid_volumes[i];
                              return (
                                <div key={`bid-${i}`} className="flex items-center justify-between text-[10px]">
                                  <span className="font-mono text-emerald-400">{price?.toFixed(2)}</span>
                                  <div className="flex-1 mx-2 h-1.5 bg-slate-900 rounded overflow-hidden">
                                    <div className="h-full bg-emerald-500/30 rounded" style={{ width: `${Math.min(100, (vol / 100) * 100)}%` }} />
                                  </div>
                                  <span className="font-mono text-slate-400">{vol}</span>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="text-[10px] text-slate-500 text-center py-2">No order book data</div>
                        )}
                      </div>

                      {/* Market Pressure */}
                      <div className="glass-panel p-3 rounded-xl">
                        <div className="text-[10px] uppercase font-bold text-slate-500 mb-2">Market Pressure</div>
                        <div className="relative h-2 bg-slate-900 rounded-full overflow-hidden">
                          <div
                            className="absolute top-0 left-0 h-full bg-emerald-500/60 transition-all"
                            style={{ width: `${multiMarketPressure}%` }}
                          />
                          <div
                            className="absolute top-0 right-0 h-full bg-rose-500/60 transition-all"
                            style={{ width: `${100 - multiMarketPressure}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-[9px] text-slate-500 mt-1">
                          <span>Bid Heavy</span>
                          <span className="font-mono">{multiMarketPressure.toFixed(1)}%</span>
                          <span>Ask Heavy</span>
                        </div>
                      </div>

                      {/* Product Summary */}
                      <div className="glass-panel p-3 rounded-xl">
                        <div className="text-[10px] uppercase font-bold text-slate-500 mb-2">Product Summary: {multiSelectedSymbol}</div>
                        <div className="space-y-2">
                          {[
                            { label: "Position", val: `${multiCurrentPortfolio?.positions?.[multiSelectedSymbol]?.qty || 0}` },
                            { label: "PnL", val: `₹${(multiCurrentPortfolio?.positions?.[multiSelectedSymbol]?.unrealized_pnl || 0).toFixed(1)}` },
                            { label: "Mid Price", val: `₹${multiMidPrice.toFixed(2)}` },
                            { label: "Spread", val: `${multiSpread.toFixed(2)}` },
                          ].map((row, i) => (
                            <div key={i} className="flex justify-between text-[10px]">
                              <span className="text-slate-500">{row.label}</span>
                              <span className="font-mono text-slate-300">{row.val}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Portfolio Snapshot */}
                      <div className="glass-panel p-3 rounded-xl">
                        <div className="text-[10px] uppercase font-bold text-slate-500 mb-2">Portfolio</div>
                        <div className="space-y-2">
                          {[
                            { label: "Equity", val: `₹${(multiCurrentPortfolio?.equity || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}` },
                            { label: "Cash", val: `₹${(multiCurrentPortfolio?.cash || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}` },
                            { label: "Margin Used", val: `₹${(multiCurrentPortfolio?.margin_used || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}` },
                            { label: "Total PnL", val: `₹${(multiCurrentPortfolio?.total_pnl || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}` },
                            { label: "Total Fees", val: `₹${(multiCurrentPortfolio?.total_fees || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}` },
                          ].map((row, i) => (
                            <div key={i} className="flex justify-between text-[10px] border-b border-slate-800/30 pb-1 last:border-0">
                              <span className="text-slate-500">{row.label}</span>
                              <span className="font-mono text-slate-300">{row.val}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* BOTTOM: Orders & Trades Panels */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 shrink-0">
                    {/* Submitted Orders */}
                    <div className="glass-panel rounded-xl overflow-hidden border border-slate-800/50">
                      <div className="px-3 py-1.5 bg-slate-950/80 border-b border-slate-800 text-[10px] font-bold font-mono text-slate-400">
                        Submitted Orders
                      </div>
                      <div className="p-2 max-h-32 overflow-y-auto">
                        {multiCurrentSubmitted.length > 0 ? (
                          multiCurrentSubmitted.map((o: any, i: number) => (
                            <div key={i} className="flex justify-between text-[10px] py-1 border-b border-slate-800/20">
                              <span className={`font-bold ${o.direction === "BUY" ? "text-emerald-400" : "text-rose-400"}`}>{o.direction}</span>
                              <span className="font-mono text-slate-300">{o.symbol}</span>
                              <span className="font-mono text-slate-400">{o.quantity} @ ₹{o.price?.toFixed(1) || "MKT"}</span>
                            </div>
                          ))
                        ) : (
                          <div className="text-[10px] text-slate-500 text-center py-2">No orders submitted</div>
                        )}
                      </div>
                    </div>

                    {/* Bot Trades at This Tick */}
                    <div className="glass-panel rounded-xl overflow-hidden border border-slate-800/50">
                      <div className="px-3 py-1.5 bg-slate-950/80 border-b border-slate-800 text-[10px] font-bold font-mono text-slate-400">
                        Bot Trades at This Tick
                      </div>
                      <div className="p-2 max-h-32 overflow-y-auto">
                        {multiCurrentFilled.length > 0 ? (
                          multiCurrentFilled.map((t: any, i: number) => (
                            <div key={i} className="flex justify-between text-[10px] py-1 border-b border-slate-800/20">
                              <span className={`font-bold ${t.direction === "BUY" ? "text-emerald-400" : "text-rose-400"}`}>{t.direction}</span>
                              <span className="font-mono text-slate-300">{t.symbol}</span>
                              <span className="font-mono text-slate-400">{t.qty} @ ₹{t.price?.toFixed(2)}</span>
                            </div>
                          ))
                        ) : (
                          <div className="text-[10px] text-slate-500 text-center py-2">No fills this tick</div>
                        )}
                      </div>
                    </div>

                    {/* Market Trades (own trades by symbol) */}
                    <div className="glass-panel rounded-xl overflow-hidden border border-slate-800/50">
                      <div className="px-3 py-1.5 bg-slate-950/80 border-b border-slate-800 text-[10px] font-bold font-mono text-slate-400">
                        Own Trades ({multiSelectedSymbol})
                      </div>
                      <div className="p-2 max-h-32 overflow-y-auto">
                        {multiCurrentEvent?.trading_state?.own_trades?.[multiSelectedSymbol]?.length > 0 ? (
                          multiCurrentEvent.trading_state.own_trades[multiSelectedSymbol].map((t: any, i: number) => (
                            <div key={i} className="flex justify-between text-[10px] py-1 border-b border-slate-800/20">
                              <span className={`font-bold ${t.direction === "BUY" ? "text-emerald-400" : "text-rose-400"}`}>{t.direction}</span>
                              <span className="font-mono text-slate-400">{t.quantity} @ ₹{t.price?.toFixed(2)}</span>
                            </div>
                          ))
                        ) : (
                          <div className="text-[10px] text-slate-500 text-center py-2">No own trades</div>
                        )}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* TAB 9: CLEANUP / DISK MANAGEMENT */}
          {activeTab === "cleanup" && (
            <div className="space-y-6">
              {/* Disk Usage Status Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="glass-panel p-4 rounded-xl">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-400 font-medium">Parquet Datasets</span>
                    <Database size={16} className="text-blue-400" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-100">
                    {cleanupStatus?.datasets_parquet?.size_human || "--"}
                  </h3>
                  <p className="text-[10px] text-slate-500 mt-1">
                    {cleanupStatus?.datasets_parquet?.exists ? "Active storage" : "No data found"}
                  </p>
                </div>
                <div className="glass-panel p-4 rounded-xl">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-400 font-medium">Backtest Logs</span>
                    <FileText size={16} className="text-amber-400" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-100">
                    {cleanupStatus?.logs?.size_human || "--"}
                  </h3>
                  <p className="text-[10px] text-slate-500 mt-1">
                    {cleanupStatus?.logs?.exists ? "JSONL replay files" : "No logs found"}
                  </p>
                </div>
                <div className="glass-panel p-4 rounded-xl">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-400 font-medium">SQLite Database</span>
                    <Database size={16} className="text-emerald-400" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-100">
                    {cleanupStatus?.database?.size_human || "--"}
                  </h3>
                  <p className="text-[10px] text-slate-500 mt-1">
                    {cleanupStatus?.database?.exists ? "quantlab.db" : "DB not found"}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Cleanup Controls */}
                <div className="glass-panel p-5 rounded-xl space-y-4">
                  <h4 className="font-bold text-slate-200 flex items-center gap-2">
                    <Trash2 size={18} className="text-rose-400" />
                    Cleanup Controls
                  </h4>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Select what to delete and whether to preview (dry-run) first. Use with caution — deletion is permanent.
                  </p>

                  {/* Target Selection */}
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Target</label>
                    <select
                      value={cleanupTarget}
                      onChange={e => setCleanupTarget(e.target.value)}
                      className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                    >
                      <option value="logs">Backtest Logs Only</option>
                      <option value="parquet">Parquet Datasets Only</option>
                      <option value="strategies">Strategy Files Only</option>
                      <option value="all">Logs + Parquet + Strategies (ALL)</option>
                      <option value="db_orphans">DB Orphan Records Only</option>
                    </select>
                  </div>

                  {/* Symbol Filter (for parquet) */}
                  {(cleanupTarget === "parquet" || cleanupTarget === "all") && (
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Symbol Filter (optional)</label>
                      <input
                        type="text"
                        value={cleanupSymbol}
                        onChange={e => setCleanupSymbol(e.target.value.toUpperCase())}
                        placeholder="e.g. SBIN"
                        className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500 font-semibold"
                      />
                    </div>
                  )}

                  {/* Interval Filter (for parquet) */}
                  {(cleanupTarget === "parquet" || cleanupTarget === "all") && (
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Interval Filter (optional)</label>
                      <select
                        value={cleanupInterval}
                        onChange={e => setCleanupInterval(e.target.value)}
                        className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                      >
                        <option value="">-- Any Interval --</option>
                        <option value="ONE_MINUTE">1 Minute</option>
                        <option value="FIVE_MINUTE">5 Minute</option>
                        <option value="FIFTEEN_MINUTE">15 Minute</option>
                        <option value="ONE_HOUR">1 Hour</option>
                        <option value="ONE_DAY">Daily</option>
                      </select>
                    </div>
                  )}

                  {/* Strategy ID Filter (for strategies) */}
                  {(cleanupTarget === "strategies" || cleanupTarget === "all") && (
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Strategy Name Filter (optional)</label>
                      <input
                        type="text"
                        value={cleanupStrategyId}
                        onChange={e => setCleanupStrategyId(e.target.value)}
                        placeholder="e.g. trader"
                        className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500 font-semibold"
                      />
                    </div>
                  )}

                  {/* Older Than */}
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Older Than (days, optional)</label>
                    <input
                      type="number"
                      min="1"
                      value={cleanupOlderThan}
                      onChange={e => setCleanupOlderThan(e.target.value ? Number(e.target.value) : "")}
                      placeholder="e.g. 7"
                      className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                    />
                  </div>

                  {/* Dry Run Toggle */}
                  <div className="flex items-center gap-3 p-3 bg-slate-950/50 rounded border border-slate-800">
                    <input
                      id="dryRun"
                      type="checkbox"
                      checked={cleanupDryRun}
                      onChange={e => setCleanupDryRun(e.target.checked)}
                      className="h-4 w-4 accent-blue-500"
                    />
                    <label htmlFor="dryRun" className="text-xs text-slate-300 cursor-pointer select-none">
                      <span className="font-bold">Dry-Run Mode</span> — Preview deletions without actually deleting
                    </label>
                  </div>

                  {/* Action Buttons */}
                  <div className="space-y-2 pt-2">
                    <button
                      onClick={handleRunCleanup}
                      disabled={cleanupLoading}
                      className={`w-full rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2 ${
                        cleanupDryRun
                          ? "bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
                          : "bg-rose-600 hover:bg-rose-700 text-white"
                      }`}
                    >
                      {cleanupLoading ? (
                        <RefreshCw size={14} className="animate-spin" />
                      ) : cleanupDryRun ? (
                        <>
                          <RefreshCw size={14} />
                          Preview Cleanup
                        </>
                      ) : (
                        <>
                          <Trash2 size={14} />
                          Execute Cleanup
                        </>
                      )}
                    </button>
                    <button
                      onClick={handleVacuumDB}
                      disabled={cleanupLoading}
                      className="w-full bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2"
                    >
                      {cleanupLoading ? <RefreshCw size={14} className="animate-spin" /> : <Database size={14} />}
                      {cleanupDryRun ? "Preview Vacuum DB" : "Vacuum Database"}
                    </button>
                    <button
                      onClick={fetchCleanupStatus}
                      disabled={cleanupLoading}
                      className="w-full bg-blue-600/15 hover:bg-blue-600/25 text-blue-400 border border-blue-800 rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2"
                    >
                      <RefreshCw size={14} />
                      Refresh Status
                    </button>
                  </div>
                </div>

                {/* Cleanup Results Panel */}
                <div className="glass-panel p-5 rounded-xl col-span-2 space-y-4">
                  <h4 className="font-bold text-slate-200 text-sm">Cleanup Results</h4>

                  {!cleanupResult && !cleanupStatus && (
                    <div className="p-8 text-center text-slate-500">
                      <Trash2 size={32} className="mx-auto mb-2 text-slate-700" />
                      <span className="text-xs">Click "Refresh Status" to load disk usage, or run a cleanup preview.</span>
                    </div>
                  )}

                  {/* Status Summary */}
                  {cleanupStatus && (
                    <div className="space-y-3">
                      <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                        <span className="text-[10px] uppercase font-bold text-slate-500">Total Disk Usage</span>
                        <h3 className="text-xl font-bold text-slate-200 font-mono mt-0.5">
                          {cleanupStatus.total_human}
                        </h3>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div className="p-2 bg-slate-950 rounded border border-slate-800">
                          <span className="text-slate-500 block text-[9px] uppercase font-bold">Parquet Data</span>
                          <span className="font-mono text-slate-300">{cleanupStatus.datasets_parquet?.size_human || "--"}</span>
                        </div>
                        <div className="p-2 bg-slate-950 rounded border border-slate-800">
                          <span className="text-slate-500 block text-[9px] uppercase font-bold">Logs</span>
                          <span className="font-mono text-slate-300">{cleanupStatus.logs?.size_human || "--"}</span>
                        </div>
                        <div className="p-2 bg-slate-950 rounded border border-slate-800">
                          <span className="text-slate-500 block text-[9px] uppercase font-bold">Strategies</span>
                          <span className="font-mono text-slate-300">{cleanupStatus.strategies?.size_human || "--"}</span>
                        </div>
                        <div className="p-2 bg-slate-950 rounded border border-slate-800">
                          <span className="text-slate-500 block text-[9px] uppercase font-bold">Database</span>
                          <span className="font-mono text-slate-300">{cleanupStatus.database?.size_human || "--"}</span>
                        </div>
                        <div className="p-2 bg-slate-950 rounded border border-slate-800">
                          <span className="text-slate-500 block text-[9px] uppercase font-bold">Backend Log</span>
                          <span className="font-mono text-slate-300">{cleanupStatus.backend_log?.size_human || "--"}</span>
                        </div>
                        <div className="p-2 bg-slate-950 rounded border border-slate-800">
                          <span className="text-slate-500 block text-[9px] uppercase font-bold">Restart Log</span>
                          <span className="font-mono text-slate-300">{cleanupStatus.backend_restart_log?.size_human || "--"}</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Cleanup Operation Result */}
                  {cleanupResult && (
                    <div className="space-y-3">
                      <div className={`p-3 rounded border ${cleanupResult.dry_run ? "bg-blue-950/30 border-blue-800" : "bg-emerald-950/30 border-emerald-800"}`}>
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] uppercase font-bold text-slate-400">
                            {cleanupResult.dry_run ? "Dry-Run Preview" : "Cleanup Executed"}
                          </span>
                          <span className="text-xs font-bold font-mono text-slate-200">
                            {cleanupResult.bytes_freed_human} freed
                          </span>
                        </div>
                        <div className="text-xs text-slate-300 mt-1">
                          Files deleted: <span className="font-mono font-bold">{cleanupResult.files_deleted}</span>
                        </div>
                      </div>

                      {/* Details List */}
                      {cleanupResult.details && cleanupResult.details.length > 0 && (
                        <div className="max-h-64 overflow-y-auto space-y-1 p-2 bg-slate-950 rounded border border-slate-800">
                          {cleanupResult.details.map((detail: string, i: number) => (
                            <div key={i} className="text-[11px] font-mono text-slate-400 py-0.5 border-b border-slate-800/30 last:border-0">
                              {detail}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Backtest Config Modal */}
      {isBacktestModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="glass-panel p-6 rounded-2xl w-full max-w-md border-emerald-500/30 shadow-[0_0_50px_rgba(16,185,129,0.15)]">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 bg-emerald-600 rounded-xl text-white">
                <Play size={20} />
              </div>
              <h3 className="text-lg font-bold text-slate-100">Backtest Configuration</h3>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Initial Capital (₹)</label>
                  <input
                    type="number"
                    value={modalCapital}
                    onChange={e => setModalCapital(Number(e.target.value))}
                    className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Slippage (%)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={modalSlippage}
                    onChange={e => setModalSlippage(Number(e.target.value))}
                    className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Trade Type</label>
                <div className="flex gap-2">
                  {["INTRADAY", "DELIVERY", "FUTURES"].map(t => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setModalTradeType(t)}
                      className={`flex-1 text-[10px] font-bold border rounded py-1.5 transition-all ${
                        modalTradeType === t
                          ? "bg-emerald-600/15 border-emerald-500 text-emerald-400"
                          : "border-slate-800 text-slate-400 bg-slate-950/50 hover:bg-slate-900"
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1 flex justify-between">
                  <span>Max Position Limit</span>
                  <span className="text-emerald-400 font-mono">
                    {modalAutoMaxPos ? "Auto (Risk-based)" : `${modalMaxPos} Qty`}
                  </span>
                </label>
                <div className="flex items-center gap-3">
                  <div className="flex bg-slate-950 rounded border border-slate-800 overflow-hidden">
                    <button
                      type="button"
                      onClick={() => setModalAutoMaxPos(true)}
                      className={`px-3 py-1.5 text-[10px] font-bold transition-all ${
                        modalAutoMaxPos
                          ? "bg-emerald-600 text-white"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      Auto
                    </button>
                    <button
                      type="button"
                      onClick={() => setModalAutoMaxPos(false)}
                      className={`px-3 py-1.5 text-[10px] font-bold transition-all ${
                        !modalAutoMaxPos
                          ? "bg-emerald-600 text-white"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      Custom
                    </button>
                  </div>
                  {!modalAutoMaxPos && (
                    <input
                      type="number"
                      min="1"
                      value={modalMaxPos}
                      onChange={e => setModalMaxPos(Math.max(1, Number(e.target.value)))}
                      className="flex-1 text-xs bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono"
                    />
                  )}
                </div>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setIsBacktestModalOpen(false)}
                className="flex-1 px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-bold text-slate-400 hover:bg-slate-800 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  setIsBacktestModalOpen(false);
                  const symbols = multiSymbols.split(",").map(s => s.trim()).filter(Boolean);
                  
                  // Ensure dates are YYYY-MM-DD format
                  const formatDate = (d: string) => {
                    if (!d) return "";
                    // If already YYYY-MM-DD, return as-is
                    if (/^\d{4}-\d{2}-\d{2}$/.test(d)) return d;
                    // Try to parse and reformat
                    const dt = new Date(d);
                    if (isNaN(dt.getTime())) return d;
                    return dt.toISOString().split("T")[0];
                  };
                  
                  const startDate = formatDate(multiFromDate);
                  const endDate = formatDate(multiToDate);
                  
                  triggerNotif("info", `Running backtest on ${symbols.join(", ")}...`);
                  
                  const result = await api.post("/backtest/run", {
                    strategy_id: multiStrategyId,
                    symbols,
                    interval: multiInterval,
                    start_date: startDate,
                    end_date: endDate,
                    initial_capital: modalCapital,
                    slippage_pct: modalSlippage / 100.0,
                    trade_type: modalTradeType,
                    max_position_size: modalAutoMaxPos ? 0 : modalMaxPos,
                    runtime_type: strategies.find(s => s.id === multiStrategyId)?.runtime_type || "legacy_on_bar",
                    auto_download: true
                  });

                  if (result.ok && result.data) {
                    triggerNotif("success", `Backtest complete! Run: ${result.data.run_id}`);
                    if (result.data.downloaded_symbols?.length > 0) {
                      triggerNotif("info", `Auto-downloaded: ${result.data.downloaded_symbols.join(", ")}`);
                    }
                    setSelectedRunId(result.data.run_id);
                    setMultiRunId(result.data.run_id);
                    fetchCoreData();
                    // Load replay data into multi-asset state
                    loadMultiAssetReplay(result.data.run_id);
                    setActiveTab("multiasset");
                  } else {
                    triggerNotif("error", `Backtest failed: ${result.error || "Engine error"}`);
                  }
                }}
                className="flex-1 px-4 py-2.5 rounded-lg bg-emerald-600 text-xs font-bold text-white hover:bg-emerald-700 transition-all shadow-lg shadow-emerald-600/20"
              >
                Execute Backtest
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TOTP Modal Popup */}
      {isTotpModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="glass-panel p-6 rounded-2xl w-full max-w-sm border-blue-500/30 shadow-[0_0_50px_rgba(59,130,246,0.15)] animate-in zoom-in-95 duration-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 bg-blue-600 rounded-xl text-white">
                <Shield size={20} />
              </div>
              <h3 className="text-lg font-bold text-slate-100">Verification Required</h3>
            </div>
            <p className="text-xs text-slate-400 mb-6 leading-relaxed">
              {pendingAction === "AUTH" 
                ? "Authorize SmartAPI session via Angel One TOTP." 
                : "Authorize market data download request."}
            </p>
            <input
              autoFocus
              type="text"
              maxLength={6}
              placeholder="000000"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-4 text-center text-3xl font-mono tracking-[0.4em] text-blue-400 focus:outline-none focus:border-blue-500 shadow-inner"
              value={totpInput}
              onChange={(e) => setTotpInput(e.target.value.replace(/\D/g, ""))}
              onKeyDown={(e) => e.key === "Enter" && handleTotpConfirm()}
            />
            <div className="flex gap-3 mt-8">
              <button
                onClick={() => { setIsTotpModalOpen(false); setTotpInput(""); setPendingAction(null); }}
                className="flex-1 px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-bold text-slate-400 hover:bg-slate-800 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleTotpConfirm}
                className="flex-1 px-4 py-2.5 rounded-lg bg-blue-600 text-xs font-bold text-white hover:bg-blue-700 transition-all shadow-lg shadow-blue-600/20"
              >
                Confirm Code
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
