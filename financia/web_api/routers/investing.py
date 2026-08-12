"""
Long-term investing API endpoints (second sub-app).

Holdings tracking, a long-term watchlist, manual fundamental screening, a
detailed per-stock fundamental report (with manual overrides), and a dividend
calendar / income projection. All scanning is manual (user-triggered).
"""

import asyncio
from datetime import datetime, date
from typing import List, Optional, Dict, Any

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from financia.web_api.database import (
    get_db,
    SessionLocal,
    now_turkey,
    LongTermHolding,
    LongTermSale,
    LongTermHoldingIncome,
    LongTermPortfolioAdvice,
    LongTermFundHolding,
    LongTermFundWatchlistItem,
    FundSnapshot,
    LongTermWatchlistItem,
    FundamentalSnapshot,
    FundamentalOverride,
)
from financia.web_api.websocket_manager import manager
from financia.markets import normalize_market, get_market_config, get_market_tickers, infer_market
from financia import fundamental_service, fund_service

router = APIRouter(prefix="/investing", tags=["investing"])

# Guards against overlapping bulk scans (one at a time).
_scan_state = {"running": False}


# ============= Pydantic Models =============


class HoldingCreate(BaseModel):
    ticker: str
    market: Optional[str] = None  # inferred from ticker if omitted
    shares: float
    cost_basis: float
    purchase_date: Optional[date] = None
    notes: str = ""


class HoldingUpdate(BaseModel):
    shares: Optional[float] = None
    cost_basis: Optional[float] = None
    purchase_date: Optional[date] = None
    notes: Optional[str] = None


class HoldingSell(BaseModel):
    shares: float
    sale_price: Optional[float] = None
    sale_date: Optional[date] = None
    notes: str = ""


class DividendAdd(BaseModel):
    amount: float


class FundHoldingCreate(BaseModel):
    ticker: str
    market: Optional[str] = None
    asset_type: str = "etf"
    units: float
    cost_basis: float
    purchase_date: Optional[date] = None
    notes: str = ""


class FundHoldingSell(BaseModel):
    units: float


class FundWatchlistCreate(BaseModel):
    ticker: str
    market: Optional[str] = None
    asset_type: str = "etf"
    notes: str = ""


class FundScanRequest(BaseModel):
    universe: Optional[str] = None
    tickers: Optional[List[str]] = None
    market: Optional[str] = None
    asset_type: Optional[str] = None


class WatchlistCreate(BaseModel):
    ticker: str
    market: Optional[str] = None
    notes: str = ""


class ScanRequest(BaseModel):
    market: Optional[str] = None  # "bist" | "us" : scan that universe
    universe: Optional[str] = None  # bist: "100"|"all" ; us: "100"|"ext"
    tickers: Optional[List[str]] = None  # explicit list
    use_watchlist: bool = False  # scan the long-term watchlist
    limit: Optional[int] = None  # cap number of tickers (full-market scans are slow)
    portfolio: bool = False  # add portfolio-specific hold/reduce advice


class OverrideUpdate(BaseModel):
    fields: Dict[str, Any]


# ============= Helpers =============


def _norm(ticker: str, market: Optional[str]) -> str:
    return normalize_market(market) if market else infer_market(ticker)


def _normalize_ticker(ticker: str, market: Optional[str]) -> str:
    """Clean a user-typed ticker, appending `.IS` for BIST when missing.

    e.g. ("thyao", "bist") -> "THYAO.IS"; ("aapl", "us") -> "AAPL".
    """
    t = ticker.strip().upper()
    if market and normalize_market(market) == "bist" and not t.endswith(".IS"):
        t += ".IS"
    return t


def _normalize_fund_ticker(ticker: str, market: Optional[str], asset_type: Optional[str] = None) -> str:
    """Normalize fund codes without turning TEFAS codes into Yahoo symbols."""
    t = ticker.strip().upper()
    if market and normalize_market(market) == "bist":
        if (asset_type or "fund").lower() == "fund":
            return t.removesuffix(".IS")
        return t if t.endswith(".IS") else f"{t}.IS"
    return t


def _live_price(ticker: str) -> Optional[float]:
    """Best-effort current price via yfinance fast_info.

    Note: FastInfo exposes snake_case attributes (`.last_price`) but its
    dict-style `.get()` expects camelCase (`"lastPrice"`) — use the attribute.
    """
    try:
        fi = yf.Ticker(ticker).fast_info
        p = getattr(fi, "last_price", None)
        return float(p) if p is not None else None
    except Exception:
        return None


def _get_override_fields(db: Session, ticker: str) -> dict:
    ov = db.query(FundamentalOverride).filter(FundamentalOverride.ticker == ticker).first()
    return (ov.fields or {}) if ov else {}


def _upsert_snapshot(db: Session, report: dict):
    """Store/update the cached fundamental snapshot for a ticker."""
    snap = (
        db.query(FundamentalSnapshot)
        .filter(FundamentalSnapshot.ticker == report["ticker"])
        .first()
    )
    if not snap:
        snap = FundamentalSnapshot(ticker=report["ticker"])
        db.add(snap)
    snap.market = report["market"]
    snap.metrics = report.get("metrics", {})
    snap.financials = report.get("financials", {})
    snap.dividend_score = report.get("dividend_score")
    snap.growth_score = report.get("growth_score")
    snap.overall_score = report.get("overall_score")
    snap.label = report.get("label")
    snap.fetched_at = now_turkey()


def _upsert_fund_snapshot(db: Session, report: dict):
    snap = db.query(FundSnapshot).filter(FundSnapshot.ticker == report["ticker"]).first()
    if not snap:
        snap = FundSnapshot(ticker=report["ticker"])
        db.add(snap)
    snap.market = report["market"]
    snap.asset_type = report["asset_type"]
    snap.name = report.get("name")
    snap.category = report.get("category")
    snap.data = report
    snap.score = report.get("score")
    snap.label = report.get("label")
    snap.fetched_at = now_turkey()


def _fund_snapshot_row(snap: Optional[FundSnapshot], ticker: str, market: str, asset_type: str) -> dict:
    if snap:
        return snap.data or {
            "ticker": ticker,
            "market": market,
            "asset_type": asset_type,
            "name": snap.name,
            "category": snap.category,
            "score": snap.score,
            "label": snap.label,
        }
    return {
        "ticker": ticker,
        "symbol": ticker.replace(".IS", ""),
        "market": market,
        "asset_type": asset_type,
        "name": ticker,
        "category": None,
        "score": None,
        "label": "Henüz analiz edilmedi",
        "metrics": {},
    }


# A sector needs at least this many scanned peers for a relative value score.
_MIN_VALUE_PEERS = 3


def _pct_lower_better(value, peers) -> Optional[float]:
    """Percentile where a LOWER value scores higher (cheaper P/E, P/B = better).

    100 = cheapest among peers. None if no data.
    """
    vals = [p for p in peers if p is not None]
    if value is None or not vals:
        return None
    more_expensive = sum(1 for p in vals if p > value)
    return more_expensive / len(vals) * 100.0


def _pct_higher_better(value, peers) -> Optional[float]:
    """Percentile where a HIGHER value scores higher (yield = better)."""
    vals = [p for p in peers if p is not None]
    if value is None or not vals:
        return None
    lower = sum(1 for p in vals if p < value)
    return lower / len(vals) * 100.0


def _value_score(target: dict, sector_peers: list) -> Optional[float]:
    """Sector-relative cheapness score (0-100): cheap P/E + P/B + high yield vs peers."""
    if len(sector_peers) < _MIN_VALUE_PEERS:
        return None
    pe = [p.get("trailing_pe") for p in sector_peers]
    pb = [p.get("price_to_book") for p in sector_peers]
    dy = [p.get("dividend_yield") for p in sector_peers]
    comps = [
        _pct_lower_better(target.get("trailing_pe"), pe),
        _pct_lower_better(target.get("price_to_book"), pb),
        _pct_higher_better(target.get("dividend_yield"), dy),
    ]
    comps = [c for c in comps if c is not None]
    if not comps:
        return None
    return round(sum(comps) / len(comps), 1)


def _attach_value_scores(rows: list) -> list:
    """Add `value_score` to each row, relative to peers in the same sector."""
    from collections import defaultdict

    groups = defaultdict(list)
    for r in rows:
        if r.get("sector"):
            groups[r["sector"]].append(r)
    for r in rows:
        sec = r.get("sector")
        r["value_score"] = _value_score(r, groups.get(sec, [])) if sec else None
    return rows


def _snapshot_summary(snap: FundamentalSnapshot) -> dict:
    m = snap.metrics or {}
    return {
        "ticker": snap.ticker,
        "market": snap.market,
        "symbol": snap.ticker.replace(".IS", ""),
        "sector": m.get("sector"),
        "industry": m.get("industry"),
        "price_to_book": m.get("price_to_book"),
        "dividend_yield": m.get("dividend_yield"),
        "trailing_pe": m.get("trailing_pe"),
        "roe": m.get("roe"),
        "revenue_growth": m.get("revenue_growth"),
        "dividend_score": snap.dividend_score,
        "growth_score": snap.growth_score,
        "overall_score": snap.overall_score,
        "label": snap.label,
        "fetched_at": snap.fetched_at.isoformat() if snap.fetched_at else None,
    }


# ============= Holdings =============


@router.get("/holdings")
def list_holdings(db: Session = Depends(get_db)):
    """All long-term holdings with live valuation, P/L and per-currency weight."""
    holdings = db.query(LongTermHolding).order_by(LongTermHolding.created_at.desc()).all()
    snaps = {s.ticker: s for s in db.query(FundamentalSnapshot).all()}
    incomes = {i.holding_id: i.amount for i in db.query(LongTermHoldingIncome).all()}
    advice_map = {a.holding_id: a.advice for a in db.query(LongTermPortfolioAdvice).all()}

    rows = []
    # value totals per currency symbol so BIST (₺) and US ($) stay separate
    totals: Dict[str, float] = {}
    summary_by_currency: Dict[str, dict] = {}
    price_cache: Dict[str, Optional[float]] = {}
    for h in holdings:
        if h.ticker not in price_cache:
            price_cache[h.ticker] = _live_price(h.ticker)
        price = price_cache[h.ticker]
        cur = get_market_config(h.market)["currency_symbol"]
        snap = snaps.get(h.ticker)
        sector = (snap.metrics or {}).get("sector") if snap else None
        industry = (snap.metrics or {}).get("industry") if snap else None
        cost_value = h.shares * h.cost_basis
        market_value = h.shares * price if price is not None else None
        pnl = (market_value - cost_value) if market_value is not None else None
        pnl_pct = (pnl / cost_value * 100) if (pnl is not None and cost_value) else None
        dividend_total = incomes.get(h.id, 0.0)
        if market_value is not None:
            totals[cur] = totals.get(cur, 0.0) + market_value
        summary = summary_by_currency.setdefault(cur, {"cost_value": 0.0, "market_value": 0.0, "pnl": 0.0, "dividends": 0.0, "has_price": True})
        summary["cost_value"] += cost_value
        summary["dividends"] += dividend_total
        if market_value is None:
            summary["has_price"] = False
        else:
            summary["market_value"] += market_value
            summary["pnl"] += pnl
        rows.append({
            "id": h.id,
            "ticker": h.ticker,
            "symbol": h.ticker.replace(".IS", ""),
            "market": h.market,
            "sector": sector,
            "industry": industry,
            "dividend_score": snap.dividend_score if snap else None,
            "growth_score": snap.growth_score if snap else None,
            "overall_score": snap.overall_score if snap else None,
            "currency": cur,
            "shares": h.shares,
            "cost_basis": h.cost_basis,
            "purchase_date": h.purchase_date.isoformat() if h.purchase_date else None,
            "notes": h.notes,
            "price": price,
            "cost_value": round(cost_value, 2),
            "market_value": round(market_value, 2) if market_value is not None else None,
            "pnl": round(pnl, 2) if pnl is not None else None,
            "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
            "dividend_total": round(dividend_total, 2),
            "portfolio_advice": advice_map.get(h.id),
        })

    fund_rows = _fund_holding_rows(db)
    for fund in fund_rows:
        cur = fund["currency"]
        summary = summary_by_currency.setdefault(
            cur,
            {"cost_value": 0.0, "market_value": 0.0, "pnl": 0.0, "dividends": 0.0, "has_price": True},
        )
        summary["cost_value"] += fund["cost_value"]
        if fund["market_value"] is None:
            summary["has_price"] = False
        else:
            totals[cur] = totals.get(cur, 0.0) + fund["market_value"]
            summary["market_value"] += fund["market_value"]
            summary["pnl"] += fund["pnl"]

    # compute weights within each currency bucket
    for r in rows:
        cur = r["currency"]
        if r["market_value"] is not None and totals.get(cur):
            r["weight"] = round(r["market_value"] / totals[cur] * 100, 1)
        else:
            r["weight"] = None
    for fund in fund_rows:
        cur = fund["currency"]
        fund["weight"] = (
            round(fund["market_value"] / totals[cur] * 100, 1)
            if fund["market_value"] is not None and totals.get(cur)
            else None
        )

    return {
        "holdings": rows,
        "fund_holdings": fund_rows,
        "totals": [{"currency": c, "market_value": round(v, 2)} for c, v in totals.items()],
        "summary": [
            {
                "currency": cur,
                "cost_value": round(s["cost_value"], 2),
                "market_value": round(s["market_value"], 2) if s["has_price"] else None,
                "pnl": round(s["pnl"], 2) if s["has_price"] else None,
                "dividends": round(s["dividends"], 2),
                "total_return": round(s["pnl"] + s["dividends"], 2) if s["has_price"] else None,
            }
            for cur, s in summary_by_currency.items()
        ],
    }


@router.post("/holdings")
def add_holding(item: HoldingCreate, db: Session = Depends(get_db)):
    import math

    ticker = _normalize_ticker(item.ticker, item.market)
    market = _norm(ticker, item.market)
    if not math.isfinite(item.shares) or item.shares <= 0:
        raise HTTPException(status_code=400, detail="Alış adedi sıfırdan büyük olmalı")
    if not math.isfinite(item.cost_basis) or item.cost_basis <= 0:
        raise HTTPException(status_code=400, detail="Maliyet sıfırdan büyük olmalı")

    # Merge repeated buys into one position. This also consolidates any older
    # duplicate rows that may have been created before this behavior existed.
    matches = (
        db.query(LongTermHolding)
        .filter(LongTermHolding.ticker == ticker, LongTermHolding.market == market)
        .order_by(LongTermHolding.created_at.asc(), LongTermHolding.id.asc())
        .all()
    )
    if matches:
        holding = matches[0]
        old_shares = sum(h.shares for h in matches)
        old_cost = sum(h.shares * h.cost_basis for h in matches)
        total_shares = old_shares + item.shares
        holding.shares = total_shares
        holding.cost_basis = (old_cost + item.shares * item.cost_basis) / total_shares
        if holding.purchase_date is None or (
            item.purchase_date is not None and item.purchase_date < holding.purchase_date
        ):
            holding.purchase_date = item.purchase_date
        if item.notes:
            holding.notes = f"{holding.notes}\nAlış: {item.notes}".strip()
        for duplicate in matches[1:]:
            duplicate_income = db.query(LongTermHoldingIncome).filter(
                LongTermHoldingIncome.holding_id == duplicate.id
            ).first()
            if duplicate_income:
                primary_income = db.query(LongTermHoldingIncome).filter(
                    LongTermHoldingIncome.holding_id == holding.id
                ).first()
                if primary_income:
                    primary_income.amount += duplicate_income.amount
                else:
                    db.add(LongTermHoldingIncome(holding_id=holding.id, amount=duplicate_income.amount))
                db.delete(duplicate_income)
            db.delete(duplicate)
        merged = True
    else:
        holding = LongTermHolding(
            ticker=ticker,
            market=market,
            shares=item.shares,
            cost_basis=item.cost_basis,
            purchase_date=item.purchase_date,
            notes=item.notes,
        )
        db.add(holding)
        merged = False
    db.commit()
    db.refresh(holding)
    return {
        "id": holding.id,
        "ticker": holding.ticker,
        "merged": merged,
        "shares": holding.shares,
        "cost_basis": holding.cost_basis,
    }


@router.put("/holdings/{holding_id}")
def update_holding(holding_id: int, item: HoldingUpdate, db: Session = Depends(get_db)):
    holding = db.query(LongTermHolding).filter(LongTermHolding.id == holding_id).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding bulunamadı")
    for field, value in item.dict(exclude_unset=True).items():
        setattr(holding, field, value)
    db.commit()
    return {"id": holding.id}


@router.post("/holdings/{holding_id}/dividend")
def add_dividend(holding_id: int, item: DividendAdd, db: Session = Depends(get_db)):
    """Add a dividend received while the holding is part of the portfolio."""
    import math

    holding = db.query(LongTermHolding).filter(LongTermHolding.id == holding_id).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding bulunamadı")
    if not math.isfinite(item.amount) or item.amount <= 0:
        raise HTTPException(status_code=400, detail="Temettü tutarı sıfırdan büyük olmalı")

    income = db.query(LongTermHoldingIncome).filter(
        LongTermHoldingIncome.holding_id == holding.id
    ).first()
    if income:
        income.amount += item.amount
    else:
        income = LongTermHoldingIncome(holding_id=holding.id, amount=item.amount)
        db.add(income)
    db.commit()
    return {"holding_id": holding.id, "dividend_total": income.amount}


@router.post("/holdings/{holding_id}/sell")
def sell_holding(holding_id: int, item: HoldingSell, db: Session = Depends(get_db)):
    """Sell part or all of a long-term holding.

    The remaining position keeps its existing average cost basis. A full sale
    removes the holding, matching the existing manual delete behavior.
    """
    holding = db.query(LongTermHolding).filter(LongTermHolding.id == holding_id).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding bulunamadı")
    import math

    if not math.isfinite(item.shares) or item.shares <= 0:
        raise HTTPException(status_code=400, detail="Satış adedi sıfırdan büyük olmalı")
    if item.shares > holding.shares:
        raise HTTPException(
            status_code=400,
            detail=f"Satış adedi mevcut adetten fazla olamaz ({holding.shares:g})",
        )
    if item.sale_price is not None and (not math.isfinite(item.sale_price) or item.sale_price <= 0):
        raise HTTPException(status_code=400, detail="Satış fiyatı sıfırdan büyük olmalı")

    remaining = holding.shares - item.shares
    # Avoid tiny floating-point remnants after selling the full position.
    fully_sold = remaining <= 1e-9
    income = db.query(LongTermHoldingIncome).filter(
        LongTermHoldingIncome.holding_id == holding.id
    ).first()
    if income:
        income.amount *= remaining / holding.shares if not fully_sold else 0
        if fully_sold:
            db.delete(income)
    db.add(LongTermSale(
        holding_id=holding.id,
        ticker=holding.ticker,
        market=holding.market,
        shares=item.shares,
        sale_price=item.sale_price,
        sale_date=item.sale_date or date.today(),
        notes=item.notes,
    ))
    if fully_sold:
        db.query(LongTermPortfolioAdvice).filter(LongTermPortfolioAdvice.holding_id == holding.id).delete()
        db.delete(holding)
    else:
        holding.shares = remaining
        if item.notes:
            holding.notes = f"{holding.notes}\nSatış: {item.notes}".strip()
    db.commit()
    return {
        "id": holding_id,
        "sold_shares": item.shares,
        "remaining_shares": 0 if fully_sold else remaining,
        "fully_sold": fully_sold,
        "sale_price": item.sale_price,
        "sale_date": item.sale_date.isoformat() if item.sale_date else None,
    }


@router.delete("/holdings/{holding_id}")
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    holding = db.query(LongTermHolding).filter(LongTermHolding.id == holding_id).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding bulunamadı")
    db.query(LongTermHoldingIncome).filter(LongTermHoldingIncome.holding_id == holding.id).delete()
    db.query(LongTermPortfolioAdvice).filter(LongTermPortfolioAdvice.holding_id == holding.id).delete()
    db.delete(holding)
    db.commit()
    return {"deleted": holding_id}


# ============= Watchlist =============


@router.get("/watchlist")
def list_watchlist(db: Session = Depends(get_db)):
    items = db.query(LongTermWatchlistItem).order_by(LongTermWatchlistItem.added_at.desc()).all()
    snaps = {s.ticker: s for s in db.query(FundamentalSnapshot).all()}
    out = []
    for it in items:
        snap = snaps.get(it.ticker)
        out.append({
            "id": it.id,
            "ticker": it.ticker,
            "symbol": it.ticker.replace(".IS", ""),
            "market": it.market,
            "notes": it.notes,
            "scores": _snapshot_summary(snap) if snap else None,
        })
    fund_snaps = {s.ticker: s for s in db.query(FundSnapshot).all()}
    fund_out = [
        {
            "id": item.id,
            "ticker": item.ticker,
            "symbol": item.ticker.replace(".IS", ""),
            "market": item.market,
            "asset_type": item.asset_type,
            "notes": item.notes,
            "analysis": _fund_snapshot_row(
                fund_snaps.get(item.ticker), item.ticker, item.market, item.asset_type
            ),
        }
        for item in db.query(LongTermFundWatchlistItem)
        .order_by(LongTermFundWatchlistItem.added_at.desc())
        .all()
    ]
    return {"watchlist": out, "fund_watchlist": fund_out}


@router.post("/watchlist")
def add_watchlist(item: WatchlistCreate, db: Session = Depends(get_db)):
    ticker = item.ticker.strip().upper()
    exists = (
        db.query(LongTermWatchlistItem)
        .filter(LongTermWatchlistItem.ticker == ticker)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Zaten izleme listesinde")
    wl = LongTermWatchlistItem(ticker=ticker, market=_norm(ticker, item.market), notes=item.notes)
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return {"id": wl.id, "ticker": wl.ticker}


@router.delete("/watchlist/{item_id}")
def delete_watchlist(item_id: int, db: Session = Depends(get_db)):
    item = db.query(LongTermWatchlistItem).filter(LongTermWatchlistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Bulunamadı")
    db.delete(item)
    db.commit()
    return {"deleted": item_id}


# ============= Funds & ETFs =============


def _fund_holding_rows(db: Session) -> list[dict]:
    holdings = db.query(LongTermFundHolding).order_by(LongTermFundHolding.created_at.desc()).all()
    snaps = {s.ticker: s for s in db.query(FundSnapshot).all()}
    rows = []
    for holding in holdings:
        snap = snaps.get(holding.ticker)
        analysis = _fund_snapshot_row(snap, holding.ticker, holding.market, holding.asset_type)
        price = None if analysis.get("data_source") == "tefas" else _live_price(holding.ticker)
        if price is None:
            price = analysis.get("price")
        currency = get_market_config(holding.market)["currency_symbol"]
        cost_value = holding.units * holding.cost_basis
        market_value = holding.units * price if price is not None else None
        pnl = market_value - cost_value if market_value is not None else None
        pnl_pct = pnl / cost_value * 100 if pnl is not None and cost_value else None
        rows.append({
            "id": holding.id,
            "ticker": holding.ticker,
            "symbol": holding.ticker.replace(".IS", ""),
            "market": holding.market,
            "asset_type": holding.asset_type,
            "units": holding.units,
            "cost_basis": holding.cost_basis,
            "purchase_date": holding.purchase_date.isoformat() if holding.purchase_date else None,
            "notes": holding.notes,
            "currency": currency,
            "price": round(price, 4) if price is not None else None,
            "cost_value": round(cost_value, 2),
            "market_value": round(market_value, 2) if market_value is not None else None,
            "pnl": round(pnl, 2) if pnl is not None else None,
            "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
            "analysis": analysis,
        })
    return rows


@router.get("/funds/holdings")
def list_fund_holdings(db: Session = Depends(get_db)):
    return {"holdings": _fund_holding_rows(db)}


@router.post("/funds/holdings")
def add_fund_holding(item: FundHoldingCreate, db: Session = Depends(get_db)):
    import math

    market = _norm(item.ticker, item.market)
    ticker = _normalize_fund_ticker(item.ticker, market, item.asset_type)
    asset_type = item.asset_type.lower()
    if asset_type not in ("etf", "fund"):
        raise HTTPException(status_code=400, detail="Varlık türü etf veya fund olmalı")
    if not math.isfinite(item.units) or item.units <= 0:
        raise HTTPException(status_code=400, detail="Adet sıfırdan büyük olmalı")
    if not math.isfinite(item.cost_basis) or item.cost_basis <= 0:
        raise HTTPException(status_code=400, detail="Maliyet sıfırdan büyük olmalı")

    holding = db.query(LongTermFundHolding).filter(
        LongTermFundHolding.ticker == ticker,
        LongTermFundHolding.market == market,
    ).first()
    if holding:
        total_units = holding.units + item.units
        holding.cost_basis = (
            holding.units * holding.cost_basis + item.units * item.cost_basis
        ) / total_units
        holding.units = total_units
        if item.notes:
            holding.notes = f"{holding.notes}\nAlış: {item.notes}".strip()
        merged = True
    else:
        holding = LongTermFundHolding(
            ticker=ticker,
            market=market,
            asset_type=asset_type,
            units=item.units,
            cost_basis=item.cost_basis,
            purchase_date=item.purchase_date,
            notes=item.notes,
        )
        db.add(holding)
        merged = False
    db.commit()
    db.refresh(holding)
    return {"id": holding.id, "ticker": holding.ticker, "merged": merged}


@router.post("/funds/holdings/{holding_id}/sell")
def sell_fund_holding(holding_id: int, item: FundHoldingSell, db: Session = Depends(get_db)):
    import math

    holding = db.query(LongTermFundHolding).filter(LongTermFundHolding.id == holding_id).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Fon/ETF pozisyonu bulunamadı")
    if not math.isfinite(item.units) or item.units <= 0 or item.units > holding.units:
        raise HTTPException(status_code=400, detail="Geçerli bir satış adedi gir")
    remaining = holding.units - item.units
    fully_sold = remaining <= 1e-9
    if fully_sold:
        db.delete(holding)
    else:
        holding.units = remaining
    db.commit()
    return {"sold_units": item.units, "remaining_units": 0 if fully_sold else remaining, "fully_sold": fully_sold}


@router.delete("/funds/holdings/{holding_id}")
def delete_fund_holding(holding_id: int, db: Session = Depends(get_db)):
    holding = db.query(LongTermFundHolding).filter(LongTermFundHolding.id == holding_id).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Fon/ETF pozisyonu bulunamadı")
    db.delete(holding)
    db.commit()
    return {"deleted": holding_id}


@router.get("/funds/watchlist")
def list_fund_watchlist(db: Session = Depends(get_db)):
    snaps = {s.ticker: s for s in db.query(FundSnapshot).all()}
    rows = []
    for item in db.query(LongTermFundWatchlistItem).order_by(LongTermFundWatchlistItem.added_at.desc()).all():
        rows.append({
            "id": item.id,
            "ticker": item.ticker,
            "symbol": item.ticker.replace(".IS", ""),
            "market": item.market,
            "asset_type": item.asset_type,
            "notes": item.notes,
            "analysis": _fund_snapshot_row(snaps.get(item.ticker), item.ticker, item.market, item.asset_type),
        })
    return {"watchlist": rows}


@router.post("/funds/watchlist")
def add_fund_watchlist(item: FundWatchlistCreate, db: Session = Depends(get_db)):
    market = _norm(item.ticker, item.market)
    ticker = _normalize_fund_ticker(item.ticker, market, item.asset_type)
    asset_type = item.asset_type.lower()
    if asset_type not in ("etf", "fund"):
        raise HTTPException(status_code=400, detail="Varlık türü etf veya fund olmalı")
    exists = db.query(LongTermFundWatchlistItem).filter(LongTermFundWatchlistItem.ticker == ticker).first()
    if exists:
        raise HTTPException(status_code=400, detail="Fon/ETF zaten izleme listesinde")
    row = LongTermFundWatchlistItem(
        ticker=ticker,
        market=market,
        asset_type=asset_type,
        notes=item.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "ticker": row.ticker}


@router.delete("/funds/watchlist/{item_id}")
def delete_fund_watchlist(item_id: int, db: Session = Depends(get_db)):
    item = db.query(LongTermFundWatchlistItem).filter(LongTermFundWatchlistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Fon/ETF bulunamadı")
    db.delete(item)
    db.commit()
    return {"deleted": item_id}


@router.get("/funds/analysis/{ticker}")
def get_fund_analysis(ticker: str, market: Optional[str] = None, asset_type: Optional[str] = None, db: Session = Depends(get_db)):
    market = normalize_market(market) if market else infer_market(ticker)
    asset_type = (asset_type or "etf").lower()
    ticker = _normalize_fund_ticker(ticker, market, asset_type)
    report = (
        fund_service.analyze_tefas(ticker, asset_type)
        if market == "bist" and asset_type == "fund"
        else fund_service.analyze(ticker, market, asset_type)
    )
    if report.get("valid"):
        _upsert_fund_snapshot(db, report)
        db.commit()
    return report


@router.post("/funds/scan")
async def scan_funds(body: FundScanRequest, db: Session = Depends(get_db)):
    if body.universe == "tefas_top30":
        try:
            reports = await asyncio.to_thread(fund_service.tefas_reports, "YAT", 30)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"TEFAS verisi alınamadı: {exc}") from exc
        # Keep old snapshots for portfolio/watchlist history, but hide funds
        # that have dropped out of the current largest-30 screener universe.
        for snap in db.query(FundSnapshot).all():
            data = dict(snap.data or {})
            if data.get("data_source") == "tefas" and data.get("asset_type") == "fund":
                data["in_top30"] = False
                snap.data = data
        for report in reports:
            report["in_top30"] = True
            _upsert_fund_snapshot(db, report)
        db.commit()
        return {"scanned": len(reports), "valid": len(reports), "errors": 0}

    tickers = [t.strip().upper() for t in body.tickers or [] if t.strip()]
    if body.universe:
        tickers.extend(fund_service.universe(body.universe))
    tickers = [
        _normalize_fund_ticker(ticker, body.market, body.asset_type) if body.market else ticker
        for ticker in tickers
    ]
    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        raise HTTPException(status_code=400, detail="Taranacak fon/ETF yok")

    metadata: dict[str, tuple[str, str, Optional[str]]] = {}
    for holding in db.query(LongTermFundHolding).all():
        metadata[holding.ticker] = (holding.market, holding.asset_type, None)
    for item in db.query(LongTermFundWatchlistItem).all():
        metadata[item.ticker] = (item.market, item.asset_type, None)
    for snap in db.query(FundSnapshot).all():
        source = (snap.data or {}).get("data_source")
        metadata[snap.ticker] = (snap.market, snap.asset_type, source)

    tefas_groups: dict[str, set[str]] = {"YAT": set(), "BYF": set()}
    yahoo_items: list[tuple[str, str, Optional[str]]] = []
    for ticker in tickers:
        known_market, known_type, source = metadata.get(
            ticker,
            (body.market or infer_market(ticker), body.asset_type or "etf", None),
        )
        market = normalize_market(known_market)
        asset_type = (body.asset_type or known_type or "etf").lower()
        if source == "tefas" or (market == "bist" and asset_type == "fund"):
            tefas_groups["BYF" if asset_type == "etf" else "YAT"].add(ticker.removesuffix(".IS"))
        else:
            yahoo_items.append((ticker, market, asset_type))

    reports = []
    for fund_type, requested in tefas_groups.items():
        if not requested:
            continue
        try:
            available = await asyncio.to_thread(fund_service.tefas_reports, fund_type, None)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"TEFAS verisi alınamadı: {exc}") from exc
        reports.extend(report for report in available if report["ticker"] in requested)

    semaphore = asyncio.Semaphore(6)

    async def worker(item: tuple[str, str, Optional[str]]):
        ticker, market, asset_type = item
        async with semaphore:
            return await asyncio.to_thread(fund_service.analyze, ticker, market, asset_type)

    reports.extend(await asyncio.gather(*(worker(item) for item in yahoo_items)))
    valid = 0
    for report in reports:
        if report.get("valid"):
            _upsert_fund_snapshot(db, report)
            valid += 1
    db.commit()
    return {"scanned": len(tickers), "valid": valid, "errors": len(tickers) - valid}


@router.get("/funds/screener")
def fund_screener(db: Session = Depends(get_db)):
    rows = [
        snap.data for snap in db.query(FundSnapshot).all()
        if snap.data and snap.data.get("in_top30") is not False
    ]
    rows.sort(key=lambda row: row.get("score") if row.get("score") is not None else -1, reverse=True)
    return {"count": len(rows), "results": rows}


@router.delete("/funds/screener/{ticker}")
def delete_fund_snapshot(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.strip().upper()
    deleted = db.query(FundSnapshot).filter(FundSnapshot.ticker == ticker).delete()
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Fon/ETF bulunamadı")
    return {"deleted": ticker}


# ============= Analysis / Screener =============


@router.get("/analysis/{ticker}")
def get_analysis(ticker: str, market: Optional[str] = None, force: bool = True, db: Session = Depends(get_db)):
    """Full fundamental report for one ticker (fetch + overrides + scores).

    `market` ("bist"/"us") lets the caller omit the `.IS` suffix for BIST.
    """
    ticker = _normalize_ticker(ticker, market)
    overrides = _get_override_fields(db, ticker)
    report = fundamental_service.analyze(ticker, overrides)
    report["overrides"] = overrides
    _upsert_snapshot(db, report)
    db.commit()
    _attach_value_to_report(report, db)
    return report


def _attach_value_to_report(report: dict, db: Session):
    """Compute a sector-relative value score for a single report using cached peers."""
    metrics = report.get("metrics", {})
    sector = metrics.get("sector")
    report["value_score"] = None
    if not sector:
        return
    peers = [
        s.metrics for s in db.query(FundamentalSnapshot).all()
        if (s.metrics or {}).get("sector") == sector
    ]
    report["value_score"] = _value_score(metrics, peers)


@router.put("/overrides/{ticker}")
def set_overrides(ticker: str, body: OverrideUpdate, market: Optional[str] = None, db: Session = Depends(get_db)):
    """Save manual fundamental overrides, then re-analyze and return the report."""
    ticker = _normalize_ticker(ticker, market)
    ov = db.query(FundamentalOverride).filter(FundamentalOverride.ticker == ticker).first()
    # keep only known, non-null fields
    clean = {
        k: v for k, v in (body.fields or {}).items()
        if k in fundamental_service.ALL_OVERRIDABLE_FIELDS and v is not None and v != ""
    }
    if not ov:
        ov = FundamentalOverride(ticker=ticker, fields=clean)
        db.add(ov)
    else:
        ov.fields = clean
        ov.updated_at = now_turkey()
    db.commit()

    report = fundamental_service.analyze(ticker, clean)
    report["overrides"] = clean
    _upsert_snapshot(db, report)
    db.commit()
    _attach_value_to_report(report, db)
    return report


async def _broadcast_scan(data: dict):
    try:
        await manager.broadcast({"type": "investing_scan", "data": data})
    except Exception as e:
        print(f"[Investing] scan broadcast failed: {e}")


# How many tickers to fetch from yfinance at once. The codebase already uses
# 8-15 concurrent yfinance calls elsewhere (EOD/news) without rate-limit issues;
# keep it moderate so Yahoo doesn't return 429.
_SCAN_CONCURRENCY = 8


def _days_until(value) -> Optional[int]:
    if not value:
        return None
    try:
        return (date.fromisoformat(str(value)[:10]) - date.today()).days
    except (TypeError, ValueError):
        return None


def _portfolio_advice(report: dict, technical: dict, pnl_pct: Optional[float]) -> dict:
    """Build a transparent 12+ month hold/add/review score.

    Daily RSI and short-term overbought readings must not turn a long-term
    holding into a sell signal. Fundamental deterioration is intentionally the
    strongest reason to reduce; a technically weak but fundamentally healthy
    holding can instead become an accumulate-on-weakness candidate.
    """
    metrics = report.get("metrics") or {}
    available = []

    def ramp(value, low, high):
        if value is None:
            return None
        return max(0.0, min(100.0, (float(value) - low) / (high - low) * 100))

    quality_parts = [
        ramp(metrics.get("roe"), 0, 30),
        ramp(metrics.get("profit_margin"), 0, 25),
        ramp(metrics.get("revenue_growth"), 0, 30),
        (100 - max(0.0, min(100.0, (float(metrics["debt_to_equity"]) - 50) / 150 * 100)))
        if metrics.get("debt_to_equity") is not None else None,
    ]
    quality_parts = [x for x in quality_parts if x is not None]
    quality = sum(quality_parts) / len(quality_parts) if quality_parts else None
    overall = report.get("overall_score")
    fundamental = (
        (float(overall) * 0.6 + quality * 0.4) if overall is not None and quality is not None
        else float(overall) if overall is not None
        else quality
    )
    if fundamental is not None:
        available.append("temel")

    tech = (technical or {}).get("technical") or {}
    price_vs_ema200 = tech.get("price_vs_ema200")
    drawdown = tech.get("drawdown")
    if price_vs_ema200 is None:
        technical_score = None
    elif price_vs_ema200 >= 8:
        technical_score = 85.0
    elif price_vs_ema200 >= 0:
        technical_score = 70.0
    elif price_vs_ema200 >= -10:
        technical_score = 50.0
    else:
        technical_score = 30.0
    if technical_score is not None:
        available.append("teknik")

    ex_days = _days_until((report.get("calendar") or {}).get("ex_dividend_date"))
    if ex_days is None:
        dividend_timing = 50.0
    elif 0 <= ex_days <= 30:
        dividend_timing = 90.0
    elif 31 <= ex_days <= 90:
        dividend_timing = 70.0
    elif ex_days < 0:
        dividend_timing = 40.0
    else:
        dividend_timing = 55.0
    if ex_days is not None:
        available.append("temettü takvimi")

    earnings_days = _days_until((report.get("calendar") or {}).get("earnings_date"))
    if earnings_days is not None and 0 <= earnings_days <= 14:
        earnings_risk = 55.0
    elif earnings_days is not None and 15 <= earnings_days <= 30:
        earnings_risk = 65.0
    else:
        earnings_risk = 70.0
    if earnings_days is not None:
        available.append("bilanço takvimi")

    # For a long-term investor, drawdowns are not automatically negative.
    # Strong fundamentals + a large drawdown is a possible staged-buy setup.
    position_score = 60.0
    if pnl_pct is not None and pnl_pct <= -20 and (fundamental or 0) >= 60:
        position_score = 80.0

    components = {
        "fundamental": round(fundamental, 1) if fundamental is not None else None,
        "technical": round(float(technical_score), 1) if technical_score is not None else None,
        "dividend_timing": round(dividend_timing, 1),
        "earnings_risk": round(earnings_risk, 1),
        "position": round(position_score, 1),
    }
    weighted = [
        (fundamental, 0.50),
        (technical_score, 0.25),
        (dividend_timing, 0.10),
        (earnings_risk, 0.05),
        (position_score, 0.10),
    ]
    known = [(value, weight) for value, weight in weighted if value is not None]
    score = round(sum(value * weight for value, weight in known) / sum(weight for _, weight in known)) if known else None

    reasons = []
    if fundamental is not None:
        reasons.append(f"Temel/bilanço skoru {fundamental:.0f}/100")
    if technical_score is not None:
        reasons.append(f"Uzun vadeli trend skoru {technical_score:.0f}/100 ({tech.get('trend', '—')})")
    if ex_days is not None and 0 <= ex_days <= 30:
        reasons.append(f"Ex-temettü tarihi {ex_days} gün içinde")
    if earnings_days is not None and 0 <= earnings_days <= 14:
        reasons.append(f"Bilanço açıklaması yaklaşık {earnings_days} gün içinde; oynaklık riski var")
    if pnl_pct is not None and pnl_pct <= -20 and (fundamental or 0) >= 60:
        reasons.append("Düşüş var ama temel skor güçlü; panik satışı yerine kademeli alım değerlendirilebilir")
    if earnings_days is not None and 0 <= earnings_days <= 14:
        reasons.append("Yaklaşan bilanço kısa vadeli oynaklık yaratabilir; uzun vadeli karar için tek başına satış sebebi değil")
    if not reasons:
        reasons.append("Yeterli analiz verisi oluşmadı; kararı tek başına bu puana göre verme")

    if score is None:
        action = "VERİ YETERSİZ"
    # A reduce signal requires a genuine long-term breakdown: very weak
    # fundamentals AND a broken long-term trend. Normal drawdowns, high RSI,
    # profit-taking and an upcoming earnings date never trigger it alone.
    elif (
        fundamental is not None
        and fundamental < 30
        and technical_score is not None
        and technical_score <= 30
    ):
        action = "KADEMELİ AZALT"
        reasons.append("Temel/bilanço göstergeleri çok zayıf ve uzun vadeli trend kırılmış; yatırım tezini yeniden değerlendir")
    elif fundamental is not None and fundamental >= 60 and drawdown is not None and drawdown <= -15:
        action = "DÜŞÜŞTE KADEMELİ AL"
    elif score >= 55:
        action = "TUT"
    else:
        action = "İZLE / TUT"
    return {
        "horizon": "uzun vade (12+ ay)",
        "score": score,
        "action": action,
        "confidence": round(min(100, len(available) / 4 * 100)),
        "components": components,
        "reasons": reasons,
        "updated_at": datetime.now().isoformat(),
    }


async def _run_scan(tickers: List[str], label: str, portfolio: bool = False):
    """Background bulk scan: score each ticker (.info only), cache, stream progress.

    yfinance fetches run in a bounded thread pool (concurrency-limited) so the
    network work overlaps; DB writes and broadcasts happen back on the event loop
    (single-threaded => safe for the one SQLite session).
    """
    total = len(tickers)
    count = 0
    errors = 0
    done = 0
    skipped: List[str] = []
    print(f"[Investing] Scan started: {label} ({total} hisse, {_SCAN_CONCURRENCY}x paralel)")
    await _broadcast_scan({"status": "started", "current": 0, "total": total, "ticker": None, "label": label})

    db = SessionLocal()
    # pre-load overrides once (avoid per-ticker DB reads inside workers)
    overrides_map = {o.ticker: (o.fields or {}) for o in db.query(FundamentalOverride).all()}
    holdings_map = {h.ticker: h for h in db.query(LongTermHolding).all()} if portfolio else {}
    sem = asyncio.Semaphore(_SCAN_CONCURRENCY)

    async def _worker(t: str):
        nonlocal count, errors, done
        try:
            async with sem:
                # network + compute in a thread; statements off for speed
                report = await asyncio.to_thread(
                    fundamental_service.analyze, t, overrides_map.get(t), portfolio
                )
                technical = await asyncio.to_thread(fundamental_service.fetch_technical, t) if portfolio else None
            # back on the event loop: DB + broadcast are serialized here
            if report.get("valid"):
                _upsert_snapshot(db, report)
                if portfolio and t in holdings_map:
                    holding = holdings_map[t]
                    price = report.get("price")
                    pnl_pct = ((price - holding.cost_basis) / holding.cost_basis * 100) if price is not None and holding.cost_basis else None
                    advice = _portfolio_advice(report, technical, pnl_pct)
                    existing = db.query(LongTermPortfolioAdvice).filter(
                        LongTermPortfolioAdvice.holding_id == holding.id
                    ).first()
                    if existing:
                        existing.ticker = t
                        existing.advice = advice
                    else:
                        db.add(LongTermPortfolioAdvice(holding_id=holding.id, ticker=t, advice=advice))
                db.commit()
                count += 1
            else:
                skipped.append(t.replace(".IS", ""))
        except Exception as e:
            errors += 1
            print(f"[Investing] {t} hata: {e}")
        done += 1
        if done % 10 == 0 or done == total:
            print(f"[Investing] {label}: {done}/{total} (skor={count}, atlanan={len(skipped)}, hata={errors})")
        await _broadcast_scan({
            "status": "running", "current": done, "total": total,
            "ticker": t.replace(".IS", ""), "label": label,
        })

    try:
        await asyncio.gather(*(_worker(t) for t in tickers))
    finally:
        db.close()
        _scan_state["running"] = False

    print(f"[Investing] Scan done: {label} | skor={count}, atlanan={len(skipped)}, hata={errors}")
    await _broadcast_scan({
        "status": "completed", "current": total, "total": total,
        "label": label, "count": count, "skipped": skipped, "errors": errors,
    })


@router.post("/scan")
async def scan(body: ScanRequest, db: Session = Depends(get_db)):
    """Kick off a manual bulk fundamental scan in the background.

    Returns immediately; progress streams over the websocket as
    `{"type":"investing_scan", ...}`. One scan at a time.
    """
    if _scan_state["running"]:
        raise HTTPException(status_code=409, detail="Zaten bir tarama çalışıyor")

    if body.use_watchlist:
        tickers = [w.ticker for w in db.query(LongTermWatchlistItem).all()]
        label = "İzleme listesi"
    elif body.tickers:
        tickers = [t.strip().upper() for t in body.tickers]
        label = "Liste"
    elif body.market:
        mkt = normalize_market(body.market)
        uni = body.universe
        if mkt == "bist":
            from financia.bist100_tickers import get_bist_tickers

            if uni == "all":
                tickers = get_bist_tickers("all")
                label = "Tüm BIST"
            else:
                tickers = get_bist_tickers("100")
                label = "BIST 100"
        else:
            from financia.us_tickers import get_us_tickers

            if uni == "ext":
                tickers = get_us_tickers("ext")
                label = "ABD (Geniş)"
            else:
                tickers = get_us_tickers("100")
                label = "S&P 100"
    else:
        raise HTTPException(status_code=400, detail="market, tickers veya use_watchlist gerekli")

    if body.limit:
        tickers = tickers[: body.limit]
    if not tickers:
        raise HTTPException(status_code=400, detail="Taranacak hisse yok")

    _scan_state["running"] = True
    asyncio.create_task(_run_scan(tickers, label, body.portfolio))
    return {"status": "started", "total": len(tickers), "label": label}


@router.get("/scan/status")
def scan_status():
    return {"running": _scan_state["running"]}


@router.get("/screener")
def screener(db: Session = Depends(get_db)):
    """Last cached snapshots, ranked by overall score (with sector value score)."""
    snaps = db.query(FundamentalSnapshot).all()
    rows = _attach_value_scores([_snapshot_summary(s) for s in snaps])
    rows.sort(key=lambda r: (r.get("overall_score") or -1), reverse=True)
    return {"count": len(rows), "results": rows}


@router.delete("/screener")
def clear_screener(db: Session = Depends(get_db)):
    """Remove all cached screener snapshots."""
    n = db.query(FundamentalSnapshot).delete()
    db.commit()
    return {"deleted": n}


@router.delete("/screener/{ticker}")
def delete_snapshot(ticker: str, db: Session = Depends(get_db)):
    """Remove one ticker from the screener cache."""
    ticker = ticker.strip().upper()
    n = (
        db.query(FundamentalSnapshot)
        .filter(FundamentalSnapshot.ticker == ticker)
        .delete()
    )
    db.commit()
    if not n:
        raise HTTPException(status_code=404, detail="Bulunamadı")
    return {"deleted": ticker}


# ============= News & events feed =============


@router.get("/chart-data/{ticker}")
def chart_data(ticker: str, market: Optional[str] = None):
    """Daily candles + EMA50/EMA200 + RSI + an entry-level technical score for one ticker."""
    ticker = _normalize_ticker(ticker, market)
    return fundamental_service.fetch_technical(ticker)


@router.get("/news/{ticker}")
def ticker_news(ticker: str, market: Optional[str] = None):
    """Recent news + upcoming earnings/dividend dates for a single ticker."""
    ticker = _normalize_ticker(ticker, market)
    mkt = normalize_market(market) if market else infer_market(ticker)
    feed = fundamental_service.fetch_news_and_events(ticker, mkt)
    return {"ticker": ticker, "symbol": ticker.replace(".IS", ""), "market": mkt, **feed}


@router.get("/news")
def news_feed(scope: str = "all", db: Session = Depends(get_db)):
    """Aggregate recent news + upcoming earnings/dividend dates for the tickers
    in the portfolio and/or watchlist (yfinance). `scope` = all|portfolio|watchlist.
    """
    from concurrent.futures import ThreadPoolExecutor

    # gather (ticker -> market), deduped
    tmap: Dict[str, str] = {}
    if scope in ("all", "portfolio"):
        for h in db.query(LongTermHolding).all():
            tmap.setdefault(h.ticker, h.market)
    if scope in ("all", "watchlist"):
        for w in db.query(LongTermWatchlistItem).all():
            tmap.setdefault(w.ticker, w.market)

    tickers = list(tmap.items())
    if not tickers:
        return {"tickers": 0, "news": [], "events": []}

    def _fetch(pair):
        ticker, market = pair
        feed = fundamental_service.fetch_news_and_events(ticker, market)
        return ticker, market, feed

    all_news = []
    events = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for ticker, market, feed in ex.map(_fetch, tickers):
            symbol = ticker.replace(".IS", "")
            for n in feed["news"]:
                if not n.get("title"):
                    continue
                all_news.append({**n, "ticker": ticker, "symbol": symbol, "market": market})
            if feed["earnings_date"] or feed["ex_dividend_date"] or feed["dividend_date"]:
                events.append({
                    "ticker": ticker,
                    "symbol": symbol,
                    "market": market,
                    "earnings_date": feed["earnings_date"],
                    "ex_dividend_date": feed["ex_dividend_date"],
                    "dividend_date": feed["dividend_date"],
                })

    # newest news first; events by soonest earnings date
    all_news.sort(key=lambda n: (n.get("published") or ""), reverse=True)
    events.sort(key=lambda e: (e.get("earnings_date") or "9999"))

    return {"tickers": len(tickers), "news": all_news, "events": events}


# ============= Dividend calendar / income =============


@router.get("/dividends/calendar")
def dividends_calendar(db: Session = Depends(get_db)):
    """Projected annual dividend income from holdings, per currency.

    Uses each holding's dividend yield (from cached snapshot, else live fetch)
    applied to current market value.
    """
    holdings = db.query(LongTermHolding).all()
    snaps = {s.ticker: s for s in db.query(FundamentalSnapshot).all()}

    income: Dict[str, float] = {}
    rows = []
    for h in holdings:
        cur = get_market_config(h.market)["currency_symbol"]
        snap = snaps.get(h.ticker)
        yield_pct = (snap.metrics or {}).get("dividend_yield") if snap else None
        price = _live_price(h.ticker)
        market_value = h.shares * price if price is not None else None
        annual = (
            market_value * (yield_pct / 100.0)
            if (market_value is not None and yield_pct)
            else None
        )
        if annual:
            income[cur] = income.get(cur, 0.0) + annual
        rows.append({
            "ticker": h.ticker,
            "symbol": h.ticker.replace(".IS", ""),
            "market": h.market,
            "sector": (snap.metrics or {}).get("sector") if snap else None,
            "industry": (snap.metrics or {}).get("industry") if snap else None,
            "currency": cur,
            "shares": h.shares,
            "dividend_yield": yield_pct,
            "annual_income": round(annual, 2) if annual is not None else None,
            "has_snapshot": snap is not None,
        })

    return {
        "holdings": rows,
        "projected_annual_income": [
            {"currency": c, "amount": round(v, 2)} for c, v in income.items()
        ],
    }


# ============= Diversification / concentration risk =============


def _usdtry_rate() -> Optional[float]:
    """USD/TRY exchange rate (to unify ₺ and $ holdings into one base)."""
    for sym in ("USDTRY=X", "TRY=X"):
        r = _live_price(sym)
        if r:
            return r
    return None


@router.get("/diversification")
def diversification(
    sector_threshold: float = 40.0,
    position_threshold: float = 25.0,
    currency_threshold: float = 85.0,
    db: Session = Depends(get_db),
):
    """Concentration-risk view of the portfolio.

    Converts ₺ and $ holdings to a common base (TRY, via USD/TRY) and reports
    sector / single-position / currency weights plus threshold warnings.
    """
    from concurrent.futures import ThreadPoolExecutor

    holdings = db.query(LongTermHolding).all()
    fund_holdings = db.query(LongTermFundHolding).all()
    if not holdings and not fund_holdings:
        return {"holdings": 0, "warnings": [], "sectors": [], "positions": [], "currencies": []}

    snaps = {s.ticker: s for s in db.query(FundamentalSnapshot).all()}
    usdtry = _usdtry_rate()

    def _enrich(h):
        snap = snaps.get(h.ticker)
        sector = (snap.metrics or {}).get("sector") if snap else None
        price = None
        if sector is None:
            # no cached sector -> fetch sector (and price) from yfinance
            data = fundamental_service.fetch_fundamentals(h.ticker, include_statements=False)
            sector = (data.get("metrics") or {}).get("sector")
            price = data.get("price")
        if price is None:
            price = _live_price(h.ticker)
        return h, sector, price

    with ThreadPoolExecutor(max_workers=8) as ex:
        enriched = list(ex.map(_enrich, holdings))

    fx_ok = True
    sector_vals: Dict[str, float] = {}
    currency_vals: Dict[str, float] = {}
    positions = []
    total_base = 0.0

    for h, sector, price in enriched:
        cur = get_market_config(h.market)["currency_symbol"]
        mv = (h.shares * price) if price else 0.0
        # convert to base TRY
        if normalize_market(h.market) == "us":
            if usdtry:
                base = mv * usdtry
            else:
                fx_ok = False
                base = mv  # cannot convert; counts raw (flagged below)
        else:
            base = mv
        total_base += base
        sec = sector or "Bilinmiyor"
        sector_vals[sec] = sector_vals.get(sec, 0.0) + base
        currency_vals[cur] = currency_vals.get(cur, 0.0) + base
        positions.append({"symbol": h.ticker.replace(".IS", ""), "market": h.market, "sector": sec, "base": base, "asset_type": "stock"})

    fund_snaps = {s.ticker: s for s in db.query(FundSnapshot).all()}
    for holding in fund_holdings:
        snap = fund_snaps.get(holding.ticker)
        data = (snap.data or {}) if snap else {}
        price = None if data.get("data_source") == "tefas" else _live_price(holding.ticker)
        price = price or data.get("price")
        cur = get_market_config(holding.market)["currency_symbol"]
        mv = holding.units * price if price else 0.0
        if normalize_market(holding.market) == "us":
            if usdtry:
                base = mv * usdtry
            else:
                fx_ok = False
                base = mv
        else:
            base = mv
        total_base += base
        category = data.get("category") or ("ETF" if holding.asset_type == "etf" else "Yatırım Fonu")
        sec = f"Fon/ETF · {category}"
        sector_vals[sec] = sector_vals.get(sec, 0.0) + base
        currency_vals[cur] = currency_vals.get(cur, 0.0) + base
        positions.append({
            "symbol": holding.ticker.replace(".IS", ""),
            "market": holding.market,
            "sector": sec,
            "base": base,
            "asset_type": holding.asset_type,
        })

    def _pct(v):
        return round(v / total_base * 100, 1) if total_base else 0.0

    sectors = sorted(
        [{"sector": s, "weight": _pct(v)} for s, v in sector_vals.items()],
        key=lambda x: x["weight"], reverse=True,
    )
    currencies = sorted(
        [{"currency": c, "weight": _pct(v)} for c, v in currency_vals.items()],
        key=lambda x: x["weight"], reverse=True,
    )
    pos_out = sorted(
        [{"symbol": p["symbol"], "market": p["market"], "sector": p["sector"], "asset_type": p["asset_type"], "weight": _pct(p["base"])} for p in positions],
        key=lambda x: x["weight"], reverse=True,
    )

    # --- warnings ---
    warnings = []
    for s in sectors:
        if s["sector"] != "Bilinmiyor" and s["weight"] > sector_threshold:
            warnings.append({"level": "high", "message": f"{s['sector']} sektörü portföyün %{s['weight']}'i — yoğunlaşma yüksek (eşik %{sector_threshold:g})."})
    for p in pos_out:
        if p["weight"] > position_threshold:
            warnings.append({"level": "high", "message": f"{p['symbol']} tek başına %{p['weight']} — tek pozisyon yüksek (eşik %{position_threshold:g})."})
    for c in currencies:
        if c["weight"] > currency_threshold:
            warnings.append({"level": "medium", "message": f"Portföyün %{c['weight']}'i {c['currency']} cinsinden — kur riski yüksek."})
    total_positions = len(holdings) + len(fund_holdings)
    if total_positions < 4:
        warnings.append({"level": "medium", "message": f"Yalnızca {total_positions} pozisyon var — çeşitlendirme düşük."})
    if not fx_ok:
        warnings.append({"level": "info", "message": "USD/TRY kuru alınamadı; $ pozisyonlar dönüştürülemedi, ağırlıklar yaklaşıktır."})
    if not warnings:
        warnings.append({"level": "ok", "message": "Belirgin bir yoğunlaşma riski görünmüyor."})

    return {
        "holdings": total_positions,
        "base_currency": "₺",
        "usdtry": usdtry,
        "total_base": round(total_base, 2),
        "warnings": warnings,
        "sectors": sectors,
        "positions": pos_out,
        "currencies": currencies,
    }
