"""
End of Day (EOD) Analysis Scheduler Service.
Runs automatically at BIST market close (18:15 Turkey time) and sends email summary.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from financia.notification_service import EmailService
from financia.web_api.database import now_turkey


class EODAnalysisService:
    """
    Service that runs end-of-day analysis at BIST market close.
    """

    def __init__(self):
        self.is_running = False
        self.is_analyzing = False  # True while analysis is in progress
        self.last_run_at: Optional[datetime] = None
        self.last_results: List[Dict] = []
        self.total_scanned: int = 0
        self._task: Optional[asyncio.Task] = None
        self._analysis_task: Optional[asyncio.Task] = None
        self._ws_manager = None  # WebSocket manager reference
        # Default filters
        self.filters = {
            "min_change": 0.0,
            "min_relative_volume": 2.0,
            "min_volume": 100_000_000,
        }
        # Schedule time (18:15 Turkey time)
        self.run_hour = 18
        self.run_minute = 15

    def set_ws_manager(self, manager):
        """Set WebSocket manager for broadcasting updates."""
        self._ws_manager = manager

    async def _broadcast_status(self):
        """Broadcast current EOD status to all connected clients."""
        if self._ws_manager:
            try:
                await self._ws_manager.broadcast({
                    "type": "eod_status",
                    "data": {
                        "is_analyzing": self.is_analyzing,
                        "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
                        "total_scanned": self.total_scanned,
                        "results_count": len(self.last_results),
                        "results": self.last_results,
                        "filters": self.filters,
                    }
                })
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
                next_run = now.replace(hour=self.run_hour, minute=self.run_minute, second=0, microsecond=0)
                
                # If we've passed today's run time, schedule for tomorrow
                if now >= next_run:
                    next_run += timedelta(days=1)
                
                # Skip weekends (Saturday=5, Sunday=6)
                while next_run.weekday() >= 5:
                    next_run += timedelta(days=1)
                
                wait_seconds = (next_run - now).total_seconds()
                print(f"[EOD] Next analysis scheduled at {next_run.strftime('%Y-%m-%d %H:%M')} (in {wait_seconds/3600:.1f} hours)")
                
                # Wait until scheduled time
                await asyncio.sleep(wait_seconds)
                
                # Run the analysis
                await self.run_analysis()
                
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

        self._analysis_task = asyncio.create_task(self.run_analysis(send_email=send_email))
        return {"status": "started"}

    async def run_analysis(self, send_email: bool = True) -> Dict:
        """Run the EOD analysis and optionally send email summary."""
        import yfinance as yf

        if self.is_analyzing:
            return {
                "count": len(self.last_results),
                "total_scanned": self.total_scanned,
                "results": self.last_results,
                "status": "already_running"
            }

        self.is_analyzing = True
        await self._broadcast_status()  # Notify clients analysis started
        try:
            print(f"[EOD] Starting analysis at {now_turkey().strftime('%H:%M:%S')}")

            # Dynamically fetch BIST tickers from yfinance
            tickers = await self._get_dynamic_tickers()

            results = []
            errors = []

            def analyze_ticker(ticker: str) -> Optional[Dict]:
                try:
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
                    vol_data = hist["Volume"].iloc[-11:-1] if len(hist) > 10 else hist["Volume"].iloc[:-1]
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

            # Run analysis in parallel
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(analyze_ticker, t): t for t in tickers}

                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        if "error" in result:
                            errors.append(result)
                        else:
                            # Apply filters
                            if (result["change_percent"] >= self.filters["min_change"] and
                                result["relative_volume"] >= self.filters["min_relative_volume"] and
                                result["volume"] >= self.filters["min_volume"]):
                                results.append(result)

            # Sort by change_percent descending
            results.sort(key=lambda x: x["change_percent"], reverse=True)

            self.last_run_at = now_turkey()
            self.last_results = results
            self.total_scanned = len(tickers)

            print(f"[EOD] Analysis complete: {len(results)} stocks found from {len(tickers)} scanned")

            # Send email summary (only if enabled)
            if send_email:
                await self._send_email_summary(results, len(tickers), len(errors))

            return {
                "count": len(results),
                "total_scanned": len(tickers),
                "results": results,
                "status": "completed"
            }
        except Exception as e:
            print(f"[EOD] Analysis error: {e}")
            return {
                "count": 0,
                "total_scanned": 0,
                "results": [],
                "status": "error",
                "error": str(e)
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
                None, 
                lambda: requests.get(url, headers=headers, timeout=10)
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Find ticker symbols in the table
                tickers = set()  # Use set to prevent duplicates
                
                # Look for table rows with ticker data
                for row in soup.select('table tbody tr'):
                    cells = row.select('td')
                    if cells and len(cells) > 0:
                        ticker_text = cells[0].get_text(strip=True)
                        if ticker_text and len(ticker_text) >= 3 and ticker_text.isalpha():
                            tickers.add(f"{ticker_text}.IS")
                
                if len(tickers) > 50:
                    print(f"[EOD] Fetched {len(tickers)} unique tickers dynamically")
                    return list(tickers)
            
        except Exception as e:
            print(f"[EOD] Dynamic fetch failed: {e}, using static list")
        
        # Fallback to static list - also deduplicate
        from financia.bist100_tickers import get_bist_tickers
        return list(set(get_bist_tickers("all")))

    async def _send_email_summary(self, results: List[Dict], total_scanned: int, error_count: int):
        """Send email summary of EOD analysis."""
        if not results:
            return
        
        now = now_turkey()
        date_str = now.strftime("%d.%m.%Y")
        
        # Build email body
        subject = f"📊 BIST Gün Sonu Raporu - {date_str} ({len(results)} hisse)"
        
        body = f"""
BIST GÜN SONU ANALİZ RAPORU
{'=' * 50}
Tarih: {date_str}
Saat: {now.strftime('%H:%M')}
Taranan: {total_scanned} hisse
Bulunan: {len(results)} hisse (filtrelere uyan)

FİLTRELER:
- Min. Değişim: %{self.filters['min_change']}
- Min. Bağıl Hacim: {self.filters['min_relative_volume']}x
- Min. Hacim: {self.filters['min_volume']:,} lot

{'=' * 50}
EN ÇOK YÜKSELENLER
{'=' * 50}
"""
        
        # Top 10 gainers
        top_gainers = results[:10]
        for i, stock in enumerate(top_gainers, 1):
            body += f"""
{i}. {stock['symbol']}
   Kapanış: ₺{stock['close']:.2f} ({stock['change_percent']:+.2f}%)
   Bağıl Hacim: {stock['relative_volume']:.1f}x
   Hacim: {self._format_volume(stock.get('volume_tl', stock['volume']))}
"""
        
        # High volume stocks (sorted by relative volume)
        high_volume = sorted(results, key=lambda x: x['relative_volume'], reverse=True)[:5]
        
        body += f"""
{'=' * 50}
EN YÜKSEK BAĞIL HACİM
{'=' * 50}
"""
        for i, stock in enumerate(high_volume, 1):
            body += f"{i}. {stock['symbol']}: {stock['relative_volume']:.1f}x hacim, {stock['change_percent']:+.2f}%\n"
        
        body += f"""
{'=' * 50}
Dashboard: http://localhost:5173

Bu rapor otomatik olarak oluşturulmuştur.
"""
        
        EmailService.send_email(subject, body)
        print(f"[EOD] Email summary sent")

    def _format_volume(self, vol: float) -> str:
        """Format volume for display."""
        if vol >= 1_000_000_000:
            return f"{vol / 1_000_000_000:.1f}B TL"
        if vol >= 1_000_000:
            return f"{vol / 1_000_000:.1f}M TL"
        if vol >= 1_000:
            return f"{vol / 1_000:.1f}K TL"
        return f"{vol:.0f} TL"


# Global EOD service instance
eod_service = EODAnalysisService()
