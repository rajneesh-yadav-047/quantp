"use client";

import React from "react";
import dynamic from "next/dynamic";
import { useQuantLab } from "./hooks/useQuantLab";
import Sidebar from "./components/shared/Sidebar";
import { TotpModal, ErrorBanners, DashboardTab, DatasetsTab } from "./components/tabs/DashboardTab";
import { StrategiesTab } from "./components/tabs/StrategiesTab";
import { BacktestsTab } from "./components/tabs/BacktestsTab";
import { DeploymentsTab } from "./components/tabs/DeploymentsTab";
import { OptimizerTab } from "./components/tabs/OptimizerTab";
import { CleanupTab } from "./components/tabs/CleanupTab";

const ResearchLab = dynamic(() => import("../components/ResearchLab"), { ssr: false });

export default function Home() {
  const q = useQuantLab();

  const tabDescriptions: Record<string, string> = {
    dashboard: "System overview, connection status, and quick actions.",
    datasets: "Manage historical candle data directories saved in Parquet formats.",
    strategies: "Primary workspace. Configure symbols, interval, capital, risk settings, and strategy code.",
    backtests: "Run strategies and view results: equity curve, PnL, drawdown, trade history, per-symbol performance.",
    deployments: "Manage paper and live deployments per strategy.",
    live: "Real-time mock trading with live market data. No real money used.",
    research: "Deep statistical analysis of any dataset — returns, volatility, regimes, seasonality, and strategy suitability scoring.",
    optimizer: "Execute grid-search sweeps to find mathematically optimal strategy weights.",
    cleanup: "Manage disk space by deleting old backtest logs and downloaded parquet datasets.",
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#050811] text-[#E2E8F0]">
      <Sidebar
        activeTab={q.activeTab}
        setActiveTab={q.setActiveTab}
        notif={q.notif}
        backendOnline={q.backendOnline}
        smartapiConnected={q.smartapiConnected}
        ollamaState={q.ollamaState}
        apiErrors={q.apiErrors}
      />

      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto bg-[#070B16] p-6">
        {/* Header */}
        <header className="flex justify-between items-center pb-5 mb-5 border-b border-slate-800/70 shrink-0">
          <div>
            <h2 className="text-2xl font-bold capitalize text-slate-100 font-sans tracking-tight">
              {q.activeTab === "strategies" ? "Strategy Workspace" : q.activeTab.replace("-", " ")}
            </h2>
            <p className="text-xs text-slate-400 mt-1">{tabDescriptions[q.activeTab] || ""}</p>
          </div>
          <div className="flex items-center gap-3">
            {q.selectedStrategyId && (
              <div className="px-3 py-1 bg-slate-900 border border-slate-800 text-xs rounded-full text-blue-400 font-mono">
                Strategy: {q.strategies.find((s: any) => s.id === q.selectedStrategyId)?.name || q.selectedStrategyId}
              </div>
            )}
            {q.selectedRunId && (
              <div className="px-3 py-1 bg-slate-900 border border-slate-800 text-xs rounded-full text-emerald-400 font-mono">
                Run: {q.selectedRunId}
              </div>
            )}
          </div>
        </header>

        <ErrorBanners apiErrors={q.apiErrors} clearEndpointError={q.clearEndpointError} />

        {/* TAB CONTENT */}
        <div className="flex-1 min-h-0">
          {q.activeTab === "dashboard" && (
            <DashboardTab
              smartapiConnected={q.smartapiConnected}
              datasets={q.datasets}
              strategies={q.strategies}
              backtestRuns={q.backtestRuns}
              selectedStrategyId={q.selectedStrategyId}
              btStartDate={q.btStartDate}
              btEndDate={q.btEndDate}
              setBtStartDate={q.setBtStartDate}
              setBtEndDate={q.setBtEndDate}
              handleSelectStrategy={q.handleSelectStrategy}
              handleRunBacktest={q.handleRunBacktest}
              triggerAuth={q.triggerAuth}
              handleSelectRun={q.handleSelectRun}
            />
          )}

          {q.activeTab === "datasets" && (
            <DatasetsTab
              dlSymbol={q.dlSymbol}
              setDlSymbol={q.setDlSymbol}
              dlInterval={q.dlInterval}
              setDlInterval={q.setDlInterval}
              dlFromDate={q.dlFromDate}
              setDlFromDate={q.setDlFromDate}
              dlToDate={q.dlToDate}
              setDlToDate={q.setDlToDate}
              downloading={q.downloading}
              triggerDownload={q.triggerDownload}
              datasets={q.datasets}
              selectedDataset={q.selectedDataset}
              setSelectedDataset={q.setSelectedDataset}
              suggestions={q.suggestions}
              showSuggestions={q.showSuggestions}
              setShowSuggestions={q.setShowSuggestions}
              triggerNotif={q.triggerNotif}
            />
          )}

          {q.activeTab === "strategies" && (
            <StrategiesTab
              strategies={q.strategies}
              selectedStrategyId={q.selectedStrategyId}
              handleSelectStrategy={q.handleSelectStrategy}
              handleNewStrategy={q.handleNewStrategy}
              handleSaveStrategy={q.handleSaveStrategy}
              code={q.code}
              setCode={q.setCode}
              fileInputRef={q.fileInputRef}
              uploadedFileName={q.uploadedFileName}
              setUploadedFileName={q.setUploadedFileName}
              handleFileUpload={q.handleFileUpload}
              strategyName={q.strategyName}
              setStrategyName={q.setStrategyName}
              strategySymbols={q.strategySymbols}
              setStrategySymbols={q.setStrategySymbols}
              strategyInterval={q.strategyInterval}
              setStrategyInterval={q.setStrategyInterval}
              strategyCapital={q.strategyCapital}
              setStrategyCapital={q.setStrategyCapital}
              strategyMaxPos={q.strategyMaxPos}
              setStrategyMaxPos={q.setStrategyMaxPos}
              strategyRuntimeType={q.strategyRuntimeType}
              setStrategyRuntimeType={q.setStrategyRuntimeType}
              strategyEntrypoint={q.strategyEntrypoint}
              setStrategyEntrypoint={q.setStrategyEntrypoint}
              strategyParams={q.strategyParams}
              setStrategyParams={q.setStrategyParams}
              strategyRisk={q.strategyRisk}
              setStrategyRisk={q.setStrategyRisk}
              strategySuggestions={q.strategySuggestions}
              showStrategySuggestions={q.showStrategySuggestions}
              setShowStrategySuggestions={q.setShowStrategySuggestions}
              setActiveTab={q.setActiveTab}
              triggerNotif={q.triggerNotif}
            />
          )}

          {q.activeTab === "backtests" && (
            <BacktestsTab
              strategies={q.strategies}
              selectedStrategyId={q.selectedStrategyId}
              handleSelectStrategy={q.handleSelectStrategy}
              btStartDate={q.btStartDate}
              setBtStartDate={q.setBtStartDate}
              btEndDate={q.btEndDate}
              setBtEndDate={q.setBtEndDate}
              btSlippage={q.btSlippage}
              setBtSlippage={q.setBtSlippage}
              btTradeType={q.btTradeType}
              setBtTradeType={q.setBtTradeType}
              btIsAutoMaxPos={q.btIsAutoMaxPos}
              setBtIsAutoMaxPos={q.setBtIsAutoMaxPos}
              btAutoMaxPosValue={q.btAutoMaxPosValue}
              setBtAutoMaxPosValue={q.setBtAutoMaxPosValue}
              btMaxPositionSize={q.btMaxPositionSize}
              setBtMaxPositionSize={q.setBtMaxPositionSize}
              handleRunBacktest={q.handleRunBacktest}
              backtestDetail={q.backtestDetail}
              backtestRuns={q.backtestRuns}
              handleSelectRun={q.handleSelectRun}
              showEmaFast={q.showEmaFast}
              setShowEmaFast={q.setShowEmaFast}
              showEmaSlow={q.showEmaSlow}
              setShowEmaSlow={q.setShowEmaSlow}
              showBuyTrades={q.showBuyTrades}
              setShowBuyTrades={q.setShowBuyTrades}
              showSellTrades={q.showSellTrades}
              setShowSellTrades={q.setShowSellTrades}
              isPlaying={q.isPlaying}
              setIsPlaying={q.setIsPlaying}
              playbackSpeed={q.playbackSpeed}
              setPlaybackSpeed={q.setPlaybackSpeed}
              currentStep={q.currentStep}
              setCurrentStep={q.setCurrentStep}
              replayEvents={q.replayEvents}
              currentEvent={q.currentEvent}
              currentPortfolio={q.currentPortfolio}
              activeCandles={q.activeCandles}
              activeTrades={q.activeTrades}
              positionCurveData={q.positionCurveData}
            />
          )}

          {q.activeTab === "deployments" && (
            <DeploymentsTab
              deploymentFormOpen={q.deploymentFormOpen}
              setDeploymentFormOpen={q.setDeploymentFormOpen}
              depStrategyId={q.depStrategyId}
              setDepStrategyId={q.setDepStrategyId}
              depName={q.depName}
              setDepName={q.setDepName}
              depSymbol={q.depSymbol}
              setDepSymbol={q.setDepSymbol}
              depMode={q.depMode}
              setDepMode={q.setDepMode}
              handleCreateDeployment={q.handleCreateDeployment}
              handleDeleteDeployment={q.handleDeleteDeployment}
              strategies={q.strategies}
              deployments={q.deployments}
            />
          )}

          {q.activeTab === "research" && (
            <ResearchLab
              datasets={q.datasets}
              apiErrors={q.apiErrors}
              setEndpointError={q.setEndpointError}
              clearEndpointError={q.clearEndpointError}
              setNotif={q.setNotif}
            />
          )}

          {q.activeTab === "optimizer" && (
            <OptimizerTab
              optParamName1={q.optParamName1}
              setOptParamName1={q.setOptParamName1}
              optParamVals1={q.optParamVals1}
              setOptParamVals1={q.setOptParamVals1}
              optParamName2={q.optParamName2}
              setOptParamName2={q.setOptParamName2}
              optParamVals2={q.optParamVals2}
              setOptParamVals2={q.setOptParamVals2}
              handleRunOptimization={q.handleRunOptimization}
              optimizationGrid={q.optimizationGrid}
            />
          )}

          {q.activeTab === "cleanup" && (
            <CleanupTab
              cleanupStatus={q.cleanupStatus}
              cleanupLoading={q.cleanupLoading}
              cleanupDryRun={q.cleanupDryRun}
              setCleanupDryRun={q.setCleanupDryRun}
              cleanupTarget={q.cleanupTarget}
              setCleanupTarget={q.setCleanupTarget}
              cleanupSymbol={q.cleanupSymbol}
              setCleanupSymbol={q.setCleanupSymbol}
              cleanupInterval={q.cleanupInterval}
              setCleanupInterval={q.setCleanupInterval}
              cleanupOlderThan={q.cleanupOlderThan}
              setCleanupOlderThan={q.setCleanupOlderThan}
              cleanupStrategyId={q.cleanupStrategyId}
              setCleanupStrategyId={q.setCleanupStrategyId}
              cleanupResult={q.cleanupResult}
              fetchCleanupStatus={q.fetchCleanupStatus}
              handleRunCleanup={q.handleRunCleanup}
              handleVacuumDB={q.handleVacuumDB}
            />
          )}
        </div>
      </main>

      <TotpModal
        isOpen={q.isTotpModalOpen}
        totpInput={q.totpInput}
        setTotpInput={q.setTotpInput}
        pendingAction={q.pendingAction}
        onConfirm={q.handleTotpConfirm}
        onCancel={() => { q.setIsTotpModalOpen(false); q.setTotpInput(""); q.setPendingAction(null); }}
      />
    </div>
  );
}
