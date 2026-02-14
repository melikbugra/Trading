"""
Simulation Mode API endpoints.
Provides endpoints for starting, controlling, and monitoring simulation mode.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date, datetime

from financia.web_api.database import (
    get_db,
    simulation_time_manager,
    clear_simulation_data,
    SimSession,
    SimSignal,
    SimTradeHistory,
    SimStrategy,
    SimWatchlistItem,
    SimScannerConfig,
    Strategy,
    WatchlistItem,
    now_turkey,
)

router = APIRouter(prefix="/simulation", tags=["simulation"])


# ============= Pydantic Models =============


class SimulationStartRequest(BaseModel):
    start_date: date
    end_date: date
    seconds_per_hour: int = 30  # How many real seconds = 1 simulation hour
    initial_balance: float = 100000.0  # Starting balance in TL


class SimulationStatusResponse(BaseModel):
    is_active: bool
    is_paused: bool
    day_completed: bool
    hour_completed: bool = False
    is_scanning: bool = False
    is_eod_running: bool = False
    is_backtest: bool = False
    is_backtest_running: bool = False
    current_time: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    seconds_per_hour: int = 30
    session_id: Optional[int]
    # Balance fields
    initial_balance: Optional[float] = 100000.0
    current_balance: Optional[float] = 100000.0
    total_profit: Optional[float] = 0.0
    profit_percent: Optional[float] = 0.0
    total_trades: Optional[int] = 0
    winning_trades: Optional[int] = 0
    losing_trades: Optional[int] = 0
    win_rate: Optional[float] = 0.0


class SimSignalResponse(BaseModel):
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
    lots: float = 0.0
    remaining_lots: float = 0.0
    created_at: datetime
    triggered_at: Optional[datetime]
    entered_at: Optional[datetime]
    closed_at: Optional[datetime]
    notes: str
    extra_data: Dict[str, Any]

    class Config:
        from_attributes = True


class SimTradeHistoryResponse(BaseModel):
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
    profit_tl: float = 0.0
    lots: float = 0.0
    risk_reward_achieved: float
    entered_at: datetime
    closed_at: datetime
    notes: str

    class Config:
        from_attributes = True


class ConfirmEntryRequest(BaseModel):
    actual_entry_price: float
    lots: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class ClosePositionRequest(BaseModel):
    exit_price: float
    lots: float
    notes: Optional[str] = None


# Strategy and Watchlist Models
class SimStrategyCreate(BaseModel):
    name: str
    description: str = ""
    strategy_type: str
    params: Dict[str, Any] = {}
    risk_reward_ratio: float = 2.0
    horizon: str = "short"


class SimStrategyResponse(BaseModel):
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


class SimWatchlistCreate(BaseModel):
    ticker: str
    market: str = "bist100"
    strategy_id: int


class SimWatchlistBulkCreate(BaseModel):
    tickers: List[str]
    market: str = "bist100"
    strategy_id: int


class BacktestStartRequest(BaseModel):
    start_date: date
    end_date: date
    initial_balance: float = 100000.0
    strategy_types: List[str]  # Python strategy type names from STRATEGY_REGISTRY


class SimWatchlistResponse(BaseModel):
    id: int
    ticker: str
    market: str
    strategy_id: int
    is_active: bool
    added_at: datetime

    class Config:
        from_attributes = True


# ============= Simulation Control Endpoints =============


@router.get("/status", response_model=SimulationStatusResponse)
def get_simulation_status():
    """Get current simulation status."""
    from financia.simulation_scanner import simulation_scanner

    status = simulation_time_manager.get_status()
    return SimulationStatusResponse(
        is_active=status["is_active"],
        is_paused=status["is_paused"],
        day_completed=status["day_completed"],
        hour_completed=status.get("hour_completed", False),
        is_scanning=status.get("is_scanning", False),
        is_eod_running=status.get("is_eod_running", False),
        is_backtest=status.get("is_backtest", False),
        is_backtest_running=simulation_scanner.is_running
        if status.get("is_backtest", False)
        else False,
        current_time=status["current_time"],
        start_date=status["start_date"],
        end_date=status["end_date"],
        seconds_per_hour=status.get("seconds_per_hour", 30),
        session_id=status["session_id"],
        initial_balance=status.get("initial_balance", 100000),
        current_balance=status.get("current_balance", 100000),
        total_profit=status.get("total_profit", 0),
        profit_percent=status.get("profit_percent", 0),
        total_trades=status.get("total_trades", 0),
        winning_trades=status.get("winning_trades", 0),
        losing_trades=status.get("losing_trades", 0),
        win_rate=status.get("win_rate", 0),
    )


@router.post("/start", response_model=SimulationStatusResponse)
async def start_simulation(
    request: SimulationStartRequest, db: Session = Depends(get_db)
):
    """
    Start a new simulation session.
    Clears all previous simulation data and begins from the specified start date.
    """
    # Validate dates
    if request.start_date > request.end_date:
        raise HTTPException(400, "Start date must be before or equal to end date")

    if request.start_date > date.today():
        raise HTTPException(400, "Start date cannot be in the future")

    # Stop any existing simulation
    if simulation_time_manager.is_active:
        simulation_time_manager.stop()

    # Clear previous simulation data
    clear_simulation_data()

    # Create new session record
    session = SimSession(
        start_date=request.start_date,
        end_date=request.end_date,
        current_date=request.start_date,
        seconds_per_hour=request.seconds_per_hour,
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Start simulation
    simulation_time_manager.start(
        start_date=request.start_date,
        end_date=request.end_date,
        seconds_per_hour=request.seconds_per_hour,
        initial_balance=request.initial_balance,
    )
    simulation_time_manager.session_id = session.id

    # Import and start simulation scanner
    from financia.simulation_scanner import simulation_scanner

    await simulation_scanner.start()

    print(
        f"[Simulation] Started: {request.start_date} to {request.end_date}, {request.seconds_per_hour}s/hour, Balance: {request.initial_balance:,.0f} TL"
    )

    return get_simulation_status()


@router.post("/pause", response_model=SimulationStatusResponse)
async def pause_simulation():
    """Pause the running simulation."""
    if not simulation_time_manager.is_active:
        raise HTTPException(400, "No simulation is active")

    if simulation_time_manager.is_paused:
        raise HTTPException(400, "Simulation is already paused")

    simulation_time_manager.pause()

    # Pause the simulation scanner
    from financia.simulation_scanner import simulation_scanner

    simulation_scanner.pause()

    print("[Simulation] Paused")
    return get_simulation_status()


@router.post("/resume", response_model=SimulationStatusResponse)
async def resume_simulation():
    """Resume a paused simulation."""
    if not simulation_time_manager.is_active:
        raise HTTPException(400, "No simulation is active")

    if (
        not simulation_time_manager.is_paused
        and not simulation_time_manager.day_completed
    ):
        raise HTTPException(400, "Simulation is not paused")

    simulation_time_manager.resume()

    # Resume the simulation scanner
    from financia.simulation_scanner import simulation_scanner

    await simulation_scanner.resume()

    print("[Simulation] Resumed")
    return get_simulation_status()


@router.post("/scan-now")
async def simulation_scan_now():
    """
    Manually trigger a scan at the current simulation time.
    """
    if not simulation_time_manager.is_active:
        raise HTTPException(400, "No simulation is active")

    from financia.simulation_scanner import simulation_scanner

    success = await simulation_scanner.scan_now()

    if success:
        return {"status": "ok", "message": "Scan completed"}
    else:
        raise HTTPException(400, "Scan failed - simulation not active")


@router.post("/eod-analysis")
async def simulation_eod_analysis():
    """
    Manually trigger EOD analysis at the current simulation time.
    """
    if not simulation_time_manager.is_active:
        raise HTTPException(400, "No simulation is active")

    from financia.simulation_scanner import simulation_scanner

    await simulation_scanner._run_sim_eod_analysis()

    return {"status": "ok", "message": "EOD analysis completed"}


@router.post("/eod-analysis/cancel")
async def cancel_simulation_eod_analysis():
    """
    Cancel ongoing EOD analysis.
    """
    if not simulation_time_manager.is_active:
        raise HTTPException(400, "No simulation is active")

    if not simulation_time_manager.is_eod_running:
        raise HTTPException(400, "No EOD analysis is running")

    # Set flag to false to signal cancellation
    simulation_time_manager.is_eod_running = False

    return {"status": "ok", "message": "EOD analysis cancelled"}


@router.post("/next-hour", response_model=SimulationStatusResponse)
async def next_simulation_hour(db: Session = Depends(get_db)):
    """
    Advance to the next hour in simulation.
    Triggers automatic scan at the new hour.
    If the day is completed (18:00), runs EOD analysis.
    """
    if not simulation_time_manager.is_active:
        raise HTTPException(400, "No simulation is active")

    if not simulation_time_manager.hour_completed:
        raise HTTPException(400, "Current hour scan not completed yet")

    if simulation_time_manager.day_completed:
        raise HTTPException(400, "Day is completed, use next-day instead")

    # Advance simulation time by 1 hour
    day_completed = simulation_time_manager.advance_hour()

    from financia.simulation_scanner import simulation_scanner

    if day_completed:
        print(f"[Simulation] Day completed: {simulation_time_manager.current_time}")
        # Pause and run EOD
        simulation_time_manager.pause()
        await simulation_scanner._broadcast_status()

        # Clean up non-entered signals at end of day
        await simulation_scanner._cleanup_day_end_signals()

        # Run EOD analysis
        simulation_time_manager.is_eod_running = True
        await simulation_scanner._broadcast_status()

        await simulation_scanner._run_sim_eod_analysis()

        simulation_time_manager.is_eod_running = False
        await simulation_scanner._broadcast_status()
    else:
        # Reset hour_completed to allow loop to scan at new hour
        simulation_time_manager.hour_completed = False
        await simulation_scanner._broadcast_status()

    print(f"[Simulation] Advanced to: {simulation_time_manager.current_time}")
    return get_simulation_status()


@router.post("/next-day", response_model=SimulationStatusResponse)
async def next_simulation_day(db: Session = Depends(get_db)):
    """
    Move to the next trading day in simulation.
    Only available when the current day is completed.
    """
    if not simulation_time_manager.is_active:
        raise HTTPException(400, "No simulation is active")

    if not simulation_time_manager.day_completed:
        raise HTTPException(400, "Current day is not completed yet")

    # Move to next day
    is_complete = simulation_time_manager.next_day()

    if is_complete:
        # Simulation finished - mark session as completed
        if simulation_time_manager.session_id:
            session = (
                db.query(SimSession)
                .filter(SimSession.id == simulation_time_manager.session_id)
                .first()
            )
            if session:
                session.status = "completed"
                session.completed_at = datetime.utcnow()
                db.commit()

        simulation_time_manager.stop()

        from financia.simulation_scanner import simulation_scanner

        await simulation_scanner.stop()

        print("[Simulation] Completed - reached end date")
        return get_simulation_status()

    # Update session current date
    if simulation_time_manager.session_id:
        session = (
            db.query(SimSession)
            .filter(SimSession.id == simulation_time_manager.session_id)
            .first()
        )
        if session and simulation_time_manager.current_time:
            session.current_date = simulation_time_manager.current_time.date()
            db.commit()

    # Clear data cache for new day and resume scanner
    from financia.simulation_scanner import simulation_scanner

    simulation_scanner.clear_cache()  # Clear cached data for fresh fetch
    await simulation_scanner.resume()

    print(f"[Simulation] Started new day: {simulation_time_manager.current_time}")
    return get_simulation_status()


@router.post("/stop", response_model=SimulationStatusResponse)
async def stop_simulation(db: Session = Depends(get_db)):
    """Stop the simulation and return to live mode."""
    if not simulation_time_manager.is_active:
        raise HTTPException(400, "No simulation is active")

    # Update session status
    if simulation_time_manager.session_id:
        session = (
            db.query(SimSession)
            .filter(SimSession.id == simulation_time_manager.session_id)
            .first()
        )
        if session:
            session.status = "stopped"
            session.completed_at = datetime.utcnow()
            db.commit()

    # Stop simulation scanner
    from financia.simulation_scanner import simulation_scanner

    await simulation_scanner.stop()

    simulation_time_manager.stop()

    print("[Simulation] Stopped")
    return get_simulation_status()


# ============= Simulation Signals Endpoints =============


@router.get("/signals", response_model=List[SimSignalResponse])
def get_sim_signals(
    status: Optional[str] = None,
    market: Optional[str] = None,
    strategy_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get simulation signals."""
    query = db.query(SimSignal)
    if status:
        query = query.filter(SimSignal.status == status)
    if market:
        query = query.filter(SimSignal.market == market)
    if strategy_id:
        query = query.filter(SimSignal.strategy_id == strategy_id)
    return query.order_by(SimSignal.created_at.desc()).all()


@router.get("/signals/active", response_model=List[SimSignalResponse])
def get_active_sim_signals(db: Session = Depends(get_db)):
    """Get active simulation signals (pending, triggered, entered)."""
    return (
        db.query(SimSignal)
        .filter(SimSignal.status.in_(["pending", "triggered", "entered"]))
        .order_by(SimSignal.created_at.desc())
        .all()
    )


@router.delete("/signals/{signal_id}")
async def cancel_sim_signal(signal_id: int, db: Session = Depends(get_db)):
    """Cancel a simulation signal."""
    signal = db.query(SimSignal).filter(SimSignal.id == signal_id).first()
    if not signal:
        raise HTTPException(404, "Signal not found")

    if signal.status in ["stopped", "target_hit", "cancelled"]:
        raise HTTPException(400, "Signal already closed")

    signal.status = "cancelled"
    signal.closed_at = now_turkey()
    signal.notes = "Manually cancelled"
    db.commit()

    # Broadcast updated signals
    from financia.simulation_scanner import simulation_scanner

    await simulation_scanner._broadcast_signals(db)

    return {"message": "Signal cancelled"}


@router.post("/signals/{signal_id}/confirm-entry")
async def confirm_sim_entry(
    signal_id: int, request: ConfirmEntryRequest, db: Session = Depends(get_db)
):
    """Confirm entry to a triggered simulation signal."""
    signal = db.query(SimSignal).filter(SimSignal.id == signal_id).first()
    if not signal:
        raise HTTPException(404, "Signal not found")

    if signal.status not in ["triggered", "pending"]:
        raise HTTPException(
            400,
            f"Signal must be in triggered or pending state (current: {signal.status})",
        )

    # Calculate position cost
    position_cost = request.actual_entry_price * request.lots

    # Check if enough balance
    if position_cost > simulation_time_manager.current_balance:
        raise HTTPException(
            400,
            f"Yetersiz bakiye. Gerekli: {position_cost:,.2f} TL, Mevcut: {simulation_time_manager.current_balance:,.2f} TL",
        )

    # Deduct from balance
    simulation_time_manager.current_balance -= position_cost
    print(
        f"[Simulation] Position opened: {signal.ticker} @ {request.actual_entry_price} x {request.lots} = {position_cost:,.0f} TL | Balance: {simulation_time_manager.current_balance:,.0f} TL"
    )

    signal.status = "entered"
    signal.entered_at = now_turkey()
    signal.actual_entry_price = request.actual_entry_price
    signal.lots = request.lots
    signal.remaining_lots = request.lots

    if request.stop_loss is not None:
        signal.stop_loss = request.stop_loss
    if request.take_profit is not None:
        signal.take_profit = request.take_profit

    signal.notes = f"Entered @ {request.actual_entry_price} x {request.lots} lot"
    db.commit()

    from financia.simulation_scanner import simulation_scanner

    await simulation_scanner._broadcast_signals(db)
    await simulation_scanner._broadcast_status()  # Broadcast updated balance

    return {
        "message": "Entry confirmed",
        "signal_id": signal_id,
        "actual_entry_price": request.actual_entry_price,
        "lots": request.lots,
        "position_cost": position_cost,
        "new_balance": simulation_time_manager.current_balance,
    }


@router.post("/signals/{signal_id}/close-position")
async def close_sim_position(
    signal_id: int, request: ClosePositionRequest, db: Session = Depends(get_db)
):
    """Close a simulation position."""
    signal = db.query(SimSignal).filter(SimSignal.id == signal_id).first()
    if not signal:
        raise HTTPException(404, "Signal not found")

    if signal.status != "entered":
        raise HTTPException(
            400, f"Signal must be in entered state (current: {signal.status})"
        )

    lots_to_sell = request.lots
    if lots_to_sell <= 0:
        raise HTTPException(400, "Lots must be greater than 0")
    if lots_to_sell > signal.remaining_lots:
        raise HTTPException(
            400,
            f"Cannot sell {lots_to_sell} lots. Only {signal.remaining_lots} remaining.",
        )

    entry_price = signal.actual_entry_price or signal.entry_price
    exit_price = request.exit_price

    if signal.direction == "long":
        profit_percent = ((exit_price - entry_price) / entry_price) * 100
        profit_per_lot = exit_price - entry_price
    else:
        profit_percent = ((entry_price - exit_price) / entry_price) * 100
        profit_per_lot = entry_price - exit_price

    profit_tl = profit_per_lot * lots_to_sell
    result = "win" if profit_percent > 0 else "loss"

    risk = abs(entry_price - signal.stop_loss) if signal.stop_loss else 1
    reward = abs(exit_price - entry_price)
    rr_achieved = reward / risk if risk > 0 else 0

    trade = SimTradeHistory(
        signal_id=signal.id,
        ticker=signal.ticker,
        market=signal.market,
        strategy_id=signal.strategy_id,
        direction=signal.direction,
        entry_price=entry_price,
        exit_price=exit_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        result=result,
        profit_percent=round(profit_percent, 2),
        profit_tl=round(profit_tl, 2),
        lots=lots_to_sell,
        risk_reward_achieved=round(rr_achieved, 2),
        entered_at=signal.entered_at,
        closed_at=now_turkey(),
        notes=request.notes or f"Sold {lots_to_sell} lots @ {exit_price}",
    )
    db.add(trade)

    # Add position value back to balance
    position_value = exit_price * lots_to_sell
    simulation_time_manager.current_balance += position_value

    # Update trade statistics
    simulation_time_manager.total_profit += profit_tl
    simulation_time_manager.total_trades += 1
    if result == "win":
        simulation_time_manager.winning_trades += 1
    else:
        simulation_time_manager.losing_trades += 1

    print(
        f"[Simulation] Position closed: {signal.ticker} {result} {profit_percent:+.2f}% ({profit_tl:+,.0f} TL) | Balance: {simulation_time_manager.current_balance:,.0f} TL"
    )

    signal.remaining_lots -= lots_to_sell
    is_fully_closed = signal.remaining_lots <= 0

    if is_fully_closed:
        signal.status = "closed"
        signal.closed_at = now_turkey()
        signal.notes = f"Fully closed @ {exit_price} | P/L: {profit_percent:+.2f}%"
    else:
        signal.notes = f"Partial exit: {lots_to_sell} lots @ {exit_price}"

    db.commit()

    from financia.simulation_scanner import simulation_scanner

    await simulation_scanner._broadcast_signals(db)
    await simulation_scanner._broadcast_status()  # Broadcast updated balance

    return {
        "message": "Position closed" if is_fully_closed else "Partial exit",
        "profit_percent": round(profit_percent, 2),
        "profit_tl": round(profit_tl, 2),
        "result": result,
        "new_balance": simulation_time_manager.current_balance,
    }


# ============= Simulation Trade History Endpoints =============


@router.get("/trades", response_model=List[SimTradeHistoryResponse])
def get_sim_trade_history(
    market: Optional[str] = None,
    strategy_id: Optional[int] = None,
    result: Optional[str] = None,
    direction: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get simulation trade history."""
    query = db.query(SimTradeHistory)
    if market:
        query = query.filter(SimTradeHistory.market == market)
    if strategy_id:
        query = query.filter(SimTradeHistory.strategy_id == strategy_id)
    if result:
        query = query.filter(SimTradeHistory.result == result)
    if direction:
        query = query.filter(SimTradeHistory.direction == direction)
    return query.order_by(SimTradeHistory.closed_at.desc()).limit(limit).all()


@router.get("/trades/stats")
def get_sim_trade_stats(
    market: Optional[str] = None,
    strategy_id: Optional[int] = None,
    direction: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get simulation trade statistics."""
    query = db.query(SimTradeHistory)
    if market:
        query = query.filter(SimTradeHistory.market == market)
    if strategy_id:
        query = query.filter(SimTradeHistory.strategy_id == strategy_id)
    if direction:
        query = query.filter(SimTradeHistory.direction == direction)

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
            "total_profit_tl": 0,
            "total_lots": 0,
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
        "total_profit_tl": round(sum(t.profit_tl or 0 for t in trades), 2),
        "total_lots": round(sum(t.lots or 0 for t in trades), 2),
    }


# ============= Simulation Chart Data Endpoint =============


@router.get("/chart-data/{ticker}")
async def get_sim_chart_data(
    ticker: str,
    market: str = "bist100",
    strategy_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Get chart data for a ticker in simulation mode.
    Returns data up to the current simulation time.
    """
    from financia.analyzer import StockAnalyzer
    from financia.strategies.base import to_python_native
    import numpy as np
    from datetime import timedelta

    if not simulation_time_manager.is_active:
        raise HTTPException(400, "Simulation is not active")

    sim_time = simulation_time_manager.current_time
    if not sim_time:
        raise HTTPException(400, "Simulation time not available")

    # Get strategy details
    horizon = "short"
    strategy_type = "EMAMACDStrategy"
    if strategy_id:
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if strategy:
            horizon = strategy.horizon or "short"
            strategy_type = strategy.strategy_type or "EMAMACDStrategy"

    # Calculate start date based on horizon (need enough data for indicators like EMA200)
    if horizon == "short":
        start_date = sim_time - timedelta(days=90)
    elif horizon == "long":
        start_date = sim_time - timedelta(days=365 * 5)
    else:  # medium
        start_date = sim_time - timedelta(days=365)

    try:
        # Get historical data up to simulation time
        analyzer = StockAnalyzer(
            ticker=ticker,
            market=market,
            horizon=horizon,
            start=start_date,
            end=sim_time,  # Key difference: limit data to simulation time
        )
        data = analyzer.data

        if data.empty:
            raise HTTPException(404, f"No data available for {ticker}")

        # Get last 50 bars
        last_bars = data.tail(50).copy()

        # Prepare OHLC data (same format as live mode - time in milliseconds)
        ohlc_data = []
        for idx, row in last_bars.iterrows():
            timestamp = (
                int(idx.timestamp() * 1000) if hasattr(idx, "timestamp") else None
            )
            ohlc_data.append(
                {
                    "time": timestamp or str(idx),
                    "open": to_python_native(row["Open"]),
                    "high": to_python_native(row["High"]),
                    "low": to_python_native(row["Low"]),
                    "close": to_python_native(row["Close"]),
                    "volume": to_python_native(row.get("Volume", 0)),
                }
            )

        # Calculate indicators
        close = data["Close"]
        indicators = {}

        if "EMAMACDStrategy" in strategy_type:
            ema200 = close.ewm(span=200, adjust=False).mean()
            indicators["ema200"] = [
                {
                    "time": int(idx.timestamp() * 1000)
                    if hasattr(idx, "timestamp")
                    else str(idx),
                    "value": to_python_native(v),
                }
                for idx, v in ema200.tail(50).items()
                if not (isinstance(v, float) and np.isnan(v))
            ]

            # MACD
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            histogram = macd_line - signal_line

            indicators["macd"] = [
                {
                    "time": int(idx.timestamp() * 1000)
                    if hasattr(idx, "timestamp")
                    else str(idx),
                    "macd": to_python_native(macd_line.loc[idx]),
                    "signal": to_python_native(signal_line.loc[idx]),
                    "histogram": to_python_native(histogram.loc[idx]),
                }
                for idx in macd_line.tail(50).index
                if not (
                    isinstance(macd_line.loc[idx], float)
                    and np.isnan(macd_line.loc[idx])
                )
            ]

        # Get active signal if any
        active_signal = (
            db.query(SimSignal)
            .filter(
                SimSignal.ticker == ticker,
                SimSignal.status.in_(["pending", "triggered", "entered"]),
            )
            .order_by(SimSignal.created_at.desc())
            .first()
        )

        signal_data = None
        if active_signal:
            signal_data = {
                "id": active_signal.id,
                "status": active_signal.status,
                "direction": active_signal.direction,
                "entry_price": active_signal.entry_price,
                "stop_loss": active_signal.stop_loss,
                "take_profit": active_signal.take_profit,
                "actual_entry_price": active_signal.actual_entry_price,
            }

        return {
            "ticker": ticker,
            "market": market,
            "simulation_time": sim_time.isoformat(),
            "current_price": to_python_native(close.iloc[-1]),
            "candles": ohlc_data,  # Frontend expects 'candles' not 'ohlc'
            "indicators": indicators,
            "signal": signal_data,
        }

    except Exception as e:
        raise HTTPException(500, f"Error fetching chart data: {str(e)}")


# ============= Manual Scan Endpoint =============


@router.post("/scan-ticker/{ticker}")
async def scan_single_ticker_sim(
    ticker: str, market: str = "bist100", db: Session = Depends(get_db)
):
    """Scan a single ticker manually during simulation."""
    if not simulation_time_manager.is_active:
        raise HTTPException(400, "Simulation is not active")

    from financia.simulation_scanner import simulation_scanner

    sim_time = simulation_time_manager.current_time
    if not sim_time:
        raise HTTPException(400, "Simulation time not set")

    # Find simulation watchlist items for this ticker
    items = (
        db.query(SimWatchlistItem)
        .filter(
            SimWatchlistItem.ticker == ticker,
            SimWatchlistItem.market == market,
            SimWatchlistItem.is_active == True,
        )
        .all()
    )

    if not items:
        raise HTTPException(404, f"No active watchlist items found for {ticker}")

    results = []
    for item in items:
        # Use simulation scanner to scan
        await simulation_scanner._scan_ticker(db, item, sim_time)

        # Get latest simulation signal for this item
        signal = (
            db.query(SimSignal)
            .filter(
                SimSignal.ticker == ticker, SimSignal.strategy_id == item.strategy_id
            )
            .order_by(SimSignal.created_at.desc())
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

    return {
        "ticker": ticker,
        "simulation_time": sim_time.isoformat(),
        "results": results,
    }


# ============= Simulation Strategy Endpoints =============


@router.get("/strategies", response_model=List[SimStrategyResponse])
def get_sim_strategies(db: Session = Depends(get_db)):
    """Get all simulation strategies."""
    strategies = db.query(SimStrategy).order_by(SimStrategy.created_at.desc()).all()
    return strategies


@router.get("/strategies/available-types")
def get_available_strategy_types():
    """Get available strategy types for simulation."""
    from financia.strategies import STRATEGY_REGISTRY

    types_list = []
    for key, cls in STRATEGY_REGISTRY.items():
        types_list.append(
            {
                "type": key,
                "name": cls.name,
                "description": cls.description,
                "default_params": cls.default_params,
            }
        )
    return types_list


@router.post("/strategies", response_model=SimStrategyResponse)
def create_sim_strategy(data: SimStrategyCreate, db: Session = Depends(get_db)):
    """Create a new simulation strategy."""
    # Check if name already exists
    existing = db.query(SimStrategy).filter(SimStrategy.name == data.name).first()
    if existing:
        raise HTTPException(400, f"Strategy with name '{data.name}' already exists")

    strategy = SimStrategy(
        name=data.name,
        description=data.description,
        strategy_type=data.strategy_type,
        params=data.params,
        risk_reward_ratio=data.risk_reward_ratio,
        horizon=data.horizon,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


@router.put("/strategies/{strategy_id}", response_model=SimStrategyResponse)
def update_sim_strategy(
    strategy_id: int, data: SimStrategyCreate, db: Session = Depends(get_db)
):
    """Update a simulation strategy."""
    strategy = db.query(SimStrategy).filter(SimStrategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    strategy.name = data.name
    strategy.description = data.description
    strategy.strategy_type = data.strategy_type
    strategy.params = data.params
    strategy.risk_reward_ratio = data.risk_reward_ratio
    strategy.horizon = data.horizon
    db.commit()
    db.refresh(strategy)
    return strategy


@router.delete("/strategies/{strategy_id}")
def delete_sim_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Delete a simulation strategy and its watchlist items."""
    strategy = db.query(SimStrategy).filter(SimStrategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    # Delete associated watchlist items
    db.query(SimWatchlistItem).filter(
        SimWatchlistItem.strategy_id == strategy_id
    ).delete()

    # Delete associated signals
    db.query(SimSignal).filter(SimSignal.strategy_id == strategy_id).delete()

    db.delete(strategy)
    db.commit()
    return {"message": "Strategy deleted"}


@router.patch("/strategies/{strategy_id}/toggle")
def toggle_sim_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Toggle a simulation strategy's active status."""
    strategy = db.query(SimStrategy).filter(SimStrategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    strategy.is_active = not strategy.is_active
    db.commit()
    return {"id": strategy_id, "is_active": strategy.is_active}


# ============= Simulation Watchlist Endpoints =============


@router.get("/watchlist", response_model=List[SimWatchlistResponse])
def get_sim_watchlist(strategy_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Get simulation watchlist items, optionally filtered by strategy."""
    query = db.query(SimWatchlistItem)
    if strategy_id:
        query = query.filter(SimWatchlistItem.strategy_id == strategy_id)
    return query.order_by(SimWatchlistItem.added_at.desc()).all()


@router.post("/watchlist", response_model=SimWatchlistResponse)
def add_sim_watchlist_item(data: SimWatchlistCreate, db: Session = Depends(get_db)):
    """Add a ticker to simulation watchlist."""
    # Check if already exists
    existing = (
        db.query(SimWatchlistItem)
        .filter(
            SimWatchlistItem.ticker == data.ticker,
            SimWatchlistItem.market == data.market,
            SimWatchlistItem.strategy_id == data.strategy_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            400, f"{data.ticker} already in watchlist for this strategy"
        )

    # Verify strategy exists
    strategy = db.query(SimStrategy).filter(SimStrategy.id == data.strategy_id).first()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    # Add .IS suffix for BIST tickers if not present
    ticker = data.ticker.upper()
    if data.market == "bist100" and not ticker.endswith(".IS"):
        ticker = f"{ticker}.IS"

    item = SimWatchlistItem(
        ticker=ticker,
        market=data.market,
        strategy_id=data.strategy_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/watchlist/bulk")
def add_sim_watchlist_bulk(
    data: SimWatchlistBulkCreate,
    db: Session = Depends(get_db),
):
    """Add multiple tickers to simulation watchlist at once."""
    # Verify strategy exists
    strategy = db.query(SimStrategy).filter(SimStrategy.id == data.strategy_id).first()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    added = 0
    skipped = 0
    for ticker in data.tickers:
        ticker_normalized = ticker.upper()
        if data.market == "bist100" and not ticker_normalized.endswith(".IS"):
            ticker_normalized = f"{ticker_normalized}.IS"

        existing = (
            db.query(SimWatchlistItem)
            .filter(
                SimWatchlistItem.ticker == ticker_normalized,
                SimWatchlistItem.market == data.market,
                SimWatchlistItem.strategy_id == data.strategy_id,
            )
            .first()
        )
        if not existing:
            item = SimWatchlistItem(
                ticker=ticker_normalized,
                market=data.market,
                strategy_id=data.strategy_id,
            )
            db.add(item)
            added += 1
        else:
            skipped += 1

    db.commit()
    return {"added": added, "skipped": skipped, "total": len(data.tickers)}


@router.delete("/watchlist/{item_id}")
async def delete_sim_watchlist_item(item_id: int, db: Session = Depends(get_db)):
    """Remove a ticker from simulation watchlist and delete related signals."""
    item = db.query(SimWatchlistItem).filter(SimWatchlistItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Watchlist item not found")

    # Also delete any pending or triggered signals for this ticker/strategy
    deleted_signals = (
        db.query(SimSignal)
        .filter(
            SimSignal.ticker == item.ticker,
            SimSignal.strategy_id == item.strategy_id,
            SimSignal.status.in_(["pending", "triggered"]),
        )
        .delete(synchronize_session=False)
    )

    db.delete(item)
    db.commit()

    # Broadcast updated signals if any were deleted
    if deleted_signals > 0:
        from financia.simulation_scanner import simulation_scanner

        await simulation_scanner._broadcast_signals(db)

    return {"message": f"Removed from watchlist, {deleted_signals} signal(s) deleted"}


@router.delete("/watchlist/strategy/{strategy_id}")
async def clear_sim_watchlist_for_strategy(
    strategy_id: int, db: Session = Depends(get_db)
):
    """Remove all watchlist items for a strategy and delete related signals."""
    # Delete pending/triggered signals for this strategy
    deleted_signals = (
        db.query(SimSignal)
        .filter(
            SimSignal.strategy_id == strategy_id,
            SimSignal.status.in_(["pending", "triggered"]),
        )
        .delete(synchronize_session=False)
    )

    # Delete watchlist items
    deleted = (
        db.query(SimWatchlistItem)
        .filter(SimWatchlistItem.strategy_id == strategy_id)
        .delete()
    )
    db.commit()

    # Broadcast updated signals if any were deleted
    if deleted_signals > 0:
        from financia.simulation_scanner import simulation_scanner

        await simulation_scanner._broadcast_signals(db)

    return {"deleted": deleted, "signals_deleted": deleted_signals}


@router.patch("/watchlist/{item_id}/toggle")
def toggle_sim_watchlist_item(item_id: int, db: Session = Depends(get_db)):
    """Toggle a simulation watchlist item's active status."""
    item = db.query(SimWatchlistItem).filter(SimWatchlistItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Watchlist item not found")

    item.is_active = not item.is_active
    db.commit()
    return {"id": item_id, "is_active": item.is_active}


# ============= Backtest Endpoints =============


@router.post("/backtest/start", response_model=SimulationStatusResponse)
async def start_backtest(request: BacktestStartRequest, db: Session = Depends(get_db)):
    """
    Start a backtest session.
    Runs the simulation automatically — auto-enters on triggered signals,
    auto-exits on SL/TP hit. No manual intervention needed.
    """
    # Validate
    if request.start_date > request.end_date:
        raise HTTPException(400, "Start date must be before or equal to end date")
    if request.start_date > date.today():
        raise HTTPException(400, "Start date cannot be in the future")
    if not request.strategy_types:
        raise HTTPException(400, "At least one strategy must be selected")

    # Validate strategy types exist in Python STRATEGY_REGISTRY
    from financia.strategies import STRATEGY_REGISTRY, get_strategy_class

    for st in request.strategy_types:
        if st not in STRATEGY_REGISTRY:
            raise HTTPException(400, f"Unknown strategy type: {st}")

    # Clear ALL sim data first
    db.query(SimSignal).delete()
    db.query(SimTradeHistory).delete()
    db.query(SimScannerConfig).delete()
    db.query(SimSession).delete()
    db.query(SimWatchlistItem).delete()
    db.query(SimStrategy).delete()
    db.commit()

    # Create sim strategies from Python class defaults
    sim_strategy_ids = []
    for st in request.strategy_types:
        cls = get_strategy_class(st)
        sim_s = SimStrategy(
            name=cls.name,
            description=cls.description,
            strategy_type=st,
            params=cls.default_params,
            risk_reward_ratio=cls.default_params.get("risk_reward_ratio", 2.0),
            horizon="short",
            is_active=True,
        )
        db.add(sim_s)
        db.flush()
        sim_strategy_ids.append(sim_s.id)

    # Add all BIST100 tickers to each selected strategy
    from financia.bist100_tickers import get_bist_tickers

    bist_tickers = get_bist_tickers("100")
    for sim_sid in sim_strategy_ids:
        for ticker in bist_tickers:
            sim_item = SimWatchlistItem(
                ticker=ticker,
                market="bist100",
                strategy_id=sim_sid,
                is_active=True,
            )
            db.add(sim_item)
    db.commit()

    strategies = db.query(SimStrategy).all()

    # Create new session
    session = SimSession(
        start_date=request.start_date,
        end_date=request.end_date,
        current_date=request.start_date,
        seconds_per_hour=0,  # instant
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Start simulation in backtest mode
    simulation_time_manager.start(
        start_date=request.start_date,
        end_date=request.end_date,
        seconds_per_hour=0,
        initial_balance=request.initial_balance,
        is_backtest=True,
    )
    simulation_time_manager.session_id = session.id

    # Import and start backtest
    from financia.simulation_scanner import simulation_scanner

    await simulation_scanner.start_backtest()

    strategy_names = [s.name for s in strategies]
    print(
        f"[Backtest] Started: {request.start_date} to {request.end_date}, "
        f"Balance: {request.initial_balance:,.0f} TL, "
        f"Strategies: {', '.join(strategy_names)}"
    )

    return get_simulation_status()


@router.post("/backtest/stop", response_model=SimulationStatusResponse)
async def stop_backtest(db: Session = Depends(get_db)):
    """Stop a running backtest or exit backtest mode after completion."""
    if not simulation_time_manager.is_active:
        raise HTTPException(400, "No simulation is active")

    # Update session
    if simulation_time_manager.session_id:
        session = (
            db.query(SimSession)
            .filter(SimSession.id == simulation_time_manager.session_id)
            .first()
        )
        if session:
            session.status = "stopped"
            session.completed_at = datetime.utcnow()
            db.commit()

    simulation_time_manager.stop()

    from financia.simulation_scanner import simulation_scanner

    await simulation_scanner.stop()

    print("[Backtest] Stopped by user")
    return get_simulation_status()


@router.get("/backtest/summary")
def get_backtest_summary(db: Session = Depends(get_db)):
    """Get backtest results summary with per-strategy breakdown."""

    # Overall stats
    balance_stats = simulation_time_manager.get_balance_stats()

    # Per-strategy breakdown
    strategy_stats = []
    strategies = db.query(SimStrategy).filter(SimStrategy.is_active == True).all()

    for strategy in strategies:
        trades = (
            db.query(SimTradeHistory)
            .filter(SimTradeHistory.strategy_id == strategy.id)
            .all()
        )

        if not trades:
            strategy_stats.append(
                {
                    "strategy_id": strategy.id,
                    "strategy_name": strategy.name,
                    "strategy_type": strategy.strategy_type,
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": 0,
                    "total_profit_tl": 0,
                    "total_profit_percent": 0,
                    "avg_profit_percent": 0,
                    "avg_rr_achieved": 0,
                    "best_trade_percent": 0,
                    "worst_trade_percent": 0,
                }
            )
            continue

        wins = [t for t in trades if t.result == "win"]
        losses = [t for t in trades if t.result == "loss"]
        total_profit_tl = sum(t.profit_tl for t in trades)
        profits = [t.profit_percent for t in trades]
        rrs = [t.risk_reward_achieved for t in trades]

        strategy_stats.append(
            {
                "strategy_id": strategy.id,
                "strategy_name": strategy.name,
                "strategy_type": strategy.strategy_type,
                "total_trades": len(trades),
                "winning_trades": len(wins),
                "losing_trades": len(losses),
                "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
                "total_profit_tl": round(total_profit_tl, 2),
                "total_profit_percent": round(sum(profits), 2),
                "avg_profit_percent": round(sum(profits) / len(profits), 2)
                if profits
                else 0,
                "avg_rr_achieved": round(sum(rrs) / len(rrs), 2) if rrs else 0,
                "best_trade_percent": round(max(profits), 2) if profits else 0,
                "worst_trade_percent": round(min(profits), 2) if profits else 0,
            }
        )

    return {
        "overall": balance_stats,
        "per_strategy": strategy_stats,
    }
