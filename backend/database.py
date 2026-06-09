"""
Database models for QuantLab metadata and results.

Supports both legacy on_bar and Prosperity trader.py strategies.
"""

import os
import uuid
from datetime import datetime
from typing import Generator
from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Environment: Fallback to SQLite if DATABASE_URL not specified
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quantlab.db")

# Setup engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class StrategyDB(Base):
    """Stores strategy code and metadata."""
    __tablename__ = "strategies"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    code = Column(Text, nullable=False)  # Full strategy source code
    
    # NEW: Runtime type and entrypoint
    runtime_type = Column(String, default="legacy_on_bar", nullable=False)  # "legacy_on_bar" or "prosperity_trader"
    entrypoint = Column(String, nullable=True)  # e.g., "trader.py:Trader" for Prosperity
    
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BacktestResultDB(Base):
    """Stores backtest run results and metadata."""
    __tablename__ = "backtest_results"

    id = Column(String, primary_key=True)
    strategy_id = Column(String, nullable=True)
    strategy_name = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    interval = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)

    initial_capital = Column(Float, nullable=False)
    final_equity = Column(Float, nullable=False)
    total_pnl = Column(Float, nullable=False)

    cagr = Column(Float, nullable=False)
    sharpe_ratio = Column(Float, nullable=False)
    sortino_ratio = Column(Float, nullable=False)
    max_drawdown = Column(Float, nullable=False)
    win_rate = Column(Float, nullable=False)
    profit_factor = Column(Float, nullable=False)
    total_fees = Column(Float, nullable=False)
    max_position_size = Column(Integer, nullable=True)

    log_file_path = Column(String, nullable=False)  # Path to JSONL replay events
    metrics_json = Column(Text, nullable=False)  # JSON: detailed metrics, trades, cost breakdown

    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Initialize database tables and perform migrations."""
    Base.metadata.create_all(bind=engine)

    # Migration 1: Add max_position_size to backtest_results
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE backtest_results ADD COLUMN max_position_size INTEGER"))
            conn.commit()
            print("INFO: Database migration: Added 'max_position_size' column.")
    except Exception:
        pass  # Column likely exists

    # Migration 2: Add runtime_type and entrypoint to strategies
    try:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE strategies ADD COLUMN runtime_type TEXT DEFAULT "legacy_on_bar"'))
            conn.commit()
            print("INFO: Database migration: Added 'runtime_type' column.")
    except Exception:
        pass

    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE strategies ADD COLUMN entrypoint TEXT"))
            conn.commit()
            print("INFO: Database migration: Added 'entrypoint' column.")
    except Exception:
        pass


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to inject database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
