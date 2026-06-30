"use client";

import { useMemo } from "react";
import type { StrategyLeg, OptionChainData, PayoffResult } from "../types";
import { resolveStrike } from "../OptionChain/useOptionChain";

const STEPS = 200;
const RANGE_PCT = 0.15;

export function usePayoff(legs: StrategyLeg[], chainData: OptionChainData | null): PayoffResult {
  return useMemo(() => {
    if (!chainData || !chainData.ltp || !chainData.strikes.length || !legs.length) {
      return { spotPrices: [], payoffs: [], maxProfit: 0, maxLoss: 0, breakevens: [] };
    }

    const ltp = chainData.ltp;
    const range = ltp * RANGE_PCT;
    const minSpot = Math.max(ltp - range, chainData.strikes[0] * 0.8);
    const maxSpot = Math.min(ltp + range, chainData.strikes[chainData.strikes.length - 1] * 1.2);
    const stepSize = (maxSpot - minSpot) / STEPS;
    const spotPrices: number[] = [];
    const payoffs: number[] = [];

    for (let i = 0; i <= STEPS; i++) {
      const spot = minSpot + i * stepSize;
      spotPrices.push(spot);
      let totalPnL = 0;

      for (const leg of legs) {
        const strike = resolveStrike(
          ltp,
          leg.strike_criteria,
          leg.strike_value,
          leg.strike_type,
          leg.option_type,
          chainData.strikes
        );
        const strikeData = chainData.chain[strike]?.[leg.option_type];
        const premium = strikeData?.ltp || 0;
        const qty = leg.qty * leg.lot_multiplier;

        let legPnL = 0;
        if (leg.option_type === "CE") {
          if (leg.position === "BUY") {
            legPnL = (Math.max(0, spot - strike) - premium) * qty;
          } else {
            legPnL = (premium - Math.max(0, spot - strike)) * qty;
          }
        } else {
          if (leg.position === "BUY") {
            legPnL = (Math.max(0, strike - spot) - premium) * qty;
          } else {
            legPnL = (premium - Math.max(0, strike - spot)) * qty;
          }
        }
        totalPnL += legPnL;
      }
      payoffs.push(totalPnL);
    }

    const maxProfit = Math.max(...payoffs, 0);
    const maxLoss = Math.min(...payoffs, 0);

    // Find breakevens (where payoff crosses zero)
    const breakevens: number[] = [];
    for (let i = 1; i < payoffs.length; i++) {
      if ((payoffs[i - 1] < 0 && payoffs[i] >= 0) || (payoffs[i - 1] > 0 && payoffs[i] <= 0)) {
        const t = Math.abs(payoffs[i - 1]) / (Math.abs(payoffs[i - 1]) + Math.abs(payoffs[i]));
        breakevens.push(spotPrices[i - 1] + t * (spotPrices[i] - spotPrices[i - 1]));
      }
    }

    return { spotPrices, payoffs, maxProfit, maxLoss, breakevens };
  }, [legs, chainData]);
}

export function calculateNetPremium(legs: StrategyLeg[], chainData: OptionChainData | null): number {
  if (!chainData || !chainData.strikes.length) return 0;
  let total = 0;
  for (const leg of legs) {
    const strike = resolveStrike(
      chainData.ltp,
      leg.strike_criteria,
      leg.strike_value,
      leg.strike_type,
      leg.option_type,
      chainData.strikes
    );
    const strikeData = chainData.chain[strike]?.[leg.option_type];
    const premium = strikeData?.ltp || 0;
    const qty = leg.qty * leg.lot_multiplier;
    total += leg.position === "SELL" ? premium * qty : -premium * qty;
  }
  return total;
}

export function calculateMarginEstimate(legs: StrategyLeg[], chainData: OptionChainData | null): number {
  if (!chainData || !chainData.ltp || !chainData.strikes.length) return 0;
  let totalMargin = 0;
  for (const leg of legs) {
    const strike = resolveStrike(
      chainData.ltp,
      leg.strike_criteria,
      leg.strike_value,
      leg.strike_type,
      leg.option_type,
      chainData.strikes
    );
    const strikeData = chainData.chain[strike]?.[leg.option_type];
    const premium = strikeData?.ltp || 0;
    const qty = leg.qty * leg.lot_multiplier;

    if (leg.position === "SELL") {
      const notional = strike * qty;
      totalMargin += notional * 0.15;
    } else {
      totalMargin += premium * qty;
    }
  }
  return totalMargin;
}
