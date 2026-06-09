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
    LongTermWatchlistItem,
    FundamentalSnapshot,
    FundamentalOverride,
)
from financia.web_api.websocket_manager import manager
from financia.markets import normalize_market, get_market_config, get_market_tickers, infer_market
from financia import fundamental_service

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


class WatchlistCreate(BaseModel):
    ticker: str
    market: Optional[str] = None
    notes: str = ""


class ScanRequest(BaseModel):
    market: Optional[str] = None  # "bist" | "us" : scan that universe
    tickers: Optional[List[str]] = None  # explicit list
    use_watchlist: bool = False  # scan the long-term watchlist
    limit: Optional[int] = None  # cap number of tickers (full-market scans are slow)


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

    rows = []
    # value totals per currency symbol so BIST (₺) and US ($) stay separate
    totals: Dict[str, float] = {}
    price_cache: Dict[str, Optional[float]] = {}
    for h in holdings:
        if h.ticker not in price_cache:
            price_cache[h.ticker] = _live_price(h.ticker)
        price = price_cache[h.ticker]
        cur = get_market_config(h.market)["currency_symbol"]
        snap = snaps.get(h.ticker)
        sector = (snap.metrics or {}).get("sector") if snap else None
        cost_value = h.shares * h.cost_basis
        market_value = h.shares * price if price is not None else None
        pnl = (market_value - cost_value) if market_value is not None else None
        pnl_pct = (pnl / cost_value * 100) if (pnl is not None and cost_value) else None
        if market_value is not None:
            totals[cur] = totals.get(cur, 0.0) + market_value
        rows.append({
            "id": h.id,
            "ticker": h.ticker,
            "symbol": h.ticker.replace(".IS", ""),
            "market": h.market,
            "sector": sector,
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
        })

    # compute weights within each currency bucket
    for r in rows:
        cur = r["currency"]
        if r["market_value"] is not None and totals.get(cur):
            r["weight"] = round(r["market_value"] / totals[cur] * 100, 1)
        else:
            r["weight"] = None

    return {
        "holdings": rows,
        "totals": [{"currency": c, "market_value": round(v, 2)} for c, v in totals.items()],
    }


@router.post("/holdings")
def add_holding(item: HoldingCreate, db: Session = Depends(get_db)):
    ticker = item.ticker.strip().upper()
    holding = LongTermHolding(
        ticker=ticker,
        market=_norm(ticker, item.market),
        shares=item.shares,
        cost_basis=item.cost_basis,
        purchase_date=item.purchase_date,
        notes=item.notes,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return {"id": holding.id, "ticker": holding.ticker}


@router.put("/holdings/{holding_id}")
def update_holding(holding_id: int, item: HoldingUpdate, db: Session = Depends(get_db)):
    holding = db.query(LongTermHolding).filter(LongTermHolding.id == holding_id).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding bulunamadı")
    for field, value in item.dict(exclude_unset=True).items():
        setattr(holding, field, value)
    db.commit()
    return {"id": holding.id}


@router.delete("/holdings/{holding_id}")
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    holding = db.query(LongTermHolding).filter(LongTermHolding.id == holding_id).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding bulunamadı")
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
    return {"watchlist": out}


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


async def _run_scan(tickers: List[str], label: str):
    """Background bulk scan: score each ticker (.info only), cache, stream progress."""
    total = len(tickers)
    count = 0
    errors = 0
    skipped: List[str] = []
    print(f"[Investing] Scan started: {label} ({total} hisse)")
    await _broadcast_scan({"status": "started", "current": 0, "total": total, "ticker": None, "label": label})

    db = SessionLocal()
    try:
        for i, t in enumerate(tickers, 1):
            try:
                overrides = _get_override_fields(db, t)
                # statements not needed for scoring -> fast .info-only fetch
                report = await asyncio.to_thread(
                    fundamental_service.analyze, t, overrides, False
                )
                if report.get("valid"):
                    _upsert_snapshot(db, report)
                    db.commit()
                    count += 1
                else:
                    skipped.append(t.replace(".IS", ""))
            except Exception as e:
                errors += 1
                print(f"[Investing] {t} hata: {e}")
            if i % 10 == 0 or i == total:
                print(f"[Investing] {label}: {i}/{total} (skor={count}, atlanan={len(skipped)}, hata={errors})")
            await _broadcast_scan({
                "status": "running", "current": i, "total": total,
                "ticker": t.replace(".IS", ""), "label": label,
            })
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
        if mkt == "bist":
            # The screener targets the BIST 100 index, not the full ~538 universe.
            from financia.bist100_tickers import get_bist_tickers
            tickers = get_bist_tickers("100")
        else:
            tickers = get_market_tickers(mkt)
        label = get_market_config(mkt)["label"]
    else:
        raise HTTPException(status_code=400, detail="market, tickers veya use_watchlist gerekli")

    if body.limit:
        tickers = tickers[: body.limit]
    if not tickers:
        raise HTTPException(status_code=400, detail="Taranacak hisse yok")

    _scan_state["running"] = True
    asyncio.create_task(_run_scan(tickers, label))
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
    if not holdings:
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
        positions.append({"symbol": h.ticker.replace(".IS", ""), "market": h.market, "sector": sec, "base": base})

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
        [{"symbol": p["symbol"], "market": p["market"], "sector": p["sector"], "weight": _pct(p["base"])} for p in positions],
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
    if len(holdings) < 4:
        warnings.append({"level": "medium", "message": f"Yalnızca {len(holdings)} pozisyon var — çeşitlendirme düşük."})
    if not fx_ok:
        warnings.append({"level": "info", "message": "USD/TRY kuru alınamadı; $ pozisyonlar dönüştürülemedi, ağırlıklar yaklaşıktır."})
    if not warnings:
        warnings.append({"level": "ok", "message": "Belirgin bir yoğunlaşma riski görünmüyor."})

    return {
        "holdings": len(holdings),
        "base_currency": "₺",
        "usdtry": usdtry,
        "total_base": round(total_base, 2),
        "warnings": warnings,
        "sectors": sectors,
        "positions": pos_out,
        "currencies": currencies,
    }
