"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import dynamic from "next/dynamic";
import {
  LineChart, Play, Pause, SkipForward, SkipBack, Cpu, FileText, BarChart2,
  PieChart, Settings, Database, Activity, Code, Shield, HelpCircle,
  Plus, PlayCircle, RefreshCw, Layers, CheckCircle2, AlertTriangle, AlertCircle, Trash2, ArrowUpRight, ArrowDownRight
} from "lucide-react";

// Dynamically import client-only libraries to prevent NextJS hydration / SSR errors
const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false });
const LightweightChart = dynamic(() => import("../components/LightweightChart"), { ssr: false });

const API_BASE = "http://127.0.0.1:8000/api";

export default function Home() {
  // Navigation State
  const [activeTab, setActiveTab] = useState<string>("dashboard");

  // Server & SmartAPI Status
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [smartapiConfigured, setSmartapiConfigured] = useState<boolean>(false);
  const [smartapiConnected, setSmartapiConnected] = useState<boolean>(false);

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
  const [code, setCode] = useState<string>(`class Strategy:
    def __init__(self):
        self.name = "EMA Crossover Template"
        self.ema_fast = 9
        self.ema_slow = 21
        self.trade_qty = 10 # Quantity to buy/sell per signal

    def on_bar(self, state):
        orders = []
        for symbol, candles in state.historical_candles.items():
            if len(candles) < self.ema_slow:
                continue

            closes = [c.close for c in candles]
            import pandas as pd
            series = pd.Series(closes)
            ema_f = series.ewm(span=self.ema_fast, adjust=False).mean().iloc[-1]
            ema_s = series.ewm(span=self.ema_slow, adjust=False).mean().iloc[-1]
            
            pos = state.positions.get(symbol)
            qty = pos.qty if pos else 0
            
            # Entry/Exit logic with quantity tracking
            # Note: The engine enforces the 'Max Position Limit' automatically
            
            if ema_f > ema_s and qty <= 0:
                # Buy signal: enter or flip long
                orders.append({
                    "symbol": symbol,
                    "direction": "BUY",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": self.trade_qty if qty == 0 else (self.trade_qty * 2)
                })
                print(f"BUY Signal generated at {state.current_time}")
            elif ema_f < ema_s and qty >= 0:
                # Sell signal: enter or flip short
                orders.append({
                    "symbol": symbol,
                    "direction": "SELL",
                    "type": "MARKET",
                    "price": 0.0,
                    "qty": self.trade_qty if qty == 0 else (self.trade_qty * 2)
                })
                print(f"SELL Signal generated at {state.current_time}")
                
        return orders
`);

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
  const [maxPositionSize, setMaxPositionSize] = useState<number>(0);

  // Research, Capital, and Optimization Dashboards States
  const [researchData, setResearchData] = useState<any>(null);
  const [capitalData, setCapitalData] = useState<any>(null);
  const [optimizationGrid, setOptimizationGrid] = useState<any>(null);
  
  // Optimization Inputs
  const [optParamName1, setOptParamName1] = useState<string>("ema_fast");
  const [optParamVals1, setOptParamVals1] = useState<string>("5, 9, 15");
  const [optParamName2, setOptParamName2] = useState<string>("ema_slow");
  const [optParamVals2, setOptParamVals2] = useState<string>("20, 30, 50");

  // Dataset Download Form Inputs
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

  // --- CONNECTIVITY & FETCHERS ---

  useEffect(() => {
    checkBackendHealth();
    // Periodically check health
    const interval = setInterval(checkBackendHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  // Fetch symbol suggestions with debounce
  useEffect(() => {
    if (!dlSymbol || dlSymbol.length < 2) {
      setSuggestions([]);
      return;
    }
    const delayDebounceFn = setTimeout(() => {
      fetch(`${API_BASE}/data/symbols/search?q=${dlSymbol}`)
        .then(res => res.json())
        .then(data => setSuggestions(data))
        .catch(err => console.error("Error fetching suggestions:", err));
    }, 250);

    return () => clearTimeout(delayDebounceFn);
  }, [dlSymbol]);

  const triggerNotif = (type: "success" | "error" | "info", msg: string) => {
    setNotif({ type, msg });
    setTimeout(() => setNotif(null), 5000);
  };

  const checkBackendHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/strategies`);
      if (res.ok) {
        setBackendOnline(true);
        fetchCoreData();
      } else {
        setBackendOnline(false);
      }
    } catch {
      setBackendOnline(false);
    }
  };

  const fetchCoreData = async () => {
    try {
      // Use independent catchers for each fetch to prevent "Failed to fetch" from crashing the loop
      // 1. Fetch Strategies
      const stratReq = fetch(`${API_BASE}/strategies`).then(r => r.ok ? r.json() : null).catch(() => null);

      // 2. Fetch Parquet Catalog
      const catReq = fetch(`${API_BASE}/data/datasets`).then(r => r.ok ? r.json() : null).catch(() => null);

      // 3. Fetch Runs Catalog
      const runsReq = fetch(`${API_BASE}/backtest/results`).then(r => r.ok ? r.json() : null).catch(() => null);

      // 4. Fetch SmartAPI Status
      const sapiReq = fetch(`${API_BASE}/auth/smartapi/status`).then(r => r.ok ? r.json() : null).catch(() => null);

      const [stratData, catData, runsData, sapiData] = await Promise.all([stratReq, catReq, runsReq, sapiReq]);

      if (stratData) setStrategies(stratData);
      if (catData) setDatasets(Object.values(catData));
      if (runsData) setBacktestRuns(runsData);
      if (sapiData) {
        setSmartapiConfigured(sapiData.configured);
        setSmartapiConnected(sapiData.connected);
      }

    } catch (e) {
      console.error("Error fetching dashboard catalog: ", e);
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
    try {
      const res = await fetch(`${API_BASE}/auth/smartapi/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          totp: code
        })
      });
      const data = await res.json();
      if (res.ok && data.connection_success) {
        setSmartapiConfigured(true);
        setSmartapiConnected(true);
        triggerNotif("success", "SmartAPI Authenticated & Connected!");
        fetchCoreData();
      } else {
        triggerNotif("error", `SmartAPI connection failed: ${data.message || "Bad keys"}`);
      }
    } catch {
      triggerNotif("error", "Error connecting to backend API.");
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

    try {
      const res = await fetch(`${API_BASE}/data/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: dlSymbol,
          interval: dlInterval,
          from_date: dlFromDate + " 09:15",
          to_date: dlToDate + " 15:30",
          totp: code
        })
      });
      const data = await res.json();
      setDownloading(false);
      if (res.ok) {
        triggerNotif("success", "Dataset downloaded and cataloged in Parquet!");
        fetchCoreData();
      } else {
        triggerNotif("error", `Download failed: ${data.detail || "Server error"}`);
      }
    } catch {
      setDownloading(false);
      triggerNotif("error", "Error requesting download from API.");
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
      
      try {
        const res = await fetch(`${API_BASE}/strategies`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, description: "Editor strategy", code })
        });
        const data = await res.json();
        if (res.ok) {
          triggerNotif("success", "Strategy created in DB!");
          fetchCoreData();
          setSelectedStrategyId(data.id);
        }
      } catch {
        triggerNotif("error", "Failed to save strategy.");
      }
    } else {
      // Update existing
      if (!backendOnline) {
        triggerNotif("success", "Local strategy updated!");
        return;
      }

      try {
        // Find existing metadata
        const stratMeta = strategies.find(s => s.id === selectedStrategyId);
        const res = await fetch(`${API_BASE}/strategies/${selectedStrategyId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: stratMeta?.name || "Strategy",
            description: stratMeta?.description || "",
            code
          })
        });
        if (res.ok) {
          triggerNotif("success", "Strategy code updated successfully!");
          fetchCoreData();
        }
      } catch {
        triggerNotif("error", "Failed to update strategy code.");
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

    if (!backendOnline) {
      runFrontendSimulation();
      return;
    }

    const parts = selectedDataset.split("_");
    const symbol = parts[0];
    const interval = parts.slice(1).join("_");
    triggerNotif("info", `Initiating backtest on ${symbol}...`);

    try {
      // Find start and end date of dataset to use full range
      const catalogItem = datasets.find(d => `${d.symbol}_${d.interval}` === selectedDataset);
      const start_date = catalogItem ? catalogItem.start_date.split(" ")[0] : "2026-06-01";
      const end_date = catalogItem ? catalogItem.end_date.split(" ")[0] : "2026-06-07";

      const res = await fetch(`${API_BASE}/backtest/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          strategy_id: selectedStrategyId,
          symbol,
          interval,
          start_date,
          end_date,
          initial_capital: initialCapital,
          slippage_pct: slippagePct / 100.0,
          trade_type: tradeType,
          max_position_size: maxPositionSize
        })
      });
      
      const data = await res.json();
      if (res.ok) {
        triggerNotif("success", "Backtest run completed successfully!");
        setSelectedRunId(data.run_id);
        fetchCoreData();
        loadBacktestReplay(data.run_id);
        setActiveTab("studio");
      } else {
        triggerNotif("error", `Backtest failed: ${data.detail || "Engine error"}`);
      }
    } catch (e) {
      triggerNotif("error", "Server communication failure during backtest.");
    }
  };

  const loadBacktestReplay = async (runId: string) => {
    if (!backendOnline) return;

    try {
      // 1. Fetch Result Details
      const resDet = await fetch(`${API_BASE}/backtest/results/${runId}`);
      if (resDet.ok) {
        const data = await resDet.json();
        setBacktestDetail(data);
      }

      // 2. Fetch Replay Logs
      const resLogs = await fetch(`${API_BASE}/backtest/logs/${runId}`);
      if (resLogs.ok) {
        const logs = await resLogs.json();
        setReplayEvents(logs);
        setCurrentStep(0);
      }

      // 3. Fetch Research Lab regimes
      const resReg = await fetch(`${API_BASE}/research/regimes/${runId}`);
      if (resReg.ok) {
        const reg = await resReg.json();
        setResearchData(reg);
      }

      // 4. Fetch Capital requirements scaling
      const resCap = await fetch(`${API_BASE}/capital/analysis/${runId}`);
      if (resCap.ok) {
        const cap = await resCap.json();
        setCapitalData(cap);
      }
    } catch {
      triggerNotif("error", "Error loading backtest replay assets.");
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

    try {
      const res = await fetch(`${API_BASE}/backtest/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          strategy_id: selectedStrategyId,
          symbol,
          interval,
          start_date,
          end_date,
          param_grid_json: JSON.stringify(gridObj),
          initial_capital: initialCapital,
          trade_type: tradeType
        })
      });

      const data = await res.json();
      if (res.ok) {
        setOptimizationGrid(data);
        triggerNotif("success", "Optimization grid calculation finished!");
      } else {
        triggerNotif("error", `Optimization error: ${data.detail}`);
      }
    } catch {
      triggerNotif("error", "Server communication failure during optimization.");
    }
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

    try {
      const res = await fetch(`${API_BASE}/strategies/${id}`);
      if (res.ok) {
        const data = await res.json();
        setCode(data.code);
        triggerNotif("success", `Loaded strategy: ${data.name}`);
      }
    } catch {
      triggerNotif("error", "Failed to fetch strategy code.");
    }
  };

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
      const c = ev.candle[currentSymbol];
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
      value: ev.portfolio.positions 
        ? Object.values(ev.portfolio.positions).reduce((acc: number, p: any) => acc + p.qty, 0) 
        : 0
    }));
  }, [replayEvents, currentStep]);

  const handleDatasetChange = async (val: string) => {
    setSelectedDataset(val);
    if (!val) {
      setMaxPositionSize(0);
      return;
    }

    if (backendOnline) {
      try {
        const parts = val.split("_");
        const symbol = parts[0];
        const interval = parts.slice(1).join("_");
        const res = await fetch(`${API_BASE}/data/datasets/${symbol}/${interval}`);
        if (res.ok) {
          const data = await res.json();
          // Initialize slider with the backend's suggested optimal value
          setMaxPositionSize(data.suggested_max_position || 0);
        }
      } catch (err) {
        console.error("Error fetching dataset metadata:", err);
      }
    } else {
      setMaxPositionSize(Math.floor(initialCapital / 500));
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
              { id: "datasets", label: "Datasets", icon: Database },
              { id: "ide", label: "Strategy IDE", icon: Code },
              { id: "studio", label: "Replay Studio", icon: PlayCircle },
              { id: "research", label: "Research Lab", icon: BarChart2 },
              { id: "capital", label: "Capital Studio", icon: Layers },
              { id: "optimizer", label: "Optimizer", icon: PieChart },
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
              {activeTab === "research" && "Classify and attribute strategy performance over trending and ranging markets."}
              {activeTab === "capital" && "Explore margin requirements, drawdown risks, and scaling limits."}
              {activeTab === "optimizer" && "Execute grid-search sweeps to find mathematically optimal strategy weights."}
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
                          <span>Max Position Limit (Quantity)</span>
                          <span className="text-blue-400 font-mono">{maxPositionSize} Qty</span>
                        </label>
                        <input
                          type="range"
                          min="1"
                          max={maxPositionSize > 0 ? Math.max(maxPositionSize * 5, 2000) : 2000}
                          value={maxPositionSize}
                          onChange={e => setMaxPositionSize(Number(e.target.value))}
                          className="w-full accent-blue-500 h-1.5 bg-slate-950 rounded-lg appearance-none cursor-pointer border border-slate-800"
                        />
                        <p className="text-[9px] text-slate-500 mt-1 italic font-medium">Optimal value calculated based on capital vs asset price. Limits total held quantity.</p>
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
                          <td className="text-slate-500">{run.start_time.split(" ")[0]} to {run.end_time.split(" ")[0]}</td>
                          <td className={run.total_pnl >= 0 ? "text-emerald-400 font-semibold" : "text-rose-400 font-semibold"}>
                            ₹{run.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                          </td>
                          <td className="font-bold">{run.sharpe_ratio.toFixed(2)}</td>
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
                          <td className="text-slate-500 font-mono text-[10px]">{d.start_date} - {d.end_date}</td>
                          <td className="font-semibold text-blue-400 font-mono">{d.records_count}</td>
                          <td className="text-slate-600 truncate max-w-xs text-[10px]" title={d.file_path}>
                            {d.file_path}
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

          {/* TAB 3: STRATEGY IDE & MONACO EDITOR */}
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
                        setCode(`# Write your Strategy program here\nclass Strategy:\n    def __init__(self):\n        self.name = "My custom Strategy"\n\n    def on_bar(self, state):\n        return []`);
                        triggerNotif("info", "Created new code buffer. Click Save to name.");
                      }}
                      className="p-1 bg-slate-800 hover:bg-slate-700 text-blue-400 rounded transition-all"
                      title="New Strategy"
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
                        <h5 className="font-semibold text-slate-200 text-xs">{s.name}</h5>
                        <p className="text-[10px] text-slate-500 font-mono mt-1">v{s.version} • {new Date(s.updated_at).toLocaleDateString()}</p>
                      </div>
                    ))}
                    {strategies.length === 0 && (
                      <p className="text-[10px] text-slate-500 text-center py-4">No strategies stored yet.</p>
                    )}
                  </div>
                </div>

                <div className="space-y-3 pt-4 border-t border-slate-800">
                  <button
                    onClick={handleSaveStrategy}
                    className="w-full bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2"
                  >
                    <FileText size={14} />
                    Save Program Code
                  </button>
                  <button
                    onClick={handleRunBacktest}
                    className="w-full bg-emerald-600 hover:bg-emerald-700 text-white rounded font-bold text-xs py-2 transition-all flex items-center justify-center gap-2"
                  >
                    <PlayCircle size={14} />
                    Execute Backtest
                  </button>
                </div>
              </div>

              {/* Monaco IDE view */}
              <div className="glass-panel rounded-xl col-span-3 flex flex-col overflow-hidden relative border border-slate-800">
                <div className="px-4 py-2 bg-slate-950/90 border-b border-slate-800 flex justify-between items-center shrink-0">
                  <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                    <span className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-pulse" />
                    trader.py
                  </div>
                  <span className="text-[10px] text-slate-600 font-mono">Restricted Sandboxed Sandbox Runtime</span>
                </div>
                <div className="flex-1 min-h-0 bg-[#1e1e1e]">
                  <Editor
                    height="100%"
                    defaultLanguage="python"
                    theme="vs-dark"
                    value={code}
                    onChange={(val) => setCode(val || "")}
                    options={{
                      minimap: { enabled: false },
                      fontSize: 13,
                      fontFamily: "Geist Mono, monospace",
                      lineHeight: 20,
                      cursorStyle: "line",
                      tabSize: 4,
                    }}
                  />
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
                    {activeCandles.length > 0 ? (
                      <LightweightChart
                        candles={activeCandles}
                        trades={activeTrades}
                        height={350}
                      />
                    ) : (
                      <div className="w-full h-80 bg-slate-950/60 rounded-xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-500">
                        <AlertTriangle size={32} className="text-slate-600 mb-2 animate-bounce" />
                        <span className="text-xs">No active replay data loaded. Run a backtest or load a past run.</span>
                      </div>
                    )}
                  </div>

                  {/* Position Exposure Baseline Chart */}
                  <div className="glass-panel rounded-xl overflow-hidden h-32 flex flex-col shrink-0 border border-slate-800/50">
                    <div className="px-3 py-1.5 bg-slate-950/80 border-b border-slate-800 text-[10px] font-bold font-mono text-slate-400 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Layers size={12} className="text-blue-400" />
                        <span>Net Position Exposure (Inventory)</span>
                      </div>
                      <span className={positionCurveData[positionCurveData.length - 1]?.value >= 0 ? "text-emerald-400" : "text-rose-400"}>
                        {positionCurveData[positionCurveData.length - 1]?.value || 0} Units
                      </span>
                    </div>
                    <div className="flex-1 p-2 bg-slate-950/40 relative">
                       {/* Zero Baseline reference */}
                       <div className="absolute left-0 right-0 top-1/2 border-t border-slate-800/50 z-0" />
                       
                       <div className="absolute inset-0 flex items-center px-2 gap-[1px] z-10">
                          {(() => {
                            const dataToDisplay = positionCurveData.slice(-100);
                            const maxAbs = Math.max(...dataToDisplay.map(v => Math.abs(v.value)), 1);
                            return dataToDisplay.map((d, i) => {
                              const height = (Math.abs(d.value) / maxAbs) * 50;
                              return (
                                <div key={i} className="flex-1 flex flex-col h-full">
                                  <div className="flex-1 flex flex-col justify-end">
                                    {d.value > 0 && <div className="bg-emerald-500/40 w-full rounded-t-sm transition-all duration-300" style={{ height: `${height}%` }} />}
                                  </div>
                                  <div className="flex-1 flex flex-col justify-start">
                                    {d.value < 0 && <div className="bg-rose-500/40 w-full rounded-b-sm transition-all duration-300" style={{ height: `${height}%` }} />}
                                  </div>
                                </div>
                              );
                            });
                          })()}
                       </div>
                    </div>
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
                            <span className="text-slate-200 font-mono">₹{t.price.toFixed(1)}</span>
                          </div>
                          <div className="flex justify-between text-[10px] text-slate-500">
                            <span>Fees: ₹{t.total_charges.toFixed(1)}</span>
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
            <div className="space-y-6">
              {researchData ? (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Regime Attribution Table */}
                  <div className="glass-panel p-5 rounded-xl col-span-2 space-y-4">
                    <h4 className="font-bold text-slate-200 text-sm">Strategy Performance Attribution by Regime</h4>
                    
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs text-slate-400 border-collapse">
                        <thead>
                          <tr className="border-b border-slate-800 text-slate-300 font-medium">
                            <th className="py-2.5">Market Regime</th>
                            <th>Trade Count</th>
                            <th>Total Return PnL</th>
                            <th>Average Trade Profit</th>
                            <th className="text-right">Win Rate</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/50">
                          {Object.entries(researchData.regime_attribution).map(([regime, data]: [string, any]) => (
                            <tr key={regime} className="hover:bg-slate-900/30">
                              <td className="py-3 font-bold text-slate-200">
                                {regime.replace("_", " ")}
                              </td>
                              <td className="font-mono">{data.trade_count}</td>
                              <td className={`font-semibold ${data.total_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                ₹{data.total_pnl.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                              </td>
                              <td className="font-mono">₹{data.avg_pnl.toFixed(1)}</td>
                              <td className="text-right font-bold text-slate-300">{(data.win_rate * 100).toFixed(0)}%</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Market Distribution Chart preview */}
                  <div className="glass-panel p-5 rounded-xl space-y-4">
                    <h4 className="font-bold text-slate-200 text-sm">Historical Market Regime Representation</h4>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Distribution of trading sessions/bars cataloged in the downloaded dataset.
                    </p>

                    <div className="space-y-3 pt-2">
                      {Object.entries(researchData.market_regime_distribution).map(([regime, weight]: [string, any]) => (
                        <div key={regime} className="space-y-1">
                          <div className="flex justify-between text-[11px]">
                            <span className="text-slate-400 font-semibold">{regime.replace("_", " ")}</span>
                            <span className="font-mono text-slate-300">{(weight * 100).toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden border border-slate-900">
                            <div
                              className="bg-blue-500 h-full rounded-full"
                              style={{ width: `${weight * 100}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="glass-panel p-8 text-center text-slate-500 rounded-xl">
                  <BarChart2 size={32} className="mx-auto mb-2 text-slate-700 animate-pulse" />
                  <span className="text-xs">Select a past backtest run in dashboard to load research regime reports.</span>
                </div>
              )}
            </div>
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
                              <td className="font-mono text-slate-500">{row.total_trades}</td>
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
        </div>
      </main>

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
