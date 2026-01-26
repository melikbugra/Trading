from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
import asyncio
from datetime import datetime, timedelta

# Internal modules
from financia.analyzer import StockAnalyzer
from financia.web_api.websocket_manager import manager
from financia.web_api.database import (
    get_db,
    SessionLocal,
    BIST100Recommendation,
    BinanceRecommendation,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationItem(BaseModel):
    ticker: str
    decision: str
    score: float
    divergence_count: int
    price: float
    last_updated: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[RecommendationItem])
def get_recommendations(
    market: str = "bist100", limit: int = 20, db: Session = Depends(get_db)
):
    """
    Get top recommendations from Database.
    """
    if market == "binance":
        model_class = BinanceRecommendation
    else:
        model_class = BIST100Recommendation

    items = (
        db.query(model_class)
        .order_by(model_class.score.desc(), model_class.divergence_count.desc())
        .limit(limit)
        .all()
    )
    return items


def get_engine(market: str):
    from financia.web_api.state import state

    if market == "binance":
        return state.binance_engine
    return state.bist100_engine


async def run_market_scan(market: str = "bist100"):
    """
    Background task to scan market using REAL AI Model and save to DB.
    """
    print(f"[{market.upper()}] Starting Market Scanner...")

    # 1. Broadcast Start
    await manager.broadcast({"type": "SCAN_STARTED", "data": {"market": market}})

    # 2. Clear Old Recommendations for this market
    try:
        with SessionLocal() as db:
            if market == "binance":
                db.query(BinanceRecommendation).delete()
            else:
                db.query(BIST100Recommendation).delete()
            db.commit()
    except Exception as e:
        print(f"DB Clear Error: {e}")

    # 3. Get Engine
    engine = get_engine(market)
    if engine is None:
        print(f"Error: {market.upper()} Model Engine not loaded.")
        await manager.broadcast(
            {
                "type": "SCAN_ERROR",
                "data": {
                    "message": f"{market.upper()} model not ready.",
                    "market": market,
                },
            }
        )
        return

    # 4. Define Tickers
    tickers = []
    if market == "bist100":
        tickers = [
            "AEFES.IS",
            "AGHOL.IS",
            "AKBNK.IS",
            "AKCNS.IS",
            "AKFGY.IS",
            "AKSA.IS",
            "AKSEN.IS",
            "ALARK.IS",
            "ALBRK.IS",
            "ALFAS.IS",
            "ANHYT.IS",
            "ARCLK.IS",
            "ASELS.IS",
            "ASTOR.IS",
            "ASUZU.IS",
            "AYDEM.IS",
            "BAGFS.IS",
            "BASGZ.IS",
            "BERA.IS",
            "BIMAS.IS",
            "BIOEN.IS",
            "BOBET.IS",
            "BRSAN.IS",
            "BRYAT.IS",
            "BUCIM.IS",
            "CANTE.IS",
            "CCOLA.IS",
            "CEMTS.IS",
            "CIMSA.IS",
            "DOHOL.IS",
            "DOAS.IS",
            "ECILC.IS",
            "ECZYT.IS",
            "EGEEN.IS",
            "EKGYO.IS",
            "ENJSA.IS",
            "ENKAI.IS",
            "EREGL.IS",
            "EUREN.IS",
            "FENER.IS",
            "FROTO.IS",
            "GARAN.IS",
            "GENIL.IS",
            "GESAN.IS",
            "GLYHO.IS",
            "GSDHO.IS",
            "GUBRF.IS",
            "GWIND.IS",
            "HALKB.IS",
            "HEKTS.IS",
            "IPEKE.IS",
            "ISCTR.IS",
            "ISDMR.IS",
            "ISFIN.IS",
            "ISGYO.IS",
            "ISMEN.IS",
            "KCAER.IS",
            "KCHOL.IS",
            "KONTR.IS",
            "KONYA.IS",
            "KORDS.IS",
            "KOZAL.IS",
            "KOZAA.IS",
            "KRDMD.IS",
            "KZBGY.IS",
            "MAVI.IS",
            "MGROS.IS",
            "MIATK.IS",
            "ODAS.IS",
            "OTKAR.IS",
            "OYAKC.IS",
            "PENTA.IS",
            "PETKM.IS",
            "PGSUS.IS",
            "PSGYO.IS",
            "QUAGR.IS",
            "SAHOL.IS",
            "SASA.IS",
            "SAYAS.IS",
            "SDTTR.IS",
            "SISE.IS",
            "SKBNK.IS",
            "SMRTG.IS",
            "SOKM.IS",
            "TAVHL.IS",
            "TCELL.IS",
            "THYAO.IS",
            "TKFEN.IS",
            "TOASO.IS",
            "TSKB.IS",
            "TTKOM.IS",
            "TTRAK.IS",
            "TUKAS.IS",
            "TUPRS.IS",
            "TURSG.IS",
            "ULKER.IS",
            "VAKBN.IS",
            "VESBE.IS",
            "VESTL.IS",
            "YEOTK.IS",
            "YKBNK.IS",
            "YYLGD.IS",
            "ZOREN.IS",
        ]
    elif market == "binance":
        tickers = [
            "BTC/USDT",
            "ETH/USDT",
            "BNB/USDT",
            "SOL/USDT",
            "XRP/USDT",
            "ADA/USDT",
            "AVAX/USDT",
            "DOGE/USDT",
            "TRX/USDT",
            "DOT/USDT",
            "MATIC/USDT",
            "LINK/USDT",
            "SHIB/USDT",
            "LTC/USDT",
            "UNI/USDT",
        ]

    # 5. Scan Loop
    count_found = 0
    total_tickers = len(tickers)

    for idx, ticker in enumerate(tickers, 1):
        ticker_display = ticker.replace(".IS", "").replace("/USDT", "")

        try:
            # Log: Starting analysis
            print(
                f"[{market.upper()}] [{idx}/{total_tickers}] Analyzing {ticker_display}..."
            )

            # Broadcast progress to frontend
            await manager.broadcast(
                {
                    "type": "SCAN_PROGRESS",
                    "data": {
                        "market": market,
                        "current": idx,
                        "total": total_tickers,
                        "ticker": ticker_display,
                    },
                }
            )

            # Analyze - run in thread pool to avoid blocking event loop
            result = await asyncio.to_thread(
                engine.analyze_ticker,
                ticker,
                horizon="short",
                use_live=True,
                market=market,
            )

            if not result or "error" in result:
                error_msg = (
                    result.get("error", "Unknown error") if result else "No result"
                )
                print(
                    f"[{market.upper()}] [{idx}/{total_tickers}] {ticker_display}: ERROR - {error_msg}"
                )
                continue

            decision = result.get("decision", "HOLD")
            score = result.get("final_score", 0.0)
            price = result.get("price", 0.0)

            # --- Filtering Logic (Legacy Style) ---
            # Must be BUY/STRONG BUY and Score >= 50
            is_recommended = decision in ["BUY", "STRONG BUY"] and score >= 50

            # Log: Decision result
            status = "RECOMMENDED" if is_recommended else "NOT RECOMMENDED"
            reason = ""
            if not is_recommended:
                if decision not in ["BUY", "STRONG BUY"]:
                    reason = f"(Decision: {decision})"
                elif score < 50:
                    reason = f"(Score: {score:.1f} < 50)"

            print(
                f"[{market.upper()}] [{idx}/{total_tickers}] {ticker_display}: {decision} | Score: {score:.1f} | {status} {reason}"
            )

            if is_recommended:
                # Calculate Divergence manually if needed
                details = result.get("indicator_details", [])
                # Divergence: 1 (Bullish)
                div_count = sum(1 for d in details if d.get("Divergence", 0) == 1)

                # Save to DB
                with SessionLocal() as db:
                    rec = None
                    if market == "binance":
                        rec = BinanceRecommendation(
                            ticker=ticker,
                            score=score,
                            decision=decision,
                            price=price,
                            divergence_count=div_count,
                            last_updated=(
                                datetime.utcnow() + timedelta(hours=3)
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                        )
                    else:
                        rec = BIST100Recommendation(
                            ticker=ticker,
                            score=score,
                            decision=decision,
                            price=price,
                            divergence_count=div_count,
                            last_updated=(
                                datetime.utcnow() + timedelta(hours=3)
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                        )

                    db.add(rec)
                    db.commit()
                count_found += 1

                print(
                    f"[{market.upper()}] [{idx}/{total_tickers}] {ticker_display}: SAVED TO DB (Divergence: {div_count})"
                )

                # Real-time Broadcast
                await manager.broadcast(
                    {
                        "type": "RECOMMENDATION_UPDATE",
                        "data": {
                            "ticker": ticker,
                            "market": market,
                            "decision": decision,
                            "score": score,
                            "divergence_count": div_count,
                            "price": price,
                            "last_updated": datetime.now().strftime("%H:%M"),
                        },
                    }
                )

            # Yield for other tasks
            await asyncio.sleep(0.05)

        except Exception as e:
            print(
                f"[{market.upper()}] [{idx}/{total_tickers}] {ticker_display}: EXCEPTION - {e}"
            )
            continue

    # 6. Notify Finish
    await manager.broadcast(
        {"type": "SCAN_FINISHED", "data": {"count": count_found, "market": market}}
    )
    print(f"[{market.upper()}] Scan Finished. Found {count_found} opportunities.")


@router.post("/scan")
async def start_scan(background_tasks: BackgroundTasks, market: str = "bist100"):
    background_tasks.add_task(run_market_scan, market)
    return {"status": "Scan started", "market": market}


@router.post("/rescan-ticker")
async def rescan_single_ticker(
    ticker: str, market: str = "bist100", db: Session = Depends(get_db)
):
    """
    Re-analyze a single ticker and update in DB.
    """
    print(f"[{market.upper()}] Re-scanning single ticker: {ticker}")

    engine = get_engine(market)
    if engine is None:
        return {"error": f"{market.upper()} model not ready."}

    try:
        # Analyze
        result = await asyncio.to_thread(
            engine.analyze_ticker,
            ticker,
            horizon="short",
            use_live=True,
            market=market,
        )

        if not result or "error" in result:
            error_msg = result.get("error", "Unknown error") if result else "No result"
            return {"error": error_msg}

        decision = result.get("decision", "HOLD")
        score = result.get("final_score", 0.0)
        price = result.get("price", 0.0)

        # Determine if still recommended
        is_recommended = decision in ["BUY", "STRONG BUY"] and score >= 50

        # Get model class
        if market == "binance":
            model_class = BinanceRecommendation
        else:
            model_class = BIST100Recommendation

        # Calculate divergence
        details = result.get("indicator_details", [])
        div_count = sum(1 for d in details if d.get("Divergence", 0) == 1)

        last_updated = (datetime.utcnow() + timedelta(hours=3)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        if is_recommended:
            # Update or insert
            existing = (
                db.query(model_class).filter(model_class.ticker == ticker).first()
            )
            if existing:
                existing.score = score
                existing.decision = decision
                existing.price = price
                existing.divergence_count = div_count
                existing.last_updated = last_updated
            else:
                rec = model_class(
                    ticker=ticker,
                    score=score,
                    decision=decision,
                    price=price,
                    divergence_count=div_count,
                    last_updated=last_updated,
                )
                db.add(rec)
            db.commit()

            # Broadcast update
            await manager.broadcast(
                {
                    "type": "RECOMMENDATION_UPDATE",
                    "data": {
                        "ticker": ticker,
                        "market": market,
                        "decision": decision,
                        "score": score,
                        "divergence_count": div_count,
                        "price": price,
                        "last_updated": datetime.now().strftime("%H:%M"),
                    },
                }
            )

            return {
                "status": "updated",
                "ticker": ticker,
                "decision": decision,
                "score": score,
                "price": price,
                "divergence_count": div_count,
            }
        else:
            # No longer recommended - remove from list
            db.query(model_class).filter(model_class.ticker == ticker).delete()
            db.commit()

            # Broadcast removal
            await manager.broadcast(
                {
                    "type": "RECOMMENDATION_REMOVED",
                    "data": {"ticker": ticker, "market": market},
                }
            )

            return {
                "status": "removed",
                "ticker": ticker,
                "reason": f"No longer meets criteria (Decision: {decision}, Score: {score:.1f})",
            }

    except Exception as e:
        print(f"Error re-scanning {ticker}: {e}")
        return {"error": str(e)}
