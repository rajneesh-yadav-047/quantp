"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Play, Pause, Square, TrendingUp, TrendingDown, Activity,
  DollarSign, Wallet, BarChart3, ArrowLeft, Radio, Shield,
  Clock, AlertTriangle, CheckCircle2, XCircle, RefreshCw,
  ChevronDown, ChevronUp, Bell
} from "lucide-react";
import { api, formatApiError } from "../../lib/api-client";

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
  const [isLoading, setIsLoading] = useState(false);
  const [notif, setNotif] = useState<{ type: "success" | "error" | "info"; msg: string } | null>(null);
  const [sseConnected, setSseConnected] = useState(false);
  const [showChargesDetail, setShowChargesDetail] = useState(false);
  const [lastTick, setLastTick] = useState<any>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

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
        setLastTick(data);
        if (data.portfolio) {
          setStatus(prev => prev ? {
            ...prev,
            portfolio: data.portfolio,
            step: data.step,
            current_price: data.ltp ?? data.candle?.[prev.symbol]?.close ?? prev.current_price
          } : null);
        }
        // If tick has LTP field, market data is active
        if (data.ltp !== undefined) {
          setMarketDataActive(true);
        }
        if (data.orders_filled && data.orders_filled.length > 0) {
          fetchTrades();
          fetchPnl();
        }
      } catch (e) {}
    });

    es.addEventListener("fill", () => {
      fetchTrades();
      fetchPnl();
    });

    es.onerror = () => {
      setSseConnected(false);
      es.close();
    };

    return () => {
      es.close();
      setSseConnected(false);
    };
  }, [selectedDeploymentId, fetchTrades, fetchPnl]);

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
    connectSSE();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        setSseConnected(false);
      }
    };
  }, [selectedDeploymentId, fetchStatus, fetchTrades, fetchPnl, fetchEvents, connectSSE]);

  // Auto-refresh polling (fallback when SSE is not connected)
  useEffect(() => {
    if (!autoRefresh || !selectedDeploymentId) return;

    refreshIntervalRef.current = setInterval(() => {
      if (!sseConnected) {
        fetchStatus();
        fetchTrades();
        fetchPnl();
      }
      fetchMarketDataStatus();
    }, 3000);

    return () => {
      if (refreshIntervalRef.current) clearInterval(refreshIntervalRef.current);
    };
  }, [autoRefresh, selectedDeploymentId, sseConnected, fetchStatus, fetchTrades, fetchPnl, fetchMarketDataStatus]);

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
      connectSSE();
    } else {
      const errMsg = formatApiError(result, "Start failed");
      // If SmartAPI not connected, show TOTP modal instead of just an error
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
      // Retry start now that we're authenticated
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
      triggerNotif("info", "Mock deployment stopped. No real orders were placed.");
      fetchDeployments();
      fetchStatus();
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

  const selectedDeployment = deployments.find(d => d.deployment_id === selectedDeploymentId);
  const isRunning = status?.status === "running";
  const isPaused = status?.status === "paused";

  // Calculate PnL change for display
  const latestPnl = pnlHistory[0];
  const previousPnl = pnlHistory[1];
  const pnlChange = latestPnl && previousPnl
    ? latestPnl.equity - previousPnl.equity
    : 0;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
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
                <Activity className="w-3 h-3" /> Live Stream
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

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Deployment Selector + Controls */}
        <div className="mb-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
            <label className="text-xs text-slate-400 uppercase tracking-wider mb-2 block">Deployment</label>
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

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center gap-2">
            {isRunning ? (
              <>
                <button onClick={handlePause} disabled={isLoading} className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors">
                  <Pause className="w-4 h-4" /> Pause
                </button>
                <button onClick={handleStop} disabled={isLoading} className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors">
                  <Square className="w-4 h-4" /> Stop
                </button>
              </>
            ) : isPaused ? (
              <>
                <button onClick={handleResume} disabled={isLoading} className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors">
                  <Play className="w-4 h-4" /> Resume
                </button>
                <button onClick={handleStop} disabled={isLoading} className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors">
                  <Square className="w-4 h-4" /> Stop
                </button>
              </>
            ) : (
              <button onClick={handleStart} disabled={isLoading || !selectedDeploymentId} className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors">
                <Play className="w-4 h-4" />
                {isLoading ? "Starting..." : "Start Mock Trading"}
              </button>
            )}
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-2 h-2 rounded-full ${status?.smartapi_connected ? "bg-emerald-400" : "bg-red-400"}`} />
              <div>
                <div className="text-sm font-medium">{status?.symbol || selectedDeployment?.symbol || "—"}</div>
                <div className="text-xs text-slate-400">{status?.interval || "—"} • Step {status?.step ?? 0}</div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-lg font-bold">
                {status?.current_price != null ? `₹${status.current_price.toFixed(2)}` : "—"}
              </div>
              <div className="flex items-center justify-end gap-1.5">
                {status?.smartapi_connected ? (
                  marketDataActive || status?.market_data_active ? (
                    <span className="flex items-center gap-1 text-[10px] text-emerald-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Real-time LTP
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[10px] text-amber-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                      Waiting for tick...
                    </span>
                  )
                ) : (
                  <span className="flex items-center gap-1 text-[10px] text-red-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                    SmartAPI Disconnected
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Portfolio Summary Cards */}
        {status?.portfolio && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <div className="text-xs text-slate-400 mb-1">Equity</div>
              <div className="text-xl font-bold text-slate-100">₹{status.portfolio.equity.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</div>
              <div className={`text-xs mt-1 ${pnlChange >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {pnlChange >= 0 ? "+" : ""}₹{pnlChange.toFixed(2)}
              </div>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <div className="text-xs text-slate-400 mb-1">Total PnL</div>
              <div className={`text-xl font-bold ${status.portfolio.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {status.portfolio.total_pnl >= 0 ? "+" : ""}₹{status.portfolio.total_pnl.toFixed(2)}
              </div>
              <div className="text-xs text-slate-500 mt-1">Realized + Unrealized</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <div className="text-xs text-slate-400 mb-1">Cash</div>
              <div className="text-xl font-bold text-slate-100">₹{status.portfolio.cash.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</div>
              <div className="text-xs text-slate-500 mt-1">Available</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <div className="text-xs text-slate-400 mb-1">Total Fees</div>
              <div className="text-xl font-bold text-amber-400">₹{status.portfolio.total_fees.toFixed(2)}</div>
              <div className="text-xs text-slate-500 mt-1">Brokerage + Taxes</div>
            </div>
          </div>
        )}

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Trades */}
          <div className="lg:col-span-2 space-y-6">
            {/* Recent Trades */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-blue-400" />
                  <h3 className="font-semibold">Recent Trades</h3>
                </div>
                <span className="text-xs text-slate-500">{trades.length} trades</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-slate-400 border-b border-slate-800">
                      <th className="px-4 py-2 text-left">Time</th>
                      <th className="px-4 py-2 text-left">Symbol</th>
                      <th className="px-4 py-2 text-left">Direction</th>
                      <th className="px-4 py-2 text-right">Qty</th>
                      <th className="px-4 py-2 text-right">Price</th>
                      <th className="px-4 py-2 text-right">Value</th>
                      <th className="px-4 py-2 text-right">Charges</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.length === 0 && (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-slate-500 text-sm">
                          No trades yet. Start the mock deployment to see trades.
                        </td>
                      </tr>
                    )}
                    {trades.map((trade) => (
                      <tr key={trade.id} className="border-b border-slate-800/50 hover:bg-slate-800/50">
                        <td className="px-4 py-2 text-slate-400">
                          {new Date(trade.timestamp).toLocaleTimeString("en-IN")}
                        </td>
                        <td className="px-4 py-2 font-medium">{trade.symbol}</td>
                        <td className="px-4 py-2">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                            trade.direction === "BUY"
                              ? "bg-emerald-500/20 text-emerald-400"
                              : "bg-red-500/20 text-red-400"
                          }`}>
                            {trade.direction === "BUY" ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                            {trade.direction}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-right">{trade.qty}</td>
                        <td className="px-4 py-2 text-right">₹{trade.price.toFixed(2)}</td>
                        <td className="px-4 py-2 text-right">₹{trade.value.toFixed(2)}</td>
                        <td className="px-4 py-2 text-right">
                          <span className="text-amber-400">₹{trade.total_charges.toFixed(2)}</span>
                          {trade.charges_source === "api" && (
                            <span className="ml-1 text-[10px] text-blue-400">API</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* PnL Chart (Simple Bar Chart) */}
            {pnlHistory.length > 0 && (
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-purple-400" />
                    <h3 className="font-semibold">Equity Curve</h3>
                  </div>
                  <div className="text-xs text-slate-400">
                    {pnlHistory.length} snapshots
                  </div>
                </div>
                <div className="h-48 flex items-end gap-1">
                  {pnlHistory.slice(0, 60).reverse().map((snapshot) => {
                    const maxEquity = Math.max(...pnlHistory.map(p => p.equity), status?.initial_capital || 100000);
                    const minEquity = Math.min(...pnlHistory.map(p => p.equity), status?.initial_capital || 100000);
                    const range = maxEquity - minEquity || 1;
                    const height = ((snapshot.equity - minEquity) / range) * 100;
                    const isProfit = snapshot.equity >= (status?.initial_capital || 100000);
                    return (
                      <div key={snapshot.id} className="flex-1 flex flex-col items-center gap-1 group relative">
                        <div
                          className={`w-full rounded-t ${isProfit ? "bg-emerald-500/60" : "bg-red-500/60"} transition-all`}
                          style={{ height: `${Math.max(height, 5)}%` }}
                        />
                        <div className="absolute bottom-full mb-1 hidden group-hover:block bg-slate-800 text-xs px-2 py-1 rounded border border-slate-700 whitespace-nowrap z-10">
                          ₹{snapshot.equity.toFixed(2)} • {new Date(snapshot.timestamp).toLocaleTimeString()}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Right: Positions + Events */}
          <div className="space-y-6">
            {/* Positions */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Wallet className="w-4 h-4 text-emerald-400" />
                  <h3 className="font-semibold">Positions</h3>
                </div>
                <span className="text-xs text-slate-500">
                  {Object.keys(status?.portfolio?.positions || {}).length} open
                </span>
              </div>
              <div className="p-4 space-y-3">
                {Object.keys(status?.portfolio?.positions || {}).length === 0 && (
                  <div className="text-center text-slate-500 text-sm py-4">
                    No open positions
                  </div>
                )}
                {Object.entries(status?.portfolio?.positions || {}).map(([sym, pos]: [string, any]) => (
                  <div key={sym} className="bg-slate-800/50 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium">{sym}</span>
                      <span className={`text-sm font-bold ${pos.qty > 0 ? "text-emerald-400" : "text-red-400"}`}>
                        {pos.qty > 0 ? "+" : ""}{pos.qty}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 flex justify-between">
                      <span>Avg: ₹{pos.avg_price.toFixed(2)}</span>
                      <span className={pos.unrealized_pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
                        PnL: ₹{pos.unrealized_pnl.toFixed(2)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Active Orders */}
            {status && status.active_orders && status.active_orders.length > 0 && (
              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-2">
                  <Bell className="w-4 h-4 text-amber-400" />
                  <h3 className="font-semibold">Active Orders</h3>
                </div>
                <div className="p-4 space-y-2">
                  {status.active_orders.map((order: any, i: number) => (
                    <div key={i} className="bg-slate-800/50 rounded-lg p-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className={`font-medium ${order.direction === "BUY" ? "text-emerald-400" : "text-red-400"}`}>
                          {order.direction} {order.qty} {order.symbol}
                        </span>
                        <span className="text-xs px-2 py-0.5 bg-slate-700 rounded">{order.type}</span>
                      </div>
                      <div className="text-xs text-slate-400 mt-1">
                        @ ₹{order.price.toFixed(2)} • {order.status}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Events Log */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 text-blue-400" />
                  <h3 className="font-semibold">Events</h3>
                </div>
                <span className="text-xs text-slate-500">{events.length}</span>
              </div>
              <div className="max-h-64 overflow-y-auto p-4 space-y-2">
                {events.length === 0 && (
                  <div className="text-center text-slate-500 text-sm py-4">
                    No events yet
                  </div>
                )}
                {events.map((event) => (
                  <div key={event.id} className="text-sm">
                    <div className="flex items-start gap-2">
                      {event.event_type === "fill" && <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />}
                      {event.event_type === "error" && <XCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />}
                      {event.event_type === "margin_call" && <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />}
                      {event.event_type === "start" && <Play className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />}
                      {event.event_type === "stop" && <Square className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />}
                      {!["fill", "error", "margin_call", "start", "stop"].includes(event.event_type) && (
                        <Activity className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
                      )}
                      <div>
                        <div className="text-slate-300">{event.message}</div>
                        <div className="text-xs text-slate-500">
                          {new Date(event.timestamp).toLocaleTimeString("en-IN")}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Charges Breakdown Toggle */}
            {trades.length > 0 && (
              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
                <button
                  onClick={() => setShowChargesDetail(!showChargesDetail)}
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-800/50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <DollarSign className="w-4 h-4 text-amber-400" />
                    <h3 className="font-semibold">Charge Breakdown</h3>
                  </div>
                  {showChargesDetail ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
                {showChargesDetail && (
                  <div className="px-4 pb-4 space-y-2">
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
                          <div className="flex justify-between text-sm"><span className="text-slate-400">Brokerage</span><span>₹{totals.brokerage.toFixed(2)}</span></div>
                          <div className="flex justify-between text-sm"><span className="text-slate-400">STT / CTT</span><span>₹{totals.stt.toFixed(2)}</span></div>
                          <div className="flex justify-between text-sm"><span className="text-slate-400">Exchange Charges</span><span>₹{totals.exc.toFixed(2)}</span></div>
                          <div className="flex justify-between text-sm"><span className="text-slate-400">GST</span><span>₹{totals.gst.toFixed(2)}</span></div>
                          <div className="flex justify-between text-sm"><span className="text-slate-400">SEBI Charges</span><span>₹{totals.sebi.toFixed(2)}</span></div>
                          <div className="flex justify-between text-sm"><span className="text-slate-400">Stamp Duty</span><span>₹{totals.stamp.toFixed(2)}</span></div>
                          <div className="border-t border-slate-700 pt-2 flex justify-between text-sm font-bold">
                            <span className="text-amber-400">Total</span>
                            <span className="text-amber-400">₹{totals.total.toFixed(2)}</span>
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
        <div className="mt-8 p-4 bg-amber-950/30 border border-amber-800/30 rounded-xl text-center">
          <div className="flex items-center justify-center gap-2 text-amber-400 text-sm font-medium mb-1">
            <Shield className="w-4 h-4" />
            MOCK / PAPER TRADING ONLY
          </div>
          <p className="text-xs text-amber-400/70">
            No real orders are placed. All trades are simulated using live market data.
            Charges are calculated based on Angel One's actual fee structure for realistic PnL estimation.
          </p>
        </div>
      </div>
    </div>
  );
}
