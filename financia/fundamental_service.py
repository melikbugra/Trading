"""
Fundamental analysis service for the long-term investing sub-app.

Pulls fundamentals + financial statements from yfinance for a single ticker,
applies any manual overrides, and produces two transparent 0-100 scores
(dividend & growth) plus an overall score and a label. Long-term fundamentals
change slowly, so callers should cache results (see FundamentalSnapshot).

yfinance unit notes (observed on the installed version):
- info["dividendYield"]  -> already a PERCENT (e.g. AAPL 0.36, GARAN.IS 4.07)
- info["returnOnEquity"], ["profitMargins"], ["revenueGrowth"],
  ["earningsGrowth"], ["payoutRatio"] -> FRACTIONS (0.166 == 16.6%)
- info["debtToEquity"] -> already a ratio number (79.5 == 79.5%); None for banks
"""

import logging
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

from financia.markets import infer_market, normalize_market, get_market_config

# yfinance logs noisy per-ticker errors (404 / "possibly delisted; no timezone
# found") for stale BIST symbols. These are handled gracefully below, so quiet
# the logger to keep the scan output clean.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


# Numeric fundamental fields the user can manually override (BIST yfinance gaps).
OVERRIDABLE_FIELDS = [
    "dividend_yield",
    "trailing_pe",
    "forward_pe",
    "price_to_book",
    "roe",
    "debt_to_equity",
    "profit_margin",
    "revenue_growth",
    "earnings_growth",
    "payout_ratio",
]

# Text fields the user can override (e.g. assign a custom sector/category).
STRING_OVERRIDABLE_FIELDS = ["sector", "industry"]

# All overridable keys (numeric + string).
ALL_OVERRIDABLE_FIELDS = OVERRIDABLE_FIELDS + STRING_OVERRIDABLE_FIELDS


def _df_to_json(df: Optional[pd.DataFrame], max_years: int = 4) -> dict:
    """Convert a yfinance financial-statement DataFrame to JSON-safe nested dict.

    Output shape: {row_label: {year_str: float|None}}, most-recent years first.
    """
    if df is None or not hasattr(df, "empty") or df.empty:
        return {}
    cols = list(df.columns)[:max_years]
    out: dict = {}
    for idx in df.index:
        row: dict = {}
        for c in cols:
            try:
                v = df.loc[idx, c]
            except Exception:
                v = None
            year = str(getattr(c, "year", c))
            row[year] = None if v is None or pd.isna(v) else float(v)
        out[str(idx)] = row
    return out


def _safe(info: dict, key: str):
    v = info.get(key)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    # yfinance occasionally returns "Infinity" sentinels
    if f != f or abs(f) == float("inf"):
        return None
    return f


def fetch_fundamentals(ticker: str, include_statements: bool = True) -> dict:
    """Fetch fundamentals (+ optionally financial statements) for one ticker.

    Returns a dict with normalized display-unit metrics (percent where natural),
    annual financial statements (~4y), recent dividends and the upcoming
    dividend/earnings calendar. Missing pieces come back as None/empty rather
    than raising (BIST coverage is incomplete).

    `include_statements=False` skips the slow statement/dividend/calendar calls
    and fetches only `.info` — used by the bulk screener, since the scores only
    depend on the ratio metrics, not the statements.
    """
    market = infer_market(ticker)
    cfg = get_market_config(market)

    result = {
        "ticker": ticker,
        "market": market,
        "currency": cfg["currency_symbol"],
        "name": ticker,
        "price": None,
        "market_cap": None,
        "metrics": {},
        "financials": {"income": {}, "balance": {}, "cashflow": {}},
        "dividends": [],
        "calendar": {},
        "fetched_at": datetime.utcnow().isoformat(),
        "error": None,
        "valid": False,  # set True once we confirm usable data exists
    }

    try:
        tk = yf.Ticker(ticker)
    except Exception as e:  # pragma: no cover - constructor rarely fails
        result["error"] = str(e)
        return result

    # --- info / ratios ---
    try:
        info = tk.info or {}
    except Exception as e:
        info = {}
        result["error"] = str(e)

    result["name"] = info.get("longName") or info.get("shortName") or ticker
    result["price"] = _safe(info, "currentPrice") or _safe(info, "regularMarketPrice")
    result["market_cap"] = _safe(info, "marketCap")

    roe = _safe(info, "returnOnEquity")
    margin = _safe(info, "profitMargins")
    rev_g = _safe(info, "revenueGrowth")
    earn_g = _safe(info, "earningsGrowth")
    payout = _safe(info, "payoutRatio")

    result["metrics"] = {
        # sector / industry classification (kept in metrics so it persists in the
        # snapshot JSON without a schema migration)
        "sector": info.get("sector") or None,
        "industry": info.get("industry") or None,
        # already a percent from yfinance
        "dividend_yield": _safe(info, "dividendYield"),
        "trailing_pe": _safe(info, "trailingPE"),
        "forward_pe": _safe(info, "forwardPE"),
        "price_to_book": _safe(info, "priceToBook"),
        # fractions -> percent for display
        "roe": round(roe * 100, 2) if roe is not None else None,
        "debt_to_equity": _safe(info, "debtToEquity"),
        "profit_margin": round(margin * 100, 2) if margin is not None else None,
        "revenue_growth": round(rev_g * 100, 2) if rev_g is not None else None,
        "earnings_growth": round(earn_g * 100, 2) if earn_g is not None else None,
        "payout_ratio": round(payout * 100, 2) if payout is not None else None,
    }

    if include_statements:
        # --- financial statements (annual, ~4y) ---
        for key, attr in (("income", "income_stmt"), ("balance", "balance_sheet"), ("cashflow", "cashflow")):
            try:
                result["financials"][key] = _df_to_json(getattr(tk, attr))
            except Exception:
                result["financials"][key] = {}

        # --- dividend history (recent) ---
        try:
            divs = tk.dividends
            if divs is not None and len(divs) > 0:
                result["dividends"] = [
                    {"date": idx.strftime("%Y-%m-%d"), "amount": float(val)}
                    for idx, val in divs.tail(12).items()
                ]
        except Exception:
            pass

        # --- upcoming calendar (dividend / earnings dates) ---
        try:
            cal = tk.calendar
            if isinstance(cal, dict):
                out = {}
                for k, v in cal.items():
                    if hasattr(v, "isoformat"):
                        out[k] = v.isoformat()
                    elif isinstance(v, list):
                        out[k] = [x.isoformat() if hasattr(x, "isoformat") else x for x in v]
                    else:
                        out[k] = v
                result["calendar"] = out
        except Exception:
            pass

    # A ticker is "valid" if yfinance gave us anything usable. Delisted/unknown
    # symbols (e.g. ALMAD.IS) return a price-less, statement-less, metric-less
    # shell — flag those so callers can skip them.
    has_metric = any(v is not None for v in result["metrics"].values())
    has_financials = any(result["financials"].get(k) for k in ("income", "balance", "cashflow"))
    result["valid"] = bool(result["price"] is not None or has_metric or has_financials)

    return result


def apply_overrides(data: dict, override_fields: Optional[dict]) -> dict:
    """Overlay manually-entered values on top of yfinance data (in place).

    Numeric fields are coerced to float; sector/industry are kept as text.
    """
    if not override_fields:
        return data
    metrics = data.setdefault("metrics", {})
    for field, value in override_fields.items():
        if value is None or value == "":
            continue
        if field in OVERRIDABLE_FIELDS:
            try:
                metrics[field] = float(value)
            except (TypeError, ValueError):
                continue
        elif field in STRING_OVERRIDABLE_FIELDS:
            metrics[field] = str(value).strip()
    data["has_overrides"] = bool(override_fields)
    return data


def _ramp(value: Optional[float], lo: float, hi: float) -> Optional[float]:
    """Linear 0..100 score: <=lo -> 0, >=hi -> 100. None passes through as None."""
    if value is None:
        return None
    if hi == lo:
        return 0.0
    pct = (value - lo) / (hi - lo) * 100.0
    return max(0.0, min(100.0, pct))


def _ramp_down(value: Optional[float], good: float, bad: float) -> Optional[float]:
    """Linear score where LOWER is better: <=good -> 100, >=bad -> 0."""
    if value is None:
        return None
    if bad == good:
        return 0.0
    pct = (bad - value) / (bad - good) * 100.0
    return max(0.0, min(100.0, pct))


def _avg(components: list) -> Optional[float]:
    vals = [c for c in components if c is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 1)


def score_fundamental(data: dict) -> dict:
    """Compute dividend_score, growth_score, overall_score and a label.

    Each component contributes only if its underlying metric is present, so
    missing BIST fields just lower the confidence rather than crash. Scores are
    None when no component is available.
    """
    m = data.get("metrics", {})

    # Dividend quality: yield (up to ~6%), low leverage, sustainable payout, sane valuation.
    dividend_components = [
        _ramp(m.get("dividend_yield"), 0, 6),
        _ramp_down(m.get("debt_to_equity"), 50, 200),
        _ramp_down(m.get("payout_ratio"), 30, 90),
        _ramp_down(m.get("trailing_pe"), 8, 30),
    ]
    dividend_score = _avg(dividend_components)

    # Growth quality: revenue & earnings growth, ROE, margins.
    growth_components = [
        _ramp(m.get("revenue_growth"), 0, 25),
        _ramp(m.get("earnings_growth"), 0, 25),
        _ramp(m.get("roe"), 0, 30),
        _ramp(m.get("profit_margin"), 0, 25),
    ]
    growth_score = _avg(growth_components)

    # Overall: mean of whichever scores exist.
    overall = _avg([dividend_score, growth_score])

    # Label by which dimension is strong (threshold 60).
    d_ok = (dividend_score or 0) >= 60
    g_ok = (growth_score or 0) >= 60
    if d_ok and g_ok:
        label = "ikisi"
    elif d_ok:
        label = "temettü"
    elif g_ok:
        label = "büyüme"
    else:
        label = "zayıf"

    data["dividend_score"] = dividend_score
    data["growth_score"] = growth_score
    data["overall_score"] = overall
    data["label"] = label
    return data


def fetch_google_news(query: str, limit: int = 8, lang: str = "tr", country: str = "TR") -> list:
    """Turkish-language news for a query via the Google News RSS feed.

    Aggregates many Turkish financial sources (Investing.com TR, Bloomberght,
    Mynet, Bigpara, CNBC-e, ...). Returns [] on any failure.
    """
    out = []
    try:
        q = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={q}&hl={lang}&gl={country}&ceid={country}:{lang}"
        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return out
        root = ET.fromstring(r.content)
        for it in root.findall("./channel/item")[:limit]:
            title = (it.findtext("title") or "").strip()
            src_el = it.find("{*}source")
            publisher = src_el.text if src_el is not None else None
            # Google appends " - <Source>" to the title; strip it.
            if publisher and title.endswith(f" - {publisher}"):
                title = title[: -(len(publisher) + 3)]
            pub = it.findtext("pubDate")
            try:
                published = parsedate_to_datetime(pub).isoformat() if pub else None
            except Exception:
                published = pub
            out.append({
                "title": title,
                "publisher": publisher,
                "link": it.findtext("link"),
                "published": published,
                "type": "NEWS",
            })
    except Exception:
        pass
    return out


def _yahoo_news(tk, max_news: int) -> list:
    """Parse yfinance's nested `content` news structure (good for US names)."""
    news = []
    try:
        for item in (tk.news or [])[:max_news]:
            c = item.get("content") if isinstance(item, dict) else None
            c = c or (item if isinstance(item, dict) else {})
            link = (
                (c.get("canonicalUrl") or {}).get("url")
                or (c.get("clickThroughUrl") or {}).get("url")
                or c.get("link")
            )
            news.append({
                "title": c.get("title"),
                "publisher": (c.get("provider") or {}).get("displayName") or c.get("publisher"),
                "link": link,
                "published": c.get("pubDate") or c.get("displayTime"),
                "type": c.get("contentType"),
            })
    except Exception:
        pass
    return news


def fetch_news_and_events(ticker: str, market: Optional[str] = None, max_news: int = 8) -> dict:
    """Recent news headlines + upcoming earnings/dividend dates for one ticker.

    BIST news comes from Google News in Turkish (many local sources); US news
    comes from yfinance (good English coverage). Earnings/dividend dates come
    from yfinance `.calendar` for both. Returns empty pieces rather than raising.
    """
    market = normalize_market(market) if market else infer_market(ticker)
    out = {
        "news": [],
        "earnings_date": None,
        "ex_dividend_date": None,
        "dividend_date": None,
    }
    try:
        tk = yf.Ticker(ticker)
    except Exception:
        return out

    # --- news ---
    if market == "bist":
        # Use the company name for a relevant Turkish search; fall back to symbol.
        name = None
        try:
            info = tk.info or {}
            name = info.get("shortName") or info.get("longName")
        except Exception:
            pass
        query = f"{name or ticker.replace('.IS', '')} hisse"
        out["news"] = fetch_google_news(query, max_news)
    else:
        out["news"] = _yahoo_news(tk, max_news)

    # --- upcoming calendar dates ---
    def _as_date(v):
        if v is None:
            return None
        if isinstance(v, list):
            v = v[0] if v else None
        if v is None:
            return None
        return v.isoformat() if hasattr(v, "isoformat") else str(v)

    try:
        cal = tk.calendar
        if isinstance(cal, dict):
            out["earnings_date"] = _as_date(cal.get("Earnings Date"))
            out["ex_dividend_date"] = _as_date(cal.get("Ex-Dividend Date"))
            out["dividend_date"] = _as_date(cal.get("Dividend Date"))
    except Exception:
        pass

    return out


def analyze(ticker: str, override_fields: Optional[dict] = None, include_statements: bool = True) -> dict:
    """Full pipeline: fetch -> apply overrides -> score. Network-bound.

    Pass `include_statements=False` for fast bulk scoring (screener).
    """
    data = fetch_fundamentals(ticker, include_statements=include_statements)
    apply_overrides(data, override_fields)
    score_fundamental(data)
    return data
