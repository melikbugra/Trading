"""
Simulation Scanner service for replaying historical data.
Iterates through hourly bars and evaluates strategies as if in real-time.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import pandas as pd
import yfinance as yf

from sqlalchemy.orm import Session

from financia.strategies import get_strategy_class
from financia.strategies.base import StrategyResult, to_python_native
from financia.web_api.database import (
    SimStrategy,
    SimWatchlistItem,
    SimSignal,
    SimTradeHistory,
    SimScannerConfig,
    SessionLocal,
    simulation_time_manager,
)

# Thread pool for running blocking operations - increased for parallel scanning
_executor = ThreadPoolExecutor(max_workers=10)

# Larger thread pool for EOD parallel fetching
_eod_executor = ThreadPoolExecutor(max_workers=15)

# Concurrency settings for EOD
EOD_BATCH_SIZE = 15  # Number of tickers to fetch in parallel
EOD_RATE_LIMIT_DELAY = 0.1  # Short delay between individual requests in batch

# Concurrency settings for scan
SCAN_BATCH_SIZE = 10  # Number of tickers to scan in parallel


class SimulationScanner:
    """
    Background service that replays historical data for simulation mode.
    Advances through hourly bars and evaluates strategies.
    """

    def __init__(self):
        self.is_running = False
        self.is_paused = False
        self._task: Optional[asyncio.Task] = None
        self._ws_manager = None

        # Data cache to avoid repeated API calls
        self._data_cache: Dict[str, pd.DataFrame] = {}

        # Progress tracking for scans
        self.scan_progress = 0
        self.scan_total = 0
        self.current_ticker = ""

    def set_ws_manager(self, manager):
        """Set WebSocket manager for broadcasting updates."""
        self._ws_manager = manager

    async def _broadcast_status(self):
        """Broadcast current simulation status to all connected clients."""
        if self._ws_manager:
            try:
                status = simulation_time_manager.get_status()
                # Add scanner-level backtest running state
                if status.get("is_backtest"):
                    status["is_backtest_running"] = self.is_running
                await self._ws_manager.broadcast(
                    {
                        "type": "sim_status",
                        "data": status,
                    }
                )
            except Exception as e:
                print(f"[SimScanner] Failed to broadcast status: {e}")

    async def _broadcast_scan_progress(self):
        """Broadcast scan progress to all connected clients."""
        if self._ws_manager:
            try:
                await self._ws_manager.broadcast(
                    {
                        "type": "sim_scan_progress",
                        "data": {
                            "status": "scanning"
                            if simulation_time_manager.is_scanning
                            else "idle",
                            "current": self.scan_progress,
                            "total": self.scan_total,
                            "ticker": self.current_ticker,
                        },
                    }
                )
            except Exception as e:
                print(f"[SimScanner] Failed to broadcast scan progress: {e}")

    async def _broadcast_signals(self, db: Session):
        """Broadcast active simulation signals to all connected clients."""
        if self._ws_manager:
            try:
                signals = (
                    db.query(SimSignal)
                    .filter(SimSignal.status.in_(["pending", "triggered", "entered"]))
                    .order_by(SimSignal.created_at.desc())
                    .all()
                )

                def get_price_updated_at(signal):
                    """Get actual data timestamp from extra_data, fallback to sim_time."""
                    if signal.extra_data and isinstance(signal.extra_data, dict):
                        data_ts = signal.extra_data.get("data_timestamp")
                        if data_ts:
                            return data_ts
                    sim_time = simulation_time_manager.current_time
                    return sim_time.isoformat() if sim_time else None

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
                        "sl_tp_alert": (s.extra_data or {}).get("sl_tp_alert")
                        if s.status == "entered"
                        else None,
                    }
                    for s in signals
                ]
                await self._ws_manager.broadcast(
                    {
                        "type": "sim_signals_update",
                        "data": signals_data,
                    }
                )
            except Exception as e:
                print(f"[SimScanner] Failed to broadcast signals: {e}")

    async def _cleanup_day_end_signals(self):
        """Clean up non-entered signals at end of day (keep only 'entered' positions)."""
        db = SessionLocal()
        try:
            sim_time = simulation_time_manager.current_time

            # Find all pending and triggered signals (not entered)
            signals_to_cancel = (
                db.query(SimSignal)
                .filter(SimSignal.status.in_(["pending", "triggered"]))
                .all()
            )

            cancelled_count = 0
            for signal in signals_to_cancel:
                signal.status = "cancelled"
                signal.closed_at = sim_time
                signal.notes = f"Gün sonu temizliği - {sim_time.strftime('%d.%m.%Y')}"
                cancelled_count += 1

            if cancelled_count > 0:
                db.commit()
                print(
                    f"[SimScanner] Day end cleanup: cancelled {cancelled_count} non-entered signals"
                )
                await self._broadcast_signals(db)

        except Exception as e:
            print(f"[SimScanner] Error in day end cleanup: {e}")
        finally:
            db.close()

    async def start(self):
        """Start the simulation scanner loop."""
        if self.is_running:
            return

        self.is_running = True
        self.is_paused = False
        self._data_cache = {}  # Clear cache on start
        self._task = asyncio.create_task(self._simulation_loop())

        print("[SimScanner] Started simulation")
        await self._broadcast_status()

    async def start_backtest(self):
        """Start the backtest mode - fully automated simulation."""
        if self.is_running:
            return

        self.is_running = True
        self.is_paused = False
        self._data_cache = {}
        self._task = asyncio.create_task(self._backtest_loop())

        print("[SimScanner] Started backtest")
        await self._broadcast_status()

    async def stop(self):
        """Stop the simulation scanner loop."""
        self.is_running = False
        self.is_paused = False
        self._data_cache = {}

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        print("[SimScanner] Stopped")
        await self._broadcast_status()

    def pause(self):
        """Pause the simulation."""
        self.is_paused = True
        print("[SimScanner] Paused")

    def clear_cache(self):
        """Clear data cache - should be called when moving to next day."""
        self._data_cache = {}
        print("[SimScanner] Data cache cleared")

    async def resume(self):
        """Resume the simulation."""
        self.is_paused = False
        print("[SimScanner] Resumed")
        await self._broadcast_status()

    async def scan_now(self):
        """Manually trigger a scan at current simulation time."""
        if not simulation_time_manager.is_active:
            print("[SimScanner] Cannot scan - simulation not active")
            return False

        print("[SimScanner] Manual scan triggered")
        await self._scan_all()

        # Broadcast updated signals
        db = SessionLocal()
        try:
            await self._broadcast_signals(db)
        finally:
            db.close()

        return True

    async def _simulation_loop(self):
        """Main simulation loop - scans at current hour and waits for manual advance."""
        while self.is_running:
            try:
                # Check if paused or day completed or EOD running
                if self.is_paused or simulation_time_manager.is_paused:
                    await asyncio.sleep(0.5)
                    continue

                if (
                    simulation_time_manager.day_completed
                    or simulation_time_manager.is_eod_running
                ):
                    await asyncio.sleep(0.5)
                    continue

                if not simulation_time_manager.is_active:
                    break

                # If current hour already scanned, wait for manual advance
                if simulation_time_manager.hour_completed:
                    await asyncio.sleep(0.5)
                    continue

                # Perform scan at current simulation time
                await self._scan_all()

                # Mark hour as completed - wait for user to click "Sonraki Saat"
                simulation_time_manager.hour_completed = True
                await self._broadcast_status()

                print(
                    f"[SimScanner] Hour scan complete at {simulation_time_manager.current_time.strftime('%Y-%m-%d %H:%M')} - waiting for manual advance"
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[SimScanner] Error in loop: {e}")
                import traceback

                traceback.print_exc()
                await asyncio.sleep(1)

    async def _backtest_loop(self):
        """
        Backtest loop - runs simulation automatically without waiting for user input.
        Auto-enters on triggered signals, auto-exits on SL/TP hit.
        """
        from datetime import datetime as dt

        loop_start = dt.now()

        # Calculate total trading days for progress
        start = simulation_time_manager.start_date
        end = simulation_time_manager.end_date
        total_days = 0
        d = start
        while d <= end:
            if d.weekday() < 5:  # Mon-Fri
                total_days += 1
            d += timedelta(days=1)

        current_day = 0

        print(f"[Backtest] Starting automated run: {total_days} trading days")

        while self.is_running and simulation_time_manager.is_active:
            try:
                sim_time = simulation_time_manager.current_time
                if not sim_time:
                    break

                # Broadcast progress at start of each day
                if sim_time.hour == 9 and sim_time.minute == 30:
                    current_day += 1
                    await self._broadcast_backtest_progress(
                        current_day, total_days, sim_time
                    )
                    print(
                        f"[Backtest] Day {current_day}/{total_days}: {sim_time.strftime('%Y-%m-%d')}"
                    )

                # 1. Scan all tickers at current hour
                await self._scan_all()

                # 2. Auto-trade: enter triggered signals, exit on SL/TP
                await self._backtest_auto_trade()

                # 3. Advance to next hour
                day_done = simulation_time_manager.advance_hour()

                if day_done:
                    # Day end: close all open positions at EOD price
                    await self._backtest_close_eod_positions()

                    # Day end: cleanup non-entered signals
                    await self._cleanup_day_end_signals()

                    # Move to next day
                    is_complete = simulation_time_manager.next_day()

                    if is_complete:
                        # Backtest finished
                        break

                    # Clear cache for new day
                    self.clear_cache()

                # Yield to event loop briefly to allow WS broadcasts and cancellation
                await asyncio.sleep(0)

            except asyncio.CancelledError:
                print("[Backtest] Loop cancelled")
                break
            except Exception as e:
                print(f"[Backtest] Error in loop: {e}")
                import traceback

                traceback.print_exc()
                # Try to continue
                try:
                    day_done = simulation_time_manager.advance_hour()
                    if day_done:
                        is_complete = simulation_time_manager.next_day()
                        if is_complete:
                            break
                        self.clear_cache()
                except Exception:
                    break

        # Backtest complete - wrap in try to handle CancelledError
        try:
            elapsed = (dt.now() - loop_start).total_seconds()
            stats = simulation_time_manager.get_balance_stats()
            print(
                f"[Backtest] Completed in {elapsed:.1f}s | "
                f"Trades: {stats['total_trades']} | "
                f"Win Rate: {stats['win_rate']:.1f}% | "
                f"P/L: {stats['total_profit']:+,.0f} TL ({stats['profit_percent']:+.1f}%)"
            )

            # Mark session as completed
            db = SessionLocal()
            try:
                if simulation_time_manager.session_id:
                    from financia.web_api.database import SimSession

                    session = (
                        db.query(SimSession)
                        .filter(SimSession.id == simulation_time_manager.session_id)
                        .first()
                    )
                    if session:
                        session.status = "completed"
                        session.completed_at = dt.utcnow()
                        db.commit()
            except Exception:
                pass
            finally:
                db.close()

            # Small delay to ensure WS connection is ready
            await asyncio.sleep(0.5)

            # Broadcast completion
            await self._broadcast_backtest_complete()

            # Send results via email
            self._send_backtest_email(stats)

            self.is_running = False
            await self._broadcast_status()
        except asyncio.CancelledError:
            print("[Backtest] Post-loop cancelled, skipping broadcast")
            self.is_running = False
        except Exception as e:
            print(f"[Backtest] Post-loop error: {e}")
            import traceback

            traceback.print_exc()
            self.is_running = False

    async def _backtest_auto_trade(self):
        """
        Auto-trade logic for backtest mode.
        - Enter triggered signals at entry_price with 1 lot.
        - Exit entered signals when SL/TP is hit at the exact SL/TP price.
        """
        db = SessionLocal()
        try:
            sim_time = simulation_time_manager.current_time

            # 1. Auto-exit: Check entered signals for SL/TP hit
            entered_signals = (
                db.query(SimSignal).filter(SimSignal.status == "entered").all()
            )

            for signal in entered_signals:
                extra = signal.extra_data or {}
                alert = extra.get("sl_tp_alert")

                if alert == "sl_hit" and signal.stop_loss:
                    # Exit at SL price
                    await self._backtest_close_position(
                        db, signal, signal.stop_loss, "stopped", sim_time
                    )
                elif alert == "tp_hit" and signal.take_profit:
                    # Exit at TP price
                    await self._backtest_close_position(
                        db, signal, signal.take_profit, "target_hit", sim_time
                    )

            # 2. Auto-enter: Enter triggered signals where entry price has been reached
            triggered_signals = (
                db.query(SimSignal)
                .filter(
                    SimSignal.status == "triggered",
                    SimSignal.entry_reached == True,
                )
                .all()
            )

            for signal in triggered_signals:
                if not signal.entry_price:
                    continue

                lots = 1.0
                position_cost = signal.entry_price * lots

                # Check balance
                if position_cost > simulation_time_manager.current_balance:
                    continue  # Skip - not enough balance

                # Deduct from balance
                simulation_time_manager.current_balance -= position_cost

                # Enter position
                signal.status = "entered"
                signal.entered_at = sim_time
                signal.actual_entry_price = signal.entry_price
                signal.lots = lots
                signal.remaining_lots = lots
                signal.notes = (
                    f"Backtest auto-entry @ {signal.entry_price} x {lots} lot"
                )

            db.commit()

        except Exception as e:
            print(f"[Backtest] Auto-trade error: {e}")
            db.rollback()
        finally:
            db.close()

    async def _backtest_close_eod_positions(self):
        """Close all open (entered) positions at end-of-day price."""
        db = SessionLocal()
        try:
            sim_time = simulation_time_manager.current_time
            entered_signals = (
                db.query(SimSignal).filter(SimSignal.status == "entered").all()
            )

            for signal in entered_signals:
                # Use current_price as EOD price
                eod_price = signal.current_price or signal.entry_price
                await self._backtest_close_position(
                    db, signal, eod_price, "stopped", sim_time
                )
                signal.notes = (
                    f"Backtest: EOD close @ {eod_price} | "
                    + (signal.notes or "").split("|", 1)[-1].strip()
                )

            if entered_signals:
                db.commit()
                print(
                    f"[Backtest] EOD: Closed {len(entered_signals)} open position(s) at day-end price"
                )
        except Exception as e:
            print(f"[Backtest] EOD close error: {e}")
            db.rollback()
        finally:
            db.close()

    async def _backtest_close_position(
        self,
        db: Session,
        signal: SimSignal,
        exit_price: float,
        reason: str,
        sim_time: datetime,
    ):
        """Close a position in backtest mode and record trade history."""
        entry_price = signal.actual_entry_price or signal.entry_price
        lots = signal.lots or 1.0

        if signal.direction == "long":
            profit_percent = ((exit_price - entry_price) / entry_price) * 100
            profit_tl = (exit_price - entry_price) * lots
        else:
            profit_percent = ((entry_price - exit_price) / entry_price) * 100
            profit_tl = (entry_price - exit_price) * lots

        result = "win" if profit_percent > 0 else "loss"

        risk = abs(entry_price - signal.stop_loss) if signal.stop_loss else 1
        reward = abs(exit_price - entry_price)
        rr_achieved = reward / risk if risk > 0 else 0

        # Create trade record
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
            lots=lots,
            risk_reward_achieved=round(rr_achieved, 2),
            entered_at=signal.entered_at,
            closed_at=sim_time,
            notes=f"Backtest auto-{reason} @ {exit_price}",
        )
        db.add(trade)

        # Update balance
        position_value = exit_price * lots
        simulation_time_manager.current_balance += position_value

        # Update stats
        simulation_time_manager.total_profit += profit_tl
        simulation_time_manager.total_trades += 1
        if result == "win":
            simulation_time_manager.winning_trades += 1
        else:
            simulation_time_manager.losing_trades += 1

        # Close signal
        signal.status = reason
        signal.closed_at = sim_time
        signal.remaining_lots = 0
        signal.notes = (
            f"Backtest: {reason} @ {exit_price} | P/L: {profit_percent:+.2f}%"
        )

        db.commit()

    async def _broadcast_backtest_progress(
        self, current_day: int, total_days: int, sim_time: datetime
    ):
        """Broadcast backtest progress."""
        if self._ws_manager:
            try:
                stats = simulation_time_manager.get_balance_stats()
                await self._ws_manager.broadcast(
                    {
                        "type": "sim_backtest_progress",
                        "data": {
                            "current_day": current_day,
                            "total_days": total_days,
                            "current_date": sim_time.strftime("%Y-%m-%d"),
                            "trades_so_far": stats["total_trades"],
                            "current_balance": stats["current_balance"],
                            "total_profit": stats["total_profit"],
                            "status": "running",
                        },
                    }
                )
            except Exception as e:
                print(f"[Backtest] Failed to broadcast progress: {e}")

    async def _broadcast_backtest_complete(self):
        """Broadcast backtest completion with summary."""
        if self._ws_manager:
            try:
                stats = simulation_time_manager.get_balance_stats()

                # Get per-strategy breakdown
                db = SessionLocal()
                try:
                    from financia.web_api.database import SimStrategy as SimStrategyDB

                    strategies = (
                        db.query(SimStrategyDB)
                        .filter(SimStrategyDB.is_active == True)
                        .all()
                    )
                    per_strategy = []
                    for strategy in strategies:
                        trades = (
                            db.query(SimTradeHistory)
                            .filter(SimTradeHistory.strategy_id == strategy.id)
                            .all()
                        )
                        if trades:
                            wins = [t for t in trades if t.result == "win"]
                            total_pl = sum(t.profit_tl for t in trades)
                            profits = [t.profit_percent for t in trades]
                            per_strategy.append(
                                {
                                    "strategy_id": strategy.id,
                                    "strategy_name": strategy.name,
                                    "total_trades": len(trades),
                                    "winning_trades": len(wins),
                                    "losing_trades": len(trades) - len(wins),
                                    "win_rate": round(len(wins) / len(trades) * 100, 1),
                                    "total_profit_tl": round(float(total_pl), 2),
                                    "avg_profit_percent": round(
                                        float(sum(profits) / len(profits)), 2
                                    ),
                                }
                            )
                        else:
                            per_strategy.append(
                                {
                                    "strategy_id": strategy.id,
                                    "strategy_name": strategy.name,
                                    "total_trades": 0,
                                    "winning_trades": 0,
                                    "losing_trades": 0,
                                    "win_rate": 0,
                                    "total_profit_tl": 0,
                                    "avg_profit_percent": 0,
                                }
                            )
                finally:
                    db.close()

                message = {
                    "type": "backtest_complete",
                    "data": {
                        "summary": stats,
                        "per_strategy": per_strategy,
                    },
                }
                print(
                    f"[Backtest] Broadcasting completion: {len(per_strategy)} strategies, {stats['total_trades']} trades"
                )
                await self._ws_manager.broadcast(message)
                print("[Backtest] Completion broadcast sent successfully")
            except Exception as e:
                print(f"[Backtest] Failed to broadcast completion: {e}")
                import traceback

                traceback.print_exc()

    def _send_backtest_email(self, stats: dict):
        """Send backtest results summary via email."""
        try:
            from financia.notification_service import EmailService

            # Get per-strategy breakdown
            db = SessionLocal()
            try:
                from financia.web_api.database import SimStrategy as SimStrategyDB

                strategies = (
                    db.query(SimStrategyDB)
                    .filter(SimStrategyDB.is_active == True)
                    .all()
                )

                # Build email body
                start_date = simulation_time_manager.start_date
                end_date = simulation_time_manager.end_date
                lines = []
                lines.append("=" * 50)
                lines.append("⚡ BACKTEST SONUÇLARI")
                lines.append("=" * 50)
                lines.append(f"📅 Dönem: {start_date} → {end_date}")
                lines.append(f"💰 Başlangıç: {stats['initial_balance']:,.0f} TL")
                lines.append(f"💰 Son Bakiye: {stats['current_balance']:,.0f} TL")
                lines.append(
                    f"📈 Toplam K/Z: {stats['total_profit']:+,.0f} TL ({stats['profit_percent']:+.1f}%)"
                )
                lines.append(f"🔢 Toplam İşlem: {stats['total_trades']}")
                lines.append(
                    f"✅ Kazanan: {stats['winning_trades']} | ❌ Kaybeden: {stats['losing_trades']}"
                )
                lines.append(f"📊 Kazanma Oranı: {stats['win_rate']:.1f}%")
                lines.append("")

                for strategy in strategies:
                    trades = (
                        db.query(SimTradeHistory)
                        .filter(SimTradeHistory.strategy_id == strategy.id)
                        .all()
                    )
                    lines.append("-" * 40)
                    lines.append(f"📋 {strategy.name} ({strategy.strategy_type})")
                    if trades:
                        wins = [t for t in trades if t.result == "win"]
                        total_pl = sum(t.profit_tl for t in trades)
                        profits = [t.profit_percent for t in trades]
                        win_rate = len(wins) / len(trades) * 100
                        avg_pct = sum(profits) / len(profits)
                        lines.append(
                            f"   İşlem: {len(trades)} | Kazanan: {len(wins)} | Kaybeden: {len(trades) - len(wins)}"
                        )
                        lines.append(f"   Kazanma Oranı: {win_rate:.1f}%")
                        lines.append(f"   Toplam K/Z: {total_pl:+,.0f} TL")
                        lines.append(f"   Ort. Getiri: {avg_pct:+.2f}%")
                        lines.append(
                            f"   En İyi: {max(profits):+.2f}% | En Kötü: {min(profits):+.2f}%"
                        )
                    else:
                        lines.append("   İşlem yok")
                    lines.append("")

                lines.append("=" * 50)
                body = "\n".join(lines)

                # Build subject
                emoji = "📈" if stats["total_profit"] >= 0 else "📉"
                subject = f"{emoji} Backtest: {stats['profit_percent']:+.1f}% | {stats['total_trades']} işlem | {start_date} → {end_date}"

                # Send directly bypassing simulation check
                from financia.notification_service import RECIPIENT_EMAIL

                EmailService._send_sync(subject, body, RECIPIENT_EMAIL)
            finally:
                db.close()

            print("[Backtest] Results email sent")
        except Exception as e:
            print(f"[Backtest] Failed to send email: {e}")

    async def _scan_all(self):
        """Scan all active watchlist items at current simulation time in parallel."""
        db = SessionLocal()
        try:
            sim_time = simulation_time_manager.current_time
            if not sim_time:
                return

            # Get active simulation watchlist items
            watchlist = (
                db.query(SimWatchlistItem)
                .filter(SimWatchlistItem.is_active.is_(True))
                .all()
            )

            if not watchlist:
                return

            # Mark scanning started
            simulation_time_manager.is_scanning = True
            self.scan_progress = 0
            self.scan_total = len(watchlist)
            self.current_ticker = ""
            await self._broadcast_status()
            await self._broadcast_scan_progress()

            print(
                f"[SimScanner] Scanning {len(watchlist)} items in parallel at {sim_time.strftime('%Y-%m-%d %H:%M')}"
            )

            # Process in batches for parallel execution
            for batch_start in range(0, len(watchlist), SCAN_BATCH_SIZE):
                batch = watchlist[batch_start : batch_start + SCAN_BATCH_SIZE]

                # Create tasks for this batch
                tasks = []
                for item in batch:
                    tasks.append(self._scan_ticker_async(item, sim_time))

                # Execute batch in parallel
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for i, (item, result) in enumerate(zip(batch, results)):
                    self.scan_progress = batch_start + i + 1
                    self.current_ticker = item.ticker.replace(".IS", "")

                    if isinstance(result, Exception):
                        print(f"[SimScanner] Error scanning {item.ticker}: {result}")
                    elif result is not None:
                        # result is (item_id, strategy_id, strategy_result, existing_signal_id)
                        item_id, strategy_id, strategy_result, existing_signal_id = (
                            result
                        )
                        # Re-fetch all objects from main db session to avoid detached instance
                        item_data = (
                            db.query(SimWatchlistItem)
                            .filter(SimWatchlistItem.id == item_id)
                            .first()
                        )
                        strategy_db = (
                            db.query(SimStrategy)
                            .filter(SimStrategy.id == strategy_id)
                            .first()
                        )
                        existing_signal = None
                        if existing_signal_id:
                            existing_signal = (
                                db.query(SimSignal)
                                .filter(SimSignal.id == existing_signal_id)
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

                # Small delay between batches
                if batch_start + SCAN_BATCH_SIZE < len(watchlist):
                    await asyncio.sleep(0.1)

            # Mark scanning completed
            simulation_time_manager.is_scanning = False
            self.scan_progress = 0
            self.scan_total = 0
            self.current_ticker = ""
            await self._broadcast_scan_progress()
            await self._broadcast_status()

            # Update last scan time
            config = db.query(SimScannerConfig).first()
            if not config:
                config = SimScannerConfig()
                db.add(config)
            config.last_scan_at = sim_time
            db.commit()

        except Exception as e:
            print(f"[SimScanner] Error in scan_all: {e}")
            simulation_time_manager.is_scanning = False
        finally:
            db.close()

    async def _scan_ticker_async(self, item: SimWatchlistItem, sim_time: datetime):
        """Async wrapper to scan a ticker and return result for batch processing."""
        db = SessionLocal()
        try:
            # Get simulation strategy
            strategy_db = (
                db.query(SimStrategy).filter(SimStrategy.id == item.strategy_id).first()
            )
            if not strategy_db or not strategy_db.is_active:
                return None

            # Get strategy class
            strategy_class = get_strategy_class(strategy_db.strategy_type)
            if not strategy_class:
                print(
                    f"[SimScanner] Unknown strategy type: {strategy_db.strategy_type}"
                )
                return None

            # Initialize strategy
            strategy = strategy_class(
                params=strategy_db.params or {},
                risk_reward_ratio=strategy_db.risk_reward_ratio,
            )

            # Fetch historical data up to simulation time
            data = await self._get_historical_data(
                ticker=item.ticker,
                market=item.market,
                horizon=strategy_db.horizon or "short",
                end_time=sim_time,
            )

            if data.empty:
                return None

            # Get actual data timestamp (last candle time)
            data_timestamp = data.index[-1].isoformat() if len(data) > 0 else None

            # Evaluate strategy
            result = strategy.evaluate(data)

            # Store data timestamp and last candle High/Low in extra_data
            if result.extra_data is None:
                result.extra_data = {}
            result.extra_data["data_timestamp"] = data_timestamp
            # Store last candle High/Low for intra-bar SL/TP detection
            result.extra_data["last_candle_high"] = float(data["High"].iloc[-1])
            result.extra_data["last_candle_low"] = float(data["Low"].iloc[-1])

            # Check for existing signal - return only ID for main session to re-fetch
            existing_signal = (
                db.query(SimSignal)
                .filter(
                    SimSignal.ticker == item.ticker,
                    SimSignal.strategy_id == item.strategy_id,
                    SimSignal.status.in_(["pending", "triggered", "entered"]),
                )
                .first()
            )
            existing_signal_id = existing_signal.id if existing_signal else None

            # Return IDs and result for processing (avoid detached instances)
            return (item.id, strategy_db.id, result, existing_signal_id)
        finally:
            db.close()

    async def _scan_ticker(
        self, db: Session, item: SimWatchlistItem, sim_time: datetime
    ):
        """Scan a single ticker at the current simulation time."""

        # Get simulation strategy
        strategy_db = (
            db.query(SimStrategy).filter(SimStrategy.id == item.strategy_id).first()
        )
        if not strategy_db or not strategy_db.is_active:
            return

        # Get strategy class
        strategy_class = get_strategy_class(strategy_db.strategy_type)
        if not strategy_class:
            print(f"[SimScanner] Unknown strategy type: {strategy_db.strategy_type}")
            return

        # Initialize strategy
        strategy = strategy_class(
            params=strategy_db.params or {},
            risk_reward_ratio=strategy_db.risk_reward_ratio,
        )

        # Fetch historical data up to simulation time
        data = await self._get_historical_data(
            ticker=item.ticker,
            market=item.market,
            horizon=strategy_db.horizon or "short",
            end_time=sim_time,
        )

        if data.empty:
            return

        # Evaluate strategy
        result = strategy.evaluate(data)

        # Check for existing signal
        existing_signal = (
            db.query(SimSignal)
            .filter(
                SimSignal.ticker == item.ticker,
                SimSignal.strategy_id == item.strategy_id,
                SimSignal.status.in_(["pending", "triggered", "entered"]),
            )
            .first()
        )

        # Process result
        await self._process_result(db, item, strategy_db, result, existing_signal)

    async def _get_historical_data(
        self, ticker: str, market: str, horizon: str, end_time: datetime
    ) -> pd.DataFrame:
        """Get historical data up to the specified end time."""

        cache_key = f"{ticker}_{market}_{horizon}"

        # Check cache first
        if cache_key in self._data_cache:
            cached_data = self._data_cache[cache_key]
            # Filter to data before end_time
            if not cached_data.empty:
                filtered = cached_data[cached_data.index <= end_time]
                if not filtered.empty:
                    return filtered

        # Fetch fresh data (with minimal rate limiting since we have cache)
        loop = asyncio.get_event_loop()

        def fetch_data():
            try:
                # Minimal delay - cache handles most requests
                import time

                time.sleep(0.15)

                # Calculate start date - need 200 days for EMA 200
                # But Yahoo Finance limits 1h data to last 730 days from TODAY
                from financia.web_api.database import now_turkey

                today = now_turkey()
                yahoo_limit_start = today - timedelta(days=729)  # Safe margin

                desired_start = end_time - timedelta(days=200)
                start_date = max(
                    desired_start, yahoo_limit_start
                )  # Don't exceed Yahoo limit

                if market == "bist100":
                    stock = yf.Ticker(ticker)
                    data = stock.history(
                        start=start_date,
                        end=end_time + timedelta(days=1),  # Include end date
                        interval="1h",
                    )

                    if isinstance(data.columns, pd.MultiIndex):
                        data.columns = data.columns.get_level_values(0)

                    return data
                else:
                    # Binance - not supported in simulation for now
                    return pd.DataFrame()

            except Exception as e:
                print(f"[SimScanner] Failed to fetch data for {ticker}: {e}")
                return pd.DataFrame()

        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(_executor, fetch_data),
                timeout=30.0,
            )

            # Cache the full data
            if not data.empty:
                self._data_cache[cache_key] = data
                # Filter to end_time
                data = data[data.index <= end_time]

            return data

        except asyncio.TimeoutError:
            print(f"[SimScanner] Timeout fetching data for {ticker}")
            return pd.DataFrame()

    async def _process_result(
        self,
        db: Session,
        item: SimWatchlistItem,
        strategy_db: SimStrategy,
        result: StrategyResult,
        existing_signal: Optional[SimSignal],
    ):
        """Process strategy result and update simulation signals."""

        # Convert numpy types to native Python types
        current_price = to_python_native(result.current_price)
        entry_price = to_python_native(result.entry_price)
        stop_loss = to_python_native(result.stop_loss)
        take_profit = to_python_native(result.take_profit)
        last_peak = to_python_native(result.last_peak)
        last_trough = to_python_native(result.last_trough)
        extra_data = to_python_native(result.extra_data)

        sim_time = simulation_time_manager.current_time

        # For entered positions, check if last candle's High/Low hit SL/TP
        candle_high = extra_data.get("last_candle_high") if extra_data else None
        candle_low = extra_data.get("last_candle_low") if extra_data else None

        def check_sl_tp_hit(signal):
            """Check if candle High/Low touched SL or TP. Returns alert string or None."""
            if (
                not candle_high
                or not candle_low
                or not signal.stop_loss
                or not signal.take_profit
            ):
                return None
            if signal.direction == "long":
                if candle_low <= signal.stop_loss:
                    return "sl_hit"
                if candle_high >= signal.take_profit:
                    return "tp_hit"
            else:  # short
                if candle_high >= signal.stop_loss:
                    return "sl_hit"
                if candle_low <= signal.take_profit:
                    return "tp_hit"
            return None

        def apply_sl_tp_alert(signal, ed):
            """Check SL/TP hit and update extra_data accordingly."""
            alert = check_sl_tp_hit(signal)
            if alert:
                ed["sl_tp_alert"] = alert
                print(
                    f"[SimScanner] {'⚠️ SL' if alert == 'sl_hit' else '🎯 TP'} HIT (intra-bar): {signal.ticker}"
                )
            else:
                ed.pop("sl_tp_alert", None)
            return ed

        # Case 1: Main condition met - new signal triggered
        if result.main_condition_met:
            if existing_signal and existing_signal.status == "triggered":
                # Already triggered, check price levels
                existing_signal.extra_data = extra_data  # Update data_timestamp
                await self._check_entry_exit(db, existing_signal, result)
            elif existing_signal and existing_signal.status == "entered":
                # Already in position, update current price
                existing_signal.current_price = current_price
                extra_data = apply_sl_tp_alert(existing_signal, extra_data)
                existing_signal.extra_data = extra_data
                await self._check_position_levels(db, existing_signal, result)
            else:
                # Create new triggered signal
                if existing_signal:
                    existing_signal.status = "cancelled"
                    existing_signal.notes = "Replaced by new signal"

                new_signal = SimSignal(
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
                    created_at=sim_time,
                    triggered_at=sim_time,
                    notes=result.notes,
                    extra_data=extra_data,
                )
                db.add(new_signal)
                print(
                    f"[SimScanner] 🎯 NEW SIGNAL: {item.ticker} {result.direction.upper()} @ {entry_price}"
                )

                # No email notifications in simulation mode!

        # Case 2: Precondition met but main condition not - pending
        elif result.precondition_met:
            if existing_signal and existing_signal.status == "entered":
                existing_signal.current_price = current_price
                extra_data = apply_sl_tp_alert(existing_signal, extra_data)
                existing_signal.extra_data = extra_data  # Update data_timestamp
            elif existing_signal and existing_signal.status == "triggered":
                # Update current price for triggered signals even when main condition not met
                existing_signal.current_price = current_price
                existing_signal.extra_data = extra_data  # Update data_timestamp
                await self._check_entry_exit(db, existing_signal, result)
            elif not existing_signal:
                new_signal = SimSignal(
                    ticker=item.ticker,
                    market=item.market,
                    strategy_id=item.strategy_id,
                    status="pending",
                    direction=result.direction,
                    current_price=current_price,
                    last_peak=last_peak,
                    last_trough=last_trough,
                    created_at=sim_time,
                    notes="Ön koşul sağlandı, ana koşul bekleniyor",
                    extra_data=extra_data,
                )
                db.add(new_signal)
            elif existing_signal.status == "pending":
                existing_signal.current_price = current_price
                existing_signal.last_peak = last_peak
                existing_signal.last_trough = last_trough
                existing_signal.extra_data = extra_data

        # Case 3: Precondition not met - cancel pending signals
        else:
            if existing_signal and existing_signal.status == "pending":
                existing_signal.status = "cancelled"
                existing_signal.closed_at = sim_time
                existing_signal.notes = "Ön koşul artık sağlanmıyor"
            elif existing_signal and existing_signal.status == "triggered":
                # Update current price for triggered signals
                existing_signal.current_price = current_price
                existing_signal.extra_data = extra_data  # Update data_timestamp
                await self._check_entry_exit(db, existing_signal, result)
            elif existing_signal and existing_signal.status == "entered":
                existing_signal.current_price = current_price
                extra_data = apply_sl_tp_alert(existing_signal, extra_data)
                existing_signal.extra_data = extra_data  # Update data_timestamp

        db.commit()
        await self._broadcast_signals(db)

    async def _check_entry_exit(
        self, db: Session, signal: SimSignal, result: StrategyResult
    ):
        """Check if entry or exit conditions are met for a triggered signal."""
        current_price = to_python_native(result.current_price)
        signal.current_price = current_price

        if signal.direction == "long":
            if current_price <= signal.stop_loss:
                await self._close_signal(db, signal, "stopped", current_price)
                return
            if current_price >= signal.take_profit:
                await self._close_signal(db, signal, "target_hit", current_price)
                return
            if (
                signal.status == "triggered"
                and not signal.entry_reached
                and current_price >= signal.entry_price
            ):
                signal.entry_reached = True
                print(
                    f"[SimScanner] 📍 ENTRY REACHED: {signal.ticker} LONG @ {current_price}"
                )
        else:  # short
            if current_price >= signal.stop_loss:
                await self._close_signal(db, signal, "stopped", current_price)
                return
            if current_price <= signal.take_profit:
                await self._close_signal(db, signal, "target_hit", current_price)
                return
            if (
                signal.status == "triggered"
                and not signal.entry_reached
                and current_price <= signal.entry_price
            ):
                signal.entry_reached = True
                print(
                    f"[SimScanner] 📍 ENTRY REACHED: {signal.ticker} SHORT @ {current_price}"
                )

        db.commit()
        await self._broadcast_signals(db)

    async def _check_position_levels(
        self, db: Session, signal: SimSignal, result: StrategyResult
    ):
        """Check SL/TP levels for an entered position."""
        current_price = to_python_native(result.current_price)
        signal.current_price = current_price

        if signal.direction == "long":
            if current_price <= signal.stop_loss:
                print(f"[SimScanner] ⚠️ SL HIT: {signal.ticker} LONG @ {current_price}")
            elif current_price >= signal.take_profit:
                print(f"[SimScanner] 🎯 TP HIT: {signal.ticker} LONG @ {current_price}")
        else:  # short
            if current_price >= signal.stop_loss:
                print(f"[SimScanner] ⚠️ SL HIT: {signal.ticker} SHORT @ {current_price}")
            elif current_price <= signal.take_profit:
                print(
                    f"[SimScanner] 🎯 TP HIT: {signal.ticker} SHORT @ {current_price}"
                )

        db.commit()
        await self._broadcast_signals(db)

    async def _close_signal(
        self, db: Session, signal: SimSignal, reason: str, exit_price: float
    ):
        """Close a signal and record trade history."""
        sim_time = simulation_time_manager.current_time

        signal.status = reason
        signal.closed_at = sim_time

        if signal.entered_at:
            entry_price = signal.actual_entry_price or signal.entry_price

            if signal.direction == "long":
                profit_percent = ((exit_price - entry_price) / entry_price) * 100
                risk = entry_price - signal.stop_loss if signal.stop_loss else 1
                reward = exit_price - entry_price
            else:
                profit_percent = ((entry_price - exit_price) / entry_price) * 100
                risk = signal.stop_loss - entry_price if signal.stop_loss else 1
                reward = entry_price - exit_price

            rr_achieved = reward / risk if risk > 0 else 0
            result = "win" if profit_percent > 0 else "loss"
            profit_tl = (exit_price - entry_price) * (signal.lots or 0)
            if signal.direction == "short":
                profit_tl = (entry_price - exit_price) * (signal.lots or 0)

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
                lots=signal.lots or 0,
                risk_reward_achieved=round(rr_achieved, 2),
                entered_at=signal.entered_at,
                closed_at=sim_time,
                notes=f"Auto-closed: {reason}",
            )
            db.add(trade)

            # Add position value back to balance (exit_price * lots)
            position_value = exit_price * (signal.lots or 0)
            simulation_time_manager.current_balance += position_value

            # Update trade statistics
            simulation_time_manager.total_profit += profit_tl
            simulation_time_manager.total_trades += 1
            if result == "win":
                simulation_time_manager.winning_trades += 1
            else:
                simulation_time_manager.losing_trades += 1

            print(
                f"[SimScanner] Trade closed: {signal.ticker} {result} {profit_percent:+.2f}% ({profit_tl:+,.0f} TL) | Balance: {simulation_time_manager.current_balance:,.0f} TL"
            )

        signal.notes = f"Closed by {reason} @ {exit_price}"
        db.commit()
        await self._broadcast_signals(db)
        await self._broadcast_status()  # Broadcast updated balance

    def _fetch_eod_data_sync(
        self, ticker: str, sim_time: datetime
    ) -> Tuple[str, Optional[pd.DataFrame]]:
        """Synchronous function to fetch EOD data for a single ticker."""
        try:
            import time

            time.sleep(EOD_RATE_LIMIT_DELAY)  # Small delay to avoid rate limiting

            start_date = sim_time - timedelta(days=30)  # Only need ~10 days for EOD

            stock = yf.Ticker(ticker)
            data = stock.history(
                start=start_date,
                end=sim_time + timedelta(days=1),
                interval="1d",  # Daily data for EOD analysis
            )

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            return (ticker, data)
        except Exception as e:
            print(f"[SimScanner] EOD fetch error for {ticker}: {e}")
            return (ticker, None)

    async def _fetch_eod_batch(
        self, tickers: List[str], sim_time: datetime
    ) -> List[Tuple[str, Optional[pd.DataFrame]]]:
        """Fetch EOD data for a batch of tickers in parallel."""
        loop = asyncio.get_event_loop()

        # Create futures for all tickers in the batch
        futures = [
            loop.run_in_executor(
                _eod_executor, self._fetch_eod_data_sync, ticker, sim_time
            )
            for ticker in tickers
        ]

        # Wait for all with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*futures, return_exceptions=True),
                timeout=60.0,  # 60 second timeout for batch
            )

            # Filter out exceptions
            valid_results = []
            for r in results:
                if isinstance(r, tuple):
                    valid_results.append(r)
                else:
                    # Exception occurred
                    pass
            return valid_results
        except asyncio.TimeoutError:
            print(f"[SimScanner] Batch timeout for {len(tickers)} tickers")
            return []

    async def _run_sim_eod_analysis(self, filters=None):
        """Run end-of-day analysis for simulation mode - PARALLELIZED VERSION."""
        sim_time = simulation_time_manager.current_time
        if not sim_time:
            return

        # Set EOD running flag at the start
        simulation_time_manager.is_eod_running = True
        await self._broadcast_status()

        # Default filters (same as live EOD)
        if filters is None:
            filters = {
                "min_change": 0.0,
                "min_relative_volume": 1.5,
                "min_volume": 50_000_000,
            }

        sim_date = sim_time.date()
        print(f"[SimScanner] Running PARALLEL EOD Analysis for {sim_date}")

        # Get BIST tickers dynamically - same as live EOD service
        tickers = await self._get_dynamic_tickers()
        total_tickers = len(tickers)
        print(
            f"[SimScanner] Analyzing {total_tickers} BIST stocks in batches of {EOD_BATCH_SIZE}"
        )

        # Broadcast EOD started
        if self._ws_manager:
            await self._ws_manager.broadcast(
                {
                    "type": "sim_eod_progress",
                    "data": {
                        "status": "started",
                        "current": 0,
                        "total": total_tickers,
                        "ticker": None,
                    },
                }
            )

        all_results = []
        errors = 0
        processed = 0
        start_time = datetime.now()

        # Process tickers in batches
        for batch_start in range(0, total_tickers, EOD_BATCH_SIZE):
            # Check if EOD was cancelled
            if not simulation_time_manager.is_eod_running:
                print("[SimScanner] EOD Analysis cancelled")
                if self._ws_manager:
                    await self._ws_manager.broadcast(
                        {
                            "type": "sim_eod_progress",
                            "data": {
                                "status": "cancelled",
                                "current": processed,
                                "total": total_tickers,
                                "ticker": None,
                            },
                        }
                    )
                    await self._broadcast_status()
                return

            batch_end = min(batch_start + EOD_BATCH_SIZE, total_tickers)
            batch_tickers = tickers[batch_start:batch_end]
            batch_num = (batch_start // EOD_BATCH_SIZE) + 1
            total_batches = (total_tickers + EOD_BATCH_SIZE - 1) // EOD_BATCH_SIZE

            # Broadcast progress
            if self._ws_manager:
                await self._ws_manager.broadcast(
                    {
                        "type": "sim_eod_progress",
                        "data": {
                            "status": "running",
                            "current": processed,
                            "total": total_tickers,
                            "ticker": f"Batch {batch_num}/{total_batches}",
                        },
                    }
                )

            # Fetch batch in parallel
            batch_results = await self._fetch_eod_batch(batch_tickers, sim_time)

            # Process results
            for ticker, data in batch_results:
                processed += 1

                if data is None or data.empty or len(data) < 2:
                    errors += 1
                    continue

                try:
                    today = data.iloc[-1]
                    prev = data.iloc[-2]

                    today_close = float(today["Close"])
                    today_open = float(today["Open"])
                    today_high = float(today["High"])
                    today_low = float(today["Low"])
                    today_volume = float(today["Volume"])
                    prev_close = float(prev["Close"])

                    # Calculate change
                    if prev_close > 0:
                        daily_change = ((today_close - prev_close) / prev_close) * 100
                    else:
                        daily_change = 0

                    # Calculate average volume (last 10 days)
                    vol_data = (
                        data["Volume"].iloc[-11:-1]
                        if len(data) > 10
                        else data["Volume"].iloc[:-1]
                    )
                    avg_volume = (
                        float(vol_data.mean()) if len(vol_data) > 0 else today_volume
                    )
                    relative_volume = today_volume / avg_volume if avg_volume > 0 else 0
                    volume_tl = today_volume * today_close

                    all_results.append(
                        {
                            "ticker": ticker,
                            "symbol": ticker.replace(".IS", ""),
                            "close": round(today_close, 2),
                            "open": round(today_open, 2),
                            "high": round(today_high, 2),
                            "low": round(today_low, 2),
                            "prev_close": round(prev_close, 2),
                            "change_percent": round(daily_change, 2),
                            "volume": int(today_volume),
                            "avg_volume": int(avg_volume),
                            "relative_volume": round(relative_volume, 2),
                            "volume_tl": round(volume_tl, 0),
                        }
                    )
                except Exception:
                    errors += 1
                    continue

            # Small delay between batches to be nice to the API
            await asyncio.sleep(0.3)

        # Apply filters
        filtered_results = [
            r
            for r in all_results
            if r["change_percent"] >= filters["min_change"]
            and r["relative_volume"] >= filters["min_relative_volume"]
            and r["volume"] >= filters["min_volume"]
        ]

        # Sort by change percent descending
        filtered_results.sort(key=lambda x: x["change_percent"], reverse=True)

        elapsed = (datetime.now() - start_time).total_seconds()
        print(
            f"[SimScanner] EOD Analysis complete in {elapsed:.1f}s: {len(all_results)} scanned, {len(filtered_results)} matched filters, {errors} errors"
        )

        # Broadcast EOD completion with results
        if self._ws_manager:
            await self._ws_manager.broadcast(
                {
                    "type": "sim_eod_progress",
                    "data": {
                        "status": "completed",
                        "current": total_tickers,
                        "total": total_tickers,
                        "ticker": None,
                    },
                }
            )
            await self._ws_manager.broadcast(
                {
                    "type": "sim_eod_complete",
                    "data": {
                        "date": sim_date.isoformat(),
                        "results_count": len(filtered_results),
                        "results": filtered_results,
                        "total_scanned": len(all_results),
                        "filters": filters,
                    },
                }
            )

        # Reset EOD running flag
        simulation_time_manager.is_eod_running = False
        # Broadcast updated status
        await self._broadcast_status()

    async def _get_dynamic_tickers(self):
        """
        Get BIST tickers dynamically - same logic as live EOD service.
        Tries to fetch from web, falls back to static list.
        """
        import asyncio

        try:
            import requests
            from bs4 import BeautifulSoup

            # Try to fetch from Borsa Istanbul
            url = "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/Temel-Degerler-Ve-Oranlar.aspx"
            headers = {"User-Agent": "Mozilla/5.0"}

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: requests.get(url, headers=headers, timeout=10)
            )

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                # Find ticker symbols in the table
                tickers = set()  # Use set to prevent duplicates

                # Look for table rows with ticker data
                for row in soup.select("table tbody tr"):
                    cells = row.select("td")
                    if cells and len(cells) > 0:
                        ticker_text = cells[0].get_text(strip=True)
                        if (
                            ticker_text
                            and len(ticker_text) >= 3
                            and ticker_text.isalpha()
                        ):
                            tickers.add(f"{ticker_text}.IS")

                if len(tickers) > 50:
                    print(
                        f"[SimScanner] Fetched {len(tickers)} unique tickers dynamically"
                    )
                    return list(tickers)

        except Exception as e:
            print(f"[SimScanner] Dynamic fetch failed: {e}, using static list")

        # Fallback to static list - also deduplicate
        from financia.bist100_tickers import get_bist_tickers

        return list(set(get_bist_tickers("all")))


# Global simulation scanner instance
simulation_scanner = SimulationScanner()
