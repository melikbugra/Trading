"""
Simulation Scanner service for replaying historical data.
Iterates through hourly bars and evaluates strategies as if in real-time.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional, Dict
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

# Thread pool for running blocking operations
_executor = ThreadPoolExecutor(max_workers=4)


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

    def set_ws_manager(self, manager):
        """Set WebSocket manager for broadcasting updates."""
        self._ws_manager = manager

    async def _broadcast_status(self):
        """Broadcast current simulation status to all connected clients."""
        if self._ws_manager:
            try:
                status = simulation_time_manager.get_status()
                await self._ws_manager.broadcast(
                    {
                        "type": "sim_status",
                        "data": status,
                    }
                )
            except Exception as e:
                print(f"[SimScanner] Failed to broadcast status: {e}")

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
                    {
                        "type": "sim_signals_update",
                        "data": signals_data,
                    }
                )
            except Exception as e:
                print(f"[SimScanner] Failed to broadcast signals: {e}")

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
        """Main simulation loop - advances time and scans."""
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

                # Perform scan at current simulation time
                await self._scan_all()

                # Wait for the configured interval (seconds_per_hour)
                wait_seconds = simulation_time_manager.seconds_per_hour
                await asyncio.sleep(wait_seconds)

                # Advance simulation time by 1 hour
                day_completed = simulation_time_manager.advance_hour()
                await self._broadcast_status()

                if day_completed:
                    print(
                        f"[SimScanner] Day completed: {simulation_time_manager.current_time}"
                    )
                    # Pause first, then run EOD
                    simulation_time_manager.pause()
                    await self._broadcast_status()

                    # Set EOD running flag and broadcast
                    simulation_time_manager.is_eod_running = True
                    await self._broadcast_status()

                    # Run EOD analysis for simulation
                    await self._run_sim_eod_analysis()

                    # EOD finished - clear flag and broadcast
                    simulation_time_manager.is_eod_running = False
                    await self._broadcast_status()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[SimScanner] Error in loop: {e}")
                import traceback

                traceback.print_exc()
                await asyncio.sleep(1)

    async def _scan_all(self):
        """Scan all active watchlist items at current simulation time."""
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

            print(
                f"[SimScanner] Scanning {len(watchlist)} items at {sim_time.strftime('%Y-%m-%d %H:%M')}"
            )

            for i, item in enumerate(watchlist):
                try:
                    await self._scan_ticker(db, item, sim_time)
                    # Small delay between tickers
                    if i < len(watchlist) - 1:
                        await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"[SimScanner] Error scanning {item.ticker}: {e}")
                    continue

            # Update last scan time
            config = db.query(SimScannerConfig).first()
            if not config:
                config = SimScannerConfig()
                db.add(config)
            config.last_scan_at = sim_time
            db.commit()

        except Exception as e:
            print(f"[SimScanner] Error in scan_all: {e}")
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

        # Fetch fresh data (with rate limiting)
        loop = asyncio.get_event_loop()

        def fetch_data():
            try:
                # Add delay for rate limiting
                import time

                time.sleep(0.5)

                # Calculate start date (need enough data for indicators)
                start_date = end_time - timedelta(days=365)  # 1 year of history

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

        # Case 1: Main condition met - new signal triggered
        if result.main_condition_met:
            if existing_signal and existing_signal.status == "triggered":
                # Already triggered, check price levels
                await self._check_entry_exit(db, existing_signal, result)
            elif existing_signal and existing_signal.status == "entered":
                # Already in position, update current price
                existing_signal.current_price = current_price
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
            elif existing_signal and existing_signal.status == "entered":
                existing_signal.current_price = current_price

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
            print(
                f"[SimScanner] Trade recorded: {signal.ticker} {result} {profit_percent:+.2f}%"
            )

        signal.notes = f"Closed by {reason} @ {exit_price}"
        db.commit()
        await self._broadcast_signals(db)

    async def _run_sim_eod_analysis(self, filters=None):
        """Run end-of-day analysis for simulation mode - analyzes all BIST stocks like live mode."""
        sim_time = simulation_time_manager.current_time
        if not sim_time:
            return

        # Default filters (same as live EOD)
        if filters is None:
            filters = {
                "min_change": 0.0,
                "min_relative_volume": 1.5,
                "min_volume": 50_000_000,
            }

        sim_date = sim_time.date()
        print(f"[SimScanner] Running EOD Analysis for {sim_date}")

        # Get BIST tickers dynamically - same as live EOD service
        tickers = await self._get_dynamic_tickers()
        total_tickers = len(tickers)
        print(f"[SimScanner] Analyzing {total_tickers} BIST stocks for EOD")

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

        all_results = []  # All results before filtering
        errors = 0

        for idx, ticker in enumerate(tickers):
            # Check if EOD was cancelled
            if not simulation_time_manager.is_eod_running:
                print("[SimScanner] EOD Analysis cancelled")
                # Broadcast cancellation
                if self._ws_manager:
                    await self._ws_manager.broadcast(
                        {
                            "type": "sim_eod_progress",
                            "data": {
                                "status": "cancelled",
                                "current": idx,
                                "total": total_tickers,
                                "ticker": None,
                            },
                        }
                    )
                    await self._broadcast_status()
                return

            try:
                # Broadcast progress every 10 tickers
                if idx % 10 == 0 and self._ws_manager:
                    await self._ws_manager.broadcast(
                        {
                            "type": "sim_eod_progress",
                            "data": {
                                "status": "running",
                                "current": idx + 1,
                                "total": total_tickers,
                                "ticker": ticker.replace(".IS", ""),
                            },
                        }
                    )

                # Get historical data up to sim_time
                data = await self._get_historical_data(
                    ticker=ticker,
                    market="bist100",
                    horizon="short",
                    end_time=sim_time,
                )

                if data.empty or len(data) < 2:
                    errors += 1
                    continue

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

        print(
            f"[SimScanner] EOD Analysis complete: {len(all_results)} scanned, {len(filtered_results)} matched filters, {errors} errors"
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
