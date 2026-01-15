"""
Binance API Router

Handles all Binance (Crypto) related endpoints.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List

from financia.web_api.database import (
    get_db, SessionLocal,
    BinancePortfolioItem, BinanceRecommendation
)
from financia.web_api.websocket_manager import manager
from financia.binance_data_generator import BINANCE_COINS

router = APIRouter(prefix="/binance", tags=["Binance"])

# Pydantic Models
from pydantic import BaseModel
from typing import Optional

class CryptoItem(BaseModel):
    ticker: str  # e.g., BTCUSDT

class PortfolioItem(BaseModel):
    ticker: str
    last_decision: str
    last_price: float
    last_volume: Optional[float] = 0.0
    last_volume_ratio: Optional[float] = 0.0
    last_updated: str
    final_score: Optional[float] = 0.0
    category_scores: Optional[dict] = {}
    indicator_details: Optional[List[dict]] = []
    
    class Config:
        from_attributes = True

class RecommendationItem(BaseModel):
    ticker: str
    score: float
    decision: str
    price: float
    divergence_count: float
    last_updated: str
    
    class Config:
        from_attributes = True

class LiveModeSetting(BaseModel):
    enabled: bool

# Global settings for this market
binance_live_mode = False

# -- Settings --
@router.get("/settings/live-mode")
def get_live_mode():
    return {"enabled": binance_live_mode}

@router.post("/settings/live-mode")
def set_live_mode(setting: LiveModeSetting):
    global binance_live_mode
    binance_live_mode = setting.enabled
    mode_str = "LIVE (Real-time)" if binance_live_mode else "STABLE (Closed Candles)"
    print(f"Binance Live Mode changed to: {mode_str}")
    return {"enabled": binance_live_mode, "message": f"Mode set to {mode_str}"}

# -- Portfolio CRUD --
@router.get("/portfolio", response_model=List[PortfolioItem])
def get_portfolio(db: Session = Depends(get_db)):
    items = db.query(BinancePortfolioItem).all()
    return items

@router.post("/portfolio")
def add_to_portfolio(item: CryptoItem, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    ticker = item.ticker.upper()
    
    # Ensure USDT pair format
    if not ticker.endswith("USDT"):
        ticker += "USDT"
    
    existing = db.query(BinancePortfolioItem).filter(BinancePortfolioItem.ticker == ticker).first()
    if existing:
        raise HTTPException(status_code=400, detail="Coin already in portfolio")
    
    new_item = BinancePortfolioItem(
        ticker=ticker,
        last_decision="PENDING",
        last_price=0.0,
        last_updated=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    )
    db.add(new_item)
    db.commit()
    
    # Trigger analysis in background
    background_tasks.add_task(analyze_single_ticker_db, ticker)
    
    return {"message": f"Added {ticker} to Binance portfolio", "ticker": ticker}

@router.delete("/portfolio/{ticker}")
def remove_from_portfolio(ticker: str, db: Session = Depends(get_db)):
    item = db.query(BinancePortfolioItem).filter(BinancePortfolioItem.ticker == ticker).first()
    if not item:
        raise HTTPException(status_code=404, detail="Coin not found")
    
    db.delete(item)
    db.commit()
    return {"message": f"Removed {ticker} from Binance portfolio"}

@router.post("/portfolio/{ticker}/refresh")
def refresh_ticker(ticker: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    item = db.query(BinancePortfolioItem).filter(BinancePortfolioItem.ticker == ticker).first()
    if not item:
        raise HTTPException(status_code=404, detail="Coin not found")
    
    background_tasks.add_task(analyze_single_ticker_db, ticker)
    return {"message": f"Refresh triggered for {ticker}"}

# -- Recommendations --
@router.get("/recommendations", response_model=List[RecommendationItem])
def get_recommendations(limit: int = 10, db: Session = Depends(get_db)):
    items = db.query(BinanceRecommendation)\
              .filter(BinanceRecommendation.decision.in_(["BUY", "STRONG BUY"]))\
              .order_by(BinanceRecommendation.score.desc())\
              .limit(limit).all()
    return items

@router.post("/recommendations/scan")
def scan_market(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_market_scanner)
    return {"message": "Binance market scan started."}

# -- Analysis Logic --
def get_engine():
    """Get the Binance inference engine from main app"""
    from financia.web_api.main import binance_engine
    return binance_engine

def analyze_single_ticker_core(ticker: str):
    engine = get_engine()
    if engine is None:
        print("Binance engine not loaded (model not trained yet)")
        return None
    
    try:
        # Binance uses 'short' horizon which maps to 5m candles
        result = engine.analyze_ticker(ticker, horizon='short', use_live=binance_live_mode)
        return result
    except Exception as e:
        print(f"Binance Analysis Error {ticker}: {e}")
        return None

def analyze_single_ticker_db(ticker: str):
    print(f"[Binance] Analyzing: {ticker}...")
    result = analyze_single_ticker_core(ticker)
    
    # If no model yet, just update with placeholder
    if result is None:
        print(f"[Binance] No model available for {ticker}, skipping analysis")
        return

    try:
        db = SessionLocal()
        item = db.query(BinancePortfolioItem).filter(BinancePortfolioItem.ticker == ticker).first()
        
        if item:
            if "error" in result:
                item.last_decision = "ERROR"
            else:
                new_decision = result["decision"]
                old_decision = item.last_decision
                
                # For now, no email alerts for crypto (can enable later)
                if old_decision != new_decision and old_decision != "PENDING":
                    print(f"[Binance] Signal Change: {ticker}: {old_decision} -> {new_decision}")
                
                item.last_decision = new_decision
                item.last_price = result["price"]
                item.last_volume = result.get("volume", 0.0)
                item.last_volume_ratio = result.get("volume_ratio", 0.0)
                item.last_updated = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                item.final_score = result.get("final_score", 0.0)
                item.category_scores = result.get("category_scores", {})
                item.indicator_details = result.get("indicator_details", [])
            
            db.commit()
            
            # Broadcast via WebSocket
            try:
                import asyncio
                payload = {
                    "market": "binance",
                    "ticker": item.ticker,
                    "last_decision": item.last_decision,
                    "last_price": item.last_price,
                    "last_volume": item.last_volume,
                    "last_volume_ratio": item.last_volume_ratio,
                    "last_updated": item.last_updated,
                    "final_score": item.final_score,
                    "category_scores": item.category_scores,
                    "indicator_details": item.indicator_details
                }
                loop = asyncio.new_event_loop()
                loop.run_until_complete(manager.broadcast({"type": "PORTFOLIO_UPDATE", "data": payload}))
                loop.close()
            except Exception as e:
                print(f"WS Broadcast error: {e}")
                
        db.close()
    except Exception as e:
        print(f"[Binance] DB Error for {ticker}: {e}")

def run_market_scanner():
    print("[Binance] Starting Market Scanner...")
    
    engine = get_engine()
    if engine is None:
        print("[Binance] No model available, skipping scan")
        return
    
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(manager.broadcast({"type": "SCAN_STARTED", "data": {"market": "binance"}}))
        loop.close()
    except:
        pass
    
    db = SessionLocal()
    
    for ticker in BINANCE_COINS:
        try:
            result = analyze_single_ticker_core(ticker)
            if result and "error" not in result:
                existing = db.query(BinanceRecommendation).filter(BinanceRecommendation.ticker == ticker).first()
                
                if existing:
                    existing.score = result.get("final_score", 0.0)
                    existing.decision = result.get("decision", "HOLD")
                    existing.price = result.get("price", 0.0)
                    existing.divergence_count = result.get("divergence_count", 0)
                    existing.last_updated = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                else:
                    new_rec = BinanceRecommendation(
                        ticker=ticker,
                        score=result.get("final_score", 0.0),
                        decision=result.get("decision", "HOLD"),
                        price=result.get("price", 0.0),
                        divergence_count=result.get("divergence_count", 0),
                        last_updated=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                    )
                    db.add(new_rec)
                
                db.commit()
        except Exception as e:
            print(f"[Binance] Scanner error for {ticker}: {e}")
    
    db.close()
    
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(manager.broadcast({"type": "SCAN_COMPLETED", "data": {"market": "binance"}}))
        loop.close()
    except:
        pass
    
    print("[Binance] Market Scanner Complete.")

def run_analysis_job():
    """Background job to analyze all portfolio items"""
    db = SessionLocal()
    items = db.query(BinancePortfolioItem).all()
    db.close()
    
    for item in items:
        analyze_single_ticker_db(item.ticker)
