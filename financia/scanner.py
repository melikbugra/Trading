"""
Scanner service for monitoring watchlist and generating signals.
Supports both BIST100 and Binance markets.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, List, Dict, Any
import pandas as pd

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
)
from financia.notification_service import EmailService

# Thread pool for running blocking operations
_executor = ThreadPoolExecutor(max_workers=4)


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
        # Email notification settings (in-memory, configurable via API)
        self.email_notifications = {
            "triggered": True,  # Send email when signal is triggered
            "entryReached": True,  # Send email when entry price is reached
        }

    def set_ws_manager(self, manager):
        """Set WebSocket manager for broadcasting updates."""
        self._ws_manager = manager

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

    async def _scan_loop(self):
        """Main scanning loop."""
        while self.is_running:
            try:
                await self.scan_all()
                await asyncio.sleep(self.scan_interval * 60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Scanner] Error in scan loop: {e}")
                await asyncio.sleep(60)  # Wait before retry

    async def scan_all(self):
        """Scan all active watchlist items."""
        # Prevent concurrent scans
        if self.is_scanning:
            print("[Scanner] Scan already in progress, skipping...")
            return

        self.is_scanning = True
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

            print(f"[Scanner] Scanning {len(watchlist)} items...")

            for i, item in enumerate(watchlist):
                try:
                    await self.scan_ticker(db, item)
                    # Rate limiting: small delay between tickers to avoid API throttling
                    if i < len(watchlist) - 1:
                        await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"[Scanner] Error scanning {item.ticker}: {e}")
                    continue  # Continue with next ticker on error

            # Update last scan time
            self.last_scan_at = datetime.utcnow()
            if config:
                config.last_scan_at = self.last_scan_at
                db.commit()

            print(f"[Scanner] Scan complete at {datetime.now().strftime('%H:%M:%S')}")

        except Exception as e:
            print(f"[Scanner] Error in scan_all: {e}")
        finally:
            self.is_scanning = False
            await self._broadcast_status()  # Notify clients scan finished
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

        # Evaluate strategy
        result = strategy.evaluate(data)

        # Check for existing signal
        existing_signal = (
            db.query(Signal)
            .filter(
                Signal.ticker == item.ticker,
                Signal.strategy_id == item.strategy_id,
                Signal.status.in_(["pending", "triggered"]),
            )
            .first()
        )

        # Process result
        await self._process_result(db, item, strategy_db, result, existing_signal)

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
                await self._check_entry_exit(db, existing_signal, result)
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
                    triggered_at=datetime.utcnow(),
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
                        db.query(Strategy).filter(Strategy.id == item.strategy_id).first()
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
            if not existing_signal:
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

        # Case 3: Precondition not met - cancel pending signals
        else:
            if existing_signal and existing_signal.status == "pending":
                existing_signal.status = "cancelled"
                existing_signal.closed_at = datetime.utcnow()
                existing_signal.notes = "Ön koşul artık sağlanmıyor"

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

    async def _close_signal(
        self, db: Session, signal: Signal, reason: str, exit_price: float
    ):
        """Close a signal and record trade history."""

        signal.status = reason
        signal.closed_at = datetime.utcnow()

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
                closed_at=datetime.utcnow(),
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
