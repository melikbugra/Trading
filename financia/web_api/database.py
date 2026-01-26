from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    Integer,
    Boolean,
    JSON,
    DateTime,
    Enum as SQLEnum,
)
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timedelta
import enum
import os


def now_turkey():
    """Return current time in Turkey timezone (UTC+3)."""
    return datetime.utcnow() + timedelta(hours=3)


DATABASE_URL = "sqlite:///./data/portfolio.db"
# Ensure data directory exists
if not os.path.exists("./data"):
    os.makedirs("./data")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ============= Enums =============
class MarketType(str, enum.Enum):
    BIST100 = "bist100"
    BINANCE = "binance"


class SignalStatus(str, enum.Enum):
    PENDING = "pending"  # Ön koşul sağlandı, ana koşul bekleniyor
    TRIGGERED = "triggered"  # Ana koşul sağlandı, giriş bekliyor
    ENTERED = "entered"  # Pozisyona girildi
    STOPPED = "stopped"  # Stop loss tetiklendi
    TARGET_HIT = "target_hit"  # Take profit tetiklendi
    CANCELLED = "cancelled"  # İptal edildi (ön koşul bozuldu)


# ============= Strategy Tables =============
class Strategy(Base):
    """User-defined strategies"""

    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)  # e.g., "EMA200_MACD"
    description = Column(String, default="")
    strategy_type = Column(String, nullable=False)  # Class name: "EMAMACDStrategy"
    params = Column(JSON, default={})  # Strategy-specific parameters
    risk_reward_ratio = Column(Float, default=2.0)
    horizon = Column(
        String, default="short"
    )  # Timeframe: short, short-mid, medium, long
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_turkey)


class WatchlistItem(Base):
    """Tickers being watched for a strategy"""

    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False)
    market = Column(String, nullable=False)  # "bist100" or "binance"
    strategy_id = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    added_at = Column(DateTime, default=now_turkey)


class Signal(Base):
    """Active signals from strategies"""

    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False)
    market = Column(String, nullable=False)
    strategy_id = Column(Integer, nullable=False)
    status = Column(
        String, default="pending"
    )  # pending, triggered, entered, stopped, target_hit, cancelled

    # Signal details
    direction = Column(String, default="long")  # long or short
    entry_price = Column(Float, nullable=True)  # Calculated entry price
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)

    # Peak/Trough data
    last_peak = Column(Float, nullable=True)
    last_trough = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=now_turkey)
    triggered_at = Column(DateTime, nullable=True)
    entered_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Entry confirmation
    entry_reached = Column(Boolean, default=False)  # True when price hits entry level
    actual_entry_price = Column(Float, nullable=True)  # User's actual entry price

    # Lot tracking
    lots = Column(Float, default=0.0)  # Total lots entered
    remaining_lots = Column(Float, default=0.0)  # Remaining lots (for partial exits)

    # Extra data
    notes = Column(String, default="")
    extra_data = Column(JSON, default={})


class TradeHistory(Base):
    """Completed trades"""

    __tablename__ = "trade_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(Integer, nullable=False)
    ticker = Column(String, nullable=False)
    market = Column(String, nullable=False)
    strategy_id = Column(Integer, nullable=False)

    direction = Column(String, default="long")
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)

    result = Column(String, nullable=False)  # "win", "loss", "breakeven"
    profit_percent = Column(Float, default=0.0)
    profit_tl = Column(Float, default=0.0)  # TL profit/loss
    lots = Column(Float, default=0.0)  # Lots sold in this trade
    risk_reward_achieved = Column(Float, default=0.0)

    entered_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, default=now_turkey)
    notes = Column(String, default="")


class ScannerConfig(Base):
    """Global scanner configuration"""

    __tablename__ = "scanner_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_interval_minutes = Column(Integer, default=5)
    is_running = Column(Boolean, default=False)
    last_scan_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=now_turkey)


# ============= BIST100 Tables =============
class BIST100PortfolioItem(Base):
    __tablename__ = "bist100_portfolio"

    ticker = Column(String, primary_key=True, index=True)
    last_decision = Column(String, default="PENDING")
    last_price = Column(Float, default=0.0)
    last_volume = Column(Float, default=0.0)
    last_volume_ratio = Column(Float, default=0.0)
    last_updated = Column(String, default="-")
    final_score = Column(Float, default=0.0)
    category_scores = Column(JSON, default={})
    indicator_details = Column(JSON, default=[])


class BIST100Recommendation(Base):
    __tablename__ = "bist100_recommendations"

    ticker = Column(String, primary_key=True, index=True)
    score = Column(Float, default=0.0)
    decision = Column(String, default="HOLD")
    price = Column(Float, default=0.0)
    divergence_count = Column(Float, default=0.0)
    last_updated = Column(String, default="-")


# ============= Binance Tables =============
class BinancePortfolioItem(Base):
    __tablename__ = "binance_portfolio"

    ticker = Column(String, primary_key=True, index=True)  # e.g., BTCUSDT
    last_decision = Column(String, default="PENDING")
    last_price = Column(Float, default=0.0)
    last_volume = Column(Float, default=0.0)
    last_volume_ratio = Column(Float, default=0.0)
    last_updated = Column(String, default="-")
    final_score = Column(Float, default=0.0)
    category_scores = Column(JSON, default={})
    indicator_details = Column(JSON, default=[])


class BinanceRecommendation(Base):
    __tablename__ = "binance_recommendations"

    ticker = Column(String, primary_key=True, index=True)
    score = Column(Float, default=0.0)
    decision = Column(String, default="HOLD")
    price = Column(Float, default=0.0)
    divergence_count = Column(Float, default=0.0)
    last_updated = Column(String, default="-")


# Legacy aliases for backward compatibility during migration
PortfolioItemDB = BIST100PortfolioItem
RecommendationDB = BIST100Recommendation


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
