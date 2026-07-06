"""
Market registry.

A single place that describes each tradeable market: its timezone, session
hours, currency, liquidity threshold and ticker universe. Used by the live
scanner (session gating), the backtest (session clock + ticker source) and the
EOD analysis (per-market liquidity filter).

BIST data from Yahoo is ~15 min delayed; US (NYSE/Nasdaq) is real-time. We run
the backtest/sim clock in *each market's own timezone* so US DST never has to be
reconciled against Turkey time — tz-aware timestamp comparisons handle the rest.
"""

from datetime import time as dtime, datetime
from typing import Optional

import pytz


def _bist_tickers() -> list:
    from financia.bist100_tickers import get_bist_tickers

    return get_bist_tickers("all")


def _us_tickers() -> list:
    from financia.us_tickers import get_us_tickers

    return get_us_tickers("100")


MARKET_CONFIG = {
    "bist": {
        "label": "BIST",
        "tz": pytz.timezone("Europe/Istanbul"),
        # Backtest/sim session: first bar at 09:30, day done when hour >= 18.
        "session_start": dtime(9, 30),
        "session_end_hour": 18,
        # Live gating window (with the historical +-30m buffer around 10:00-18:00).
        "live_open": dtime(9, 30),
        "live_close": dtime(18, 30),
        "currency": "TL",
        "currency_symbol": "₺",
        # Min daily turnover (price * volume) in local currency for EOD liquidity.
        "min_volume": 75_000_000,
        # Flat broker commission per order. Midas is commission-free on BIST.
        "trade_fee": 0.0,
        "tickers": _bist_tickers,
        "data_delayed": True,
        "data_delay_minutes": 15,  # Yahoo BIST feed lags ~15 min behind real-time
    },
    "us": {
        "label": "ABD (S&P 100)",
        "tz": pytz.timezone("America/New_York"),
        # US regular session 09:30-16:00 ET.
        "session_start": dtime(9, 30),
        "session_end_hour": 16,
        "live_open": dtime(9, 30),
        "live_close": dtime(16, 0),
        "currency": "USD",
        "currency_symbol": "$",
        # Min daily dollar volume. S&P 100 names all clear this easily.
        "min_volume": 50_000_000,
        # Midas charges a flat ~$1.50 per order on US trades.
        "trade_fee": 1.5,
        "tickers": _us_tickers,
        "data_delayed": False,
        "data_delay_minutes": 0,  # US (NYSE/Nasdaq) feed is real-time
    },
}

# Backward-compatible market id aliases (legacy watchlist/sim items use "bist100").
_ALIASES = {"bist100": "bist", "sp100": "us", "nasdaq": "us", "nyse": "us"}

DEFAULT_MARKET = "bist"


def normalize_market(market: Optional[str]) -> str:
    """Map any legacy/alias market id to a canonical key in MARKET_CONFIG."""
    if not market:
        return DEFAULT_MARKET
    m = market.lower()
    m = _ALIASES.get(m, m)
    return m if m in MARKET_CONFIG else DEFAULT_MARKET


def get_market_config(market: str) -> dict:
    return MARKET_CONFIG[normalize_market(market)]


def get_market_tickers(market: str) -> list:
    return get_market_config(market)["tickers"]()


def infer_market(ticker: str) -> str:
    """Guess the market from a ticker symbol (.IS suffix => BIST, else US)."""
    return "bist" if ticker.upper().endswith(".IS") else "us"


def is_market_open(market: str, now: Optional[datetime] = None) -> bool:
    """
    True if the market's regular session is currently open (DST-correct).

    `now` may be naive or tz-aware; it is converted into the market's own
    timezone before the weekday/time check.
    """
    cfg = get_market_config(market)
    tz = cfg["tz"]
    if now is None:
        now = datetime.now(tz)
    elif now.tzinfo is None:
        now = tz.localize(now)
    local = now.astimezone(tz)
    if local.weekday() >= 5:  # Sat/Sun
        return False
    return cfg["live_open"] <= local.time() <= cfg["live_close"]
