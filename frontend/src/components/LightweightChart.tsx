"use client";

import React, { useEffect, useRef } from "react";
import { createChart, ColorType, ISeriesApi, UTCTimestamp, CandlestickSeries, LineSeries, createSeriesMarkers } from "lightweight-charts";

interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface TradeMarker {
  time: string;
  direction: "BUY" | "SELL";
  price: number;
  qty: number;
}

interface LightweightChartProps {
  candles: CandleData[];
  trades?: TradeMarker[];
  showEmaFast?: boolean;
  showEmaSlow?: boolean;
  showBuyTrades?: boolean;
  showSellTrades?: boolean;
  emaFastPeriod?: number;
  emaSlowPeriod?: number;
  height?: number;
}

export default function LightweightChart({
  candles,
  trades = [],
  showEmaFast = true,
  showEmaSlow = true,
  showBuyTrades = true,
  showSellTrades = true,
  emaFastPeriod = 9,
  emaSlowPeriod = 21,
  height = 400
}: LightweightChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  // Helper to calculate EMA
  const calculateEMA = (data: number[], period: number): number[] => {
    const k = 2 / (period + 1);
    const ema = [data[0]];
    for (let i = 1; i < data.length; i++) {
      ema.push(data[i] * k + ema[i - 1] * (1 - k));
    }
    return ema;
  };

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;

    // Create chart
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0B0F19" },
        textColor: "#94A3B8",
      },
      grid: {
        vertLines: { color: "#1E293B" },
        horzLines: { color: "#1E293B" },
      },
      width: containerRef.current.clientWidth,
      height: height,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: "#1E293B",
      },
      rightPriceScale: {
        borderColor: "#1E293B",
      }
    });

    chartRef.current = chart;

    // Add candlestick series
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#10B981",
      downColor: "#EF4444",
      borderVisible: false,
      wickUpColor: "#10B981",
      wickDownColor: "#EF4444",
    });

    // Format candle times to UTC/epoch timestamp or clean string
    const formattedCandles = candles.map(c => {
      let timeVal: any = c.time;
      if (typeof timeVal === "string") {
        // Robust parsing for ISO strings, timestamps, and space-separated formats
        let cleanStr = timeVal;
        if (timeVal.includes(" ") && !timeVal.includes("T")) {
          cleanStr = timeVal.replace(" ", "T");
        }
        
        const dt = new Date(cleanStr);
        if (!isNaN(dt.getTime())) {
          timeVal = (Math.floor(dt.getTime() / 1000)) as UTCTimestamp;
        }
      }
      return {
        ...c,
        time: timeVal
      };
    });

    candlestickSeries.setData(formattedCandles);

    // Calculate and add indicators
    let emaFastSeries: ISeriesApi<"Line"> | null = null;
    let emaSlowSeries: ISeriesApi<"Line"> | null = null;

    if (candles.length > 0) {
      const closePrices = candles.map(c => c.close);

      if (showEmaFast && candles.length >= emaFastPeriod) {
        const emaFastVals = calculateEMA(closePrices, emaFastPeriod);
        const emaFastData = formattedCandles.map((c, idx) => ({
          time: c.time,
          value: emaFastVals[idx]
        })).slice(emaFastPeriod - 1);

        emaFastSeries = chart.addSeries(LineSeries, {
          color: "#3B82F6",
          lineWidth: 2,
          title: `EMA ${emaFastPeriod}`,
        });
        emaFastSeries.setData(emaFastData);
      }

      if (showEmaSlow && candles.length >= emaSlowPeriod) {
        const emaSlowVals = calculateEMA(closePrices, emaSlowPeriod);
        const emaSlowData = formattedCandles.map((c, idx) => ({
          time: c.time,
          value: emaSlowVals[idx]
        })).slice(emaSlowPeriod - 1);

        emaSlowSeries = chart.addSeries(LineSeries, {
          color: "#F59E0B",
          lineWidth: 2,
          title: `EMA ${emaSlowPeriod}`,
        });
        emaSlowSeries.setData(emaSlowData);
      }
    }

    // Set markers for trades
    if (trades.length > 0) {
      const markers = trades
        .filter(t => {
          if (t.direction === "BUY" && !showBuyTrades) return false;
          if (t.direction === "SELL" && !showSellTrades) return false;
          return true;
        })
        .map(t => {
          let timeVal: any = t.time;
          if (typeof timeVal === "string") {
            let cleanStr = timeVal;
            if (timeVal.includes(" ") && !timeVal.includes("T")) {
              cleanStr = timeVal.replace(" ", "T");
            }
            const dt = new Date(cleanStr);
            if (!isNaN(dt.getTime())) {
              timeVal = (Math.floor(dt.getTime() / 1000)) as UTCTimestamp;
            }
          }

          const isBuy = t.direction === "BUY";
          return {
            time: timeVal,
            position: isBuy ? "belowBar" as const : "aboveBar" as const,
            color: isBuy ? "#10B981" : "#EF4444",
            shape: isBuy ? "arrowUp" as const : "arrowDown" as const,
            text: `${t.direction} ${t.qty} @ ${t.price.toFixed(1)}`,
            size: 1.5
          };
        });

      if (markers.length > 0) {
        // Sort markers by time
        markers.sort((a: any, b: any) => a.time - b.time);
        createSeriesMarkers(candlestickSeries, markers);
      }
    }

    chart.timeScale().fitContent();

    // Handle resize
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [candles, trades, showEmaFast, showEmaSlow, showBuyTrades, showSellTrades, emaFastPeriod, emaSlowPeriod, height]);

  return (
    <div className="w-full relative bg-[#0B0F19] rounded-xl border border-slate-800 p-2 overflow-hidden">
      <div ref={containerRef} className="w-full" style={{ height: `${height}px` }} />
    </div>
  );
}
