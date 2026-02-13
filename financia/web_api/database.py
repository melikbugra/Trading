from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    Integer,
    Boolean,
    JSON,
    DateTime,
    Date,
    Enum as SQLEnum,
)
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timedelta, date, time
from typing import Optional
import enum
import os
import pytz

# Turkey timezone constant
TZ_TURKEY = pytz.timezone("Europe/Istanbul")


# ============= Simulation Time Manager =============
class SimulationTimeManager:
    """
    Singleton class to manage simulation time.
    When simulation is active, now_turkey() returns simulation time instead of real time.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Simulation state
        self.is_active: bool = False
        self.is_paused: bool = False
        self.day_completed: bool = False
        self.is_eod_running: bool = False  # Track if EOD analysis is in progress
        self.is_scanning: bool = False  # Track if scan is in progress
        self.hour_completed: bool = (
            False  # Track if current hour scan is done (waiting for manual advance)
        )
        self.is_backtest: bool = False  # Track if running in backtest mode

        # Simulation time settings
        self.current_time: Optional[datetime] = None
        self.start_date: Optional[date] = None
        self.end_date: Optional[date] = None
        self.seconds_per_hour: int = 30  # Default: 1 sim hour = 30 real seconds

        # Session tracking
        self.session_id: Optional[int] = None

        # Balance tracking
        self.initial_balance: float = 100000.0  # Default 100,000 TL
        self.current_balance: float = 100000.0
        self.total_profit: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.losing_trades: int = 0

    def start(
        self,
        start_date: date,
        end_date: date,
        seconds_per_hour: int = 30,
        initial_balance: float = 100000.0,
        is_backtest: bool = False,
    ):
        """Start a new simulation session."""
        self.is_active = True
        self.is_paused = False
        self.day_completed = False
        self.is_eod_running = False
        self.hour_completed = False
        self.is_backtest = is_backtest
        self.start_date = start_date
        self.end_date = end_date
        self.seconds_per_hour = seconds_per_hour
        # Balance initialization
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.total_profit = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        # Start at 09:30 on the first trading day (timezone-aware)
        naive_time = datetime.combine(start_date, time(9, 30))
        self.current_time = TZ_TURKEY.localize(naive_time)
        # Skip to next trading day if weekend
        self._skip_weekend()

    def stop(self):
        """Stop the simulation."""
        self.is_active = False
        self.is_paused = False
        self.day_completed = False
        self.is_eod_running = False
        self.is_scanning = False
        self.hour_completed = False
        self.is_backtest = False
        self.current_time = None
        self.start_date = None
        self.end_date = None
        self.session_id = None
        # Reset balance tracking
        self.initial_balance = 100000.0
        self.current_balance = 100000.0
        self.total_profit = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

    def pause(self):
        """Pause the simulation."""
        self.is_paused = True

    def resume(self):
        """Resume the simulation."""
        self.is_paused = False
        self.day_completed = False
        self.hour_completed = False

    def advance_hour(self) -> bool:
        """
        Advance simulation time by 1 hour.
        Returns True if day is completed (reached 18:00 - BIST closes at 18:00).
        """
        if not self.is_active or not self.current_time:
            return False

        self.current_time += timedelta(hours=1)

        # Check if day is completed (18:00 - BIST closes)
        if self.current_time.hour >= 18:
            self.day_completed = True
            return True

        return False

    def next_day(self) -> bool:
        """
        Move to the next trading day.
        Returns True if simulation is complete (past end_date).
        """
        if not self.is_active or not self.current_time:
            return True

        # Move to next day at 09:30 (keep timezone-aware)
        next_date = self.current_time.date() + timedelta(days=1)
        naive_time = datetime.combine(next_date, time(9, 30))
        self.current_time = TZ_TURKEY.localize(naive_time)

        # Skip weekends
        self._skip_weekend()

        # Check if simulation is complete
        if self.current_time.date() > self.end_date:
            return True

        self.day_completed = False
        self.is_paused = False
        self.hour_completed = False
        return False

    def _skip_weekend(self):
        """Skip to Monday if current day is weekend."""
        if self.current_time:
            while self.current_time.weekday() >= 5:  # Saturday=5, Sunday=6
                # Keep timezone when adding days
                next_date = self.current_time.date() + timedelta(days=1)
                naive_time = datetime.combine(next_date, time(9, 30))
                self.current_time = TZ_TURKEY.localize(naive_time)

    def get_time(self) -> datetime:
        """Get current simulation time or real time if not in simulation."""
        if self.is_active and self.current_time:
            return self.current_time
        return datetime.utcnow() + timedelta(hours=3)  # Real Turkey time

    def record_trade(self, profit_tl: float, is_winner: bool):
        """Record a completed trade and update balance."""
        self.current_balance += profit_tl
        self.total_profit += profit_tl
        self.total_trades += 1
        if is_winner:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

    def get_balance_stats(self) -> dict:
        """Get current balance statistics."""
        profit_percent = (
            ((self.current_balance - self.initial_balance) / self.initial_balance * 100)
            if self.initial_balance > 0
            else 0
        )
        win_rate = (
            (self.winning_trades / self.total_trades * 100)
            if self.total_trades > 0
            else 0
        )
        return {
            "initial_balance": self.initial_balance,
            "current_balance": round(self.current_balance, 2),
            "total_profit": round(self.total_profit, 2),
            "profit_percent": round(profit_percent, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(win_rate, 1),
        }

    def get_status(self) -> dict:
        """Get current simulation status."""
        status = {
            "is_active": self.is_active,
            "is_paused": self.is_paused,
            "day_completed": self.day_completed,
            "is_eod_running": self.is_eod_running,
            "is_scanning": self.is_scanning,
            "hour_completed": self.hour_completed,
            "is_backtest": self.is_backtest,
            "current_time": self.current_time.isoformat()
            if self.current_time
            else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "seconds_per_hour": self.seconds_per_hour,
            "session_id": self.session_id,
        }
        # Add balance stats
        status.update(self.get_balance_stats())
        return status


# Global simulation time manager instance
simulation_time_manager = SimulationTimeManager()


def now_turkey():
    """Return current time in Turkey timezone (UTC+3), or simulation time if active."""
    return simulation_time_manager.get_time()


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


# ============= Simulation Tables =============
class SimStrategy(Base):
    """Simulation strategies - mirrors Strategy table structure"""

    __tablename__ = "sim_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, default="")
    strategy_type = Column(String, nullable=False)
    params = Column(JSON, default={})
    risk_reward_ratio = Column(Float, default=2.0)
    horizon = Column(String, default="short")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_turkey)


class SimWatchlistItem(Base):
    """Simulation watchlist - mirrors WatchlistItem table structure"""

    __tablename__ = "sim_watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False)
    market = Column(String, nullable=False)
    strategy_id = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    added_at = Column(DateTime, default=now_turkey)


class SimSignal(Base):
    """Simulation signals - mirrors Signal table structure"""

    __tablename__ = "sim_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False)
    market = Column(String, nullable=False)
    strategy_id = Column(Integer, nullable=False)
    status = Column(String, default="pending")

    # Signal details
    direction = Column(String, default="long")
    entry_price = Column(Float, nullable=True)
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
    entry_reached = Column(Boolean, default=False)
    actual_entry_price = Column(Float, nullable=True)

    # Lot tracking
    lots = Column(Float, default=0.0)
    remaining_lots = Column(Float, default=0.0)

    # Extra data
    notes = Column(String, default="")
    extra_data = Column(JSON, default={})


class SimTradeHistory(Base):
    """Simulation trade history - mirrors TradeHistory table structure"""

    __tablename__ = "sim_trade_history"

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

    result = Column(String, nullable=False)
    profit_percent = Column(Float, default=0.0)
    profit_tl = Column(Float, default=0.0)
    lots = Column(Float, default=0.0)
    risk_reward_achieved = Column(Float, default=0.0)

    entered_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, default=now_turkey)
    notes = Column(String, default="")


class SimScannerConfig(Base):
    """Simulation scanner configuration"""

    __tablename__ = "sim_scanner_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    last_scan_at = Column(DateTime, nullable=True)


class SimSession(Base):
    """Simulation session tracking"""

    __tablename__ = "sim_session"

    id = Column(Integer, primary_key=True, autoincrement=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    current_date = Column(Date, nullable=True)
    seconds_per_hour = Column(Integer, default=30)
    status = Column(String, default="active")  # active, paused, completed, stopped
    created_at = Column(DateTime, default=now_turkey)
    completed_at = Column(DateTime, nullable=True)


def clear_simulation_data():
    """Clear all simulation data from sim_* tables. Called when starting a new simulation."""
    db = SessionLocal()
    try:
        db.query(SimSignal).delete()
        db.query(SimTradeHistory).delete()
        db.query(SimScannerConfig).delete()
        db.query(SimSession).delete()
        db.query(SimWatchlistItem).delete()
        db.query(SimStrategy).delete()
        db.commit()
        print("[Database] Simulation data cleared")
    except Exception as e:
        print(f"[Database] Error clearing simulation data: {e}")
        db.rollback()
    finally:
        db.close()


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
