from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime

class Candle(BaseModel):
    time: str  # ISO string or YYYY-MM-DD HH:MM:SS
    open: float
    high: float
    low: float
    close: float
    volume: int
    open_interest: int = 0

class OrderRequest(BaseModel):
    symbol: str
    direction: str  # BUY or SELL
    type: str  # MARKET or LIMIT
    price: float
    qty: int
    trigger_price: float = 0.0

class Order(BaseModel):
    id: str
    symbol: str
    direction: str
    type: str
    price: float
    qty: int
    status: str  # PENDING, FILLED, CANCELLED, REJECTED
    trigger_price: float = 0.0
    created_at: str
    filled_at: Optional[str] = None
    filled_qty: int = 0
    avg_fill_price: float = 0.0

class Trade(BaseModel):
    id: str
    order_id: str
    timestamp: str
    symbol: str
    direction: str
    price: float
    qty: int
    value: float
    slippage: float = 0.0
    brokerage: float = 0.0
    stt: float = 0.0
    exc_charges: float = 0.0
    gst: float = 0.0
    sebi_charges: float = 0.0
    stamp_duty: float = 0.0
    total_charges: float = 0.0

class Position(BaseModel):
    symbol: str
    qty: int = 0  # positive for long, negative for short
    avg_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    margin_required: float = 0.0

class Portfolio(BaseModel):
    cash: float
    margin_used: float = 0.0
    margin_free: float = 0.0
    equity: float = 0.0
    unrealized_pnl: float = 0.0
    positions: Dict[str, Position] = Field(default_factory=dict)
    total_fees: float = 0.0
    total_pnl: float = 0.0

class MarketState(BaseModel):
    current_time: str
    current_candle: Dict[str, Candle]  # symbol -> current candle
    historical_candles: Dict[str, List[Candle]]  # symbol -> past candles list (sliding window)
    positions: Dict[str, Position]
    portfolio: Portfolio
    active_orders: List[Order]

class ReplayEvent(BaseModel):
    step: int
    timestamp: str
    candle: Dict[str, Candle]
    orders_submitted: List[OrderRequest] = Field(default_factory=list)
    orders_filled: List[Trade] = Field(default_factory=list)
    portfolio: Portfolio
    log_messages: List[str] = Field(default_factory=list)

class BacktestRunMetadata(BaseModel):
    id: str
    strategy_name: str
    symbol: str
    interval: str
    start_time: str
    end_time: str
    initial_capital: float
    status: str  # RUNNING, COMPLETED, FAILED
    error_message: Optional[str] = None
    created_at: str
