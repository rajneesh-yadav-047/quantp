"use client";

import React, { useState, useEffect, useMemo } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useAxon } from "./hooks/useAxon";
import AxonSidebar from "./components/shared/AxonSidebar";
import { TotpModal, ErrorBanners, DashboardTab, DatasetsTab } from "./components/tabs/DashboardTab";
import { StrategiesTab } from "./components/tabs/StrategiesTab";
import { BacktestsTab } from "./components/tabs/BacktestsTab";
import { DeploymentsTab } from "./components/tabs/DeploymentsTab";
import { OptimizerTab } from "./components/tabs/OptimizerTab";
import { CleanupTab } from "./components/tabs/CleanupTab";

const ResearchLab = dynamic(() => import("../components/ResearchLab"), { ssr: false });
const MultiAssetResearch = dynamic(() => import("../components/MultiAssetResearch"), { ssr: false });
const PortfolioAnalytics = dynamic(() => import("../components/PortfolioAnalytics"), { ssr: false });

/* ── Top nav sections ── */
const topSections = [
  { id: "overview", label: "Overview", tab: "dashboard" },
  { id: "data", label: "Data", tab: "datasets" },
  { id: "strategies", label: "Strategies", tab: "strategies" },
  { id: "trading", label: "Trading", tab: "deployments" },
  { id: "research", label: "Research", tab: "research" },
];

function getSectionForTab(tab: string): string {
  for (const s of topSections) {
    if (s.tab === tab) return s.id;
  }
  if (["backtests", "optimizer"].includes(tab)) return "strategies";
  if (["deployments", "live", "cleanup"].includes(tab)) return "trading";
  if (["research", "multi-asset", "portfolio-risk"].includes(tab)) return "research";
  return "overview";
}

function getSectionLabel(tab: string): string {
  return topSections.find((s) => s.id === getSectionForTab(tab))?.label ?? "Overview";
}

export default function Home() {
  const q = useAxon();
  const router = useRouter();
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const savedTheme = localStorage.getItem("theme") as "dark" | "light" | null;
    if (savedTheme === "light" || savedTheme === "dark") {
      setTheme(savedTheme);
    } else {
      setTheme("dark");
    }
  }, []);

  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    localStorage.setItem("theme", theme);
  }, [theme]);

  const currentSection = useMemo(() => getSectionForTab(q.activeTab), [q.activeTab]);
  const sectionLabel = useMemo(() => getSectionLabel(q.activeTab), [q.activeTab]);

  const tabDescriptions: Record<string, string> = {
    dashboard: "System overview, connection status, and quick actions.",
    datasets: "Manage historical candle data directories saved in CSV and Excel formats.",
    strategies: "Primary workspace. Configure symbols, interval, capital, risk settings, and strategy code.",
    backtests: "Run strategies and view results: equity curve, PnL, drawdown, trade history, per-symbol performance.",
    deployments: "Manage paper and live deployments per strategy.",
    live: "Real-time mock trading with live market data. No real money used.",
    research: "Deep statistical analysis of any dataset — returns, volatility, regimes, seasonality, and strategy suitability scoring.",
    "multi-asset": "Multi-asset research: correlation matrices, pair discovery, cointegration, spread analysis, lead-lag, sector breadth, and factor ranking.",
    "portfolio-risk": "Portfolio risk analytics: Monte Carlo simulation, stress testing, risk-of-ruin, drawdown projections, and confidence intervals.",
    optimizer: "Execute grid-search and random-search sweeps to find mathematically optimal strategy weights.",
    cleanup: "Manage disk space by deleting old backtest logs and downloaded CSV datasets.",
  };

  return (
    <div className="flex flex-col h-screen bg-[var(--ax-bg)] font-space">
      {/* ── Top Navigation Bar ── */}
      <nav className="h-11 bg-[#0a0a0a] border-b border-[var(--ax-border)] flex items-center px-4 shrink-0">
        <span className="text-sm font-semibold text-[#e8e8e8] tracking-tight mr-2">Axon</span>
        <div className="w-px h-4 bg-[var(--ax-border)] mx-3" />
        {topSections.map((section) => {
          const isActive = currentSection === section.id;
          const isHighlighted = section.id === "trading";
          return (
            <button
              key={section.id}
              onClick={() => {
                q.setActiveTab(section.tab);
              }}
              className={`h-11 px-3 text-xs flex items-center gap-1 border-b-2 transition-colors ${
                isActive
                  ? isHighlighted
                    ? "text-[#93b4ff] border-b-[#4a7fcc]"
                    : "text-[#d0d0d0] border-b-[#d0d0d0]"
                  : "text-[#505050] border-transparent hover:text-[#888]"
              }`}
            >
              {section.label}
            </button>
          );
        })}
        <div className="flex-1" />
        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5" />
        <span className="text-xs text-[#444]">NSE live</span>
        <span className="ml-2 text-xs px-2 py-0.5 rounded border border-[var(--ax-border)] text-[#555]">SmartAPI</span>
      </nav>

      {/* ── Sidebar + Main Content ── */}
      <div className="flex flex-1 overflow-hidden">
        <AxonSidebar
          activeTab={q.activeTab}
          setActiveTab={(id) => {
            if (id === "live") {
              router.push("/live");
            } else {
              q.setActiveTab(id);
            }
          }}
          notif={q.notif}
          backendOnline={q.backendOnline}
          smartapiConnected={q.smartapiConnected}
          theme={theme}
          setTheme={setTheme}
        />

        <main className="flex-1 flex flex-col overflow-hidden">
          {/* ── Page Header Bar ── */}
          <div className="h-9 bg-[var(--ax-header-bg)] border-b border-[var(--ax-border)] flex items-center px-4 gap-2 shrink-0">
            {/* Breadcrumb */}
            <div className="flex items-center gap-1 text-xs">
              <span className="text-[#a0a0a0]">{sectionLabel}</span>
              <span className="text-[#606060]">›</span>
              <span className="text-[#c0c0c0]">
                {q.activeTab === "strategies" ? "Strategy Workspace" : q.activeTab.replace("-", " ")}
              </span>
            </div>
            <div className="flex-1" />
            {/* Page-level action buttons */}
            {q.selectedStrategyId && (
              <div className="px-3 py-1 text-[10px] rounded-full font-mono font-medium bg-[var(--ax-surface-2)] border border-[var(--ax-border)] text-[var(--ax-accent-blue-light)]">
                Strategy: {q.strategies.find((s: any) => s.id === q.selectedStrategyId)?.name || q.selectedStrategyId}
              </div>
            )}
            {q.selectedRunId && (
              <div className="px-3 py-1 text-[10px] rounded-full font-mono font-medium bg-[var(--ax-surface-2)] border border-[var(--ax-border)] text-emerald-400">
                Run: {q.selectedRunId}
              </div>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            <ErrorBanners apiErrors={q.apiErrors} clearEndpointError={q.clearEndpointError} />

            {/* ── TAB CONTENT ── */}
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
                  dlJobId={q.dlJobId}
                  dlJobProgress={q.dlJobProgress}
                  triggerDownload={q.triggerDownload}
                  datasets={q.datasets}
                  selectedDataset={q.selectedDataset}
                  setSelectedDataset={q.setSelectedDataset}
                  suggestions={q.suggestions}
                  showSuggestions={q.showSuggestions}
                  setShowSuggestions={q.setShowSuggestions}
                  triggerNotif={q.triggerNotif}
                  previewData={q.previewData}
                  setPreviewData={q.setPreviewData}
                  previewLoading={q.previewLoading}
                  previewError={q.previewError}
                  handlePreviewDataset={q.handlePreviewDataset}
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
                  pnlCurveData={q.pnlCurveData}
                  datasets={q.datasets}
                  checkDataCoverage={q.checkDataCoverage}
                  pendingBacktest={q.pendingBacktest}
                  setPendingBacktest={q.setPendingBacktest}
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
                  theme={theme}
                />
              )}

              {q.activeTab === "multi-asset" && (
                <MultiAssetResearch
                  datasets={q.datasets}
                  theme={theme}
                  setNotif={q.setNotif}
                  backendOnline={q.backendOnline}
                  dlSymbol={q.dlSymbol}
                  setDlSymbol={q.setDlSymbol}
                  dlInterval={q.dlInterval}
                  setDlInterval={q.setDlInterval}
                  dlFromDate={q.dlFromDate}
                  setDlFromDate={q.setDlFromDate}
                  dlToDate={q.dlToDate}
                  setDlToDate={q.setDlToDate}
                  pendingMultiAsset={q.pendingMultiAsset}
                  setPendingMultiAsset={q.setPendingMultiAsset}
                  multiAssetRetrySignal={q.multiAssetRetrySignal}
                  setIsTotpModalOpen={q.setIsTotpModalOpen}
                  setPendingAction={q.setPendingAction}
                  setDownloadQueue={q.setDownloadQueue}
                />
              )}

              {q.activeTab === "portfolio-risk" && (
                <PortfolioAnalytics
                  backtestResults={q.backtestRuns || []}
                  theme={theme}
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
          </div>
        </main>
      </div>

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
