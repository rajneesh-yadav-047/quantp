import os
import uuid
from datetime import datetime
from typing import Generator
from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Environment check: Fallback to local SQLite if PostgreSQL is not specified
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quantlab.db")

# Setup engine with SQLite compatibility for thread-sharing if using SQLite
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 1. User Table
class UserDB(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    
    # SmartAPI configurations
    smartapi_api_key = Column(String, nullable=True)
    smartapi_client_code = Column(String, nullable=True)
    smartapi_password = Column(String, nullable=True)
    smartapi_totp_secret = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

# 2. Strategy Table
class StrategyDB(Base):
    __tablename__ = "strategies"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    code = Column(Text, nullable=False)  # trader.py code
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 3. BacktestResult Table
class BacktestResultDB(Base):
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
    
    log_file_path = Column(String, nullable=False)
    metrics_json = Column(Text, nullable=False)  # Holds all detailed sub-metrics, trade metrics, and cost breakdown
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    """Initializes and creates all database tables."""
    Base.metadata.create_all(bind=engine)

def get_db() -> Generator[Session, None, None]:
    """Dependency to inject database session into FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
