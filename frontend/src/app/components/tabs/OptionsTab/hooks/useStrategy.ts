"use client";

import { useState, useCallback } from "react";
import { api } from "@/lib/api-client";
import type { StrategyLeg, SavedStrategy, StrategyTemplate, TradeDays } from "../types";

const generateId = () => Math.random().toString(36).substring(2, 10);

const DEFAULT_LEG: Omit<StrategyLeg, "id" | "leg_index"> = {
  position: "SELL",
  option_type: "CE",
  qty: 75,
  lot_multiplier: 1,
  strike_criteria: "ATM",
  strike_value: 0,
  strike_type: "POINTS",
  sl_enabled: false,
  sl_type: "PERCENT",
  sl_value: 0,
  sl_on_price: "ENTRY",
  tp_enabled: false,
  tp_type: "PERCENT",
  tp_value: 0,
  tp_on_price: "ENTRY",
  trail_sl_enabled: false,
  trail_sl_type: "PERCENT",
  trail_sl_value: 0,
  trail_sl_step: 0,
};

export function useStrategy(
  chainSymbol: string,
  triggerNotif: (type: "success" | "error", msg: string) => void,
  backendOnline: boolean
) {
  const [strategyName, setStrategyName] = useState("My Option Strategy");
  const [strategyType, setStrategyType] = useState("indicator");
  const [tradeType, setTradeType] = useState("MIS");
  const [startTime, setStartTime] = useState("09:16");
  const [endTime, setEndTime] = useState("15:15");
  const [expiryType, setExpiryType] = useState("WEEKLY");
  const [initialCapital, setInitialCapital] = useState(1000000);
  const [tradeDays, setTradeDays] = useState<TradeDays>({
    mon: true, tue: true, wed: true, thu: true, fri: true,
  });

  const [legs, setLegs] = useState<StrategyLeg[]>([
    { ...DEFAULT_LEG, id: generateId(), leg_index: 0, position: "SELL", option_type: "CE" },
    { ...DEFAULT_LEG, id: generateId(), leg_index: 1, position: "SELL", option_type: "PE" },
  ]);

  const [savedStrategies, setSavedStrategies] = useState<SavedStrategy[]>([]);
  const [savedLoading, setSavedLoading] = useState(false);
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);

  const addLeg = useCallback(() => {
    setLegs(prev => [
      ...prev,
      { ...DEFAULT_LEG, id: generateId(), leg_index: prev.length },
    ]);
  }, []);

  const addConfiguredLeg = useCallback((config: Partial<StrategyLeg>) => {
    setLegs(prev => [
      ...prev,
      {
        ...DEFAULT_LEG,
        id: generateId(),
        leg_index: prev.length,
        position: config.position || "SELL",
        option_type: config.option_type || "CE",
        qty: config.qty ?? 75,
        lot_multiplier: config.lot_multiplier ?? 1,
        strike_criteria: config.strike_criteria || "ATM",
        strike_value: config.strike_value ?? 0,
        strike_type: config.strike_type || "POINTS",
        sl_enabled: config.sl_enabled ?? false,
        sl_type: config.sl_type || "PERCENT",
        sl_value: config.sl_value ?? 0,
        tp_enabled: config.tp_enabled ?? false,
        tp_type: config.tp_type || "PERCENT",
        tp_value: config.tp_value ?? 0,
      },
    ]);
  }, []);

  const removeLeg = useCallback((id: string) => {
    setLegs(prev => prev.filter(l => l.id !== id).map((l, i) => ({ ...l, leg_index: i })));
  }, []);

  const updateLeg = useCallback((id: string, updates: Partial<StrategyLeg>) => {
    setLegs(prev => prev.map(l => l.id === id ? { ...l, ...updates } : l));
  }, []);

  const duplicateLeg = useCallback((id: string) => {
    setLegs(prev => {
      const leg = prev.find(l => l.id === id);
      if (!leg) return prev;
      return [...prev, { ...leg, id: generateId(), leg_index: prev.length }];
    });
  }, []);

  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    const result = await api.get<{ templates: StrategyTemplate[] }>("/options/templates");
    if (result.ok && result.data) {
      setTemplates(result.data.templates || []);
    }
    setTemplatesLoading(false);
  }, []);

  const loadSavedStrategies = useCallback(async () => {
    setSavedLoading(true);
    const result = await api.get<{ strategies: SavedStrategy[] }>("/options/strategies");
    if (result.ok && result.data) {
      setSavedStrategies(result.data.strategies || []);
    }
    setSavedLoading(false);
  }, []);

  const createFromTemplate = useCallback(async (templateId: string) => {
    if (!backendOnline) {
      triggerNotif("error", "Backend is offline.");
      return;
    }
    const result = await api.post<{ strategy?: SavedStrategy }>("/options/strategies/template", {
      template_name: templateId,
      underlying_symbol: chainSymbol,
    });
    if (result.ok && result.data?.strategy?.id) {
      triggerNotif("success", `Strategy created from template: ${result.data.strategy.name}`);
      loadSavedStrategies();
      // Fetch full details and populate local form state
      const detailRes = await api.get<{ strategy?: SavedStrategy }>(`/options/strategies/${result.data.strategy.id}`);
      if (detailRes.ok && detailRes.data?.strategy) {
        const s = detailRes.data.strategy;
        setStrategyName(s.name || "My Option Strategy");
        setStrategyType(s.strategy_type || "indicator");
        setTradeType(s.trade_type || "MIS");
        setStartTime(s.start_time || "09:16");
        setEndTime(s.end_time || "15:15");
        setExpiryType(s.expiry_type || "WEEKLY");
        setInitialCapital(s.initial_capital ?? 1000000);
        if (s.trade_days) {
          setTradeDays({
            mon: s.trade_days.mon ?? true,
            tue: s.trade_days.tue ?? true,
            wed: s.trade_days.wed ?? true,
            thu: s.trade_days.thu ?? true,
            fri: s.trade_days.fri ?? true,
          });
        }
        if (s.legs && s.legs.length > 0) {
          setLegs(s.legs.map((l, i) => ({ ...l, id: generateId(), leg_index: i })));
        } else {
          // Default legs for the template if none returned
          setLegs([
            { ...DEFAULT_LEG, id: generateId(), leg_index: 0, position: "SELL", option_type: "CE" },
            { ...DEFAULT_LEG, id: generateId(), leg_index: 1, position: "SELL", option_type: "PE" },
          ]);
        }
        triggerNotif("success", `Loaded ${s.legs?.length ?? 0} legs into builder.`);
      }
    } else {
      triggerNotif("error", result.error || "Failed to create from template.");
    }
  }, [chainSymbol, backendOnline, triggerNotif, loadSavedStrategies]);

  const saveStrategy = useCallback(async () => {
    if (!backendOnline) {
      triggerNotif("error", "Backend is offline.");
      return;
    }
    const result = await api.post<{ strategy?: SavedStrategy }>("/options/strategies", {
      name: strategyName,
      underlying_symbol: chainSymbol,
      trade_type: tradeType,
      start_time: startTime,
      end_time: endTime,
      expiry_type: expiryType,
      strategy_type: strategyType,
      initial_capital: initialCapital,
      trade_mon: tradeDays.mon,
      trade_tue: tradeDays.tue,
      trade_wed: tradeDays.wed,
      trade_thu: tradeDays.thu,
      trade_fri: tradeDays.fri,
      legs: legs.map(l => ({
        position: l.position,
        option_type: l.option_type,
        qty: l.qty,
        lot_multiplier: l.lot_multiplier,
        strike_criteria: l.strike_criteria,
        strike_value: l.strike_value,
        strike_type: l.strike_type,
        sl_enabled: l.sl_enabled,
        sl_type: l.sl_type,
        sl_value: l.sl_value,
        sl_on_price: l.sl_on_price,
        tp_enabled: l.tp_enabled,
        tp_type: l.tp_type,
        tp_value: l.tp_value,
        tp_on_price: l.tp_on_price,
        trail_sl_enabled: l.trail_sl_enabled,
        trail_sl_type: l.trail_sl_type,
        trail_sl_value: l.trail_sl_value,
        trail_sl_step: l.trail_sl_step,
      })),
    });
    if (result.ok && result.data) {
      triggerNotif("success", "Strategy saved successfully.");
      loadSavedStrategies();
    } else {
      triggerNotif("error", result.error || "Failed to save strategy.");
    }
  }, [
    backendOnline, chainSymbol, tradeType, startTime, endTime, expiryType,
    strategyType, initialCapital, tradeDays, legs, strategyName, triggerNotif, loadSavedStrategies,
  ]);

  return {
    // Strategy meta
    strategyName, setStrategyName,
    strategyType, setStrategyType,
    tradeType, setTradeType,
    startTime, setStartTime,
    endTime, setEndTime,
    expiryType, setExpiryType,
    initialCapital, setInitialCapital,
    tradeDays, setTradeDays,

    // Legs
    legs,
    addLeg,
    addConfiguredLeg,
    removeLeg,
    updateLeg,
    duplicateLeg,

    // Templates & saved
    templates,
    templatesLoading,
    loadTemplates,
    savedStrategies,
    savedLoading,
    loadSavedStrategies,
    createFromTemplate,
    saveStrategy,
  };
}
