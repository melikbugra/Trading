"""
US Ticker Lists (Yahoo Finance format)

S&P 100 (OEX) constituents — the largest, most liquid US large-caps. These are
the names almost all available on Midas, suitable for intraday long-only trading
with real-time (non-delayed) Yahoo data. Yahoo uses '-' instead of '.' for share
classes (e.g. BRK.B -> BRK-B).
"""

# S&P 100 — large, liquid US names tradeable on Midas
SP100_TICKERS = [
    "AAPL", "ABBV", "ABT", "ACN", "ADBE", "AIG", "AMD", "AMGN", "AMT", "AMZN",
    "AVGO", "AXP", "BA", "BAC", "BK", "BKNG", "BLK", "BMY", "BRK-B", "C",
    "CAT", "CHTR", "CL", "CMCSA", "COF", "COP", "COST", "CRM", "CSCO", "CVS",
    "CVX", "DE", "DHR", "DIS", "DOW", "DUK", "EMR", "F", "FDX", "GD",
    "GE", "GILD", "GM", "GOOG", "GOOGL", "GS", "HD", "HON", "IBM", "INTC",
    "INTU", "JNJ", "JPM", "KHC", "KO", "LIN", "LLY", "LMT", "LOW", "MA",
    "MCD", "MDLZ", "MDT", "MET", "META", "MMM", "MO", "MRK", "MS", "MSFT",
    "NEE", "NFLX", "NKE", "NVDA", "ORCL", "PEP", "PFE", "PG", "PM", "PYPL",
    "QCOM", "RTX", "SBUX", "SCHW", "SO", "SPG", "T", "TGT", "TMO", "TMUS",
    "TSLA", "TXN", "UNH", "UNP", "UPS", "USB", "V", "VZ", "WFC", "WMT",
    "XOM",
]

# Deduplicate + stable sort
US_ALL_TICKERS = sorted(set(SP100_TICKERS))


def get_us_tickers(index: str = "100") -> list:
    """
    Get US ticker list.

    Args:
        index: "100" for S&P 100 (currently the only list).

    Returns:
        List of ticker symbols in Yahoo Finance format.
    """
    return US_ALL_TICKERS
