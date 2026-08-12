"""Long-term fund and ETF analysis from Yahoo Finance and TEFAS."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
import unicodedata

import numpy as np
import pandas as pd
import yfinance as yf

from financia.markets import get_market_config, infer_market, normalize_market


# A broad but curated ETF universe. Keeping the list explicit makes scans
# repeatable and avoids pulling delisted/leveraged products into long-term ideas.
US_ETF_UNIVERSE = [
    "SPY", "IVV", "VOO", "VTI", "VT", "VXUS", "QQQ", "QQQM", "DIA",
    "IWM", "SCHB", "ITOT", "ACWI", "SCHD", "VIG", "VYM", "DGRO", "HDV",
    "SDY", "NOBL", "DVY", "VUG", "VTV", "IWF", "IWD", "SCHG", "SCHV",
    "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB",
    "XLRE", "XLC", "SMH", "SOXX", "XBI", "VNQ", "IYR", "BND", "AGG",
    "TLT", "IEF", "SHY", "SGOV", "VGSH", "VCIT", "LQD", "HYG", "TIP",
    "VEA", "VWO", "EFA", "EEM", "EWJ", "EWZ", "INDA", "MCHI", "GLD",
    "IAU", "SLV", "PDBC", "DBC", "USO", "ARKK", "ICLN", "TAN", "LIT",
    "BOTZ", "CIBR",
]
US_FUND_UNIVERSE = ["VFIAX", "VTSAX", "VTIAX", "FXAIX", "FSKAX", "SWPPX"]
BIST_ETF_UNIVERSE = [
    "APBDL.IS", "APGLD.IS", "APLIB.IS", "APMDL.IS", "APX30.IS", "GLDTR.IS",
    "GMSTR.IS", "ISGLK.IS", "NPTLR.IS", "OPK30.IS", "USDTR.IS", "Z30KE.IS",
    "Z30KP.IS", "ZGOLD.IS", "ZTLRK.IS",
]


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


def _tefas_number(value) -> Optional[float]:
    """Parse both numeric and Turkish-formatted TEFAS values."""
    if isinstance(value, (int, float)):
        return _number(value)
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace("\xa0", "").replace(" ", "")
    if not text or text in {"-", "—"}:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    return _number(text)


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


def _annualize_total(total_return: Optional[float], years: int) -> Optional[float]:
    if total_return is None or total_return <= -100:
        return None
    return ((1 + total_return / 100) ** (1 / years) - 1) * 100


def _ascii_upper(value: str) -> str:
    translated = value.translate(str.maketrans({"ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G"}))
    return unicodedata.normalize("NFKD", translated).encode("ascii", "ignore").decode().upper()


def _distribution_from_title(name: str) -> tuple[bool, str]:
    # TEFAS has no uniform cash-distribution field. Only make a positive claim
    # when the fund title explicitly identifies a profit-distributing fund.
    distributes = "KAR PAYI ODEYEN" in _ascii_upper(name)
    status = "Kâr payı ödüyor" if distributes else "Birikimli / nakit dağıtım bilgisi yok"
    return distributes, status


def analyze(ticker: str, market: Optional[str] = None, asset_type: Optional[str] = None) -> dict:
    ticker = ticker.strip().upper()
    market = normalize_market(market) if market else infer_market(ticker)
    cfg = get_market_config(market)
    out = {
        "ticker": ticker,
        "symbol": ticker.replace(".IS", ""),
        "market": market,
        "asset_type": asset_type or "etf",
        "data_source": "yfinance",
        "name": ticker,
        "category": None,
        "fund_family": None,
        "currency": cfg["currency_symbol"],
        "price": None,
        "distribution_status": "Bilinmiyor",
        "distributes_cash": None,
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
        hist = tk.history(period="5y", interval="1d", auto_adjust=True, actions=True)
    except Exception as exc:
        out["error"] = str(exc)
        return out

    quote_type = str(info.get("quoteType") or "").upper()
    if not asset_type:
        out["asset_type"] = "fund" if quote_type == "MUTUALFUND" else "etf"
    out["name"] = info.get("longName") or info.get("shortName") or ticker
    out["category"] = info.get("category") or ("Fon/ETF" if info.get("fundInceptionDate") else None)
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
    dividends = hist.get("Dividends", pd.Series(dtype=float)).fillna(0)
    dividend_events = dividends[dividends > 0]
    recent_cutoff = hist.index[-1] - pd.Timedelta(days=370)
    recent_dividends = dividend_events[dividend_events.index >= recent_cutoff]
    distributes_cash = not recent_dividends.empty
    if distributes_cash:
        out["distribution_status"] = "Dağıtıyor"
    elif not dividend_events.empty:
        out["distribution_status"] = "Geçmişte dağıttı"
    else:
        out["distribution_status"] = "Dağıtmıyor"
    out["distributes_cash"] = distributes_cash
    last_distribution_date = dividend_events.index[-1].date().isoformat() if not dividend_events.empty else None
    trailing_distribution = float(recent_dividends.sum()) if not recent_dividends.empty else 0.0
    if price > 0 and trailing_distribution > 0:
        dividend_yield = trailing_distribution / price * 100

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
    reasons.append(f"Nakit dağıtım: {out['distribution_status']}")

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
            "last_distribution_date": last_distribution_date,
            "trailing_distribution": round(trailing_distribution, 4),
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


def tefas_reports(fund_type: str = "YAT", limit: Optional[int] = None) -> list[dict]:
    """Build TEFAS reports with three bulk requests, sorted by fund size."""
    from tefasmak import fonlar_buyukluk, fonlar_donemsel_getiri, fonlar_yonetim_ucretleri

    fund_type = fund_type.upper()
    sizes = fonlar_buyukluk(fund_type)
    returns = fonlar_donemsel_getiri(fund_type)
    fees = fonlar_yonetim_ucretleri(fund_type)
    returns_by_code = {str(row.get("fonKodu") or "").upper(): row for row in returns}
    fees_by_code = {str(row.get("fonKodu") or "").upper(): row for row in fees}

    ranked = []
    for row in sizes:
        code = str(row.get("fonKodu") or "").strip().upper()
        size = _tefas_number(row.get("sonPortfoyDegeri"))
        if code and size is not None and size > 0:
            ranked.append((size, code, row))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if limit is not None:
        ranked = ranked[:limit]

    reports = []
    for size_rank, (size, code, size_row) in enumerate(ranked, start=1):
        return_row = returns_by_code.get(code, {})
        fee_row = fees_by_code.get(code, {})
        name = str(size_row.get("fonUnvan") or return_row.get("fonUnvan") or code).strip()
        category = size_row.get("fonTurAciklama") or return_row.get("fonTurAciklama")
        shares = _tefas_number(size_row.get("sonPayAdedi"))
        price = size / shares if shares and shares > 0 else None
        return_1y = _tefas_number(return_row.get("getiri1y"))
        return_3y = _annualize_total(_tefas_number(return_row.get("getiri3y")), 3)
        return_5y = _annualize_total(_tefas_number(return_row.get("getiri5y")), 5)
        return_6m = _tefas_number(return_row.get("getiri6a"))
        ytd_return = _tefas_number(return_row.get("getiriyb"))
        risk_level = _tefas_number(return_row.get("riskDegeri"))
        expense = _tefas_number(fee_row.get("uygulananYu1Y"))

        performance_parts = [_ramp(return_3y, -5, 35), _ramp(return_1y, -20, 60)]
        performance_parts = [value for value in performance_parts if value is not None]
        performance = sum(performance_parts) / len(performance_parts) if performance_parts else None
        risk = _lower_better(risk_level, 1, 7) if risk_level is not None else None
        cost = _lower_better(expense, 0.5, 4.0) if expense is not None else None
        trend = _ramp(return_6m, -20, 35)
        weighted = [(performance, 0.45), (risk, 0.30), (cost, 0.15), (trend, 0.10)]
        known = [(value, weight) for value, weight in weighted if value is not None]
        score = round(sum(value * weight for value, weight in known) / sum(weight for _, weight in known)) if known else None
        distributes, distribution_status = _distribution_from_title(name)

        if score is None:
            label, action = "Veri yetersiz", "VERİ YETERSİZ"
        elif score >= 70:
            label, action = "Güçlü uzun vade adayı", "TUT"
        elif score >= 55:
            label, action = "İzle / kademeli al", ("DÜŞÜŞTE KADEMELİ AL" if (return_6m or 0) < 0 else "TUT")
        elif score >= 40:
            label, action = "Nötr", "İZLE / TUT"
        else:
            label, action = "Zayıf", "İZLE / TUT"

        reasons = []
        if return_3y is not None:
            reasons.append(f"3 yıllık yıllıklandırılmış getiri %{return_3y:.1f}")
        if return_1y is not None:
            reasons.append(f"1 yıllık getiri %{return_1y:.1f}")
        if risk_level is not None:
            reasons.append(f"TEFAS risk değeri {risk_level:.0f}/7")
        if expense is not None:
            reasons.append(f"Yıllık yönetim ücreti %{expense:.2f}")
        reasons.append(f"Nakit dağıtım: {distribution_status}")

        reports.append({
            "ticker": code,
            "symbol": code,
            "market": "bist",
            "asset_type": "etf" if fund_type == "BYF" else "fund",
            "data_source": "tefas",
            "name": name,
            "category": category,
            "fund_family": size_row.get("kurucuKodu") or fee_row.get("kurucuKod"),
            "currency": "₺",
            "price": round(price, 6) if price is not None else None,
            "distribution_status": distribution_status,
            "distributes_cash": distributes,
            "metrics": {
                "return_1y": round(return_1y, 2) if return_1y is not None else None,
                "return_3y": round(return_3y, 2) if return_3y is not None else None,
                "return_5y": round(return_5y, 2) if return_5y is not None else None,
                "return_6m": round(return_6m, 2) if return_6m is not None else None,
                "ytd_return": round(ytd_return, 2) if ytd_return is not None else None,
                "risk_level": round(risk_level, 1) if risk_level is not None else None,
                "expense_ratio": round(expense, 3) if expense is not None else None,
                "total_assets": round(size, 2),
                "size_rank": size_rank,
                "volatility_1y": None,
                "max_drawdown_3y": None,
                "dividend_yield": None,
            },
            "components": {
                "performance": round(performance, 1) if performance is not None else None,
                "risk": round(risk, 1) if risk is not None else None,
                "cost": round(cost, 1) if cost is not None else None,
                "trend": round(trend, 1) if trend is not None else None,
                "income": None,
            },
            "score": score,
            "label": label,
            "portfolio_action": action,
            "reasons": reasons,
            "valid": True,
            "error": None,
            "fetched_at": datetime.utcnow().isoformat(),
        })
    return reports


def analyze_tefas(ticker: str, asset_type: str = "fund") -> dict:
    code = ticker.strip().upper().removesuffix(".IS")
    fund_type = "BYF" if asset_type == "etf" else "YAT"
    for report in tefas_reports(fund_type):
        if report["ticker"] == code:
            return report
    return {
        "ticker": code,
        "symbol": code,
        "market": "bist",
        "asset_type": asset_type,
        "data_source": "tefas",
        "valid": False,
        "error": "Fon TEFAS verisinde bulunamadı",
    }
