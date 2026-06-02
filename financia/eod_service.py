"""
End of Day (EOD) Analysis Scheduler Service.
Runs automatically at BIST market close (18:15 Turkey time) and sends email summary.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np

from financia.notification_service import TelegramService
from financia.web_api.database import now_turkey


def score_daily(ticker: str, hist: pd.DataFrame, trend_filters: dict) -> Optional[Dict]:
    """
    Compute the daily TREND + REVERSAL scores and type for a ticker from a daily
    OHLCV DataFrame. Pure/as-of: pass `hist` already sliced to the desired cutoff
    (e.g. up to the previous day for a backtest). Returns the result dict, or None
    if there isn't enough data / volume is too low.

    Reused by both the live EOD analysis and the backtest's daily watchlist.
    """
    if hist is None or hist.empty or len(hist) < 30:
        return None

    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]
    volume = hist["Volume"]

    current_close = close.iloc[-1]
    current_volume = volume.iloc[-1]
    volume_tl = current_volume * current_close
    if volume_tl < trend_filters.get("min_volume_tl", 0):
        return None

    # RSI (14) — Wilder smoothing
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]

    # MACD (12/26/9)
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal
    macd_current, macd_prev = macd.iloc[-1], macd.iloc[-2]
    hist_current, hist_prev = histogram.iloc[-1], histogram.iloc[-2]

    # EMA 20/50
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema20_c, ema50_c = ema20.iloc[-1], ema50.iloc[-1]
    ema20_p, ema50_p = ema20.iloc[-2], ema50.iloc[-2]

    # ADX / DMI (index-aligned)
    tr = np.maximum(
        high - low, np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1)))
    )
    atr = tr.rolling(14).mean()
    plus_dm = pd.Series(
        np.where((high.diff() > low.diff().abs()) & (high.diff() > 0), high.diff(), 0),
        index=close.index,
    )
    minus_dm = pd.Series(
        np.where((low.diff().abs() > high.diff()) & (low.diff() < 0), low.diff().abs(), 0),
        index=close.index,
    )
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(14).mean()
    adx_c = adx.iloc[-1] if not np.isnan(adx.iloc[-1]) else 0
    plus_di_c = plus_di.iloc[-1] if not np.isnan(plus_di.iloc[-1]) else 0
    minus_di_c = minus_di.iloc[-1] if not np.isnan(minus_di.iloc[-1]) else 0

    # Volume trend + relative volume (today vs previous ~10 bars)
    vol_sma5 = volume.rolling(5).mean()
    vol_sma20 = volume.rolling(20).mean()
    vol_ratio = (
        vol_sma5.iloc[-1] / vol_sma20.iloc[-1] if vol_sma20.iloc[-1] > 0 else 1
    )
    price_up = close.iloc[-1] > close.iloc[-5]
    prev_vol = volume.iloc[-11:-1]
    avg_vol10 = prev_vol.mean() if len(prev_vol) > 0 else current_volume
    relative_volume = round(current_volume / avg_vol10, 2) if avg_vol10 > 0 else 0

    # Bollinger position
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper_band = sma20 + (2 * std20)
    lower_band = sma20 - (2 * std20)
    bb_position = (current_close - lower_band.iloc[-1]) / (
        upper_band.iloc[-1] - lower_band.iloc[-1]
    )

    # Stochastic %K (14)
    lowest_low = low.rolling(14).min()
    highest_high = high.rolling(14).max()
    stoch_k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    stoch_k_c, stoch_k_p = stoch_k.iloc[-1], stoch_k.iloc[-2]

    # EMA200 gate
    ema200 = close.ewm(
        span=200 if len(close) >= 200 else len(close), adjust=False
    ).mean()
    ema200_c = ema200.iloc[-1]
    above_ema200 = current_close > ema200_c
    price_vs_ema200 = (current_close - ema200_c) / ema200_c * 100

    # TREND score
    t = 0
    if macd_current > 0 and hist_current > hist_prev:
        t += 20
    elif macd_current > macd_prev:
        t += 14
    elif hist_current > hist_prev:
        t += 6
    if ema20_c > ema50_c:
        t += 20 if ema20_p <= ema50_p else 14
    if adx_c > 25 and plus_di_c > minus_di_c:
        t += 15
    elif adx_c > 20:
        t += 8
    if vol_ratio > 1.5 and price_up:
        t += 15
    elif vol_ratio > 1.2 and price_up:
        t += 10
    elif vol_ratio > 1.0:
        t += 5
    if above_ema200:
        t += 15 if price_vs_ema200 <= 5 else 10
    if 50 <= current_rsi <= 70:
        t += 15
    elif 40 <= current_rsi < 50:
        t += 8
    trend_score = int(t)

    # REVERSAL score (gated above EMA200)
    r = 0
    if above_ema200:
        if current_rsi < 30:
            r += 40
        elif current_rsi < 40:
            r += 25
        elif current_rsi < 45:
            r += 10
        if bb_position < 0.15:
            r += 25
        elif bb_position < 0.30:
            r += 15
        elif bb_position < 0.45:
            r += 5
        if stoch_k_c < 20:
            r += 20
        elif stoch_k_c > stoch_k_p and stoch_k_c < 30:
            r += 14
        elif stoch_k_c < 50:
            r += 6
        if hist_current > hist_prev:
            r += 15
    reversal_score = int(r)

    trend_min = trend_filters.get("trend_min", 60)
    reversal_min = trend_filters.get("reversal_min", 55)
    if trend_score >= trend_min and reversal_score >= 50:
        ttype = "both"
    elif trend_score >= trend_min:
        ttype = "trend"
    elif reversal_score >= reversal_min and above_ema200:
        ttype = "reversal"
    else:
        ttype = "neutral"

    prev_close = close.iloc[-2]
    daily_change = ((current_close - prev_close) / prev_close) * 100
    five_day_change = (
        ((current_close - close.iloc[-6]) / close.iloc[-6]) * 100
        if len(close) > 5
        else 0
    )

    return {
        "ticker": ticker,
        "symbol": ticker.replace(".IS", ""),
        "close": round(current_close, 2),
        "change_percent": round(daily_change, 2),
        "five_day_change": round(five_day_change, 2),
        "trend_score": trend_score,
        "reversal_score": reversal_score,
        "type": ttype,
        "volume_tl": round(volume_tl, 0),
        "relative_volume": relative_volume,
        "rsi": round(current_rsi, 1),
        "adx": round(adx_c, 1),
        "bb_position": round(bb_position * 100, 0),
        "scores": {"trend": trend_score, "reversal": reversal_score},
        "direction": "bullish"
        if ttype in ("trend", "both")
        else "reversal"
        if ttype == "reversal"
        else "neutral",
    }


class EODAnalysisService:
    """
    Service that runs end-of-day analysis at BIST market close.
    Supports two modes:
    1. Volume Analysis - finds high volume movers
    2. Trend Prediction - predicts next day trend using multiple indicators
    """

    def __init__(self):
        self.is_running = False
        self.is_analyzing = False  # True while analysis is in progress
        self.is_cancelled = False  # Flag to cancel ongoing analysis
        self.last_run_at: Optional[datetime] = None
        self.last_results: List[Dict] = []
        self.last_trend_results: List[Dict] = []  # Trend prediction results
        self.total_scanned: int = 0
        self.current_progress: int = 0  # Current ticker being processed
        self.current_ticker: str = ""  # Current ticker name
        self._task: Optional[asyncio.Task] = None
        self._analysis_task: Optional[asyncio.Task] = None
        self._ws_manager = None  # WebSocket manager reference
        # Default filters
        self.filters = {
            "min_change": 0.0,
            "min_relative_volume": 2.0,
            "min_volume": 100_000_000,
        }
        # Trend prediction filters
        self.trend_filters = {
            "min_trend_score": 60,  # Backward-compat alias (= trend_min)
            "trend_min": 60,  # Min TREND (continuation) score 0-100
            "reversal_min": 55,  # Min REVERSAL (bounce) score 0-100
            "min_volume_tl": 75_000_000,  # Min daily volume in TL (liquidity)
            "top_n": 20,  # Per-category cap when applying to watchlists
        }
        # Schedule time (18:15 Turkey time)
        self.run_hour = 18
        self.run_minute = 15

    def set_ws_manager(self, manager):
        """Set WebSocket manager for broadcasting updates."""
        self._ws_manager = manager

    def cancel_analysis(self):
        """Cancel ongoing analysis."""
        if self.is_analyzing:
            self.is_cancelled = True
            print("[EOD] Analysis cancellation requested")

    async def _broadcast_progress(
        self, current: int, total: int, ticker: str, status: str = "running"
    ):
        """Broadcast analysis progress to all connected clients."""
        if self._ws_manager:
            try:
                await self._ws_manager.broadcast(
                    {
                        "type": "eod_progress",
                        "data": {
                            "status": status,
                            "current": current,
                            "total": total,
                            "ticker": ticker.replace(".IS", "") if ticker else None,
                        },
                    }
                )
            except Exception as e:
                print(f"[EOD] Failed to broadcast progress: {e}")

    async def _broadcast_status(self):
        """Broadcast current EOD status to all connected clients."""
        if self._ws_manager:
            try:
                await self._ws_manager.broadcast(
                    {
                        "type": "eod_status",
                        "data": {
                            "is_analyzing": self.is_analyzing,
                            "last_run_at": self.last_run_at.isoformat()
                            if self.last_run_at
                            else None,
                            "total_scanned": self.total_scanned,
                            "results_count": len(self.last_results),
                            "results": self.last_results,
                            "filters": self.filters,
                            "trend_results_count": len(self.last_trend_results),
                            "trend_results": self.last_trend_results,
                            "trend_filters": self.trend_filters,
                        },
                    }
                )
            except Exception as e:
                print(f"[EOD] Failed to broadcast status: {e}")

    async def start(self):
        """Start the EOD scheduler."""
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._schedule_loop())
        print("[EOD] Scheduler started")

    async def stop(self):
        """Stop the EOD scheduler."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("[EOD] Scheduler stopped")

    async def _schedule_loop(self):
        """Main scheduling loop - waits until 18:15 each weekday."""
        while self.is_running:
            try:
                now = now_turkey()

                # Calculate next run time
                next_run = now.replace(
                    hour=self.run_hour, minute=self.run_minute, second=0, microsecond=0
                )

                # If we've passed today's run time, schedule for tomorrow
                if now >= next_run:
                    next_run += timedelta(days=1)

                # Skip weekends (Saturday=5, Sunday=6)
                while next_run.weekday() >= 5:
                    next_run += timedelta(days=1)

                wait_seconds = (next_run - now).total_seconds()
                print(
                    f"[EOD] Next analysis scheduled at {next_run.strftime('%Y-%m-%d %H:%M')} (in {wait_seconds / 3600:.1f} hours)"
                )

                # Wait until scheduled time
                await asyncio.sleep(wait_seconds)

                # Run both analyses (volume + trend) for next-day prep
                await self.run_combined()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[EOD] Error in schedule loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def start_analysis(self, send_email: bool = False):
        """Start analysis in background (non-blocking)."""
        if self.is_analyzing:
            return {"status": "already_running"}

        # Cancel previous task if exists
        if self._analysis_task and not self._analysis_task.done():
            self._analysis_task.cancel()

        self._analysis_task = asyncio.create_task(
            self.run_analysis(send_email=send_email)
        )
        return {"status": "started"}

    async def run_combined(self):
        """
        Run volume analysis then trend analysis sequentially (they share the
        is_analyzing lock so cannot run concurrently). Telegram summary is sent
        once, from the trend step.
        """
        await self.run_analysis(send_email=False)
        await self.run_trend_analysis(send_email=True)

    async def start_combined(self):
        """Start the combined (volume + trend) analysis in the background."""
        if self.is_analyzing:
            return {"status": "already_running"}
        if self._analysis_task and not self._analysis_task.done():
            self._analysis_task.cancel()
        self._analysis_task = asyncio.create_task(self.run_combined())
        return {"status": "started"}

    async def run_analysis(self, send_email: bool = True) -> Dict:
        """Run the EOD analysis and optionally send email summary."""
        import yfinance as yf
        import time

        if self.is_analyzing:
            return {
                "count": len(self.last_results),
                "total_scanned": self.total_scanned,
                "results": self.last_results,
                "status": "already_running",
            }

        self.is_analyzing = True
        self.is_cancelled = False
        self.current_progress = 0
        self.current_ticker = ""
        await self._broadcast_status()  # Notify clients analysis started
        await self._broadcast_progress(0, 0, None, "started")

        try:
            print(f"[EOD] Starting analysis at {now_turkey().strftime('%H:%M:%S')}")

            # Dynamically fetch BIST tickers from yfinance
            tickers = await self._get_dynamic_tickers()
            total_tickers = len(tickers)

            results = []
            errors = []
            processed = 0

            def analyze_ticker(ticker: str) -> Optional[Dict]:
                try:
                    time.sleep(0.1)  # Small delay for rate limiting
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="30d", interval="1d")

                    if hist.empty or len(hist) < 5:
                        return None

                    today = hist.iloc[-1]
                    today_open = today["Open"]
                    today_close = today["Close"]
                    today_high = today["High"]
                    today_low = today["Low"]
                    today_volume = today["Volume"]

                    # Get previous day's close for proper change calculation
                    prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else today_open

                    # Calculate daily change % (previous close → current close, like TradingView)
                    if prev_close > 0:
                        daily_change = ((today_close - prev_close) / prev_close) * 100
                    else:
                        daily_change = 0

                    # Calculate average volume (last 10 days, excluding today)
                    vol_data = (
                        hist["Volume"].iloc[-11:-1]
                        if len(hist) > 10
                        else hist["Volume"].iloc[:-1]
                    )
                    avg_volume = vol_data.mean() if len(vol_data) > 0 else today_volume
                    relative_volume = today_volume / avg_volume if avg_volume > 0 else 0

                    # Calculate volume in TL (approximate)
                    volume_tl = today_volume * today_close

                    return {
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
                except Exception as e:
                    return {"ticker": ticker, "error": str(e)}

            # Run analysis in parallel with progress tracking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=15) as executor:
                futures = {executor.submit(analyze_ticker, t): t for t in tickers}

                for future in as_completed(futures):
                    # Check for cancellation
                    if self.is_cancelled:
                        print("[EOD] Analysis cancelled")
                        await self._broadcast_progress(
                            processed, total_tickers, None, "cancelled"
                        )
                        return {
                            "count": len(results),
                            "total_scanned": processed,
                            "results": results,
                            "status": "cancelled",
                        }

                    ticker = futures[future]
                    processed += 1
                    self.current_progress = processed
                    self.current_ticker = ticker

                    # Broadcast progress every 10 tickers
                    if processed % 10 == 0 or processed == total_tickers:
                        await self._broadcast_progress(processed, total_tickers, ticker)

                    result = future.result()
                    if result:
                        if "error" in result:
                            errors.append(result)
                        else:
                            # Apply filters
                            if (
                                result["change_percent"] >= self.filters["min_change"]
                                and result["relative_volume"]
                                >= self.filters["min_relative_volume"]
                                and result["volume"] >= self.filters["min_volume"]
                            ):
                                results.append(result)

            # Sort by change_percent descending
            results.sort(key=lambda x: x["change_percent"], reverse=True)

            self.last_run_at = now_turkey()
            self.last_results = results
            self.total_scanned = len(tickers)

            print(
                f"[EOD] Analysis complete: {len(results)} stocks found from {len(tickers)} scanned"
            )
            await self._broadcast_progress(
                total_tickers, total_tickers, None, "completed"
            )

            # Send email summary (only if enabled)
            if send_email:
                await self._send_email_summary(results, len(tickers), len(errors))

            return {
                "count": len(results),
                "total_scanned": len(tickers),
                "results": results,
                "status": "completed",
            }
        except Exception as e:
            print(f"[EOD] Analysis error: {e}")
            return {
                "count": 0,
                "total_scanned": 0,
                "results": [],
                "status": "error",
                "error": str(e),
            }
        finally:
            self.is_analyzing = False
            await self._broadcast_status()  # Notify clients analysis finished

    async def _get_dynamic_tickers(self) -> List[str]:
        """
        Get BIST tickers dynamically.
        Tries to fetch from web, falls back to static list.
        """
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
                    print(f"[EOD] Fetched {len(tickers)} unique tickers dynamically")
                    return list(tickers)

        except Exception as e:
            print(f"[EOD] Dynamic fetch failed: {e}, using static list")

        # Fallback to static list - also deduplicate
        from financia.bist100_tickers import get_bist_tickers

        return list(set(get_bist_tickers("all")))

    async def _send_email_summary(
        self, results: List[Dict], total_scanned: int, error_count: int
    ):
        """Send email summary of EOD analysis."""
        if not results:
            return

        now = now_turkey()
        date_str = now.strftime("%d.%m.%Y")

        # Build email body
        subject = f"📊 BIST Gün Sonu Raporu - {date_str} ({len(results)} hisse)"

        body = f"""
BIST GÜN SONU ANALİZ RAPORU
{"=" * 50}
Tarih: {date_str}
Saat: {now.strftime("%H:%M")}
Taranan: {total_scanned} hisse
Bulunan: {len(results)} hisse (filtrelere uyan)

FİLTRELER:
- Min. Değişim: %{self.filters["min_change"]}
- Min. Bağıl Hacim: {self.filters["min_relative_volume"]}x
- Min. Hacim: {self.filters["min_volume"]:,} lot

{"=" * 50}
EN ÇOK YÜKSELENLER
{"=" * 50}
"""

        # Top 10 gainers
        top_gainers = results[:10]
        for i, stock in enumerate(top_gainers, 1):
            body += f"""
{i}. {stock["symbol"]}
   Kapanış: ₺{stock["close"]:.2f} ({stock["change_percent"]:+.2f}%)
   Bağıl Hacim: {stock["relative_volume"]:.1f}x
   Hacim: {self._format_volume(stock.get("volume_tl", stock["volume"]))}
"""

        # High volume stocks (sorted by relative volume)
        high_volume = sorted(results, key=lambda x: x["relative_volume"], reverse=True)[
            :5
        ]

        body += f"""
{"=" * 50}
EN YÜKSEK BAĞIL HACİM
{"=" * 50}
"""
        for i, stock in enumerate(high_volume, 1):
            body += f"{i}. {stock['symbol']}: {stock['relative_volume']:.1f}x hacim, {stock['change_percent']:+.2f}%\n"

        body += f"""
{"=" * 50}
Dashboard: http://localhost:5173

Bu rapor otomatik olarak oluşturulmuştur.
"""

        TelegramService.send_message(subject, body)
        print(f"[EOD] Telegram summary sent")

    def _format_volume(self, vol: float) -> str:
        """Format volume for display."""
        if vol >= 1_000_000_000:
            return f"{vol / 1_000_000_000:.1f}B TL"
        if vol >= 1_000_000:
            return f"{vol / 1_000_000:.1f}M TL"
        if vol >= 1_000:
            return f"{vol / 1_000:.1f}K TL"
        return f"{vol:.0f} TL"

    async def start_trend_analysis(self):
        """Start trend prediction analysis in background (non-blocking)."""
        if self.is_analyzing:
            return {"status": "already_running"}

        if self._analysis_task and not self._analysis_task.done():
            self._analysis_task.cancel()

        self._analysis_task = asyncio.create_task(self.run_trend_analysis())
        return {"status": "started"}

    async def run_trend_analysis(self, send_email: bool = False) -> Dict:
        """
        Run trend prediction analysis using daily candles.
        Calculates a trend score (0-100) for each stock based on multiple indicators.
        Higher score = stronger bullish potential for next day.
        """
        import yfinance as yf
        import numpy as np

        if self.is_analyzing:
            return {
                "count": len(self.last_trend_results),
                "total_scanned": self.total_scanned,
                "results": self.last_trend_results,
                "status": "already_running",
            }

        self.is_analyzing = True
        await self._broadcast_status()

        try:
            print(
                f"[EOD-Trend] Starting trend prediction at {now_turkey().strftime('%H:%M:%S')}"
            )

            tickers = await self._get_dynamic_tickers()
            results = []
            errors = []

            def calculate_trend_score(ticker: str) -> Optional[Dict]:
                """Fetch daily candles and score (delegates to module score_daily)."""
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="60d", interval="1d")
                    return score_daily(ticker, hist, self.trend_filters)
                except Exception as e:
                    return {"ticker": ticker, "error": str(e)}

            # Run analysis in parallel
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {
                    executor.submit(calculate_trend_score, t): t for t in tickers
                }

                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        if "error" in result:
                            errors.append(result)
                        elif result.get("type", "neutral") != "neutral":
                            results.append(result)

            # Sort by the best of the two scores (descending)
            results.sort(
                key=lambda x: max(
                    x.get("trend_score", 0), x.get("reversal_score", 0)
                ),
                reverse=True,
            )

            self.last_run_at = now_turkey()
            self.last_trend_results = results
            self.total_scanned = len(tickers)

            print(
                f"[EOD-Trend] Analysis complete: {len(results)} stocks with score >= {self.trend_filters.get('min_trend_score', 0)} from {len(tickers)} scanned"
            )

            # Send email summary if enabled
            if send_email and results:
                await self._send_trend_email_summary(results, len(tickers))

            return {
                "count": len(results),
                "total_scanned": len(tickers),
                "results": results,
                "status": "completed",
            }
        except Exception as e:
            print(f"[EOD-Trend] Analysis error: {e}")
            import traceback

            traceback.print_exc()
            return {
                "count": 0,
                "total_scanned": 0,
                "results": [],
                "status": "error",
                "error": str(e),
            }
        finally:
            self.is_analyzing = False
            await self._broadcast_status()

    async def _send_trend_email_summary(self, results: List[Dict], total_scanned: int):
        """Send email summary of trend prediction analysis."""
        if not results:
            return

        now = now_turkey()
        date_str = now.strftime("%d.%m.%Y")

        trend_list = [s for s in results if s.get("type") in ("trend", "both")]
        reversal_list = [s for s in results if s.get("type") in ("reversal", "both")]
        trend_list.sort(key=lambda x: x.get("trend_score", 0), reverse=True)
        reversal_list.sort(key=lambda x: x.get("reversal_score", 0), reverse=True)

        subject = (
            f"🎯 BIST Yarın İçin Adaylar - {date_str} "
            f"({len(trend_list)} trend / {len(reversal_list)} toparlanma)"
        )

        def fmt(stock, score_key, label):
            return (
                f"{stock['symbol']} — {label} {stock[score_key]}/100 | "
                f"₺{stock['close']:.2f} ({stock['change_percent']:+.2f}%) | "
                f"RSI {stock['rsi']:.0f} ADX {stock['adx']:.0f} BB %{stock['bb_position']:.0f}"
            )

        body = (
            f"BIST YARIN İÇİN ADAYLAR — {date_str} {now.strftime('%H:%M')}\n"
            f"Taranan: {total_scanned} hisse\n\n"
            f"📈 TREND (devam/kırılım) — {len(trend_list)} hisse\n"
        )
        if trend_list:
            for i, s in enumerate(trend_list[:15], 1):
                body += f"{i}. {fmt(s, 'trend_score', 'Trend')}\n"
        else:
            body += "   (yok)\n"

        body += f"\n🔄 TOPARLANMA (dip dönüşü, EMA200 üstü) — {len(reversal_list)} hisse\n"
        if reversal_list:
            for i, s in enumerate(reversal_list[:15], 1):
                body += f"{i}. {fmt(s, 'reversal_score', 'Bounce')}\n"
        else:
            body += "   (yok)\n"

        body += (
            "\nNOT: Sadece teknik analiz. Trend listesi → kırılım stratejileri, "
            "toparlanma listesi → VWAP için adaydır. Kendi araştırmanı yap."
        )

        TelegramService.send_message(subject, body)
        print(f"[EOD-Trend] Telegram summary sent")


# Global EOD service instance
eod_service = EODAnalysisService()
