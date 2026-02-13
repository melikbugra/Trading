"""
Scanner service for monitoring watchlist and generating signals.
Supports both BIST100 and Binance markets.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, List, Dict, Any
import pandas as pd
import yfinance as yf

from sqlalchemy.orm import Session

from financia.analyzer import StockAnalyzer
from financia.strategies import get_strategy_class, STRATEGY_REGISTRY
from financia.strategies.base import StrategyResult, to_python_native
from financia.web_api.database import (
    Strategy,
    WatchlistItem,
    Signal,
    ScannerConfig,
    TradeHistory,
    SessionLocal,
    engine,
    Base,
    now_turkey,
)
from financia.notification_service import EmailService

# Thread pool for running blocking operations - increased for parallel scanning
_executor = ThreadPoolExecutor(max_workers=10)

# Concurrency settings for parallel scanning
SCAN_BATCH_SIZE = 10  # Number of tickers to scan in parallel


class ScannerService:
    """
    Background service that scans watchlist items and generates signals.
    """

    def __init__(self):
        self.is_running = False
        self.is_scanning = False  # True while actively scanning
        self.scan_interval = 5  # minutes, default
        self._task: Optional[asyncio.Task] = None
        self._ws_manager = None  # WebSocket manager reference
        self.last_scan_at: Optional[datetime] = None
        # Progress tracking
        self.scan_progress = 0
        self.scan_total = 0
        self.current_ticker = ""
        # Email notification settings (in-memory, configurable via API)
        self.email_notifications = {
            "triggered": True,  # Send email when signal is triggered
            "entryReached": True,  # Send email when entry price is reached
        }

    def set_ws_manager(self, manager):
        """Set WebSocket manager for broadcasting updates."""
        self._ws_manager = manager

    async def _broadcast_scan_progress(self):
        """Broadcast scan progress to all connected clients."""
        if self._ws_manager:
            try:
                await self._ws_manager.broadcast(
                    {
                        "type": "scan_progress",
                        "data": {
                            "status": "scanning" if self.is_scanning else "idle",
                            "current": self.scan_progress,
                            "total": self.scan_total,
                            "ticker": self.current_ticker,
                        },
                    }
                )
            except Exception as e:
                print(f"[Scanner] Failed to broadcast progress: {e}")

    async def _broadcast_status(self):
        """Broadcast current scanner status to all connected clients."""
        if self._ws_manager:
            try:
                await self._ws_manager.broadcast(
                    {
                        "type": "scanner_status",
                        "data": {
                            "is_running": self.is_running,
                            "is_scanning": self.is_scanning,
                            "scan_interval_minutes": self.scan_interval,
                            "last_scan_at": self.last_scan_at.isoformat()
                            if self.last_scan_at
                            else None,
                        },
                    }
                )
            except Exception as e:
                print(f"[Scanner] Failed to broadcast status: {e}")

    async def _broadcast_signals(self, db: Session):
        """Broadcast active signals to all connected clients."""
        if self._ws_manager:
            try:
                signals = (
                    db.query(Signal)
                    .filter(Signal.status.in_(["pending", "triggered", "entered"]))
                    .order_by(Signal.created_at.desc())
                    .all()
                )

                def get_price_updated_at(signal):
                    """Get actual data timestamp from extra_data, fallback to now."""
                    if signal.extra_data and isinstance(signal.extra_data, dict):
                        data_ts = signal.extra_data.get("data_timestamp")
                        if data_ts:
                            return data_ts
                    return now_turkey().isoformat()

                signals_data = [
                    {
                        "id": s.id,
                        "ticker": s.ticker,
                        "market": s.market,
                        "strategy_id": s.strategy_id,
                        "status": s.status,
                        "direction": s.direction,
                        "entry_price": s.entry_price,
                        "stop_loss": s.stop_loss,
                        "take_profit": s.take_profit,
                        "current_price": s.current_price,
                        "price_updated_at": get_price_updated_at(s),
                        "last_peak": s.last_peak,
                        "last_trough": s.last_trough,
                        "entry_reached": s.entry_reached or False,
                        "actual_entry_price": s.actual_entry_price,
                        "lots": s.lots or 0,
                        "remaining_lots": s.remaining_lots or 0,
                        "notes": s.notes,
                        "created_at": s.created_at.isoformat()
                        if s.created_at
                        else None,
                        "triggered_at": s.triggered_at.isoformat()
                        if s.triggered_at
                        else None,
                        "entered_at": s.entered_at.isoformat()
                        if s.entered_at
                        else None,
                    }
                    for s in signals
                ]
                await self._ws_manager.broadcast(
                    {"type": "signals_update", "data": signals_data}
                )
            except Exception as e:
                print(f"[Scanner] Failed to broadcast signals: {e}")

    async def start(self):
        """Start the scanner loop."""
        if self.is_running:
            return

        self.is_running = True
        self._task = asyncio.create_task(self._scan_loop())
        print(f"[Scanner] Started with {self.scan_interval} minute interval")
        await self._broadcast_status()

    async def stop(self):
        """Stop the scanner loop."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("[Scanner] Stopped")
        await self._broadcast_status()

    def set_interval(self, minutes: int):
        """Set scan interval in minutes."""
        self.scan_interval = max(1, minutes)
        print(f"[Scanner] Interval set to {self.scan_interval} minutes")

    def _is_bist_market_open(self) -> bool:
        """
        Check if BIST100 market is open.
        BIST100 hours: Monday-Friday, 10:00-18:00 Turkey time
        With +-30 min buffer: 09:30-18:30
        """
        now = now_turkey()

        # Check if weekend (Saturday=5, Sunday=6)
        if now.weekday() >= 5:
            return False

        # Check time (09:30 - 18:30 with buffer)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=18, minute=30, second=0, microsecond=0)

        return market_open <= now <= market_close

    async def _cleanup_day_end_signals(self):
        """Clean up non-entered signals at end of day (keep only 'entered' positions)."""
        db = SessionLocal()
        try:
            now = now_turkey()

            # Find all pending and triggered signals (not entered)
            signals_to_cancel = (
                db.query(Signal)
                .filter(Signal.status.in_(["pending", "triggered"]))
                .all()
            )

            if signals_to_cancel:
                print(
                    f"[Scanner] 🌙 End of day cleanup: cancelling {len(signals_to_cancel)} pending/triggered signals"
                )
                for signal in signals_to_cancel:
                    signal.status = "cancelled"
                    signal.closed_at = now
                    signal.notes = (
                        f"Gün sonu temizliği - {now.strftime('%Y-%m-%d %H:%M')}"
                    )
                db.commit()
                await self._broadcast_signals(db)
        except Exception as e:
            print(f"[Scanner] Error in day-end cleanup: {e}")
            db.rollback()
        finally:
            db.close()

    async def _scan_loop(self):
        """Main scanning loop."""
        _day_end_cleanup_done = None  # Track which day we did cleanup for
        _was_market_open = False  # Track market state transitions

        while self.is_running:
            try:
                now = now_turkey()
                today = now.date()
                market_open = self._is_bist_market_open()

                # Day-end cleanup: when market transitions from open to closed
                if (
                    _was_market_open
                    and not market_open
                    and _day_end_cleanup_done != today
                ):
                    print(f"[Scanner] Market just closed, running day-end cleanup...")
                    await self._cleanup_day_end_signals()
                    _day_end_cleanup_done = today

                _was_market_open = market_open

                # Check if BIST market is open
                if not market_open:
                    # Also do cleanup if we haven't yet today (e.g., scanner started after market close)
                    if (
                        now.weekday() < 5
                        and now.hour >= 18
                        and _day_end_cleanup_done != today
                    ):
                        print(
                            f"[Scanner] Market already closed, running day-end cleanup..."
                        )
                        await self._cleanup_day_end_signals()
                        _day_end_cleanup_done = today

                    print(
                        f"[Scanner] Market closed ({now.strftime('%H:%M')}), skipping scan..."
                    )
                    await asyncio.sleep(self.scan_interval * 60)
                    continue

                await self.scan_all()
                await asyncio.sleep(self.scan_interval * 60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Scanner] Error in scan loop: {e}")
                await asyncio.sleep(60)  # Wait before retry

    async def scan_all(self):
        """Scan all active watchlist items in parallel."""
        # Prevent concurrent scans
        if self.is_scanning:
            print("[Scanner] Scan already in progress, skipping...")
            return

        self.is_scanning = True
        self.scan_progress = 0
        self.scan_total = 0
        self.current_ticker = ""
        await self._broadcast_status()  # Notify clients scan started

        db = SessionLocal()
        try:
            # Get scanner config
            config = db.query(ScannerConfig).first()
            if config:
                self.scan_interval = config.scan_interval_minutes

            # Get active watchlist items
            watchlist = (
                db.query(WatchlistItem).filter(WatchlistItem.is_active == True).all()
            )

            if not watchlist:
                return

            self.scan_total = len(watchlist)
            print(
                f"[Scanner] Scanning {len(watchlist)} items in parallel (batch size: {SCAN_BATCH_SIZE})..."
            )
            await self._broadcast_scan_progress()

            # Process in batches for parallel execution
            for batch_start in range(0, len(watchlist), SCAN_BATCH_SIZE):
                batch = watchlist[batch_start : batch_start + SCAN_BATCH_SIZE]

                # Create tasks for this batch
                tasks = []
                for item in batch:
                    tasks.append(self._scan_ticker_async(item))

                # Execute batch in parallel
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for i, (item, result) in enumerate(zip(batch, results)):
                    self.scan_progress = batch_start + i + 1
                    self.current_ticker = item.ticker.replace(".IS", "")

                    if isinstance(result, Exception):
                        print(f"[Scanner] Error scanning {item.ticker}: {result}")
                    elif result is not None:
                        # result is (item_id, strategy_id, strategy_result, existing_signal_id)
                        item_id, strategy_id, strategy_result, existing_signal_id = (
                            result
                        )
                        # Re-fetch all objects from main db session to avoid detached instance
                        item_data = (
                            db.query(WatchlistItem)
                            .filter(WatchlistItem.id == item_id)
                            .first()
                        )
                        strategy_db = (
                            db.query(Strategy)
                            .filter(Strategy.id == strategy_id)
                            .first()
                        )
                        existing_signal = None
                        if existing_signal_id:
                            existing_signal = (
                                db.query(Signal)
                                .filter(Signal.id == existing_signal_id)
                                .first()
                            )

                        if item_data and strategy_db:
                            await self._process_result(
                                db,
                                item_data,
                                strategy_db,
                                strategy_result,
                                existing_signal,
                            )

                    # Broadcast progress every few tickers
                    if (
                        self.scan_progress % 5 == 0
                        or self.scan_progress == self.scan_total
                    ):
                        await self._broadcast_scan_progress()

                # Small delay between batches to avoid API throttling
                if batch_start + SCAN_BATCH_SIZE < len(watchlist):
                    await asyncio.sleep(0.3)

            # Update last scan time
            self.last_scan_at = now_turkey()
            if config:
                config.last_scan_at = self.last_scan_at
                db.commit()

            print(f"[Scanner] Scan complete at {now_turkey().strftime('%H:%M:%S')}")

        except Exception as e:
            print(f"[Scanner] Error in scan_all: {e}")
        finally:
            self.is_scanning = False
            self.scan_progress = 0
            self.scan_total = 0
            self.current_ticker = ""
            await self._broadcast_scan_progress()
            await self._broadcast_status()  # Notify clients scan finished
            db.close()

    async def _scan_ticker_async(self, item: WatchlistItem):
        """Async wrapper to scan a ticker and return result for batch processing."""
        db = SessionLocal()
        try:
            # Get strategy
            strategy_db = (
                db.query(Strategy).filter(Strategy.id == item.strategy_id).first()
            )
            if not strategy_db or not strategy_db.is_active:
                return None

            # Get strategy class
            strategy_class = get_strategy_class(strategy_db.strategy_type)
            if not strategy_class:
                print(f"[Scanner] Unknown strategy type: {strategy_db.strategy_type}")
                return None

            # Initialize strategy
            strategy = strategy_class(
                params=strategy_db.params or {},
                risk_reward_ratio=strategy_db.risk_reward_ratio,
            )

            # Fetch data in a thread pool to avoid blocking the event loop
            def fetch_data():
                try:
                    analyzer = StockAnalyzer(
                        ticker=item.ticker,
                        market=item.market,
                        horizon=strategy_db.horizon or "short",
                    )
                    return analyzer.data
                except Exception as e:
                    print(f"[Scanner] Failed to fetch data for {item.ticker}: {e}")
                    return pd.DataFrame()

            loop = asyncio.get_event_loop()
            try:
                data = await asyncio.wait_for(
                    loop.run_in_executor(_executor, fetch_data),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                print(f"[Scanner] Timeout fetching data for {item.ticker}")
                return None
            except Exception as e:
                print(f"[Scanner] Error fetching data for {item.ticker}: {e}")
                return None

            if data.empty:
                return None

            # Get actual data timestamp (last candle time)
            data_timestamp = data.index[-1].isoformat() if len(data) > 0 else None

            # Evaluate strategy
            result = strategy.evaluate(data)

            # Store data timestamp in result's extra_data
            if result.extra_data is None:
                result.extra_data = {}
            result.extra_data["data_timestamp"] = data_timestamp

            # Get real-time current price
            real_current_price = await self._get_realtime_price(
                item.ticker, item.market
            )
            if real_current_price is not None:
                result.current_price = real_current_price

            # Check for existing signal - return only ID for main session to re-fetch
            existing_signal = (
                db.query(Signal)
                .filter(
                    Signal.ticker == item.ticker,
                    Signal.strategy_id == item.strategy_id,
                    Signal.status.in_(["pending", "triggered", "entered"]),
                )
                .first()
            )
            existing_signal_id = existing_signal.id if existing_signal else None

            # Return IDs and result for processing (avoid detached instances)
            return (item.id, strategy_db.id, result, existing_signal_id)
        finally:
            db.close()

    async def scan_ticker(self, db: Session, item: WatchlistItem):
        """Scan a single ticker for the assigned strategy."""

        # Get strategy
        strategy_db = db.query(Strategy).filter(Strategy.id == item.strategy_id).first()
        if not strategy_db or not strategy_db.is_active:
            return

        # Get strategy class
        strategy_class = get_strategy_class(strategy_db.strategy_type)
        if not strategy_class:
            print(f"[Scanner] Unknown strategy type: {strategy_db.strategy_type}")
            return

        # Initialize strategy
        strategy = strategy_class(
            params=strategy_db.params or {},
            risk_reward_ratio=strategy_db.risk_reward_ratio,
        )

        # Fetch data in a thread pool to avoid blocking the event loop
        def fetch_data():
            try:
                analyzer = StockAnalyzer(
                    ticker=item.ticker,
                    market=item.market,
                    horizon=strategy_db.horizon or "short",  # Use strategy's timeframe
                )
                return analyzer.data
            except Exception as e:
                print(f"[Scanner] Failed to fetch data for {item.ticker}: {e}")
                return pd.DataFrame()

        loop = asyncio.get_event_loop()
        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(_executor, fetch_data),
                timeout=30.0,  # 30 second timeout per ticker
            )
        except asyncio.TimeoutError:
            print(f"[Scanner] Timeout fetching data for {item.ticker}")
            return
        except Exception as e:
            print(f"[Scanner] Error fetching data for {item.ticker}: {e}")
            return

        if data.empty:
            return

        # Get actual data timestamp (last candle time)
        data_timestamp = data.index[-1].isoformat() if len(data) > 0 else None

        # Evaluate strategy
        result = strategy.evaluate(data)

        # Store data timestamp in result's extra_data
        if result.extra_data is None:
            result.extra_data = {}
        result.extra_data["data_timestamp"] = data_timestamp

        # Get real-time current price (independent of strategy timeframe)
        # This ensures all signals show the same current price regardless of horizon
        real_current_price = await self._get_realtime_price(item.ticker, item.market)
        if real_current_price is not None:
            result.current_price = real_current_price

        # Check for existing signal (including entered positions to avoid duplicates)
        existing_signal = (
            db.query(Signal)
            .filter(
                Signal.ticker == item.ticker,
                Signal.strategy_id == item.strategy_id,
                Signal.status.in_(["pending", "triggered", "entered"]),
            )
            .first()
        )

        # Process result
        await self._process_result(db, item, strategy_db, result, existing_signal)

    async def _get_realtime_price(self, ticker: str, market: str) -> Optional[float]:
        """Get real-time price for a ticker, independent of strategy timeframe."""
        loop = asyncio.get_event_loop()

        def fetch_price():
            try:
                if market == "bist100":
                    # Use yfinance for BIST stocks
                    yf_ticker = yf.Ticker(ticker)
                    # Try fast_info first (faster), fallback to history
                    try:
                        price = yf_ticker.fast_info.last_price
                        if price and price > 0:
                            return float(price)
                    except Exception:
                        pass
                    # Fallback: get last close from recent history
                    hist = yf_ticker.history(period="1d", interval="1m")
                    if not hist.empty:
                        return float(hist["Close"].iloc[-1])
                else:
                    # Use ccxt for Binance
                    import ccxt

                    exchange = ccxt.binance()
                    symbol = ticker.replace("TRY", "/TRY")
                    ticker_data = exchange.fetch_ticker(symbol)
                    if ticker_data and "last" in ticker_data:
                        return float(ticker_data["last"])
            except Exception as e:
                print(f"[Scanner] Failed to get realtime price for {ticker}: {e}")
            return None

        try:
            return await asyncio.wait_for(
                loop.run_in_executor(_executor, fetch_price),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            print(f"[Scanner] Timeout getting realtime price for {ticker}")
            return None

    async def _process_result(
        self,
        db: Session,
        item: WatchlistItem,
        strategy_db: Strategy,
        result: StrategyResult,
        existing_signal: Optional[Signal],
    ):
        """Process strategy result and update signals."""

        # Convert numpy types to native Python types for JSON serialization
        current_price = to_python_native(result.current_price)
        entry_price = to_python_native(result.entry_price)
        stop_loss = to_python_native(result.stop_loss)
        take_profit = to_python_native(result.take_profit)
        last_peak = to_python_native(result.last_peak)
        last_trough = to_python_native(result.last_trough)
        extra_data = to_python_native(result.extra_data)

        # Case 1: Main condition met - new signal triggered
        if result.main_condition_met:
            if existing_signal and existing_signal.status == "triggered":
                # Already triggered, check price levels
                existing_signal.extra_data = extra_data  # Update data_timestamp
                await self._check_entry_exit(db, existing_signal, result)
            elif existing_signal and existing_signal.status == "entered":
                # Already in position, just update current price and check SL/TP
                existing_signal.current_price = current_price
                existing_signal.extra_data = extra_data  # Update data_timestamp
                # Check if SL or TP hit for entered position
                await self._check_position_levels(db, existing_signal, result)
            else:
                # Create new triggered signal
                if existing_signal:
                    existing_signal.status = "cancelled"
                    existing_signal.notes = "Replaced by new signal"

                new_signal = Signal(
                    ticker=item.ticker,
                    market=item.market,
                    strategy_id=item.strategy_id,
                    status="triggered",
                    direction=result.direction,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    current_price=current_price,
                    last_peak=last_peak,
                    last_trough=last_trough,
                    triggered_at=now_turkey(),
                    notes=result.notes,
                    extra_data=extra_data,
                )
                db.add(new_signal)
                print(
                    f"[Scanner] 🎯 NEW SIGNAL: {item.ticker} {result.direction.upper()} @ {entry_price}"
                )

                # Send email notification for new triggered signal (if enabled)
                if self.email_notifications.get("triggered", True):
                    strategy = (
                        db.query(Strategy)
                        .filter(Strategy.id == item.strategy_id)
                        .first()
                    )
                    strategy_name = strategy.name if strategy else ""
                    EmailService.send_signal_triggered(
                        ticker=item.ticker,
                        market=item.market,
                        direction=result.direction,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        current_price=current_price,
                        strategy_name=strategy_name,
                    )

        # Case 2: Precondition met but main condition not - pending
        elif result.precondition_met:
            # Skip if already in position
            if existing_signal and existing_signal.status == "entered":
                existing_signal.current_price = current_price
                existing_signal.extra_data = extra_data  # Update data_timestamp
            elif existing_signal and existing_signal.status == "triggered":
                # Update current price for triggered signals even when main condition not met
                existing_signal.current_price = current_price
                existing_signal.extra_data = extra_data  # Update data_timestamp
                await self._check_entry_exit(db, existing_signal, result)
            elif not existing_signal:
                new_signal = Signal(
                    ticker=item.ticker,
                    market=item.market,
                    strategy_id=item.strategy_id,
                    status="pending",
                    direction=result.direction,
                    current_price=current_price,
                    last_peak=last_peak,
                    last_trough=last_trough,
                    notes="Ön koşul sağlandı, ana koşul bekleniyor",
                    extra_data=extra_data,
                )
                db.add(new_signal)
            elif existing_signal.status == "pending":
                # Update existing pending signal
                existing_signal.current_price = current_price
                existing_signal.last_peak = last_peak
                existing_signal.last_trough = last_trough
                existing_signal.extra_data = extra_data

        # Case 3: Precondition not met - cancel pending signals (but not entered positions)
        else:
            if existing_signal and existing_signal.status == "pending":
                existing_signal.status = "cancelled"
                existing_signal.closed_at = now_turkey()
                existing_signal.notes = "Ön koşul artık sağlanmıyor"
            elif existing_signal and existing_signal.status == "triggered":
                # Update current price for triggered signals
                existing_signal.current_price = current_price
                existing_signal.extra_data = extra_data  # Update data_timestamp
                await self._check_entry_exit(db, existing_signal, result)
            elif existing_signal and existing_signal.status == "entered":
                # Just update current price for entered positions
                existing_signal.current_price = current_price
                existing_signal.extra_data = extra_data  # Update data_timestamp

        db.commit()
        await self._broadcast_signals(db)

    async def _check_entry_exit(
        self, db: Session, signal: Signal, result: StrategyResult
    ):
        """Check if entry or exit conditions are met for a triggered signal."""

        current_price = to_python_native(result.current_price)
        signal.current_price = current_price

        if signal.direction == "long":
            # Check stop loss
            if current_price <= signal.stop_loss:
                await self._close_signal(db, signal, "stopped", current_price)
                return

            # Check take profit
            if current_price >= signal.take_profit:
                await self._close_signal(db, signal, "target_hit", current_price)
                return

            # Check entry price reached (notify user, don't auto-enter)
            if (
                signal.status == "triggered"
                and not signal.entry_reached
                and current_price >= signal.entry_price
            ):
                signal.entry_reached = True
                print(
                    f"[Scanner] 📍 ENTRY REACHED: {signal.ticker} LONG @ {current_price} - Awaiting user confirmation"
                )

                # Send email notification - user should confirm entry (if enabled)
                if self.email_notifications.get("entryReached", True):
                    EmailService.send_signal_entered(
                        ticker=signal.ticker,
                        market=signal.market,
                        direction=signal.direction,
                        entry_price=signal.entry_price,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                    )

        else:  # short
            # Check stop loss
            if current_price >= signal.stop_loss:
                await self._close_signal(db, signal, "stopped", current_price)
                return

            # Check take profit
            if current_price <= signal.take_profit:
                await self._close_signal(db, signal, "target_hit", current_price)
                return

            # Check entry price reached (notify user, don't auto-enter)
            if (
                signal.status == "triggered"
                and not signal.entry_reached
                and current_price <= signal.entry_price
            ):
                signal.entry_reached = True
                print(
                    f"[Scanner] 📍 ENTRY REACHED: {signal.ticker} SHORT @ {current_price} - Awaiting user confirmation"
                )

                # Send email notification - user should confirm entry (if enabled)
                if self.email_notifications.get("entryReached", True):
                    EmailService.send_signal_entered(
                        ticker=signal.ticker,
                        market=signal.market,
                        direction=signal.direction,
                        entry_price=signal.entry_price,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                    )

        db.commit()
        await self._broadcast_signals(db)

    async def _check_position_levels(
        self, db: Session, signal: Signal, result: StrategyResult
    ):
        """Check SL/TP levels for an entered position."""

        current_price = to_python_native(result.current_price)
        signal.current_price = current_price

        if signal.direction == "long":
            # Check stop loss
            if current_price <= signal.stop_loss:
                print(f"[Scanner] ⚠️ SL HIT: {signal.ticker} LONG @ {current_price}")
                # Don't auto-close, just notify - user manages position manually
                return

            # Check take profit
            if current_price >= signal.take_profit:
                print(f"[Scanner] 🎯 TP HIT: {signal.ticker} LONG @ {current_price}")
                return

        else:  # short
            # Check stop loss
            if current_price >= signal.stop_loss:
                print(f"[Scanner] ⚠️ SL HIT: {signal.ticker} SHORT @ {current_price}")
                return

            # Check take profit
            if current_price <= signal.take_profit:
                print(f"[Scanner] 🎯 TP HIT: {signal.ticker} SHORT @ {current_price}")
                return

        db.commit()
        await self._broadcast_signals(db)

    async def _close_signal(
        self, db: Session, signal: Signal, reason: str, exit_price: float
    ):
        """Close a signal and record trade history."""

        signal.status = reason
        signal.closed_at = now_turkey()

        # Calculate profit/loss
        if signal.entered_at:  # Only if actually entered
            if signal.direction == "long":
                profit_percent = (
                    (exit_price - signal.entry_price) / signal.entry_price
                ) * 100
            else:
                profit_percent = (
                    (signal.entry_price - exit_price) / signal.entry_price
                ) * 100

            # Calculate achieved R:R
            if signal.direction == "long":
                risk = signal.entry_price - signal.stop_loss
                reward = exit_price - signal.entry_price
            else:
                risk = signal.stop_loss - signal.entry_price
                reward = signal.entry_price - exit_price

            rr_achieved = reward / risk if risk > 0 else 0

            result = (
                "win"
                if profit_percent > 0
                else ("loss" if profit_percent < 0 else "breakeven")
            )

            # Record trade history
            trade = TradeHistory(
                signal_id=signal.id,
                ticker=signal.ticker,
                market=signal.market,
                strategy_id=signal.strategy_id,
                direction=signal.direction,
                entry_price=signal.entry_price,
                exit_price=exit_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                result=result,
                profit_percent=round(profit_percent, 2),
                risk_reward_achieved=round(rr_achieved, 2),
                entered_at=signal.entered_at,
                closed_at=now_turkey(),
                notes=f"Closed by {reason}",
            )
            db.add(trade)

            emoji = "🟢" if result == "win" else ("🔴" if result == "loss" else "⚪")
            print(
                f"[Scanner] {emoji} CLOSED: {signal.ticker} {reason} @ {exit_price} ({profit_percent:+.2f}%)"
            )

        db.commit()
        await self._broadcast_signals(db)


# Global scanner instance
scanner = ScannerService()
