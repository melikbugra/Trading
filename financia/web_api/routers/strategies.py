"""
Strategy API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

from financia.web_api.database import (
    get_db,
    Strategy,
    WatchlistItem,
    Signal,
    ScannerConfig,
    TradeHistory,
)
from financia.strategies import list_available_strategies, get_strategy_class
from financia.scanner import scanner

router = APIRouter(prefix="/strategies", tags=["strategies"])


# ============= Pydantic Models =============


class StrategyCreate(BaseModel):
    name: str
    description: str = ""
    strategy_type: str
    params: Dict[str, Any] = {}
    risk_reward_ratio: float = 2.0
    horizon: str = "short"  # short, short-mid, medium, long


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    risk_reward_ratio: Optional[float] = None
    is_active: Optional[bool] = None
    horizon: Optional[str] = None


class StrategyResponse(BaseModel):
    id: int
    name: str
    description: str
    strategy_type: str
    params: Dict[str, Any]
    risk_reward_ratio: float
    horizon: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class WatchlistCreate(BaseModel):
    ticker: str
    market: str  # "bist100" or "binance"
    strategy_id: int


class WatchlistResponse(BaseModel):
    id: int
    ticker: str
    market: str
    strategy_id: int
    is_active: bool
    added_at: datetime

    class Config:
        from_attributes = True


class SignalResponse(BaseModel):
    id: int
    ticker: str
    market: str
    strategy_id: int
    status: str
    direction: str
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    current_price: Optional[float]
    last_peak: Optional[float]
    last_trough: Optional[float]
    entry_reached: bool = False
    actual_entry_price: Optional[float]
    created_at: datetime
    triggered_at: Optional[datetime]
    entered_at: Optional[datetime]
    closed_at: Optional[datetime]
    notes: str
    extra_data: Dict[str, Any]

    class Config:
        from_attributes = True


class ConfirmEntryRequest(BaseModel):
    actual_entry_price: float


class TradeHistoryResponse(BaseModel):
    id: int
    signal_id: int
    ticker: str
    market: str
    strategy_id: int
    direction: str
    entry_price: float
    exit_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    result: str
    profit_percent: float
    risk_reward_achieved: float
    entered_at: datetime
    closed_at: datetime
    notes: str

    class Config:
        from_attributes = True


class ScannerConfigUpdate(BaseModel):
    scan_interval_minutes: Optional[int] = None
    is_running: Optional[bool] = None


class ScannerConfigResponse(BaseModel):
    scan_interval_minutes: int
    is_running: bool
    is_scanning: bool  # True while actively scanning
    last_scan_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============= Strategy Endpoints =============


@router.get("/available-types")
def get_available_strategy_types():
    """Get list of available strategy types."""
    strategies = []
    for name in list_available_strategies():
        cls = get_strategy_class(name)
        strategies.append(
            {
                "type": name,
                "name": cls.name if cls else name,
                "description": cls.description if cls else "",
                "default_params": cls.default_params if cls else {},
            }
        )
    return strategies


@router.get("", response_model=List[StrategyResponse])
def get_strategies(db: Session = Depends(get_db)):
    """Get all strategies."""
    return db.query(Strategy).all()


@router.post("", response_model=StrategyResponse)
def create_strategy(strategy: StrategyCreate, db: Session = Depends(get_db)):
    """Create a new strategy."""
    # Validate strategy type
    if strategy.strategy_type not in list_available_strategies():
        raise HTTPException(400, f"Unknown strategy type: {strategy.strategy_type}")

    # Check for duplicate name
    existing = db.query(Strategy).filter(Strategy.name == strategy.name).first()
    if existing:
        raise HTTPException(400, f"Strategy with name '{strategy.name}' already exists")

    db_strategy = Strategy(
        name=strategy.name,
        description=strategy.description,
        strategy_type=strategy.strategy_type,
        params=strategy.params,
        risk_reward_ratio=strategy.risk_reward_ratio,
        horizon=strategy.horizon,
    )
    db.add(db_strategy)
    db.commit()
    db.refresh(db_strategy)
    return db_strategy


@router.put("/{strategy_id}", response_model=StrategyResponse)
def update_strategy(
    strategy_id: int, update: StrategyUpdate, db: Session = Depends(get_db)
):
    """Update a strategy."""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    if update.name is not None:
        strategy.name = update.name
    if update.description is not None:
        strategy.description = update.description
    if update.params is not None:
        strategy.params = update.params
    if update.risk_reward_ratio is not None:
        strategy.risk_reward_ratio = update.risk_reward_ratio
    if update.is_active is not None:
        strategy.is_active = update.is_active
    if update.horizon is not None:
        strategy.horizon = update.horizon

    db.commit()
    db.refresh(strategy)
    return strategy


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Delete a strategy."""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    # Also delete related watchlist items and signals
    db.query(WatchlistItem).filter(WatchlistItem.strategy_id == strategy_id).delete()
    db.query(Signal).filter(Signal.strategy_id == strategy_id).delete()

    db.delete(strategy)
    db.commit()
    return {"message": "Strategy deleted"}


# ============= Watchlist Endpoints =============


@router.get("/watchlist", response_model=List[WatchlistResponse])
def get_watchlist(
    strategy_id: Optional[int] = None,
    market: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get watchlist items."""
    query = db.query(WatchlistItem)
    if strategy_id:
        query = query.filter(WatchlistItem.strategy_id == strategy_id)
    if market:
        query = query.filter(WatchlistItem.market == market)
    return query.all()


@router.post("/watchlist", response_model=WatchlistResponse)
def add_to_watchlist(item: WatchlistCreate, db: Session = Depends(get_db)):
    """Add ticker to watchlist."""
    # Check strategy exists
    strategy = db.query(Strategy).filter(Strategy.id == item.strategy_id).first()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    # Check for duplicate
    existing = (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.ticker == item.ticker,
            WatchlistItem.strategy_id == item.strategy_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(400, "Ticker already in watchlist for this strategy")

    db_item = WatchlistItem(
        ticker=item.ticker, market=item.market, strategy_id=item.strategy_id
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.delete("/watchlist/{item_id}")
def remove_from_watchlist(item_id: int, db: Session = Depends(get_db)):
    """Remove ticker from watchlist."""
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Watchlist item not found")

    db.delete(item)
    db.commit()
    return {"message": "Removed from watchlist"}


@router.put("/watchlist/{item_id}/toggle")
def toggle_watchlist_item(item_id: int, db: Session = Depends(get_db)):
    """Toggle active status of watchlist item."""
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Watchlist item not found")

    item.is_active = not item.is_active
    db.commit()
    db.refresh(item)
    return {"is_active": item.is_active}


# ============= Signal Endpoints =============


@router.get("/signals", response_model=List[SignalResponse])
def get_signals(
    status: Optional[str] = None,
    market: Optional[str] = None,
    strategy_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get signals."""
    query = db.query(Signal)
    if status:
        query = query.filter(Signal.status == status)
    if market:
        query = query.filter(Signal.market == market)
    if strategy_id:
        query = query.filter(Signal.strategy_id == strategy_id)
    return query.order_by(Signal.created_at.desc()).all()


@router.get("/signals/active", response_model=List[SignalResponse])
def get_active_signals(db: Session = Depends(get_db)):
    """Get active signals (pending, triggered, entered)."""
    return (
        db.query(Signal)
        .filter(Signal.status.in_(["pending", "triggered", "entered"]))
        .order_by(Signal.created_at.desc())
        .all()
    )


@router.delete("/signals/{signal_id}")
async def cancel_signal(signal_id: int, db: Session = Depends(get_db)):
    """Cancel a signal."""
    signal = db.query(Signal).filter(Signal.id == signal_id).first()
    if not signal:
        raise HTTPException(404, "Signal not found")

    if signal.status in ["stopped", "target_hit", "cancelled"]:
        raise HTTPException(400, "Signal already closed")

    signal.status = "cancelled"
    signal.closed_at = datetime.utcnow()
    signal.notes = "Manually cancelled"
    db.commit()

    # Broadcast updated signals
    await scanner._broadcast_signals(db)

    return {"message": "Signal cancelled"}


@router.post("/signals/{signal_id}/confirm-entry")
async def confirm_entry(
    signal_id: int, request: ConfirmEntryRequest, db: Session = Depends(get_db)
):
    """Confirm entry to a triggered signal with actual entry price."""
    signal = db.query(Signal).filter(Signal.id == signal_id).first()
    if not signal:
        raise HTTPException(404, "Signal not found")

    if signal.status != "triggered":
        raise HTTPException(
            400, f"Signal is not in triggered state (current: {signal.status})"
        )

    if not signal.entry_reached:
        raise HTTPException(400, "Entry price has not been reached yet")

    # Update signal
    signal.status = "entered"
    signal.entered_at = datetime.utcnow()
    signal.actual_entry_price = request.actual_entry_price
    signal.notes = f"Manually confirmed entry @ {request.actual_entry_price}"
    db.commit()

    # Broadcast updated signals
    await scanner._broadcast_signals(db)

    return {
        "message": "Entry confirmed",
        "signal_id": signal_id,
        "actual_entry_price": request.actual_entry_price,
    }


# ============= Trade History Endpoints =============


@router.get("/trades", response_model=List[TradeHistoryResponse])
def get_trade_history(
    market: Optional[str] = None,
    strategy_id: Optional[int] = None,
    result: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get trade history."""
    query = db.query(TradeHistory)
    if market:
        query = query.filter(TradeHistory.market == market)
    if strategy_id:
        query = query.filter(TradeHistory.strategy_id == strategy_id)
    if result:
        query = query.filter(TradeHistory.result == result)
    return query.order_by(TradeHistory.closed_at.desc()).limit(limit).all()


@router.get("/trades/stats")
def get_trade_stats(
    market: Optional[str] = None,
    strategy_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get trade statistics."""
    query = db.query(TradeHistory)
    if market:
        query = query.filter(TradeHistory.market == market)
    if strategy_id:
        query = query.filter(TradeHistory.strategy_id == strategy_id)

    trades = query.all()

    if not trades:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "avg_profit": 0,
            "avg_rr": 0,
            "total_profit": 0,
        }

    wins = len([t for t in trades if t.result == "win"])
    losses = len([t for t in trades if t.result == "loss"])

    return {
        "total_trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / len(trades)) * 100, 1) if trades else 0,
        "avg_profit": round(sum(t.profit_percent for t in trades) / len(trades), 2),
        "avg_rr": round(sum(t.risk_reward_achieved for t in trades) / len(trades), 2),
        "total_profit": round(sum(t.profit_percent for t in trades), 2),
    }


# ============= Scanner Endpoints =============


@router.get("/scanner/config", response_model=ScannerConfigResponse)
def get_scanner_config(db: Session = Depends(get_db)):
    """Get scanner configuration."""
    config = db.query(ScannerConfig).first()
    if not config:
        config = ScannerConfig()
        db.add(config)
        db.commit()
        db.refresh(config)

    return ScannerConfigResponse(
        scan_interval_minutes=config.scan_interval_minutes,
        is_running=scanner.is_running,
        is_scanning=scanner.is_scanning,
        last_scan_at=config.last_scan_at,
    )


@router.put("/scanner/config", response_model=ScannerConfigResponse)
async def update_scanner_config(
    update: ScannerConfigUpdate, db: Session = Depends(get_db)
):
    """Update scanner configuration."""
    config = db.query(ScannerConfig).first()
    if not config:
        config = ScannerConfig()
        db.add(config)

    if update.scan_interval_minutes is not None:
        config.scan_interval_minutes = update.scan_interval_minutes
        scanner.set_interval(update.scan_interval_minutes)

    if update.is_running is not None:
        if update.is_running and not scanner.is_running:
            await scanner.start()
        elif not update.is_running and scanner.is_running:
            await scanner.stop()
        config.is_running = update.is_running

    config.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(config)

    return ScannerConfigResponse(
        scan_interval_minutes=config.scan_interval_minutes,
        is_running=scanner.is_running,
        is_scanning=scanner.is_scanning,
        last_scan_at=config.last_scan_at,
    )


@router.post("/scanner/scan-now")
async def trigger_scan_now(db: Session = Depends(get_db)):
    """Trigger immediate scan."""
    await scanner.scan_all()
    return {"message": "Scan completed"}


@router.post("/scanner/scan-ticker/{ticker}")
async def scan_single_ticker(
    ticker: str, market: str = "bist100", db: Session = Depends(get_db)
):
    """Scan a single ticker manually."""
    # Find watchlist items for this ticker
    items = (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.ticker == ticker,
            WatchlistItem.market == market,
            WatchlistItem.is_active == True,
        )
        .all()
    )

    if not items:
        raise HTTPException(404, f"No active watchlist items found for {ticker}")

    results = []
    for item in items:
        await scanner.scan_ticker(db, item)

        # Get latest signal for this item
        signal = (
            db.query(Signal)
            .filter(Signal.ticker == ticker, Signal.strategy_id == item.strategy_id)
            .order_by(Signal.created_at.desc())
            .first()
        )

        if signal:
            results.append(
                {
                    "strategy_id": item.strategy_id,
                    "status": signal.status,
                    "direction": signal.direction,
                    "entry_price": signal.entry_price,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "notes": signal.notes,
                }
            )

    return {"ticker": ticker, "results": results}


@router.get("/chart-data/{ticker}")
async def get_chart_data(
    ticker: str,
    market: str = "bist100",
    strategy_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Get chart data for a ticker including:
    - Last 7 days of OHLC data
    - Indicator values (EMA200, MACD)
    - Current price
    - Active signal if any
    """
    from financia.analyzer import StockAnalyzer
    from financia.strategies.base import to_python_native
    import numpy as np

    # Get horizon from strategy if provided
    horizon = "short"  # Default to 1h candles
    if strategy_id:
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if strategy:
            horizon = strategy.horizon or "short"

    try:
        # Get data based on strategy's timeframe
        analyzer = StockAnalyzer(
            ticker=ticker,
            market=market,
            horizon=horizon,
        )
        data = analyzer.data
    except Exception as e:
        raise HTTPException(400, f"Failed to fetch data: {str(e)}")

    if data.empty:
        raise HTTPException(404, f"No data found for {ticker}")

    # Last 7 days (roughly 7 * 24 hours if hourly, or 7 bars if daily)
    # For daily data, take last 50 bars for good chart view
    chart_data = data.tail(50).copy()

    # Calculate indicators
    close = data["Close"]

    # EMA 200
    ema200 = close.ewm(span=200, adjust=False).mean()

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal

    # Prepare candle data
    candles = []
    for idx, row in chart_data.iterrows():
        timestamp = int(idx.timestamp() * 1000) if hasattr(idx, "timestamp") else None
        candles.append(
            {
                "time": timestamp or str(idx),
                "open": to_python_native(row["Open"]),
                "high": to_python_native(row["High"]),
                "low": to_python_native(row["Low"]),
                "close": to_python_native(row["Close"]),
                "volume": to_python_native(row.get("Volume", 0)),
            }
        )

    # Prepare EMA200 data (aligned with chart_data)
    ema_data = []
    for idx in chart_data.index:
        if idx in ema200.index:
            val = ema200.loc[idx]
            if not np.isnan(val):
                timestamp = (
                    int(idx.timestamp() * 1000) if hasattr(idx, "timestamp") else None
                )
                ema_data.append(
                    {"time": timestamp or str(idx), "value": to_python_native(val)}
                )

    # Prepare MACD data
    macd_data = []
    for idx in chart_data.index:
        if idx in macd.index:
            m = macd.loc[idx]
            s = macd_signal.loc[idx]
            h = macd_hist.loc[idx]
            if not (np.isnan(m) or np.isnan(s)):
                timestamp = (
                    int(idx.timestamp() * 1000) if hasattr(idx, "timestamp") else None
                )
                macd_data.append(
                    {
                        "time": timestamp or str(idx),
                        "macd": to_python_native(m),
                        "signal": to_python_native(s),
                        "histogram": to_python_native(h),
                    }
                )

    # Current price
    current_price = to_python_native(close.iloc[-1])

    # Get active signal if any
    signal_data = None
    if strategy_id:
        signal = (
            db.query(Signal)
            .filter(
                Signal.ticker == ticker,
                Signal.strategy_id == strategy_id,
                Signal.status.in_(["pending", "triggered", "entered"]),
            )
            .order_by(Signal.created_at.desc())
            .first()
        )
        if signal:
            signal_data = {
                "status": signal.status,
                "direction": signal.direction,
                "entry_price": to_python_native(signal.entry_price),
                "stop_loss": to_python_native(signal.stop_loss),
                "take_profit": to_python_native(signal.take_profit),
                "notes": signal.notes,
            }

    return {
        "ticker": ticker,
        "market": market,
        "current_price": current_price,
        "candles": candles,
        "indicators": {
            "ema200": ema_data,
            "macd": macd_data,
        },
        "signal": signal_data,
    }
