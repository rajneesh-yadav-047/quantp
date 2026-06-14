"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Play, Pause, Square, TrendingUp, TrendingDown, Activity,
  DollarSign, Wallet, BarChart3, ArrowLeft, Radio, Shield,
  Clock, AlertTriangle, CheckCircle2, XCircle, RefreshCw,
  ChevronDown, ChevronUp, Bell, PlusCircle, RotateCcw
} from "lucide-react";
import { api, formatApiError } from "../../lib/api-client";
import LightweightChart from "../../components/LightweightChart";

// Types
interface LiveTrade {
  id: string;
  symbol: string;
  direction: "BUY" | "SELL";
  price: number;
  qty: number;
  value: number;
  brokerage: number;
  stt: number;
  exc_charges: number;
  gst: number;
  sebi_charges: number;
  stamp_duty: number;
  total_charges: number;
  charges_source: string;
  timestamp: string;
}

interface PnLSnapshot {
  id: string;
  cash: number;
  equity: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_fees: number;
  total_pnl: number;
  margin_used: number;
  margin_free: number;
  position_count: number;
  total_qty: number;
  positions: Record<string, { qty: number; avg_price: number; unrealized_pnl: number; realized_pnl: number }>;
  timestamp: string;
}

interface DeploymentEvent {
  id: string;
  event_type: string;
  message: string;
  data: any;
  timestamp: string;
}

interface DeploymentStatus {
  deployment_id: string;
  status: string;
  running: boolean;
  symbol: string;
  interval: string;
  step: number;
  initial_capital: number;
  current_price: number | null;
  smartapi_connected: boolean;
  market_data_active: boolean;
  mds_subscribed: boolean;
  portfolio: {
    cash: number;
    equity: number;
    unrealized_pnl: number;
    total_fees: number;
    total_pnl: number;
    margin_used: number;
    margin_free: number;
    positions: Record<string, any>;
  };
  active_orders: any[];
  poll_interval: number;
}

interface Deployment {
  deployment_id: string;
  status: string;
  running: boolean;
  symbol: string | null;
  interval: string | null;
  portfolio: any;
}

export default function LiveTradingPage() {
  const router = useRouter();
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [selectedDeploymentId, setSelectedDeploymentId] = useState<string>("");
  const [status, setStatus] = useState<DeploymentStatus | null>(null);
  const [trades, setTrades] = useState<LiveTrade[]>([]);
  const [pnlHistory, setPnlHistory] = useState<PnLSnapshot[]>([]);
  const [events, setEvents] = useState<DeploymentEvent[]>([]);
  const [candles, setCandles] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [notif, setNotif] = useState<{ type: "success" | "error" | "info"; msg: string } | null>(null);
  const [sseConnected, setSseConnected] = useState(false);
  const [showChargesDetail, setShowChargesDetail] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Manual Trading States
  const [manualDirection, setManualDirection] = useState<"BUY" | "SELL">("BUY");
  const [manualQty, setManualQty] = useState<number>(10);
  const [manualOrderType, setManualOrderType] = useState<"MARKET" | "LIMIT">("MARKET");
  const [manualPrice, setManualPrice] = useState<string>("");
  const [manualTradingPending, setManualTradingPending] = useState(false);

  // Capital Reset State
  const [capitalInput, setCapitalInput] = useState<string>("100000");
  const [capitalResetPending, setCapitalResetPending] = useState(false);

  const [marketDataActive, setMarketDataActive] = useState(false);
  const [showTotpModal, setShowTotpModal] = useState(false);
  const [totpInput, setTotpInput] = useState("");
  const [authPending, setAuthPending] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const triggerNotif = useCallback((type: "success" | "error" | "info", msg: string) => {
    setNotif({ type, msg });
    setTimeout(() => setNotif(null), 5000);
  }, []);

  // Fetch all deployments
  const fetchDeployments = useCallback(async () => {
    const result = await api.get("/live/all");
    if (result.ok && result.data) {
      setDeployments(result.data);
      if (!selectedDeploymentId && result.data.length > 0) {
        setSelectedDeploymentId(result.data[0].deployment_id);
      }
    }
  }, [selectedDeploymentId]);

  // Fetch status for selected deployment
  const fetchStatus = useCallback(async () => {
    if (!selectedDeploymentId) return;
    const result = await api.get(`/live/status/${selectedDeploymentId}`);
    if (result.ok && result.data) {
      setStatus(result.data);
      setMarketDataActive(result.data.market_data_active || false);
      if (result.data.current_price && !manualPrice) {
        setManualPrice(result.data.current_price.toString());
      }
    }
  }, [selectedDeploymentId, manualPrice]);

  // Fetch candles
  const fetchCandles = useCallback(async () => {
    if (!selectedDeploymentId) return;
    const result = await api.get(`/live/candles/${selectedDeploymentId}`);
    if (result.ok && result.data) {
      setCandles(result.data);
    }
  }, [selectedDeploymentId]);

  // Fetch market data service status
  const fetchMarketDataStatus = useCallback(async () => {
    const result = await api.get("/live/market-data/status");
    if (result.ok && result.data) {
      setMarketDataActive(result.data.status === "connected" || result.data.running);
    }
  }, []);

  // Fetch trades
  const fetchTrades = useCallback(async () => {
    if (!selectedDeploymentId) return;
    const result = await api.get(`/live/trades/${selectedDeploymentId}?limit=50`);
    if (result.ok && result.data) {
      setTrades(result.data);
    }
  }, [selectedDeploymentId]);

  // Fetch PnL
  const fetchPnl = useCallback(async () => {
    if (!selectedDeploymentId) return;
    const result = await api.get(`/live/pnl/${selectedDeploymentId}?limit=100`);
    if (result.ok && result.data) {
      setPnlHistory(result.data);
    }
  }, [selectedDeploymentId]);

  // Fetch events
  const fetchEvents = useCallback(async () => {
    if (!selectedDeploymentId) return;
    const result = await api.get(`/live/events/${selectedDeploymentId}?limit=50`);
    if (result.ok && result.data) {
      setEvents(result.data);
    }
  }, [selectedDeploymentId]);

  // Setup SSE stream
  const connectSSE = useCallback(() => {
    if (!selectedDeploymentId) return;
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource(`/api/live/stream/${selectedDeploymentId}`);
    eventSourceRef.current = es;

    es.onopen = () => {
      setSseConnected(true);
    };

    es.addEventListener("tick", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.candle && status?.symbol) {
          const symCandle = data.candle[status.symbol];
          if (symCandle) {
            setCandles(prev => {
              const time = symCandle.time;
              const idx = prev.findIndex(c => c.time === time);
              if (idx > -1) {
                const copy = [...prev];
                copy[idx] = symCandle;
                return copy;
              } else {
                return [...prev, symCandle];
              }
            });
          }
        }
        if (data.portfolio) {
          setStatus(prev => prev ? {
            ...prev,
            portfolio: data.portfolio,
            step: data.step ?? prev.step,
            current_price: data.ltp ?? data.candle?.[prev.symbol]?.close ?? prev.current_price
          } : null);
        }
        if (data.ltp !== undefined) {
          setMarketDataActive(true);
        }
        if (data.orders_filled && data.orders_filled.length > 0) {
          fetchTrades();
          fetchPnl();
        }
      } catch (e) {}
    });

    es.addEventListener("fill", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.trade) {
          fetchTrades();
          fetchPnl();
          fetchEvents();
        }
      } catch (e) {}
    });

    es.onerror = () => {
      setSseConnected(false);
      es.close();
    };

    return () => {
      es.close();
      setSseConnected(false);
    };
  }, [selectedDeploymentId, status?.symbol, fetchTrades, fetchPnl, fetchEvents]);

  // Initial load
  useEffect(() => {
    fetchDeployments();
  }, [fetchDeployments]);

  // Load data when deployment changes
  useEffect(() => {
    if (!selectedDeploymentId) return;
    fetchStatus();
    fetchTrades();
    fetchPnl();
    fetchEvents();
    fetchCandles();
    connectSSE();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        setSseConnected(false);
      }
    };
  }, [selectedDeploymentId, fetchStatus, fetchTrades, fetchPnl, fetchEvents, fetchCandles, connectSSE]);

  // Auto-refresh polling (fallback when SSE is not connected)
  useEffect(() => {
    if (!autoRefresh || !selectedDeploymentId) return;

    refreshIntervalRef.current = setInterval(() => {
      if (!sseConnected) {
        fetchStatus();
        fetchTrades();
        fetchPnl();
        fetchCandles();
      }
      fetchMarketDataStatus();
    }, 3000);

    return () => {
      if (refreshIntervalRef.current) clearInterval(refreshIntervalRef.current);
    };
  }, [autoRefresh, selectedDeploymentId, sseConnected, fetchStatus, fetchTrades, fetchPnl, fetchCandles, fetchMarketDataStatus]);

  // Actions
  const handleStart = async () => {
    if (!selectedDeploymentId) return;
    setIsLoading(true);
    const result = await api.post("/live/start", {
      deployment_id: selectedDeploymentId,
      slippage_pct: 0.0,
      use_real_charges: true,
    });
    setIsLoading(false);
    if (result.ok) {
      triggerNotif("success", result.data?.message || "Mock deployment started!");
      fetchDeployments();
      fetchStatus();
      fetchCandles();
      connectSSE();
    } else {
      const errMsg = formatApiError(result, "Start failed");
      if (errMsg.toLowerCase().includes("smartapi not connected") || errMsg.toLowerCase().includes("totp")) {
        setShowTotpModal(true);
      } else {
        triggerNotif("error", errMsg);
      }
    }
  };

  const handleTotpSubmit = async () => {
    if (totpInput.length !== 6) {
      triggerNotif("error", "Enter a 6-digit TOTP code.");
      return;
    }
    setAuthPending(true);
    const authResult = await api.post("/auth/smartapi/connect", { totp: totpInput });
    setAuthPending(false);
    if (authResult.ok) {
      setShowTotpModal(false);
      setTotpInput("");
      triggerNotif("success", "SmartAPI connected! Retrying deployment start...");
      await handleStart();
    } else {
      triggerNotif("error", formatApiError(authResult, "SmartAPI auth failed"));
    }
  };

  const handleStop = async () => {
    if (!selectedDeploymentId) return;
    setIsLoading(true);
    const result = await api.post(`/live/stop/${selectedDeploymentId}`, {});
    setIsLoading(false);
    if (result.ok) {
      triggerNotif("info", "Mock deployment stopped.");
      fetchDeployments();
      fetchStatus();
      setCandles([]);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        setSseConnected(false);
      }
    } else {
      triggerNotif("error", formatApiError(result, "Stop failed"));
    }
  };

  const handlePause = async () => {
    if (!selectedDeploymentId) return;
    const result = await api.post(`/live/pause/${selectedDeploymentId}`, {});
    if (result.ok) {
      triggerNotif("info", "Deployment paused");
      fetchStatus();
    }
  };

  const handleResume = async () => {
    if (!selectedDeploymentId) return;
    const result = await api.post(`/live/resume/${selectedDeploymentId}`, {});
    if (result.ok) {
      triggerNotif("success", "Deployment resumed");
      fetchStatus();
    }
  };

  // Submit manual order
  const handleExecuteManualTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDeploymentId) return;
    
    setManualTradingPending(true);
    const orderPrice = manualOrderType === "LIMIT" ? parseFloat(manualPrice) : null;
    const result = await api.post("/live/order", {
      deployment_id: selectedDeploymentId,
      direction: manualDirection,
      qty: manualQty,
      price: orderPrice,
      order_type: manualOrderType
    });
    setManualTradingPending(false);

    if (result.ok) {
      triggerNotif("success", result.data?.message || "Manual trade executed!");
      fetchTrades();
      fetchPnl();
      fetchEvents();
      // Keep price input updated
      if (status && result.data?.portfolio) {
        setStatus(prev => prev ? { ...prev, portfolio: result.data.portfolio } : null);
      }
    } else {
      triggerNotif("error", formatApiError(result, "Order execution failed"));
    }
  };

  // Reset starting capital
  const handleResetCapital = async () => {
    if (!selectedDeploymentId) return;
    
    const amt = parseFloat(capitalInput);
    if (isNaN(amt) || amt <= 0) {
      triggerNotif("error", "Please enter a valid starting capital amount.");
      return;
    }

    setCapitalResetPending(true);
    const result = await api.post("/live/reset-capital", {
      deployment_id: selectedDeploymentId,
      amount: amt
    });
    setCapitalResetPending(false);

    if (result.ok) {
      triggerNotif("success", result.data?.message || "Starting capital reset successfully!");
      fetchStatus();
      fetchTrades();
      fetchPnl();
      fetchEvents();
    } else {
      triggerNotif("error", formatApiError(result, "Reset capital failed"));
    }
  };

  // Convert trade timestamp to UTC clock-time seconds to align markers with chart
  const getTradeUtcClockTimeSeconds = (timestampStr: string) => {
    if (!timestampStr) return 0;
    
    // Check if it's already a string representation of a number
    if (/^\d+$/.test(timestampStr)) {
      return parseInt(timestampStr);
    }

    // Attempt direct regex extraction for local time parts to avoid time offsets
    const match = timestampStr.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/);
    if (match) {
      const y = parseInt(match[1]);
      const m = parseInt(match[2]) - 1;
      const d = parseInt(match[3]);
      const h = parseInt(match[4]);
      const min = parseInt(match[5]);
      const s = parseInt(match[6]);
      const utcDate = new Date(Date.UTC(y, m, d, h, min, s));
      return Math.floor(utcDate.getTime() / 1000);
    }
    
    const dt = new Date(timestampStr);
    return isNaN(dt.getTime()) ? 0 : Math.floor(dt.getTime() / 1000);
  };

  const chartTrades = trades.map(t => ({
    time: String(getTradeUtcClockTimeSeconds(t.timestamp)),
    direction: t.direction,
    price: t.price,
    qty: t.qty
  })).filter(t => t.time !== "0");

  const selectedDeployment = deployments.find(d => d.deployment_id === selectedDeploymentId);
  const isRunning = status?.status === "running";
  const isPaused = status?.status === "paused";

  const latestPnl = pnlHistory[0];
  const previousPnl = pnlHistory[1];
  const pnlChange = latestPnl && previousPnl
    ? latestPnl.equity - previousPnl.equity
    : 0;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-12">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/")}
              className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <Radio className="w-5 h-5 text-emerald-400" />
              <h1 className="text-lg font-bold">Live Mock Trading</h1>
            </div>
            <span className="px-2 py-0.5 text-xs bg-amber-500/20 text-amber-400 rounded border border-amber-500/30">
              PAPER MODE
            </span>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <Shield className="w-4 h-4 text-emerald-400" />
              <span>No real money</span>
            </div>
            {sseConnected ? (
              <span className="flex items-center gap-1 text-xs text-emerald-400">
                <Activity className="w-3 h-3 animate-pulse" /> Live Stream
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs text-slate-500">
                <Clock className="w-3 h-3" /> Polling
              </span>
            )}
          </div>
        </div>
      </header>

      {/* Notification */}
      {notif && (
        <div className={`fixed top-16 right-4 z-50 px-4 py-3 rounded-lg shadow-lg border text-sm max-w-sm ${
          notif.type === "success" ? "bg-emerald-950/90 border-emerald-700 text-emerald-200" :
          notif.type === "error" ? "bg-red-950/90 border-red-700 text-red-200" :
          "bg-blue-950/90 border-blue-700 text-blue-200"
        }`}>
          {notif.msg}
        </div>
      )}

      {/* TOTP Modal */}
      {showTotpModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl">
            <div className="flex items-center gap-2 mb-4">
              <Shield className="w-5 h-5 text-amber-400" />
              <h3 className="font-semibold text-lg">SmartAPI Authentication Required</h3>
            </div>
            <p className="text-sm text-slate-400 mb-4">
              Enter the 6-digit TOTP from your Angel One authenticator app to connect live market data.
            </p>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={totpInput}
              onChange={(e) => setTotpInput(e.target.value.replace(/\D/g, ""))}
              placeholder="000000"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-center text-lg tracking-[0.5em] font-mono focus:outline-none focus:border-blue-500 mb-4"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") handleTotpSubmit();
                if (e.key === "Escape") setShowTotpModal(false);
              }}
            />
            <div className="flex items-center gap-2">
              <button
                onClick={handleTotpSubmit}
                disabled={authPending || totpInput.length !== 6}
                className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
              >
                {authPending ? "Connecting..." : "Connect"}
              </button>
              <button
                onClick={() => setShowTotpModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm font-medium transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Top bar control layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Deployment Selector */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
            <div>
              <label className="text-xs text-slate-400 uppercase tracking-wider mb-2 block font-semibold">Deployment</label>
              <select
                value={selectedDeploymentId}
                onChange={(e) => setSelectedDeploymentId(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
              >
                <option value="">Select deployment...</option>
                {deployments.map(d => (
                  <option key={d.deployment_id} value={d.deployment_id}>
                    {d.symbol || "No symbol"} — {d.status} {d.running ? "(running)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="mt-4 flex items-center gap-2">
              {isRunning ? (
                <>
                  <button onClick={handlePause} disabled={isLoading} className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 rounded-lg text-sm font-semibold transition-colors">
                    <Pause className="w-4 h-4" /> Pause
                  </button>
                  <button onClick={handleStop} disabled={isLoading} className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg text-sm font-semibold transition-colors">
                    <Square className="w-4 h-4" /> Stop
                  </button>
                </>
              ) : isPaused ? (
                <>
                  <button onClick={handleResume} disabled={isLoading} className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-sm font-semibold transition-colors">
                    <Play className="w-4 h-4" /> Resume
                  </button>
                  <button onClick={handleStop} disabled={isLoading} className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg text-sm font-semibold transition-colors">
                    <Square className="w-4 h-4" /> Stop
                  </button>
                </>
              ) : (
                <button onClick={handleStart} disabled={isLoading || !selectedDeploymentId} className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-sm font-semibold transition-colors">
                  <Play className="w-4 h-4" />
                  {isLoading ? "Starting..." : "Start Mock Trading"}
                </button>
              )}
            </div>
          </div>

          {/* Capital Reset */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
            <div>
              <label className="text-xs text-slate-400 uppercase tracking-wider mb-2 block font-semibold">Starting Capital Config</label>
              <div className="relative">
                <span className="absolute left-3 top-2.5 text-slate-500 text-xs font-semibold">₹</span>
                <input
                  type="text"
                  value={capitalInput}
                  onChange={(e) => setCapitalInput(e.target.value.replace(/\D/g, ""))}
                  placeholder="100000"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-7 pr-3 py-2 text-sm focus:outline-none focus:border-blue-500 font-semibold"
                />
              </div>
            </div>
            <button
              onClick={handleResetCapital}
              disabled={capitalResetPending || !selectedDeploymentId}
              className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 disabled:opacity-50 rounded-lg text-sm font-semibold transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              {capitalResetPending ? "Resetting..." : "Reset Capital & Clear Positions"}
            </button>
          </div>

          {/* Active Asset Info */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-3.5 h-3.5 rounded-full ${status?.smartapi_connected ? "bg-emerald-400" : "bg-red-400"} shadow-lg`} />
              <div>
                <div className="text-base font-bold">{status?.symbol || selectedDeployment?.symbol || "—"}</div>
                <div className="text-xs text-slate-400 font-semibold">{status?.interval || "—"} • Step {status?.step ?? 0}</div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-xl font-mono font-bold text-slate-100">
                {status?.current_price != null ? `₹${status.current_price.toFixed(2)}` : "—"}
              </div>
              <div className="flex items-center justify-end gap-1.5 mt-1">
                {status?.smartapi_connected ? (
                  marketDataActive || status?.market_data_active ? (
                    <span className="flex items-center gap-1 text-[10px] text-emerald-400 font-bold bg-emerald-950/40 border border-emerald-900 px-1.5 py-0.5 rounded">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Real-time Feed
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[10px] text-amber-400 font-bold bg-amber-950/40 border border-amber-900 px-1.5 py-0.5 rounded">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                      Closed Simulation
                    </span>
                  )
                ) : (
                  <span className="flex items-center gap-1 text-[10px] text-red-400 font-bold bg-red-950/40 border border-red-900 px-1.5 py-0.5 rounded">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                    Disconnected
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Portfolio Summary Cards */}
        {status?.portfolio && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-1 font-bold">Equity</div>
              <div className="text-2xl font-bold text-slate-100 font-mono">₹{status.portfolio.equity.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</div>
              <div className={`text-xs mt-1.5 font-semibold ${pnlChange >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {pnlChange >= 0 ? "+" : ""}₹{pnlChange.toFixed(2)}
              </div>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-1 font-bold">Total PnL</div>
              <div className={`text-2xl font-bold font-mono ${status.portfolio.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {status.portfolio.total_pnl >= 0 ? "+" : ""}₹{status.portfolio.total_pnl.toFixed(2)}
              </div>
              <div className="text-xs text-slate-500 mt-2 font-medium">Realized + Unrealized</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-1 font-bold">Cash Balance</div>
              <div className="text-2xl font-bold text-slate-100 font-mono">₹{status.portfolio.cash.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</div>
              <div className="text-xs text-slate-500 mt-2 font-medium">Available to Trade</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-1 font-bold">Taxes & Charges</div>
              <div className="text-2xl font-bold text-amber-500 font-mono">₹{status.portfolio.total_fees.toFixed(2)}</div>
              <div className="text-xs text-slate-500 mt-2 font-medium">Brokerage + STT + GST</div>
            </div>
          </div>
        )}

        {/* Main interactive section */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
          {/* Main Chart Column */}
          <div className="lg:col-span-3 space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl p-4">
              <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-blue-400" />
                Live Candlestick Feed & Orders (Replay / Simulated Ticks)
              </h3>
              {candles.length > 0 ? (
                <LightweightChart candles={candles} trades={chartTrades} height={420} showEmaFast={false} showEmaSlow={false} />
              ) : (
                <div className="h-[420px] bg-slate-950 rounded-lg flex items-center justify-center border border-slate-850 text-slate-500 text-sm">
                  {selectedDeploymentId ? "Waiting for first tick to populate chart..." : "Select a deployment to view chart"}
                </div>
              )}
            </div>
          </div>

          {/* Manual Order Terminal Panel */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-2xl space-y-4">
            <h3 className="font-bold text-slate-200 text-sm flex items-center gap-2 border-b border-slate-800 pb-3">
              <PlusCircle className="w-5 h-5 text-blue-400" />
              Manual Trade Terminal
            </h3>

            <form onSubmit={handleExecuteManualTrade} className="space-y-4">
              {/* Asset Display */}
              <div>
                <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Asset Symbol</label>
                <div className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-300 font-bold text-xs">
                  {status?.symbol || selectedDeployment?.symbol || "Select Deployment First"}
                </div>
              </div>

              {/* Buy/Sell Direction */}
              <div>
                <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Direction</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setManualDirection("BUY")}
                    className={`py-1.5 rounded text-xs font-bold transition-all ${
                      manualDirection === "BUY"
                        ? "bg-emerald-600 text-white shadow"
                        : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-850"
                    }`}
                  >
                    BUY
                  </button>
                  <button
                    type="button"
                    onClick={() => setManualDirection("SELL")}
                    className={`py-1.5 rounded text-xs font-bold transition-all ${
                      manualDirection === "SELL"
                        ? "bg-red-600 text-white shadow"
                        : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-850"
                    }`}
                  >
                    SELL
                  </button>
                </div>
              </div>

              {/* Quantity */}
              <div>
                <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Quantity (Qty)</label>
                <input
                  type="number"
                  min={1}
                  value={manualQty}
                  onChange={(e) => setManualQty(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500 font-semibold font-mono"
                />
              </div>

              {/* Order Type (Market/Limit) */}
              <div>
                <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Order Type</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setManualOrderType("MARKET")}
                    className={`py-1.5 rounded text-xs font-bold transition-all ${
                      manualOrderType === "MARKET"
                        ? "bg-slate-800 text-blue-400 border border-blue-900"
                        : "bg-slate-950 text-slate-400 border border-slate-850"
                    }`}
                  >
                    MARKET
                  </button>
                  <button
                    type="button"
                    onClick={() => setManualOrderType("LIMIT")}
                    className={`py-1.5 rounded text-xs font-bold transition-all ${
                      manualOrderType === "LIMIT"
                        ? "bg-slate-800 text-blue-400 border border-blue-900"
                        : "bg-slate-950 text-slate-400 border border-slate-850"
                    }`}
                  >
                    LIMIT
                  </button>
                </div>
              </div>

              {/* Limit Price */}
              {manualOrderType === "LIMIT" && (
                <div>
                  <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Limit Price (₹)</label>
                  <input
                    type="text"
                    value={manualPrice}
                    onChange={(e) => setManualPrice(e.target.value)}
                    className="w-full text-xs bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500 font-semibold font-mono"
                  />
                </div>
              )}

              {/* Execute Trade Button */}
              <button
                type="submit"
                disabled={manualTradingPending || !selectedDeploymentId}
                className={`w-full text-white font-bold text-xs py-2 rounded transition-all flex items-center justify-center gap-2 ${
                  manualDirection === "BUY"
                    ? "bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-800 disabled:text-slate-500"
                    : "bg-red-600 hover:bg-red-700 disabled:bg-slate-800 disabled:text-slate-500"
                }`}
              >
                {manualTradingPending ? (
                  <RefreshCw size={14} className="animate-spin" />
                ) : (
                  <>
                    {manualDirection === "BUY" ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                    Execute Manual {manualDirection}
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Detailed Logs, Trades & Charges */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Position & Trades lists */}
          <div className="lg:col-span-2 space-y-6">
            {/* Positions Table */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
              <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Wallet className="w-4 h-4 text-emerald-400" />
                  <h3 className="font-semibold text-sm">Active Positions</h3>
                </div>
                <span className="text-xs text-slate-500 font-semibold">
                  {Object.keys(status?.portfolio?.positions || {}).length} open
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-400 border-b border-slate-800 text-left bg-slate-950/40">
                      <th className="px-4 py-2">Symbol</th>
                      <th className="px-4 py-2">Quantity</th>
                      <th className="px-4 py-2">Avg Purchase Price</th>
                      <th className="px-4 py-2 text-right">Current Value</th>
                      <th className="px-4 py-2 text-right">Unrealized P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.keys(status?.portfolio?.positions || {}).length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-4 py-6 text-center text-slate-500 font-medium">
                          No open positions. Use the terminal to place paper trades.
                        </td>
                      </tr>
                    )}
                    {Object.entries(status?.portfolio?.positions || {}).map(([sym, pos]: [string, any]) => {
                      const curVal = pos.qty * (status?.current_price || pos.avg_price);
                      return (
                        <tr key={sym} className="border-b border-slate-800/40 hover:bg-slate-800/40 font-mono">
                          <td className="px-4 py-2.5 font-bold text-slate-200">{sym}</td>
                          <td className={`px-4 py-2.5 font-bold ${pos.qty > 0 ? "text-emerald-400" : "text-red-400"}`}>
                            {pos.qty > 0 ? "+" : ""}{pos.qty}
                          </td>
                          <td className="px-4 py-2.5">₹{pos.avg_price.toFixed(2)}</td>
                          <td className="px-4 py-2.5 text-right text-slate-300">₹{curVal.toFixed(2)}</td>
                          <td className={`px-4 py-2.5 text-right font-bold ${pos.unrealized_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                            ₹{pos.unrealized_pnl.toFixed(2)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Trades History Table */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
              <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-blue-400" />
                  <h3 className="font-semibold text-sm">Recent Trades & Fees</h3>
                </div>
                <span className="text-xs text-slate-500 font-semibold">{trades.length} trades</span>
              </div>
              <div className="overflow-x-auto max-h-72 custom-scrollbar">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-400 border-b border-slate-800 text-left bg-slate-950/40 sticky top-0">
                      <th className="px-4 py-2">Timestamp</th>
                      <th className="px-4 py-2">Symbol</th>
                      <th className="px-4 py-2">Type</th>
                      <th className="px-4 py-2 text-right">Qty</th>
                      <th className="px-4 py-2 text-right">Price</th>
                      <th className="px-4 py-2 text-right">Value</th>
                      <th className="px-4 py-2 text-right">Charges</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.length === 0 && (
                      <tr>
                        <td colSpan={7} className="px-4 py-6 text-center text-slate-500 font-medium">
                          No trades generated yet.
                        </td>
                      </tr>
                    )}
                    {trades.map((trade) => {
                      const dt = new Date(trade.timestamp);
                      const displayTime = isNaN(dt.getTime()) 
                        ? trade.timestamp 
                        : dt.toLocaleTimeString("en-IN", { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                      return (
                        <tr key={trade.id} className="border-b border-slate-800/40 hover:bg-slate-800/40 font-mono">
                          <td className="px-4 py-2 text-slate-500">{displayTime}</td>
                          <td className="px-4 py-2 font-bold text-slate-200">{trade.symbol}</td>
                          <td className="px-4 py-2">
                            <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                              trade.direction === "BUY" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-950" : "bg-red-500/10 text-red-400 border border-red-950"
                            }`}>
                              {trade.direction}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-right">{trade.qty}</td>
                          <td className="px-4 py-2 text-right text-slate-300">₹{trade.price.toFixed(2)}</td>
                          <td className="px-4 py-2 text-right text-slate-300">₹{trade.value.toFixed(2)}</td>
                          <td className="px-4 py-2 text-right text-amber-500 font-bold">
                            ₹{trade.total_charges.toFixed(2)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Right column: Event Logs & Charges */}
          <div className="space-y-6">
            {/* Event Logs */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg flex flex-col h-[320px]">
              <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 text-purple-400" />
                  <h3 className="font-semibold text-sm">Deployment Events</h3>
                </div>
                <span className="text-xs text-slate-500 font-mono font-semibold">{events.length}</span>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
                {events.length === 0 && (
                  <div className="text-center text-slate-500 text-xs py-8">
                    No deployment events logged
                  </div>
                )}
                {events.map((event) => {
                  const dt = new Date(event.timestamp);
                  const displayTime = isNaN(dt.getTime()) ? event.timestamp : dt.toLocaleTimeString("en-IN");
                  return (
                    <div key={event.id} className="text-xs leading-relaxed border-b border-slate-850 pb-2">
                      <div className="flex items-start gap-2">
                        {event.event_type === "fill" && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />}
                        {event.event_type === "error" && <XCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" />}
                        {event.event_type === "margin_call" && <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />}
                        {event.event_type === "start" && <Play className="w-3.5 h-3.5 text-blue-400 mt-0.5 shrink-0" />}
                        {event.event_type === "stop" && <Square className="w-3.5 h-3.5 text-slate-400 mt-0.5 shrink-0" />}
                        {!["fill", "error", "margin_call", "start", "stop"].includes(event.event_type) && (
                          <Activity className="w-3.5 h-3.5 text-slate-400 mt-0.5 shrink-0" />
                        )}
                        <div className="flex-1">
                          <div className="text-slate-300 font-medium">{event.message}</div>
                          <div className="text-[10px] text-slate-500 font-mono mt-0.5">{displayTime}</div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Charges Breakdown Panel */}
            {trades.length > 0 && (
              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
                <button
                  onClick={() => setShowChargesDetail(!showChargesDetail)}
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-800/50 transition-colors border-b border-slate-800"
                >
                  <div className="flex items-center gap-2">
                    <DollarSign className="w-4 h-4 text-amber-500" />
                    <h3 className="font-semibold text-sm">Tax & Charges Breakdown</h3>
                  </div>
                  {showChargesDetail ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
                {showChargesDetail && (
                  <div className="p-4 space-y-2.5 font-mono text-xs">
                    {(() => {
                      const totals = trades.reduce((acc, t) => ({
                        brokerage: acc.brokerage + t.brokerage,
                        stt: acc.stt + t.stt,
                        exc: acc.exc + t.exc_charges,
                        gst: acc.gst + t.gst,
                        sebi: acc.sebi + t.sebi_charges,
                        stamp: acc.stamp + t.stamp_duty,
                        total: acc.total + t.total_charges,
                      }), { brokerage: 0, stt: 0, exc: 0, gst: 0, sebi: 0, stamp: 0, total: 0 });
                      return (
                        <>
                          <div className="flex justify-between"><span className="text-slate-400">Brokerage</span><span>₹{totals.brokerage.toFixed(2)}</span></div>
                          <div className="flex justify-between"><span className="text-slate-400">STT / CTT</span><span>₹{totals.stt.toFixed(2)}</span></div>
                          <div className="flex justify-between"><span className="text-slate-400">Exchange Charges</span><span>₹{totals.exc.toFixed(2)}</span></div>
                          <div className="flex justify-between"><span className="text-slate-400">GST (18%)</span><span>₹{totals.gst.toFixed(2)}</span></div>
                          <div className="flex justify-between"><span className="text-slate-400">SEBI Turnovers</span><span>₹{totals.sebi.toFixed(2)}</span></div>
                          <div className="flex justify-between"><span className="text-slate-400">Stamp Duty</span><span>₹{totals.stamp.toFixed(2)}</span></div>
                          <div className="border-t border-slate-800 pt-2 flex justify-between font-bold text-sm">
                            <span className="text-amber-500">Total Frictional Cost</span>
                            <span className="text-amber-500">₹{totals.total.toFixed(2)}</span>
                          </div>
                        </>
                      );
                    })()}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Footer Disclaimer */}
        <div className="p-4 bg-amber-950/10 border border-amber-500/20 rounded-xl text-center shadow">
          <div className="flex items-center justify-center gap-2 text-amber-500 text-xs font-bold mb-1">
            <Shield className="w-4 h-4" />
            PAPER MODE SIMULATION ONLY
          </div>
          <p className="text-[11px] text-slate-400 max-w-2xl mx-auto leading-relaxed">
            No real orders are routed to any exchange. Charges are calculated based on Zerodha/AngelOne actual rate cards (brokerage, GST, STT, exchange charges, stamp duties) to verify strategies under realistic frictional drag.
          </p>
        </div>
      </div>
    </div>
  );
}
