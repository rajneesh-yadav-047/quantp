"use client";

import React, { useEffect } from "react";
import { OptionChainPanel } from "./OptionChain/OptionChainPanel";
import { StrategyBuilderPanel } from "./StrategyBuilder/StrategyBuilderPanel";
import { PayoffChart } from "./PayoffChart/PayoffChart";
import { useOptionChain } from "./OptionChain/useOptionChain";
import { useStrategy } from "./hooks/useStrategy";
import { usePayoff, calculateNetPremium, calculateMarginEstimate } from "./PayoffChart/usePayoff";

interface OptionsTabProps {
  triggerNotif: (type: "success" | "error", msg: string) => void;
  smartapiConnected: boolean;
  backendOnline: boolean;
  datasets: any[];
  checkDataCoverage: (symbols: string[], interval: string, startDate: string, endDate: string) => { symbol: string; interval: string; reason: string }[];
  // TOTP
  isTotpModalOpen: boolean;
  setIsTotpModalOpen: (v: boolean) => void;
  totpInput: string;
  setTotpInput: (v: string) => void;
  pendingAction: string | null;
  setPendingAction: (v: any) => void;
  handleTotpConfirm: () => void;
  // Options download
  optionsDlSymbol: string;
  setOptionsDlSymbol: (v: string) => void;
  optionsDlExpiry: string;
  setOptionsDlExpiry: (v: string) => void;
  optionsDlStrikes: string;
  setOptionsDlStrikes: (v: string) => void;
  optionsDlOptionTypes: string;
  setOptionsDlOptionTypes: (v: string) => void;
  optionsDlFromDate: string;
  setOptionsDlFromDate: (v: string) => void;
  optionsDlToDate: string;
  setOptionsDlToDate: (v: string) => void;
  optionsDlJobId: string | null;
  // Bhavcopy
  bhavcopyFromDate: string;
  setBhavcopyFromDate: (v: string) => void;
  bhavcopyToDate: string;
  setBhavcopyToDate: (v: string) => void;
  bhavcopyJobId: string | null;
  // Handlers
  triggerOptionsDownload: (e: React.FormEvent) => void;
  triggerOptionsBhavcopyImport: (e: React.FormEvent) => void;
  handleOptionsBacktest: (strategyId: string, startDate: string, endDate: string) => void;
  handleOptionsBacktestFullFlow: (strategyId: string, startDate: string, endDate: string) => void;
  // Backtest inputs
  btStartDate: string;
  setBtStartDate: (v: string) => void;
  btEndDate: string;
  setBtEndDate: (v: string) => void;
  btSlippage: number;
  setBtSlippage: (v: number) => void;
}

export function OptionsTab({
  triggerNotif, smartapiConnected, backendOnline, datasets, checkDataCoverage,
  isTotpModalOpen, setIsTotpModalOpen, totpInput, setTotpInput,
  pendingAction, setPendingAction, handleTotpConfirm,
  optionsDlSymbol, setOptionsDlSymbol, optionsDlExpiry, setOptionsDlExpiry,
  optionsDlStrikes, setOptionsDlStrikes, optionsDlOptionTypes, setOptionsDlOptionTypes,
  optionsDlFromDate, setOptionsDlFromDate, optionsDlToDate, setOptionsDlToDate,
  optionsDlJobId, bhavcopyFromDate, setBhavcopyFromDate, bhavcopyToDate, setBhavcopyToDate,
  bhavcopyJobId, triggerOptionsDownload, triggerOptionsBhavcopyImport, handleOptionsBacktest, handleOptionsBacktestFullFlow,
  btStartDate, setBtStartDate, btEndDate, setBtEndDate, btSlippage, setBtSlippage,
}: OptionsTabProps) {
  // ── Option Chain ──
  const {
    chainSymbol, setChainSymbol,
    selectedExpiry, setSelectedExpiry,
    chainData, loading: chainLoading,
    error: chainError, loadChain,
    atmStrike, expiryDates, ltp,
  } = useOptionChain(smartapiConnected, backendOnline);

  useEffect(() => {
    if (chainError) triggerNotif("error", chainError);
  }, [chainError, triggerNotif]);

  useEffect(() => {
    if (chainData && !chainLoading) {
      triggerNotif("success", `Option chain loaded: ${chainData.is_mock ? "Mock" : "Live"}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chainData?.symbol, chainData?.is_mock]);

  // ── Strategy Builder ──
  const strategy = useStrategy(chainSymbol, triggerNotif, backendOnline);

  useEffect(() => {
    strategy.loadTemplates();
    strategy.loadSavedStrategies();
  }, [strategy.loadTemplates, strategy.loadSavedStrategies]);

  // ── Payoff ──
  const payoff = usePayoff(strategy.legs, chainData);
  const netPremium = React.useMemo(() => calculateNetPremium(strategy.legs, chainData), [strategy.legs, chainData]);
  const marginEstimate = React.useMemo(() => calculateMarginEstimate(strategy.legs, chainData), [strategy.legs, chainData]);

  return (
    <div className="flex-1 grid grid-cols-2 overflow-hidden gap-0">
      {/* Left pane: Option Chain */}
      <div className="flex flex-col overflow-hidden border-r border-[var(--ax-border)]">
        <OptionChainPanel
          chainSymbol={chainSymbol}
          setChainSymbol={setChainSymbol}
          selectedExpiry={selectedExpiry}
          setSelectedExpiry={setSelectedExpiry}
          expiryDates={expiryDates}
          ltp={ltp}
          chainData={chainData}
          loading={chainLoading}
          onRefresh={loadChain}
          onAddLeg={strategy.addConfiguredLeg}
        />
      </div>

      {/* Right pane: Strategy Builder */}
      <div className="flex flex-col overflow-y-auto p-4 gap-4">
        <StrategyBuilderPanel
          strategyName={strategy.strategyName}
          setStrategyName={strategy.setStrategyName}
          strategyType={strategy.strategyType}
          setStrategyType={strategy.setStrategyType}
          tradeType={strategy.tradeType}
          setTradeType={strategy.setTradeType}
          startTime={strategy.startTime}
          setStartTime={strategy.setStartTime}
          endTime={strategy.endTime}
          setEndTime={strategy.setEndTime}
          expiryType={strategy.expiryType}
          setExpiryType={strategy.setExpiryType}
          initialCapital={strategy.initialCapital}
          setInitialCapital={strategy.setInitialCapital}
          tradeDays={strategy.tradeDays}
          setTradeDays={strategy.setTradeDays}
          legs={strategy.legs}
          onAddLeg={strategy.addLeg}
          onUpdateLeg={strategy.updateLeg}
          onRemoveLeg={strategy.removeLeg}
          onDuplicateLeg={strategy.duplicateLeg}
          onSaveStrategy={strategy.saveStrategy}
          templates={strategy.templates}
          templatesLoading={strategy.templatesLoading}
          onSelectTemplate={strategy.createFromTemplate}
          // Data coverage
          datasets={datasets}
          checkDataCoverage={checkDataCoverage}
          // Options download
          optionsDlSymbol={optionsDlSymbol}
          setOptionsDlSymbol={setOptionsDlSymbol}
          optionsDlExpiry={optionsDlExpiry}
          setOptionsDlExpiry={setOptionsDlExpiry}
          optionsDlStrikes={optionsDlStrikes}
          setOptionsDlStrikes={setOptionsDlStrikes}
          optionsDlOptionTypes={optionsDlOptionTypes}
          setOptionsDlOptionTypes={setOptionsDlOptionTypes}
          optionsDlFromDate={optionsDlFromDate}
          setOptionsDlFromDate={setOptionsDlFromDate}
          optionsDlToDate={optionsDlToDate}
          setOptionsDlToDate={setOptionsDlToDate}
          optionsDlJobId={optionsDlJobId}
          triggerOptionsDownload={triggerOptionsDownload}
          // Bhavcopy
          bhavcopyFromDate={bhavcopyFromDate}
          setBhavcopyFromDate={setBhavcopyFromDate}
          bhavcopyToDate={bhavcopyToDate}
          setBhavcopyToDate={setBhavcopyToDate}
          bhavcopyJobId={bhavcopyJobId}
          triggerOptionsBhavcopyImport={triggerOptionsBhavcopyImport}
          // Backtest
          chainSymbol={chainSymbol}
          selectedExpiry={selectedExpiry}
          btStartDate={btStartDate}
          setBtStartDate={setBtStartDate}
          btEndDate={btEndDate}
          setBtEndDate={setBtEndDate}
          btSlippage={btSlippage}
          setBtSlippage={setBtSlippage}
          handleOptionsBacktest={handleOptionsBacktest}
          handleOptionsBacktestFullFlow={handleOptionsBacktestFullFlow}
          backendOnline={backendOnline}
        />

        <PayoffChart payoff={payoff} />
      </div>
    </div>
  );
}
