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

# Popular US growth / small-mid-cap names that retail investors track and that
# are generally tradeable on Midas. High-growth themes (space, EV, fintech,
# AI/semis, biotech, quantum, nuclear, consumer) often missed by the S&P 100 —
# e.g. LUNR, RKLB, ASTS.
GROWTH_TICKERS = [
    # Space & defense-tech
    "RKLB", "ASTS", "LUNR", "RDW", "PL", "BKSY", "ACHR", "JOBY", "KTOS", "AVAV",
    # EV / mobility
    "RIVN", "LCID", "NIO", "XPEV", "LI", "CHPT", "QS",
    # Fintech / crypto-adjacent
    "SOFI", "AFRM", "UPST", "HOOD", "COIN", "NU", "MSTR", "MARA", "RIOT", "CLSK", "XYZ",
    # AI / software / semis (growth)
    "PLTR", "SMCI", "ARM", "MRVL", "MU", "ON", "WOLF", "AI", "BBAI", "SOUN",
    "PATH", "SNOW", "NET", "DDOG", "CRWD", "ZS", "PANW", "MDB", "S", "GTLB",
    "ESTC", "CFLT", "U", "RBLX", "NOW", "ANET", "VRT", "DELL", "TSM", "ASML",
    "IONQ", "RGTI", "QBTS",
    # Energy / clean / nuclear
    "ENPH", "FSLR", "RUN", "PLUG", "BE", "SHLS", "OKLO", "SMR", "CEG", "VST", "GEV",
    # Biotech / health
    "MRNA", "BNTX", "CRSP", "NTLA", "BEAM", "RXRX", "HIMS", "TDOC", "VKTX", "TEM",
    "RVMD", "INSM", "NTRA", "EXAS", "ALNY", "TGTX",
    # Consumer / internet growth
    "SHOP", "SE", "MELI", "ABNB", "UBER", "LYFT", "DASH", "CPNG", "GRAB", "RDDT",
    "PINS", "SNAP", "SPOT", "ROKU", "TTD", "DKNG", "CELH", "ELF", "DUOL", "CAVA",
    "SG", "WING", "CROX", "DECK", "ONON", "GME",
]

# Deduplicate + stable sort
US_ALL_TICKERS = sorted(set(SP100_TICKERS))
US_EXT_TICKERS = sorted(set(SP100_TICKERS) | set(GROWTH_TICKERS))


def get_us_tickers(index: str = "100") -> list:
    """
    Get US ticker list.

    Args:
        index: "100" for S&P 100 (large caps), "ext" for S&P 100 + popular
               growth / small-mid-cap names.

    Returns:
        List of ticker symbols in Yahoo Finance format.
    """
    if index == "ext":
        return US_EXT_TICKERS
    return US_ALL_TICKERS
