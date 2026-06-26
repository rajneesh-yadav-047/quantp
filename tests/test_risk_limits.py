import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import StrategyDB
from backend.services.deployment_orchestrator import DeploymentOrchestrator
from engine.execution_engine import TradeEvent

class TestRiskLimits(unittest.TestCase):
    def setUp(self):
        self.strategy = StrategyDB(
            id="test-strategy-id",
            name="Test Strategy",
            code="pass",
            risk_settings_json=json.dumps({"max_drawdown_pct": 2.0})
        )
        self.orchestrator = DeploymentOrchestrator(
            deployment_id="test-deployment-id",
            strategy=self.strategy,
            symbol="NSE:SBIN-EQ",
            interval="FIVE_MINUTE",
            initial_capital=100000.0
        )
        
        # Mock services that start() normally initializes
        self.orchestrator.execution_engine = MagicMock()
        self.orchestrator.event_bus = MagicMock()
        self.orchestrator.persistence = MagicMock()
        self.orchestrator.strategy_executor = MagicMock()
        self.orchestrator.status = "running"
        self.orchestrator.current_prices = {"NSE:SBIN-EQ": 100.0}
        
    def test_no_risk_breach_when_equity_high(self):
        # Set equity to 99,000 (only 1% loss, which is below the 2% drawdown limit)
        portfolio = MagicMock()
        portfolio.equity = 99000.0
        self.orchestrator.execution_engine.portfolio_mgr.portfolio = portfolio
        
        self.orchestrator._check_risk_limits(ts_seconds=1600000000)
        
        # Verify no liquidation was triggered and orchestrator was not paused
        self.orchestrator.execution_engine.liquidate_all_positions.assert_not_called()
        self.assertEqual(self.orchestrator.status, "running")
        
    def test_risk_breach_triggers_liquidation_and_pause(self):
        # Set equity to 97,500 (2.5% loss, which is above the 2% drawdown limit)
        portfolio = MagicMock()
        portfolio.equity = 97500.0
        self.orchestrator.execution_engine.portfolio_mgr.portfolio = portfolio
        
        # Setup mock trade events returned by liquidation
        mock_event = TradeEvent(
            trade_id="trade-123",
            order_id="order-123",
            symbol="NSE:SBIN-EQ",
            direction="SELL",
            price=97.5,
            qty=10,
            value=975.0,
            total_charges=5.0,
            timestamp="1600000000"
        )
        self.orchestrator.execution_engine.liquidate_all_positions.return_value = [mock_event]
        
        # Mock self._handle_trade_event and self.pause
        self.orchestrator._handle_trade_event = MagicMock()
        self.orchestrator.pause = MagicMock()
        
        self.orchestrator._check_risk_limits(ts_seconds=1600000000)
        
        # Verify liquidation was called
        self.orchestrator.execution_engine.liquidate_all_positions.assert_called_once_with(
            current_prices={"NSE:SBIN-EQ": 100.0},
            timestamp="1600000000"
        )
        # Verify handle_trade_event was called with the risk_liquidation reason
        self.orchestrator._handle_trade_event.assert_called_once_with(mock_event, 1600000000, "risk_liquidation")
        # Verify orchestrator pause was triggered
        self.orchestrator.pause.assert_called_once()

if __name__ == "__main__":
    unittest.main()
