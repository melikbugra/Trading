"""Long-term fund and ETF analysis built from yfinance history/profile data."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

from financia.markets import get_market_config, infer_market, normalize_market


US_ETF_UNIVERSE = [
    "VOO", "VTI", "VT", "VXUS", "QQQ", "IWM", "SCHD", "VIG",
    "BND", "TLT", "GLD", "XLK", "XLF", "XLE", "SOXX", "SMH",
]
US_FUND_UNIVERSE = ["VFIAX", "VTSAX", "VTIAX", "FXAIX", "FSKAX", "SWPPX"]
BIST_ETF_UNIVERSE = ["GLDTR.IS", "Z30EA.IS", "ZPX30.IS"]


def universe(name: str) -> list[str]:
    return {
        "us_etf": US_ETF_UNIVERSE,
        "us_fund": US_FUND_UNIVERSE,
        "bist_etf": BIST_ETF_UNIVERSE,
    }.get(name, [])


def _number(value) -> Optional[float]:
    try:
        number = float(value)
        return number if np.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _percent(value) -> Optional[float]:
    value = _number(value)
    if value is None:
        return None
    return value * 100 if abs(value) <= 1 else value


def _ramp(value: Optional[float], low: float, high: float) -> Optional[float]:
    if value is None:
        return None
    return max(0.0, min(100.0, (value - low) / (high - low) * 100))


def _lower_better(value: Optional[float], good: float, bad: float) -> Optional[float]:
    if value is None:
        return None
    return 100.0 - max(0.0, min(100.0, (value - good) / (bad - good) * 100))


def _annualized_return(close: pd.Series, years: int) -> Optional[float]:
    window = close.tail(252 * years + 10)
    if len(window) < min(180, 252 * years * 0.7):
        return None
    elapsed = (window.index[-1] - window.index[0]).days / 365.25
    if elapsed <= 0 or window.iloc[0] <= 0:
        return None
    return ((float(window.iloc[-1]) / float(window.iloc[0])) ** (1 / elapsed) - 1) * 100


def analyze(ticker: str, market: Optional[str] = None, asset_type: Optional[str] = None) -> dict:
    ticker = ticker.strip().upper()
    market = normalize_market(market) if market else infer_market(ticker)
    cfg = get_market_config(market)
    out = {
        "ticker": ticker,
        "symbol": ticker.replace(".IS", ""),
        "market": market,
        "asset_type": asset_type or "etf",
        "name": ticker,
        "category": None,
        "fund_family": None,
        "currency": cfg["currency_symbol"],
        "price": None,
        "metrics": {},
        "components": {},
        "score": None,
        "label": "Veri yetersiz",
        "portfolio_action": "VERİ YETERSİZ",
        "reasons": [],
        "valid": False,
        "error": None,
        "fetched_at": datetime.utcnow().isoformat(),
    }

    try:
        tk = yf.Ticker(ticker)
        try:
            info = tk.info or {}
        except Exception:
            info = {}
        hist = tk.history(period="5y", interval="1d", auto_adjust=True)
    except Exception as exc:
        out["error"] = str(exc)
        return out

    quote_type = str(info.get("quoteType") or "").upper()
    if not asset_type:
        out["asset_type"] = "fund" if quote_type == "MUTUALFUND" else "etf"
    out["name"] = info.get("longName") or info.get("shortName") or ticker
    out["category"] = info.get("category") or info.get("fundInceptionDate") and "Fon/ETF" or None
    out["fund_family"] = info.get("fundFamily")

    expense = _percent(
        info.get("annualReportExpenseRatio")
        or info.get("netExpenseRatio")
        or info.get("expenseRatio")
    )
    dividend_yield = _percent(info.get("yield") or info.get("dividendYield"))
    total_assets = _number(info.get("totalAssets"))

    if hist is None or hist.empty or "Close" not in hist:
        out["error"] = "Fiyat geçmişi bulunamadı"
        out["metrics"] = {
            "expense_ratio": expense,
            "dividend_yield": dividend_yield,
            "total_assets": total_assets,
        }
        return out

    close = hist["Close"].dropna()
    if len(close) < 30:
        out["error"] = "Analiz için yeterli fiyat geçmişi yok"
        return out

    price = float(close.iloc[-1])
    returns = close.pct_change().dropna()
    return_1y = _annualized_return(close, 1)
    return_3y = _annualized_return(close, 3)
    return_5y = _annualized_return(close, 5)
    volatility = float(returns.tail(252).std(ddof=0) * np.sqrt(252) * 100) if len(returns) >= 30 else None
    three_year = close.tail(252 * 3)
    running_max = three_year.cummax()
    max_drawdown = float(((three_year / running_max) - 1).min() * 100) if not three_year.empty else None
    sma200 = float(close.tail(min(200, len(close))).mean())
    price_vs_sma200 = (price - sma200) / sma200 * 100 if sma200 else None
    high_52 = float(close.tail(252).max())
    drawdown_52 = (price - high_52) / high_52 * 100 if high_52 else None

    performance_parts = [_ramp(return_3y, -5, 18), _ramp(return_1y, -15, 25)]
    performance_parts = [v for v in performance_parts if v is not None]
    performance = sum(performance_parts) / len(performance_parts) if performance_parts else None
    risk_parts = [
        _lower_better(volatility, 10, 45),
        _lower_better(abs(max_drawdown) if max_drawdown is not None else None, 10, 55),
    ]
    risk_parts = [v for v in risk_parts if v is not None]
    risk = sum(risk_parts) / len(risk_parts) if risk_parts else None
    cost = _lower_better(expense, 0.10, 1.50) if expense is not None else None
    trend = _ramp(price_vs_sma200, -20, 15)
    income = _ramp(dividend_yield, 0, 6) if dividend_yield is not None else None

    weighted = [(performance, 0.35), (risk, 0.30), (cost, 0.15), (trend, 0.15), (income, 0.05)]
    known = [(value, weight) for value, weight in weighted if value is not None]
    score = round(sum(value * weight for value, weight in known) / sum(weight for _, weight in known)) if known else None

    reasons = []
    if return_3y is not None:
        reasons.append(f"3 yıllık yıllıklandırılmış getiri %{return_3y:.1f}")
    if volatility is not None:
        reasons.append(f"1 yıllık oynaklık %{volatility:.1f}")
    if max_drawdown is not None:
        reasons.append(f"3 yıllık maksimum düşüş %{max_drawdown:.1f}")
    if expense is not None:
        reasons.append(f"Yıllık gider oranı %{expense:.2f}")
    if price_vs_sma200 is not None:
        reasons.append(f"Fiyat 200 günlük ortalamanın %{abs(price_vs_sma200):.1f} {'üstünde' if price_vs_sma200 >= 0 else 'altında'}")

    if score is None:
        label = "Veri yetersiz"
    elif score >= 70:
        label = "Güçlü uzun vade adayı"
    elif score >= 55:
        label = "İzle / kademeli al"
    elif score >= 40:
        label = "Nötr"
    else:
        label = "Zayıf"

    if score is None:
        action = "VERİ YETERSİZ"
    elif score < 30 and (price_vs_sma200 or 0) <= -20 and (max_drawdown or 0) <= -35:
        action = "KADEMELİ AZALT"
    elif score >= 60 and drawdown_52 is not None and drawdown_52 <= -15:
        action = "DÜŞÜŞTE KADEMELİ AL"
    elif score >= 50:
        action = "TUT"
    else:
        action = "İZLE / TUT"

    out.update({
        "price": round(price, 4),
        "metrics": {
            "return_1y": round(return_1y, 2) if return_1y is not None else None,
            "return_3y": round(return_3y, 2) if return_3y is not None else None,
            "return_5y": round(return_5y, 2) if return_5y is not None else None,
            "volatility_1y": round(volatility, 2) if volatility is not None else None,
            "max_drawdown_3y": round(max_drawdown, 2) if max_drawdown is not None else None,
            "price_vs_sma200": round(price_vs_sma200, 2) if price_vs_sma200 is not None else None,
            "drawdown_52w": round(drawdown_52, 2) if drawdown_52 is not None else None,
            "expense_ratio": round(expense, 3) if expense is not None else None,
            "dividend_yield": round(dividend_yield, 2) if dividend_yield is not None else None,
            "total_assets": total_assets,
        },
        "components": {
            "performance": round(performance, 1) if performance is not None else None,
            "risk": round(risk, 1) if risk is not None else None,
            "cost": round(cost, 1) if cost is not None else None,
            "trend": round(trend, 1) if trend is not None else None,
            "income": round(income, 1) if income is not None else None,
        },
        "score": score,
        "label": label,
        "portfolio_action": action,
        "reasons": reasons,
        "valid": True,
    })
    return out
